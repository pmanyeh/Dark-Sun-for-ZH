"""
Dark Sun Official GFF Container Specification & Directory Table Parser
Based on SSI Master GFF Spec (Glassmyer/dsun_music reverse engineering)
"""
import os, sys, struct, json
sys.stdout.reconfigure(encoding='utf-8')

GAME_DIR = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN"

def parse_official_gff_toc(filepath):
    fname = os.path.basename(filepath)
    data = open(filepath, "rb").read()

    if data[:4] != b'GFFI':
        return None

    # Header Structure (Official SSI GFF Specification):
    # 0x00: Magic 'GFFI' (4)
    # 0x04: Version (2) + Flags (2) -> uint32
    # 0x08: TOC Offset (uint32)
    # 0x0C: Total Entry Table Size (uint32)
    # 0x10: Total Resource Count (uint32)
    
    toc_off   = struct.unpack_from('<I', data, 8)[0]
    toc_size  = struct.unpack_from('<I', data, 12)[0]
    res_count = struct.unpack_from('<I', data, 16)[0]

    print(f"\n==================================================")
    print(f"OFFICIAL GFF TOC ANALYSIS: {fname} ({len(data):,} bytes)")
    print(f"==================================================")
    print(f"  TOC Offset: 0x{toc_off:06X} ({toc_off})")
    print(f"  TOC Size  : {toc_size:,} bytes")
    print(f"  Resource Count: {res_count}")

    # Read TOC Table (Each TOC Entry is 12 bytes: Type Tag (4) + ID (4) + Offset (4))
    # or Type Tag (4) + Chunk Offset (4) + Chunk Length (4)
    entries = []
    
    # Analyze first 20 TOC Entries
    curr = toc_off
    for i in range(min(res_count, 40)):
        if curr + 12 > len(data): break
        
        tag_b = data[curr : curr+4]
        arg1  = struct.unpack_from('<I', data, curr+4)[0]
        arg2  = struct.unpack_from('<I', data, curr+8)[0]
        
        tag_str = ''.join(chr(b) if 0x20<=b<=0x7E else '.' for b in tag_b)
        print(f"  [{i:3d}] Offset 0x{curr:06X}: Tag={tag_str!r:6s}  Arg1=0x{arg1:08X} ({arg1:<8d})  Arg2=0x{arg2:08X} ({arg2:<8d})")
        curr += 12

def main():
    for f in ["GPLDATA.GFF", "RESOURCE.GFF", "RGN02.GFF"]:
        path = os.path.join(GAME_DIR, f)
        if os.path.exists(path):
            parse_official_gff_toc(path)

if __name__ == "__main__":
    main()
