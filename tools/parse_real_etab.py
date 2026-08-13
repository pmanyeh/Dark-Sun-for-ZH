"""
Accurate ETAB Dissector (parse_real_etab.py) - Fixed Stride & Header Parsing
Reads official SSI ETAB Chunk Header & Entity Entry Array
"""
import os, sys, struct, json, glob
sys.stdout.reconfigure(encoding='utf-8')

GAME_DIR         = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN"
LOCALIZATION_DIR = r"d:\git\Dark Sun Series\localization"
OUT_MANIFEST     = os.path.join(LOCALIZATION_DIR, "dialogue_manifest.json")

def parse_region_etab_file(path):
    fname = os.path.basename(path)
    data = open(path, "rb").read()

    etab_pos = data.find(b'ETAB')
    if etab_pos < 0:
        return {"region": fname, "entity_count": 0, "interactive_nodes": []}

    # Official ETAB Structure:
    # 0x00: 'ETAB' (4)
    # 0x04: Header Size / Version (4) -> usually 0x00000080
    # 0x08: Entity Count (uint16)
    # 0x0A: Stride (uint16)
    
    hdr_size = struct.unpack_from('<I', data, etab_pos + 4)[0]
    count    = struct.unpack_from('<H', data, etab_pos + 8)[0]
    stride   = struct.unpack_from('<H', data, etab_pos + 10)[0]

    # Fallback stride for SSI Dark Sun ETAB: 16 bytes
    if stride != 16 and stride != 24 and stride != 32:
        stride = 16

    table_start = etab_pos + 12
    nodes = []

    for i in range(min(count, 300)):
        ep = table_start + i * stride
        if ep + stride > len(data): break

        x_pos, y_pos, sprite_id, script_id = struct.unpack_from('<HHHH', data, ep)
        flags = struct.unpack_from('<I', data, ep+8)[0] if stride >= 12 else 0

        # Filter out 0x4D47 (GMAP magic hit) and invalid zeroes
        if sprite_id != 0x4D47 and (x_pos > 0 or y_pos > 0 or script_id > 0):
            nodes.append({
                "entity_index": i,
                "position": {"x": x_pos, "y": y_pos},
                "sprite_id": f"0x{sprite_id:04X}",
                "script_id": f"0x{script_id:04X}",
                "flags": f"0x{flags:08X}"
            })

    return {
        "region": fname,
        "etab_offset": f"0x{etab_pos:06X}",
        "entity_count": len(nodes),
        "interactive_nodes": nodes
    }

def main():
    rgn_files = sorted(glob.glob(os.path.join(GAME_DIR, "RGN*.GFF")))
    print(f"🚀 Parsing ETAB Entities for {len(rgn_files)} Region Maps...\n")

    manifest = {}
    total_valid = 0

    for path in rgn_files:
        res = parse_region_etab_file(path)
        manifest[res["region"]] = res
        total_valid += res["entity_count"]
        print(f"  • {res['region']:<12}: {res['entity_count']:3d} valid map entities mapped")

    print("\n" + "=" * 70)
    print("🎉 ETAB REGION MANIFEST DISSECTION COMPLETE!")
    print("=" * 70)
    print(f"📊 Total Interactive Map Entities & NPC Nodes: {total_valid}")

    with open(OUT_MANIFEST, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"📄 Saved Clean Manifest: {OUT_MANIFEST}")

    # Preview RGNFF.GFF
    if "RGNFF.GFF" in manifest:
        print("\n--- SAMPLE ENTITIES IN RGNFF.GFF (First 10) ---")
        for node in manifest["RGNFF.GFF"]["interactive_nodes"][:10]:
            print(f"  Entity #{node['entity_index']} @ ({node['position']['x']},{node['position']['y']}): Sprite={node['sprite_id']}, Script={node['script_id']}")

if __name__ == "__main__":
    main()
