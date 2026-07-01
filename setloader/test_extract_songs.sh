#!/bin/bash
# Test harness for extract_songs.py

set -e

echo "🧪 Testing Song Extractor CLI"
echo "================================"

# Check dependencies
echo "📋 Checking dependencies..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found"
    exit 1
fi

if ! python3 -c "import sbp_library" 2>/dev/null; then
    echo "❌ sbp_library not found"
    exit 1
fi

if ! python3 -c "import song_extraction_library" 2>/dev/null; then
    echo "❌ song_extraction_library not found"
    exit 1
fi

echo "✅ Dependencies OK"

# Create test directory
TEST_DIR="test_extract_songs_$(date +%s)"
mkdir -p "$TEST_DIR"
cd "$TEST_DIR"

echo "📁 Created test directory: $TEST_DIR"

# Create test SBP backup
echo "🔧 Creating test SBP backup..."
PYTHONPATH="/usr/local/src/setloader:$PYTHONPATH" python3 -c "
from sbp_library import SBPLibrary, SBPFile, Song, Set, SetItem
from datetime import datetime

# Create test songs
songs = [
    Song(id=1, name='Test Song 1', author='Test Artist', key=1, content='Test content 1'),
    Song(id=2, name='Test Song 2', author='Test Artist', key=2, content='Test content 2'),
    Song(id=3, name='Test Song 3', author='Test Artist', key=3, content='Test content 3'),
    Song(id=4, name='Another Song', author='Another Artist', key=4, content='Another content'),
    Song(id=5, name='Final Song', author='Final Artist', key=5, content='Final content')
]

# Create test sets
sets = [
    Set(id=1, name='Test Set 1', date='2025-10-16', items=[
        SetItem(id=1, order=1, capo=0, set_id=1, song_id=1, key_offset=0, 
                modified_datetime=datetime.now().isoformat() + 'Z', deleted=False, 
                sync_id=None, notes_text=None, section_order='', item_type=1, content=''),
        SetItem(id=2, order=2, capo=0, set_id=1, song_id=2, key_offset=0, 
                modified_datetime=datetime.now().isoformat() + 'Z', deleted=False, 
                sync_id=None, notes_text=None, section_order='', item_type=1, content='')
    ])
]

# Create SBP file
sbp_file = SBPFile(version='1.0', songs=songs, sets=sets, folders=[])

# Save backup
sbp_lib = SBPLibrary()
sbp_lib.save_sbp_file(sbp_file, 'test_backup.sbpbackup')
print('✅ Test backup created')
"

# Create test validated JSON
echo "📝 Creating test validated JSON..."
cat > test_validated.json << 'EOF'
{
  "sets": [
    {
      "name": "Set 1",
      "time_window": "7-8:30",
      "break_minutes": 20,
      "songs": [
        {
          "order": 1,
          "title": "Test Song 1",
          "validated": true,
          "status": "Found in backup",
          "song_id": 1,
          "validated_title": "Test Song 1",
          "key": "A"
        },
        {
          "order": 2,
          "title": "Test Song 2",
          "validated": true,
          "status": "Found in backup",
          "song_id": 2,
          "validated_title": "Test Song 2",
          "key": "B"
        },
        {
          "order": 3,
          "title": "Missing Song",
          "validated": false,
          "status": "Not found in backup or mappings",
          "song_id": null,
          "validated_title": "Missing Song",
          "key": ""
        }
      ],
      "validated_count": 2,
      "missing_count": 1
    }
  ],
  "extras": [
    {
      "order": 1,
      "title": "Another Song",
      "validated": true,
      "status": "Found in backup",
      "song_id": 4,
      "validated_title": "Another Song"
    },
    {
      "order": 2,
      "title": "Final Song",
      "validated": true,
      "status": "Found in backup",
      "song_id": 5,
      "validated_title": "Final Song"
    }
  ],
  "counts": {
    "per_set": {
      "Set 1": {
        "total": 3,
        "validated": 2,
        "missing": 1
      }
    },
    "extras": {
      "total": 2,
      "validated": 2,
      "missing": 0
    },
    "total": 5,
    "validated_total": 4,
    "missing_total": 1
  },
  "errors": [],
  "validation_info": {
    "user_id": "test_user@example.com",
    "backup_path": "test_backup.sbpbackup",
    "mappings_path": null,
    "validated_at": "2025-10-16T23:50:49.427150",
    "total_songs_in_backup": 5,
    "total_mappings": 0
  }
}
EOF

echo "✅ Test validated JSON created"

# Test 1: Basic extraction
echo ""
echo "🧪 Test 1: Basic song extraction"
echo "--------------------------------"
PYTHONPATH="/usr/local/src/setloader:$PYTHONPATH" python3 ../extract_songs.py \
    --input test_validated.json \
    --user-id test_user@example.com \
    --backup test_backup.sbpbackup \
    --output test_output.sbp \
    --set-name "Test Set" \
    --verbose

if [ -f "test_output.sbp" ]; then
    echo "✅ Test 1 passed: SBP file created"
    echo "📊 File size: $(stat -f%z test_output.sbp) bytes"
else
    echo "❌ Test 1 failed: SBP file not created"
    exit 1
fi

# Test 2: Auto-detect backup
echo ""
echo "🧪 Test 2: Auto-detect backup"
echo "-----------------------------"
# Create user directory structure for auto-detection
mkdir -p /usr/local/src/setloader/user_data/test_user@example.com
cp test_backup.sbpbackup /usr/local/src/setloader/user_data/test_user@example.com/backup_20251016_test.sbpbackup

PYTHONPATH="/usr/local/src/setloader:$PYTHONPATH" python3 ../extract_songs.py \
    --input test_validated.json \
    --user-id test_user@example.com \
    --output test_output_auto.sbp \
    --set-name "Auto Test Set" \
    --verbose

if [ -f "test_output_auto.sbp" ]; then
    echo "✅ Test 2 passed: Auto-detection worked"
    echo "📊 File size: $(stat -f%z test_output_auto.sbp) bytes"
else
    echo "❌ Test 2 failed: Auto-detection failed"
    exit 1
fi

# Test 3: Validate SBP file
echo ""
echo "🧪 Test 3: Validate SBP file content"
echo "------------------------------------"
PYTHONPATH="/usr/local/src/setloader:$PYTHONPATH" python3 -c "
from sbp_library import SBPLibrary

# Load the created SBP file
sbp_lib = SBPLibrary()
sbp_file = sbp_lib.load_sbp_file('test_output.sbp')

print(f'✅ SBP file loaded successfully')
print(f'📊 Version: {sbp_file.version}')
print(f'🎵 Total songs: {len(sbp_file.songs)}')
print(f'📁 Total sets: {len(sbp_file.sets)}')

for i, set_obj in enumerate(sbp_file.sets):
    print(f'  Set {i+1}: {set_obj.name} ({len(set_obj.items)} songs)')
    for j, item in enumerate(set_obj.items):
        song = next((s for s in sbp_file.songs if s.id == item.song_id), None)
        if song:
            print(f'    {j+1}. {song.name} (ID: {song.id})')
        else:
            print(f'    {j+1}. Song ID {item.song_id} (not found)')

print('✅ SBP file validation passed')
"

# Test 4: Error handling
echo ""
echo "🧪 Test 4: Error handling"
echo "-------------------------"
echo "Testing missing input file..."
if PYTHONPATH="/usr/local/src/setloader:$PYTHONPATH" python3 ../extract_songs.py --input missing.json --user-id test@example.com --output test.sbp 2>/dev/null; then
    echo "❌ Test 4 failed: Should have failed with missing input"
    exit 1
else
    echo "✅ Test 4 passed: Correctly handled missing input"
fi

echo "Testing missing backup file..."
if PYTHONPATH="/usr/local/src/setloader:$PYTHONPATH" python3 ../extract_songs.py --input test_validated.json --user-id test@example.com --backup missing.sbpbackup --output test.sbp 2>/dev/null; then
    echo "❌ Test 4 failed: Should have failed with missing backup"
    exit 1
else
    echo "✅ Test 4 passed: Correctly handled missing backup"
fi

# Test 5: Malformed JSON
echo ""
echo "🧪 Test 5: Malformed JSON handling"
echo "----------------------------------"
cat > malformed.json << 'EOF'
{
  "sets": [
    {
      "name": "Set 1",
      "songs": [
        {
          "title": "Test Song 1",
          "validated": true,
          "song_id": 1
        }
      ]
    }
  ],
  "extras": []
}
EOF

PYTHONPATH="/usr/local/src/setloader:$PYTHONPATH" python3 ../extract_songs.py \
    --input malformed.json \
    --user-id test_user@example.com \
    --backup test_backup.sbpbackup \
    --output test_malformed.sbp \
    --verbose

if [ -f "test_malformed.sbp" ]; then
    echo "✅ Test 5 passed: Handled malformed JSON gracefully"
else
    echo "❌ Test 5 failed: Could not handle malformed JSON"
    exit 1
fi

# Cleanup
echo ""
echo "🧹 Cleaning up..."
cd ..
rm -rf "$TEST_DIR"
rm -rf /usr/local/src/setloader/user_data/test_user@example.com

echo ""
echo "🎉 All tests passed!"
echo "==================="
echo "✅ Basic extraction"
echo "✅ Auto-detect backup"
echo "✅ SBP file validation"
echo "✅ Error handling"
echo "✅ Malformed JSON handling"
echo ""
echo "🚀 Song extractor CLI is working correctly!"
