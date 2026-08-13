"""
Search MSG (Message / Dialogue) Chunks across all GFF files
"""
import os, sys, glob, struct

GAME_DIR = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN"

def scan_msg_chunks(path):
    fname = os.path.basename(path)
    data = open(path, "rb").read()
    
    msg_tags = []
    pos = 0
    while True:
        p = data.find(b'MSG ', pos)
        if p < 0: break
        msg_tags.append(p)
        pos = p + 1
        
    return fname, len(data), msg_tags

def main():
    files = sorted(glob.glob(os.path.join(GAME_DIR, "*.GFF")))
    print(f"Scanning {len(files)} files for 'MSG ' dialogue tags...")
    
    total = 0
    for f in files:
        fname, size, tags = scan_msg_chunks(f)
        if tags:
            total += len(tags)
            print(f"  • {fname:<15} ({size:<9,} bytes): Found {len(tags)} MSG tags!")
            
    print(f"\nTotal MSG tags across game: {total}")

if __name__ == "__main__":
    main()
