#!/bin/bash
"""
Test harness for validate_titles.py CLI tool.
"""

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_DIR="${SCRIPT_DIR}/test_validation"
RESULTS_DIR="${TEST_DIR}/results"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

echo "🧪 Test Harness for validate_titles.py"
echo "======================================"

# Create test directories
mkdir -p "$TEST_DIR"
mkdir -p "$RESULTS_DIR"

# Test data setup
echo "📁 Setting up test data..."

# Create a sample input JSON file
cat > "$TEST_DIR/sample_input.json" << 'EOF'
{
  "sets": [
    {
      "name": "Set 1",
      "time_window": "7-8:30",
      "break_minutes": 20,
      "songs": [
        {
          "order": 1,
          "title": "Hurt So Good",
          "key": "A"
        },
        {
          "order": 2,
          "title": "Pontoon",
          "key": "A"
        },
        {
          "order": 3,
          "title": "Hot Blooded",
          "key": "G"
        },
        {
          "order": 4,
          "title": "Nonexistent Song",
          "key": "C"
        }
      ]
    },
    {
      "name": "Set 2",
      "time_window": "8:50-10",
      "break_minutes": 15,
      "songs": [
        {
          "order": 1,
          "title": "Free Fallin",
          "key": "F"
        },
        {
          "order": 2,
          "title": "Another Missing Song",
          "key": "Dm"
        }
      ]
    }
  ],
  "extras": [
    {
      "title": "TNT"
    },
    {
      "title": "Unknown Extra Song"
    }
  ],
  "counts": {
    "per_set": {
      "Set 1": 4,
      "Set 2": 2
    },
    "extras": 2,
    "total": 8
  },
  "errors": []
}
EOF

# Create sample title mappings
cat > "$TEST_DIR/sample_mappings.json" << 'EOF'
{
  "Nonexistent Song": "Hurt So Good",
  "Another Missing Song": "Pontoon",
  "Unknown Extra Song": "TNT"
}
EOF

echo "✅ Test data created"

# Check dependencies
echo "🔍 Checking dependencies..."

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python3 not found${NC}"
    exit 1
fi

# Check if required modules are available
python3 -c "import json, sys, pathlib, sbp_library" 2>/dev/null || {
    echo -e "${RED}❌ Required Python modules not found${NC}"
    echo "Please install required dependencies:"
    echo "  pip install sbp_library"
    exit 1
}

echo "✅ Dependencies check passed"

# Test 1: Basic functionality test
echo ""
echo "🧪 Test 1: Basic functionality test"

# Create a minimal SBP backup for testing
echo "📦 Creating test SBP backup..."
python3 -c "
from sbp_library import SBPLibrary, SBPFile, Song
import json

# Create a simple SBP file with test songs
songs = [
    Song(id=1, name='Hurt So Good', author='John Mellencamp', key=0),
    Song(id=2, name='Pontoon', author='Little Big Town', key=0),
    Song(id=3, name='Hot Blooded', author='Foreigner', key=0),
    Song(id=4, name='Free Fallin', author='Tom Petty', key=0),
    Song(id=5, name='TNT', author='AC/DC', key=0)
]

sbp_file = SBPFile(version='1.0', songs=songs, sets=[], folders=[])
sbp_lib = SBPLibrary()
sbp_lib.save_sbp_file(sbp_file, '$TEST_DIR/test_backup.sbpbackup')
print('Test backup created with', len(songs), 'songs')
"

# Run the validation
echo "🔄 Running validation..."
python3 validate_titles.py \
    --input "$TEST_DIR/sample_input.json" \
    --output "$RESULTS_DIR/validation_result.json" \
    --user-id "test@example.com" \
    --backup "$TEST_DIR/test_backup.sbpbackup" \
    --mappings "$TEST_DIR/sample_mappings.json" \
    --verbose

# Check results
if [ -f "$RESULTS_DIR/validation_result.json" ]; then
    echo -e "${GREEN}✅ Validation completed successfully${NC}"
    
    # Display results summary
    echo "📊 Results summary:"
    python3 -c "
import json
with open('$RESULTS_DIR/validation_result.json', 'r') as f:
    data = json.load(f)
    
counts = data['counts']
print(f'  Total songs: {counts[\"total\"]}')
print(f'  Validated: {counts[\"validated_total\"]}')
print(f'  Missing: {counts[\"missing_total\"]}')

for set_name, set_counts in counts['per_set'].items():
    print(f'  {set_name}: {set_counts[\"validated\"]}/{set_counts[\"total\"]} validated')

if counts['extras']['total'] > 0:
    print(f'  Extras: {counts[\"extras\"][\"validated\"]}/{counts[\"extras\"][\"total\"]} validated')
"
else
    echo -e "${RED}❌ Validation failed - no output file created${NC}"
    exit 1
fi

# Test 2: Test without mappings
echo ""
echo "🧪 Test 2: Test without mappings"

python3 validate_titles.py \
    --input "$TEST_DIR/sample_input.json" \
    --output "$RESULTS_DIR/validation_no_mappings.json" \
    --user-id "test@example.com" \
    --backup "$TEST_DIR/test_backup.sbpbackup" \
    --verbose

if [ -f "$RESULTS_DIR/validation_no_mappings.json" ]; then
    echo -e "${GREEN}✅ Validation without mappings completed${NC}"
else
    echo -e "${RED}❌ Validation without mappings failed${NC}"
    exit 1
fi

# Test 3: Test with missing backup
echo ""
echo "🧪 Test 3: Test with missing backup (should fail)"

python3 validate_titles.py \
    --input "$TEST_DIR/sample_input.json" \
    --output "$RESULTS_DIR/validation_missing_backup.json" \
    --user-id "test@example.com" \
    --backup "$TEST_DIR/nonexistent_backup.sbpbackup" \
    --verbose 2>/dev/null && {
    echo -e "${RED}❌ Test should have failed with missing backup${NC}"
    exit 1
} || {
    echo -e "${GREEN}✅ Correctly failed with missing backup${NC}"
}

# Test 4: Test with malformed input
echo ""
echo "🧪 Test 4: Test with malformed input (should fail)"

echo '{"invalid": "json"' > "$TEST_DIR/malformed_input.json"

python3 validate_titles.py \
    --input "$TEST_DIR/malformed_input.json" \
    --output "$RESULTS_DIR/validation_malformed.json" \
    --user-id "test@example.com" \
    --backup "$TEST_DIR/test_backup.sbpbackup" \
    --verbose 2>/dev/null && {
    echo -e "${RED}❌ Test should have failed with malformed input${NC}"
    exit 1
} || {
    echo -e "${GREEN}✅ Correctly handled malformed input${NC}"
}

# Generate test report
echo ""
echo "📋 Generating test report..."

cat > "$RESULTS_DIR/test_report_${TIMESTAMP}.md" << EOF
# Test Report for validate_titles.py

**Date:** $(date)
**Test Harness Version:** 1.0

## Test Results

### Test 1: Basic Functionality ✅
- **Input:** sample_input.json (8 songs across 2 sets + 2 extras)
- **Backup:** test_backup.sbpbackup (5 songs)
- **Mappings:** sample_mappings.json (3 mappings)
- **Result:** Validation completed successfully

### Test 2: Without Mappings ✅
- **Input:** sample_input.json
- **Backup:** test_backup.sbpbackup
- **Mappings:** None
- **Result:** Validation completed successfully

### Test 3: Missing Backup ✅
- **Input:** sample_input.json
- **Backup:** nonexistent_backup.sbpbackup
- **Result:** Correctly failed as expected

### Test 4: Malformed Input ✅
- **Input:** malformed_input.json
- **Result:** Correctly handled malformed input

## Summary
All tests passed successfully. The validate_titles.py tool is working correctly.

## Files Generated
- validation_result.json: Full validation with mappings
- validation_no_mappings.json: Validation without mappings
- test_report_${TIMESTAMP}.md: This report
EOF

echo -e "${GREEN}✅ Test report generated: $RESULTS_DIR/test_report_${TIMESTAMP}.md${NC}"

# Final summary
echo ""
echo "🎉 Test Harness Complete!"
echo "========================"
echo -e "${GREEN}✅ All tests passed successfully${NC}"
echo ""
echo "Generated files:"
echo "  - $RESULTS_DIR/validation_result.json"
echo "  - $RESULTS_DIR/validation_no_mappings.json"
echo "  - $RESULTS_DIR/test_report_${TIMESTAMP}.md"
echo ""
echo "The validate_titles.py tool is ready for use!"
