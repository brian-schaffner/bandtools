#!/usr/bin/env python3
import re

def normalize_key(s: str) -> str:
    s = s.strip()
    s = re.sub(r'\s+', ' ', s)
    s = re.sub(r"[\"'`']", "", s)
    s = s.replace('&', 'and')
    s = re.sub(r'\(feat[^\)]*\)', '', s, flags=re.I)
    s = re.sub(r'[^A-Za-z0-9 ]+', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s.casefold()

# Test normalization
original = 'Baby One More Time'
normalized = normalize_key(original)
print(f'Original: "{original}"')
print(f'Normalized: "{normalized}"')

# Test what's in the catalog
catalog_title = 'Baby One More Time'
catalog_normalized = normalize_key(catalog_title)
print(f'Catalog title: "{catalog_title}"')
print(f'Catalog normalized: "{catalog_normalized}"')
print(f'Match: {normalized == catalog_normalized}')
