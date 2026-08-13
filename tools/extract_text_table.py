"""
Text ID Table Decoder & Dialogue Extractor (extract_text_table.py)
Extracts all English dialogue & story strings mapped to Text IDs from RESOURCE.GFF / GPLDATA.GFF
"""
import os, sys, struct, json, re
sys.stdout.reconfigure(encoding='utf-8')

RES_PATH     = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN\RESOURCE.GFF"
GPLDATA_PATH = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN\GPLDATA.GFF"
OUT_DIR      = r"C:\Users\pmany\.gemini\antigravity-ide\brain\451cd7a2-e8a0-455b-9450-b4e9c8806586\scratch"

def extract_strings_from_gff(data, label=""):
    """Extract null-terminated string table entries from GFF data"""
    print(f"Scanning string tables in {label} ({len(data):,} bytes)...")

    # Find TEXT tag in GFF directory
    text_pos = data.find(b'TEXT')
    string_dict = {}

    if text_pos >= 0:
        print(f"  Found 'TEXT' tag @ 0x{text_pos:06X}")
        # Read TEXT block directory info
        # Header + 4 = tag, + 8 = count/table info
        count = struct.unpack_from('<I', data, text_pos + 8)[0] if text_pos + 12 <= len(data) else 0
        print(f"  TEXT Block Count / Marker: {count} (0x{count:08X})")

    # Full scan for null-terminated printable ASCII strings
    pattern = re.compile(rb'[\x20-\x7E\r\n]{3,}\x00')
    matches = list(pattern.finditer(data))
    print(f"  Found {len(matches)} potential null-terminated ASCII string candidates")

    for i, m in enumerate(matches):
        s_bytes = m.group()[:-1] # strip trailing null byte
        try:
            s_text = s_bytes.decode('ascii').strip()
            if len(s_text) >= 3 and not s_text.startswith("GFF"):
                string_dict[m.start()] = s_text
        except Exception:
            pass

    return string_dict

def main():
    if not os.path.exists(RES_PATH) or not os.path.exists(GPLDATA_PATH):
        print("❌ Prerequisite GFF files missing")
        return

    res_data = open(RES_PATH, "rb").read()
    gpl_data = open(GPLDATA_PATH, "rb").read()

    res_strings = extract_strings_from_gff(res_data, "RESOURCE.GFF")
    gpl_strings = extract_strings_from_gff(gpl_data, "GPLDATA.GFF")

    combined_strings = {}
    for off, s in res_strings.items():
        combined_strings[f"RES_0x{off:06X}"] = s
    for off, s in gpl_strings.items():
        combined_strings[f"GPL_0x{off:06X}"] = s

    print(f"\n✅ Extracted Total {len(combined_strings)} Game Text Strings across RESOURCE.GFF & GPLDATA.GFF")

    out_file = os.path.join(OUT_DIR, "extracted_game_strings.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(combined_strings, f, indent=2, ensure_ascii=False)

    print(f"📄 Saved full extracted string database to: {out_file}")

    # Display sample extracted dialogue/text strings
    print("\n--- SAMPLE EXTRACTED GAME STRINGS (First 25 Entries) ---")
    count = 0
    for k, s in combined_strings.items():
        if len(s) > 10 and ' ' in s and not s.endswith(".GFF"):
            print(f"  [{k}] {s}")
            count += 1
            if count >= 25:
                break

if __name__ == "__main__":
    main()
