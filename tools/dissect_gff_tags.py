"""
GFF Tag Pointers & String Index Dissecting Tool
Target: GPLDATA.GFF & RESOURCE.GFF Text Index Pointers
"""
import os, sys, struct, re
sys.stdout.reconfigure(encoding='utf-8')

GAME_DIR = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN"

def inspect_gff_tags(filename):
    path = os.path.join(GAME_DIR, filename)
    data = open(path, "rb").read()
    
    print(f"\n==================================================")
    print(f"DISSECTING GFF CONTAINER: {filename} ({len(data):,} bytes)")
    print(f"==================================================")

    # 1. Search for all 4-byte uppercase ASCII tags
    matches = list(re.finditer(rb'[A-Z0-9]{4}', data))
    tag_map = {}
    for m in matches:
        tag = m.group().decode('ascii')
        tag_map[tag] = tag_map.get(tag, []) + [m.start()]

    print(f"Total 4-char Tags Identified: {len(tag_map)}")
    for tag, locs in sorted(tag_map.items(), key=lambda x: -len(x[1]))[:15]:
        print(f"  • Tag {tag!r:6s}: {len(locs):4d} occurrences | First @ 0x{locs[0]:06X}")

    # 2. Inspect context around 'NAME' tag entries in GPLDATA.GFF
    if 'NAME' in tag_map:
        name_off = tag_map['NAME'][0]
        print(f"\nContext around first 'NAME' tag @ 0x{name_off:06X}:")
        chunk = data[max(0, name_off-32) : min(len(data), name_off+128)]
        h = ' '.join(f'{b:02X}' for b in chunk)
        a = ''.join(chr(b) if 0x20<=b<=0x7E else '.' for b in chunk)
        print(f"  Hex: {h}")
        print(f"  ASCII: {a}")

def main():
    inspect_gff_tags("GPLDATA.GFF")
    inspect_gff_tags("RESOURCE.GFF")

if __name__ == "__main__":
    main()
