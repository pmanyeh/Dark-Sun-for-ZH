"""
TEXT and Dialogue Extraction Test
Target: RESOURCE.GFF and RGN*.GFF
Goal: Locate English dialogue texts associated with the GPL script IDs
"""
import os, sys, struct, re
sys.stdout.reconfigure(encoding='utf-8')

RES_PATH = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN\RESOURCE.GFF"
RGN02_PATH = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN\RGN02.GFF"
OUT_DIR  = r"C:\Users\pmany\.gemini\antigravity-ide\brain\451cd7a2-e8a0-455b-9450-b4e9c8806586\scratch"

def scan_text_blocks(data, filename):
    print(f"\n{'='*70}")
    print(f"TEXT / DIALOGUE SCAN: {filename} ({len(data):,} bytes)")
    print('='*70)

    # 1. Search for TEXT tags
    text_pos = 0
    text_tags = []
    while True:
        pos = data.find(b'TEXT', text_pos)
        if pos < 0: break
        text_tags.append(pos)
        text_pos = pos + 1

    print(f"Found {len(text_tags)} 'TEXT' tag occurrences in {filename}")

    # 2. Extract long readable sentences (len >= 15)
    sentences = [(m.start(), m.group().decode('ascii', errors='replace'))
                 for m in re.finditer(rb'[\x20-\x7E\r\n]{15,}', data)]
    
    # Filter out garbage ASCII
    clean_sentences = []
    for off, s in sentences:
        s_strip = s.strip()
        # Sentence heuristic: contains spaces, has normal punctuation or English words
        if ' ' in s_strip and any(c in s_strip for c in ".,!?'\""):
            clean_sentences.append((off, s_strip))

    print(f"Found {len(clean_sentences)} readable dialogue/sentence entries")
    print("\nSample Dialogue Texts (First 20):")
    for off, s in clean_sentences[:20]:
        print(f"  0x{off:06X}: {s[:90]}")

    return clean_sentences

def main():
    if os.path.exists(RES_PATH):
        res_data = open(RES_PATH, "rb").read()
        scan_text_blocks(res_data, "RESOURCE.GFF")

    if os.path.exists(RGN02_PATH):
        rgn_data = open(RGN02_PATH, "rb").read()
        scan_text_blocks(rgn_data, "RGN02.GFF")

if __name__ == "__main__":
    main()
