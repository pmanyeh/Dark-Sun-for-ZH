"""
Trace Text ID Offset Mapping in GFF files
Goal: Map Text IDs (e.g., 2688, 2049, 1541) to offsets in GPLDATA.GFF / RESOURCE.GFF
"""
import os, sys, struct, json, re

GPLDATA_PATH = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN\GPLDATA.GFF"
RES_PATH     = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN\RESOURCE.GFF"

def search_text_id_indices(data, name):
    print(f"\n--- Searching Text ID Indices in {name} ({len(data):,} bytes) ---")
    
    # In SSI GFF format, a string table resource often has:
    # count (uint16/uint32) + array of offsets (uint16/uint32[]) followed by null-terminated strings
    # Or string entries: string_id (uint16) + string_offset (uint32)
    
    # Search for contiguous arrays of offsets that point to ASCII strings inside data
    candidates = []
    
    for i in range(0, len(data) - 512, 4):
        # Check if i points to a table of offsets
        offsets = struct.unpack_from('<32I', data, i)
        # Check if offsets are ascending and within file bounds
        if all(0 < o < len(data) for o in offsets):
            if all(offsets[k] < offsets[k+1] for k in range(31)):
                # Check if offsets point to printable ASCII strings
                string_hits = 0
                for o in offsets:
                    if o < len(data) - 4:
                        sub = data[o : o+64]
                        end = sub.find(b'\x00')
                        if end > 2 and all(0x20 <= b <= 0x7E for b in sub[:end]):
                            string_hits += 1
                if string_hits > 20:
                    candidates.append((i, offsets[0], offsets[-1], string_hits))

    print(f"Found {len(candidates)} string offset table candidates!")
    for i, start_o, end_o, hits in candidates[:10]:
        print(f"  • Table @ 0x{i:06X}: Range [0x{start_o:06X} - 0x{end_o:06X}], String Hits: {hits}/32")

def main():
    if os.path.exists(GPLDATA_PATH):
        search_text_id_indices(open(GPLDATA_PATH, "rb").read(), "GPLDATA.GFF")
    if os.path.exists(RES_PATH):
        search_text_id_indices(open(RES_PATH, "rb").read(), "RESOURCE.GFF")

if __name__ == "__main__":
    main()
