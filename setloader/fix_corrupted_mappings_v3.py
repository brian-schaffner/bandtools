#!/usr/bin/env python3
"""
Fix corrupted mappings by deleting and recreating them.
"""

import sqlite3
import re

def fix_corrupted_mappings():
    """Fix corrupted mappings by deleting and recreating them."""
    
    print("🔧 Fixing Corrupted Mappings (v3)")
    print("=" * 40)
    
    # Connect to database
    conn = sqlite3.connect('setloader.db')
    cursor = conn.cursor()
    
    # Get all mappings for the user
    cursor.execute("""
        SELECT id, pdf_title, catalog_title 
        FROM title_mappings 
        WHERE user_id = '35e76f8b-65f7-48c1-9920-932122e98219'
        ORDER BY pdf_title
    """)
    
    mappings = cursor.fetchall()
    print(f"📋 Found {len(mappings)} total mappings")
    
    # Identify corrupted mappings
    corrupted_mappings = []
    clean_mappings = []
    
    for mapping_id, pdf_title, catalog_title in mappings:
        # Check if corrupted (has leading punctuation)
        if (pdf_title.startswith(',') or pdf_title.startswith('.') or 
            pdf_title.startswith(';') or pdf_title.startswith(':')):
            corrupted_mappings.append((mapping_id, pdf_title, catalog_title))
        else:
            clean_mappings.append((mapping_id, pdf_title, catalog_title))
    
    print(f"📋 Found {len(corrupted_mappings)} corrupted mappings")
    print(f"📋 Found {len(clean_mappings)} clean mappings")
    
    # Delete all corrupted mappings
    if corrupted_mappings:
        print(f"\n🗑️ Deleting {len(corrupted_mappings)} corrupted mappings...")
        for mapping_id, pdf_title, catalog_title in corrupted_mappings:
            print(f"   Deleting: '{pdf_title}' -> '{catalog_title}'")
            cursor.execute("DELETE FROM title_mappings WHERE id = ?", (mapping_id,))
    
    # Commit the deletions
    conn.commit()
    
    print(f"\n✅ Deleted corrupted mappings")
    
    # Verify the fix
    print("\n🔍 Verifying fix...")
    
    # Check for any remaining corrupted mappings
    cursor.execute("""
        SELECT pdf_title, catalog_title 
        FROM title_mappings 
        WHERE user_id = '35e76f8b-65f7-48c1-9920-932122e98219'
        AND (pdf_title LIKE ',%' OR pdf_title LIKE '.%' OR pdf_title LIKE ';%' OR pdf_title LIKE ':%')
        LIMIT 5
    """)
    
    remaining_bad = cursor.fetchall()
    if remaining_bad:
        print(f"❌ Still found {len(remaining_bad)} corrupted mappings:")
        for mapping in remaining_bad:
            print(f"   '{mapping[0]}' -> '{mapping[1]}'")
    else:
        print("✅ No corrupted mappings found")
    
    # Check Refuge mapping
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
    
    # Show remaining clean mappings
    cursor.execute("""
        SELECT COUNT(*) 
        FROM title_mappings 
        WHERE user_id = '35e76f8b-65f7-48c1-9920-932122e98219'
    """)
    
    remaining_count = cursor.fetchone()[0]
    print(f"\n📊 Remaining mappings: {remaining_count}")
    
    # Show some clean mappings
    cursor.execute("""
        SELECT pdf_title, catalog_title 
        FROM title_mappings 
        WHERE user_id = '35e76f8b-65f7-48c1-9920-932122e98219'
        ORDER BY pdf_title
        LIMIT 5
    """)
    
    clean_mappings = cursor.fetchall()
    print(f"\n📋 Clean mappings (first 5):")
    for mapping in clean_mappings:
        print(f"   '{mapping[0]}' -> '{mapping[1]}'")
    
    conn.close()

if __name__ == "__main__":
    fix_corrupted_mappings()
