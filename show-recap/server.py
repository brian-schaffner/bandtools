#!/usr/bin/env python3
"""
Show Recap Service - Analyze multitrack recordings and split into sets.

Workflow:
1. Upload multitrack audio files from A&H Qu-16 or similar mixer
2. Analyze for silence/dead air to detect set boundaries
3. Split into individual sets
4. Export as stereo MP3s
5. Upload to Dropbox and notify band members
"""

import os
import json
import time
import shutil
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, UploadFile, HTTPException, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from audio_analyzer import AudioAnalyzer
from audio_processor import AudioProcessor

# Configuration
DATA_DIR = Path(os.getenv("SHOW_RECAP_DATA_DIR", "/data/show-recap"))
UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = DATA_DIR / "output"

# Ensure directories exist
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# In-memory job tracking (would use DB in production)
jobs: Dict[str, Dict[str, Any]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    print("Show Recap service starting...")
    yield
    print("Show Recap service shutting down...")


app = FastAPI(
    title="Show Recap Service",
    description="Analyze multitrack recordings and split into sets",
    version="0.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SetBoundary(BaseModel):
    """Detected set boundary."""
    set_number: int
    start_time: float  # seconds
    end_time: float    # seconds
    duration: float    # seconds


class AnalysisResult(BaseModel):
    """Result of audio analysis."""
    job_id: str
    status: str
    total_duration: float
    sets: List[SetBoundary]
    silence_threshold_db: float
    min_silence_duration: float


class JobStatus(BaseModel):
    """Status of a processing job."""
    job_id: str
    status: str  # pending, analyzing, processing, complete, error
    message: str
    progress: float  # 0-100
    created_at: str
    updated_at: str
    analysis: Optional[AnalysisResult] = None
    output_files: List[str] = []


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "show-recap",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.post("/upload/init")
async def init_upload(
    show_name: str = Form(...),
    show_date: str = Form(None),
    file_count: int = Form(...),
    total_size: int = Form(...),
    silence_threshold_db: float = Form(-40.0),
    min_silence_duration: float = Form(10.0),
    min_set_duration: float = Form(300.0),
):
    """
    Initialize a chunked upload session.
    
    Returns a job_id to use for subsequent chunk uploads.
    """
    job_id = f"{int(time.time())}_{show_name.replace(' ', '_').replace('/', '_')}"
    job_dir = UPLOAD_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    
    jobs[job_id] = {
        "job_id": job_id,
        "status": "uploading",
        "message": f"Waiting for {file_count} files ({total_size / (1024*1024*1024):.2f} GB)",
        "progress": 0,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "show_name": show_name,
        "show_date": show_date or datetime.now().strftime("%Y-%m-%d"),
        "files": [],
        "expected_files": file_count,
        "total_size_bytes": total_size,
        "uploaded_size_bytes": 0,
        "settings": {
            "silence_threshold_db": silence_threshold_db,
            "min_silence_duration": min_silence_duration,
            "min_set_duration": min_set_duration,
        },
        "analysis": None,
        "output_files": [],
    }
    
    # Save job metadata
    with open(job_dir / "job.json", "w") as f:
        json.dump(jobs[job_id], f, indent=2)
    
    return {"job_id": job_id, "status": "ready"}


@app.post("/upload/chunk/{job_id}")
async def upload_chunk(
    job_id: str,
    file: UploadFile = File(...),
    filename: str = Form(...),
    chunk_index: int = Form(...),
    total_chunks: int = Form(...),
    file_index: int = Form(0),
):
    """
    Upload a chunk of a file.
    
    For large files, split into chunks and upload sequentially.
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    job_dir = UPLOAD_DIR / job_id
    
    # Create temp file for chunks
    temp_file = job_dir / f"{filename}.part{chunk_index}"
    chunk_data = await file.read()
    
    with open(temp_file, "wb") as f:
        f.write(chunk_data)
    
    job["uploaded_size_bytes"] = job.get("uploaded_size_bytes", 0) + len(chunk_data)
    
    # If this is the last chunk, combine all chunks
    if chunk_index == total_chunks - 1:
        final_path = job_dir / filename
        with open(final_path, "wb") as outfile:
            for i in range(total_chunks):
                chunk_path = job_dir / f"{filename}.part{i}"
                if chunk_path.exists():
                    with open(chunk_path, "rb") as infile:
                        outfile.write(infile.read())
                    chunk_path.unlink()  # Delete chunk
        
        job["files"].append(str(final_path))
        print(f"[UPLOAD] Completed file: {filename}")
    
    # Update progress
    if job.get("total_size_bytes", 0) > 0:
        job["progress"] = (job["uploaded_size_bytes"] / job["total_size_bytes"]) * 50  # 0-50% for upload
    
    job["updated_at"] = datetime.utcnow().isoformat()
    
    return {
        "status": "ok",
        "chunk": chunk_index,
        "total_chunks": total_chunks,
        "progress": job["progress"]
    }


@app.post("/upload/complete/{job_id}")
async def complete_upload(
    job_id: str,
    background_tasks: BackgroundTasks,
    auto_process: bool = Form(True),
):
    """
    Mark upload as complete and optionally start processing.
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    job["status"] = "pending"
    job["message"] = f"Upload complete: {len(job['files'])} files"
    job["progress"] = 50
    
    # Save job metadata
    with open(UPLOAD_DIR / job_id / "job.json", "w") as f:
        json.dump(job, f, indent=2)
    
    if auto_process:
        background_tasks.add_task(process_job, job_id)
    
    return {"status": "complete", "job_id": job_id}


@app.post("/upload")
async def upload_audio(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    show_name: str = Form(...),
    show_date: str = Form(None),
    auto_process: bool = Form(True),
    silence_threshold_db: float = Form(-40.0),
    min_silence_duration: float = Form(10.0),
    min_set_duration: float = Form(300.0),  # 5 minutes minimum set
):
    """
    Upload multitrack audio files for processing.
    
    Supports large files (multi-GB) via streaming upload.
    
    Args:
        files: Audio files (WAV format expected)
        show_name: Name of the show/gig
        show_date: Date of the show (YYYY-MM-DD)
        auto_process: Automatically start processing after upload
        silence_threshold_db: Silence threshold in dB (default -40)
        min_silence_duration: Minimum silence duration in seconds to detect break
        min_set_duration: Minimum set duration in seconds
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")
    
    # Create job
    job_id = f"{int(time.time())}_{show_name.replace(' ', '_').replace('/', '_')}"
    job_dir = UPLOAD_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    
    # Save uploaded files using streaming to handle large files
    saved_files = []
    total_size = 0
    CHUNK_SIZE = 1024 * 1024 * 10  # 10MB chunks
    
    for f in files:
        file_path = job_dir / f.filename
        file_size = 0
        
        print(f"[UPLOAD] Starting: {f.filename}")
        
        with open(file_path, "wb") as out:
            while True:
                chunk = await f.read(CHUNK_SIZE)
                if not chunk:
                    break
                out.write(chunk)
                file_size += len(chunk)
                
        saved_files.append(str(file_path))
        total_size += file_size
        print(f"[UPLOAD] Saved: {file_path} ({file_size / (1024*1024):.1f} MB)")
    
    # Create job record
    jobs[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "message": f"Uploaded {len(saved_files)} files ({total_size / (1024*1024*1024):.2f} GB)",
        "progress": 0,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "show_name": show_name,
        "show_date": show_date or datetime.now().strftime("%Y-%m-%d"),
        "files": saved_files,
        "total_size_bytes": total_size,
        "settings": {
            "silence_threshold_db": silence_threshold_db,
            "min_silence_duration": min_silence_duration,
            "min_set_duration": min_set_duration,
        },
        "analysis": None,
        "output_files": [],
    }
    
    # Save job metadata
    with open(job_dir / "job.json", "w") as f:
        json.dump(jobs[job_id], f, indent=2)
    
    if auto_process:
        background_tasks.add_task(process_job, job_id)
    
    return {
        "job_id": job_id,
        "status": "pending",
        "message": f"Uploaded {len(saved_files)} files",
        "files": [Path(f).name for f in saved_files],
    }


@app.get("/jobs/{job_id}")
async def get_job_status(job_id: str) -> JobStatus:
    """Get the status of a processing job."""
    if job_id not in jobs:
        # Try to load from disk
        job_file = UPLOAD_DIR / job_id / "job.json"
        if job_file.exists():
            with open(job_file) as f:
                jobs[job_id] = json.load(f)
        else:
            raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    return JobStatus(
        job_id=job["job_id"],
        status=job["status"],
        message=job["message"],
        progress=job["progress"],
        created_at=job["created_at"],
        updated_at=job["updated_at"],
        analysis=job.get("analysis"),
        output_files=job.get("output_files", []),
    )


@app.get("/jobs")
async def list_jobs():
    """List all jobs."""
    # Scan upload directory for jobs
    all_jobs = []
    for job_dir in UPLOAD_DIR.iterdir():
        if job_dir.is_dir():
            job_file = job_dir / "job.json"
            if job_file.exists():
                with open(job_file) as f:
                    job = json.load(f)
                    all_jobs.append({
                        "job_id": job["job_id"],
                        "status": job["status"],
                        "show_name": job.get("show_name", "Unknown"),
                        "show_date": job.get("show_date"),
                        "created_at": job["created_at"],
                    })
    
    return sorted(all_jobs, key=lambda x: x["created_at"], reverse=True)


@app.post("/jobs/{job_id}/analyze")
async def analyze_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    silence_threshold_db: float = -40.0,
    min_silence_duration: float = 10.0,
):
    """Re-analyze a job with different parameters."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    job["settings"]["silence_threshold_db"] = silence_threshold_db
    job["settings"]["min_silence_duration"] = min_silence_duration
    job["status"] = "pending"
    job["message"] = "Re-analyzing with new parameters"
    
    background_tasks.add_task(process_job, job_id)
    
    return {"status": "analyzing", "job_id": job_id}


@app.post("/jobs/{job_id}/process")
async def process_job_endpoint(
    job_id: str,
    background_tasks: BackgroundTasks,
    set_boundaries: List[Dict] = None,
):
    """
    Process a job to split into sets and export MP3s.
    
    Optionally provide manual set boundaries to override auto-detection.
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    
    if set_boundaries:
        job["analysis"] = {
            "sets": set_boundaries,
            "manual": True,
        }
    
    background_tasks.add_task(export_sets, job_id)
    
    return {"status": "processing", "job_id": job_id}


@app.get("/jobs/{job_id}/download/{filename}")
async def download_file(job_id: str, filename: str):
    """Download a processed file."""
    file_path = OUTPUT_DIR / job_id / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        file_path,
        media_type="audio/mpeg",
        filename=filename
    )


def update_job(job_id: str, **kwargs):
    """Update job status and save to disk."""
    if job_id in jobs:
        jobs[job_id].update(kwargs)
        jobs[job_id]["updated_at"] = datetime.utcnow().isoformat()
        
        # Save to disk
        job_file = UPLOAD_DIR / job_id / "job.json"
        with open(job_file, "w") as f:
            json.dump(jobs[job_id], f, indent=2)


async def process_job(job_id: str):
    """Background task to process a job."""
    try:
        job = jobs[job_id]
        update_job(job_id, status="analyzing", message="Analyzing audio...", progress=10)
        
        # Initialize analyzer
        analyzer = AudioAnalyzer(
            silence_threshold_db=job["settings"]["silence_threshold_db"],
            min_silence_duration=job["settings"]["min_silence_duration"],
            min_set_duration=job["settings"]["min_set_duration"],
        )
        
        # Analyze first file (assuming main mix or we'll need to handle multiple)
        # For Qu-16, typically there's a stereo main mix or we need to sum channels
        audio_file = job["files"][0]  # Start with first file
        
        update_job(job_id, message=f"Analyzing {Path(audio_file).name}...", progress=20)
        
        # Run analysis
        analysis = analyzer.analyze(audio_file)
        
        update_job(
            job_id,
            status="analyzed",
            message=f"Found {len(analysis['sets'])} sets",
            progress=50,
            analysis=analysis
        )
        
        # Automatically export sets
        await export_sets(job_id)
        
    except Exception as e:
        print(f"[ERROR] Job {job_id} failed: {e}")
        import traceback
        traceback.print_exc()
        update_job(job_id, status="error", message=str(e))


async def export_sets(job_id: str):
    """Export detected sets as MP3 files."""
    try:
        job = jobs[job_id]
        analysis = job.get("analysis")
        
        if not analysis or not analysis.get("sets"):
            update_job(job_id, status="error", message="No sets detected")
            return
        
        update_job(job_id, status="processing", message="Exporting sets...", progress=60)
        
        # Create output directory
        output_dir = OUTPUT_DIR / job_id
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize processor
        processor = AudioProcessor()
        
        # Get source file
        source_file = job["files"][0]
        show_name = job["show_name"]
        show_date = job["show_date"]
        
        output_files = []
        total_sets = len(analysis["sets"])
        
        for i, set_info in enumerate(analysis["sets"]):
            set_num = set_info.get("set_number", i + 1)
            start_time = set_info["start_time"]
            end_time = set_info["end_time"]
            
            # Generate output filename
            output_name = f"{show_date}_{show_name.replace(' ', '_')}_Set{set_num}.mp3"
            output_path = output_dir / output_name
            
            update_job(
                job_id,
                message=f"Exporting Set {set_num} of {total_sets}...",
                progress=60 + (30 * (i + 1) / total_sets)
            )
            
            # Export the set
            processor.export_segment(
                source_file,
                str(output_path),
                start_time,
                end_time,
                metadata={
                    "title": f"{show_name} - Set {set_num}",
                    "artist": show_name,
                    "album": f"{show_name} - {show_date}",
                    "track": str(set_num),
                }
            )
            
            output_files.append(output_name)
            print(f"[EXPORT] Created: {output_path}")
        
        update_job(
            job_id,
            status="complete",
            message=f"Exported {len(output_files)} sets",
            progress=100,
            output_files=output_files
        )
        
    except Exception as e:
        print(f"[ERROR] Export failed for job {job_id}: {e}")
        import traceback
        traceback.print_exc()
        update_job(job_id, status="error", message=f"Export failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
