#!/usr/local/bin/python3
"""
Remove the mapping for "Party Started" from the database.
"""

import sqlite3
import json
from pathlib import Path

def remove_party_started_mapping():
    """Remove the mapping for 'Party Started' from the database."""
    
    # Connect to database
    conn = sqlite3.connect("setloader.db")
    cursor = conn.cursor()
    
    # Find the mapping for "Party Started"
    cursor.execute(
        "SELECT * FROM title_mappings WHERE pdf_title = ? OR catalog_title = ?",
        ("Party Started", "Party Started")
    )
    
    mappings = cursor.fetchall()
    print(f"Found {len(mappings)} mappings for 'Party Started':")
    
    for mapping in mappings:
        print(f"  ID: {mapping[0]}")
        print(f"  User ID: {mapping[1]}")
        print(f"  PDF Title: {mapping[2]}")
        print(f"  Catalog Title: {mapping[3]}")
        print(f"  Created: {mapping[5]}")
        print()
    
    if mappings:
        # Delete the mapping(s)
        cursor.execute(
            "DELETE FROM title_mappings WHERE pdf_title = ? OR catalog_title = ?",
            ("Party Started", "Party Started")
        )
        
        deleted_count = cursor.rowcount
        conn.commit()
        
        print(f"Deleted {deleted_count} mapping(s) for 'Party Started'")
        
    else:
        print("No mappings found for 'Party Started'")
    
    conn.close()
    print("Database operation completed")

if __name__ == "__main__":
    remove_party_started_mapping()