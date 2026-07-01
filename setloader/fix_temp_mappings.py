#!/usr/bin/env python3
"""
Fix all temporary mapping files to use the clean mappings
"""

import json
import os
import glob
from pathlib import Path

def fix_temp_mappings():
    """Fix all temporary mapping files"""
    
    print("🔧 Fixing all temporary mapping files...")
    
    # Clean mappings that should be used everywhere
    clean_mappings = {
        "Refuge": "Refugee",
        "3 steps": "Gimme Three Steps", 
        "Hurt So Good": "Hurts So Good",
        "U're No Good": "Youre No Good",
        "No One Else Earth": "No One Else On Earth",
        "Ex's Ohs": "Exs And Ohs",
        "Stuck": "Stuck In The Middle With You",
        "Workin' Man": "Workin Man Blues",
        "One Headlt": "One Headlight",
        "When B Loved": "When Will I Be Loved",
        "Knock Wood": "Knock On Wood",
        "Boogie Oogie": "Boogie Oogie Oogie",
        "Get Down2nite": "Get Down Tonight",
        "Makes U Happy": "If It Makes You Happy",
        "Whenever U Come Around": "Whenever You Come Around",
        "Heaven": "Locked Out Of Heaven",
        "Party Started": "Get The Party Started",
        "Str8 On": "Straight On",
        "Poker": "Poker Face",
        "Running Empty": "Running On Empty",
        "Blvd Brkn Drms": "Boulevard Of Broken Dreams",
        "Man I Feel": "Man I Feel Like A Woman",
        "Alright Now": "All Right Now",
        "Hands 2 Urself": "Keep Your Hands To Yourself",
        "Not in 4 Love": "If Youre Not In It For Love Im Outta Here",
        "Roll Changes": "Roll With The Changes",
        "Oh Baby Baby": "Baby One More Time",
        "Ever Seen Rain": "Have You Ever Seen The Rain",
        "Liv Prayer": "Livin On A Prayer",
        "Cake": "Cake By The Ocean",
        "Folsom": "Folsom Prison Blues",
        "I'm Only One": "Im The Only One"
    }
    
    # Find all temp_mappings.json files
    temp_files = glob.glob("work/*/temp_mappings.json")
    print(f"Found {len(temp_files)} temporary mapping files")
    
    fixed_count = 0
    for temp_file in temp_files:
        try:
            print(f"Fixing: {temp_file}")
            
            # Create the clean structure
            clean_data = {
                "title_mapper": clean_mappings
            }
            
            # Write the clean mappings
            with open(temp_file, 'w') as f:
                json.dump(clean_data, f, indent=2)
            
            fixed_count += 1
            print(f"  ✅ Fixed {temp_file}")
            
        except Exception as e:
            print(f"  ❌ Error fixing {temp_file}: {e}")
    
    print(f"🎉 Fixed {fixed_count} temporary mapping files")
    
    # Also update the main user mappings file
    user_id = "35e76f8b-65f7-48c1-9920-932122e98219"
    main_file = f"user_data/{user_id}/title_mapper.json"
    
    if os.path.exists(main_file):
        print(f"Updating main mappings file: {main_file}")
        with open(main_file, 'w') as f:
            json.dump(clean_mappings, f, indent=2)
        print("  ✅ Updated main mappings file")
    
    print("🎉 All mapping files now have clean, working mappings!")

if __name__ == "__main__":
    fix_temp_mappings()
