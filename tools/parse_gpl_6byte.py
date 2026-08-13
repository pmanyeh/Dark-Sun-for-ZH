"""
GPL 6-Byte Record Dissecting Script
Based on reverse engineering of DSUN.EXE @ 0x0699D2 (div ebx=6, imul dx=6)
"""
import os, sys, struct, re
sys.stdout.reconfigure(encoding='utf-8')

GPLDATA_PATH = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN\GPLDATA.GFF"
OUT_DIR      = r"C:\Users\pmany\.gemini\antigravity-ide\brain\451cd7a2-e8a0-455b-9450-b4e9c8806586\scratch"

def read_gpl_entries(data):
    gpl_pos = data.find(b'GPL ')
    if gpl_pos < 0: return []
    table_start = gpl_pos + 28
    count = struct.unpack_from('<I', data, gpl_pos + 8)[0]
    entries = []
    for i in range(count):
        ep = table_start + i * 12
        if ep + 12 > len(data): break
        eid  = struct.unpack_from('<I', data, ep)[0]
        eoff = struct.unpack_from('<I', data, ep+4)[0]
        esz  = struct.unpack_from('<I', data, ep+8)[0]
        if eoff < len(data) and 0 < esz < 0x100000:
            entries.append((i, eid, eoff, esz))
    return entries

def parse_6byte_records(block, block_id):
    print(f"\n{'='*70}")
    print(f"6-BYTE RECORD PARSER: GPL Block ID 0x{block_id:08X} (Total Size={len(block)})")
    print('='*70)

    hdr_len = struct.unpack_from('<I', block, 0)[0]
    print(f"Header Size: {hdr_len} bytes")

    # Data content after 4-byte header
    payload = block[4:]
    rec_count = len(payload) // 6
    remainder = len(payload) % 6
    print(f"6-byte Records Count: {rec_count} (Remainder bytes: {remainder})")

    print(f"\n{'Index':<6} {'Field0 (w0)':<12} {'Field2 (w1)':<12} {'Field4 (w2)':<12} {'Hex Raw':<18} {'ASCII'}")
    print("-" * 75)

    for i in range(min(rec_count, 35)):
        off = i * 6
        rec = payload[off : off+6]
        w0, w1, w2 = struct.unpack('<HHH', rec)
        h_str = ' '.join(f'{b:02X}' for b in rec)
        a_str = ''.join(chr(b) if 0x20<=b<=0x7E else '.' for b in rec)
        print(f"[{i:3d}]   0x{w0:04X} ({w0:<5}) 0x{w1:04X} ({w1:<5}) 0x{w2:04X} ({w2:<5}) {h_str:<18} {a_str}")

def main():
    data = open(GPLDATA_PATH, "rb").read()
    entries = read_gpl_entries(data)
    
    # Check Block 0, Block 2, Block 20
    for idx in [0, 1, 2, 20, 21]:
        if idx < len(entries):
            _, eid, eoff, esz = entries[idx]
            block = data[eoff : eoff + esz]
            parse_6byte_records(block, eid)

if __name__ == "__main__":
    main()
