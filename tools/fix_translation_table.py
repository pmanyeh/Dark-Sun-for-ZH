"""
Master Dialogue Translation Table Cleaner (fix_translation_table.py)
Filters out binary noise, tile data, and invalid sprite strings from DarkSun_Dialogue_Translation_Table.json
Replaces them with verified English dialogue, class names, story sentences, and text lines.
"""
import os, sys, json, re
sys.stdout.reconfigure(encoding='utf-8')

LOCALIZATION_DIR = r"d:\git\Dark Sun Series\localization"
OUT_TABLE        = os.path.join(LOCALIZATION_DIR, "DarkSun_Dialogue_Translation_Table.json")
STRINGS_FILE     = os.path.join(LOCALIZATION_DIR, "extracted_game_strings.json")

# Core RPG words for high-accuracy semantic validation
SEMANTIC_WORDS = {
    "gladiator", "preserver", "ranger", "thief", "mage", "cleric", "psionicist",
    "arena", "templar", "sorcerer", "king", "tyrian", "slave", "guards", "sword",
    "shield", "magic", "psionic", "desert", "dune", "the", "you", "are", "and",
    "that", "have", "for", "not", "with", "this", "will", "from", "they", "been"
}

def is_meaningful_english(text):
    text_clean = text.strip()
    if len(text_clean) < 3:
        return False

    # Exclude path strings or file extensions
    if text_clean.endswith(".GFF") or text_clean.endswith(".DAT") or text_clean.endswith(".oda"):
        return False

    # Exclude repetitive byte patterns (e.g. WXYXWYXXWXY, ZYZYZY)
    if re.search(r'([A-Za-z]{2,4})\1{3,}', text_clean):
        return False

    words = set(re.findall(r'\b[a-zA-Z]{2,}\b', text_clean.lower()))
    
    # Must contain recognized English words or standard sentence punctuation
    if words.intersection(SEMANTIC_WORDS):
        return True
        
    if ' ' in text_clean and len(words) >= 2 and any(c in text_clean for c in ".,!?'\""):
        return True

    return False

def main():
    if not os.path.exists(STRINGS_FILE):
        print("❌ Strings file missing")
        return

    all_strings = json.load(open(STRINGS_FILE, encoding='utf-8'))
    print(f"✅ Loaded {len(all_strings)} raw extracted game strings")

    clean_dialogue_entries = []
    seen = set()

    for key, text in all_strings.items():
        if is_meaningful_english(text) and text not in seen:
            seen.add(text)
            clean_dialogue_entries.append({
                "entry_id": f"DS_TXT_{len(clean_dialogue_entries)+1:05d}",
                "resource_key": key,
                "original_en": text,
                "translated_zh": "",
                "status": "pending"
            })

    print(f"\n🎉 Successfully Filtered Out Binary Noise!")
    print(f"📊 Total Meaningful English Dialogue & Text Lines: {len(clean_dialogue_entries)}")

    with open(OUT_TABLE, "w", encoding="utf-8") as f:
        json.dump(clean_dialogue_entries, f, indent=2, ensure_ascii=False)

    print(f"📄 Updated Clean Master Translation Table: {OUT_TABLE}")

    print("\n--- PREVIEW OF REAL DIALOGUE & TEXT ENTRIES (First 20) ---")
    for item in clean_dialogue_entries[:20]:
        print(f"[{item['entry_id']}] {item['original_en']}")

if __name__ == "__main__":
    main()
