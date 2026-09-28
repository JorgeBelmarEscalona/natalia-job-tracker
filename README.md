# Postulaciones de Natalia

Tablero para registrar ofertas laborales (Control de Gestión / Finanzas) y el estado de cada postulación.

Sitio publicado: https://jorgebelmarescalona.github.io/natalia-job-tracker/

## Cómo funciona

- El estado de cada oferta (Nueva, Postulada, En proceso, Rechazada, Oferta recibida) y las notas se guardan
  **en el navegador del dispositivo que lo usa** (localStorage), no en un servidor.
- Usa los botones **Exportar** / **Importar** para respaldar la información o pasarla a otro computador.
- `data/ofertas.json` es la lista compartida de ofertas detectadas. **Se llena sola**: cada corrida del
  workflow ejecuta primero `scripts/buscar_ofertas.py`, que busca en chiletrabajos.cl avisos de
  Control de Gestión / Finanzas / Contabilidad / Administración publicados en los últimos 10 días en la
  Región Metropolitana, y los agrega automáticamente (sin login ni intervención manual).
  Al abrir el sitio, cualquier oferta nueva de ese archivo que no esté ya en el tablero se agrega sola,
  sin tocar el progreso de las que ya están.
  - La comuna exacta rara vez viene declarada en el aviso (la mayoría solo dice "Santiago"), así que el
    filtro de ubicación no es estricto: se guarda la comuna cuando el aviso la menciona (ej. La Reina,
    Ñuñoa, Providencia, Las Condes) y si no, queda como "Santiago (RM)" para revisar la dirección en el
    link antes de postular.
- `.github/workflows/daily-email.yml` corre todos los días: busca ofertas nuevas, envía un correo con las
  que aún no se habían notificado (o un aviso de que no hubo novedades), y guarda los cambios en el
  repositorio. Usa `scripts/buscar_ofertas.py` + `scripts/send_digest.py` y Gmail SMTP.

## Configurar el correo automático (una sola vez)

Se necesitan 3 secretos del repositorio (Settings → Secrets and variables → Actions → New repository secret):

- `GMAIL_USER`: la cuenta Gmail que envía los correos.
- `GMAIL_APP_PASSWORD`: una "contraseña de aplicación" de esa cuenta (no la contraseña normal).
  Se genera en https://myaccount.google.com/apppasswords (requiere verificación en 2 pasos activada).
- `NATALIA_EMAIL`: el correo de Natalia que recibe el resumen.

Una vez configurados, el flujo corre solo cada día (`cron` en el workflow) y también se puede lanzar a mano
desde la pestaña **Actions → Resumen diario por correo → Run workflow**.
