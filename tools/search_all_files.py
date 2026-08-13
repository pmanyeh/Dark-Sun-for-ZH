"""
Comprehensive Search for English Sentences across ALL files in DARKSUN folder
"""
import os, sys, glob, re

GAME_DIR = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN"

# Words that MUST appear in game dialogue or intro
SEARCH_PATTERNS = [
    rb'welcome', rb'Welcome',
    rb'arena', rb'Arena',
    rb'templar', rb'Templar',
    rb'gladiator', rb'Gladiator',
    rb'freedom', rb'Freedom',
    rb'slave', rb'Slave',
    rb'sorcerer', rb'Sorcerer',
    rb'Dethkun', rb'Kalak'
]

def search_file(filepath):
    data = open(filepath, "rb").read()
    results = []
    for pat in SEARCH_PATTERNS:
        for m in re.finditer(pat, data, re.IGNORECASE):
            pos = m.start()
            start = max(0, pos - 40)
            end = min(len(data), pos + len(m.group()) + 60)
            snippet = data[start:end]
            # Try to decode snippet as printable ascii
            asc = ''.join(chr(b) if 0x20 <= b <= 0x7E else '.' for b in snippet)
            results.append((pos, m.group().decode('ascii', errors='ignore'), asc))
    return results

def main():
    files = glob.glob(os.path.join(GAME_DIR, "*"))
    print(f"Scanning {len(files)} files in {GAME_DIR}...")
    
    total_found = 0
    for f in sorted(files):
        if os.path.isdir(f): continue
        res = search_file(f)
        if res:
            fname = os.path.basename(f)
            print(f"\n=== {fname} ({len(res)} hits) ===")
            for pos, word, snippet in res[:10]:
                print(f"  0x{pos:06X} [{word}]: {snippet}")
            if len(res) > 10:
                print(f"  ... and {len(res)-10} more hits")
            total_found += len(res)
            
    print(f"\nTotal hits: {total_found}")

if __name__ == "__main__":
    main()
