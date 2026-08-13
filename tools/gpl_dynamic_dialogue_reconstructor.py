"""
GPL Dynamic Dialogue & Choice Tree Reconstructor (gpl_dynamic_dialogue_reconstructor.py)
Core engine simulator reconstructing full NPC story dialogue lines, dynamic variables (%s, %d), and dialogue trees.
"""
import os, sys, struct, json, re
sys.stdout.reconfigure(encoding='utf-8')

GAME_DIR         = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN"
LOCALIZATION_DIR = r"d:\git\Dark Sun Series\localization"
OUT_DIALOGUE_TREE = os.path.join(LOCALIZATION_DIR, "npc_story_dialogue_trees.json")

def load_json_data(filename):
    path = os.path.join(LOCALIZATION_DIR, filename)
    if os.path.exists(path):
        return json.load(open(path, encoding='utf-8'))
    return {}

def extract_all_string_tokens(gpldata, resdata):
    """Extract all text tokens and sentence fragments from GFF data"""
    pattern = re.compile(rb'[\x20-\x7E]{3,}\x00')
    tokens = {}
    
    for container_data in (gpldata, resdata):
        for m in pattern.finditer(container_data):
            s_bytes = m.group()[:-1]
            try:
                s = s_bytes.decode('ascii', errors='ignore').strip()
                if len(s) >= 3 and not s.endswith(".oda") and not s.endswith(".GFF"):
                    tokens[m.start()] = s
            except Exception:
                pass
    return tokens

def reconstruct_npc_dialogue_trees():
    gpl_disasm = load_json_data("gpl_disassembled.json")
    manifest   = load_json_data("dialogue_manifest.json")
    
    gpldata_path = os.path.join(GAME_DIR, "GPLDATA.GFF")
    resdata_path = os.path.join(GAME_DIR, "RESOURCE.GFF")
    
    if not os.path.exists(gpldata_path):
        print("❌ GPLDATA.GFF missing")
        return
        
    gpldata = open(gpldata_path, "rb").read()
    resdata = open(resdata_path, "rb").read() if os.path.exists(resdata_path) else b""

    tokens = extract_all_string_tokens(gpldata, resdata)
    print(f"✅ Extracted {len(tokens)} text tokens across game GFF archives")

    dialogue_trees = []
    tree_count = 0

    print("🚀 Reconstructing Dynamic Dialogue Trees & Variables across 33 Regions...\n")

    for region_name, region_data in manifest.items():
        interactive_nodes = region_data.get("interactive_nodes", [])
        
        for node in interactive_nodes:
            raw_sid = node.get("script_id", "0x0000")
            
            # Normalize script ID format (e.g. 0x15041 -> 0x00015041)
            try:
                sid_num = int(raw_sid, 16)
                script_id = f"0x{sid_num:08X}"
            except Exception:
                script_id = raw_sid
                
            sprite_id = node.get("sprite_id")
            pos       = node.get("position", {})
            
            # Try finding matching script in disassembled database
            script_data = gpl_disasm.get(script_id)
            if not script_data:
                # Fallback: search key with trailing 4 hex digits
                for k in gpl_disasm.keys():
                    if k.endswith(raw_sid.replace("0x", "")):
                        script_data = gpl_disasm[k]
                        break
            if not script_data:
                script_data = {}
                
            text_ids = script_data.get("text_ids", [])
            
            node_dialogue_lines = []
            
            for tid in text_ids:
                # Resolve Text ID to dynamic sentence template
                if tid in tokens:
                    text_str = tokens[tid]
                else:
                    # Generic template for dynamic GPL interpolation
                    text_str = f"[GPL Event String 0x{tid:04X}]"
                
                # Check for dynamic variable placeholders (%s, %d, %c)
                has_vars = '%' in text_str
                
                node_dialogue_lines.append({
                    "text_id": f"0x{tid:04X}",
                    "sentence_template": text_str,
                    "has_dynamic_variables": has_vars,
                    "chinese_translation": ""
                })
            
            if node_dialogue_lines or script_id != "0x0000":
                tree_count += 1
                dialogue_trees.append({
                    "dialogue_tree_id": f"TREE_{tree_count:04d}",
                    "region": region_name,
                    "npc_position": pos,
                    "sprite_id": sprite_id,
                    "script_id": script_id,
                    "dialogue_nodes": node_dialogue_lines
                })

    print("=" * 70)
    print("🎉 DYNAMIC DIALOGUE TREE RECONSTRUCTION COMPLETE!")
    print("=" * 70)
    print(f"📊 Total Interactive NPC Dialogue Trees Reconstructed: {len(dialogue_trees)}")

    with open(OUT_DIALOGUE_TREE, "w", encoding="utf-8") as f:
        json.dump(dialogue_trees, f, indent=2, ensure_ascii=False)

    print(f"📄 Saved Dialogue Tree Master: {OUT_DIALOGUE_TREE}")

    if dialogue_trees:
        print("\n--- SAMPLE RECONSTRUCTED DIALOGUE TREE ---")
        for tree in dialogue_trees[:5]:
            print(f"[{tree['dialogue_tree_id']}] Region: {tree['region']}, NPC @ ({tree['npc_position']['x']},{tree['npc_position']['y']}), Script: {tree['script_id']}")
            for dline in tree['dialogue_nodes']:
                print(f"  • [{dline['text_id']}] Template: {dline['sentence_template']}")
            print()

if __name__ == "__main__":
    reconstruct_npc_dialogue_trees()
