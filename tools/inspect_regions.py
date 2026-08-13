"""
Region Files (RGN*.GFF) Deep Inspector
Goal: Extract text & dialogue index structures from all 41 region files
"""
import os, sys, struct, re, glob
sys.stdout.reconfigure(encoding='utf-8')

GAME_DIR = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN"
OUT_DIR  = r"C:\Users\pmany\.gemini\antigravity-ide\brain\451cd7a2-e8a0-455b-9450-b4e9c8806586\scratch"

def inspect_rgn_file(path):
    filename = os.path.basename(path)
    data = open(path, "rb").read()
    
    # Search for all 4-char tags in this region file
    tag_positions = {}
    known_tags = [b'GPL ', b'NAME', b'TEXT', b'MSG ', b'GMAP', b'ETAB', b'OTAB', b'ITAB']
    
    for tag in known_tags:
        positions = []
        p = 0
        while True:
            pos = data.find(tag, p)
            if pos < 0: break
            positions.append(pos)
            p = pos + 1
        if positions:
            tag_positions[tag.decode('ascii','replace')] = positions
            
    # Search for ASCII strings in this region
    strings = [(m.start(), m.group().decode('ascii', errors='replace').strip())
               for m in re.finditer(rb'[\x20-\x7E]{4,}', data)]
    
    # Filter out path-like or noise strings
    good_strings = [s for off, s in strings if ' ' in s or len(s) > 8]
    
    return filename, len(data), tag_positions, good_strings, strings

def main():
    rgn_files = sorted(glob.glob(os.path.join(GAME_DIR, "RGN*.GFF")))
    print(f"✅ Found {len(rgn_files)} RGN*.GFF region files\n")
    
    print(f"{'Filename':<12} {'Size':<10} {'Tags Found':<40} {'Strings Count'}")
    print("-" * 75)
    
    total_strings = 0
    all_region_strings = {}
    
    for path in rgn_files:
        fname, size, tags, good_s, all_s = inspect_rgn_file(path)
        tag_str = ', '.join(f"{t}:{len(p)}" for t, p in tags.items()) if tags else "None"
        print(f"{fname:<12} {size:<10} {tag_str:<40} {len(good_s)}")
        total_strings += len(good_s)
        if good_s:
            all_region_strings[fname] = good_s

    print("-" * 75)
    print(f"Total readable dialogue/text candidates across all regions: {total_strings}\n")

    # Sample dialogue from a few regions
    print("=" * 70)
    print("SAMPLE REGION TEXTS:")
    print("=" * 70)
    for fname, st_list in list(all_region_strings.items())[:5]:
        print(f"\n--- {fname} ({len(st_list)} text items) ---")
        for s in st_list[:10]:
            print(f"  • {s}")

if __name__ == "__main__":
    main()
