"""
Global Text String Table Locator (locate_global_text_table.py)
Locates the Master Text Table in RESOURCE.GFF and DSUN.EXE by searching for Text ID indices (e.g. 0x1591)
"""
import os, sys, struct, glob

GAME_DIR = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN"

def main():
    res_path = os.path.join(GAME_DIR, "RESOURCE.GFF")
    exe_path = os.path.join(GAME_DIR, "DSUN.EXE")
    
    res_data = open(res_path, "rb").read()
    exe_data = open(exe_path, "rb").read()
    
    print(f"Scanning RESOURCE.GFF ({len(res_data):,} bytes) and DSUN.EXE ({len(exe_data):,} bytes) for Text ID 0x1591 (5521)...")

    # Search for uint16 0x1591 in RESOURCE.GFF
    res_hits = []
    pos = 0
    while True:
        p = res_data.find(b'\x91\x15', pos)
        if p < 0: break
        res_hits.append(p)
        pos = p + 1

    print(f"Found {len(res_hits)} occurrences of 0x1591 in RESOURCE.GFF!")
    for p in res_hits[:10]:
        print(f"  • RESOURCE.GFF @ 0x{p:06X}: Context = {res_data[max(0, p-8):min(len(res_data), p+24)].hex()}")

    # Search in DSUN.EXE
    exe_hits = []
    pos = 0
    while True:
        p = exe_data.find(b'\x91\x15', pos)
        if p < 0: break
        exe_hits.append(p)
        pos = p + 1

    print(f"\nFound {len(exe_hits)} occurrences of 0x1591 in DSUN.EXE!")
    for p in exe_hits[:10]:
        print(f"  • DSUN.EXE @ 0x{p:06X}: Context = {exe_data[max(0, p-8):min(len(exe_data), p+24)].hex()}")

if __name__ == "__main__":
    main()
