#!/usr/bin/env python3
"""
Fix the mappings file to match the database.
"""

import json
from pathlib import Path
from simple_database import SimpleDatabase

def fix_mappings_file():
    """Update the mappings file to match the database."""
    print("🔧 Fixing mappings file...")
    
    user_id = "35e76f8b-65f7-48c1-9920-932122e98219"
    
    # Get all mappings from database
    db = SimpleDatabase()
    mappings = db.get_user_title_mappings(user_id)
    mappings_dict = {mapping['pdf_title']: mapping['catalog_title'] for mapping in mappings}
    
    print(f"✅ Database has {len(mappings_dict)} mappings")
    
    # Update the mappings file
    user_data_dir = Path("user_data") / user_id
    user_data_dir.mkdir(parents=True, exist_ok=True)
    mappings_file = user_data_dir / "title_mapper.json"
    
    with open(mappings_file, 'w', encoding='utf-8') as f:
        json.dump({"title_mapper": mappings_dict}, f, indent=2)
    
    print(f"✅ Updated mappings file: {mappings_file}")
    print(f"✅ File now has {len(mappings_dict)} mappings")
    
    return True

if __name__ == "__main__":
    fix_mappings_file()
