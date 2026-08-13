"""
Search for exact dialogue quote "Tectuktitlay" or "arena" across all files in Dark Sun
"""
import os, sys, glob, re

GAME_DIR = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN"

SEARCH_TERMS = [b"Tectuktitlay", b"weakness", b"slavepen", b"Draj", b"gladiators"]

def main():
    files = glob.glob(os.path.join(GAME_DIR, "*"))
    print(f"Searching {len(files)} files for exact opening quotes...")
    
    for f in sorted(files):
        if os.path.isdir(f): continue
        data = open(f, "rb").read()
        fname = os.path.basename(f)
        
        for term in SEARCH_TERMS:
            pos = 0
            while True:
                p = data.find(term, pos)
                if p < 0: break
                
                snippet = data[max(0, p-30):min(len(data), p+50)]
                asc = ''.join(chr(b) if 0x20<=b<=0x7E else '.' for b in snippet)
                print(f"[{fname}] @ 0x{p:06X} [{term.decode()}]: {asc}")
                pos = p + len(term)

if __name__ == "__main__":
    main()
