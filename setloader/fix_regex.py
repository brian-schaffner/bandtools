#!/usr/bin/env python3
"""Fix the regex syntax error in server.py"""

# Read the file
with open('server.py', 'r') as f:
    content = f.read()

# Fix the problematic regex line
old_regex = "s = re.sub(r'[\"\\'`\\']', '', s)"
new_regex = 's = re.sub(r"[\\"\'`\']", "", s)'

if old_regex in content:
    content = content.replace(old_regex, new_regex)
    print("✅ Fixed first regex")
else:
    print("❌ First regex not found")

# Also fix the second occurrence
old_regex2 = "s = re.sub(r'[\"\\'`\\']', '', s)"
if old_regex2 in content:
    content = content.replace(old_regex2, new_regex)
    print("✅ Fixed second regex")

# Write back
with open('server.py', 'w') as f:
    f.write(content)

print("✅ Fixed regex syntax in server.py")
