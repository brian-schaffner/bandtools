#!/usr/bin/env python3
"""
Audio Analyzer - Detect silence and set boundaries in audio files.

Uses RMS-based silence detection to find:
1. Dead air before the show starts
2. Breaks between sets
3. End of the show
"""

import subprocess
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass


@dataclass
class SilenceRegion:
    """A detected region of silence."""
    start: float  # seconds
    end: float    # seconds
    duration: float
    
    @property
    def midpoint(self) -> float:
        return (self.start + self.end) / 2


@dataclass
class SetBoundary:
    """A detected set with start and end times."""
    set_number: int
    start_time: float
    end_time: float
    
    @property
    def duration(self) -> float:
        return self.end_time - self.start_time


class AudioAnalyzer:
    """
    Analyze audio files to detect set boundaries based on silence.
    
    The analyzer looks for significant periods of silence (dead air) that
    indicate breaks between sets. It uses ffmpeg's silencedetect filter.
    """
    
    def __init__(
        self,
        silence_threshold_db: float = -40.0,
        min_silence_duration: float = 10.0,
        min_set_duration: float = 300.0,  # 5 minutes
    ):
        """
        Initialize the analyzer.
        
        Args:
            silence_threshold_db: Audio level (in dB) below which is considered silence
            min_silence_duration: Minimum duration (seconds) of silence to detect a break
            min_set_duration: Minimum duration (seconds) for a valid set
        """
        self.silence_threshold_db = silence_threshold_db
        self.min_silence_duration = min_silence_duration
        self.min_set_duration = min_set_duration
    
    def get_duration(self, audio_path: str) -> float:
        """Get the total duration of an audio file in seconds."""
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "json",
            audio_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffprobe failed: {result.stderr}")
        
        data = json.loads(result.stdout)
        return float(data["format"]["duration"])
    
    def detect_silence(self, audio_path: str) -> List[SilenceRegion]:
        """
        Detect silence regions in an audio file.
        
        Uses ffmpeg's silencedetect filter.
        """
        cmd = [
            "ffmpeg",
            "-i", audio_path,
            "-af", f"silencedetect=noise={self.silence_threshold_db}dB:d={self.min_silence_duration}",
            "-f", "null",
            "-"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Parse silence detection output from stderr
        silence_regions = []
        silence_start = None
        
        for line in result.stderr.split('\n'):
            # Look for silence_start and silence_end markers
            if 'silence_start:' in line:
                match = re.search(r'silence_start:\s*([\d.]+)', line)
                if match:
                    silence_start = float(match.group(1))
            
            elif 'silence_end:' in line:
                match = re.search(r'silence_end:\s*([\d.]+)', line)
                if match and silence_start is not None:
                    silence_end = float(match.group(1))
                    duration = silence_end - silence_start
                    silence_regions.append(SilenceRegion(
                        start=silence_start,
                        end=silence_end,
                        duration=duration
                    ))
                    silence_start = None
        
        print(f"[ANALYZER] Found {len(silence_regions)} silence regions")
        for region in silence_regions:
            print(f"  - {region.start:.1f}s to {region.end:.1f}s ({region.duration:.1f}s)")
        
        return silence_regions
    
    def find_set_boundaries(
        self,
        silence_regions: List[SilenceRegion],
        total_duration: float
    ) -> List[SetBoundary]:
        """
        Find set boundaries based on detected silence regions.
        
        Logic:
        1. First significant silence after audio starts = end of pre-show / start of set 1
        2. Each subsequent significant silence = break between sets
        3. Last significant silence before end = end of last set
        """
        if not silence_regions:
            # No silence detected - treat entire recording as one set
            return [SetBoundary(set_number=1, start_time=0, end_time=total_duration)]
        
        sets = []
        set_number = 1
        
        # Find where actual audio starts (skip initial silence/dead air)
        # Look for first silence region - the START of it is where pre-show silence ends
        # and the END of it is where we should actually start looking
        
        # Sort silence regions by start time
        silence_regions = sorted(silence_regions, key=lambda x: x.start)
        
        # Determine the start of actual show content
        # If there's silence at the very beginning, skip it
        if silence_regions[0].start < 60:  # Silence starts within first minute
            # Pre-show silence - show starts after this silence ends
            show_start = silence_regions[0].end
            break_silences = silence_regions[1:]  # Remaining silences are potential breaks
        else:
            # No pre-show silence, show starts at beginning
            show_start = 0
            break_silences = silence_regions
        
        # Determine the end of the show
        # If there's silence at the very end, the show ends before it
        if break_silences and (total_duration - break_silences[-1].end) < 60:
            # Post-show silence
            show_end = break_silences[-1].start
            break_silences = break_silences[:-1]
        else:
            show_end = total_duration
        
        # Now break_silences contains only the breaks between sets
        # Each break defines where one set ends and the next begins
        
        current_start = show_start
        
        for silence in break_silences:
            # The set ends at the start of the silence
            set_end = silence.start
            
            # Check if this would be a valid set (meets minimum duration)
            if (set_end - current_start) >= self.min_set_duration:
                sets.append(SetBoundary(
                    set_number=set_number,
                    start_time=current_start,
                    end_time=set_end
                ))
                set_number += 1
                # Next set starts at the end of this silence
                current_start = silence.end
        
        # Add the final set
        if (show_end - current_start) >= self.min_set_duration:
            sets.append(SetBoundary(
                set_number=set_number,
                start_time=current_start,
                end_time=show_end
            ))
        elif sets:
            # Final segment too short - extend the last set to include it
            sets[-1] = SetBoundary(
                set_number=sets[-1].set_number,
                start_time=sets[-1].start_time,
                end_time=show_end
            )
        else:
            # No valid sets found - treat as one set
            sets.append(SetBoundary(
                set_number=1,
                start_time=show_start,
                end_time=show_end
            ))
        
        return sets
    
    def analyze(self, audio_path: str) -> Dict[str, Any]:
        """
        Analyze an audio file and return set boundaries.
        
        Returns:
            Dictionary with analysis results including detected sets.
        """
        print(f"[ANALYZER] Analyzing: {audio_path}")
        
        # Get total duration
        total_duration = self.get_duration(audio_path)
        print(f"[ANALYZER] Total duration: {total_duration:.1f}s ({total_duration/60:.1f} minutes)")
        
        # Detect silence regions
        silence_regions = self.detect_silence(audio_path)
        
        # Find set boundaries
        sets = self.find_set_boundaries(silence_regions, total_duration)
        
        print(f"[ANALYZER] Detected {len(sets)} sets:")
        for s in sets:
            print(f"  - Set {s.set_number}: {s.start_time:.1f}s to {s.end_time:.1f}s ({s.duration/60:.1f} minutes)")
        
        return {
            "total_duration": total_duration,
            "silence_threshold_db": self.silence_threshold_db,
            "min_silence_duration": self.min_silence_duration,
            "silence_regions": [
                {"start": r.start, "end": r.end, "duration": r.duration}
                for r in silence_regions
            ],
            "sets": [
                {
                    "set_number": s.set_number,
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "duration": s.duration
                }
                for s in sets
            ]
        }


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python audio_analyzer.py <audio_file>")
        sys.exit(1)
    
    analyzer = AudioAnalyzer()
    result = analyzer.analyze(sys.argv[1])
    print("\n" + json.dumps(result, indent=2))
