#!/usr/local/bin/python3
"""
CLI tool to extract songs from PDF files using AI prompts.
"""

import argparse
import sys
from pathlib import Path
from pdf_extraction_library import PDFExtractor, PDFExtractionError

def main():
    parser = argparse.ArgumentParser(description='Extract songs from PDF using AI')
    parser.add_argument('--input', '-i', required=True, help='Input PDF file')
    parser.add_argument('--output', '-o', required=True, help='Output JSON file')
    parser.add_argument('--prompt', '-p', default='prompts/openai_extraction.prompt', 
                       help='AI prompt file (default: prompts/openai_extraction.prompt)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--model', default='gpt-4o', help='OpenAI model to use (default: gpt-4o)')
    parser.add_argument('--temperature', type=float, default=0.1, help='Temperature for response generation (default: 0.1)')
    
    args = parser.parse_args()
    
    # Validate inputs
    input_path = Path(args.input)
    output_path = Path(args.output)
    prompt_path = Path(args.prompt)
    
    try:
        # Initialize the PDF extractor
        extractor = PDFExtractor()
        
        if args.verbose:
            print(f"Reading PDF: {input_path}")
            print(f"Using prompt: {prompt_path}")
            print(f"Using model: {args.model}")
        
        # Extract songs using the library
        result = extractor.extract_songs(
            pdf_path=input_path,
            prompt_path=prompt_path,
            model=args.model,
            temperature=args.temperature
        )
        
        if args.verbose:
            print("Received response from OpenAI")
        
        # Save results
        extractor.save_results(result, output_path)
        
        if args.verbose:
            print(f"Results written to: {output_path}")
        
        # Print summary
        summary = extractor.get_summary(result)
        print(summary)
        
    except PDFExtractionError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
