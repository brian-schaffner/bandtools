#!/bin/bash
# Test script for Show Recap - The Dock Sep 6 2026
# Processes tracks 17 and 18 (likely the stereo main mix)

RECORDING_DIR="/Volumes/Projects 25/Projects/llb/the dock sep 6 2026"
SHOW_NAME="The Dock Sep 6 2026"
SHOW_DATE="2026-09-06"

# Check if directory exists
if [ ! -d "$RECORDING_DIR" ]; then
    echo "Error: Directory not found: $RECORDING_DIR"
    echo "Make sure the drive is mounted."
    exit 1
fi

# Find track 17 and 18 files
echo "Looking for tracks in: $RECORDING_DIR"
echo ""

# List available tracks
echo "Available audio files:"
ls -la "$RECORDING_DIR"/*.wav 2>/dev/null || ls -la "$RECORDING_DIR"/*.WAV 2>/dev/null || echo "No WAV files found"
echo ""

# Find track 17 and 18 (case insensitive, various naming patterns)
TRACK17=$(find "$RECORDING_DIR" -iname "*track*17*.wav" -o -iname "*tr17*.wav" -o -iname "*17*.wav" 2>/dev/null | head -1)
TRACK18=$(find "$RECORDING_DIR" -iname "*track*18*.wav" -o -iname "*tr18*.wav" -o -iname "*18*.wav" 2>/dev/null | head -1)

if [ -z "$TRACK17" ] && [ -z "$TRACK18" ]; then
    echo "Could not find Track 17 or Track 18 automatically."
    echo ""
    echo "Please specify the file paths manually. Example filenames might be:"
    echo "  - Track 17.wav / Track 18.wav"
    echo "  - Tr17.wav / Tr18.wav"
    echo "  - Ch17.wav / Ch18.wav"
    echo ""
    echo "Run manually with:"
    echo "  cd $(dirname $0)"
    echo "  python cli.py process \"<path-to-track17>\" --name \"$SHOW_NAME\" --date $SHOW_DATE"
    exit 1
fi

echo "Found files:"
[ -n "$TRACK17" ] && echo "  Track 17: $TRACK17"
[ -n "$TRACK18" ] && echo "  Track 18: $TRACK18"
echo ""

# Use track 17 as the main file (or both if mixing needed)
MAIN_FILE="${TRACK17:-$TRACK18}"

echo "Processing with main file: $MAIN_FILE"
echo ""

# Change to script directory
cd "$(dirname "$0")"

# Run the CLI
python cli.py process "$MAIN_FILE" \
    --name "$SHOW_NAME" \
    --date "$SHOW_DATE" \
    --output "$HOME/Desktop/ShowRecap/$SHOW_NAME"

echo ""
echo "Done! Check output at: $HOME/Desktop/ShowRecap/$SHOW_NAME"
