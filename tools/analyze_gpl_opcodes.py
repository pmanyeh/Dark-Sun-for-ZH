"""
Analyze GPL Opcodes and Message Pointers in GPLDATA.GFF
"""
import os, sys, struct, re

GPLDATA_PATH = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN\GPLDATA.GFF"

def main():
    data = open(GPLDATA_PATH, "rb").read()
    gpl_pos = data.find(b'GPL ')
    if gpl_pos < 0:
        print("GPL tag not found")
        return
        
    table_start = gpl_pos + 28
    count = struct.unpack_from('<I', data, gpl_pos + 8)[0]
    print(f"GPL Tag at 0x{gpl_pos:06X}, Count: {count}")
    
    # Inspect first 10 scripts in detail
    for i in range(min(count, 15)):
        ep = table_start + i * 12
        eid  = struct.unpack_from('<I', data, ep)[0]
        eoff = struct.unpack_from('<I', data, ep+4)[0]
        esz  = struct.unpack_from('<I', data, ep+8)[0]
        
        block = data[eoff:eoff+esz]
        print(f"\n--- Script #{i} (ID: 0x{eid:08X}, Offset: 0x{eoff:06X}, Size: {esz}) ---")
        
        # Parse 6-byte records
        payload = block[4:]
        recs = len(payload) // 6
        for r in range(min(recs, 10)):
            rec = payload[r*6 : r*6+6]
            w0, w1, w2 = struct.unpack('<HHH', rec)
            print(f"  Rec {r:2d}:  w0=0x{w0:04X} ({w0:5d})  w1=0x{w1:04X} ({w1:5d})  w2=0x{w2:04X} ({w2:5d})")

if __name__ == "__main__":
    main()
