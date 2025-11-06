#!/usr/bin/env python3
"""Get three active listings from Cian"""

import sys
sys.path.insert(0, 'src')

from cian_parser import CianParser
import json

parser = CianParser(delay=1.0)

# Search for apartments in SPb
search_url = "https://spb.cian.ru/cat.php?deal_type=sale&engine_version=2&offer_type=flat&region=2&room1=1&room2=1"

print("Searching for listings...")
listings = parser.parse_search_page(search_url)

print(f"\nFound {len(listings)} listings")
print("\nFirst 3 listings:")
for i, listing in enumerate(listings[:3], 1):
    print(f"\n{i}. {listing.get('title', 'No title')}")
    print(f"   Price: {listing.get('price', 'N/A')}")
    print(f"   URL: {listing.get('url', 'N/A')}")
