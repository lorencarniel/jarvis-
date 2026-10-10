import imaplib
import smtplib
import email
from email.mime.text import MIMEText
from email.header import decode_header
from pathlib import Path
import json

import memory as mem


def is_configured():
    addr = mem.get_config("gmail_address")
    pwd = mem.get_config("gmail_app_password")
    return bool(addr and pwd)


def is_authenticated():
    return is_configured()


def _get_creds():
    addr = mem.get_config("gmail_address")
    pwd = mem.get_config("gmail_app_password")
    if not addr or not pwd:
        return None, None
    return addr, pwd


def read_emails(count=5):
    addr, pwd = _get_creds()
    if not addr:
        return {"error": "Gmail no configurado. Usa /gmail tu@gmail.com tu-app-password en el chat."}

    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(addr, pwd)
        mail.select("inbox")

        _, data = mail.search(None, "ALL")
        mail_ids = data[0].split()
        latest = mail_ids[-count:] if len(mail_ids) >= count else mail_ids
        latest.reverse()

        emails = []
        for mid in latest:
            _, msg_data = mail.fetch(mid, "(RFC822)")
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)

            subject = ""
            raw_subject = msg["Subject"]
            if raw_subject:
                decoded = decode_header(raw_subject)
                subject = "".join(
                    part.decode(enc or "utf-8") if isinstance(part, bytes) else part
                    for part, enc in decoded
                )

            from_addr = msg["From"] or "Desconocido"
            date = msg["Date"] or ""

            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        payload = part.get_payload(decode=True)
                        if payload:
                            body = payload.decode("utf-8", errors="replace")[:300]
                        break
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    body = payload.decode("utf-8", errors="replace")[:300]

            emails.append({
                "from": from_addr,
                "subject": subject,
                "date": date,
                "snippet": body.strip()
            })

        mail.logout()
        return {"emails": emails}

    except imaplib.IMAP4.error as e:
        return {"error": f"Error de autenticacion Gmail: {e}. Verifica tu App Password."}
    except Exception as e:
        return {"error": f"Error leyendo emails: {e}"}


def send_email(to, subject, body):
    addr, pwd = _get_creds()
    if not addr:
        return {"error": "Gmail no configurado"}

    try:
        msg = MIMEText(body)
        msg["From"] = addr
        msg["To"] = to
        msg["Subject"] = subject

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(addr, pwd)
            server.sendmail(addr, to, msg.as_string())

        return {"success": True}

    except smtplib.SMTPAuthenticationError:
        return {"error": "Error de autenticacion. Verifica tu App Password."}
    except Exception as e:
        return {"error": f"Error enviando email: {e}"}
