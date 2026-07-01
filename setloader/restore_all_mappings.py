#!/usr/bin/env python3
"""
Restore all mappings from the backup file to database and temp files
"""

import sqlite3
import json
import os
import glob
from pathlib import Path

def restore_all_mappings():
    """Restore all mappings from backup"""
    
    print("🔧 Restoring ALL mappings from backup...")
    
    # Connect to database
    db_path = "setloader.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    user_id = "35e76f8b-65f7-48c1-9920-932122e98219"
    
    # 1. Clear existing mappings
    print("1. Clearing existing mappings...")
    cursor.execute("DELETE FROM title_mappings WHERE user_id = ?", (user_id,))
    conn.commit()
    print(f"   ✅ Cleared existing mappings")
    
    # 2. Load mappings from backup file
    backup_file = "user_data/35e76f8b-65f7-48c1-9920-932122e98219/title_mapper.json"
    print(f"2. Loading mappings from {backup_file}...")
    
    with open(backup_file, 'r') as f:
        mappings = json.load(f)
    
    print(f"   ✅ Loaded {len(mappings)} mappings from backup")
    
    # 3. Save all mappings to database
    print("3. Saving all mappings to database...")
    for pdf_title, catalog_title in mappings.items():
        cursor.execute("""
            INSERT INTO title_mappings (user_id, pdf_title, catalog_title, created_at)
            VALUES (?, ?, ?, datetime('now'))
        """, (user_id, pdf_title, catalog_title))
    
    conn.commit()
    print(f"   ✅ Saved {len(mappings)} mappings to database")
    
    # 4. Update all temp mapping files
    print("4. Updating all temporary mapping files...")
    temp_files = glob.glob("work/*/temp_mappings.json")
    print(f"Found {len(temp_files)} temporary mapping files")
    
    fixed_count = 0
    for temp_file in temp_files:
        try:
            # Create the structure with all mappings
            clean_data = {
                "title_mapper": mappings
            }
            
            # Write the mappings
            with open(temp_file, 'w') as f:
                json.dump(clean_data, f, indent=2)
            
            fixed_count += 1
            
        except Exception as e:
            print(f"  ❌ Error fixing {temp_file}: {e}")
    
    print(f"   ✅ Updated {fixed_count} temporary mapping files")
    
    # 5. Verify the fix
    print("5. Verifying restoration...")
    cursor.execute("SELECT COUNT(*) FROM title_mappings WHERE user_id = ?", (user_id,))
    count = cursor.fetchone()[0]
    print(f"   ✅ Database now has {count} mappings")
    
    # Show some examples
    cursor.execute("SELECT pdf_title, catalog_title FROM title_mappings WHERE user_id = ? LIMIT 10", (user_id,))
    examples = cursor.fetchall()
    print("   📋 Sample mappings:")
    for pdf_title, catalog_title in examples:
        print(f"      '{pdf_title}' -> '{catalog_title}'")
    
    conn.close()
    print(f"🎉 Restored {len(mappings)} title mappings successfully!")

if __name__ == "__main__":
    restore_all_mappings()
