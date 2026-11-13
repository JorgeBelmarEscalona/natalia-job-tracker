#!/usr/bin/env python3
"""Mantiene data/ofertas.json solo con ofertas vigentes de chiletrabajos.cl.

En cada corrida:
1. Depura las ofertas ya guardadas: saca las publicadas hace más de DIAS_MAX
   días, las que el sitio ya cerró y las que vienen de portales donde no se
   puede comprobar la vigencia (ej. links de LinkedIn sacados de un buscador).
2. Busca ofertas nuevas publicadas hace <= DIAS_MAX días y las agrega. No requiere login ni scraping de
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
import urllib.error
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
DIAS_MAX = 7

# Cargos que no calzan con el perfil (analista junior a semi-senior).
CARGOS_EXCLUIDOS = [
    "practica",
    "practicante",
    "pasantia",
    "jefe",
    "jefa",
    "jefatura",
    "gerente",
    "subgerente",
    "director",
    "head of",
]

# Frases con las que el sitio marca un aviso que ya no recibe postulaciones.
MARCAS_CERRADA = [
    "oferta expirada",
    "oferta caducada",
    "oferta finalizada",
    "aviso expirado",
    "aviso caducado",
    "aviso finalizado",
    "ya no esta disponible",
    "ya no se encuentra disponible",
    "no esta disponible",
    "proceso cerrado",
]

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
    return get_con_url(url)[0]


def get_con_url(url: str) -> tuple[str, str]:
    """Devuelve (html, url_final) para detectar redirecciones."""
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace"), resp.geturl()


def fecha_ok(fecha: str) -> bool:
    try:
        dt = datetime.strptime(fecha[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        return False
    return dt >= datetime.now() - timedelta(days=DIAS_MAX)


def motivo_baja(oferta: dict) -> str | None:
    """Devuelve por qué una oferta guardada debe salir del tablero, o None si sigue vigente.

    Ante un error de red pasajero se conserva la oferta: se vuelve a revisar
    en la corrida siguiente.
    """
    link = oferta.get("link") or ""
    if not link.startswith(BASE + "/trabajo/"):
        return "portal sin verificación de vigencia"
    if not fecha_ok(oferta.get("fecha", "")):
        return f"publicada hace más de {DIAS_MAX} días"
    try:
        pagina, url_final = get_con_url(link)
    except urllib.error.HTTPError as e:
        if e.code in (404, 410):
            return f"el aviso ya no existe (HTTP {e.code})"
        print(f"  ? no se pudo revisar {link}: HTTP {e.code}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  ? no se pudo revisar {link}: {e}", file=sys.stderr)
        return None

    if "/trabajo/" not in url_final:
        return "el aviso redirige fuera de la oferta"
    jp = extraer_jobposting(pagina)
    if not jp:
        return "el aviso ya no publica la oferta"
    vence = str(jp.get("validThrough") or "")[:10]
    if vence:
        try:
            if datetime.strptime(vence, "%Y-%m-%d").date() < datetime.now().date():
                return f"venció el {vence}"
        except ValueError:
            pass
    texto = normalizar(re.sub(r"<[^>]+>", " ", pagina))
    for marca in MARCAS_CERRADA:
        if marca in texto:
            return f"el sitio la marca como cerrada ('{marca}')"
    if not fecha_ok(str(jp.get("datePosted") or "")):
        return f"publicada hace más de {DIAS_MAX} días"
    return None


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
    palabras_cargo = f" {re.sub(r'[^a-z0-9]+', ' ', normalizar(cargo))} "
    if any(f" {excl} " in palabras_cargo for excl in CARGOS_EXCLUIDOS):
        return None  # practicas y jefaturas quedan fuera del perfil

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
    guardadas = json.loads(DATA_PATH.read_text()) if DATA_PATH.exists() else []

    print(f"Revisando vigencia de {len(guardadas)} ofertas guardadas")
    existentes = []
    bajas: dict[str, int] = {}
    for oferta in guardadas:
        motivo = motivo_baja(oferta)
        if motivo is None:
            existentes.append(oferta)
            time.sleep(0.5)
        else:
            clave = re.sub(r"\(.*\)|\d{4}-\d{2}-\d{2}", "", motivo).strip()
            bajas[clave] = bajas.get(clave, 0) + 1
            print(f"  - {oferta.get('cargo')} ({oferta.get('fecha')}): {motivo}")
    for clave, n in sorted(bajas.items()):
        print(f"  = {n} fuera: {clave}")
    print(f"  = {len(existentes)} siguen vigentes\n")

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

    if nuevas_ofertas or len(existentes) != len(guardadas):
        todas = existentes + nuevas_ofertas
        DATA_PATH.write_text(json.dumps(todas, ensure_ascii=False, indent=2) + "\n")
    print(
        f"\n{len(nuevas_ofertas)} ofertas nuevas, {len(guardadas) - len(existentes)} dadas de baja, "
        f"{len(existentes) + len(nuevas_ofertas)} vigentes en {DATA_PATH.name}"
    )


if __name__ == "__main__":
    main()
