# mailer.py
import os
import smtplib
import mimetypes
from typing import Optional, Sequence
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

def send_email_with_attachment(
    to_addr: str,
    subject: str,
    body: str,
    attachment_path: Optional[str] = None,
    attachments: Optional[Sequence[str]] = None,  # NEW: multiple files supported
) -> None:
    """
    Send an email with optional attachments.

    - Keep using `attachment_path` for a single file (backward compatible).
    - Or pass `attachments=[...paths...]` for multiple files.
    """
#
    SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
    SMTP_USER = os.getenv("SMTP_USER")
    SMTP_PASS = os.getenv("SMTP_PASS")
    FROM_NAME = os.getenv("FROM_NAME", "Set Loader")
    FROM_ADDR = os.getenv("FROM_ADDR", SMTP_USER)

    # normalize file list
    files = []
    if attachment_path:
        files.append(attachment_path)
    if attachments:
        files.extend([p for p in attachments if p])

    # build message
    if files:
        msg = MIMEMultipart()
        msg.attach(MIMEText(body or "", "plain"))
    else:
        msg = MIMEText(body or "", "plain")

    msg["From"] = f"{FROM_NAME} <{FROM_ADDR}>"
    msg["To"] = to_addr
    msg["Subject"] = subject

    # attach files
    for path in files:
        if not os.path.exists(path):
            continue
        ctype, encoding = mimetypes.guess_type(path)
        if ctype is None or encoding is not None:
            ctype = "application/octet-stream"
        maintype, subtype = ctype.split("/", 1)

        with open(path, "rb") as f:
            part = MIMEBase(maintype, subtype)
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment", filename=os.path.basename(path))
        msg.attach(part)

    # send
    if SMTP_PORT == 465:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as s:
            s.login(SMTP_USER, SMTP_PASS)
            s.sendmail(FROM_ADDR, [to_addr], msg.as_string())
    else:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
            s.sendmail(FROM_ADDR, [to_addr], msg.as_string())