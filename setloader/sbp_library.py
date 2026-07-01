#!/usr/bin/env python3
"""
Song Book Pro (.sbp) File Library

A comprehensive, reverse-engineered library for working with Song Book Pro files.
This library provides robust parsing, validation, and manipulation of .sbp files.

Features:
- Parse .sbp files (ZIP archives with specific structure)
- Extract songs, sets, and metadata
- Validate file integrity (MD5 checksums)
- Create new .sbp files
- Convert between formats
- Handle version differences gracefully

Author: AI Assistant
Date: 2025-10-12
"""

import json
import zipfile
import hashlib
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class Song:
    """Represents a single song in the Song Book Pro format."""
    id: int
    name: str
    author: str = ""
    content: str = ""
    capo: int = 0
    key: int = 0
    key_shift: int = 0
    hash: str = ""
    sub_title: str = ""
    song_type: int = 1
    modified_datetime: str = ""
    deleted: bool = False
    sync_id: str = ""
    time_sig: str = ""
    zoom_factor: float = 1.0
    duration: int = 0
    duration2: int = 0
    display_params: str = "{}"
    tempo_int: int = 0
    tags: str = "[]"
    url: str = ""
    deep_search: str = ""
    copyright: str = ""
    notes_text: str = ""
    zoom: float = 1.0
    section_order: str = ""
    song_number: int = 0
    has_children: int = 0
    parent_id: int = 0
    v_name: Optional[str] = None
    locked: int = 0
    linked_audio: Optional[str] = None
    chords: Optional[str] = None
    midi_on_load: Optional[str] = None
    folders: str = "[]"
    drawing_paths_backup: Optional[str] = None

@dataclass
class SetItem:
    """Represents an item in a set list."""
    id: int
    order: int
    capo: int
    set_id: int
    song_id: int
    key_offset: int
    modified_datetime: str = ""
    deleted: bool = False
    sync_id: Optional[str] = None
    notes_text: Optional[str] = None
    section_order: str = ""
    item_type: int = 1
    content: str = ""

@dataclass
class Set:
    """Represents a set list."""
    id: int
    name: str
    date: str
    modified_datetime: str = ""
    deleted: bool = False
    sync_id: Optional[str] = None
    items: List[SetItem] = None
    
    def __post_init__(self):
        if self.items is None:
            self.items = []

@dataclass
class SBPFile:
    """Represents a complete Song Book Pro file."""
    version: str = "1.0"
    songs: List[Song] = None
    sets: List[Set] = None
    folders: List[Dict] = None
    
    def __post_init__(self):
        if self.songs is None:
            self.songs = []
        if self.sets is None:
            self.sets = []
        if self.folders is None:
            self.folders = []

class SBPError(Exception):
    """Base exception for SBP library errors."""
    pass

class SBPParseError(SBPError):
    """Raised when parsing an SBP file fails."""
    pass

class SBPValidationError(SBPError):
    """Raised when SBP file validation fails."""
    pass

class SBPLibrary:
    """Main library class for working with Song Book Pro files."""
    
    def __init__(self):
        self.logger = logger
    
    def load_sbp_file(self, file_path: Union[str, Path]) -> SBPFile:
        """
        Load and parse a .sbp file.
        
        Args:
            file_path: Path to the .sbp file
            
        Returns:
            SBPFile object containing all data
            
        Raises:
            SBPParseError: If the file cannot be parsed
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise SBPParseError(f"File not found: {file_path}")
        
        if not file_path.suffix.lower() in ['.sbp', '.sbpbackup']:
            raise SBPParseError(f"File is not a .sbp or .sbpbackup file: {file_path}")
        
        try:
            with zipfile.ZipFile(file_path, 'r') as zip_file:
                # Check required files
                required_files = ['dataFile.txt']
                missing_files = [f for f in required_files if f not in zip_file.namelist()]
                if missing_files:
                    raise SBPParseError(f"Missing required files: {missing_files}")
                
                # Parse dataFile.txt
                with zip_file.open('dataFile.txt') as f:
                    content = f.read().decode('utf-8')
                
                return self._parse_datafile_content(content)
                
        except zipfile.BadZipFile:
            raise SBPParseError(f"Invalid ZIP file: {file_path}")
        except Exception as e:
            raise SBPParseError(f"Error reading file {file_path}: {e}")
    
    def _parse_datafile_content(self, content: str) -> SBPFile:
        """Parse the content of dataFile.txt."""
        try:
            lines = content.strip().split('\n')
            
            # Handle version line
            version = "1.0"
            if lines and lines[0].strip().replace('.', '').isdigit():
                version = lines[0].strip()
                json_content = '\n'.join(lines[1:])
            else:
                json_content = content
            
            # Parse JSON
            data = json.loads(json_content)
            
            # Extract songs
            songs = []
            if 'songs' in data and isinstance(data['songs'], list):
                for song_data in data['songs']:
                    if isinstance(song_data, dict):
                        song = self._parse_song(song_data)
                        songs.append(song)
            
            # Extract sets
            sets = []
            if 'sets' in data and isinstance(data['sets'], list):
                for set_data in data['sets']:
                    if isinstance(set_data, dict):
                        set_obj = self._parse_set(set_data)
                        sets.append(set_obj)
            
            # Extract folders
            folders = []
            if 'folders' in data and isinstance(data['folders'], list):
                folders = data['folders']
            
            return SBPFile(
                version=version,
                songs=songs,
                sets=sets,
                folders=folders
            )
            
        except json.JSONDecodeError as e:
            raise SBPParseError(f"Invalid JSON in dataFile.txt: {e}")
        except Exception as e:
            raise SBPParseError(f"Error parsing dataFile.txt: {e}")
    
    def _parse_song(self, data: Dict[str, Any]) -> Song:
        """Parse a song from JSON data."""
        return Song(
            id=data.get('Id', 0),
            name=data.get('name', ''),
            author=data.get('author', ''),
            content=data.get('content', ''),
            capo=data.get('Capo', 0),
            key=data.get('key', 0),
            key_shift=data.get('KeyShift', 0),
            hash=data.get('hash', ''),
            sub_title=data.get('subTitle', ''),
            song_type=data.get('type', 1),
            modified_datetime=data.get('ModifiedDateTime', ''),
            deleted=data.get('Deleted', False),
            sync_id=data.get('SyncId', ''),
            time_sig=data.get('timeSig', ''),
            zoom_factor=data.get('ZoomFactor', 1.0),
            duration=data.get('Duration', 0),
            duration2=data.get('Duration2', 0),
            display_params=data.get('_displayParams', '{}'),
            tempo_int=data.get('TempoInt', 0),
            tags=data.get('_tags', '[]'),
            url=data.get('Url', ''),
            deep_search=data.get('DeepSearch', ''),
            copyright=data.get('Copyright', ''),
            notes_text=data.get('NotesText', ''),
            zoom=data.get('Zoom', 1.0),
            section_order=data.get('SectionOrder', ''),
            song_number=data.get('SongNumber', 0),
            has_children=data.get('HasChildren', 0),
            parent_id=data.get('ParentId', 0),
            v_name=data.get('vName'),
            locked=data.get('locked', 0),
            linked_audio=data.get('LinkedAudio'),
            chords=data.get('Chords'),
            midi_on_load=data.get('midiOnLoad'),
            folders=data.get('_folders', '[]'),
            drawing_paths_backup=data.get('drawingPathsBackup')
        )
    
    def _parse_set(self, data: Dict[str, Any]) -> Set:
        """Parse a set from JSON data."""
        details = data.get('details', {})
        contents = data.get('contents', [])
        
        set_obj = Set(
            id=details.get('Id', 0),
            name=details.get('name', ''),
            date=details.get('date', ''),
            modified_datetime=details.get('ModifiedDateTime', ''),
            deleted=details.get('Deleted', False),
            sync_id=details.get('SyncId')
        )
        
        # Parse set items
        for item_data in contents:
            if isinstance(item_data, dict):
                item = SetItem(
                    id=item_data.get('Id', 0),
                    order=item_data.get('Order', 0),
                    capo=item_data.get('Capo', 0),
                    set_id=item_data.get('SetId', 0),
                    song_id=item_data.get('SongId', 0),
                    key_offset=item_data.get('keyOfset', 0),
                    modified_datetime=item_data.get('ModifiedDateTime', ''),
                    deleted=item_data.get('Deleted', False),
                    sync_id=item_data.get('SyncId'),
                    notes_text=item_data.get('NotesText'),
                    section_order=item_data.get('SectionOrder', ''),
                    item_type=item_data.get('ItemType', 1),
                    content=item_data.get('Content', '')
                )
                set_obj.items.append(item)
        
        return set_obj
    
    def save_sbp_file(self, sbp_file: SBPFile, output_path: Union[str, Path]) -> None:
        """
        Save an SBPFile object to a .sbp file.
        
        Args:
            sbp_file: SBPFile object to save
            output_path: Path where to save the file
        """
        output_path = Path(output_path)
        
        # Create temporary directory for file construction
        temp_dir = output_path.parent / f"temp_{output_path.stem}"
        temp_dir.mkdir(exist_ok=True)
        
        try:
            # Create dataFile.txt
            datafile_path = temp_dir / "dataFile.txt"
            self._create_datafile(sbp_file, datafile_path)
            
            # Create dataFile.hash
            hash_path = temp_dir / "dataFile.hash"
            self._create_hash_file(datafile_path, hash_path)
            
            # Create ZIP file
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                zip_file.write(datafile_path, 'dataFile.txt')
                zip_file.write(hash_path, 'dataFile.hash')
            
            self.logger.info(f"Successfully saved SBP file: {output_path}")
            
        finally:
            # Clean up temporary directory
            if temp_dir.exists():
                import shutil
                shutil.rmtree(temp_dir)
    
    def _create_datafile(self, sbp_file: SBPFile, output_path: Path) -> None:
        """Create the dataFile.txt content."""
        # Convert songs to dict format
        songs_data = []
        for song in sbp_file.songs:
            song_dict = asdict(song)
            # Convert field names to match SBP format
            song_dict['Id'] = song_dict.pop('id')
            song_dict['Capo'] = song_dict.pop('capo')
            song_dict['KeyShift'] = song_dict.pop('key_shift')
            song_dict['subTitle'] = song_dict.pop('sub_title')
            song_dict['type'] = song_dict.pop('song_type')
            song_dict['ModifiedDateTime'] = song_dict.pop('modified_datetime')
            song_dict['Deleted'] = song_dict.pop('deleted')  # Keep as boolean for songs
            song_dict['SyncId'] = song_dict.pop('sync_id')
            song_dict['timeSig'] = song_dict.pop('time_sig')
            song_dict['ZoomFactor'] = song_dict.pop('zoom_factor')
            song_dict['_displayParams'] = song_dict.pop('display_params')
            song_dict['TempoInt'] = song_dict.pop('tempo_int')
            song_dict['_tags'] = song_dict.pop('tags')
            song_dict['Url'] = song_dict.pop('url')
            song_dict['DeepSearch'] = song_dict.pop('deep_search')
            song_dict['Copyright'] = song_dict.pop('copyright')
            song_dict['NotesText'] = song_dict.pop('notes_text')
            song_dict['Zoom'] = song_dict.pop('zoom')
            song_dict['SectionOrder'] = song_dict.pop('section_order')
            song_dict['SongNumber'] = song_dict.pop('song_number')
            song_dict['HasChildren'] = song_dict.pop('has_children')
            song_dict['ParentId'] = song_dict.pop('parent_id')
            song_dict['vName'] = song_dict.pop('v_name')
            song_dict['LinkedAudio'] = song_dict.pop('linked_audio')
            song_dict['Chords'] = song_dict.pop('chords')
            song_dict['midiOnLoad'] = song_dict.pop('midi_on_load')
            song_dict['_folders'] = song_dict.pop('folders')
            song_dict['drawingPathsBackup'] = song_dict.pop('drawing_paths_backup')
            songs_data.append(song_dict)
        
        # Convert sets to dict format
        sets_data = []
        for set_obj in sbp_file.sets:
            set_dict = {
                'details': {
                    'Id': set_obj.id,
                    'name': set_obj.name,
                    'date': set_obj.date,
                    'ModifiedDateTime': set_obj.modified_datetime,
                    'Deleted': 1 if set_obj.deleted else 0,
                    'SyncId': set_obj.sync_id
                },
                'contents': []
            }
            
            for item in set_obj.items:
                item_dict = asdict(item)
                item_dict['Id'] = item_dict.pop('id')
                item_dict['Order'] = item_dict.pop('order')
                item_dict['Capo'] = item_dict.pop('capo')
                item_dict['SetId'] = item_dict.pop('set_id')
                item_dict['SongId'] = item_dict.pop('song_id')
                item_dict['keyOfset'] = item_dict.pop('key_offset')
                item_dict['ModifiedDateTime'] = item_dict.pop('modified_datetime')
                item_dict['Deleted'] = 1 if item_dict.pop('deleted') else 0
                item_dict['SyncId'] = item_dict.pop('sync_id')
                item_dict['NotesText'] = item_dict.pop('notes_text')
                item_dict['SectionOrder'] = item_dict.pop('section_order')
                item_dict['ItemType'] = item_dict.pop('item_type')
                item_dict['Content'] = item_dict.pop('content')
                set_dict['contents'].append(item_dict)
            
            sets_data.append(set_dict)
        
        # Create the complete data structure
        data = {
            'songs': songs_data,
            'sets': sets_data,
            'folders': sbp_file.folders
        }
        
        # Write to file with version line (Windows line endings)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"{sbp_file.version}\r\n")
            f.write(json.dumps(data, indent=None, separators=(',', ':')))
    
    def _create_hash_file(self, datafile_path: Path, hash_path: Path) -> None:
        """Create the MD5 hash file."""
        with open(datafile_path, 'rb') as f:
            content = f.read()
        
        md5_hash = hashlib.md5(content).hexdigest()
        
        with open(hash_path, 'w') as f:
            f.write(md5_hash)
    
    def validate_sbp_file(self, file_path: Union[str, Path]) -> Tuple[bool, List[str]]:
        """
        Validate a .sbp file for integrity and structure.
        
        Args:
            file_path: Path to the .sbp file
            
        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []
        
        try:
            with zipfile.ZipFile(file_path, 'r') as zip_file:
                # Check required files
                required_files = ['dataFile.txt']
                missing_files = [f for f in required_files if f not in zip_file.namelist()]
                if missing_files:
                    issues.append(f"Missing required files: {missing_files}")
                
                # Validate dataFile.txt
                if 'dataFile.txt' in zip_file.namelist():
                    with zip_file.open('dataFile.txt') as f:
                        content = f.read().decode('utf-8')
                    
                    # Check for version line
                    lines = content.strip().split('\n')
                    if not lines or not lines[0].strip().replace('.', '').isdigit():
                        issues.append("Missing or invalid version line in dataFile.txt")
                    
                    # Try to parse JSON
                    try:
                        if len(lines) > 1:
                            json_content = '\n'.join(lines[1:])
                        else:
                            json_content = content
                        json.loads(json_content)
                    except json.JSONDecodeError as e:
                        issues.append(f"Invalid JSON in dataFile.txt: {e}")
                
                # Validate hash file
                if 'dataFile.hash' in zip_file.namelist():
                    with zip_file.open('dataFile.hash') as f:
                        hash_content = f.read().decode('utf-8').strip()
                    
                    if len(hash_content) != 32:
                        issues.append("Invalid MD5 hash length in dataFile.hash")
                    elif not all(c in '0123456789abcdef' for c in hash_content.lower()):
                        issues.append("Invalid MD5 hash format in dataFile.hash")
                    
                    # Verify hash matches content
                    if 'dataFile.txt' in zip_file.namelist():
                        with zip_file.open('dataFile.txt') as f:
                            content = f.read()
                        expected_hash = hashlib.md5(content).hexdigest()
                        if hash_content.lower() != expected_hash:
                            issues.append("MD5 hash does not match dataFile.txt content")
        
        except zipfile.BadZipFile:
            issues.append("Invalid ZIP file format")
        except Exception as e:
            issues.append(f"Error validating file: {e}")
        
        return len(issues) == 0, issues
    
    def get_song_count(self, sbp_file: SBPFile) -> int:
        """Get the number of songs in the file."""
        return len(sbp_file.songs)
    
    def get_set_count(self, sbp_file: SBPFile) -> int:
        """Get the number of sets in the file."""
        return len(sbp_file.sets)
    
    def get_songs_by_name(self, sbp_file: SBPFile, name_pattern: str) -> List[Song]:
        """Find songs by name pattern (case-insensitive)."""
        pattern_lower = name_pattern.lower()
        return [song for song in sbp_file.songs 
                if pattern_lower in song.name.lower()]
    
    def get_active_songs(self, sbp_file: SBPFile) -> List[Song]:
        """Get all non-deleted songs."""
        return [song for song in sbp_file.songs if not song.deleted]
    
    def get_songs_with_content(self, sbp_file: SBPFile) -> List[Song]:
        """Get songs that have actual content (not empty)."""
        return [song for song in sbp_file.songs 
                if song.content and song.content.strip()]
    
    def create_song(self, name: str, author: str = "", content: str = "", **kwargs) -> Song:
        """Create a new song with default values."""
        return Song(
            id=kwargs.get('id', 0),
            name=name,
            author=author,
            content=content,
            modified_datetime=datetime.now().isoformat() + 'Z',
            **{k: v for k, v in kwargs.items() if k != 'id'}
        )
    
    def create_set(self, name: str, songs: List[Song] = None, **kwargs) -> Set:
        """Create a new set with songs."""
        set_obj = Set(
            id=kwargs.get('id', 1),
            name=name,
            date=datetime.now().isoformat() + 'Z',
            modified_datetime=datetime.now().isoformat() + 'Z',
            **{k: v for k, v in kwargs.items() if k not in ['id', 'name', 'date']}
        )
        
        if songs:
            for i, song in enumerate(songs):
                item = SetItem(
                    id=i,
                    order=i,
                    set_id=set_obj.id,
                    song_id=song.id,
                    modified_datetime=datetime.now().isoformat() + 'Z'
                )
                set_obj.items.append(item)
        
        return set_obj

# Convenience functions
def load_sbp(file_path: Union[str, Path]) -> SBPFile:
    """Load a .sbp file."""
    library = SBPLibrary()
    return library.load_sbp_file(file_path)

def save_sbp(sbp_file: SBPFile, output_path: Union[str, Path]) -> None:
    """Save an SBPFile to a .sbp file."""
    library = SBPLibrary()
    library.save_sbp_file(sbp_file, output_path)

def validate_sbp(file_path: Union[str, Path]) -> Tuple[bool, List[str]]:
    """Validate a .sbp file."""
    library = SBPLibrary()
    return library.validate_sbp_file(file_path)

# Example usage
if __name__ == "__main__":
    # Example: Load and analyze a .sbp file
    try:
        sbp_file = load_sbp("test_gaslight.sbp")
        print(f"Loaded SBP file with {len(sbp_file.songs)} songs and {len(sbp_file.sets)} sets")
        
        # Get active songs
        active_songs = [song for song in sbp_file.songs if not song.deleted]
        print(f"Active songs: {len(active_songs)}")
        
        # Get songs with content
        content_songs = [song for song in sbp_file.songs if song.content and song.content.strip()]
        print(f"Songs with content: {len(content_songs)}")
        
        # Validate file
        is_valid, issues = validate_sbp("test_gaslight.sbp")
        print(f"File valid: {is_valid}")
        if issues:
            print(f"Issues: {issues}")
            
    except Exception as e:
        print(f"Error: {e}")



