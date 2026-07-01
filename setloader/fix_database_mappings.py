#!/usr/bin/env python3
"""
Fix the database mappings by completely clearing and rebuilding from the clean backup
"""

import sqlite3
import json
import os
from pathlib import Path

def fix_database_mappings():
    """Fix the database mappings completely"""
    
    print("🔧 Fixing database mappings...")
    
    # Connect to database
    db_path = "setloader.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    user_id = "35e76f8b-65f7-48c1-9920-932122e98219"
    
    # 1. Clear ALL existing mappings for this user
    print("1. Clearing ALL existing mappings from database...")
    cursor.execute("DELETE FROM title_mappings WHERE user_id = ?", (user_id,))
    conn.commit()
    print(f"   ✅ Cleared all existing mappings")
    
    # 2. Load clean mappings from the backup file
    backup_file = "user_data/35e76f8b-65f7-48c1-9920-932122e98219/title_mapper_clean.json"
    print(f"2. Loading clean mappings from {backup_file}...")
    
    with open(backup_file, 'r', encoding='utf-8') as f:
        backup_data = json.load(f)
    
    # Extract the clean mappings - the backup file has mappings directly, not nested
    clean_mappings = backup_data
    print(f"   ✅ Loaded {len(clean_mappings)} clean mappings")
    
    # 3. Insert clean mappings into database
    print("3. Inserting clean mappings into database...")
    
    for pdf_title, catalog_title in clean_mappings.items():
        # Skip empty or invalid mappings
        if not pdf_title or not catalog_title or pdf_title.strip() == "":
            continue
            
        cursor.execute("""
            INSERT INTO title_mappings (user_id, pdf_title, catalog_title)
            VALUES (?, ?, ?)
        """, (user_id, pdf_title.strip(), catalog_title.strip()))
    
    conn.commit()
    
    # 4. Verify the fix
    cursor.execute("SELECT COUNT(*) FROM title_mappings WHERE user_id = ?", (user_id,))
    count = cursor.fetchone()[0]
    print(f"   ✅ Inserted {count} clean mappings into database")
    
    # 5. Show sample of clean mappings
    cursor.execute("SELECT pdf_title, catalog_title FROM title_mappings WHERE user_id = ? LIMIT 5", (user_id,))
    samples = cursor.fetchall()
    print("   Sample clean mappings:")
    for pdf_title, catalog_title in samples:
        print(f"     '{pdf_title}' -> '{catalog_title}'")
    
    conn.close()
    
    print("🎉 Database mappings fixed successfully!")
    print(f"   - Cleared all corrupted mappings")
    print(f"   - Restored {count} clean mappings from backup")
    print(f"   - Database is now clean and ready to use")

if __name__ == "__main__":
    fix_database_mappings()
