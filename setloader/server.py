"""FastAPI service for orchestrating set loader runs."""

from __future__ import annotations

import base64
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

from fastapi import File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uuid
import json
from datetime import datetime

from mailer import send_email_with_attachment
from src.backup_to_catalog import process_backup


app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:3002", "http://127.0.0.1:3002"],  # Next.js dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _find_run_sh(start: Path) -> Optional[Path]:
    """Walk up the tree looking for run.sh."""

    current = start
    for _ in range(6):  # a few levels is enough for tests + prod
        candidate = current / "run.sh"
        if candidate.exists():
            return candidate
        current = current.parent
    return None


THIS_FILE = Path(__file__).resolve()
RUN_SH = _find_run_sh(THIS_FILE)
if RUN_SH is None:
    raise RuntimeError("Unable to locate run.sh")

ROOT = RUN_SH.parent


def _configure_dir(name: str, default: str) -> Path:
    path = ROOT / os.getenv(name, default)
    path.mkdir(parents=True, exist_ok=True)
    return path


UPLOADS = _configure_dir("UPLOAD_DIR", "uploads")
WORK = _configure_dir("WORK_DIR", "work")
PACK = _configure_dir("PACK_DIR", "pack")
USER_DATA = _configure_dir("USER_DATA_DIR", "user_data")

# User session storage (in production, use Redis or database)
user_sessions = {}
user_files = {}

# Debug mode - set to True to disable cleanup for diagnostics
DEBUG_NO_CLEANUP = os.getenv("DEBUG_NO_CLEANUP", "false").lower() in ("true", "1", "yes")

SECRET = os.getenv("WEBHOOK_SECRET") or os.getenv("SECRET") or "change-me"


def slugify(raw: str) -> str:
    cleaned = (raw or "set").strip()
    cleaned = re.sub(r"[^\w\-]+", "_", cleaned)
    return cleaned.strip("_") or "set"


def _cleanup_old_files():
    """Clean up old files unless debug mode is enabled."""
    if DEBUG_NO_CLEANUP:
        return
    
    current_time = time.time()
    cleanup_age = 3600  # 1 hour in seconds
    
    # Clean up old PDF files in uploads
    for pdf_file in UPLOADS.glob("*.pdf"):
        if current_time - pdf_file.stat().st_mtime > cleanup_age:
            try:
                pdf_file.unlink()
                print(f"🧹 Cleaned up old PDF: {pdf_file.name}")
            except Exception as e:
                print(f"⚠️ Failed to clean up {pdf_file.name}: {e}")
    
    # Clean up old .sbp files in pack (keep last 10)
    sbp_files = sorted(PACK.glob("*.sbp"), key=lambda f: f.stat().st_mtime, reverse=True)
    for sbp_file in sbp_files[10:]:  # Keep only the 10 most recent
        try:
            sbp_file.unlink()
            print(f"🧹 Cleaned up old .sbp: {sbp_file.name}")
        except Exception as e:
            print(f"⚠️ Failed to clean up {sbp_file.name}: {e}")


def first_existing(*paths: Path) -> Optional[Path]:
    for path in paths:
        if path and path.exists():
            return path
    return None


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "ok": "true",
        "root": str(ROOT),
        "run_sh": str(RUN_SH),
        "uploads": str(UPLOADS),
    }


async def _extract_pdf_bytes(request: Request, name: str) -> tuple[bytes, str]:
    """Extract PDF bytes from a request body."""

    content_type = (request.headers.get("content-type") or "").lower()
    slug_hint: Optional[str] = None
    pdf_bytes: Optional[bytes] = None

    if "multipart/form-data" in content_type:
        form = await request.form()
        for key, value in form.multi_items():
            if hasattr(value, "read"):
                slug_hint = getattr(value, "filename", None)
                pdf_bytes = await value.read()  # type: ignore[union-attr]
                break
        if not pdf_bytes:
            keys = list(form.keys())
            types = [type(form[k]).__name__ for k in keys]
            raise HTTPException(
                422,
                f"file missing in multipart; saw keys: {keys} (types: {types})",
            )
        if "name" in form:
            name = str(form["name"])
    elif "application/pdf" in content_type:
        pdf_bytes = await request.body()
    elif "application/json" in content_type:
        try:
            payload = await request.json()
        except Exception as exc:  # pragma: no cover - defensive
            raise HTTPException(422, f"invalid json body: {exc}") from exc
        else:
            encoded = payload.get("file_b64")
            if encoded:
                pdf_bytes = base64.b64decode(encoded)
            name = payload.get("name", name)

    if not pdf_bytes:
        raise HTTPException(422, f"no file received; Content-Type={content_type}")

    # Clean up the name for the set name
    if slug_hint:
        # Use the filename without extension as the set name
        clean_name = Path(slug_hint).stem
        
        # URL decode common patterns
        clean_name = clean_name.replace('%20', ' ')
        clean_name = clean_name.replace('_', ' ')
        
        # Remove common prefixes/suffixes
        clean_name = re.sub(r'^(setlist|set|list|songbook|backup)[\s_-]*', '', clean_name, flags=re.IGNORECASE)
        clean_name = re.sub(r'[\s_-]*(setlist|set|list|songbook|backup)$', '', clean_name, flags=re.IGNORECASE)
        
        # Remove date patterns (YYYY-MM-DD, YYYY_MM_DD, etc.)
        clean_name = re.sub(r'\b\d{4}[-_]\d{1,2}[-_]\d{1,2}\b', '', clean_name)
        clean_name = re.sub(r'\b\d{1,2}[-_]\d{1,2}[-_]\d{4}\b', '', clean_name)
        
        # Remove time patterns (HH:MM, HH_MM, etc.)
        clean_name = re.sub(r'\b\d{1,2}[:_]\d{2}(?::\d{2})?\b', '', clean_name)
        
        # Remove version numbers and IDs
        clean_name = re.sub(r'\b(v\d+|version\s*\d+|id\s*:?\s*\w+)\b', '', clean_name, flags=re.IGNORECASE)
        
        # Remove standalone numbers (like "20" in "Bonnie 20Sloan")
        clean_name = re.sub(r'\b\d+\b', '', clean_name)
        
        # Remove special characters but keep spaces, hyphens, and basic punctuation
        clean_name = re.sub(r'[^\w\s\-.,&]', ' ', clean_name)
        
        # Clean up multiple spaces and trim
        clean_name = re.sub(r'\s+', ' ', clean_name).strip()
        
        # Remove leading/trailing punctuation
        clean_name = clean_name.strip('.,-_ ')
        
        # Ensure we have a meaningful name
        if not clean_name or len(clean_name) < 2:
            clean_name = "Set List"
            
        return pdf_bytes, clean_name
    else:
        return pdf_bytes, name


def _prepare_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PATH", "")
    env["PATH"] = "/opt/homebrew/bin:/usr/local/bin:" + env["PATH"]
    env["PY"] = sys.executable
    return env


def _get_user_id_from_backup_path(backup_path: str) -> str:
    """Extract user ID from backup path."""
    # backup_path format: /path/to/user_data/user_123456/backup_20251012_160313_filename.sbpbackup
    path_parts = Path(backup_path).parts
    for part in path_parts:
        if part.startswith('user_') and part != 'user_data':
            return part
    # Fallback to deterministic user ID
    return _get_user_id_from_email("brian@schaffner.net")

def _get_user_id_from_email(email: str) -> str:
    """Get deterministic user ID from email."""
    import hashlib
    return f"user_{int(hashlib.md5(email.encode()).hexdigest()[:6], 16) % 1000000}"

def _process_with_user_backup(pdf_path: Path, name: str, backup_path: str, env: dict) -> subprocess.CompletedProcess:
    """Process setlist using user's backup file instead of global catalog."""
    try:
        # Extract dataFile.txt from user's backup
        backup_datafile = PACK / "user_dataFile.txt"
        subprocess.run([
            "unzip", "-o", backup_path, "dataFile.txt"
        ], cwd=str(PACK), check=True)
        
        # Rename to avoid conflicts
        (PACK / "dataFile.txt").rename(backup_datafile)
        
        # Step 1: Extract titles from PDF
        raw_titles = PACK / "raw_titles.txt"
        proc1 = subprocess.run([
            "python3", "src/pdf_to_titles.py", 
            "--in", str(pdf_path), 
            "--out", str(raw_titles)
        ], cwd=str(ROOT), env=env, capture_output=True, text=True)
        
        if proc1.returncode != 0:
            return proc1
        
        # Step 2: Extract song titles from user's backup to create a catalog
        user_catalog = PACK / "user_catalog.txt"
        _extract_song_titles_from_backup(backup_datafile, user_catalog)
        
        # Step 3: Verify titles against user's catalog
        verified_titles = PACK / "verified.txt"
        report_file = PACK / "unresolved_report.txt"
        
        # Get user's mapping file
        user_id = _get_user_id_from_backup_path(backup_path)
        user_mapper = USER_DATA / user_id / "title_mapper.json"
        
        proc2 = subprocess.run([
            "python3", "src/titles_verify.py",
            "--in", str(raw_titles),
            "--catalog", str(user_catalog),
            "--mapper", str(user_mapper),
            "--out", str(verified_titles),
            "--report", str(report_file)
        ], cwd=str(ROOT), env=env, capture_output=True, text=True)
        
        if proc2.returncode != 0:
            return proc2
        
        # Step 3: Extract songs using user's backup
        output_datafile = PACK / "dataFile.txt"
        proc3 = subprocess.run([
            "python3", "src/extract_songs.py",
            "--verified", str(verified_titles),
            "--datafile", str(backup_datafile),
            "--out", str(output_datafile),
            "--format", "container",
            "--make-set", name
        ], cwd=str(ROOT), env=env, capture_output=True, text=True)
        
        if proc3.returncode != 0:
            return proc3
        
        # Step 4: Create hash file with exactly 32 bytes of MD5 hash
        hash_file = PACK / "dataFile.hash"
        import hashlib
        
        # Read the dataFile.txt and compute MD5 hash
        with open(output_datafile, 'rb') as f:
            content = f.read()
        md5_hash = hashlib.md5(content).hexdigest()
        
        # Write exactly 32 bytes of hash (no filename, no newline)
        with open(hash_file, 'w') as f:
            f.write(md5_hash)
        
        # Step 5: Create final .sbp file
        artifact_name = f"{name}.sbp"
        artifact_path = PACK / artifact_name
        subprocess.run([
            "zip", "-q", artifact_name, "dataFile.txt", "dataFile.hash"
        ], cwd=str(PACK), check=True)
        
        # Validate the output
        validation_result = _validate_output(artifact_path, verified_titles)
        
        # Return success with artifact path and validation
        stdout = f"Wrote: {artifact_path}\nARTIFACT={artifact_path}\n"
        if validation_result:
            stdout += f"VALIDATION: {validation_result}\n"
        
        return subprocess.CompletedProcess(
            args=[], returncode=0, 
            stdout=stdout,
            stderr=""
        )
        
    except subprocess.CalledProcessError as e:
        return subprocess.CompletedProcess(
            args=[], returncode=e.returncode,
            stdout=e.stdout or "", stderr=e.stderr or ""
        )
    except Exception as e:
        return subprocess.CompletedProcess(
            args=[], returncode=1,
            stdout="", stderr=str(e)
        )


def _extract_song_titles_from_backup(backup_datafile: Path, catalog_output: Path) -> None:
    """Extract song titles from user's backup and create a simple catalog file."""
    try:
        with open(backup_datafile, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        if len(lines) >= 2:
            json_line = lines[1].strip()
            data = json.loads(json_line)
            songs = data.get('songs', [])
            
            # Extract song titles
            titles = []
            for song in songs:
                title = song.get('title', song.get('name', ''))
                if title and title.strip():
                    titles.append(title.strip())
            
            # Write to catalog file
            with open(catalog_output, 'w', encoding='utf-8') as f:
                for title in sorted(set(titles)):  # Remove duplicates and sort
                    f.write(f"{title}\n")
        else:
            # Create empty catalog if backup is invalid
            with open(catalog_output, 'w', encoding='utf-8') as f:
                f.write("")
    except Exception as e:
        # Create empty catalog on error
        with open(catalog_output, 'w', encoding='utf-8') as f:
            f.write("")


def _validate_output(artifact_path: Path, verified_titles_path: Path) -> str:
    """Validate the output JSON and identify any missing songs."""
    try:
        # Extract and read the output
        with tempfile.TemporaryDirectory() as temp_dir:
            subprocess.run(['unzip', '-o', str(artifact_path)], cwd=temp_dir, check=True)
            
            with open(Path(temp_dir) / 'dataFile.txt', 'r', encoding='utf-8') as f:
                lines = f.readlines()
                json_line = lines[1].strip()
                data = json.loads(json_line)
                songs = data.get('songs', [])
        
        # Read expected titles
        expected_titles = []
        if verified_titles_path.exists():
            with open(verified_titles_path, 'r', encoding='utf-8') as f:
                expected_titles = [line.strip() for line in f if line.strip()]
        
        # Analyze results
        actual_titles = [song.get('title', song.get('name', '')) for song in songs]
        actual_count = len(actual_titles)
        expected_count = len(expected_titles)
        
        # Find missing songs
        missing_songs = []
        for expected in expected_titles:
            if not any(expected.lower() in actual.lower() for actual in actual_titles):
                missing_songs.append(expected)
        
        # Create validation report
        report = f"Expected: {expected_count}, Actual: {actual_count}"
        if missing_songs:
            report += f", Missing: {', '.join(missing_songs[:5])}"
            if len(missing_songs) > 5:
                report += f" and {len(missing_songs) - 5} more"
        
        return report
        
    except Exception as e:
        return f"Validation error: {str(e)}"


def _resolve_artifact(stdout: str, fallback_name: str) -> Path:
    match = re.search(r"^ARTIFACT=(.+)$", stdout, flags=re.MULTILINE)
    if match:
        artifact_candidate = Path(match.group(1))
        if not artifact_candidate.is_absolute():
            artifact_candidate = (ROOT / artifact_candidate).resolve()
        return artifact_candidate
    return (PACK / f"{slugify(fallback_name)}.sbp").resolve()


async def _persist_pdf(pdf_bytes: bytes, slug_hint: str) -> Path:
    slug = slugify(Path(slug_hint).stem or slug_hint)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(pdf_bytes)
        tmp.flush()
        temp_path = Path(tmp.name)
    pdf_path = (UPLOADS / f"{slug}.pdf").resolve()
    shutil.move(str(temp_path), pdf_path)
    return pdf_path


def _tail(text: str, limit: int = 40) -> list[str]:
    lines = (text or "").splitlines()
    return lines[-limit:]


def _get_user_id(request: Request) -> str:
    """Get or create user ID from session or user email."""
    # For now, use a fixed user ID for brian@schaffner.net
    # In the future, this will be determined by authentication
    user_email = "brian@schaffner.net"
    # Use a deterministic hash by converting to bytes first
    import hashlib
    user_id = f"user_{int(hashlib.md5(user_email.encode()).hexdigest()[:6], 16) % 1000000}"
    
    if user_id not in user_sessions:
        user_sessions[user_id] = {
            "created": datetime.now().isoformat(),
            "backup_uploaded": False,
            "backup_path": None,
            "user_email": user_email,
            "song_count": 0
        }
    
    return user_id

def _get_user_id_only(request: Request) -> str:
    """Get user ID without creating a session."""
    user_email = "brian@schaffner.net"
    import hashlib
    user_id = f"user_{int(hashlib.md5(user_email.encode()).hexdigest()[:6], 16) % 1000000}"
    return user_id


def _get_user_data(user_id: str) -> dict:
    """Get user data, creating if not exists."""
    if user_id not in user_files:
        # Try to load existing data from filesystem
        user_data_file = USER_DATA / user_id / "user_data.json"
        if user_data_file.exists():
            try:
                with open(user_data_file, 'r') as f:
                    user_files[user_id] = json.load(f)
            except Exception as e:
                print(f"Error loading user data for {user_id}: {e}")
                user_files[user_id] = {
                    "backups": [],
                    "setlists": [],
                    "downloads": []
                }
        else:
            user_files[user_id] = {
                "backups": [],
                "setlists": [],
                "downloads": []
            }
    return user_files[user_id]


def _count_songs_in_backup(backup_path: Path) -> int:
    """Count songs in a backup file using the same logic as backup_to_catalog.py."""
    try:
        import json
        import zipfile
        
        # Use the same logic as backup_to_catalog.py
        if backup_path.suffix.lower() in ['.zip', '.sbpbackup', '.bkp']:
            with zipfile.ZipFile(backup_path, 'r') as zf:
                # Read dataFile.txt from inside the backup
                data_bytes = zf.read("dataFile.txt")
            
            # Decode text (handle BOM)
            text = data_bytes.decode("utf-8-sig").strip()
            
            # Parse JSON content using the same logic as backup_to_catalog.py
            songs_items = []
            
            def collect_from_obj(obj):
                # Accept {"songs":[...]}, or a top-level list of song dicts/strings
                if isinstance(obj, dict):
                    if isinstance(obj.get("songs"), list):
                        songs_items.extend(obj["songs"])
                elif isinstance(obj, list):
                    songs_items.extend(obj)
            
            try:
                obj = json.loads(text)
                collect_from_obj(obj)
            except json.JSONDecodeError:
                # JSONL: parse each non-empty line
                for ln in (ln for ln in text.splitlines() if ln.strip()):
                    try:
                        obj = json.loads(ln)
                        collect_from_obj(obj)
                    except json.JSONDecodeError:
                        # ignore non-JSON lines in JSONL (be permissive)
                        continue
            
            # Count only active (non-deleted) songs
            active_songs = [song for song in songs_items if isinstance(song, dict) and not song.get("Deleted", False)]
            return len(active_songs)
        
        return 0
    except Exception:
        return 0


def _check_empty_content_songs(backup_path: Path) -> dict:
    """Check for songs with empty content in backup file."""
    try:
        import json
        import zipfile
        
        empty_songs = []
        
        if backup_path.suffix.lower() in ['.zip', '.sbpbackup', '.bkp']:
            with zipfile.ZipFile(backup_path, 'r') as zf:
                # Read dataFile.txt from inside the backup
                data_bytes = zf.read("dataFile.txt")
            
            # Decode text (handle BOM)
            text = data_bytes.decode("utf-8-sig").strip()
            
            # Parse JSON content
            songs_items = []
            
            def collect_from_obj(obj):
                if isinstance(obj, dict):
                    if isinstance(obj.get("songs"), list):
                        songs_items.extend(obj["songs"])
                elif isinstance(obj, list):
                    songs_items.extend(obj)
            
            try:
                obj = json.loads(text)
                collect_from_obj(obj)
            except json.JSONDecodeError:
                # JSONL: parse each non-empty line
                for ln in (ln for ln in text.splitlines() if ln.strip()):
                    try:
                        obj = json.loads(ln)
                        collect_from_obj(obj)
                    except json.JSONDecodeError:
                        continue
            
            # Check each song for empty content (excluding deleted songs)
            for song in songs_items:
                if isinstance(song, dict):
                    song_id = song.get("Id")
                    song_name = song.get("name", "Unknown")
                    content = song.get("content", "")
                    deleted = song.get("Deleted", False)
                    
                    # Skip deleted songs - they shouldn't be considered for processing
                    if deleted:
                        continue
                    
                    # Check if content is empty or very short (less than 10 characters)
                    if not content or len(content.strip()) < 10:
                        empty_songs.append({
                            "id": song_id,
                            "name": song_name,
                            "content_length": len(content) if content else 0
                        })
        
        # Count active songs for total
        active_songs = [song for song in songs_items if isinstance(song, dict) and not song.get("Deleted", False)] if 'songs_items' in locals() else []
        
        return {
            "empty_songs": empty_songs,
            "empty_count": len(empty_songs),
            "total_songs": len(active_songs)
        }
        
    except Exception as e:
        return {
            "empty_songs": [],
            "empty_count": 0,
            "total_songs": 0,
            "error": str(e)
        }


def _save_user_file(user_id: str, file_type: str, file_path: str, metadata: dict = None):
    """Save file reference to user's data."""
    user_data = _get_user_data(user_id)
    file_entry = {
        "id": str(uuid.uuid4()),
        "path": str(file_path),
        "filename": file_path.name,
        "uploaded_at": datetime.now().isoformat(),
        "metadata": metadata or {}
    }
    user_data[file_type].append(file_entry)
    _save_user_data(user_id, user_data)
    return file_entry


def _save_user_data(user_id: str, user_data: dict):
    """Save user data to filesystem."""
    user_data_file = USER_DATA / user_id / "user_data.json"
    user_data_file.parent.mkdir(parents=True, exist_ok=True)
    with open(user_data_file, 'w') as f:
        json.dump(user_data, f, indent=2)


@app.post("/process_setlist_simple")
async def process_setlist_simple(
    request: Request,
    secret_form: str | None = Form(None, alias="secret"),
    x_secret: str | None = Header(default=None, alias="X-Secret"),
    secret_query: str | None = Query(default=None, alias="secret"),
    name: str = Form("Set"),
):
    """Process setlist using the new three-step workflow."""
    provided = secret_form or x_secret or secret_query
    if provided != SECRET:
        raise HTTPException(401, "unauthorized")

    user_id = _get_user_id(request)
    
    # Check if user has uploaded a backup
    if not user_sessions.get(user_id, {}).get("backup_uploaded", False):
        raise HTTPException(400, "No backup file uploaded. Please upload a backup file first.")

    try:
        # Extract PDF bytes and filename
        pdf_bytes, slug_hint = await _extract_pdf_bytes(request, name)
        
        # Create working directory for this processing event
        working_dir = Path(f"work/{user_id}_{int(time.time())}")
        working_dir.mkdir(parents=True, exist_ok=True)
        
        # Step 1: PDF Extraction
        from pdf_extraction_library import PDFExtractor
        pdf_extractor = PDFExtractor()
        # Save PDF bytes to temporary file for processing
        pdf_path = working_dir / "input.pdf"
        with open(pdf_path, 'wb') as f:
            f.write(pdf_bytes)
        
        # Extract songs using the PDFExtractor
        prompt_path = Path("prompts/openai_extraction.prompt")
        extraction_result = pdf_extractor.extract_songs(pdf_path, prompt_path)
        
        # Save the extraction result to JSON file
        with open(working_dir / "titles.json", 'w', encoding='utf-8') as f:
            json.dump(extraction_result["data"], f, indent=2)
        
        if not extraction_result["success"]:
            return JSONResponse(content={"ok": False, "error": f"PDF extraction failed: {extraction_result['error']}"})
        
        # Step 2: Title Validation
        from title_validation_library import validate_titles_from_json
        # Get user's backup file path
        user_data = _get_user_data(user_id)
        latest_backup = user_data.get("latest_backup")
        if not latest_backup:
            return JSONResponse(content={"ok": False, "error": "No backup file found for user"})
        
        backup_path = Path(latest_backup["path"])
        mappings_path = Path(f"user_data/{user_id}/user_data.json")
        
        # Load the titles JSON
        with open(working_dir / "titles.json", 'r', encoding='utf-8') as f:
            titles_data = json.load(f)
        
        # Validate titles
        try:
            validation_result = validate_titles_from_json(titles_data, user_id, backup_path, mappings_path)
        except Exception as e:
            return JSONResponse(content={"ok": False, "error": f"Title validation failed: {e}"})
        
        # Save validated titles
        with open(working_dir / "validated_titles.json", 'w', encoding='utf-8') as f:
            json.dump(validation_result, f, indent=2)
        
        # Step 3: Song Extraction
        from song_extraction_library import SongExtractor
        song_extractor = SongExtractor(user_id, backup_path)
        extraction_result = song_extractor.extract_and_save(validation_result, working_dir / f"{name}.sbp", name)
        
        if not extraction_result["success"]:
            return JSONResponse(content={"ok": False, "error": f"Song extraction failed: {extraction_result['error']}"})
        
        # Save to user's archive
        archive_result = _save_user_file(user_id, "downloads", working_dir / f"{name}.sbp", {
            "original_filename": f"{name}.sbp",
            "file_size": (working_dir / f"{name}.sbp").stat().st_size,
            "set_name": name
        })
        
        # Read processing results for detailed statistics
        try:
            # Read from the new three-step workflow files
            titles_json_path = working_dir / "titles.json"
            validated_json_path = working_dir / "validated_titles.json"
            
            # Read raw titles from titles.json
            raw_titles = []
            if titles_json_path.exists():
                with open(titles_json_path, 'r', encoding='utf-8') as f:
                    titles_data = json.load(f)
                    # Extract all song titles from sets and extras
                    for set_data in titles_data.get('sets', []):
                        for song in set_data.get('songs', []):
                            raw_titles.append(song.get('title', ''))
                    for extra in titles_data.get('extras', []):
                        raw_titles.append(extra.get('title', ''))
            
            # Read validated results from validated_titles.json
            verified_titles = []
            unfound_titles = []
            if validated_json_path.exists():
                with open(validated_json_path, 'r', encoding='utf-8') as f:
                    validated_data = json.load(f)
                    # Extract validated and unfound titles
                    for set_data in validated_data.get('sets', []):
                        for song in set_data.get('songs', []):
                            if song.get('validated'):
                                verified_titles.append(song.get('title', ''))
                            else:
                                unfound_titles.append(song.get('title', ''))
                    for extra in validated_data.get('extras', []):
                        if extra.get('validated'):
                            verified_titles.append(extra.get('title', ''))
                        else:
                            unfound_titles.append(extra.get('title', ''))
            
            return JSONResponse(content={
                "ok": True,
                "download_id": archive_result["id"],
                "file_id": archive_result["id"],
                "filename": f"{name}.sbp",
                "download_url": f"{base_url}/download_file/{archive_result['id']}",
                "file_size": (working_dir / f"{name}.sbp").stat().st_size,
                "created_at": archive_result["uploaded_at"],
                "processing_results": {
                    "song_count": len(raw_titles),
                    "successful_mappings": len(verified_titles),
                    "unfound_titles": unfound_titles,
                    "all_titles": raw_titles
                }
            })
        except Exception as e:
            print(f"[WARNING] Could not read processing statistics: {e}")
            return JSONResponse(content={
                "ok": True,
                "download_id": archive_result["id"],
                "file_id": archive_result["id"],
                "filename": f"{name}.sbp",
                "download_url": f"{base_url}/download_file/{archive_result['id']}",
                "file_size": (working_dir / f"{name}.sbp").stat().st_size,
                "created_at": archive_result["uploaded_at"]
            })
        finally:
            # Clean up working directory
            import shutil
            if working_dir.exists():
                shutil.rmtree(working_dir)
        
    except Exception as e:
        print(f"[ERROR] Processing failed: {e}")
        import traceback
        print(f"[DEBUG] Traceback: {traceback.format_exc()}")
        return JSONResponse(content={"ok": False, "error": str(e)})

@app.post("/process_setlist")
async def process_setlist(
    request: Request,
    secret_form: str | None = Form(None, alias="secret"),
    x_secret: str | None = Header(default=None, alias="X-Secret"),
    secret_query: str | None = Query(default=None, alias="secret"),
    name: str = Form("Set"),
):
    """Process setlist and return download link instead of email."""
    provided = secret_form or x_secret or secret_query
    if provided != SECRET:
        raise HTTPException(401, "unauthorized")

    user_id = _get_user_id(request)
    
    # Check if user has uploaded a backup
    if not user_sessions.get(user_id, {}).get("backup_uploaded", False):
        raise HTTPException(400, "No backup file uploaded. Please upload a backup file first.")

    pdf_bytes, slug_hint = await _extract_pdf_bytes(request, name)
    pdf_path = await _persist_pdf(pdf_bytes, slug_hint)

    # Save setlist to user directory
    user_dir = USER_DATA / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    user_setlist_path = user_dir / f"setlist_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{slug_hint}"
    shutil.copy2(pdf_path, user_setlist_path)
    
    # Save file reference
    setlist_entry = _save_user_file(user_id, "setlists", user_setlist_path, {
        "original_filename": slug_hint,
        "file_size": user_setlist_path.stat().st_size,
        "set_name": name
    })

    # Use user's backup file instead of global catalog
    user_session = user_sessions.get(user_id, {})
    backup_path = user_session.get("backup_path")
    
    if not backup_path or not Path(backup_path).exists():
        raise HTTPException(status_code=400, detail="User backup not found")
    
    # Create a custom processing pipeline using user's backup
    env = _prepare_env()
    extra = shlex.split(os.getenv("RUN_EXTRA_FLAGS", ""))
    
    # Use custom processing with user's backup
    proc = _process_with_user_backup(pdf_path, slug_hint, backup_path, env)

    artifact = _resolve_artifact(proc.stdout or "", slug_hint)

    if proc.returncode != 0:
        return JSONResponse(
            {
                "ok": False,
                "code": proc.returncode,
                "stdout": _tail(proc.stdout or ""),
                "stderr": _tail(proc.stderr or ""),
            },
            status_code=500,
        )

    if not artifact.exists():
        return JSONResponse(
            {
                "ok": False,
                "error": f"artifact not found: {artifact}",
                "stdout": _tail(proc.stdout or ""),
                "stderr": _tail(proc.stderr or ""),
            },
            status_code=500,
        )

    # Copy artifact to user directory for download
    user_artifact_path = user_dir / f"download_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{artifact.name}"
    shutil.copy2(artifact, user_artifact_path)
    
    # Save download reference
    download_entry = _save_user_file(user_id, "downloads", user_artifact_path, {
        "original_filename": slug_hint,  # Use the original input filename
        "file_size": user_artifact_path.stat().st_size,
        "set_name": name,
        "setlist_id": setlist_entry["id"]
    })

    # Clean up old files after successful processing
    _cleanup_old_files()
    
    # Get the base URL from the request - point to backend for downloads
    base_url = f"http://{request.client.host}:8002" if request.client.host != "127.0.0.1" else "http://localhost:8002"
    
    # Extract titles from the processed setlist for analysis
    titles = []
    debug_info = {
        "verified_file_exists": False,
        "verified_file_path": None,
        "raw_titles": [],
        "verified_titles": [],
        "processing_steps": []
    }
    
    try:
        # Try to read the verified.txt file from pack directory (where run.sh creates it)
        verified_path = PACK / "verified.txt"
        debug_info["verified_file_path"] = str(verified_path)
        debug_info["verified_file_exists"] = verified_path.exists()
        
        # Use raw titles instead of pre-processed verified titles
        raw_path = PACK / "raw_titles.txt"
        if raw_path.exists():
            with open(raw_path, 'r', encoding='utf-8') as f:
                titles = [line.strip() for line in f if line.strip()]
                debug_info["raw_titles"] = titles.copy()
                debug_info["processing_steps"].append(f"Read {len(titles)} raw titles from pack/raw_titles.txt")
        else:
            debug_info["processing_steps"].append("pack/raw_titles.txt file not found")
            
    except Exception as e:
        debug_info["processing_steps"].append(f"Error reading files: {str(e)}")
        pass
    
    # Initialize variables
    verification_results = []
    successful_mappings = 0
    unfound_titles = []
    
    # Use the proven manual verification process
    if titles:
        try:
            debug_info["processing_steps"].append(f"Starting manual verification for {len(titles)} titles")
            
            # Get user's catalog
            catalog_response = await get_user_catalog(request, x_secret)
            catalog = catalog_response["catalog"]
            debug_info["catalog_size"] = len(catalog)
            debug_info["processing_steps"].append(f"Loaded catalog with {len(catalog)} songs")
            
            # Get user's existing mappings
            user_dir = USER_DATA / user_id
            mapper_path = user_dir / "title_mapper.json"
            
            if mapper_path.exists():
                with open(mapper_path, 'r', encoding='utf-8') as f:
                    existing_mappings = json.load(f)
                debug_info["mappings_count"] = len(existing_mappings)
                debug_info["processing_steps"].append(f"Loaded {len(existing_mappings)} existing mappings")
            else:
                existing_mappings = {}
                debug_info["processing_steps"].append("No existing mappings found")
            
            # Read the report file to get unfound titles
            unfound_titles = []
            report_file_path = PACK / "unresolved_report.txt"
            if report_file_path.exists():
                with open(report_file_path, 'r', encoding='utf-8') as f:
                    report_content = f.read()
                    # Parse unresolved titles from report
                    lines = report_content.split('\n')
                    for line in lines:
                        if line.startswith('UNRESOLVED:'):
                            title = line.replace('UNRESOLVED:', '').strip()
                            unfound_titles.append(title)
            
            debug_info["processing_steps"].append(f"Found {len(unfound_titles)} unfound titles from report")
            
            # Read verified titles
            verified_titles = []
            verified_titles_path = PACK / "verified.txt"
            if verified_titles_path.exists():
                with open(verified_titles_path, 'r', encoding='utf-8') as f:
                    verified_titles = [line.strip() for line in f if line.strip()]
            
            debug_info["processing_steps"].append(f"Read {len(verified_titles)} verified titles")
            debug_info["verified_titles"] = verified_titles
            
            # Calculate successful mappings
            successful_mappings = len(verified_titles)
            
            # Create verification results
            for title in verified_titles:
                verification_results.append({
                    "title": title,
                    "status": "verified",
                    "mapped_to": title
                })
                
        except Exception as e:
            debug_info["processing_steps"].append(f"Error in manual verification: {str(e)}")
            # Fallback to simple counting
            successful_mappings = len(titles)
            unfound_titles = []

    # Add final debug info
    debug_info["final_counts"] = {
        "total_titles": len(titles),
        "successful_mappings": successful_mappings,
        "unfound_titles": len(unfound_titles),
        "verification_results": len(verification_results)
    }
    debug_info["processing_steps"].append(f"Final: {successful_mappings} mapped, {len(unfound_titles)} unfound")
    
    return {
        "ok": True,
        "download_id": download_entry["id"],
        "file_id": download_entry["id"],
        "filename": artifact.name,
        "download_url": f"{base_url}/download_file/{download_entry['id']}",
        "file_size": user_artifact_path.stat().st_size,
        "created_at": download_entry["uploaded_at"],
        "processing_results": {
            "song_count": len(titles),
            "successful_mappings": successful_mappings,
            "unfound_titles": unfound_titles,
            "all_titles": titles,
            "verification_results": verification_results
        },
        "debug_info": debug_info
    }
    

@app.get("/download/{slug}")
def download(slug: str, kind: str = "verified"):
    # kind=verified | raw | zip | json | datafile
    targets = {
        "verified": [ROOT / f"{slug}.verified.txt", UPLOADS / f"{slug}.verified.txt"],
        "raw": [ROOT / f"{slug}.raw.txt", UPLOADS / f"{slug}.raw.txt"],
        "zip": [ROOT / f"{slug}.container.zip", UPLOADS / f"{slug}.container.zip"],
        "json": [ROOT / f"{slug}.container.json", UPLOADS / f"{slug}.container.json"],
        "datafile": [ROOT / "pack" / "dataFile.txt", UPLOADS / "pack" / "dataFile.txt"],
    }
    path = first_existing(*targets.get(kind, []))
    if not path:
        raise HTTPException(status_code=404, detail="not found")

    mime = (
        "text/plain" if path.suffix == ".txt"
        else "application/zip" if path.suffix == ".zip"
        else "application/json" if path.suffix == ".json"
        else "application/octet-stream"
    )
    return FileResponse(path, media_type=mime, filename=path.name)

@app.post("/debug/echo")
async def debug_echo(request: Request):
    # return headers and form structure to see what Make is sending
    headers = dict(request.headers)
    form = await request.form()
    fields = {}
    files = {}
    for k, v in form.multi_items():
        if hasattr(v, "filename"):  # UploadFile
            files[k] = {"filename": v.filename, "content_type": v.content_type}
        else:
            fields[k] = str(v)
    return {"headers": headers, "fields": fields, "files": files}

@app.post("/verify_backup")
async def verify_backup(
    request: Request,
    backup: UploadFile = File(..., description="Backup file to verify"),
    secret: str | None = Header(None, alias="X-Secret"),
):
    """Verify and store backup file for user."""
    # simple shared-secret auth, same as /run
    expected = SECRET
    if not expected or secret != expected:
        raise HTTPException(status_code=403, detail="Forbidden")

    user_id = _get_user_id(request)

    # basic validation
    fname = backup.filename or "upload.bkp"
    if not (fname.endswith(".bkp") or fname.endswith(".zip") or fname.endswith(".backup") or fname.endswith(".sbpbackup")):
        raise HTTPException(status_code=400, detail="Upload must be .bkp, .zip, .backup, or .sbpbackup file")

    try:
        # Save uploaded file to user directory
        user_dir = USER_DATA / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        
        backup_path = user_dir / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{fname}"
        with open(backup_path, "wb") as f:
            f.write(await backup.read())

        # Count songs in the backup
        song_count = _count_songs_in_backup(backup_path)
        
        # Check for songs with empty content
        empty_content_info = _check_empty_content_songs(backup_path)
        
        # Save file reference to user data
        file_entry = _save_user_file(user_id, "backups", backup_path, {
            "original_filename": fname,
            "file_size": backup_path.stat().st_size,
            "song_count": song_count,
            "empty_content_info": empty_content_info
        })
        
        # Update user session
        user_sessions[user_id]["backup_uploaded"] = True
        user_sessions[user_id]["backup_path"] = str(backup_path)
        user_sessions[user_id]["song_count"] = song_count

        # Prepare response message
        message = "Backup file verified and stored successfully"
        if empty_content_info["empty_count"] > 0:
            empty_song_names = [song["name"] for song in empty_content_info["empty_songs"][:5]]
            message += f". Warning: {empty_content_info['empty_count']} songs have empty content"
            if len(empty_song_names) > 0:
                message += f" (including: {', '.join(empty_song_names)})"
            if empty_content_info["empty_count"] > 5:
                message += f" and {empty_content_info['empty_count'] - 5} more"

        return {
            "ok": True,
            "message": message,
            "file_id": file_entry["id"],
            "filename": fname,
            "file_size": backup_path.stat().st_size,
            "uploaded_at": file_entry["uploaded_at"],
            "song_count": song_count,
            "empty_content_info": empty_content_info
        }
    except HTTPException:
        raise
    except Exception as e:
        return {
            "ok": False,
            "error": "verification_failed",
            "message": str(e),
        }


@app.get("/auth/google")
async def auth_google():
    """Mock Google OAuth endpoint for testing."""
    return {"message": "Google OAuth not implemented, using hardcoded user"}

@app.get("/auth/google/callback")
async def auth_google_callback():
    """Mock Google OAuth callback for testing."""
    return {"message": "Google OAuth callback not implemented, using hardcoded user"}

@app.post("/auth/login")
async def auth_login(request: Request):
    """Mock login endpoint that creates a session."""
    user_id = _get_user_id(request)
    
    # Create or update user session
    user_sessions[user_id] = {
        "created": datetime.now().isoformat(),
        "user_email": "brian@schaffner.net",
        "backup_uploaded": False,
        "backup_path": None
    }
    
    return {"message": "Login successful", "user_id": user_id}

@app.get("/auth/logout")
async def auth_logout(request: Request):
    """Logout endpoint that clears the session."""
    user_id = _get_user_id(request)
    
    # Clear the user session
    if user_id in user_sessions:
        del user_sessions[user_id]
    
    return {"message": "Logout successful", "user_id": user_id}

@app.get("/user/status")
async def get_user_status(request: Request, secret: str | None = Header(None, alias="X-Secret")):
    """Get user status and backup information."""
    expected = SECRET
    if not expected or secret != expected:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    user_id = _get_user_id_only(request)
    user_session = user_sessions.get(user_id, {})
    
    # Check if user session exists (user is authenticated)
    if not user_session:
        return {
            "user_id": None,
            "user_email": None,
            "authenticated": False,
            "message": "Not authenticated"
        }
    
    user_data = _get_user_data(user_id)
    
    # Get latest backup info
    latest_backup = None
    if user_data.get("backups"):
        latest_backup = user_data["backups"][-1]  # Most recent backup
    
    # Get mapping count
    mapping_count = 0
    if user_data.get("title_mapper"):
        mapping_count = len(user_data["title_mapper"])
    
    return {
        "user_id": user_id,
        "user_email": user_session.get("user_email", "brian@schaffner.net"),
        "authenticated": True,
        "backup_uploaded": len(user_data.get("backups", [])) > 0,
        "backup_count": len(user_data.get("backups", [])),
        "setlist_count": len(user_data.get("setlists", [])),
        "download_count": len(user_data.get("downloads", [])),
        "mapping_count": mapping_count,
        "session_created": user_session.get("created"),
        "song_count": latest_backup.get("metadata", {}).get("song_count", 0) if latest_backup else 0,
        "latest_backup": {
            "filename": latest_backup.get("metadata", {}).get("original_filename") if latest_backup else None,
            "uploaded_at": latest_backup.get("uploaded_at") if latest_backup else None,
            "song_count": latest_backup.get("metadata", {}).get("song_count", 0) if latest_backup else 0,
            "empty_content_info": latest_backup.get("metadata", {}).get("empty_content_info") if latest_backup else None
        } if latest_backup else None,
        "backups": user_data.get("backups", []),
        "setlists": user_data.get("setlists", []),
        "downloads": user_data.get("downloads", [])
    }


@app.get("/user/files")
async def get_user_files(request: Request, secret: str | None = Header(None, alias="X-Secret")):
    """Get user's file history."""
    expected = SECRET
    if not expected or secret != expected:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    user_id = _get_user_id(request)
    user_data = _get_user_data(user_id)
    
    return {
        "backups": user_data.get("backups", []),
        "setlists": user_data.get("setlists", []),
        "downloads": user_data.get("downloads", [])
    }


@app.get("/download_file/{file_id}")
async def download_user_file(
    file_id: str, 
    request: Request, 
    secret: str | None = Header(None, alias="X-Secret"),
    secret_query: str | None = Query(None, alias="X-Secret")
):
    """Download a user's file by ID."""
    expected = SECRET
    # Check both header and query parameter for authentication
    auth_secret = secret or secret_query
    if not expected or auth_secret != expected:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    # Get session ID from header or query parameter
    session_id = request.headers.get("X-Session-ID") or request.query_params.get("X-Session-ID")
    if not session_id:
        session_id = str(uuid.uuid4())
    
    if session_id not in user_sessions:
        user_sessions[session_id] = {
            "created": datetime.now().isoformat(),
            "backup_uploaded": False,
            "backup_path": None
        }
    
    user_id = _get_user_id(request)
    user_data = _get_user_data(user_id)
    
    # Find file in user's data
    file_entry = None
    for file_type in ["backups", "setlists", "downloads"]:
        for file in user_data.get(file_type, []):
            if file["id"] == file_id:
                file_entry = file
                break
        if file_entry:
            break
    
    if not file_entry:
        raise HTTPException(status_code=404, detail="File not found")
    
    file_path = Path(file_entry["path"])
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File no longer exists")
    
    # Use original filename base with .sbp extension
    original_filename = file_entry.get("metadata", {}).get("original_filename", file_entry["filename"])
    # Remove extension from original filename and add .sbp
    original_base = Path(original_filename).stem
    download_filename = f"{original_base}.sbp"
    
    return FileResponse(
        file_path, 
        media_type="application/octet-stream",
        filename=download_filename
    )


@app.get("/admin/errors")
async def get_admin_errors(secret: str | None = Header(None, alias="X-Secret")):
    """Get detailed error information for admin."""
    expected = SECRET
    if not expected or secret != expected:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    # In a real implementation, you'd want to log errors to a database
    # For now, return basic system info
    return {
        "system_info": {
            "root": str(ROOT),
            "uploads": str(UPLOADS),
            "user_data": str(USER_DATA),
            "active_sessions": len(user_sessions),
            "total_users": len(user_files)
        },
        "recent_errors": [],  # Would be populated from error logs
        "system_health": "ok"
    }


@app.get("/user/title-mappings")
async def get_user_title_mappings(request: Request, secret: str | None = Header(None, alias="X-Secret")):
    """Get user's title mappings."""
    expected = SECRET
    if not expected or secret != expected:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    user_id = _get_user_id(request)
    user_data = _get_user_data(user_id)
    
    # Get title mappings from user data
    mappings = user_data.get("title_mapper", {})
    
    return {
        "mappings": mappings,
        "count": len(mappings)
    }


@app.post("/user/title-mappings")
async def save_user_title_mappings(
    request: Request,
    mappings: dict,
    secret: str | None = Header(None, alias="X-Secret")
):
    """Save user's title mappings."""
    expected = SECRET
    if not expected or secret != expected:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    user_id = _get_user_id(request)
    user_dir = USER_DATA / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    mapper_path = user_dir / "title_mapper.json"
    
    with open(mapper_path, 'w', encoding='utf-8') as f:
        json.dump(mappings, f, ensure_ascii=False, indent=2)
    
    # Update user data with title mappings
    user_data = _get_user_data(user_id)
    user_data["title_mapper"] = mappings
    _save_user_data(user_id, user_data)
    
    return {
        "ok": True,
        "message": "Title mappings saved successfully",
        "count": len(mappings)
    }


@app.get("/user/archive")
async def get_user_archive(request: Request, secret: str | None = Header(None, alias="X-Secret")):
    """Get user's archive of processed files."""
    if secret != SECRET:
        raise HTTPException(401, "unauthorized")
    
    user_id = _get_user_id(request)
    user_data = _get_user_data(user_id)
    
    # Get all file types
    backups = user_data.get("backups", [])
    setlists = user_data.get("setlists", [])
    downloads = user_data.get("downloads", [])
    title_mapper = user_data.get("title_mapper", {})
    
    # Create summary
    summary = {
        "total_backups": len(backups),
        "total_setlists": len(setlists),
        "total_downloads": len(downloads),
        "total_mappings": len(title_mapper),
        "latest_backup": backups[-1] if backups else None,
        "latest_setlist": setlists[-1] if setlists else None,
        "latest_download": downloads[-1] if downloads else None,
        "total_combined_items": len(setlists) + len(downloads)
    }
    
    # Create combined items (setlists with their downloads)
    combined_items = []
    for setlist in setlists:
        item = setlist.copy()
        # Find downloads for this setlist
        setlist_downloads = [d for d in downloads if d.get("metadata", {}).get("setlist_id") == setlist.get("id")]
        item["downloads"] = setlist_downloads
        item["has_downloads"] = len(setlist_downloads) > 0
        combined_items.append(item)
    
    return JSONResponse(content={
        "downloads": downloads,
        "backups": backups,
        "setlists": setlists,
        "combined_items": combined_items,
        "title_mapper": title_mapper,
        "summary": summary
    })

@app.get("/user/catalog")
async def get_user_catalog(request: Request, secret: str | None = Header(None, alias="X-Secret")):
    """Get the user's song catalog from their backup."""
    expected = SECRET
    if not expected or secret != expected:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    user_id = _get_user_id(request)
    user_data = _get_user_data(user_id)
    
    if not user_data.get("backups"):
        raise HTTPException(status_code=400, detail="No backup uploaded")
    
    latest_backup = user_data["backups"][-1]
    backup_path = Path(latest_backup["path"])
    
    try:
        # Extract catalog from backup using the same logic as backup_to_catalog.py
        import zipfile
        
        with zipfile.ZipFile(backup_path, 'r') as zf:
            data_bytes = zf.read("dataFile.txt")
        
        text = data_bytes.decode("utf-8-sig").strip()
        
        # Parse JSON content to extract song titles
        songs_items = []
        
        def collect_from_obj(obj):
            if isinstance(obj, dict):
                if isinstance(obj.get("songs"), list):
                    songs_items.extend(obj["songs"])
            elif isinstance(obj, list):
                songs_items.extend(obj)
        
        try:
            obj = json.loads(text)
            collect_from_obj(obj)
        except json.JSONDecodeError:
            # JSONL: parse each non-empty line
            for ln in (ln for ln in text.splitlines() if ln.strip()):
                try:
                    obj = json.loads(ln)
                    collect_from_obj(obj)
                except json.JSONDecodeError:
                    continue
        
        # Extract titles and songs with IDs
        titles = []
        songs = []
        for s in songs_items:
            if isinstance(s, dict):
                t = s.get("title") or s.get("name")
                if isinstance(t, str) and t.strip():
                    titles.append(t.strip())
                    # Only include active (non-deleted) songs
                    if not s.get("Deleted", False):
                        songs.append({
                            "id": s.get("Id"),
                            "name": t.strip()
                        })
            elif isinstance(s, str) and s.strip():
                titles.append(s.strip())
        
        return {
            "catalog": sorted(set(titles)),  # Remove duplicates and sort
            "songs": songs,  # Songs with IDs for the new mapping UI
            "count": len(set(titles))
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to extract catalog: {str(e)}")


@app.post("/user/verify-titles")
async def verify_user_titles(
    request: Request,
    titles: list[str],
    secret: str | None = Header(None, alias="X-Secret")
):
    """Verify titles against user's catalog and return suggestions."""
    expected = SECRET
    if not expected or secret != expected:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    user_id = _get_user_id(request)
    
    # Get user's catalog
    catalog_response = await get_user_catalog(request, secret)
    catalog = catalog_response["catalog"]
    
    # Get user's existing mappings
    user_dir = USER_DATA / user_id
    mapper_path = user_dir / "title_mapper.json"
    existing_mappings = {}
    if mapper_path.exists():
        with open(mapper_path, 'r', encoding='utf-8') as f:
            existing_mappings = json.load(f)
    
    # Normalize function (same as titles_verify.py)
    def normalize_key(s: str) -> str:
        import re
        s = s.strip()
        s = re.sub(r'\s+', ' ', s)
        s = re.sub(r"[\"'`']", "", s)
        s = s.replace('&', 'and')
        s = re.sub(r'\(feat[^\)]*\)', '', s, flags=re.I)
        s = re.sub(r'[^A-Za-z0-9 ]+', ' ', s)
        s = re.sub(r'\s+', ' ', s).strip()
        return s.casefold()
    
    # Build catalog index
    exact = {}
    canon_list = []
    for title in catalog:
        canon = title.strip()
        if not canon:
            continue
        nk = normalize_key(canon)
        exact[nk] = canon
        canon_list.append(canon)
    
    # Get suggestions for each title
    import difflib
    
    def best_suggestions(query: str, choices: list[str], n: int = 5):
        scores = []
        for c in choices:
            r = difflib.SequenceMatcher(a=normalize_key(query), b=normalize_key(c)).ratio()
            scores.append((c, r))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:n]
    
    # First apply title mappings (like titles_verify.py does)
    mapped_titles = []
    for title in titles:
        nk = normalize_key(title)
        if nk in existing_mappings:
            mapped = existing_mappings[nk]
            if mapped == "":
                continue  # dropped
            mapped_titles.append(mapped)
        else:
            mapped_titles.append(title)
    
    # Now verify the mapped titles against catalog
    results = []
    for title in mapped_titles:
        nk = normalize_key(title)
        
        # Check for exact match
        if nk in exact:
            results.append({
                "title": title,
                "status": "exact_match",
                "mapped_to": exact[nk],
                "suggestions": []
            })
            continue
        
        # Get suggestions
        suggestions = best_suggestions(title, canon_list, n=5)
        results.append({
            "title": title,
            "status": "needs_mapping",
            "mapped_to": None,
            "suggestions": [{"title": s[0], "score": s[1]} for s in suggestions]
        })
    
    return {
        "results": results,
        "total": len(titles),
        "needs_mapping": len([r for r in results if r["status"] == "needs_mapping"])
        }


@app.post("/user/reprocess-setlist")
async def reprocess_setlist(
    request: Request,
    secret: str | None = Header(None, alias="X-Secret")
):
    """Reprocess the most recent setlist with updated mappings."""
    expected = SECRET
    if not expected or secret != expected:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    user_id = _get_user_id(request)
    user_data = _get_user_data(user_id)
    
    # Get the most recent setlist
    if not user_data.get("setlists"):
        raise HTTPException(status_code=400, detail="No setlist found to reprocess")
    
    latest_setlist = user_data["setlists"][-1]
    setlist_path = Path(latest_setlist["path"])
    
    if not setlist_path.exists():
        raise HTTPException(status_code=400, detail="Setlist file not found")
    
    # Get the latest backup
    if not user_data.get("backups"):
        raise HTTPException(status_code=400, detail="No backup found")
    
    latest_backup = user_data["backups"][-1]
    backup_path = latest_backup["path"]
    
    try:
        # Reprocess the setlist using the updated mappings
        env = _prepare_env()
        result = _process_with_user_backup(
            setlist_path, 
            latest_setlist["name"], 
            backup_path,
            env
        )
        
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Reprocessing failed: {result.stderr}")
        
        # Create new download file
        file_id = str(uuid.uuid4())
        download_path = USER_DATA / user_id / f"download_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{latest_setlist['name']}.sbp"
        
        # Copy the generated file to user's download directory
        import shutil
        artifact_path = PACK / f"{latest_setlist['name']}.sbp"
        if artifact_path.exists():
            shutil.copy2(artifact_path, download_path)
            
            # Update user's download history
            download_entry = {
                "id": file_id,
                "filename": f"{latest_setlist['name']}.sbp",
                "original_filename": latest_setlist["filename"],
                "path": str(download_path),
                "created": datetime.now().isoformat(),
                "size": download_path.stat().st_size
            }
            
            if "downloads" not in user_data:
                user_data["downloads"] = []
            user_data["downloads"].append(download_entry)
            _save_user_data(user_id, user_data)
            
            # Generate download URL
            download_url = f"{request.url.scheme}://{request.url.netloc}/download_file/{file_id}"
            
            return {
                "ok": True,
                "message": "Setlist reprocessed successfully",
                "download_url": download_url,
                "file_id": file_id
            }
        else:
            raise HTTPException(status_code=500, detail="Generated file not found")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reprocessing error: {str(e)}")
