"""Email a rendered logistics schedule over SMTP."""

from __future__ import annotations

import html
import os
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from logistics.render import render_markdown, render_text
from logistics.schedule import LogisticsSchedule

DEFAULT_RECIPIENT = "brian@schaffner.net"


def recipient() -> str:
    return os.getenv("LOGISTICS_EMAIL_TO", DEFAULT_RECIPIENT).strip()


def email_configured() -> bool:
    return bool(os.getenv("SMTP_HOST", "").strip() and recipient())


def subject_for(schedule: LogisticsSchedule) -> str:
    prefix = "REVISED: " if schedule.revised else ""
    return f"{prefix}Gig day schedule — {schedule.gig.event_date:%a %b} {schedule.gig.event_date.day} · {schedule.profile.name}"


def markdown_to_html(markdown: str) -> str:
    lines = []
    for line in markdown.rstrip("\n").splitlines():
        escaped = html.escape(line)
        escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
        escaped = re.sub(r"\*(.+?)\*", r"<em>\1</em>", escaped)
        lines.append(escaped)
    return "<br>\n".join(lines)


def send_schedule_email(schedule: LogisticsSchedule, to: str = "") -> str:
    host = os.getenv("SMTP_HOST", "").strip()
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").strip()
    to = to or recipient()
    if not host or not to:
        raise RuntimeError("Email is not configured (set SMTP_HOST, SMTP_USER, SMTP_PASSWORD).")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject_for(schedule)
    msg["From"] = os.getenv("EMAIL_FROM", user or "band-tools@localhost").strip()
    msg["To"] = to
    msg.attach(MIMEText(render_text(schedule), "plain", "utf-8"))
    body = markdown_to_html(render_markdown(schedule))
    msg.attach(MIMEText(f'<div style="font-family:-apple-system,Segoe UI,sans-serif;line-height:1.5">{body}</div>', "html", "utf-8"))

    smtp_cls = smtplib.SMTP_SSL if port == 465 else smtplib.SMTP
    with smtp_cls(host, port, timeout=30) as server:
        if smtp_cls is smtplib.SMTP:
            server.starttls()
        if user and password:
            server.login(user, password)
        server.sendmail(msg["From"], [to], msg.as_string())
    return to
