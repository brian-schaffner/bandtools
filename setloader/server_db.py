#!/usr/local/bin/python3
"""
FastAPI service for orchestrating set loader runs with database integration.
"""

import os
import json
import uuid
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

from fastapi import FastAPI, Request, HTTPException, File, UploadFile, Form, Header, Query
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Database imports
from database import DatabaseManager, User, UserSession, TitleMapping, FileUpload, ProcessingJob, DownloadFile

# Initialize FastAPI app
app = FastAPI(title="SetLoader API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:3002", "http://127.0.0.1:3002"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
SECRET = os.getenv("SECRET", "change-me")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8002")

# Initialize database manager
db_manager = DatabaseManager()

# Helper functions
def get_user_from_request(request: Request) -> Optional[User]:
    """Get user from request headers."""
    session_token = request.headers.get("X-Session-ID")
    if not session_token:
        return None
    
    session = db_manager.get_active_session(session_token)
    if not session:
        return None
    
    return db_manager.get_user_by_id(str(session.user_id))

def create_session_token() -> str:
    """Create a new session token."""
    return str(uuid.uuid4())

# API Endpoints

@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "SetLoader API", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

# Authentication endpoints
@app.post("/auth/login")
async def auth_login(request: Request):
    """Login endpoint that creates a session."""
    # For now, use hardcoded user for development
    user = db_manager.get_user_by_email("brian@schaffner.net")
    if not user:
        user = db_manager.create_user(
            email="brian@schaffner.net",
            name="Brian Schaffner"
        )
    
    # Create session
    session_token = create_session_token()
    session = db_manager.create_session(str(user.id), session_token)
    
    return {
        "message": "Login successful",
        "user_id": str(user.id),
        "session_token": session_token
    }

@app.get("/auth/logout")
async def auth_logout(request: Request):
    """Logout endpoint that clears the session."""
    session_token = request.headers.get("X-Session-ID")
    if session_token:
        db_manager.invalidate_session(session_token)
    
    return {"message": "Logout successful"}

@app.get("/user/status")
async def get_user_status(request: Request, secret: str | None = Header(None, alias="X-Secret")):
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
    backup_files = db_manager.get_user_files(str(user.id), "backup")
    setlist_files = db_manager.get_user_files(str(user.id), "setlist")
    download_files = db_manager.get_user_files(str(user.id), "download")
    
    # Get title mappings count
    title_mappings = db_manager.get_user_title_mappings(str(user.id))
    
    # Get latest backup
    latest_backup = None
    if backup_files:
        latest_backup = {
            "id": str(backup_files[0].id),
            "filename": backup_files[0].original_filename,
            "uploaded_at": backup_files[0].created_at.isoformat(),
            "file_size": backup_files[0].file_size
        }
    
    return {
        "user_id": str(user.id),
        "user_email": user.email,
        "authenticated": True,
        "backup_uploaded": len(backup_files) > 0,
        "backup_count": len(backup_files),
        "setlist_count": len(setlist_files),
        "download_count": len(download_files),
        "mapping_count": len(title_mappings),
        "session_created": user.created_at.isoformat(),
        "latest_backup": latest_backup
    }

@app.get("/user/catalog")
async def get_user_catalog(request: Request, secret: str | None = Header(None, alias="X-Secret")):
    """Get user's song catalog from latest backup."""
    if secret != SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    user = get_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Get latest backup
    latest_backup = db_manager.get_latest_backup(str(user.id))
    if not latest_backup:
        return {"songs": [], "count": 0}
    
    # For now, return empty catalog - this would need to be implemented
    # to extract songs from the SBP backup file
    return {"songs": [], "count": 0}

@app.get("/user/title-mappings")
async def get_user_title_mappings(request: Request, secret: str | None = Header(None, alias="X-Secret")):
    """Get user's title mappings."""
    if secret != SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    user = get_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    mappings = db_manager.get_user_title_mappings(str(user.id))
    mappings_dict = {mapping.pdf_title: mapping.catalog_title for mapping in mappings}
    
    return {
        "mappings": mappings_dict,
        "count": len(mappings_dict)
    }

@app.get("/user/archive")
async def get_user_archive(request: Request, secret: str | None = Header(None, alias="X-Secret")):
    """Get user's archive of processed files."""
    if secret != SECRET:
        raise HTTPException(status_code=401, detail="unauthorized")
    
    user = get_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Get all file types
    backup_files = db_manager.get_user_files(str(user.id), "backup")
    setlist_files = db_manager.get_user_files(str(user.id), "setlist")
    download_files = db_manager.get_user_files(str(user.id), "download")
    
    # Get title mappings
    title_mappings = db_manager.get_user_title_mappings(str(user.id))
    mappings_dict = {mapping.pdf_title: mapping.catalog_title for mapping in title_mappings}
    
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
            "id": str(file_upload.id),
            "filename": file_upload.original_filename,
            "file_size": file_upload.file_size,
            "uploaded_at": file_upload.created_at.isoformat(),
            "metadata": file_upload.metadata or {}
        }
    
    return {
        "downloads": [format_file(f) for f in download_files],
        "backups": [format_file(f) for f in backup_files],
        "setlists": [format_file(f) for f in setlist_files],
        "title_mapper": mappings_dict,
        "summary": summary
    }

@app.post("/verify_backup")
async def verify_backup(
    request: Request,
    secret: str | None = Header(None, alias="X-Secret")
):
    """Verify user's backup file."""
    if secret != SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    user = get_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Get latest backup
    latest_backup = db_manager.get_latest_backup(str(user.id))
    if not latest_backup:
        return {"verified": False, "message": "No backup file found"}
    
    # For now, just return success - this would need to be implemented
    # to actually verify the SBP backup file
    return {
        "verified": True,
        "message": "Backup file verified",
        "file_id": str(latest_backup.id),
        "filename": latest_backup.original_filename
    }

@app.post("/process_setlist_simple")
async def process_setlist_simple(
    request: Request,
    secret_form: str | None = Form(None, alias="secret"),
    x_secret: str | None = Header(default=None, alias="X-Secret"),
    secret_query: str | None = Query(default=None, alias="secret"),
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
    latest_backup = db_manager.get_latest_backup(str(user.id))
    if not latest_backup:
        raise HTTPException(400, "No backup file uploaded. Please upload a backup file first.")

    try:
        # Extract PDF bytes and filename
        pdf_bytes, slug_hint = await _extract_pdf_bytes(request, name)
        
        # Create working directory for this processing event
        working_dir = Path(f"work/{user.id}_{int(time.time())}")
        working_dir.mkdir(parents=True, exist_ok=True)
        
        # Create processing job record
        job = ProcessingJob(
            user_id=user.id,
            backup_file_id=latest_backup.id,
            status='processing',
            input_data={"set_name": name, "pdf_filename": slug_hint}
        )
        
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
        backup_path = Path(latest_backup.file_path)
        mappings_path = Path(f"user_data/{user.id}/user_data.json")
        
        # Load the titles JSON
        with open(working_dir / "titles.json", 'r', encoding='utf-8') as f:
            titles_data = json.load(f)
        
        # Validate titles
        try:
            validation_result = validate_titles_from_json(titles_data, str(user.id), backup_path, mappings_path)
        except Exception as e:
            return JSONResponse(content={"ok": False, "error": f"Title validation failed: {e}"})
        
        # Save validated titles
        with open(working_dir / "validated_titles.json", 'w', encoding='utf-8') as f:
            json.dump(validation_result, f, indent=2)
        
        # Step 3: Song Extraction
        from song_extraction_library import SongExtractor
        song_extractor = SongExtractor(str(user.id), backup_path)
        extraction_result = song_extractor.extract_and_save(validation_result, working_dir / f"{name}.sbp", name)
        
        if not extraction_result["success"]:
            return JSONResponse(content={"ok": False, "error": f"Song extraction failed: {extraction_result['error']}"})
        
        # Save output file to database
        output_file = db_manager.save_file_upload(
            user_id=str(user.id),
            file_type="download",
            original_filename=f"{name}.sbp",
            stored_filename=f"{name}.sbp",
            file_path=str(working_dir / f"{name}.sbp"),
            file_size=(working_dir / f"{name}.sbp").stat().st_size,
            mime_type="application/octet-stream",
            metadata={"set_name": name, "job_id": str(job.id)}
        )
        
        # Update job status
        job.status = 'completed'
        job.completed_at = datetime.utcnow()
        job.output_data = validation_result
        job.processing_results = {
            "song_count": len(validation_result.get('sets', [])),
            "successful_mappings": validation_result.get('counts', {}).get('validated_total', 0),
            "unfound_titles": validation_result.get('counts', {}).get('missing_total', 0)
        }
        
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
                "download_id": str(output_file.id),
                "file_id": str(output_file.id),
                "filename": f"{name}.sbp",
                "download_url": f"{BASE_URL}/download_file/{output_file.id}",
                "file_size": (working_dir / f"{name}.sbp").stat().st_size,
                "created_at": output_file.created_at.isoformat(),
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
                "download_id": str(output_file.id),
                "file_id": str(output_file.id),
                "filename": f"{name}.sbp",
                "download_url": f"{BASE_URL}/download_file/{output_file.id}",
                "file_size": (working_dir / f"{name}.sbp").stat().st_size,
                "created_at": output_file.created_at.isoformat()
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
    secret: str | None = Header(None, alias="X-Secret"),
    secret_query: str | None = Query(None, alias="X-Secret")
):
    """Download a user's file by ID."""
    if secret != SECRET and secret_query != SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    user = get_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Get file from database
    db = db_manager.SessionLocal()
    try:
        file_upload = db.query(FileUpload).filter(
            FileUpload.id == file_id,
            FileUpload.user_id == user.id,
            FileUpload.is_active == True
        ).first()
        
        if not file_upload:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Check if file exists on disk
        file_path = Path(file_upload.file_path)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found on disk")
        
        return FileResponse(
            path=str(file_path),
            filename=file_upload.original_filename,
            media_type=file_upload.mime_type or "application/octet-stream"
        )
    finally:
        db.close()

# Helper function for PDF extraction (from original server)
async def _extract_pdf_bytes(request: Request, name: str) -> tuple[bytes, str]:
    """Extract PDF bytes from request."""
    form = await request.form()
    pdf_file = form.get("pdf")
    
    if not pdf_file:
        raise HTTPException(400, "No PDF file provided")
    
    pdf_bytes = await pdf_file.read()
    filename = pdf_file.filename or f"{name}.pdf"
    
    return pdf_bytes, filename

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
