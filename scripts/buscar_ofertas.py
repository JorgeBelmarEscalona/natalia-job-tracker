#!/usr/bin/env python3
"""Busca ofertas nuevas en chiletrabajos.cl y las agrega a data/ofertas.json.

Filtra por: publicadas hace <= DIAS_MAX días, y que el cuerpo de la oferta
mencione una comuna cercana a La Reina. No requiere login ni scraping de
sitios que lo prohíben (revisar robots.txt); solo usa chiletrabajos.cl, que
permite user-agents genéricos en estas rutas.
"""
from __future__ import annotations

import html
import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

BASE = "https://www.chiletrabajos.cl"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; natalia-job-tracker/1.0)"}

PALABRAS_CLAVE = [
    "control de gestion",
    "analista finanzas",
    "analista control de gestion",
    "administracion y finanzas",
    "contabilidad y finanzas",
]

# fecha=6 -> "Hace un mes" (el filtro mas amplio del sitio); el recorte real
# a DIAS_MAX dias se hace despues con la fecha exacta de cada oferta.
FECHA_PARAM = "6"
DIAS_MAX = 10

CARGOS_RELEVANTES = [
    "control de gestion",
    "finanza",
    "contab",
    "administra",
    "tesorer",
    "cobranza",
    "facturacion",
    "presupuesto",
    "auditor",
    "riesgo",
]

COMUNAS_CERCA = {
    "la reina": "La Reina",
    "nunoa": "Ñuñoa",
    "ñuñoa": "Ñuñoa",
    "penalolen": "Peñalolén",
    "peñalolen": "Peñalolén",
    "las condes": "Las Condes",
    "providencia": "Providencia",
    "macul": "Macul",
    "vitacura": "Vitacura",
}

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "ofertas.json"


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in texto if not unicodedata.combining(c))


def get(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


def buscar_links(palabra: str) -> set[str]:
    q = urllib.parse.urlencode({"2": palabra, "fecha": FECHA_PARAM})
    url = f"{BASE}/encuentra-un-empleo?{q}"
    try:
        pagina = get(url)
    except Exception as e:
        print(f"  ! error buscando '{palabra}': {e}", file=sys.stderr)
        return set()
    return set(re.findall(r'https://www\.chiletrabajos\.cl/trabajo/([a-z0-9-]+)', pagina))


def extraer_jobposting(pagina: str) -> dict | None:
    """Devuelve el bloque JSON-LD @type=JobPosting de la propia oferta.

    Es la única fuente confiable: el resto de la página incluye ofertas
    relacionadas de OTRAS comunas (sidebar/footer) que contaminan cualquier
    búsqueda de texto sobre el HTML completo.
    """
    for bloque in re.findall(
        r"<script type=['\"]application/ld\+json['\"]>(.*?)</script>", pagina, re.S
    ):
        try:
            data = json.loads(bloque.strip())
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("@type") == "JobPosting":
            return data
    return None


def detalle_oferta(slug: str) -> dict | None:
    url = f"{BASE}/trabajo/{slug}"
    try:
        pagina = get(url)
    except Exception as e:
        print(f"  ! error en detalle {slug}: {e}", file=sys.stderr)
        return None

    jp = extraer_jobposting(pagina)
    if not jp:
        return None

    fecha_raw = jp.get("datePosted", "")
    try:
        fecha_dt = datetime.strptime(fecha_raw[:10], "%Y-%m-%d")
    except ValueError:
        return None
    if fecha_dt < datetime.now() - timedelta(days=DIAS_MAX):
        return None
    fecha = fecha_dt.strftime("%Y-%m-%d")

    cargo = html.unescape(jp.get("title", slug)).strip()
    industria = jp.get("industry", "")

    cargo_norm = normalizar(f"{cargo} {industria}")
    if not any(clave in cargo_norm for clave in CARGOS_RELEVANTES):
        return None  # el titulo no calza con el perfil buscado (control de gestion/finanzas)

    empresa = html.unescape((jp.get("hiringOrganization") or {}).get("name", "Empresa no especificada"))

    direccion = (jp.get("jobLocation") or {}).get("address") or {}
    region = normalizar(direccion.get("addressRegion", ""))
    localidad = direccion.get("addressLocality", "")
    if "rm" not in region and "metropolitana" not in region and "santiago" not in normalizar(localidad):
        return None  # oferta fuera de la Región Metropolitana

    # La comuna exacta rara vez aparece declarada; se busca en la descripción
    # real de ESTA oferta (nunca en el resto del HTML) y si no aparece se
    # deja la localidad genérica para que Natalia revise la dirección en el link.
    texto_propio = normalizar(f"{localidad} {jp.get('description', '')}")
    comuna = html.unescape(localidad) if localidad else "Santiago (RM)"
    for clave, nombre in COMUNAS_CERCA.items():
        if clave in texto_propio:
            comuna = nombre
            break

    return {
        "id": slug,
        "fecha": fecha,
        "cargo": cargo,
        "empresa": empresa,
        "comuna": comuna,
        "link": url,
    }


def main():
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    existentes = json.loads(DATA_PATH.read_text()) if DATA_PATH.exists() else []
    ids_existentes = {o["id"] for o in existentes} | {o.get("link") for o in existentes}

    slugs_candidatos: set[str] = set()
    for palabra in PALABRAS_CLAVE:
        print(f"Buscando: {palabra}")
        nuevos = buscar_links(palabra)
        print(f"  -> {len(nuevos)} avisos encontrados")
        slugs_candidatos |= nuevos
        time.sleep(1)

    nuevas_ofertas = []
    for slug in sorted(slugs_candidatos):
        if slug in ids_existentes:
            continue
        oferta = detalle_oferta(slug)
        time.sleep(0.5)
        if oferta and oferta["link"] not in ids_existentes and oferta["id"] not in ids_existentes:
            nuevas_ofertas.append(oferta)
            ids_existentes.add(oferta["id"])
            print(f"  + {oferta['cargo']} ({oferta['comuna']}, {oferta['fecha']})")

    if nuevas_ofertas:
        todas = existentes + nuevas_ofertas
        DATA_PATH.write_text(json.dumps(todas, ensure_ascii=False, indent=2) + "\n")
        print(f"\n{len(nuevas_ofertas)} ofertas nuevas agregadas a {DATA_PATH}")
    else:
        print("\nNo se encontraron ofertas nuevas que cumplan los filtros.")


if __name__ == "__main__":
    main()
