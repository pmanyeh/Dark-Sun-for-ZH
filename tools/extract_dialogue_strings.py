"""
Dark Sun Dialogue Text Extraction Master Solution (extract_dialogue_strings.py)
Iterates through all 216 GPL script entries and extracts embedded string sections using GFF record metadata
"""
import os, sys, struct, json, re
sys.stdout.reconfigure(encoding='utf-8')

GAME_DIR         = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN"
LOCALIZATION_DIR = r"d:\git\Dark Sun Series\localization"
OUT_TABLE        = os.path.join(LOCALIZATION_DIR, "DarkSun_Dialogue_Translation_Table.json")

def parse_gpl_data_entries(gpldata):
    """Find GPL chunk directory in GPLDATA.GFF"""
    gpl_pos = gpldata.find(b'GPL ')
    if gpl_pos < 0:
        return []
    
    table_start = gpl_pos + 28
    count = struct.unpack_from('<I', gpldata, gpl_pos + 8)[0]
    
    entries = []
    for i in range(count):
        ep = table_start + i * 12
        if ep + 12 > len(gpldata): break
        eid  = struct.unpack_from('<I', gpldata, ep)[0]
        eoff = struct.unpack_from('<I', gpldata, ep+4)[0]
        esz  = struct.unpack_from('<I', gpldata, ep+8)[0]
        if eoff < len(gpldata) and 0 < esz < 0x200000:
            entries.append((i, eid, eoff, esz))
    return entries

def extract_strings_from_script_block(block):
    """
    Extracts embedded English dialogue strings inside a GPL script block.
    GPL scripts contain opcode blocks followed by null-terminated string pools.
    """
    strings = []
    
    # Use regex for printable ASCII sequences (len >= 4) with spaces or dialogue punctuation
    matches = list(re.finditer(rb'[\x20-\x7E\r\n]{4,}\x00', block))
    
    for m in matches:
        s_bytes = m.group()[:-1] # Remove trailing null byte
        try:
            s_str = s_bytes.decode('ascii').strip()
            
            # Filter valid English text (skip single words/noise/file extensions)
            if len(s_str) >= 4 and not s_str.endswith(".oda") and not s_str.endswith(".GFF"):
                # Must contain letters and spaces or punctuation
                if any(c.isalpha() for c in s_str) and not re.match(r'^[A-Z0-9_]{4,}$', s_str):
                    strings.append((m.start(), s_str))
        except Exception:
            pass
            
    return strings

def main():
    gpldata_path = os.path.join(GAME_DIR, "GPLDATA.GFF")
    if not os.path.exists(gpldata_path):
        print(f"❌ Missing {gpldata_path}")
        return
        
    gpldata = open(gpldata_path, "rb").read()
    entries = parse_gpl_data_entries(gpldata)
    
    print(f"✅ Found {len(entries)} GPL Script entries in GPLDATA.GFF")
    print("🚀 Extracting embedded dialogue & text strings from GPL script blocks...\n")
    
    dialogue_table = []
    seen = set()

    for idx, eid, eoff, esz in entries:
        block = gpldata[eoff : eoff + esz]
        extracted = extract_strings_from_script_block(block)
        
        for pos, text in extracted:
            if text not in seen:
                seen.add(text)
                dialogue_table.append({
                    "entry_id": f"DS_TXT_{len(dialogue_table)+1:05d}",
                    "script_id": f"0x{eid:08X}",
                    "offset": f"0x{eoff + pos:06X}",
                    "original_en": text,
                    "translated_zh": "", # Ready for Traditional Chinese Translation
                    "status": "pending"
                })

    print("=" * 70)
    print("🎉 DIALOGUE EXTRACTION COMPLETE!")
    print("=" * 70)
    print(f"📊 Total Unique Dialogue & Text Strings Extracted: {len(dialogue_table)}")

    with open(OUT_TABLE, "w", encoding="utf-8") as f:
        json.dump(dialogue_table, f, indent=2, ensure_ascii=False)

    print(f"📄 Updated Master Dialogue Translation Table: {OUT_TABLE}")

    print("\n--- SAMPLE EXTRACTED DIALOGUE & TEXT STRINGS (First 25) ---")
    for item in dialogue_table[:25]:
        print(f"[{item['entry_id']}] ({item['script_id']} @ {item['offset']}): {item['original_en']}")

if __name__ == "__main__":
    main()
