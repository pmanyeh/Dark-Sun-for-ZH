"""
Locate Dialogue Chunks & Search for Key Story Terms (locate_dialogue_chunks.py)
Search for iconic Dark Sun intro dialogue terms across all game containers
"""
import os, sys, struct, re, glob
sys.stdout.reconfigure(encoding='utf-8')

GAME_DIR = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN"
OUT_DIR  = r"C:\Users\pmany\.gemini\antigravity-ide\brain\451cd7a2-e8a0-455b-9450-b4e9c8806586\scratch"

# Iconic Dark Sun Opening Words & Dialogue Keywords
SEARCH_WORDS = [
    b"Arena", b"gladiator", b"Templar", b"Dethkun", b"Tyr", b"Kalak",
    b"slave", b"welcome", b"fight", b"kill", b"freedom", b"sorcerer",
    b"desert", b"rebel", b"guard", b"cell", b"pit", b"gate"
]

def scan_file_for_dialogue_words(path):
    fname = os.path.basename(path)
    data = open(path, "rb").read()
    
    hits = []
    for word in SEARCH_WORDS:
        p = 0
        while True:
            pos = data.find(word, p)
            if pos < 0: break
            
            # Extract surrounding 64 bytes context
            start = max(0, pos - 20)
            end   = min(len(data), pos + len(word) + 40)
            chunk = data[start:end]
            asc = ''.join(chr(b) if 0x20<=b<=0x7E else '.' for b in chunk)
            
            hits.append((pos, word.decode(), asc))
            p = pos + len(word)
            
    return fname, len(data), hits

def main():
    gff_files = sorted(glob.glob(os.path.join(GAME_DIR, "*.GFF")))
    print(f"🔍 Searching {len(gff_files)} GFF files for iconic Dark Sun dialogue keywords...\n")

    total_hits = 0
    file_hits = {}

    for path in gff_files:
        fname, size, hits = scan_file_for_dialogue_words(path)
        if hits:
            file_hits[fname] = hits
            total_hits += len(hits)
            print(f"  • {fname:<15} ({size:<9,} bytes): Found {len(hits):4d} Dialogue Keyword Matches!")

    print("\n" + "=" * 70)
    print(f"TOTAL DIALOGUE KEYWORD MATCHES: {total_hits}")
    print("=" * 70)

    print("\n--- SAMPLE KEYWORD MATCHES WITH CONTEXT ---")
    for fname, hits in file_hits.items():
        print(f"\n[{fname}]")
        for pos, word, ctx in hits[:8]:
            print(f"  @ 0x{pos:06X} [{word}]: {ctx}")

if __name__ == "__main__":
    main()
