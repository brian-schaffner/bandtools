# Song Extractor CLI Tool

A command-line tool for extracting songs from PDF setlists using AI prompts.

## Setup

1. Install dependencies:
```bash
pip install -r requirements_cli.txt
```

2. Set up your OpenAI API key:
```bash
export OPENAI_API_KEY="your-api-key-here"
```
Or create a `.env` file:
```
OPENAI_API_KEY=your-api-key-here
```

## Usage

### Basic Usage
```bash
./read_songs.py --input tks-1.pdf --output tks-1.json
```

### With Custom Prompt
```bash
./read_songs.py --input tks-1.pdf --output tks-1.json --prompt prompts/custom.prompt
```

### Verbose Output
```bash
./read_songs.py --input tks-1.pdf --output tks-1.json --verbose
```

### Command Line Options
- `--input, -i`: Input PDF file (required)
- `--output, -o`: Output JSON file (required)
- `--prompt, -p`: AI prompt file (default: prompts/openai_extraction.prompt)
- `--verbose, -v`: Enable verbose output

## Output Format

The tool outputs JSON in the following format:

```json
{
  "sets": [
    {
      "name": "Set 1",
      "time_window": "9-10:30",
      "break_minutes": 15,
      "songs": [
        { "order": 1, "title": "Hurt So Good", "key": "A" },
        { "order": 2, "title": "Pontoon", "key": "A" }
      ]
    }
  ],
  "extras": [
    { "title": "Save Me" }
  ],
  "counts": {
    "per_set": { "Set 1": 2, "Set 2": 3, "Set 3": 1 },
    "extras": 1,
    "total": 7
  },
  "errors": []
}
```

## Testing

Run the test harness:
```bash
./test_read_songs.sh
```

The test harness will:
1. Check dependencies
2. Find all PDF files in `test_data/` directory
3. Run the CLI tool on each PDF
4. Validate JSON output
5. Generate a summary report

### Test Results

Test results are saved in:
- `test_output/`: Generated JSON files
- `test_results/`: Individual test results and summary

## Error Handling

The tool handles various error conditions:
- Missing input files
- Invalid PDF files
- OpenAI API errors
- JSON parsing errors
- File I/O errors

All errors are reported to stderr with appropriate exit codes.
