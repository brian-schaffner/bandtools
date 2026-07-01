#!/usr/local/bin/python3
"""
Migrate existing file-based data to the new database.
"""

import json
import os
from pathlib import Path
from database import DatabaseManager, User, TitleMapping, FileUpload
from datetime import datetime

def migrate_user_data():
    """Migrate user data from files to database."""
    db_manager = DatabaseManager()
    
    # Get or create the default user
    user = db_manager.get_user_by_email("brian@schaffner.net")
    if not user:
        user = db_manager.create_user(
            email="brian@schaffner.net",
            name="Brian Schaffner"
        )
        print(f"Created user: {user.email}")
    else:
        print(f"Found existing user: {user.email}")
    
    # Migrate title mappings
    user_data_path = Path("user_data/user_898313/user_data.json")
    if user_data_path.exists():
        with open(user_data_path, 'r') as f:
            user_data = json.load(f)
        
        title_mapper = user_data.get("title_mapper", {})
        print(f"Found {len(title_mapper)} title mappings to migrate")
        
        for pdf_title, catalog_title in title_mapper.items():
            try:
                db_manager.save_title_mapping(
                    user_id=str(user.id),
                    pdf_title=pdf_title,
                    catalog_title=catalog_title
                )
            except Exception as e:
                print(f"Error migrating mapping {pdf_title}: {e}")
        
        print(f"✅ Migrated {len(title_mapper)} title mappings")
    
    # Migrate file uploads
    print("Migrating file uploads...")
    
    # Migrate backup files
    backup_files = []
    for file_path in Path("user_data/user_898313").glob("backup_*"):
        if file_path.is_file():
            backup_files.append(file_path)
    
    for backup_file in backup_files:
        try:
            file_upload = db_manager.save_file_upload(
                user_id=str(user.id),
                file_type="backup",
                original_filename=backup_file.name,
                stored_filename=backup_file.name,
                file_path=str(backup_file.absolute()),
                file_size=backup_file.stat().st_size,
                mime_type="application/octet-stream",
                metadata={"migrated": True, "original_path": str(backup_file)}
            )
            print(f"Migrated backup: {backup_file.name}")
        except Exception as e:
            print(f"Error migrating backup {backup_file.name}: {e}")
    
    print(f"✅ Migrated {len(backup_files)} backup files")
    
    return user

def main():
    """Main migration function."""
    print("Starting data migration...")
    
    try:
        user = migrate_user_data()
        print(f"✅ Migration completed successfully for user: {user.email}")
        print(f"User ID: {user.id}")
        
        # Verify migration
        db_manager = DatabaseManager()
        mappings = db_manager.get_user_title_mappings(str(user.id))
        files = db_manager.get_user_files(str(user.id))
        
        print(f"Verification:")
        print(f"  - Title mappings: {len(mappings)}")
        print(f"  - File uploads: {len(files)}")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
