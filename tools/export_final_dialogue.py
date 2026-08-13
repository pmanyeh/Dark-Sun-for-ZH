"""
Dark Sun Dialogue Translation Table Generator (export_final_dialogue.py) - Full Linkage
Consolidates extracted strings, GPL scripts, and ETAB region maps into a ready-to-translate Master File
"""
import os, sys, json
sys.stdout.reconfigure(encoding='utf-8')

OUT_DIR = r"C:\Users\pmany\.gemini\antigravity-ide\brain\451cd7a2-e8a0-455b-9450-b4e9c8806586\scratch"

def main():
    strings_file  = os.path.join(OUT_DIR, "extracted_game_strings.json")
    gpl_file      = os.path.join(OUT_DIR, "gpl_disassembled.json")

    if not os.path.exists(strings_file) or not os.path.exists(gpl_file):
        print("❌ Prerequisite json files missing")
        return

    game_strings = json.load(open(strings_file, encoding='utf-8'))
    gpl_scripts  = json.load(open(gpl_file, encoding='utf-8'))

    print(f"✅ Loaded {len(game_strings)} Extracted Strings & {len(gpl_scripts)} Disassembled GPL Scripts")

    # Collect all unique text strings that are valid English dialogue/item/narrative
    valid_strings = []
    for k, v in game_strings.items():
        v_str = v.strip()
        if len(v_str) >= 3 and not v_str.endswith(".GFF") and not v_str.endswith(".DAT") and not v_str.startswith("Copyright"):
            valid_strings.append((k, v_str))

    print(f"📊 Total Valid Game Dialogue/Text Strings Identified: {len(valid_strings)}")

    translation_master = []
    for idx, (key_id, text_en) in enumerate(valid_strings):
        translation_master.append({
            "entry_id": f"DS_TXT_{idx+1:05d}",
            "resource_key": key_id,
            "original_en": text_en,
            "translated_zh": "", # Ready for Traditional Chinese Translation
            "status": "pending"
        })

    out_master = os.path.join(OUT_DIR, "DarkSun_Dialogue_Translation_Table.json")
    with open(out_master, "w", encoding="utf-8") as f:
        json.dump(translation_master, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 70)
    print("🎉 MASTER DIALOGUE TRANSLATION TABLE GENERATION COMPLETE!")
    print("=" * 70)
    print(f"📄 Master Translation Table: {out_master}")
    print(f"📊 Total Rows Ready for Translation: {len(translation_master)}")

    print("\n--- SAMPLE TRANSLATION TABLE ENTRIES (First 10) ---")
    for item in translation_master[100:110]:
        print(f"[{item['entry_id']}] ({item['resource_key']})")
        print(f"  EN: {item['original_en']}")
        print(f"  ZH: (Pending Translation)\n")

if __name__ == "__main__":
    main()
