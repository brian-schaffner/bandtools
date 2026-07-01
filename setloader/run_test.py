#!/usr/bin/env python3
import subprocess
import sys
import os

# Change to the setloader directory
os.chdir('/usr/local/src/setloader')

# Run the end-to-end test
result = subprocess.run([sys.executable, 'test_end_to_end.py'], 
                       capture_output=True, text=True)

print("STDOUT:")
print(result.stdout)
print("\nSTDERR:")
print(result.stderr)
print(f"\nReturn code: {result.returncode}")
