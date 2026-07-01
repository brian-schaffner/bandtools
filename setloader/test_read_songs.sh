#!/bin/bash

# Test harness for read_songs.py CLI tool

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLI_TOOL="$SCRIPT_DIR/read_songs.py"
TEST_DATA_DIR="$SCRIPT_DIR/test_data"
OUTPUT_DIR="$SCRIPT_DIR/test_output"
RESULTS_DIR="$SCRIPT_DIR/test_results"

# Create directories if they don't exist
mkdir -p "$OUTPUT_DIR" "$RESULTS_DIR"

echo -e "${BLUE}🧪 Starting read_songs.py test harness${NC}"
echo "================================================"

# Check if CLI tool exists
if [ ! -f "$CLI_TOOL" ]; then
    echo -e "${RED}❌ Error: CLI tool not found at $CLI_TOOL${NC}"
    exit 1
fi

# Check if test data directory exists
if [ ! -d "$TEST_DATA_DIR" ]; then
    echo -e "${YELLOW}⚠️  Warning: Test data directory not found at $TEST_DATA_DIR${NC}"
    echo "Creating test data directory..."
    mkdir -p "$TEST_DATA_DIR"
    echo -e "${YELLOW}Please add PDF files to $TEST_DATA_DIR and run the test again${NC}"
    exit 1
fi

# Check for required dependencies
echo -e "${BLUE}🔍 Checking dependencies...${NC}"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Error: python3 not found${NC}"
    exit 1
fi

# Check if required Python packages are installed
python3 -c "import openai, PyPDF2, json, argparse" 2>/dev/null || {
    echo -e "${RED}❌ Error: Required Python packages not installed${NC}"
    echo "Please install: pip install openai PyPDF2 python-dotenv"
    exit 1
}

# Check for OpenAI API key
if [ -z "$OPENAI_API_KEY" ]; then
    echo -e "${YELLOW}⚠️  Warning: OPENAI_API_KEY environment variable not set${NC}"
    echo "Please set your OpenAI API key: export OPENAI_API_KEY='your-key-here'"
    echo "Or create a .env file with: OPENAI_API_KEY=your-key-here"
fi

echo -e "${GREEN}✅ Dependencies check passed${NC}"

# Find PDF files in test data directory
PDF_FILES=($(find "$TEST_DATA_DIR" -name "*.pdf" -type f))

if [ ${#PDF_FILES[@]} -eq 0 ]; then
    echo -e "${YELLOW}⚠️  No PDF files found in $TEST_DATA_DIR${NC}"
    echo "Please add PDF files to test and run again"
    exit 1
fi

echo -e "${BLUE}📁 Found ${#PDF_FILES[@]} PDF file(s) to test${NC}"

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0
TOTAL_TESTS=${#PDF_FILES[@]}

# Function to run a single test
run_test() {
    local pdf_file="$1"
    local pdf_name=$(basename "$pdf_file" .pdf)
    local output_file="$OUTPUT_DIR/${pdf_name}.json"
    local result_file="$RESULTS_DIR/${pdf_name}_test_result.json"
    
    echo -e "${BLUE}🧪 Testing: $pdf_name${NC}"
    echo "  Input: $pdf_file"
    echo "  Output: $output_file"
    
    # Record test start time
    local start_time=$(date +%s)
    
    # Run the CLI tool
    if python3 "$CLI_TOOL" --input "$pdf_file" --output "$output_file" --verbose; then
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        
        # Check if output file was created and is valid JSON
        if [ -f "$output_file" ]; then
            if python3 -m json.tool "$output_file" > /dev/null 2>&1; then
                echo -e "${GREEN}✅ Test passed: $pdf_name (${duration}s)${NC}"
                
                # Extract summary information
                local total_songs=$(python3 -c "
import json
with open('$output_file', 'r') as f:
    data = json.load(f)
    print(data.get('counts', {}).get('total', 0))
" 2>/dev/null || echo "0")
                
                local error_count=$(python3 -c "
import json
with open('$output_file', 'r') as f:
    data = json.load(f)
    print(len(data.get('errors', [])))
" 2>/dev/null || echo "0")
                
                # Save test result
                cat > "$result_file" << EOF
{
    "test_name": "$pdf_name",
    "input_file": "$pdf_file",
    "output_file": "$output_file",
    "status": "PASSED",
    "duration_seconds": $duration,
    "total_songs": $total_songs,
    "error_count": $error_count,
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
                
                TESTS_PASSED=$((TESTS_PASSED + 1))
            else
                echo -e "${RED}❌ Test failed: $pdf_name - Invalid JSON output${NC}"
                TESTS_FAILED=$((TESTS_FAILED + 1))
                
                # Save test result
                cat > "$result_file" << EOF
{
    "test_name": "$pdf_name",
    "input_file": "$pdf_file",
    "output_file": "$output_file",
    "status": "FAILED",
    "error": "Invalid JSON output",
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
            fi
        else
            echo -e "${RED}❌ Test failed: $pdf_name - No output file created${NC}"
            TESTS_FAILED=$((TESTS_FAILED + 1))
        fi
    else
        echo -e "${RED}❌ Test failed: $pdf_name - CLI tool returned error${NC}"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        
        # Save test result
        cat > "$result_file" << EOF
{
    "test_name": "$pdf_name",
    "input_file": "$pdf_file",
    "status": "FAILED",
    "error": "CLI tool returned error",
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
    fi
    
    echo ""
}

# Run all tests
echo -e "${BLUE}🚀 Running tests...${NC}"
echo ""

for pdf_file in "${PDF_FILES[@]}"; do
    run_test "$pdf_file"
done

# Generate summary report
SUMMARY_FILE="$RESULTS_DIR/test_summary_$(date +%Y%m%d_%H%M%S).json"

cat > "$SUMMARY_FILE" << EOF
{
    "test_run": {
        "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
        "total_tests": $TOTAL_TESTS,
        "passed": $TESTS_PASSED,
        "failed": $TESTS_FAILED,
        "success_rate": "$(echo "scale=1; $TESTS_PASSED * 100 / $TOTAL_TESTS" | bc -l)%"
    },
    "test_files": [
$(for pdf_file in "${PDF_FILES[@]}"; do
    pdf_name=$(basename "$pdf_file" .pdf)
    result_file="$RESULTS_DIR/${pdf_name}_test_result.json"
    if [ -f "$result_file" ]; then
        echo "        $(cat "$result_file"),"
    fi
done | sed '$ s/,$//')
    ]
}
EOF

# Print final summary
echo "================================================"
echo -e "${BLUE}📊 Test Summary${NC}"
echo "================================================"
echo -e "Total tests: ${TOTAL_TESTS}"
echo -e "Passed: ${GREEN}${TESTS_PASSED}${NC}"
echo -e "Failed: ${RED}${TESTS_FAILED}${NC}"

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}🎉 All tests passed!${NC}"
    exit 0
else
    echo -e "${YELLOW}⚠️  Some tests failed. Check the results above.${NC}"
    exit 1
fi
