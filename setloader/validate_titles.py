#!/usr/local/bin/python3
"""
CLI tool to validate song titles against user's SBP backup and title mappings.
"""

import argparse
import json
import sys
from pathlib import Path
from title_validation_library import TitleValidator, TitleValidationError

def main():
    parser = argparse.ArgumentParser(description='Validate song titles against user backup and mappings')
    parser.add_argument('--input', '-i', required=True, help='Input JSON file with extracted songs')
    parser.add_argument('--output', '-o', required=True, help='Output JSON file with validated songs')
    parser.add_argument('--user-id', '-u', required=True, help='User email address/account ID')
    parser.add_argument('--backup', '-b', required=True, help='Path to user SBP backup file')
    parser.add_argument('--mappings', '-m', help='Path to user title mappings file (optional)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    # Validate inputs
    input_path = Path(args.input)
    output_path = Path(args.output)
    backup_path = Path(args.backup)
    mappings_path = Path(args.mappings) if args.mappings else None
    
    if not input_path.exists():
        print(f"Error: Input file {input_path} does not exist", file=sys.stderr)
        sys.exit(1)
    
    if not backup_path.exists():
        print(f"Error: Backup file {backup_path} does not exist", file=sys.stderr)
        sys.exit(1)
    
    if mappings_path and not mappings_path.exists():
        print(f"Warning: Mappings file {mappings_path} does not exist", file=sys.stderr)
        mappings_path = None
    
    try:
        if args.verbose:
            print(f"Loading input from: {input_path}")
            print(f"User ID: {args.user_id}")
            print(f"Backup file: {backup_path}")
            if mappings_path:
                print(f"Mappings file: {mappings_path}")
            else:
                print("Mappings file: Auto-detecting...")
        
        # Load input JSON
        with open(input_path, 'r', encoding='utf-8') as f:
            input_data = json.load(f)
        
        if args.verbose:
            print(f"Loaded input with {len(input_data.get('sets', []))} sets and {len(input_data.get('extras', []))} extras")
        
        # Initialize validator using the library
        validator = TitleValidator(args.user_id, backup_path, mappings_path)
        
        # Validate the input
        validated_data = validator.validate_input(input_data)
        
        # Save results
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(validated_data, f, indent=2, ensure_ascii=False)
        
        if args.verbose:
            print(f"Results written to: {output_path}")
        
        # Print summary using library method
        summary = validator.get_summary(validated_data)
        print("Validation complete:")
        print(summary)
        
    except TitleValidationError as e:
        print(f"Validation error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
