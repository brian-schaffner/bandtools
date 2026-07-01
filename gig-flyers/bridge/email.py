"""Send flyer images via email (Mail.app or SMTP)."""

from __future__ import annotations

import os
import smtplib
import subprocess
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path


def _recipient() -> str:
    return os.getenv("EMAIL_RECIPIENT", os.getenv("IMESSAGE_RECIPIENT", "")).strip()


def send_via_mail_app(image_path: Path, subject: str, body: str) -> None:
    recipient = _recipient()
    if not recipient:
        raise RuntimeError("EMAIL_RECIPIENT or IMESSAGE_RECIPIENT is not set")

    path_escaped = str(image_path.resolve()).replace("\\", "\\\\").replace('"', '\\"')
    subject_escaped = subject.replace("\\", "\\\\").replace('"', '\\"')
    body_escaped = body.replace("\\", "\\\\").replace('"', '\\"')
    recipient_escaped = recipient.replace("\\", "\\\\").replace('"', '\\"')

    script = f'''
tell application "Mail"
    set newMessage to make new outgoing message with properties {{subject:"{subject_escaped}", content:"{body_escaped}", visible:false}}
    tell newMessage
        make new to recipient at end of to recipients with properties {{address:"{recipient_escaped}"}}
        tell content
            make new attachment with properties {{file name:POSIX file "{path_escaped}"}} at after the last paragraph
        end tell
    end tell
    send newMessage
end tell
'''
    subprocess.run(["osascript", "-e", script], check=True, capture_output=True, text=True)


def send_via_smtp(image_path: Path, subject: str, body: str) -> None:
    host = os.getenv("SMTP_HOST", "").strip()
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").strip()
    recipient = _recipient()
    sender = os.getenv("EMAIL_FROM", user or "gig-flyers@localhost").strip()

    if not host or not recipient:
        raise RuntimeError("SMTP_HOST and recipient required for SMTP delivery")

    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(body, "plain"))

    with image_path.open("rb") as f:
        part = MIMEApplication(f.read(), Name=image_path.name)
    part["Content-Disposition"] = f'attachment; filename="{image_path.name}"'
    msg.attach(part)

    with smtplib.SMTP(host, port, timeout=30) as smtp:
        if os.getenv("SMTP_TLS", "1").strip().lower() in {"1", "true", "yes"}:
            smtp.starttls()
        if user and password:
            smtp.login(user, password)
        smtp.sendmail(sender, [recipient], msg.as_string())


def send_flyer_image(image_path: Path, gig_label: str, option: str) -> str:
    """Send approved flyer by SMTP if configured, else Mail.app."""
    subject = f"Approved flyer: {gig_label} (option {option})"
    body = f"Your approved gig flyer for {gig_label}, option {option}."
    if os.getenv("SMTP_HOST", "").strip():
        send_via_smtp(image_path, subject, body)
        return "smtp"
    send_via_mail_app(image_path, subject, body)
    return "mail_app"
