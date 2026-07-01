#!/usr/local/bin/python3
"""
Reusable library for validating song titles against user's SBP backup and title mappings.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from sbp_library import SBPLibrary, SBPFile, Song
from datetime import datetime

class TitleValidationError(Exception):
    """Custom exception for title validation errors."""
    pass

class TitleValidator:
    """
    A reusable library for validating song titles against user's SBP backup and title mappings.
    """
    
    def __init__(self, user_id: str, backup_path: Path, mappings_path: Optional[Path] = None):
        """
        Initialize the title validator.
        
        Args:
            user_id: User's email address/account ID
            backup_path: Path to user's SBP backup file
            mappings_path: Optional path to user's title mappings file
        """
        self.user_id = user_id
        self.backup_path = backup_path
        self.sbp_lib = SBPLibrary()
        self.backup_sbp = None
        self.title_mappings = {}
        
        # Auto-detect mappings path if not provided
        if mappings_path is None:
            mappings_path = self._find_user_mappings_path(user_id)
        
        self.mappings_path = mappings_path
        
        # Load SBP backup
        self._load_backup()
        
        # Load title mappings if available
        if mappings_path and mappings_path.exists():
            print(f"[DEBUG] Loading mappings from {mappings_path}")
            self._load_mappings()
        elif mappings_path:
            print(f"Warning: Mappings file {mappings_path} not found")
    
    def _find_user_mappings_path(self, user_id: str) -> Optional[Path]:
        """
        Find the user's title mappings file based on user ID.
        
        Args:
            user_id: User's email address/account ID
            
        Returns:
            Path to mappings file if found, None otherwise
        """
        # Search for user data directory
        user_data_dir = Path("user_data")
        if not user_data_dir.exists():
            return None
        
        # Look for directories that might contain this user's data
        # First, try to find a directory that matches the user_id exactly
        user_dir = user_data_dir / user_id
        if user_dir.exists():
            mappings_file = user_dir / "title_mapper.json"
            if mappings_file.exists():
                return mappings_file
        
        # Fallback: Check for Google OAuth directories (legacy support)
        google_dirs = [d for d in user_data_dir.iterdir() if d.is_dir() and d.name.startswith('google_')]
        
        # If we have Google directories, check them for title_mapper.json
        for google_dir in google_dirs:
            mappings_file = google_dir / "title_mapper.json"
            if mappings_file.exists():
                return mappings_file
        
        # Fallback: look for any directory with title_mapper.json
        for user_dir in user_data_dir.iterdir():
            if user_dir.is_dir():
                mappings_file = user_dir / "title_mapper.json"
                if mappings_file.exists():
                    return mappings_file
        
        return None
    
    def _load_backup(self):
        """Load the user's SBP backup file."""
        try:
            self.backup_sbp = self.sbp_lib.load_sbp_file(self.backup_path)
            print(f"Loaded backup with {len(self.backup_sbp.songs)} songs")
        except Exception as e:
            raise TitleValidationError(f"Error loading SBP backup {self.backup_path}: {e}")
    
    def _load_mappings(self):
        """Load the user's title mappings."""
        try:
            with open(self.mappings_path, 'r', encoding='utf-8') as f:
                user_data = json.load(f)
                # Extract title_mapper from user_data.json
                self.title_mappings = user_data.get("title_mapper", {})
            print(f"[DEBUG] Loaded {len(self.title_mappings)} title mappings")
            print(f"[DEBUG] Sample mappings: {list(self.title_mappings.items())[:3]}")
        except Exception as e:
            print(f"Warning: Could not load title mappings from {self.mappings_path}: {e}")
            self.title_mappings = {}
    
    def _normalize_title(self, title: str) -> str:
        """
        Normalize a song title for comparison.
        
        Args:
            title: Original title
            
        Returns:
            Normalized title
        """
        if not title:
            return ""
        
        # Convert to lowercase and strip whitespace
        normalized = title.lower().strip()
        
        # Remove common punctuation and extra spaces
        import re
        normalized = re.sub(r'[^\w\s]', '', normalized)
        normalized = re.sub(r'\s+', ' ', normalized)
        
        return normalized
    
    def _find_song_in_backup(self, title: str) -> Optional[Song]:
        """
        Find a song in the backup by exact title match.
        
        Args:
            title: Song title to search for
            
        Returns:
            Song object if found, None otherwise
        """
        normalized_title = self._normalize_title(title)
        
        for song in self.backup_sbp.songs:
            if self._normalize_title(song.name) == normalized_title:
                return song
        
        return None
    
    def _find_song_by_mapping(self, title: str) -> Optional[Song]:
        """
        Find a song in the backup using title mappings.
        
        Args:
            title: Original song title
            
        Returns:
            Song object if found through mapping, None otherwise
        """
        print(f"[DEBUG] Looking for mapping for title: '{title}'")
        print(f"[DEBUG] Available mappings: {list(self.title_mappings.keys())[:5]}...")
        
        # Check if we have a mapping for this title (case-insensitive)
        normalized_title = self._normalize_title(title)
        mapped_title = None
        
        # Try exact match first
        if title in self.title_mappings:
            mapped_title = self.title_mappings[title]
            print(f"[DEBUG] Found exact match: '{title}' -> '{mapped_title}'")
        else:
            # Try case-insensitive match
            for key, value in self.title_mappings.items():
                if self._normalize_title(key) == normalized_title:
                    mapped_title = value
                    print(f"[DEBUG] Found case-insensitive match: '{key}' -> '{mapped_title}'")
                    break
        
        if not mapped_title:
            print(f"[DEBUG] No mapping found for '{title}'")
            return None
        
        # Look up the mapped title in the backup
        result = self._find_song_in_backup(mapped_title)
        print(f"[DEBUG] Lookup result for '{mapped_title}': {result is not None}")
        return result
    
    def validate_song(self, title: str) -> Tuple[bool, Optional[Song], str]:
        """
        Validate a single song title.
        
        Args:
            title: Song title to validate
            
        Returns:
            Tuple of (is_valid, song_object, status_message)
        """
        # Step 1: Try direct lookup in backup
        song = self._find_song_in_backup(title)
        if song:
            return True, song, "Found in backup"
        
        # Step 2: Try lookup through title mappings
        song = self._find_song_by_mapping(title)
        if song:
            return True, song, "Found through mapping"
        
        # Step 3: Not found
        return False, None, "Not found in backup or mappings"
    
    def validate_song_list(self, songs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Validate a list of songs.
        
        Args:
            songs: List of song dictionaries with 'title' field
            
        Returns:
            List of validated song dictionaries with additional fields
        """
        validated_songs = []
        
        for i, song_data in enumerate(songs):
            title = song_data.get('title', '').strip()
            if not title:
                continue
            
            is_valid, song_obj, status = self.validate_song(title)
            
            # Determine the validated title based on how it was found
            if is_valid and song_obj:
                if status == "Found through mapping":
                    # For mapped songs, use the mapped title (song_obj.name)
                    validated_title = song_obj.name
                else:
                    # For direct backup matches, use the original title
                    validated_title = title
            else:
                # Not found, use original title
                validated_title = title
            
            validated_song = {
                'order': song_data.get('order', i + 1),
                'title': title,
                'validated': is_valid,
                'status': status,
                'song_id': song_obj.id if song_obj else None,
                'validated_title': validated_title
            }
            
            # Preserve other fields from original song data
            for key, value in song_data.items():
                if key not in validated_song:
                    validated_song[key] = value
            
            validated_songs.append(validated_song)
        
        return validated_songs
    
    def validate_sets(self, sets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Validate all sets while maintaining grouping and sequence.
        
        Args:
            sets: List of set dictionaries
            
        Returns:
            List of validated set dictionaries
        """
        validated_sets = []
        
        for set_data in sets:
            validated_set = {
                'name': set_data.get('name', ''),
                'time_window': set_data.get('time_window', ''),
                'break_minutes': set_data.get('break_minutes', 0),
                'songs': self.validate_song_list(set_data.get('songs', [])),
                'validated_count': 0,
                'missing_count': 0
            }
            
            # Count validated and missing songs
            for song in validated_set['songs']:
                if song['validated']:
                    validated_set['validated_count'] += 1
                else:
                    validated_set['missing_count'] += 1
            
            validated_sets.append(validated_set)
        
        return validated_sets
    
    def validate_extras(self, extras: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Validate extras while maintaining sequence.
        
        Args:
            extras: List of extra song dictionaries
            
        Returns:
            List of validated extra song dictionaries
        """
        return self.validate_song_list(extras)
    
    def validate_input(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate the entire input JSON structure.
        
        Args:
            input_data: Input JSON data
            
        Returns:
            Validated JSON data with additional fields
        """
        validated_data = {
            'sets': self.validate_sets(input_data.get('sets', [])),
            'extras': self.validate_extras(input_data.get('extras', [])),
            'counts': {
                'per_set': {},
                'extras': 0,
                'total': 0,
                'validated_total': 0,
                'missing_total': 0
            },
            'errors': input_data.get('errors', []),
            'validation_info': {
                'user_id': self.user_id,
                'backup_path': str(self.backup_path),
                'mappings_path': str(self.mappings_path) if self.mappings_path else None,
                'validated_at': datetime.now().isoformat(),
                'total_songs_in_backup': len(self.backup_sbp.songs),
                'total_mappings': len(self.title_mappings)
            }
        }
        
        # Calculate counts
        total_validated = 0
        total_missing = 0
        
        for set_data in validated_data['sets']:
            set_name = set_data['name']
            validated_count = set_data['validated_count']
            missing_count = set_data['missing_count']
            
            validated_data['counts']['per_set'][set_name] = {
                'total': len(set_data['songs']),
                'validated': validated_count,
                'missing': missing_count
            }
            
            total_validated += validated_count
            total_missing += missing_count
        
        # Count extras
        extras_validated = sum(1 for song in validated_data['extras'] if song['validated'])
        extras_missing = sum(1 for song in validated_data['extras'] if not song['validated'])
        
        validated_data['counts']['extras'] = {
            'total': len(validated_data['extras']),
            'validated': extras_validated,
            'missing': extras_missing
        }
        
        total_validated += extras_validated
        total_missing += extras_missing
        
        validated_data['counts']['total'] = total_validated + total_missing
        validated_data['counts']['validated_total'] = total_validated
        validated_data['counts']['missing_total'] = total_missing
        
        return validated_data
    
    def get_summary(self, validated_data: Dict[str, Any]) -> str:
        """
        Get a summary of the validation results.
        
        Args:
            validated_data: Validated data dictionary
            
        Returns:
            Summary string
        """
        counts = validated_data['counts']
        summary_parts = []
        
        summary_parts.append(f"Total songs: {counts['total']}")
        summary_parts.append(f"Validated: {counts['validated_total']}")
        summary_parts.append(f"Missing: {counts['missing_total']}")
        
        for set_name, set_counts in counts['per_set'].items():
            summary_parts.append(f"{set_name}: {set_counts['validated']}/{set_counts['total']} validated")
        
        if counts['extras']['total'] > 0:
            summary_parts.append(f"Extras: {counts['extras']['validated']}/{counts['extras']['total']} validated")
        
        if counts['missing_total'] > 0:
            summary_parts.append(f"\nMissing songs:")
            for set_data in validated_data['sets']:
                for song in set_data['songs']:
                    if not song['validated']:
                        summary_parts.append(f"  - {song['title']} (in {set_data['name']})")
            for song in validated_data['extras']:
                if not song['validated']:
                    summary_parts.append(f"  - {song['title']} (in extras)")
        
        return "\n".join(summary_parts)

# Convenience function for simple usage
def validate_titles_from_json(input_data: Dict[str, Any], user_id: str, backup_path: Path, mappings_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Convenience function to validate titles from JSON data.
    
    Args:
        input_data: Input JSON data with songs
        user_id: User's email address/account ID
        backup_path: Path to user's SBP backup file
        mappings_path: Optional path to user's title mappings file
        
    Returns:
        Validated JSON data with additional fields
        
    Raises:
        TitleValidationError: If validation fails
    """
    validator = TitleValidator(user_id, backup_path, mappings_path)
    return validator.validate_input(input_data)
