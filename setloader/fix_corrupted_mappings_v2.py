#!/usr/bin/env python3
"""
Fix corrupted mappings in the database - handle duplicates properly.
"""

import sqlite3
import re

def fix_corrupted_mappings():
    """Fix corrupted mappings with leading commas and spaces."""
    
    print("🔧 Fixing Corrupted Mappings (v2)")
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
    
    # Process mappings and handle duplicates
    cleaned_mappings = {}
    mappings_to_delete = []
    
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
            
            # Check if we already have a mapping for the cleaned title
            if cleaned_pdf_title in cleaned_mappings:
                # Keep the existing one, mark this one for deletion
                print(f"     Duplicate found, marking for deletion")
                mappings_to_delete.append(mapping_id)
            else:
                # Update this mapping
                cursor.execute("""
                    UPDATE title_mappings 
                    SET pdf_title = ? 
                    WHERE id = ?
                """, (cleaned_pdf_title, mapping_id))
                cleaned_mappings[cleaned_pdf_title] = catalog_title
        else:
            # No change needed
            cleaned_mappings[pdf_title] = catalog_title
    
    # Delete duplicate mappings
    if mappings_to_delete:
        print(f"\n🗑️ Deleting {len(mappings_to_delete)} duplicate mappings...")
        for mapping_id in mappings_to_delete:
            cursor.execute("DELETE FROM title_mappings WHERE id = ?", (mapping_id,))
    
    # Commit changes
    conn.commit()
    conn.close()
    
    print(f"\n✅ Fixed corrupted mappings and removed duplicates")
    
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
