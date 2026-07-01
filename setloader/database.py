#!/usr/local/bin/python3
"""
Database connection and ORM models for SetLoader.
"""

import os
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import uuid
import json

from sqlalchemy import create_engine, Column, String, Integer, Boolean, DateTime, Text, BigInteger, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.exc import SQLAlchemyError

# Database configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://setloader:setloader_password@localhost:5432/setloader"
)

# Create engine and session
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    google_id = Column(String(255), unique=True)
    name = Column(String(255))
    picture_url = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)
    
    # Relationships
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    title_mappings = relationship("TitleMapping", back_populates="user", cascade="all, delete-orphan")
    file_uploads = relationship("FileUpload", back_populates="user", cascade="all, delete-orphan")
    processing_jobs = relationship("ProcessingJob", back_populates="user", cascade="all, delete-orphan")

class UserSession(Base):
    __tablename__ = "user_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    session_token = Column(String(255), unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    user = relationship("User", back_populates="sessions")

class TitleMapping(Base):
    __tablename__ = "title_mappings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    pdf_title = Column(String(500), nullable=False)
    catalog_title = Column(String(500), nullable=False)
    catalog_song_id = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="title_mappings")

class FileUpload(Base):
    __tablename__ = "file_uploads"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    file_type = Column(String(50), nullable=False)  # 'backup', 'setlist', 'download'
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False)
    file_path = Column(Text, nullable=False)
    file_size = Column(BigInteger, nullable=False)
    mime_type = Column(String(100))
    metadata = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True)
    
    # Relationships
    user = relationship("User", back_populates="file_uploads")

class ProcessingJob(Base):
    __tablename__ = "processing_jobs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    setlist_file_id = Column(UUID(as_uuid=True), ForeignKey("file_uploads.id"))
    backup_file_id = Column(UUID(as_uuid=True), ForeignKey("file_uploads.id"))
    status = Column(String(50), nullable=False, default='pending')  # 'pending', 'processing', 'completed', 'failed'
    input_data = Column(JSON)
    output_data = Column(JSON)
    processing_results = Column(JSON)
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    
    # Relationships
    user = relationship("User", back_populates="processing_jobs")

class DownloadFile(Base):
    __tablename__ = "download_files"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    job_id = Column(UUID(as_uuid=True), ForeignKey("processing_jobs.id"), nullable=False)
    file_id = Column(UUID(as_uuid=True), ForeignKey("file_uploads.id"), nullable=False)
    set_name = Column(String(255))
    song_count = Column(Integer)
    processing_stats = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# Database utility functions
def get_db() -> Session:
    """Get database session."""
    db = SessionLocal()
    try:
        return db
    finally:
        pass

def close_db(db: Session):
    """Close database session."""
    db.close()

class DatabaseManager:
    """Database operations manager."""
    
    def __init__(self):
        self.engine = engine
        self.SessionLocal = SessionLocal
    
    def create_tables(self):
        """Create all tables."""
        Base.metadata.create_all(bind=self.engine)
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        db = self.SessionLocal()
        try:
            return db.query(User).filter(User.email == email, User.is_active == True).first()
        finally:
            db.close()
    
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        db = self.SessionLocal()
        try:
            return db.query(User).filter(User.id == user_id, User.is_active == True).first()
        finally:
            db.close()
    
    def create_user(self, email: str, google_id: str = None, name: str = None, picture_url: str = None) -> User:
        """Create a new user."""
        db = self.SessionLocal()
        try:
            user = User(
                email=email,
                google_id=google_id,
                name=name,
                picture_url=picture_url
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            return user
        finally:
            db.close()
    
    def create_session(self, user_id: str, session_token: str, expires_in_hours: int = 24) -> UserSession:
        """Create a user session."""
        db = self.SessionLocal()
        try:
            expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours)
            session = UserSession(
                user_id=user_id,
                session_token=session_token,
                expires_at=expires_at
            )
            db.add(session)
            db.commit()
            db.refresh(session)
            return session
        finally:
            db.close()
    
    def get_active_session(self, session_token: str) -> Optional[UserSession]:
        """Get active session by token."""
        db = self.SessionLocal()
        try:
            return db.query(UserSession).filter(
                UserSession.session_token == session_token,
                UserSession.is_active == True,
                UserSession.expires_at > datetime.utcnow()
            ).first()
        finally:
            db.close()
    
    def invalidate_session(self, session_token: str):
        """Invalidate a session."""
        db = self.SessionLocal()
        try:
            session = db.query(UserSession).filter(UserSession.session_token == session_token).first()
            if session:
                session.is_active = False
                db.commit()
        finally:
            db.close()
    
    def get_user_title_mappings(self, user_id: str) -> List[TitleMapping]:
        """Get user's title mappings."""
        db = self.SessionLocal()
        try:
            return db.query(TitleMapping).filter(TitleMapping.user_id == user_id).all()
        finally:
            db.close()
    
    def save_title_mapping(self, user_id: str, pdf_title: str, catalog_title: str, catalog_song_id: str = None) -> TitleMapping:
        """Save or update a title mapping."""
        db = self.SessionLocal()
        try:
            # Check if mapping already exists
            existing = db.query(TitleMapping).filter(
                TitleMapping.user_id == user_id,
                TitleMapping.pdf_title == pdf_title
            ).first()
            
            if existing:
                # Update existing mapping
                existing.catalog_title = catalog_title
                existing.catalog_song_id = catalog_song_id
                existing.updated_at = datetime.utcnow()
                db.commit()
                return existing
            else:
                # Create new mapping
                mapping = TitleMapping(
                    user_id=user_id,
                    pdf_title=pdf_title,
                    catalog_title=catalog_title,
                    catalog_song_id=catalog_song_id
                )
                db.add(mapping)
                db.commit()
                db.refresh(mapping)
                return mapping
        finally:
            db.close()
    
    def get_user_files(self, user_id: str, file_type: str = None) -> List[FileUpload]:
        """Get user's files, optionally filtered by type."""
        db = self.SessionLocal()
        try:
            query = db.query(FileUpload).filter(
                FileUpload.user_id == user_id,
                FileUpload.is_active == True
            )
            if file_type:
                query = query.filter(FileUpload.file_type == file_type)
            return query.order_by(FileUpload.created_at.desc()).all()
        finally:
            db.close()
    
    def save_file_upload(self, user_id: str, file_type: str, original_filename: str, 
                        stored_filename: str, file_path: str, file_size: int, 
                        mime_type: str = None, metadata: Dict = None) -> FileUpload:
        """Save a file upload record."""
        db = self.SessionLocal()
        try:
            file_upload = FileUpload(
                user_id=user_id,
                file_type=file_type,
                original_filename=original_filename,
                stored_filename=stored_filename,
                file_path=file_path,
                file_size=file_size,
                mime_type=mime_type,
                metadata=metadata
            )
            db.add(file_upload)
            db.commit()
            db.refresh(file_upload)
            return file_upload
        finally:
            db.close()
    
    def get_latest_backup(self, user_id: str) -> Optional[FileUpload]:
        """Get user's latest backup file."""
        db = self.SessionLocal()
        try:
            return db.query(FileUpload).filter(
                FileUpload.user_id == user_id,
                FileUpload.file_type == 'backup',
                FileUpload.is_active == True
            ).order_by(FileUpload.created_at.desc()).first()
        finally:
            db.close()

# Initialize database
def init_database():
    """Initialize the database with tables."""
    db_manager = DatabaseManager()
    db_manager.create_tables()
    print("Database initialized successfully")

if __name__ == "__main__":
    init_database()
