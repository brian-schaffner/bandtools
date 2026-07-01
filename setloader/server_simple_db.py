#!/usr/local/bin/python3
"""
FastAPI service for orchestrating set loader runs with simple SQLite database.
"""
from __future__ import annotations

import os
import re
import json
import uuid
import time
import shutil
import asyncio
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from fastapi import FastAPI, Request, HTTPException, File, UploadFile, Form, Header, Query
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

# Database imports
from simple_database import db

# Initialize FastAPI app
app = FastAPI(title="SetLoader API", version="2.1.0")

# CORS middleware
_tailnet_origin = os.getenv("TAILNET_ORIGIN", "https://setlists.risk-tailor.ts.net")
_app_url = os.getenv("APP_URL", "").rstrip("/")
_cors_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3002",
    "http://127.0.0.1:3002",
    _tailnet_origin,
]
if _app_url:
    _cors_origins.append(_app_url)
_fly_app = os.getenv("FLY_APP_NAME", "").strip()
if _fly_app:
    _cors_origins.append(f"https://{_fly_app}.fly.dev")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
SECRET = os.getenv("SECRET", "change-me")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8002")

# Helper functions
def get_user_from_request(request: Request) -> Optional[Dict]:
    """Get user from request headers."""
    session_token = request.headers.get("X-Session-ID")
    if not session_token:
        return None
    
    session = db.get_active_session(session_token)
    if not session:
        return None
    
    return db.get_user_by_id(session['user_id'])

def create_session_token() -> str:
    """Create a new session token."""
    return str(uuid.uuid4())

# API Endpoints

@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "SetLoader API", "version": "2.1.0"}

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@app.get("/gig/suggestions")
async def gig_suggestions(
    date: Optional[str] = Query(None, description="Target date YYYY-MM-DD"),
    secret: Optional[str] = Header(None, alias="X-Secret"),
):
    """Suggest output names from the band's public gig calendar."""
    if secret != SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")

    try:
        from gig_calendar import get_gig_suggestions, get_local_today

        target_date = None
        if date:
            try:
                target_date = datetime.strptime(date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format; use YYYY-MM-DD")

        return get_gig_suggestions(target_date=target_date)
    except HTTPException:
        raise
    except Exception as e:
        print(f"Gig calendar lookup failed: {e}")
        raise HTTPException(status_code=502, detail=f"Gig calendar lookup failed: {str(e)}")

# Authentication endpoints
@app.get("/auth/google")
async def auth_google():
    """Initiate Google OAuth flow."""
    try:
        from google_oauth import google_oauth
        if not google_oauth.client_id:
            return JSONResponse(
                status_code=503,
                content={
                    "configured": False,
                    "detail": "Google OAuth is not configured on the server",
                },
            )
        authorization_url, state = google_oauth.get_authorization_url()
        return {"authorization_url": authorization_url, "state": state, "configured": True}
    except ImportError as e:
        print(f"Google OAuth import error: {e}")
        raise HTTPException(status_code=503, detail="Google OAuth libraries not installed")
    except Exception as e:
        print(f"Google OAuth error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/auth/google/callback")
async def auth_google_callback(code: str, state: str = None):
    """Handle Google OAuth callback."""
    try:
        from google_oauth import google_oauth
        
        # Exchange code for credentials and user info
        credentials, user_info = google_oauth.exchange_code_for_token(code, state)
        
        # Get or create user
        user = db.get_user_by_email(user_info['email'])
        if not user:
            user = db.create_user(
                email=user_info['email'],
                name=user_info.get('name', user_info['email'].split('@')[0])
            )
        
        # Save credentials for the user
        google_oauth.save_credentials(user['id'], credentials)
        
        # Create session
        session_token = create_session_token()
        session = db.create_session(user['id'], session_token)
        
        return {
            "message": "Login successful",
            "user_id": user['id'],
            "session_token": session_token,
            "user_email": user['email'],
            "user_name": user['name']
        }
    except Exception as e:
        print(f"Google OAuth callback error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/auth/login")
async def auth_login(request: Request):
    """Login endpoint that creates a session (fallback for development)."""
    # For development, use hardcoded user if Google OAuth is not configured
    try:
        from oauth_config import validate_config
        if not validate_config():
            # Fallback to hardcoded user for development
            user = db.get_user_by_email("brian@schaffner.net")
            if not user:
                user = db.create_user(
                    email="brian@schaffner.net",
                    name="Brian Schaffner"
                )
            
            # Create session
            session_token = create_session_token()
            session = db.create_session(user['id'], session_token)
            
            return {
                "message": "Login successful (development mode)",
                "user_id": user['id'],
                "session_token": session_token,
                "user_email": user['email'],
                "user_name": user['name']
            }
    except Exception as e:
        print(f"Development login error: {e}")
        raise HTTPException(status_code=500, detail="Login failed")

@app.get("/auth/logout")
async def auth_logout(request: Request):
    """Logout endpoint that clears the session."""
    session_token = request.headers.get("X-Session-ID")
    if session_token:
        db.invalidate_session(session_token)
    
    return {"message": "Logout successful"}

@app.get("/user/status")
async def get_user_status(request: Request, secret: Optional[str] = Header(None, alias="X-Secret")):
    """Get user status and information."""
    if secret != SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    user = get_user_from_request(request)
    if not user:
        return {
            "user_id": None,
            "user_email": None,
            "authenticated": False,
            "message": "Not authenticated"
        }
    
    # Get user's files
    backup_files = db.get_user_files(user['id'], "backup")
    setlist_files = db.get_user_files(user['id'], "setlist")
    download_files = db.get_user_files(user['id'], "download")
    
    # Get title mappings count
    title_mappings = db.get_user_title_mappings(user['id'])
    
    # Get latest backup
    latest_backup = None
    if backup_files:
        latest_backup = {
            "id": backup_files[0]['id'],
            "filename": backup_files[0]['original_filename'],
            "uploaded_at": backup_files[0]['created_at'],
            "file_size": backup_files[0]['file_size']
        }
    
    return {
        "user_id": user['id'],
        "user_email": user['email'],
        "authenticated": True,
        "backup_uploaded": len(backup_files) > 0,
        "backup_count": len(backup_files),
        "setlist_count": len(setlist_files),
        "download_count": len(download_files),
        "mapping_count": len(title_mappings),
        "session_created": user['created_at'],
        "latest_backup": latest_backup
    }

@app.get("/user/catalog")
async def get_user_catalog(request: Request, secret: Optional[str] = Header(None, alias="X-Secret")):
    """Get user's song catalog from latest backup."""
    if secret != SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    user = get_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Get latest backup
    latest_backup = db.get_latest_backup(user['id'])
    if not latest_backup:
        return {"catalog": [], "count": 0}
    
    # Extract songs from the SBP backup file
    try:
        from sbp_library import SBPLibrary
        sbp = SBPLibrary()
        backup_file = sbp.load_sbp_file(Path(latest_backup['file_path']))
        
        # Get all songs from the backup
        songs = sbp.get_active_songs(backup_file)
        catalog = [song.name for song in songs if song.name]
        return {"catalog": catalog, "count": len(catalog)}
    except Exception as e:
        print(f"Error extracting catalog from backup: {e}")
        import traceback
        traceback.print_exc()
        return {"catalog": [], "count": 0}

@app.get("/user/title-mappings")
async def get_user_title_mappings(request: Request, secret: Optional[str] = Header(None, alias="X-Secret")):
    """Get user's title mappings."""
    if secret != SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    user = get_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    mappings = db.get_user_title_mappings(user['id'])
    mappings_dict = {mapping['pdf_title']: mapping['catalog_title'] for mapping in mappings}
    
    return {
        "mappings": mappings_dict,
        "count": len(mappings_dict)
    }

@app.post("/user/title-mappings")
async def post_user_title_mapping(
    request: Request,
    secret: Optional[str] = Header(None, alias="X-Secret")
):
    """
    Create or update title mappings.

    Accepts either:
      - Single mapping: { pdf_title, catalog_title, catalog_song_id? }
      - Bulk mapping object: { "userTitle1": "Catalog Title 1", ... }
    """
    if secret != SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")

    user = get_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        body = await request.json()
        
        # Case 1: single mapping payload
        if isinstance(body, dict) and ('pdf_title' in body or 'catalog_title' in body):
            pdf_title = body.get('pdf_title')
            catalog_title = body.get('catalog_title')
            catalog_song_id = body.get('catalog_song_id')
            if not pdf_title or not catalog_title:
                raise HTTPException(status_code=400, detail="pdf_title and catalog_title are required")
            mapping = db.save_title_mapping(user['id'], pdf_title, catalog_title, catalog_song_id)
            return {"ok": True, "mapping": mapping}

        # Case 2: bulk mapping dictionary { pdf_title: catalog_title }
        if isinstance(body, dict):
            # First, delete all existing mappings for this user
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM title_mappings WHERE user_id = ?", (user['id'],))
            conn.commit()
            conn.close()
            
            # Then, save all new mappings
            saved = 0
            for pdf_title, catalog_title in body.items():
                if not pdf_title or not catalog_title:
                    # Skip invalid entries but continue
                    continue
                db.save_title_mapping(user['id'], str(pdf_title), str(catalog_title))
                saved += 1
            
            # Update the user's mappings file for immediate use
            try:
                user_data_dir = Path("user_data") / user['id']
                user_data_dir.mkdir(parents=True, exist_ok=True)
                mappings_file = user_data_dir / "title_mapper.json"
                
                # Load ALL mappings from database (not just the new ones)
                all_mappings = db.get_user_title_mappings(user['id'])
                all_mappings_dict = {mapping['pdf_title']: mapping['catalog_title'] for mapping in all_mappings}
                
                # Create the mappings file with ALL mappings from database
                with open(mappings_file, 'w', encoding='utf-8') as f:
                    json.dump({"title_mapper": all_mappings_dict}, f, indent=2)
                print(f"Updated mappings file: {mappings_file} with {len(all_mappings_dict)} mappings")
            except Exception as e:
                print(f"Warning: Could not update mappings file: {e}")
            
            # Force database connection to ensure transaction is committed
            import time
            time.sleep(0.1)  # Small delay to ensure database transaction is committed
            
            return {"ok": True, "count": saved}

        raise HTTPException(status_code=400, detail="Invalid payload format")
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error saving title mapping: {e}")
        return JSONResponse(status_code=500, content={"ok": False, "error": str(e)})

@app.get("/user/archive")
async def get_user_archive(request: Request, secret: Optional[str] = Header(None, alias="X-Secret")):
    """Get user's archive of processed files."""
    if secret != SECRET:
        raise HTTPException(status_code=401, detail="unauthorized")
    
    user = get_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Get all file types
    backup_files = db.get_user_files(user['id'], "backup")
    setlist_files = db.get_user_files(user['id'], "setlist")
    download_files = db.get_user_files(user['id'], "download")
    
    # Get title mappings
    title_mappings = db.get_user_title_mappings(user['id'])
    mappings_dict = {mapping['pdf_title']: mapping['catalog_title'] for mapping in title_mappings}
    
    # Create summary
    summary = {
        "total_backups": len(backup_files),
        "total_setlists": len(setlist_files),
        "total_downloads": len(download_files),
        "total_mappings": len(mappings_dict),
        "latest_backup": backup_files[0] if backup_files else None,
        "latest_setlist": setlist_files[0] if setlist_files else None,
        "latest_download": download_files[0] if download_files else None,
        "total_combined_items": len(setlist_files) + len(download_files)
    }
    
    # Format files for response
    def format_file(file_upload):
        return {
            "id": file_upload['id'],
            "filename": file_upload['original_filename'],
            "file_size": file_upload['file_size'],
            "uploaded_at": file_upload['created_at'],
            "metadata": file_upload['metadata'] or {}
        }
    
    return {
        "downloads": [format_file(f) for f in download_files],
        "backups": [format_file(f) for f in backup_files],
        "setlists": [format_file(f) for f in setlist_files],
        "title_mapper": mappings_dict,
        "summary": summary
    }

@app.delete("/user/archive")
async def clear_user_archive(request: Request, secret: Optional[str] = Header(None, alias="X-Secret")):
    """Clear user's downloads while preserving title mappings."""
    if secret != SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    user = get_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Clear downloads, setlists, and backups but keep title mappings
    db.clear_user_files(user['id'])
    
    return {"ok": True, "message": "Archive cleared (title mappings preserved)"}

@app.delete("/user/archive/{item_type}/{item_id}")
async def delete_archive_item(
    item_type: str,
    item_id: str,
    request: Request,
    secret: Optional[str] = Header(None, alias="X-Secret")
):
    """Delete an archived item."""
    if secret != SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    user = get_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Get the file from database
    files = db.get_user_files(user['id'])
    file_upload = next((f for f in files if f['id'] == item_id), None)
    
    if not file_upload:
        raise HTTPException(status_code=404, detail=f"{item_type.title()} not found")
    
    # Verify the file type matches
    if file_upload['file_type'] != item_type:
        raise HTTPException(status_code=400, detail=f"File type mismatch: expected {item_type}, got {file_upload['file_type']}")
    
    try:
        # Delete the physical file if it exists
        file_path = Path(file_upload['file_path'])
        if file_path.exists():
            file_path.unlink()
            print(f"🗑️ Deleted file: {file_path}")
        
        # Delete from database
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM file_uploads WHERE id = ? AND user_id = ?",
            (item_id, user['id'])
        )
        conn.commit()
        conn.close()
        
        return {"ok": True, "message": f"{item_type.title()} deleted successfully"}
        
    except Exception as e:
        print(f"Error deleting {item_type} {item_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete {item_type}: {str(e)}")

@app.post("/user/reprocess-archive")
async def reprocess_archive_item(
    request: Request,
    item_type: str = Form(...),
    item_id: str = Form(...),
    secret: Optional[str] = Header(None, alias="X-Secret")
):
    """Reprocess an archived item (setlist, backup, or download)."""
    if secret != SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    user = get_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # For now, return a not implemented message
    # This would need to be implemented to actually reprocess files
    return {
        "ok": False, 
        "message": f"Reprocessing {item_type} items is not yet implemented in the database version"
    }

@app.post("/verify_backup")
async def verify_backup(
    request: Request,
    backup: UploadFile = File(..., description="Backup file to verify"),
    secret: Optional[str] = Header(None, alias="X-Secret")
):
    """Verify and store backup file for user."""
    if secret != SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    user = get_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Basic validation
    fname = backup.filename or "upload.bkp"
    if not (fname.endswith(".bkp") or fname.endswith(".zip") or fname.endswith(".backup") or fname.endswith(".sbpbackup")):
        raise HTTPException(status_code=400, detail="Upload must be .bkp, .zip, .backup, or .sbpbackup file")
    
    try:
        # Create user directory
        user_dir = Path(f"user_data/{user['id']}")
        user_dir.mkdir(parents=True, exist_ok=True)
        
        # Save uploaded file with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = user_dir / f"backup_{timestamp}_{fname}"
        
        with open(backup_path, "wb") as f:
            f.write(await backup.read())
        
        # Count songs in the backup (basic validation)
        song_count = 0
        try:
            from sbp_library import SBPLibrary
            sbp = SBPLibrary()
            backup_file = sbp.load_sbp_file(backup_path)
            songs = sbp.get_active_songs(backup_file)
            song_count = len([song for song in songs if song.name])
        except Exception as e:
            print(f"Warning: Could not count songs in backup: {e}")
            song_count = 0
        
        # Save file to database
        file_upload = db.save_file_upload(
            user_id=user['id'],
            file_type="backup",
            original_filename=fname,
            stored_filename=backup_path.name,
            file_path=str(backup_path),
            file_size=backup_path.stat().st_size,
            mime_type="application/octet-stream",
            metadata={
                "original_filename": fname,
                "song_count": song_count,
                "uploaded_at": datetime.now().isoformat()
            }
        )
        
        return {
            "verified": True,
            "message": f"Backup file verified and stored successfully ({song_count} songs found)",
            "file_id": file_upload['id'],
            "filename": fname,
            "song_count": song_count,
            "file_size": backup_path.stat().st_size
        }
        
    except Exception as e:
        print(f"Error processing backup upload: {e}")
        raise HTTPException(status_code=500, detail=f"Backup processing failed: {str(e)}")

@app.post("/process_setlist_streaming")
async def process_setlist_streaming(
    request: Request,
    secret_form: Optional[str] = Form(None, alias="secret"),
    x_secret: Optional[str] = Header(default=None, alias="X-Secret"),
    secret_query: Optional[str] = Query(default=None, alias="secret"),
    name: str = Form("Set"),
):
    """Process setlist with streaming progress updates."""
    provided = secret_form or x_secret or secret_query
    if provided != SECRET:
        raise HTTPException(401, "unauthorized")

    user = get_user_from_request(request)
    if not user:
        raise HTTPException(401, "Not authenticated")
    
    # Check if user has uploaded a backup
    latest_backup = db.get_latest_backup(user['id'])
    if not latest_backup:
        raise HTTPException(400, "No backup file uploaded. Please upload a backup file first.")

    # Parse form data once
    form = await request.form()
    pdf_file = form.get("file") or form.get("pdf")
    
    if not pdf_file:
        raise HTTPException(400, "No setlist file provided")

    pdf_bytes = await pdf_file.read()
    filename = pdf_file.filename or f"{name}.pdf"
    _validate_upload_bytes(pdf_bytes, filename)

    async def generate_progress():
        working_dir = None
        try:
            yield f"data: {json.dumps({'stage': 'pdf_extraction', 'message': f'PDF file ready ({len(pdf_bytes)} bytes)', 'progress': 15})}\n\n"
            
            # Create working directory for this processing event
            working_dir = Path(f"work/{user['id']}_{int(time.time())}")
            working_dir.mkdir(parents=True, exist_ok=True)
            
            # Step 1: PDF Extraction with detailed progress
            yield f"data: {json.dumps({'stage': 'pdf_extraction', 'message': 'Starting PDF extraction...', 'progress': 0})}\n\n"
            
            from pdf_extraction_library import PDFExtractor, UnsupportedFileTypeError
            pdf_extractor = PDFExtractor()

            file_path = _save_upload_file(working_dir, pdf_bytes, filename)

            yield f"data: {json.dumps({'stage': 'pdf_extraction', 'message': 'File saved, starting extraction...', 'progress': 10})}\n\n"
            
            # Create progress callback for streaming
            progress_messages = []
            def progress_callback(message):
                progress_messages.append(message)
            
            # Extract songs using the PDFExtractor
            prompt_path = Path("prompts/openai_extraction.prompt")
            try:
                extraction_result = pdf_extractor.extract_songs(file_path, prompt_path, progress_callback=progress_callback)
            except UnsupportedFileTypeError as e:
                yield f"data: {json.dumps({'stage': 'pdf_extraction', 'message': str(e), 'progress': 100, 'error': True})}\n\n"
                return

            # Stream progress messages
            for i, message in enumerate(progress_messages):
                progress = 20 + (i * 60 / len(progress_messages)) if progress_messages else 20
                yield f"data: {json.dumps({'stage': 'pdf_extraction', 'message': message, 'progress': int(progress)})}\n\n"
                await asyncio.sleep(0.1)  # Small delay to make progress visible
            
            if not extraction_result["success"]:
                error_msg = f"Extraction failed: {extraction_result['error']}"
                yield f"data: {json.dumps({'stage': 'pdf_extraction', 'message': error_msg, 'progress': 100, 'error': True})}\n\n"
                return
            
            # Save the extraction result to JSON file
            with open(working_dir / "titles.json", 'w', encoding='utf-8') as f:
                json.dump(extraction_result["data"], f, indent=2)

            # Compute extraction counts
            total_extracted = 0
            try:
                data_obj = extraction_result.get("data") or {}
                for set_obj in data_obj.get('sets', []):
                    total_extracted += len(set_obj.get('songs', []))
                total_extracted += len(data_obj.get('extras', []))
            except Exception:
                total_extracted = 0
            
            # Get the actual titles for the frontend
            titles_list = []
            try:
                with open(working_dir / "titles.json", 'r', encoding='utf-8') as f:
                    titles_data = json.load(f)
                    # Extract all song titles from sets and extras
                    for set_data in titles_data.get('sets', []):
                        for song in set_data.get('songs', []):
                            if song.get('title'):
                                titles_list.append(song['title'])
                    for extra in titles_data.get('extras', []):
                        if extra.get('title'):
                            titles_list.append(extra['title'])
            except Exception as e:
                print(f"Warning: Could not extract titles from JSON: {e}")
                titles_list = []
            
            yield f"data: {json.dumps({'stage': 'pdf_extraction', 'message': 'PDF extraction completed successfully', 'progress': 100, 'success': True, 'total': total_extracted, 'titles': titles_list})}\n\n"
            
            # Step 2: Title Validation
            yield f"data: {json.dumps({'stage': 'title_validation', 'message': 'Starting title validation...', 'progress': 0})}\n\n"
            
            from title_validation_library import validate_titles_from_json
            backup_path = Path(latest_backup['file_path'])
            
            # Load the titles JSON
            with open(working_dir / "titles.json", 'r', encoding='utf-8') as f:
                titles_data = json.load(f)
            
            yield f"data: {json.dumps({'stage': 'title_validation', 'message': 'Validating titles against catalog...', 'progress': 50})}\n\n"
            
            # Validate titles using database mappings
            validation_result = validate_titles_with_database(titles_data, user['id'], backup_path)

            # Compute validation counts
            validated_count = 0
            total_count = 0
            unfound_titles = []
            try:
                for set_obj in validation_result.get('sets', []):
                    for song in set_obj.get('songs', []):
                        total_count += 1
                        if song.get('validated'):
                            validated_count += 1
                        else:
                            unfound_titles.append(song.get('title') or '')
                for extra in validation_result.get('extras', []):
                    total_count += 1
                    if extra.get('validated'):
                        validated_count += 1
                    else:
                        unfound_titles.append(extra.get('title') or '')
            except Exception:
                pass
            
            yield f"data: {json.dumps({'stage': 'title_validation', 'message': f'Validated {validated_count} of {total_count}', 'progress': 100, 'success': True, 'validated': validated_count, 'total': total_count, 'unfound_titles': unfound_titles})}\n\n"
            
            # Save validated titles
            with open(working_dir / "validated_titles.json", 'w', encoding='utf-8') as f:
                json.dump(validation_result, f, indent=2)
            
            # Step 3: Song Extraction
            yield f"data: {json.dumps({'stage': 'song_extraction', 'message': 'Starting song extraction...', 'progress': 0})}\n\n"
            
            from song_extraction_library import SongExtractor
            song_extractor = SongExtractor(user['id'], backup_path)
            extraction_result = song_extractor.extract_and_save(validation_result, working_dir / f"{name}.sbp", name)
            
            yield f"data: {json.dumps({'stage': 'song_extraction', 'message': 'Creating SBP file...', 'progress': 50})}\n\n"
            
            if not extraction_result["success"]:
                error_msg = f"Song extraction failed: {extraction_result['error']}"
                yield f"data: {json.dumps({'stage': 'song_extraction', 'message': error_msg, 'progress': 100, 'error': True})}\n\n"
                return
            
            yield f"data: {json.dumps({'stage': 'song_extraction', 'message': 'SBP file created successfully', 'progress': 100, 'success': True})}\n\n"
            
            # Move file to permanent downloads directory
            downloads_dir = Path("downloads")
            downloads_dir.mkdir(exist_ok=True)
            
            # Create unique filename to avoid conflicts
            timestamp = int(time.time())
            permanent_filename = f"{name}_{timestamp}.sbp"
            permanent_path = downloads_dir / permanent_filename
            
            # Move the file from working directory to permanent location
            shutil.move(str(working_dir / f"{name}.sbp"), str(permanent_path))
            
            # Save to user's archive with permanent path
            archive_result = db.save_file_upload(
                user_id=user['id'],
                file_type='download',
                original_filename=f"{name}.sbp",
                stored_filename=permanent_filename,
                file_path=str(permanent_path),
                file_size=permanent_path.stat().st_size,
                mime_type="application/octet-stream",
                metadata={
                    "set_name": name
                }
            )
            
            # Final result
            yield f"data: {json.dumps({'stage': 'complete', 'message': 'Processing completed successfully', 'progress': 100, 'success': True, 'download_id': archive_result['id'], 'filename': f'{name}.sbp'})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'stage': 'error', 'message': f'Processing failed: {str(e)}', 'progress': 100, 'error': True})}\n\n"
        finally:
            # Clean up working directory
            try:
                if working_dir and working_dir.exists():
                    shutil.rmtree(working_dir)
            except Exception:
                pass

    return StreamingResponse(generate_progress(), media_type="text/plain")

@app.post("/process_setlist_simple")
async def process_setlist_simple(
    request: Request,
    secret_form: Optional[str] = Form(None, alias="secret"),
    x_secret: Optional[str] = Header(default=None, alias="X-Secret"),
    secret_query: Optional[str] = Query(default=None, alias="secret"),
    name: str = Form("Set"),
):
    """Process setlist using the new three-step workflow with database."""
    provided = secret_form or x_secret or secret_query
    if provided != SECRET:
        raise HTTPException(401, "unauthorized")

    user = get_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Check if user has uploaded a backup
    latest_backup = db.get_latest_backup(user['id'])
    if not latest_backup:
        raise HTTPException(400, "No backup file uploaded. Please upload a backup file first.")

    try:
        # Extract PDF bytes and filename
        pdf_bytes, slug_hint = await _extract_pdf_bytes(request, name)
        _validate_upload_bytes(pdf_bytes, slug_hint)
        
        # Create working directory for this processing event
        working_dir = Path(f"work/{user['id']}_{int(time.time())}")
        working_dir.mkdir(parents=True, exist_ok=True)
        
        # Step 1: Setlist extraction
        from pdf_extraction_library import PDFExtractor, UnsupportedFileTypeError
        pdf_extractor = PDFExtractor()
        file_path = _save_upload_file(working_dir, pdf_bytes, slug_hint)

        prompt_path = Path("prompts/openai_extraction.prompt")

        def progress_callback(message):
            print(f"[PDF_EXTRACTION] {message}")

        try:
            extraction_result = pdf_extractor.extract_songs(file_path, prompt_path, progress_callback=progress_callback)
        except UnsupportedFileTypeError as e:
            return JSONResponse(status_code=400, content={"ok": False, "error": str(e)})

        with open(working_dir / "titles.json", 'w', encoding='utf-8') as f:
            json.dump(extraction_result["data"], f, indent=2)

        if not extraction_result["success"]:
            return JSONResponse(status_code=500, content={"ok": False, "error": f"Extraction failed: {extraction_result['error']}"})
        
        # Step 2: Title Validation
        from title_validation_library import validate_titles_from_json
        backup_path = Path(latest_backup['file_path'])
        mappings_path = Path(f"user_data/{user['id']}/user_data.json")
        
        # Load the titles JSON
        with open(working_dir / "titles.json", 'r', encoding='utf-8') as f:
            titles_data = json.load(f)
        
        # Validate titles
        try:
            validation_result = validate_titles_from_json(titles_data, user['id'], backup_path, mappings_path)
        except Exception as e:
            return JSONResponse(content={"ok": False, "error": f"Title validation failed: {e}"})
        
        # Save validated titles
        with open(working_dir / "validated_titles.json", 'w', encoding='utf-8') as f:
            json.dump(validation_result, f, indent=2)
        
        # Step 3: Song Extraction
        from song_extraction_library import SongExtractor
        song_extractor = SongExtractor(user['id'], backup_path)
        extraction_result = song_extractor.extract_and_save(validation_result, working_dir / f"{name}.sbp", name)
        
        if not extraction_result["success"]:
            return JSONResponse(content={"ok": False, "error": f"Song extraction failed: {extraction_result['error']}"})
        
        # Move file to permanent downloads directory
        downloads_dir = Path("downloads")
        downloads_dir.mkdir(exist_ok=True)
        
        # Create unique filename to avoid conflicts
        timestamp = int(time.time())
        permanent_filename = f"{name}_{timestamp}.sbp"
        permanent_path = downloads_dir / permanent_filename
        
        # Move the file from working directory to permanent location
        shutil.move(str(working_dir / f"{name}.sbp"), str(permanent_path))
        
        # Save output file to database with permanent path
        output_file = db.save_file_upload(
            user_id=user['id'],
            file_type="download",
            original_filename=f"{name}.sbp",
            stored_filename=permanent_filename,
            file_path=str(permanent_path),
            file_size=permanent_path.stat().st_size,
            mime_type="application/octet-stream",
            metadata={"set_name": name}
        )
        
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
                "download_id": output_file['id'],
                "file_id": output_file['id'],
                "filename": f"{name}.sbp",
                "download_url": f"{BASE_URL}/download_file/{output_file['id']}",
                "file_size": permanent_path.stat().st_size,
                "created_at": output_file['created_at'],
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
                "download_id": output_file['id'],
                "file_id": output_file['id'],
                "filename": f"{name}.sbp",
                "download_url": f"{BASE_URL}/download_file/{output_file['id']}",
                "file_size": permanent_path.stat().st_size,
                "created_at": output_file['created_at']
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

@app.get("/download_file/{file_id}")
async def download_user_file(
    file_id: str, 
    request: Request, 
    secret: Optional[str] = Header(None, alias="X-Secret"),
    secret_query: Optional[str] = Query(None, alias="X-Secret"),
    session_query: Optional[str] = Query(None, alias="X-Session-ID")
):
    """Download a user's file by ID."""
    if secret != SECRET and secret_query != SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")

    # Support session via header or query param for direct link downloads
    # Also support standalone access for hardcoded user
    session_token = request.headers.get("X-Session-ID") or session_query
    standalone_user_id = request.headers.get("X-Standalone-User-ID") or request.query_params.get("X-Standalone-User-ID")
    
    if standalone_user_id == "35e76f8b-65f7-48c1-9920-932122e98219":
        # Standalone access for hardcoded user
        user = db.get_user_by_id(standalone_user_id)
        if not user:
            raise HTTPException(status_code=401, detail="Standalone user not found")
    else:
        # Regular session-based access
        if not session_token:
            raise HTTPException(status_code=401, detail="Not authenticated")
        session = db.get_active_session(session_token)
        if not session:
            raise HTTPException(status_code=401, detail="Not authenticated")
        user = db.get_user_by_id(session['user_id'])
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Get file from database
    files = db.get_user_files(user['id'])
    file_upload = next((f for f in files if f['id'] == file_id), None)
    
    if not file_upload:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Check if file exists on disk
    file_path = Path(file_upload['file_path'])
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    
    return FileResponse(
        path=str(file_path),
        filename=file_upload['original_filename'],
        media_type=file_upload['mime_type'] or "application/octet-stream"
    )

# Helper function for title validation with database
def validate_titles_with_database(titles_data: Dict[str, Any], user_id: str, backup_path: Path) -> Dict[str, Any]:
    """Validate titles using database mappings."""
    from sbp_library import SBPLibrary
    from title_validation_library import TitleValidator
    
    # Create a temporary mappings file from database
    mappings = db.get_user_title_mappings(user_id)
    if mappings:
        # Create a temporary mappings file
        temp_mappings_path = Path(f"temp_mappings_{user_id}.json")
        mappings_dict = {mapping['pdf_title']: mapping['catalog_title'] for mapping in mappings}
        
        with open(temp_mappings_path, 'w', encoding='utf-8') as f:
            json.dump({"title_mapper": mappings_dict}, f, indent=2)
        
        # Use the existing validation logic
        validator = TitleValidator(user_id, backup_path, temp_mappings_path)
        result = validator.validate_input(titles_data)
        
        # Clean up temp file
        temp_mappings_path.unlink(missing_ok=True)
        
        return result
    else:
        # No mappings, just validate against backup
        validator = TitleValidator(user_id, backup_path)
        return validator.validate_input(titles_data)

@app.post("/verify_titles")
async def verify_titles(
    request: Request,
    secret: Optional[str] = Header(None, alias="X-Secret")
):
    """Validate a list of titles against the user's catalog and mappings."""
    
    if secret != SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    user = get_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        # Get titles from request body
        body = await request.json()
        titles = body.get("titles", [])
        
        if not titles:
            raise HTTPException(status_code=400, detail="No titles provided")
        
        # Get user's backup file
        files = db.get_user_files(user['id'])
        backup_files = [f for f in files if f['file_type'] == 'backup']
        
        if not backup_files:
            raise HTTPException(status_code=404, detail="No backup file found")
        
        latest_backup = max(backup_files, key=lambda x: x['created_at'])
        backup_path = Path(latest_backup['file_path'])
        
        if not backup_path.exists():
            raise HTTPException(status_code=404, detail="Backup file not found")
        
        # Prepare titles data in the expected format
        titles_data = {
            "titles": titles,
            "total_count": len(titles)
        }
        
        # Validate titles using database mappings
        validation_result = validate_titles_with_database(titles_data, user['id'], backup_path)
        
        return {
            "success": True,
            "validated_count": validation_result.get("validated_count", 0),
            "unfound_titles": validation_result.get("unfound_titles", []),
            "total_count": len(titles)
        }
        
    except Exception as e:
        print(f"Error validating titles: {e}")
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")

def _validate_upload_bytes(content: bytes, filename: str) -> None:
    """Validate file type before processing; raises HTTPException 400 if unsupported."""
    from pdf_extraction_library import detect_file_type, UnsupportedFileTypeError

    suffix = Path(filename).suffix or '.pdf'
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    try:
        detect_file_type(tmp_path)
    except UnsupportedFileTypeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        tmp_path.unlink(missing_ok=True)


def _sanitize_upload_filename(filename: str, fallback: str = "input.pdf") -> str:
    """Sanitize an uploaded filename for safe storage."""
    name = Path(filename or fallback).name
    name = re.sub(r'[^\w.\- ]', '', name).strip()
    name = re.sub(r'\s+', '_', name)
    if not name or name.startswith('.'):
        return fallback
    return name


def _save_upload_file(working_dir: Path, content: bytes, filename: str) -> Path:
    """Save uploaded bytes with sanitized original filename."""
    safe_name = _sanitize_upload_filename(filename)
    file_path = working_dir / safe_name
    with open(file_path, 'wb') as f:
        f.write(content)
    return file_path


# Helper function for setlist file extraction (from original server)
async def _extract_pdf_bytes(request: Request, name: str) -> tuple[bytes, str]:
    """Extract setlist file bytes from request."""
    form = await request.form()
    pdf_file = form.get("file") or form.get("pdf")  # Support both field names

    if not pdf_file:
        raise HTTPException(400, "No setlist file provided")

    file_bytes = await pdf_file.read()
    filename = pdf_file.filename or f"{name}.pdf"

    if hasattr(pdf_file, 'seek'):
        try:
            pdf_file.seek(0)
        except Exception:
            pass

    return file_bytes, filename

@app.post("/user/reprocess-setlist")
async def reprocess_setlist(
    request: Request,
    secret: Optional[str] = Header(None, alias="X-Secret")
):
    """Reprocess the most recent setlist with updated mappings."""
    if secret != SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    user = get_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        # Get the most recent download file for this user (these are the processed setlists)
        files = db.get_user_files(user['id'])
        print(f"DEBUG: Found {len(files)} files for user {user['id']}")
        print(f"DEBUG: File types: {[f['file_type'] for f in files]}")
        
        download_files = [f for f in files if f['file_type'] == 'download']
        print(f"DEBUG: Found {len(download_files)} download files")
        
        if not download_files:
            raise HTTPException(status_code=404, detail="No processed setlist found to reprocess")
        
        # Get the most recent download
        latest_setlist = max(download_files, key=lambda x: x['created_at'])
        
        # For reprocessing, we need to re-run the entire pipeline
        # Since we don't have the original PDF, we'll need to ask the user to re-upload
        # or find another approach
        
        # For now, return an error asking for PDF re-upload
        raise HTTPException(status_code=400, detail="Reprocessing requires the original PDF file. Please re-upload your PDF to reprocess with updated mappings.")
        
        # Create a new working directory for reprocessing
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        working_dir = Path(f"work/{user['id']}_{timestamp}")
        working_dir.mkdir(parents=True, exist_ok=True)
        
        # Get user's backup file
        backup_files = [f for f in files if f['file_type'] == 'backup']
        if not backup_files:
            raise HTTPException(status_code=404, detail="No backup file found")
        
        latest_backup = max(backup_files, key=lambda x: x['created_at'])
        backup_path = Path(latest_backup['file_path'])
        
        # Reprocess using the streaming endpoint logic
        from sbp_library import SBPLibrary
        from title_validation_library import TitleValidator
        from song_extraction_library import SongExtractor
        
        # Step 1: Extract PDF again
        sbp = SBPLibrary()
        pdf_result = sbp.extract_pdf_to_titles(pdf_path, working_dir / "titles.json")
        
        if not pdf_result['success']:
            raise HTTPException(status_code=500, detail=f"PDF extraction failed: {pdf_result['error']}")
        
        # Step 2: Validate titles with updated mappings
        with open(working_dir / "titles.json", 'r', encoding='utf-8') as f:
            titles_data = json.load(f)
        
        # Get user's title mappings
        mappings = db.get_user_title_mappings(user['id'])
        mappings_dict = {mapping['pdf_title']: mapping['catalog_title'] for mapping in mappings}
        
        # Create temporary mappings file
        temp_mappings_path = working_dir / "temp_mappings.json"
        with open(temp_mappings_path, 'w', encoding='utf-8') as f:
            json.dump({"title_mapper": mappings_dict}, f, indent=2)
        
        # Validate titles
        validator = TitleValidator(user['id'], backup_path, temp_mappings_path)
        validation_result = validator.validate_input(titles_data)
        
        # Save validated titles
        with open(working_dir / "validated_titles.json", 'w', encoding='utf-8') as f:
            json.dump(validation_result, f, indent=2)
        
        # Step 3: Extract songs
        song_extractor = SongExtractor(user['id'], backup_path)
        extraction_result = song_extractor.extract_and_save(
            validation_result, 
            working_dir / f"{latest_setlist['stored_filename']}", 
            latest_setlist['stored_filename'].replace('.sbp', '')
        )
        
        if not extraction_result["success"]:
            raise HTTPException(status_code=500, detail=f"Song extraction failed: {extraction_result['error']}")
        
        # Save the reprocessed file to downloads
        file_upload = db.save_file_upload(
            user_id=user['id'],
            file_type="download",
            original_filename=latest_setlist['stored_filename'],
            stored_filename=working_dir / f"{latest_setlist['stored_filename']}",
            file_path=str(working_dir / f"{latest_setlist['stored_filename']}"),
            file_size=(working_dir / f"{latest_setlist['stored_filename']}").stat().st_size,
            mime_type="application/octet-stream",
            metadata={
                "original_filename": latest_setlist['stored_filename'],
                "reprocessed_at": datetime.now().isoformat(),
                "song_count": extraction_result.get('song_count', 0)
            }
        )
        
        # Clean up temp file
        temp_mappings_path.unlink(missing_ok=True)
        
        return {
            "ok": True,
            "message": "Setlist reprocessed successfully",
            "download_url": f"/download_file/{file_upload['id']}",
            "file_id": file_upload['id']
        }
        
    except Exception as e:
        print(f"Error reprocessing setlist: {e}")
        raise HTTPException(status_code=500, detail=f"Reprocessing failed: {str(e)}")

# Standalone processing endpoints
@app.post("/standalone/pdf-extraction")
async def standalone_pdf_extraction(
    pdf: UploadFile = File(...),
    secret: str = Form(...),
    name: str = Form("Standalone Extraction")
):
    """Standalone PDF extraction for testing."""
    if secret != SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    # Use hardcoded user for testing
    user_id = "35e76f8b-65f7-48c1-9920-932122e98219"
    
    try:
        # Create working directory
        working_dir = Path(f"work/{user_id}_{int(time.time())}")
        working_dir.mkdir(parents=True, exist_ok=True)
        
        # Create forensic directory for analysis
        forensic_dir = Path("forensic")
        forensic_dir.mkdir(exist_ok=True)
        
        content = await pdf.read()
        file_path = _save_upload_file(working_dir, content, pdf.filename or "input.pdf")

        timestamp = int(time.time())
        forensic_pdf_path = forensic_dir / f"pdf_upload_{timestamp}_{_sanitize_upload_filename(pdf.filename or 'upload')}"
        with open(forensic_pdf_path, 'wb') as f:
            f.write(content)

        print(f"[FORENSIC] Saved upload: {forensic_pdf_path}")

        from pdf_extraction_library import PDFExtractor, UnsupportedFileTypeError
        pdf_extractor = PDFExtractor()
        prompt_path = Path("prompts/openai_extraction.prompt")

        def progress_callback(message):
            print(f"[STANDALONE_PDF] {message}")

        try:
            extraction_result = pdf_extractor.extract_songs(file_path, prompt_path, progress_callback=progress_callback)
        except UnsupportedFileTypeError as e:
            raise HTTPException(status_code=400, detail=str(e))

        if not extraction_result["success"]:
            raise HTTPException(status_code=500, detail=f"Extraction failed: {extraction_result['error']}")
        
        # Save result
        result_path = working_dir / "extraction_result.json"
        with open(result_path, 'w', encoding='utf-8') as f:
            json.dump(extraction_result["data"], f, indent=2)
        
        # Save forensic copy of result
        forensic_result_path = forensic_dir / f"pdf_extraction_result_{timestamp}.json"
        with open(forensic_result_path, 'w', encoding='utf-8') as f:
            json.dump(extraction_result["data"], f, indent=2)
        
        print(f"[FORENSIC] Saved PDF extraction result: {forensic_result_path}")
        
        return {
            "success": True,
            "data": extraction_result["data"],
            "message": "PDF extraction completed successfully",
            "forensic_upload": str(forensic_pdf_path),
            "forensic_result": str(forensic_result_path)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in standalone extraction: {e}")
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")

@app.post("/standalone/title-validation")
async def standalone_title_validation(
    json_file: UploadFile = File(...),
    secret: str = Form(...)
):
    """Standalone title validation for testing."""
    if secret != SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    # Use hardcoded user for testing
    user_id = "35e76f8b-65f7-48c1-9920-932122e98219"
    
    try:
        # Get user's backup file
        files = db.get_user_files(user_id)
        backup_files = [f for f in files if f['file_type'] == 'backup']
        
        if not backup_files:
            raise HTTPException(status_code=404, detail="No backup file found for user")
        
        latest_backup = max(backup_files, key=lambda x: x['created_at'])
        backup_path = Path(latest_backup['file_path'])
        
        if not backup_path.exists():
            raise HTTPException(status_code=404, detail="Backup file not found")
        
        # Create forensic directory for analysis
        forensic_dir = Path("forensic")
        forensic_dir.mkdir(exist_ok=True)
        
        # Load JSON data
        json_content = await json_file.read()
        titles_data = json.loads(json_content.decode('utf-8'))
        
        # Save forensic copy of input
        timestamp = int(time.time())
        forensic_input_path = forensic_dir / f"title_validation_input_{timestamp}.json"
        with open(forensic_input_path, 'wb') as f:
            f.write(json_content)
        
        print(f"[FORENSIC] Saved title validation input: {forensic_input_path}")
        
        # Get user's mappings
        mappings_list = db.get_user_title_mappings(user_id)
        
        # Convert list to dictionary format expected by TitleValidator
        mappings_dict = {}
        for mapping in mappings_list:
            mappings_dict[mapping['pdf_title']] = mapping['catalog_title']
        
        # Create working directory
        working_dir = Path(f"work/{user_id}_{int(time.time())}")
        working_dir.mkdir(parents=True, exist_ok=True)
        
        # Create temporary mappings file
        temp_mappings_path = working_dir / "temp_mappings.json"
        with open(temp_mappings_path, 'w', encoding='utf-8') as f:
            json.dump({"title_mapper": mappings_dict}, f, indent=2)
        
        # Validate titles
        from title_validation_library import TitleValidator
        validator = TitleValidator(user_id, backup_path, temp_mappings_path)
        validation_result = validator.validate_input(titles_data)
        
        # Save validated result
        result_path = working_dir / "validation_result.json"
        with open(result_path, 'w', encoding='utf-8') as f:
            json.dump(validation_result, f, indent=2)
        
        # Save forensic copy of result
        forensic_result_path = forensic_dir / f"title_validation_result_{timestamp}.json"
        with open(forensic_result_path, 'w', encoding='utf-8') as f:
            json.dump(validation_result, f, indent=2)
        
        print(f"[FORENSIC] Saved title validation result: {forensic_result_path}")
        
        return {
            "success": True,
            "data": validation_result,
            "message": "Title validation completed successfully",
            "forensic_input": str(forensic_input_path),
            "forensic_result": str(forensic_result_path)
        }
        
    except Exception as e:
        print(f"Error in standalone title validation: {e}")
        raise HTTPException(status_code=500, detail=f"Title validation failed: {str(e)}")

@app.get("/standalone/user-catalog")
async def standalone_user_catalog(
    secret: str = Header(None, alias="X-Secret")
):
    """Get user catalog for standalone components."""
    if secret != SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    # Use hardcoded user for testing
    user_id = "35e76f8b-65f7-48c1-9920-932122e98219"
    
    try:
        # Get user's backup file
        files = db.get_user_files(user_id)
        backup_files = [f for f in files if f['file_type'] == 'backup']
        
        if not backup_files:
            raise HTTPException(status_code=404, detail="No backup file found for user")
        
        latest_backup = max(backup_files, key=lambda x: x['created_at'])
        backup_path = Path(latest_backup['file_path'])
        
        if not backup_path.exists():
            raise HTTPException(status_code=404, detail="Backup file not found")
        
        # Load backup and extract song names
        from sbp_library import SBPLibrary
        sbp_lib = SBPLibrary()
        backup_sbp = sbp_lib.load_sbp_file(backup_path)
        
        # Extract song names
        songs = [{"name": song.name, "id": song.id} for song in backup_sbp.songs]
        
        return {
            "success": True,
            "songs": songs,
            "total": len(songs)
        }
        
    except Exception as e:
        print(f"Error in standalone user catalog: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load catalog: {str(e)}")

@app.post("/standalone/save-mapping")
async def standalone_save_mapping(
    request: Request,
    secret: str = Header(None, alias="X-Secret")
):
    """Save a title mapping for standalone components."""
    if secret != SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    # Use hardcoded user for testing
    user_id = "35e76f8b-65f7-48c1-9920-932122e98219"
    
    try:
        # Get mapping data from request body
        body = await request.json()
        pdf_title = body.get("pdf_title")
        catalog_title = body.get("catalog_title")
        
        if not pdf_title or not catalog_title:
            raise HTTPException(status_code=400, detail="Missing pdf_title or catalog_title")
        
        # Save mapping to database
        # Note: The catalog_title should match exactly what's in the backup
        # For "Hurt So Good", the actual song in backup is "Hurts So Good"
        if catalog_title == "Hurt So Good":
            catalog_title = "Hurts So Good"
        
        db.save_title_mapping(user_id, pdf_title, catalog_title)
        
        return {
            "success": True,
            "message": f"Mapping saved: '{pdf_title}' -> '{catalog_title}'"
        }
        
    except Exception as e:
        print(f"Error in standalone save mapping: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save mapping: {str(e)}")

@app.post("/standalone/song-extraction")
async def standalone_song_extraction(
    json_file: UploadFile = File(...),
    secret: str = Form(...),
    set_name: str = Form("Extracted Set")
):
    """Standalone song extraction for testing."""
    if secret != SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    # Use hardcoded user for testing
    user_id = "35e76f8b-65f7-48c1-9920-932122e98219"
    
    try:
        # Get user's backup file
        files = db.get_user_files(user_id)
        backup_files = [f for f in files if f['file_type'] == 'backup']
        
        if not backup_files:
            raise HTTPException(status_code=404, detail="No backup file found for user")
        
        latest_backup = max(backup_files, key=lambda x: x['created_at'])
        backup_path = Path(latest_backup['file_path'])
        
        if not backup_path.exists():
            raise HTTPException(status_code=404, detail="Backup file not found")
        
        # Create forensic directory for analysis
        forensic_dir = Path("forensic")
        forensic_dir.mkdir(exist_ok=True)
        
        # Load JSON data
        json_content = await json_file.read()
        validated_data = json.loads(json_content.decode('utf-8'))
        
        # Save forensic copy of input
        timestamp = int(time.time())
        forensic_input_path = forensic_dir / f"song_extraction_input_{timestamp}.json"
        with open(forensic_input_path, 'wb') as f:
            f.write(json_content)
        
        print(f"[FORENSIC] Saved song extraction input: {forensic_input_path}")
        
        # Create working directory
        working_dir = Path(f"work/{user_id}_{int(time.time())}")
        working_dir.mkdir(parents=True, exist_ok=True)
        
        # Extract songs
        from song_extraction_library import SongExtractor
        song_extractor = SongExtractor(user_id, backup_path)
        
        output_filename = f"{set_name.replace(' ', '_')}.sbp"
        output_path = working_dir / output_filename
        
        extraction_result = song_extractor.extract_and_save(
            validated_data, 
            output_path, 
            set_name
        )
        
        # Save file to database
        file_record = db.save_file_upload(
            user_id=user_id,
            file_type='download',
            original_filename=output_filename,
            stored_filename=output_filename,
            file_path=str(output_path),
            file_size=output_path.stat().st_size
        )
        file_id = file_record['id']
        
        # Save forensic copy of output SBP file
        forensic_output_path = forensic_dir / f"song_extraction_output_{timestamp}.sbp"
        with open(forensic_output_path, 'wb') as f:
            with open(output_path, 'rb') as src:
                f.write(src.read())
        
        print(f"[FORENSIC] Saved song extraction output: {forensic_output_path}")
        
        return {
            "success": True,
            "data": {
                **extraction_result,
                "download_id": file_id,
                "download_url": f"/download_file/{file_id}?X-Standalone-User-ID=35e76f8b-65f7-48c1-9920-932122e98219"
            },
            "message": "Song extraction completed successfully",
            "forensic_input": str(forensic_input_path),
            "forensic_output": str(forensic_output_path)
        }
        
    except Exception as e:
        print(f"Error in standalone song extraction: {e}")
        raise HTTPException(status_code=500, detail=f"Song extraction failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
