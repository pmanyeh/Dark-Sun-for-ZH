"""
GPL Bytecode & String Table Dissecting Script
Goal: Inspect the binary layout of GPL blocks, find string pools or opcodes
"""
import os, sys, struct, re
from collections import Counter
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

def inspect_gpl_block(block, block_id):
    print(f"\n{'='*70}")
    print(f"GPL BLOCK INSPECTION: ID 0x{block_id:08X} (Len={len(block)})")
    print('='*70)

    # First 4 bytes = block length
    hdr_len = struct.unpack_from('<I', block, 0)[0]
    print(f"Header Length: {hdr_len} (matches block size: {hdr_len == len(block)})")

    # Hex dump first 128 bytes
    print("\nHex Dump (First 128 bytes):")
    for i in range(0, min(128, len(block)), 16):
        row = block[i:i+16]
        h = ' '.join(f'{b:02X}' for b in row)
        a = ''.join(chr(b) if 0x20<=b<=0x7E else '.' for b in row)
        print(f"  {i:04X}:  {h:<47}  {a}")

    # Search for string sequences within the block
    print("\nASCII Strings Found in Block:")
    strings = [(m.start(), m.group().decode('ascii', errors='replace'))
               for m in re.finditer(rb'[\x20-\x7E]{3,}', block)]
    if strings:
        for off, s in strings[:15]:
            print(f"  +0x{off:04X}: {s!r}")
    else:
        print("  (None found)")

    # Analyze byte frequency to identify opcode distribution
    print("\nByte Frequency Distribution (Top 10):")
    freq = Counter(block)
    for byte_val, count in freq.most_common(10):
        pct = (count / len(block)) * 100
        ch = chr(byte_val) if 0x20 <= byte_val <= 0x7E else '.'
        print(f"  0x{byte_val:02X} ({ch}): {count:4d} times ({pct:4.1f}%)")

def main():
    data = open(GPLDATA_PATH, "rb").read()
    entries = read_gpl_entries(data)
    
    # Pick a few diverse blocks for deep inspection
    # Entry 0: ID 0x00000000
    # Entry 2: ID 0x00001068
    # Entry 20: ID 0x000010D4
    target_indices = [0, 2, 3, 20, 21]
    
    for idx in target_indices:
        if idx < len(entries):
            _, eid, eoff, esz = entries[idx]
            block = data[eoff : eoff + esz]
            inspect_gpl_block(block, eid)

if __name__ == "__main__":
    main()
