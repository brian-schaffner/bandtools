"""iMessage send/receive helpers for macOS Messages.app."""

from __future__ import annotations

import os
import re
import sqlite3
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ParsedReply:
    action: str  # approve | revise | unknown
    option: str
    feedback: str
    raw_text: str


def _recipient() -> str:
    value = os.getenv("IMESSAGE_RECIPIENT", "").strip()
    if not value:
        raise RuntimeError("IMESSAGE_RECIPIENT is not set")
    return value


def _messages_db_path() -> Path:
    custom = os.getenv("MESSAGES_DB_PATH", "").strip()
    if custom:
        return Path(custom)
    return Path.home() / "Library" / "Messages" / "chat.db"


def send_text(message: str) -> None:
    recipient = _recipient()
    escaped = message.replace("\\", "\\\\").replace('"', '\\"')
    script = f'''
tell application "Messages"
    set targetService to 1st account whose service type = iMessage
    set targetBuddy to participant "{recipient}" of targetService
    send "{escaped}" to targetBuddy
end tell
'''
    subprocess.run(["osascript", "-e", script], check=True, capture_output=True, text=True)


def send_image(image_path: Path, caption: str = "") -> None:
    recipient = _recipient()
    abs_path = str(image_path.resolve())
    caption_escaped = caption.replace("\\", "\\\\").replace('"', '\\"')
    path_escaped = abs_path.replace("\\", "\\\\").replace('"', '\\"')
    script = f'''
tell application "Messages"
    set targetService to 1st account whose service type = iMessage
    set targetBuddy to participant "{recipient}" of targetService
    set theFile to POSIX file "{path_escaped}"
    send theFile to targetBuddy
    if "{caption_escaped}" is not "" then
        send "{caption_escaped}" to targetBuddy
    end if
end tell
'''
    subprocess.run(["osascript", "-e", script], check=True, capture_output=True, text=True)


def send_review_bundle(header: str, option_paths: dict[str, Path]) -> None:
    send_text(header)
    for letter in sorted(option_paths.keys()):
        path = option_paths[letter]
        send_image(path, caption=f"Option {letter}")


def parse_reply(text: str) -> ParsedReply:
    raw = (text or "").strip()
    upper = raw.upper()

    approve = re.match(r"^APPROVE\s+([ABC])\b", upper)
    if approve:
        return ParsedReply("approve", approve.group(1), "", raw)

    revise = re.match(r"^REVISE\s+([ABC])\s*:\s*(.+)$", raw, flags=re.I | re.S)
    if revise:
        return ParsedReply("revise", revise.group(1).upper(), revise.group(2).strip(), raw)

    return ParsedReply("unknown", "", raw, raw)


def _connect_readonly(db_path: Path) -> sqlite3.Connection:
    if not db_path.exists():
        raise FileNotFoundError(
            f"Messages database not found at {db_path}. Grant Full Disk Access to Terminal/Cursor."
        )
    uri = f"file:{db_path}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def fetch_recent_replies_via_applescript(limit: int = 20) -> list[dict]:
    """Fallback when chat.db is not readable: scan recent Messages for APPROVE/REVISE."""
    recipient = _recipient().replace("\\", "\\\\").replace('"', '\\"')
    script = f'''
tell application "Messages"
    set hits to {{}}
    set targetService to 1st account whose service type = iMessage
    repeat with aChat in chats of targetService
        try
            set msgs to messages of aChat
            set msgCount to count of msgs
            set startIdx to msgCount - {limit} + 1
            if startIdx < 1 then set startIdx to 1
            repeat with i from startIdx to msgCount
                try
                    set t to text of (item i of msgs)
                    if t is not missing value then
                        if t contains "APPROVE" or t contains "REVISE" then
                            set end of hits to t
                        end if
                    end if
                end try
            end repeat
        end try
    end repeat
    return hits
end tell
'''
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []

    texts: list[str] = []
    raw = (result.stdout or "").strip()
    if not raw:
        return []
    # osascript returns comma-separated items for lists
    if raw.startswith("{") and raw.endswith("}"):
        inner = raw[1:-1]
        for part in inner.split(", "):
            cleaned = part.strip().strip('"')
            if cleaned:
                texts.append(cleaned.replace("\\n", "\n"))
    else:
        texts.append(raw)

    replies = []
    for idx, text in enumerate(texts, start=1):
        parsed = parse_reply(text)
        if parsed.action != "unknown":
            replies.append({"rowid": 1_000_000 + idx, "text": text, "handle": recipient})
    return replies


def fetch_new_incoming_messages(since_rowid: int) -> list[dict]:
    """Return iMessage texts with APPROVE/REVISE from the configured recipient thread."""
    db_path = _messages_db_path()
    recipient = _recipient().lower()
    try:
        conn = _connect_readonly(db_path)
    except (FileNotFoundError, sqlite3.DatabaseError):
        return fetch_recent_replies_via_applescript()

    conn.row_factory = sqlite3.Row
    try:
        # Include self-replies (same Apple ID on phone/Mac) when text matches flyer commands.
        query = """
            SELECT m.ROWID as rowid, m.text, m.date, h.id as handle, m.is_from_me
            FROM message m
            JOIN handle h ON m.handle_id = h.ROWID
            WHERE m.ROWID > ?
              AND m.text IS NOT NULL
              AND TRIM(m.text) != ''
              AND (
                m.is_from_me = 0
                OR UPPER(m.text) LIKE 'APPROVE %'
                OR UPPER(m.text) LIKE 'REVISE %'
              )
            ORDER BY m.ROWID ASC
        """
        rows = conn.execute(query, (since_rowid,)).fetchall()
    except sqlite3.DatabaseError:
        return fetch_recent_replies_via_applescript()
    finally:
        conn.close()

    results = []
    for row in rows:
        handle = (row["handle"] or "").lower()
        if recipient not in handle and handle not in recipient:
            continue
        parsed = parse_reply(row["text"])
        if parsed.action == "unknown":
            continue
        results.append(
            {
                "rowid": row["rowid"],
                "text": row["text"],
                "handle": row["handle"],
            }
        )
    if not results:
        return fetch_recent_replies_via_applescript()
    return results
