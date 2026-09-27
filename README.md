# Postulaciones de Natalia

Tablero para registrar ofertas laborales (Control de Gestión / Finanzas) y el estado de cada postulación.

Sitio publicado: https://jorgebelmarescalona.github.io/natalia-job-tracker/

## Cómo funciona

- El estado de cada oferta (Nueva, Postulada, En proceso, Rechazada, Oferta recibida) y las notas se guardan
  **en el navegador del dispositivo que lo usa** (localStorage), no en un servidor.
- Usa los botones **Exportar** / **Importar** para respaldar la información o pasarla a otro computador.
- `data/ofertas.json` es la lista compartida de ofertas detectadas (se actualiza agregando entradas ahí).
  Al abrir el sitio, cualquier oferta nueva de ese archivo que no esté ya en el tablero se agrega sola,
  sin tocar el progreso de las que ya están.
- `.github/workflows/daily-email.yml` corre todos los días y envía un correo con las ofertas nuevas
  (o un aviso de que no hubo novedades). Usa `scripts/send_digest.py` y Gmail SMTP.

## Configurar el correo automático (una sola vez)

Se necesitan 3 secretos del repositorio (Settings → Secrets and variables → Actions → New repository secret):

- `GMAIL_USER`: la cuenta Gmail que envía los correos.
- `GMAIL_APP_PASSWORD`: una "contraseña de aplicación" de esa cuenta (no la contraseña normal).
  Se genera en https://myaccount.google.com/apppasswords (requiere verificación en 2 pasos activada).
- `NATALIA_EMAIL`: el correo de Natalia que recibe el resumen.

Una vez configurados, el flujo corre solo cada día (`cron` en el workflow) y también se puede lanzar a mano
desde la pestaña **Actions → Resumen diario por correo → Run workflow**.
