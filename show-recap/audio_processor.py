#!/usr/bin/env python3
"""
Audio Processor - Split and export audio segments as MP3.

Handles:
- Extracting segments from audio files
- Converting to stereo MP3
- Adding ID3 metadata
- Normalizing audio levels
"""

import subprocess
import json
from pathlib import Path
from typing import Dict, Optional, List


class AudioProcessor:
    """
    Process audio files - split, convert, and export.
    
    Uses ffmpeg for all audio processing operations.
    """
    
    def __init__(
        self,
        output_format: str = "mp3",
        bitrate: str = "192k",
        sample_rate: int = 44100,
        normalize: bool = True,
    ):
        """
        Initialize the processor.
        
        Args:
            output_format: Output audio format (mp3, wav, etc.)
            bitrate: Output bitrate for MP3
            sample_rate: Output sample rate
            normalize: Whether to normalize audio levels
        """
        self.output_format = output_format
        self.bitrate = bitrate
        self.sample_rate = sample_rate
        self.normalize = normalize
    
    def get_audio_info(self, audio_path: str) -> Dict:
        """Get information about an audio file."""
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-show_format",
            "-show_streams",
            "-of", "json",
            audio_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffprobe failed: {result.stderr}")
        
        return json.loads(result.stdout)
    
    def export_segment(
        self,
        input_path: str,
        output_path: str,
        start_time: float,
        end_time: float,
        metadata: Optional[Dict[str, str]] = None,
        fade_in: float = 0.5,
        fade_out: float = 2.0,
    ):
        """
        Export a segment of audio to MP3.
        
        Args:
            input_path: Source audio file
            output_path: Destination MP3 file
            start_time: Start time in seconds
            end_time: End time in seconds
            metadata: ID3 metadata (title, artist, album, etc.)
            fade_in: Fade in duration in seconds
            fade_out: Fade out duration in seconds
        """
        duration = end_time - start_time
        
        # Build filter chain
        filters = []
        
        # Add fade in/out
        if fade_in > 0:
            filters.append(f"afade=t=in:st=0:d={fade_in}")
        if fade_out > 0:
            fade_start = duration - fade_out
            filters.append(f"afade=t=out:st={fade_start}:d={fade_out}")
        
        # Normalize audio if requested
        if self.normalize:
            filters.append("loudnorm=I=-16:TP=-1.5:LRA=11")
        
        filter_str = ",".join(filters) if filters else None
        
        # Build ffmpeg command
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output
            "-i", input_path,
            "-ss", str(start_time),
            "-t", str(duration),
        ]
        
        # Add filter if any
        if filter_str:
            cmd.extend(["-af", filter_str])
        
        # Add output settings
        cmd.extend([
            "-ac", "2",  # Stereo output
            "-ar", str(self.sample_rate),
            "-b:a", self.bitrate,
            "-map_metadata", "-1",  # Strip existing metadata
        ])
        
        # Add metadata
        if metadata:
            for key, value in metadata.items():
                cmd.extend(["-metadata", f"{key}={value}"])
        
        cmd.append(output_path)
        
        print(f"[PROCESSOR] Exporting: {start_time:.1f}s to {end_time:.1f}s -> {output_path}")
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr}")
        
        print(f"[PROCESSOR] Created: {output_path}")
        return output_path
    
    def mix_multitrack(
        self,
        input_files: List[str],
        output_path: str,
        channel_gains: Optional[Dict[int, float]] = None,
    ):
        """
        Mix multiple audio files into a stereo output.
        
        Useful for combining individual channel recordings from
        a multitrack recorder into a stereo mix.
        
        Args:
            input_files: List of input audio files (one per channel)
            output_path: Destination audio file
            channel_gains: Optional gain adjustments per channel (in dB)
        """
        if not input_files:
            raise ValueError("No input files provided")
        
        # Build ffmpeg command for mixing
        cmd = ["ffmpeg", "-y"]
        
        # Add all input files
        for f in input_files:
            cmd.extend(["-i", f])
        
        # Build amix filter
        n = len(input_files)
        
        # If channel gains provided, apply them
        if channel_gains:
            # Create filter for each input with volume adjustment
            filter_parts = []
            for i, f in enumerate(input_files):
                gain = channel_gains.get(i, 0)
                if gain != 0:
                    filter_parts.append(f"[{i}:a]volume={gain}dB[a{i}]")
                else:
                    filter_parts.append(f"[{i}:a]anull[a{i}]")
            
            # Mix all adjusted inputs
            input_labels = "".join(f"[a{i}]" for i in range(n))
            filter_parts.append(f"{input_labels}amix=inputs={n}:duration=longest[aout]")
            
            filter_str = ";".join(filter_parts)
            cmd.extend(["-filter_complex", filter_str, "-map", "[aout]"])
        else:
            # Simple mix without gain adjustment
            filter_str = f"amix=inputs={n}:duration=longest"
            cmd.extend(["-filter_complex", filter_str])
        
        # Output settings
        cmd.extend([
            "-ac", "2",
            "-ar", str(self.sample_rate),
            "-b:a", self.bitrate,
            output_path
        ])
        
        print(f"[PROCESSOR] Mixing {n} tracks -> {output_path}")
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg mix failed: {result.stderr}")
        
        return output_path
    
    def create_preview(
        self,
        input_path: str,
        output_path: str,
        start_time: float = 0,
        duration: float = 30,
    ):
        """
        Create a short preview clip of an audio file.
        
        Args:
            input_path: Source audio file
            output_path: Destination preview file
            start_time: Start time for preview
            duration: Duration of preview in seconds
        """
        cmd = [
            "ffmpeg",
            "-y",
            "-i", input_path,
            "-ss", str(start_time),
            "-t", str(duration),
            "-ac", "2",
            "-ar", "44100",
            "-b:a", "128k",
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg preview failed: {result.stderr}")
        
        return output_path


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 5:
        print("Usage: python audio_processor.py <input> <output> <start_time> <end_time>")
        sys.exit(1)
    
    processor = AudioProcessor()
    processor.export_segment(
        sys.argv[1],
        sys.argv[2],
        float(sys.argv[3]),
        float(sys.argv[4]),
        metadata={"title": "Test Export"}
    )
