"""
ETAB & Region Map Parser (etab_parser.py)
Extracts Entity & Event Tables (ETAB) from all 33 RGN*.GFF files
Maps Map Entities, NPC Positions, Triggers & Bound GPL Script IDs
"""
import os, sys, struct, json, glob
sys.stdout.reconfigure(encoding='utf-8')

GAME_DIR = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN"
OUT_DIR  = r"C:\Users\pmany\.gemini\antigravity-ide\brain\451cd7a2-e8a0-455b-9450-b4e9c8806586\scratch"

def parse_etab_block(data, rgn_filename):
    etab_pos = data.find(b'ETAB')
    if etab_pos < 0:
        return None

    # Parse ETAB block header & entries
    # ETAB structure: tag (4) + flags (4) + count (4) + stride (4) + entries...
    header_offset = etab_pos
    tag = data[header_offset : header_offset+4].decode('ascii', errors='replace')
    
    # Read entry table count
    count = struct.unpack_from('<I', data, header_offset + 8)[0] if header_offset + 12 <= len(data) else 0
    stride = struct.unpack_from('<I', data, header_offset + 12)[0] if header_offset + 16 <= len(data) else 16

    entities = []
    table_start = header_offset + 16
    
    for i in range(min(count, 500)):
        ep = table_start + i * stride
        if ep + 16 > len(data): break
        
        # Read typical ETAB record: X(2), Y(2), EntityType(2), ScriptID/ID(4), Flags(4)
        x_pos, y_pos, ent_type = struct.unpack_from('<HHH', data, ep)
        script_id = struct.unpack_from('<I', data, ep+6)[0] if ep+10<=len(data) else 0
        flags = struct.unpack_from('<I', data, ep+10)[0] if ep+14<=len(data) else 0

        entities.append({
            "index": i,
            "x": x_pos,
            "y": y_pos,
            "type": ent_type,
            "script_id": f"0x{script_id:08X}",
            "flags": f"0x{flags:08X}",
            "raw_hex": ' '.join(f'{b:02X}' for b in data[ep:ep+min(stride,16)])
        })

    return {
        "region_file": rgn_filename,
        "etab_offset": f"0x{etab_pos:06X}",
        "entity_count": count,
        "stride": stride,
        "entities": entities
    }

def main():
    rgn_files = sorted(glob.glob(os.path.join(GAME_DIR, "RGN*.GFF")))
    print(f"✅ Scanning {len(rgn_files)} Region Files for ETAB Entity/Event tables...\n")

    all_region_maps = {}
    total_entities = 0

    for path in rgn_files:
        fname = os.path.basename(path)
        d = open(path, "rb").read()
        res = parse_etab_block(d, fname)
        if res:
            all_region_maps[fname] = res
            total_entities += res["entity_count"]
            print(f"  • {fname:<12}: Found {res['entity_count']:3d} entities/triggers @ {res['etab_offset']}")

    out_file = os.path.join(OUT_DIR, "etab_region_maps.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(all_region_maps, f, indent=2, ensure_ascii=False)

    print(f"\n✅ ETAB Parsing Complete! Saved to: {out_file}")
    print(f"📊 Total Map Entities/Triggers mapped across all 33 Regions: {total_entities}")

if __name__ == "__main__":
    main()
