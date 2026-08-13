"""
GPL Dialogue Reconstructor & Master Table Integrator (gpl_dialogue_reconstructor.py)
Uses 6-bit Bitstream Decoding to extract full English dialogue sentences from all 216 GPL blocks
Integrates decoded dialogue directly into DarkSun_Dialogue_Translation_Table.json
"""
import os, sys, struct, json, re
sys.stdout.reconfigure(encoding='utf-8')

LOCALIZATION_DIR = r"d:\git\Dark Sun Series\localization"
GPLDATA_PATH     = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN\GPLDATA.GFF"
OUT_TABLE        = os.path.join(LOCALIZATION_DIR, "DarkSun_Dialogue_Translation_Table.json")

ALPHABET_6BIT = " ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,!?'\"-\n"

def decode_6bit_bitstream(payload):
    decoded_chars = []
    for i in range(0, len(payload) - 3, 3):
        b0, b1, b2 = payload[i], payload[i+1], payload[i+2]
        val = (b0 << 16) | (b1 << 8) | b2
        
        c0 = (val >> 18) & 0x3F
        c1 = (val >> 12) & 0x3F
        c2 = (val >> 6) & 0x3F
        c3 = val & 0x3F
        
        for c in (c0, c1, c2, c3):
            if c < len(ALPHABET_6BIT):
                decoded_chars.append(ALPHABET_6BIT[c])

    text = "".join(decoded_chars)
    
    # Extract clean readable segments
    segments = [s.strip() for s in re.split(r'[\r\n\t]+', text) if len(s.strip()) >= 4]
    return segments

def main():
    if not os.path.exists(GPLDATA_PATH) or not os.path.exists(OUT_TABLE):
        print("❌ Missing prerequisite files")
        return

    data = open(GPLDATA_PATH, "rb").read()
    current_table = json.load(open(OUT_TABLE, encoding='utf-8'))

    print(f"✅ Loaded current Master Table ({len(current_table)} items)")
    print(f"✅ Scanning GPLDATA.GFF with 6-bit Bitstream Reconstruction Engine...")

    gpl_pos = data.find(b'GPL ')
    if gpl_pos < 0:
        print("❌ GPL tag not found")
        return

    table_start = gpl_pos + 28
    count = struct.unpack_from('<I', data, gpl_pos + 8)[0]
    
    reconstructed_entries = []
    seen = set()

    # Retain existing clean items (e.g. items, spells, driver strings)
    for item in current_table:
        seen.add(item["original_en"])
        reconstructed_entries.append(item)

    # Add 6-bit decoded dialogue lines from 216 GPL blocks
    for i in range(count):
        ep = table_start + i * 12
        if ep + 12 > len(data): break
        eid  = struct.unpack_from('<I', data, ep)[0]
        eoff = struct.unpack_from('<I', data, ep+4)[0]
        esz  = struct.unpack_from('<I', data, ep+8)[0]
        
        if eoff < len(data) and 4 < esz < 0x100000:
            block = data[eoff+4 : eoff+esz]
            segments = decode_6bit_bitstream(block)
            
            for seg in segments:
                # Filter meaningful segments
                words = re.findall(r'\b[a-zA-Z]{2,}\b', seg)
                if len(words) >= 2 and seg not in seen:
                    seen.add(seg)
                    reconstructed_entries.append({
                        "entry_id": f"DS_TXT_{len(reconstructed_entries)+1:05d}",
                        "resource_key": f"GPL_0x{eid:08X}",
                        "original_en": seg,
                        "translated_zh": "",
                        "status": "pending"
                    })

    print(f"\n🎉 Reconstructed Total {len(reconstructed_entries)} Dialogue & Text Entries!")

    with open(OUT_TABLE, "w", encoding="utf-8") as f:
        json.dump(reconstructed_entries, f, indent=2, ensure_ascii=False)

    print(f"📄 Saved Reconstructed Master Table to: {OUT_TABLE}")

    print("\n--- PREVIEW OF RECONSTRUCTED DIALOGUE ENTRIES (Sample Lines) ---")
    for item in reconstructed_entries[-20:]:
        print(f"[{item['entry_id']}] ({item['resource_key']})")
        print(f"  EN: {item['original_en']}\n")

if __name__ == "__main__":
    main()
