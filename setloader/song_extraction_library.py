#!/usr/local/bin/python3
"""
Reusable library for extracting songs from validated titles and creating SBP files.
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from sbp_library import SBPLibrary, SBPFile, Song, Set, SetItem
from sbp_naming import format_sbp_set_name, truncate_name
from datetime import datetime

class SongExtractionError(Exception):
    """Custom exception for song extraction errors."""
    pass

class SongExtractor:
    """
    A reusable library for extracting songs from validated titles and creating SBP files.
    """
    
    def __init__(self, user_id: str, backup_path: Path):
        """
        Initialize the song extractor.
        
        Args:
            user_id: User's email address/account ID
            backup_path: Path to user's SBP backup file
        """
        self.user_id = user_id
        self.backup_path = backup_path
        self.sbp_lib = SBPLibrary()
        self.backup_sbp = None
        
        # Load SBP backup
        self._load_backup()
    
    def _load_backup(self):
        """Load the user's SBP backup file."""
        try:
            self.backup_sbp = self.sbp_lib.load_sbp_file(self.backup_path)
            print(f"Loaded backup with {len(self.backup_sbp.songs)} songs")
        except Exception as e:
            raise SongExtractionError(f"Error loading SBP backup {self.backup_path}: {e}")
    
    def _find_song_by_id(self, song_id: int) -> Optional[Song]:
        """
        Find a song in the backup by ID.
        
        Args:
            song_id: Song ID to search for
            
        Returns:
            Song object if found, None otherwise
        """
        for song in self.backup_sbp.songs:
            if song.id == song_id:
                return song
        return None
    
    def _find_song_by_title(self, title: str) -> Optional[Song]:
        """
        Find a song in the backup by title (case-insensitive).
        
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
    
    def extract_songs_from_set(self, set_data: Dict[str, Any]) -> Tuple[List[Song], List[str]]:
        """
        Extract songs from a validated set.
        
        Args:
            set_data: Set data with validated songs
            
        Returns:
            Tuple of (extracted_songs, missing_titles)
        """
        extracted_songs = []
        missing_titles = []
        
        for song_data in set_data.get('songs', []):
            if not song_data.get('validated', False):
                missing_titles.append(song_data.get('title', 'Unknown'))
                continue
            
            song_id = song_data.get('song_id')
            if song_id:
                # Try to find by ID first (most reliable)
                song = self._find_song_by_id(song_id)
                if song:
                    extracted_songs.append(song)
                    continue
            
            # Fallback to mapped catalog title, then original PDF title
            title = song_data.get('validated_title') or song_data.get('title', '')
            if title:
                song = self._find_song_by_title(title)
                if song:
                    extracted_songs.append(song)
                else:
                    missing_titles.append(title)
        
        return extracted_songs, missing_titles
    
    def extract_songs_from_extras(self, extras: List[Dict[str, Any]]) -> Tuple[List[Song], List[str]]:
        """
        Extract songs from validated extras.
        
        Args:
            extras: List of extra song data
            
        Returns:
            Tuple of (extracted_songs, missing_titles)
        """
        extracted_songs = []
        missing_titles = []
        
        for song_data in extras:
            if not song_data.get('validated', False):
                missing_titles.append(song_data.get('title', 'Unknown'))
                continue
            
            song_id = song_data.get('song_id')
            if song_id:
                # Try to find by ID first (most reliable)
                song = self._find_song_by_id(song_id)
                if song:
                    extracted_songs.append(song)
                    continue
            
            # Fallback to mapped catalog title, then original PDF title
            title = song_data.get('validated_title') or song_data.get('title', '')
            if title:
                song = self._find_song_by_title(title)
                if song:
                    extracted_songs.append(song)
                else:
                    missing_titles.append(title)
        
        return extracted_songs, missing_titles
    
    def create_sbp_file(self, validated_data: Dict[str, Any], set_name: str = "Extracted Set") -> SBPFile:
        """
        Create a new SBP file from validated data.
        
        Args:
            validated_data: Validated song data
            set_name: Name for the new set
            
        Returns:
            New SBP file with extracted songs
        """
        # Collect all unique songs that will be used in sets
        used_songs = set()
        
        # Process each set to collect used songs
        for set_data in validated_data.get('sets', []):
            set_songs, _ = self.extract_songs_from_set(set_data)
            for song in set_songs:
                used_songs.add(song.id)
        
        # Process extras to collect used songs
        for extra_data in validated_data.get('extras', []):
            if extra_data.get('validated', False):
                song_id = extra_data.get('song_id')
                if song_id:
                    used_songs.add(song_id)
        
        # Create new SBP file with only the songs that are actually used
        used_songs_list = [song for song in self.backup_sbp.songs if song.id in used_songs]
        
        new_sbp = SBPFile(
            version="1.0",
            songs=used_songs_list,  # Only include songs that are actually used
            sets=[],
            folders=self.backup_sbp.folders
        )
        
        # Process each set
        set_id = 1
        pdf_sets = validated_data.get('sets', [])
        has_extras = bool(validated_data.get('extras'))
        total_pdf_sets = len(pdf_sets)

        for set_data in pdf_sets:
            set_songs, missing_titles = self.extract_songs_from_set(set_data)
            
            if set_songs:
                set_label = set_data.get('name', 'Set')
                set_obj = self.sbp_lib.create_set(
                    name=format_sbp_set_name(
                        set_name,
                        set_label,
                        total_pdf_sets=total_pdf_sets,
                        has_extras=has_extras,
                    ),
                    songs=[],
                    id=set_id
                )
                
                # Add songs to set
                for i, song in enumerate(set_songs):
                    item = SetItem(
                        id=i,
                        order=i,
                        capo=0,
                        set_id=set_id,
                        song_id=song.id,
                        key_offset=0,
                        modified_datetime=datetime.now().isoformat() + 'Z',
                        deleted=False,
                        sync_id=None,
                        notes_text=None,
                        section_order="",
                        item_type=1,
                        content=""
                    )
                    set_obj.items.append(item)
                
                new_sbp.sets.append(set_obj)
                set_id += 1
        
        # Process extras as a separate set
        extras = validated_data.get('extras', [])
        if extras:
            extra_songs, missing_extras = self.extract_songs_from_extras(extras)
            
            if extra_songs:
                extras_set = self.sbp_lib.create_set(
                    name=format_sbp_set_name(
                        set_name,
                        "Extras",
                        total_pdf_sets=total_pdf_sets,
                        has_extras=True,
                    ),
                    songs=[],
                    id=set_id
                )
                
                # Add extra songs to set
                for i, song in enumerate(extra_songs):
                    item = SetItem(
                        id=i,
                        order=i,
                        capo=0,
                        set_id=set_id,
                        song_id=song.id,
                        key_offset=0,
                        modified_datetime=datetime.now().isoformat() + 'Z',
                        deleted=False,
                        sync_id=None,
                        notes_text=None,
                        section_order="",
                        item_type=1,
                        content=""
                    )
                    extras_set.items.append(item)
                
                new_sbp.sets.append(extras_set)
        
        return new_sbp
    
    def extract_and_save(self, input_data: Dict[str, Any], output_path: Path, set_name: str = "Extracted Set") -> Dict[str, Any]:
        """
        Extract songs and save to SBP file.
        
        Args:
            input_data: Validated song data
            output_path: Path to save the SBP file
            set_name: Name for the new set
            
        Returns:
            Dictionary with extraction results and statistics
        """
        try:
            # Create SBP file
            new_sbp = self.create_sbp_file(input_data, set_name)
            
            # Save SBP file
            self.sbp_lib.save_sbp_file(new_sbp, output_path)
            
            # Calculate statistics
            total_songs = 0
            extracted_songs = 0
            missing_songs = 0
            
            # Count songs in sets
            for set_data in input_data.get('sets', []):
                songs = set_data.get('songs', [])
                total_songs += len(songs)
                for song in songs:
                    if song.get('validated', False):
                        extracted_songs += 1
                    else:
                        missing_songs += 1
            
            # Count extras
            extras = input_data.get('extras', [])
            total_songs += len(extras)
            for song in extras:
                if song.get('validated', False):
                    extracted_songs += 1
                else:
                    missing_songs += 1
            
            # Get file size
            file_size = output_path.stat().st_size if output_path.exists() else 0
            
            return {
                'success': True,
                'output_path': str(output_path),
                'file_size': file_size,
                'statistics': {
                    'total_songs': total_songs,
                    'extracted_songs': extracted_songs,
                    'missing_songs': missing_songs,
                    'sets_created': len(new_sbp.sets),
                    'songs_in_backup': len(self.backup_sbp.songs)
                },
                'sets': [
                    {
                        'name': set_obj.name,
                        'song_count': len(set_obj.items)
                    }
                    for set_obj in new_sbp.sets
                ]
            }
            
        except Exception as e:
            raise SongExtractionError(f"Error creating SBP file: {e}")
    
    def get_summary(self, result: Dict[str, Any]) -> str:
        """
        Get a summary of the extraction results.
        
        Args:
            result: Extraction result dictionary
            
        Returns:
            Summary string
        """
        if not result.get('success', False):
            return "Extraction failed"
        
        stats = result['statistics']
        summary_parts = []
        
        summary_parts.append(f"✅ SBP file created: {result['output_path']}")
        summary_parts.append(f"📊 File size: {result['file_size']:,} bytes")
        summary_parts.append(f"🎵 Total songs: {stats['total_songs']}")
        summary_parts.append(f"✅ Extracted: {stats['extracted_songs']}")
        summary_parts.append(f"❌ Missing: {stats['missing_songs']}")
        summary_parts.append(f"📁 Sets created: {stats['sets_created']}")
        
        if result.get('sets'):
            summary_parts.append("\nSets created:")
            for set_info in result['sets']:
                summary_parts.append(f"  - {set_info['name']}: {set_info['song_count']} songs")
        
        return "\n".join(summary_parts)

# Convenience function for simple usage
def extract_songs_from_json(input_data: Dict[str, Any], user_id: str, backup_path: Path, output_path: Path, set_name: str = "Extracted Set") -> Dict[str, Any]:
    """
    Convenience function to extract songs from JSON data.
    
    Args:
        input_data: Validated song data
        user_id: User's email address/account ID
        backup_path: Path to user's SBP backup file
        output_path: Path to save the SBP file
        set_name: Name for the new set
        
    Returns:
        Dictionary with extraction results
        
    Raises:
        SongExtractionError: If extraction fails
    """
    extractor = SongExtractor(user_id, backup_path)
    return extractor.extract_and_save(input_data, output_path, set_name)