"""
Strict Dialogue Filter and Table Cleaner (clean_translation_table_strict.py)
Filters out 4-char resource tags, oda file names, and random ASCII to isolate TRUE readable English strings
"""
import os, sys, json, re
sys.stdout.reconfigure(encoding='utf-8')

LOCALIZATION_DIR = r"d:\git\Dark Sun Series\localization"
OUT_TABLE        = os.path.join(LOCALIZATION_DIR, "DarkSun_Dialogue_Translation_Table.json")
STRINGS_FILE     = os.path.join(LOCALIZATION_DIR, "extracted_game_strings.json")

def is_true_english_text(text):
    t = text.strip()
    if len(t) < 3: return False
    
    # Filter out GFF tags (APFM, BUTN, WIND, etc)
    if t in ("APFMt", "BUTNn", "WINDn", "IDRBt", "EBOXt", "IRINn", "IDTIt"):
        return False
    if t.endswith(".oda") or t.endswith(".GFF") or t.endswith(".DAT") or t.endswith(".GFS"):
        return False
    if t.startswith("IX\\*") or t.startswith("EIX\\*") or t.startswith("late\\"):
        return False
    if re.match(r'^[A-Z0-9]{4}[a-z]?$', t): # Tag pattern
        return False
    if re.match(r'^[a-zA-Z]{1,3}$', t): # Too short random letters
        return False
        
    return True

def main():
    all_strings = json.load(open(STRINGS_FILE, encoding='utf-8'))
    clean_entries = []
    seen = set()

    for k, v in all_strings.items():
        v_clean = v.strip()
        if is_true_english_text(v_clean) and v_clean not in seen:
            seen.add(v_clean)
            clean_entries.append({
                "entry_id": f"DS_TXT_{len(clean_entries)+1:05d}",
                "resource_key": k,
                "original_en": v_clean,
                "translated_zh": "",
                "status": "pending"
            })

    print(f"✅ Filtered total {len(clean_entries)} true English plaintext entries!")
    with open(OUT_TABLE, "w", encoding="utf-8") as f:
        json.dump(clean_entries, f, indent=2, ensure_ascii=False)

    print("\n--- ALL TRUE PLAINTEXT GAME STRINGS ---")
    for item in clean_entries:
        print(f"[{item['entry_id']}] ({item['resource_key']}): {item['original_en']}")

if __name__ == "__main__":
    main()
