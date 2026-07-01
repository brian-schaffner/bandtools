#!/usr/bin/env python3
"""
Fix corrupted mappings in the database.
"""

import sqlite3
import re

def fix_corrupted_mappings():
    """Fix corrupted mappings with leading commas and spaces."""
    
    print("🔧 Fixing Corrupted Mappings")
    print("=" * 40)
    
    # Connect to database
    conn = sqlite3.connect('setloader.db')
    cursor = conn.cursor()
    
    # Get all mappings for the user
    cursor.execute("""
        SELECT id, pdf_title, catalog_title 
        FROM title_mappings 
        WHERE user_id = '35e76f8b-65f7-48c1-9920-932122e98219'
    """)
    
    mappings = cursor.fetchall()
    print(f"📋 Found {len(mappings)} total mappings")
    
    # Fix corrupted mappings
    fixed_count = 0
    for mapping_id, pdf_title, catalog_title in mappings:
        original_pdf_title = pdf_title
        
        # Remove leading commas and spaces
        cleaned_pdf_title = pdf_title.lstrip(', ')
        
        # Remove leading dots and spaces
        cleaned_pdf_title = cleaned_pdf_title.lstrip('. ')
        
        # Remove leading semicolons and spaces
        cleaned_pdf_title = cleaned_pdf_title.lstrip('; ')
        
        # Remove leading colons and spaces
        cleaned_pdf_title = cleaned_pdf_title.lstrip(': ')
        
        # Remove any other leading punctuation
        cleaned_pdf_title = re.sub(r'^[^\w\s]+', '', cleaned_pdf_title)
        
        # Clean up extra spaces
        cleaned_pdf_title = re.sub(r'\s+', ' ', cleaned_pdf_title).strip()
        
        if cleaned_pdf_title != original_pdf_title:
            print(f"   Fixing: '{original_pdf_title}' -> '{cleaned_pdf_title}'")
            
            # Update the database
            cursor.execute("""
                UPDATE title_mappings 
                SET pdf_title = ? 
                WHERE id = ?
            """, (cleaned_pdf_title, mapping_id))
            
            fixed_count += 1
    
    # Commit changes
    conn.commit()
    conn.close()
    
    print(f"\n✅ Fixed {fixed_count} corrupted mappings")
    
    # Verify the fix
    print("\n🔍 Verifying fix...")
    conn = sqlite3.connect('setloader.db')
    cursor = conn.cursor()
    
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
    
    conn.close()

if __name__ == "__main__":
    fix_corrupted_mappings()
