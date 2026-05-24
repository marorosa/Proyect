"""Script para reintentar el envío de correos guardados en failed_emails.log.

Formato esperado en failed_emails.log (generado por la app):
{iso_ts} | destinatario | subject: {subject}\n{html}\n\n---\n
Uso:
  python scripts/resend_failed_emails.py

El script intenta SendGrid si encuentra `SENDGRID_API_KEY` en el .env;
si no, intenta SMTP usando `EMAIL_SENDER` + `EMAIL_PASSWORD`.
Si un correo se envía con éxito se elimina del log; los fallos se reescriben.
"""
from __future__ import annotations
import os
from pathlib import Path
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json

FAILED_PATH = Path(__file__).resolve().parent.parent / "failed_emails.log"


def send_via_smtp(from_email: str, password: str, to_email: str, subject: str, html: str) -> bool:
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_email
        msg["To"] = to_email
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP(smtp_server, smtp_port, timeout=10) as s:
            s.starttls()
            s.login(from_email, password)
            s.sendmail(from_email, to_email, msg.as_string())
        return True
    except Exception as e:
        print("SMTP send error:", e)
        return False


def send_via_sendgrid(api_key: str, from_email: str, to_email: str, subject: str, html: str) -> bool:
    try:
        import requests
        payload = {
            "personalizations": [{"to": [{"email": to_email}]}],
            "from": {"email": from_email},
            "subject": subject,
            "content": [{"type": "text/html", "value": html}],
        }
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        resp = requests.post("https://api.sendgrid.com/v3/mail/send", json=payload, headers=headers, timeout=10)
        return resp.status_code in (200, 202)
    except Exception as e:
        print("SendGrid send error:", e)
        return False


def parse_failed_file(contents: str) -> list[dict]:
    parts = [p.strip() for p in contents.split("\n\n---\n") if p.strip()]
    entries = []
    for p in parts:
        lines = p.splitlines()
        if not lines:
            continue
        header = lines[0]
        try:
            # formato: {iso_ts} | destinatario | subject: {subject}
            ts, rest = header.split("|", 1)
            ts = ts.strip()
            rest = rest.strip()
            if "subject:" in rest:
                dest_part, subj_part = rest.split("subject:", 1)
                destinatario = dest_part.strip().rstrip("|").strip()
                subject = subj_part.strip()
            else:
                # fallback
                parts2 = rest.split("|")
                destinatario = parts2[0].strip()
                subject = "(sin asunto)"
        except Exception:
            # si no cumple formato, saltamos
            continue
        html = "\n".join(lines[1:]).strip()
        entries.append({"ts": ts, "to": destinatario, "subject": subject, "html": html})
    return entries


def main():
    if not FAILED_PATH.exists():
        print("No existe failed_emails.log; nada que reintentar.")
        return

    contents = FAILED_PATH.read_text(encoding="utf-8")
    entries = parse_failed_file(contents)
    if not entries:
        print("No se encontraron entradas parseables en failed_emails.log")
        return

    print(f"Encontradas {len(entries)} entradas para reintentar.")

    sendgrid_key = os.getenv("SENDGRID_API_KEY")
    email_sender = os.getenv("EMAIL_SENDER", "enlacepqrs1755@gmail.com")
    email_password = os.getenv("EMAIL_PASSWORD")

    remaining = []
    for e in entries:
        to = e["to"]
        subj = e["subject"]
        html = e["html"]
        sent = False
        # Prefer SendGrid if available
        if sendgrid_key:
            print(f"Intentando SendGrid -> {to}")
            sent = send_via_sendgrid(sendgrid_key, email_sender, to, subj, html)
            if sent:
                print("Enviado vía SendGrid:", to)
                time.sleep(0.5)
                continue
        # Else try SMTP if password present
        if email_password:
            print(f"Intentando SMTP -> {to}")
            sent = send_via_smtp(email_sender, email_password, to, subj, html)
            if sent:
                print("Enviado vía SMTP:", to)
                time.sleep(0.5)
                continue

        print("No enviado:", to)
        remaining.append(e)

    # Reescribir archivo con los que quedaron
    if remaining:
        print(f"Reescribiendo {len(remaining)} entradas restantes en {FAILED_PATH}")
        with open(FAILED_PATH, "w", encoding="utf-8") as f:
            for r in remaining:
                f.write(f"{r['ts']} | {r['to']} | subject: {r['subject']}\n{r['html']}\n\n---\n")
    else:
        print("Todos los correos reintentados fueron enviados; eliminando archivo.")
        try:
            FAILED_PATH.unlink()
        except Exception as e:
            print("No se pudo eliminar el archivo:", e)


if __name__ == '__main__':
    main()
