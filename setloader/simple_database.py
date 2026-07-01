#!/usr/local/bin/python3
"""
Simple SQLite database using Python's built-in sqlite3 module.
"""

import sqlite3
import json
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path

class SimpleDatabase:
    """Simple SQLite database manager."""
    
    def __init__(self, db_path: str = "setloader.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize the database with tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                google_id TEXT UNIQUE,
                name TEXT,
                picture_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                session_token TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS title_mappings (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                pdf_title TEXT NOT NULL,
                catalog_title TEXT NOT NULL,
                catalog_song_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, pdf_title),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS file_uploads (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                file_type TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                stored_filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                mime_type TEXT,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def get_connection(self):
        """Get database connection."""
        return sqlite3.connect(self.db_path)
    
    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """Get user by email."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM users WHERE email = ? AND is_active = 1", 
            (email,)
        )
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'id': row[0],
                'email': row[1],
                'google_id': row[2],
                'name': row[3],
                'picture_url': row[4],
                'created_at': row[5],
                'last_login': row[6],
                'is_active': bool(row[7])
            }
        return None
    
    def get_user_by_id(self, user_id: str) -> Optional[Dict]:
        """Get user by ID."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM users WHERE id = ? AND is_active = 1", 
            (user_id,)
        )
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'id': row[0],
                'email': row[1],
                'google_id': row[2],
                'name': row[3],
                'picture_url': row[4],
                'created_at': row[5],
                'last_login': row[6],
                'is_active': bool(row[7])
            }
        return None
    
    def create_user(self, email: str, google_id: str = None, name: str = None, picture_url: str = None) -> Dict:
        """Create a new user."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        user_id = str(uuid.uuid4())
        cursor.execute(
            "INSERT INTO users (id, email, google_id, name, picture_url) VALUES (?, ?, ?, ?, ?)",
            (user_id, email, google_id, name, picture_url)
        )
        conn.commit()
        conn.close()
        
        return self.get_user_by_id(user_id)
    
    def create_session(self, user_id: str, session_token: str, expires_in_hours: int = 24) -> Dict:
        """Create a user session."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        session_id = str(uuid.uuid4())
        expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours)
        
        cursor.execute(
            "INSERT INTO user_sessions (id, user_id, session_token, expires_at) VALUES (?, ?, ?, ?)",
            (session_id, user_id, session_token, expires_at.isoformat())
        )
        conn.commit()
        conn.close()
        
        return {
            'id': session_id,
            'user_id': user_id,
            'session_token': session_token,
            'expires_at': expires_at.isoformat()
        }
    
    def get_active_session(self, session_token: str) -> Optional[Dict]:
        """Get active session by token."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM user_sessions WHERE session_token = ? AND is_active = 1 AND expires_at > ?",
            (session_token, datetime.utcnow().isoformat())
        )
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'id': row[0],
                'user_id': row[1],
                'session_token': row[2],
                'created_at': row[3],
                'expires_at': row[4],
                'is_active': bool(row[5])
            }
        return None
    
    def invalidate_session(self, session_token: str):
        """Invalidate a session."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE user_sessions SET is_active = 0 WHERE session_token = ?",
            (session_token,)
        )
        conn.commit()
        conn.close()
    
    def get_user_title_mappings(self, user_id: str) -> List[Dict]:
        """Get user's title mappings."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM title_mappings WHERE user_id = ?",
            (user_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                'id': row[0],
                'user_id': row[1],
                'pdf_title': row[2],
                'catalog_title': row[3],
                'catalog_song_id': row[4],
                'created_at': row[5],
                'updated_at': row[6]
            }
            for row in rows
        ]
    
    def save_title_mapping(self, user_id: str, pdf_title: str, catalog_title: str, catalog_song_id: str = None) -> Dict:
        """Save or update a title mapping."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Check if mapping already exists
        cursor.execute(
            "SELECT id FROM title_mappings WHERE user_id = ? AND pdf_title = ?",
            (user_id, pdf_title)
        )
        existing = cursor.fetchone()
        
        if existing:
            # Update existing mapping
            cursor.execute(
                "UPDATE title_mappings SET catalog_title = ?, catalog_song_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (catalog_title, catalog_song_id, existing[0])
            )
            mapping_id = existing[0]
        else:
            # Create new mapping
            mapping_id = str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO title_mappings (id, user_id, pdf_title, catalog_title, catalog_song_id) VALUES (?, ?, ?, ?, ?)",
                (mapping_id, user_id, pdf_title, catalog_title, catalog_song_id)
            )
        
        conn.commit()
        conn.close()
        
        return {
            'id': mapping_id,
            'user_id': user_id,
            'pdf_title': pdf_title,
            'catalog_title': catalog_title,
            'catalog_song_id': catalog_song_id
        }
    
    def get_user_files(self, user_id: str, file_type: str = None) -> List[Dict]:
        """Get user's files, optionally filtered by type."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if file_type:
            cursor.execute(
                "SELECT * FROM file_uploads WHERE user_id = ? AND file_type = ? AND is_active = 1 ORDER BY created_at DESC",
                (user_id, file_type)
            )
        else:
            cursor.execute(
                "SELECT * FROM file_uploads WHERE user_id = ? AND is_active = 1 ORDER BY created_at DESC",
                (user_id,)
            )
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                'id': row[0],
                'user_id': row[1],
                'file_type': row[2],
                'original_filename': row[3],
                'stored_filename': row[4],
                'file_path': row[5],
                'file_size': row[6],
                'mime_type': row[7],
                'metadata': json.loads(row[8]) if row[8] else None,
                'created_at': row[9],
                'is_active': bool(row[10])
            }
            for row in rows
        ]
    
    def save_file_upload(self, user_id: str, file_type: str, original_filename: str, 
                        stored_filename: str, file_path: str, file_size: int, 
                        mime_type: str = None, metadata: Dict = None) -> Dict:
        """Save a file upload record."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        file_id = str(uuid.uuid4())
        metadata_json = json.dumps(metadata) if metadata else None
        
        cursor.execute(
            "INSERT INTO file_uploads (id, user_id, file_type, original_filename, stored_filename, file_path, file_size, mime_type, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (file_id, user_id, file_type, original_filename, stored_filename, file_path, file_size, mime_type, metadata_json)
        )
        conn.commit()
        conn.close()
        
        return {
            'id': file_id,
            'user_id': user_id,
            'file_type': file_type,
            'original_filename': original_filename,
            'stored_filename': stored_filename,
            'file_path': file_path,
            'file_size': file_size,
            'mime_type': mime_type,
            'metadata': metadata,
            'created_at': datetime.utcnow().isoformat(),
            'is_active': True
        }
    
    def get_latest_backup(self, user_id: str) -> Optional[Dict]:
        """Get user's latest backup file."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM file_uploads WHERE user_id = ? AND file_type = 'backup' AND is_active = 1 ORDER BY created_at DESC LIMIT 1",
            (user_id,)
        )
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'id': row[0],
                'user_id': row[1],
                'file_type': row[2],
                'original_filename': row[3],
                'stored_filename': row[4],
                'file_path': row[5],
                'file_size': row[6],
                'mime_type': row[7],
                'metadata': json.loads(row[8]) if row[8] else None,
                'created_at': row[9],
                'is_active': bool(row[10])
            }
        return None
    
    def clear_user_files(self, user_id: str):
        """Clear user's files (downloads, setlists, backups) but keep title mappings."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Delete file uploads but keep title mappings
        cursor.execute(
            "DELETE FROM file_uploads WHERE user_id = ?",
            (user_id,)
        )
        
        conn.commit()
        conn.close()

# Global database instance
db = SimpleDatabase()

def init_database():
    """Initialize the database."""
    print("Simple SQLite database initialized successfully")

if __name__ == "__main__":
    init_database()
