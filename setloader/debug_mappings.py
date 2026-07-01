#!/usr/bin/env python3
"""
Debug the mappings loading issue.
"""

import sqlite3
import json

def debug_mappings():
    """Debug the mappings loading issue."""
    
    print("🔍 Debugging Mappings Loading")
    print("=" * 40)
    
    # Connect to database
    conn = sqlite3.connect('setloader.db')
    cursor = conn.cursor()
    
    # Get mappings for the user
    cursor.execute("""
        SELECT pdf_title, catalog_title 
        FROM title_mappings 
        WHERE user_id = '35e76f8b-65f7-48c1-9920-932122e98219'
        ORDER BY pdf_title
        LIMIT 10
    """)
    
    mappings = cursor.fetchall()
    print(f"📋 Raw database mappings (first 10):")
    for mapping in mappings:
        print(f"   '{mapping[0]}' -> '{mapping[1]}'")
    
    # Check for any mappings with leading commas
    cursor.execute("""
        SELECT pdf_title, catalog_title 
        FROM title_mappings 
        WHERE user_id = '35e76f8b-65f7-48c1-9920-932122e98219'
        AND (pdf_title LIKE ',%' OR catalog_title LIKE ',%')
        LIMIT 10
    """)
    
    bad_mappings = cursor.fetchall()
    print(f"\n📋 Mappings with leading commas: {len(bad_mappings)}")
    for mapping in bad_mappings:
        print(f"   '{mapping[0]}' -> '{mapping[1]}'")
    
    # Check for Refuge specifically
    cursor.execute("""
        SELECT pdf_title, catalog_title 
        FROM title_mappings 
        WHERE user_id = '35e76f8b-65f7-48c1-9920-932122e98219'
        AND pdf_title = 'Refuge'
    """)
    
    refuge_mappings = cursor.fetchall()
    print(f"\n📋 Refuge mappings: {len(refuge_mappings)}")
    for mapping in refuge_mappings:
        print(f"   '{mapping[0]}' -> '{mapping[1]}'")
    
    conn.close()

if __name__ == "__main__":
    debug_mappings()
