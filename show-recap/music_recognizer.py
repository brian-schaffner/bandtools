#!/usr/bin/env python3
"""
Music Recognizer - Detect commercial/studio music using ACRCloud.

Uses audio fingerprinting to identify known songs, helping distinguish
between pre-recorded break music and live performances.
"""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

try:
    from acrcloud.recognizer import ACRCloudRecognizer
    ACRCLOUD_AVAILABLE = True
except ImportError:
    ACRCLOUD_AVAILABLE = False


class MusicRecognizer:
    """
    Recognize commercial music using ACRCloud fingerprinting.
    
    If a segment matches a known song in ACRCloud's database,
    it's likely studio-recorded break music, not live performance.
    """
    
    def __init__(
        self,
        access_key: str = None,
        access_secret: str = None,
        host: str = "identify-us-west-2.acrcloud.com",
    ):
        """
        Initialize the recognizer.
        
        Args:
            access_key: ACRCloud access key (or set ACRCLOUD_KEY env var)
            access_secret: ACRCloud access secret (or set ACRCLOUD_SECRET env var)
            host: ACRCloud API host
        """
        self.access_key = access_key or os.environ.get("ACRCLOUD_KEY")
        self.access_secret = access_secret or os.environ.get("ACRCLOUD_SECRET")
        self.host = host
        
        if not ACRCLOUD_AVAILABLE:
            print("[RECOGNIZER] Warning: pyacrcloud not installed. Install with: pip install pyacrcloud")
            self.recognizer = None
        elif not self.access_key or not self.access_secret:
            print("[RECOGNIZER] Warning: ACRCloud credentials not configured")
            self.recognizer = None
        else:
            config = {
                'host': self.host,
                'access_key': self.access_key,
                'access_secret': self.access_secret,
                'timeout': 10,
            }
            self.recognizer = ACRCloudRecognizer(config)
            print(f"[RECOGNIZER] ACRCloud initialized (host: {self.host})")
    
    @property
    def available(self) -> bool:
        """Check if recognition is available."""
        return self.recognizer is not None
    
    def extract_sample(
        self,
        audio_path: str,
        start_time: float,
        duration: float = 15.0,
    ) -> Optional[str]:
        """
        Extract a sample from the audio file for recognition.
        
        Args:
            audio_path: Source audio file
            start_time: Start time in seconds
            duration: Sample duration (default 15s, ACRCloud recommends 10-20s)
            
        Returns:
            Path to temporary sample file, or None on failure
        """
        temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        temp_path = temp_file.name
        temp_file.close()
        
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start_time),
            "-i", audio_path,
            "-t", str(duration),
            "-ac", "1",  # Mono
            "-ar", "8000",  # 8kHz sample rate (sufficient for fingerprinting)
            temp_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[RECOGNIZER] Failed to extract sample: {result.stderr}")
            return None
        
        return temp_path
    
    def recognize_sample(self, sample_path: str) -> Dict[str, Any]:
        """
        Send a sample to ACRCloud for recognition.
        
        Args:
            sample_path: Path to audio sample file
            
        Returns:
            Recognition result dict with 'matched', 'title', 'artist', etc.
        """
        if not self.available:
            return {'matched': False, 'error': 'ACRCloud not configured'}
        
        import json
        result_str = self.recognizer.recognize_by_file(sample_path, 0)
        result = json.loads(result_str)
        
        status = result.get('status', {})
        if status.get('code') != 0:
            return {
                'matched': False,
                'error': status.get('msg', 'Unknown error'),
            }
        
        metadata = result.get('metadata', {})
        music = metadata.get('music', [])
        
        if not music:
            return {'matched': False}
        
        track = music[0]
        return {
            'matched': True,
            'title': track.get('title', 'Unknown'),
            'artist': ', '.join(a.get('name', '') for a in track.get('artists', [])),
            'album': track.get('album', {}).get('name', ''),
            'score': track.get('score', 0),
        }
    
    def check_segment(
        self,
        audio_path: str,
        start_time: float,
        sample_duration: float = 15.0,
    ) -> Dict[str, Any]:
        """
        Check if a segment contains commercial/studio music.
        
        Args:
            audio_path: Source audio file
            start_time: Position to check
            sample_duration: How much audio to sample
            
        Returns:
            Recognition result
        """
        sample_path = self.extract_sample(audio_path, start_time, sample_duration)
        if not sample_path:
            return {'matched': False, 'error': 'Failed to extract sample'}
        
        try:
            result = self.recognize_sample(sample_path)
            return result
        finally:
            # Clean up temp file
            try:
                os.unlink(sample_path)
            except:
                pass
    
    def find_live_music_start(
        self,
        audio_path: str,
        search_start: float,
        max_search_duration: float = 1800.0,  # 30 minutes max
        step_size: float = 30.0,  # Check every 30 seconds
        sample_duration: float = 15.0,
    ) -> Tuple[float, bool]:
        """
        Find where live music starts by scanning for end of commercial music.
        
        Args:
            audio_path: Source audio file
            search_start: Where to start searching (detected set start)
            max_search_duration: Maximum time to search forward
            step_size: How far to jump between checks
            sample_duration: Duration of each sample to check
            
        Returns:
            Tuple of (live_start_time, was_commercial_detected)
        """
        if not self.available:
            return (search_start, False)
        
        print(f"[RECOGNIZER] Scanning for live music start from {search_start:.0f}s...")
        
        current_pos = search_start
        end_pos = search_start + max_search_duration
        commercial_detected = False
        last_commercial_end = search_start
        
        while current_pos < end_pos:
            result = self.check_segment(audio_path, current_pos, sample_duration)
            
            if result.get('matched'):
                commercial_detected = True
                artist = result.get('artist', 'Unknown')
                title = result.get('title', 'Unknown')
                print(f"    {current_pos:.0f}s: Commercial music - \"{title}\" by {artist}")
                last_commercial_end = current_pos + sample_duration
                current_pos += step_size
            else:
                if commercial_detected:
                    # We were in commercial music and now we're not
                    print(f"    {current_pos:.0f}s: No match - likely live music")
                    # Back up slightly and return
                    return (current_pos, True)
                else:
                    # Never detected commercial music, assume it's live from the start
                    print(f"    {current_pos:.0f}s: No match - appears to be live")
                    return (search_start, False)
        
        # Searched the full duration, return last known position
        if commercial_detected:
            print(f"[RECOGNIZER] Warning: Commercial music detected for full search duration")
            return (last_commercial_end, True)
        
        return (search_start, False)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python music_recognizer.py <audio_file> <start_time>")
        print("  Checks if the audio at start_time is commercial/studio music")
        sys.exit(1)
    
    recognizer = MusicRecognizer()
    if not recognizer.available:
        print("ACRCloud not configured. Set ACRCLOUD_KEY and ACRCLOUD_SECRET env vars.")
        sys.exit(1)
    
    audio_file = sys.argv[1]
    start_time = float(sys.argv[2])
    
    result = recognizer.check_segment(audio_file, start_time)
    print(f"\nResult: {result}")
