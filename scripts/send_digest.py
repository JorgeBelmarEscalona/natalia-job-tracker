#!/usr/bin/env python3
"""Envía el resumen diario de postulaciones a Natalia por correo (Gmail SMTP)
y actualiza data/.notified.json con las ofertas ya avisadas."""

import json
import os
import smtplib
import sys
from email.mime.text import MIMEText
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OFERTAS_PATH = ROOT / "data" / "ofertas.json"
NOTIFIED_PATH = ROOT / "data" / ".notified.json"
SITE_URL = "https://jorgebelmarescalona.github.io/natalia-job-tracker/"

ACCENT = "#6B4CE0"
ACCENT_DARK = "#2B1B63"


def load_json(path, default):
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def build_html(nuevas, total, pendientes):
    if nuevas:
        rows = "".join(
            f"""
            <tr>
              <td style="padding:10px 12px;border-bottom:1px solid #E4E1F3;">
                <div style="font-weight:600;color:#262433;font-size:14px;">{o['cargo']}</div>
                <div style="color:#6B6880;font-size:12.5px;margin-top:2px;">{o['empresa']} · {o['comuna']}</div>
              </td>
              <td style="padding:10px 12px;border-bottom:1px solid #E4E1F3;text-align:right;white-space:nowrap;">
                <a href="{o['link']}" style="color:{ACCENT_DARK};font-weight:600;font-size:12.5px;text-decoration:none;">Ver oferta &#8599;</a>
              </td>
            </tr>"""
            for o in nuevas
        )
        nuevas_block = f"""
        <table style="width:100%;border-collapse:collapse;margin-top:14px;">
          {rows}
        </table>"""
        headline = f"{len(nuevas)} oferta{'s' if len(nuevas) != 1 else ''} nueva{'s' if len(nuevas) != 1 else ''} hoy"
    else:
        nuevas_block = """
        <p style="color:#6B6880;font-size:13.5px;margin-top:14px;">
          Sin ofertas nuevas hoy. Sigue pendiente revisar las que ya tienes en el tablero.
        </p>"""
        headline = "Sin ofertas nuevas hoy"

    return f"""\
<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:520px;margin:0 auto;">
  <div style="background:linear-gradient(135deg,{ACCENT},{ACCENT_DARK});padding:22px 24px;border-radius:14px 14px 0 0;">
    <h1 style="color:#fff;font-size:18px;margin:0 0 4px;">Resumen de postulaciones &#x1F49C;</h1>
    <p style="color:rgba(255,255,255,.85);font-size:13px;margin:0;">{headline}</p>
  </div>
  <div style="background:#FFFFFF;border:1px solid #E4E1F3;border-top:none;border-radius:0 0 14px 14px;padding:20px 24px;">
    <p style="color:#262433;font-size:13.5px;line-height:1.6;margin:0;">
      Tienes <strong>{total}</strong> ofertas registradas en total, <strong>{pendientes}</strong> pendientes por postular.
    </p>
    {nuevas_block}
    <a href="{SITE_URL}" style="display:inline-block;margin-top:20px;background:{ACCENT_DARK};color:#fff;
       padding:10px 18px;border-radius:10px;text-decoration:none;font-size:13.5px;font-weight:600;">
      Abrir tablero de postulaciones
    </a>
  </div>
</div>"""


def main():
    gmail_user = os.environ.get("GMAIL_USER")
    gmail_pass = os.environ.get("GMAIL_APP_PASSWORD")
    recipient = os.environ.get("NATALIA_EMAIL")

    if not gmail_user or not gmail_pass or not recipient:
        print("Faltan variables de entorno GMAIL_USER / GMAIL_APP_PASSWORD / NATALIA_EMAIL", file=sys.stderr)
        sys.exit(1)

    ofertas = load_json(OFERTAS_PATH, [])
    notified_ids = set(load_json(NOTIFIED_PATH, []))

    nuevas = [o for o in ofertas if o.get("id") not in notified_ids]
    total = len(ofertas)
    pendientes = len(ofertas) - len(notified_ids & {o["id"] for o in ofertas})

    html = build_html(nuevas, total, pendientes)

    msg = MIMEText(html, "html", "utf-8")
    msg["Subject"] = (
        f"{len(nuevas)} oferta{'s' if len(nuevas) != 1 else ''} nueva{'s' if len(nuevas) != 1 else ''} para ti"
        if nuevas
        else "Resumen de postulaciones (sin novedades hoy)"
    )
    msg["From"] = gmail_user
    msg["To"] = recipient

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_user, gmail_pass)
        server.sendmail(gmail_user, [recipient], msg.as_string())

    print(f"Correo enviado a {recipient} ({len(nuevas)} nuevas de {total} totales).")

    updated_notified = list(notified_ids | {o["id"] for o in ofertas if o.get("id")})
    save_json(NOTIFIED_PATH, updated_notified)


if __name__ == "__main__":
    main()
