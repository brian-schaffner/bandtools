#!/usr/bin/env python3
"""Export/import Setlist Loader backup + title mappings between Fly apps."""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import tarfile
import uuid
from datetime import datetime, timezone
from pathlib import Path


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def export_data(db_path: Path, data_dir: Path, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT id, email FROM users WHERE email LIKE '%@%' ORDER BY created_at DESC LIMIT 1"
    )
    user = cur.fetchone()
    if not user:
        raise SystemExit("No users found")
    uid = user["id"]
    email = user["email"]

    cur.execute("SELECT * FROM title_mappings WHERE user_id = ?", (uid,))
    mappings = [dict(r) for r in cur.fetchall()]
    cur.execute(
        """
        SELECT * FROM file_uploads
        WHERE user_id = ? AND file_type = 'backup' AND is_active = 1
        ORDER BY created_at DESC LIMIT 1
        """,
        (uid,),
    )
    backup = cur.fetchone()
    backup_path = None
    if backup:
        rel = backup["file_path"]
        for candidate in (Path(rel), data_dir / rel, Path("/app/setloader") / rel):
            if candidate.is_file():
                backup_path = candidate
                break

    manifest = {
        "source_user_id": uid,
        "email": email,
        "mappings": mappings,
        "backup_record": dict(backup) if backup else None,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if backup_path:
        shutil.copy2(backup_path, out_dir / "backup.sbpbackup")
    return {"email": email, "mappings": len(mappings), "backup": bool(backup_path)}


def import_data(db_path: Path, data_dir: Path, in_dir: Path) -> dict:
    manifest = json.loads((in_dir / "manifest.json").read_text(encoding="utf-8"))
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    email = manifest["email"]
    cur.execute("SELECT id FROM users WHERE email = ?", (email,))
    row = cur.fetchone()
    if row:
        staging_uid = row["id"]
    else:
        staging_uid = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO users (id, email, name, is_active, created_at) VALUES (?, ?, ?, 1, ?)",
            (staging_uid, email, email.split("@")[0], _now_iso()),
        )

    cur.execute("DELETE FROM title_mappings WHERE user_id = ?", (staging_uid,))
    for mapping in manifest.get("mappings", []):
        cur.execute(
            """
            INSERT INTO title_mappings
            (id, user_id, pdf_title, catalog_title, catalog_song_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                staging_uid,
                mapping["pdf_title"],
                mapping["catalog_title"],
                mapping.get("catalog_song_id"),
                mapping.get("created_at") or _now_iso(),
                mapping.get("updated_at") or _now_iso(),
            ),
        )

    backup_record = manifest.get("backup_record")
    backup_src = in_dir / "backup.sbpbackup"
    if backup_record and backup_src.is_file():
        user_dir = data_dir / "user_data" / staging_uid
        user_dir.mkdir(parents=True, exist_ok=True)
        stored_name = backup_record["stored_filename"]
        dest = user_dir / stored_name
        shutil.copy2(backup_src, dest)
        rel_path = f"user_data/{staging_uid}/{stored_name}"
        cur.execute(
            "DELETE FROM file_uploads WHERE user_id = ? AND file_type = 'backup'",
            (staging_uid,),
        )
        cur.execute(
            """
            INSERT INTO file_uploads
            (id, user_id, file_type, original_filename, stored_filename, file_path,
             file_size, mime_type, metadata, created_at, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                str(uuid.uuid4()),
                staging_uid,
                "backup",
                backup_record["original_filename"],
                stored_name,
                rel_path,
                backup_src.stat().st_size,
                backup_record.get("mime_type") or "application/octet-stream",
                backup_record.get("metadata"),
                backup_record.get("created_at") or _now_iso(),
            ),
        )

    conn.commit()
    cur.execute("SELECT COUNT(*) FROM title_mappings WHERE user_id = ?", (staging_uid,))
    mapping_count = cur.fetchone()[0]
    cur.execute(
        "SELECT COUNT(*) FROM file_uploads WHERE user_id = ? AND file_type = 'backup'",
        (staging_uid,),
    )
    backup_count = cur.fetchone()[0]
    return {
        "staging_user_id": staging_uid,
        "mappings": mapping_count,
        "backups": backup_count,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    export_parser = sub.add_parser("export")
    export_parser.add_argument("--db", default="/data/setloader.db")
    export_parser.add_argument("--data-dir", default="/data")
    export_parser.add_argument("--out-dir", required=True)

    import_parser = sub.add_parser("import")
    import_parser.add_argument("--db", default="/data/setloader.db")
    import_parser.add_argument("--data-dir", default="/data")
    import_parser.add_argument("--in-dir", required=True)

    pack_parser = sub.add_parser("pack")
    pack_parser.add_argument("--in-dir", required=True)
    pack_parser.add_argument("--archive", required=True)

    unpack_parser = sub.add_parser("unpack")
    unpack_parser.add_argument("--archive", required=True)
    unpack_parser.add_argument("--out-dir", required=True)

    args = parser.parse_args()
    if args.cmd == "export":
        print(json.dumps(export_data(Path(args.db), Path(args.data_dir), Path(args.out_dir))))
    elif args.cmd == "import":
        print(json.dumps(import_data(Path(args.db), Path(args.data_dir), Path(args.in_dir))))
    elif args.cmd == "pack":
        with tarfile.open(args.archive, "w:gz") as tar:
            tar.add(args.in_dir, arcname="export")
    elif args.cmd == "unpack":
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        with tarfile.open(args.archive, "r:gz") as tar:
            tar.extractall(out_dir)


if __name__ == "__main__":
    main()
