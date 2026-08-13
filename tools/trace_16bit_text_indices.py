"""
16-Bit Relative Text Index Table Scanner (trace_16bit_text_indices.py)
Scans for 16-bit relative string offset tables inside GFF resources
"""
import os, sys, struct, json, re
sys.stdout.reconfigure(encoding='utf-8')

GPLDATA_PATH = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN\GPLDATA.GFF"
RES_PATH     = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN\RESOURCE.GFF"

def scan_16bit_text_tables(data, fname):
    print(f"\n{'='*70}")
    print(f"16-BIT RELATIVE TEXT TABLE SCAN: {fname} ({len(data):,} bytes)")
    print('='*70)

    # Search for uint16_t offset tables pointing to null-terminated string pools
    tables_found = []

    for i in range(0, len(data) - 256, 2):
        shorts = struct.unpack_from('<32H', data, i)
        
        # Check if shorts are strictly increasing
        if all(0 < shorts[k] < 0x8000 for k in range(32)):
            if all(shorts[k] < shorts[k+1] for k in range(31)):
                # Test if relative to i, these offsets point to printable ASCII
                valid_ascii_count = 0
                for s in shorts:
                    target_off = i + s
                    if target_off < len(data) - 4:
                        sub = data[target_off : target_off + 64]
                        end = sub.find(b'\x00')
                        if end > 1 and all(0x20 <= b <= 0x7E for b in sub[:end]):
                            valid_ascii_count += 1
                if valid_ascii_count > 20:
                    tables_found.append((i, valid_ascii_count, shorts[:5]))

    print(f"🎉 Found {len(tables_found)} 16-bit relative text offset tables in {fname}!")
    for off, hits, sample in tables_found[:10]:
        print(f"  • Table @ Offset 0x{off:06X}: String Hits={hits}/32, Sample Offsets={[hex(s) for s in sample]}")

    return tables_found

def main():
    if os.path.exists(GPLDATA_PATH):
        scan_16bit_text_tables(open(GPLDATA_PATH, "rb").read(), "GPLDATA.GFF")
    if os.path.exists(RES_PATH):
        scan_16bit_text_tables(open(RES_PATH, "rb").read(), "RESOURCE.GFF")

if __name__ == "__main__":
    main()
