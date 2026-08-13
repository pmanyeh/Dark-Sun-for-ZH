"""
Text ID Index Table Finder
Goal: Locate the Text ID offset lookup tables in GPLDATA.GFF / RESOURCE.GFF
"""
import os, sys, struct, re
sys.stdout.reconfigure(encoding='utf-8')

GPLDATA_PATH = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN\GPLDATA.GFF"
RES_PATH     = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN\RESOURCE.GFF"
OUT_DIR      = r"C:\Users\pmany\.gemini\antigravity-ide\brain\451cd7a2-e8a0-455b-9450-b4e9c8806586\scratch"

def find_text_index_tables(data, filename):
    print(f"\n{'='*70}")
    print(f"SEARCHING TEXT INDEX TABLES IN {filename} ({len(data):,} bytes)")
    print('='*70)

    # Search for known tags in GFF: 'TEXT', 'NAME', 'SPIN', 'MSG '
    tags = [b'TEXT', b'NAME', b'SPIN', b'MSG ', b'STR ', b'NARR']
    for tag in tags:
        pos = 0
        hits = []
        while True:
            p = data.find(tag, pos)
            if p < 0: break
            hits.append(p)
            pos = p + 1
        if hits:
            print(f"  Tag {tag!r:8s}: {len(hits)} hits | First @ 0x{hits[0]:06X}")
            for p in hits[:5]:
                # Print hex around tag
                chunk = data[max(0, p-16) : min(len(data), p+64)]
                h = ' '.join(f'{b:02X}' for b in chunk)
                a = ''.join(chr(b) if 0x20<=b<=0x7E else '.' for b in chunk)
                print(f"    0x{p:06X}: {h}")
                print(f"            ASCII: {a}")

def main():
    if os.path.exists(GPLDATA_PATH):
        find_text_index_tables(open(GPLDATA_PATH, "rb").read(), "GPLDATA.GFF")
    if os.path.exists(RES_PATH):
        find_text_index_tables(open(RES_PATH, "rb").read(), "RESOURCE.GFF")

if __name__ == "__main__":
    main()
