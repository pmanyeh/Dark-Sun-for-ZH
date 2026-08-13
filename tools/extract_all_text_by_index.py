"""
Master Text Index Table & Dialogue Extractor (extract_all_text_by_index.py)
Uses the 16-bit Text ID index table at DSUN.EXE (0x0677B6 & 0x077B2F)
and the GFF text lookup block at RESOURCE.GFF (0x05219B) to decode all story dialogue text!
"""
import os, sys, struct, json, re
sys.stdout.reconfigure(encoding='utf-8')

GAME_DIR         = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN"
EXE_PATH         = os.path.join(GAME_DIR, "DSUN.EXE")
RES_PATH         = os.path.join(GAME_DIR, "RESOURCE.GFF")
LOCALIZATION_DIR = r"d:\git\Dark Sun Series\localization"
OUT_FILE         = os.path.join(LOCALIZATION_DIR, "real_extracted_story_dialogues.json")

def parse_text_id_array(data, off, count):
    """Parses 16-bit uint16_t Text ID array from DSUN.EXE"""
    text_ids = []
    for i in range(count):
        tid = struct.unpack_from('<H', data, off + i * 2)[0]
        text_ids.append(tid)
        
    return text_ids

def decode_ssi_text_chunk(chunk_data):
    """
    Decodes an SSI Dark Sun compressed text chunk into string
    """
    decoded = []
    charmap = " abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.,'!?-:\n"
    
    bit_buf = 0
    bits = 0
    
    for b in chunk_data:
        bit_buf = (bit_buf << 8) | b
        bits += 8
        while bits >= 6:
            bits -= 6
            idx = (bit_buf >> bits) & 0x3F
            if idx < len(charmap):
                decoded.append(charmap[idx])
            bit_buf &= (1 << bits) - 1
            
    return ''.join(decoded)

def main():
    exe_data = open(EXE_PATH, "rb").read()
    res_data = open(RES_PATH, "rb").read()

    print("🚀 Extracting 16-bit Text ID Index Table from DSUN.EXE @ 0x0677B6...")

    # Read 200 Text IDs from table 1 and table 2
    tids_1 = parse_text_id_array(exe_data, 0x0677B6, 120)
    tids_2 = parse_text_id_array(exe_data, 0x077B2F, 120)
    all_tids = sorted(list(set(tids_1 + tids_2)))

    print(f"✅ Found {len(all_tids)} unique Text IDs in master index table!")
    print(f"  Sample Text IDs: {[hex(t) for t in all_tids[:10]]}")

    # Process RESOURCE.GFF around 0x05219B
    text_resource_block = res_data[0x052000 : 0x070000]
    
    extracted_story = []
    seen = set()

    # Iterate through chunks inside text resource block
    for tid in all_tids:
        # Search for tid pattern inside RESOURCE text block
        tid_pattern = struct.pack('<H', tid)
        pos = 0
        while True:
            p = text_resource_block.find(tid_pattern, pos)
            if p < 0: break
            
            # Read chunk payload after pointer
            sub_chunk = text_resource_block[p+2 : p+128]
            decoded_s = decode_ssi_text_chunk(sub_chunk)
            
            # Clean up and find English sentences
            clean_s = ' '.join(decoded_s.split()).strip()
            if len(clean_s) >= 10 and clean_s not in seen:
                seen.add(clean_s)
                extracted_story.append({
                    "id": f"STORY_TEXT_{len(extracted_story)+1:05d}",
                    "text_id": f"0x{tid:04X}",
                    "gff_offset": f"0x{0x052000 + p:06X}",
                    "english_dialogue": clean_s,
                    "traditional_chinese": "" # Ready for Traditional Chinese Translation
                })
            pos = p + 1

    print("=" * 70)
    print("🎉 MASTER STORY DIALOGUE EXTRACTION COMPLETE!")
    print("=" * 70)
    print(f"📊 Total Extracted Master Story Dialogue Lines: {len(extracted_story)}")

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(extracted_story, f, indent=2, ensure_ascii=False)

    print(f"📄 Saved Master Story Dialogue File: {OUT_FILE}\n")

    if extracted_story:
        print("--- SAMPLE EXTRACTED STORY DIALOGUE LINES (First 15) ---")
        for item in extracted_story[:15]:
            print(f"[{item['id']}] (TextID {item['text_id']} @ {item['gff_offset']})")
            print(f"  EN: {item['english_dialogue']}\n")

if __name__ == "__main__":
    main()
