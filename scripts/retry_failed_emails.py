"""Reintenta el envío de correos guardados en failed_emails.log vía SMTP.

Formato en failed_emails.log:
{iso_ts} | destinatario | subject: {subject}
{html}

---

Uso:
  python scripts/retry_failed_emails.py
"""
from __future__ import annotations

import os
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

FAILED_PATH = Path(__file__).resolve().parent.parent / "failed_emails.log"


def send_via_smtp(from_email: str, password: str, to_email: str, subject: str, html: str) -> bool:
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

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


def parse_failed_file(contents: str) -> list[dict]:
    parts = [p.strip() for p in contents.split("\n\n---\n") if p.strip()]
    entries = []
    for p in parts:
        lines = p.splitlines()
        if not lines:
            continue
        header = lines[0]
        try:
            ts, rest = header.split("|", 1)
            ts = ts.strip()
            rest = rest.strip()
            if "subject:" in rest:
                dest_part, subj_part = rest.split("subject:", 1)
                destinatario = dest_part.strip().rstrip("|").strip()
                subject = subj_part.strip()
            else:
                parts2 = rest.split("|")
                destinatario = parts2[0].strip()
                subject = "(sin asunto)"
        except Exception:
            continue
        html = "\n".join(lines[1:]).strip()
        entries.append({"ts": ts, "to": destinatario, "subject": subject, "html": html})
    return entries


def main() -> None:
    if not FAILED_PATH.exists():
        print("No existe failed_emails.log; nada que reintentar.")
        return

    entries = parse_failed_file(FAILED_PATH.read_text(encoding="utf-8"))
    if not entries:
        print("No se encontraron entradas parseables en failed_emails.log")
        return

    print(f"Encontradas {len(entries)} entradas para reintentar.")

    email_sender = os.getenv("EMAIL_SENDER", "enlacepqrs1755@gmail.com")
    email_password = os.getenv("EMAIL_PASSWORD")
    if not email_password:
        print("ERROR: configure EMAIL_PASSWORD en .env")
        return

    remaining = []
    for e in entries:
        to = e["to"]
        print(f"Intentando SMTP -> {to}")
        if send_via_smtp(email_sender, email_password, to, e["subject"], e["html"]):
            print("Enviado:", to)
            time.sleep(0.5)
        else:
            print("No enviado:", to)
            remaining.append(e)

    if remaining:
        print(f"Reescribiendo {len(remaining)} entradas restantes en {FAILED_PATH}")
        with open(FAILED_PATH, "w", encoding="utf-8") as f:
            for r in remaining:
                f.write(f"{r['ts']} | {r['to']} | subject: {r['subject']}\n{r['html']}\n\n---\n")
    else:
        print("Todos los correos fueron enviados; eliminando archivo.")
        try:
            FAILED_PATH.unlink()
        except Exception as e:
            print("No se pudo eliminar el archivo:", e)


if __name__ == "__main__":
    main()
