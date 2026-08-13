"""
GFF Container Entry Extractor (gff_entry_extractor.py)
Iterates through all chunk headers in RESOURCE.GFF & GPLDATA.GFF to catalog resource types
"""
import os, sys, struct, json
sys.stdout.reconfigure(encoding='utf-8')

GAME_DIR = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN"

def parse_gff_entries(filepath):
    fname = os.path.basename(filepath)
    data = open(filepath, "rb").read()
    
    if data[:4] != b'GFFI':
        return None
        
    toc_off = struct.unpack_from('<I', data, 8)[0]
    count   = struct.unpack_from('<I', data, 16)[0]
    
    print(f"\n=== GFF: {fname} ({len(data):,} bytes) ===")
    print(f"  TOC Offset: 0x{toc_off:06X}, Count: {count}")
    
    entries = []
    # Try directory entries parsing (12-byte entries)
    curr = toc_off
    tags_found = {}
    
    while curr + 12 <= len(data):
        tag = data[curr:curr+4]
        if all(0x20 <= b <= 0x7E for b in tag):
            tag_str = tag.decode('ascii')
            e_off = struct.unpack_from('<I', data, curr+4)[0]
            e_sz  = struct.unpack_from('<I', data, curr+8)[0]
            
            if 0 < e_off < len(data) and 0 < e_sz < 0x200000:
                tags_found[tag_str] = tags_found.get(tag_str, 0) + 1
                entries.append((tag_str, e_off, e_sz))
        curr += 12
        if len(entries) >= count and count > 0:
            break

    print(f"  Total Valid Cataloged Entries: {len(entries)}")
    for t, c in tags_found.items():
        print(f"    • Tag {t!r:8s}: {c} entries")
        
    return entries

def main():
    for f in ["GPLDATA.GFF", "RESOURCE.GFF", "RGN02.GFF", "CINE.GFF"]:
        path = os.path.join(GAME_DIR, f)
        if os.path.exists(path):
            parse_gff_entries(path)

if __name__ == "__main__":
    main()
