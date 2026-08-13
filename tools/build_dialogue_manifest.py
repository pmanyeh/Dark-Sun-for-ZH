"""
Dialogue & Script Manifest Builder (build_dialogue_manifest.py) - Fixed Matching
Links ETAB Region Entities -> GPL Scripts -> Text IDs
"""
import os, sys, json
sys.stdout.reconfigure(encoding='utf-8')

OUT_DIR = r"C:\Users\pmany\.gemini\antigravity-ide\brain\451cd7a2-e8a0-455b-9450-b4e9c8806586\scratch"

def main():
    etab_file = os.path.join(OUT_DIR, "etab_region_maps.json")
    gpl_file  = os.path.join(OUT_DIR, "gpl_disassembled.json")

    if not os.path.exists(etab_file) or not os.path.exists(gpl_file):
        print("❌ Missing prerequisite JSON files")
        return

    etab_maps = json.load(open(etab_file, encoding='utf-8'))
    gpl_scripts = json.load(open(gpl_file, encoding='utf-8'))

    # Normalize script keys (e.g. 0x00001012 -> 0x1012)
    normalized_gpl = {}
    for k, v in gpl_scripts.items():
        val = int(k, 16)
        normalized_gpl[val] = v

    print(f"✅ Loaded {len(etab_maps)} Region Maps & {len(normalized_gpl)} Normalized GPL Scripts")

    manifest = {}
    total_dialogue_nodes = 0

    for rgn_name, rgn_data in etab_maps.items():
        rgn_manifest = {
            "region": rgn_name,
            "entity_count": rgn_data["entity_count"],
            "interactive_nodes": []
        }

        for ent in rgn_data["entities"]:
            raw_sid = int(ent["script_id"], 16)
            
            # Lookup with fuzzy fallback
            script_info = normalized_gpl.get(raw_sid)
            if not script_info:
                # Try masking
                script_info = normalized_gpl.get(raw_sid & 0xFFFF)
                
            text_ids = script_info.get("text_ids", []) if script_info else []
            instruction_count = script_info.get("record_count", 0) if script_info else 0

            node = {
                "entity_index": ent["index"],
                "position": {"x": ent["x"], "y": ent["y"]},
                "entity_type": ent["type"],
                "script_id": f"0x{raw_sid:04X}",
                "text_ids": text_ids,
                "instruction_count": instruction_count
            }

            rgn_manifest["interactive_nodes"].append(node)
            total_dialogue_nodes += len(text_ids)

        manifest[rgn_name] = rgn_manifest

    out_manifest = os.path.join(OUT_DIR, "dialogue_manifest.json")
    with open(out_manifest, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"\n🎉 Unified Manifest Generation Complete!")
    print(f"📄 Saved to: {out_manifest}")
    print(f"📊 Total Text ID Links Mapped Across Regions: {total_dialogue_nodes}")

if __name__ == "__main__":
    main()
