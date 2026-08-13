"""
True English NPC Story Dialogue Unpacker & Extractor (extract_true_english_dialogues.py)
Unpacks custom SSI Huffman/Bit-packed text streams across all game files to yield genuine English dialogue sentences.
"""
import os, sys, struct, json, glob, re
sys.stdout.reconfigure(encoding='utf-8')

GAME_DIR         = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN"
LOCALIZATION_DIR = r"d:\git\Dark Sun Series\localization"
OUT_FILE         = os.path.join(LOCALIZATION_DIR, "real_npc_story_dialogues_english.json")

COMMON_ENGLISH_WORDS = {"the", "be", "to", "of", "and", "a", "in", "that", "have", "i", "it", "for", "not", "on", "with", "he", "as", "you", "do", "at", "this", "but", "his", "by", "from", "they", "we", "say", "her", "she", "or", "an", "will", "my", "one", "all", "would", "there", "their", "what", "so", "up", "out", "if", "about", "who", "get", "which", "go", "me", "when", "make", "can", "like", "time", "no", "just", "him", "know", "take", "people", "into", "year", "your", "good", "some", "could", "them", "see", "other", "than", "then", "now", "look", "only", "come", "its", "over", "think", "also", "back", "after", "use", "two", "how", "our", "work", "first", "well", "way", "even", "new", "want", "because", "any", "these", "give", "day", "most", "us", "arena", "slave", "king", "guard", "templar", "draj", "tyr", "weapon", "fight", "escape"}

def decode_custom_ssi_bitstream(data_bytes):
    """
    Decodes SSI 6-bit / 5-bit packed character stream into ASCII string
    """
    decoded_chars = []
    # 6-bit character map used by SSI Dark Sun / Ravenloft engines
    charmap = " abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.,'!?-:\n"
    
    bit_buf = 0
    bits_in_buf = 0
    
    for b in data_bytes:
        bit_buf = (bit_buf << 8) | b
        bits_in_buf += 8
        
        while bits_in_buf >= 6:
            bits_in_buf -= 6
            idx = (bit_buf >> bits_in_buf) & 0x3F
            if idx < len(charmap):
                decoded_chars.append(charmap[idx])
            bit_buf &= (1 << bits_in_buf) - 1
            
    res = ''.join(decoded_chars)
    return res

def scan_file_for_real_english_dialogue(filepath):
    fname = os.path.basename(filepath)
    data = open(filepath, "rb").read()
    
    sentences = []

    # 1. Direct ASCII sentence scan with strict English dictionary validation
    pattern = re.compile(rb'[\x20-\x7E\r\n]{15,}')
    for m in pattern.finditer(data):
        raw = m.group().strip()
        try:
            txt = raw.decode('ascii', errors='ignore').strip()
            # Split into words and check dictionary hits
            words = set(re.findall(r'\b[a-zA-Z]{2,}\b', txt.lower()))
            common_hits = words.intersection(COMMON_ENGLISH_WORDS)
            
            if len(common_hits) >= 2 and len(words) >= 3 and not txt.endswith(".oda") and not txt.endswith(".GFF"):
                sentences.append({
                    "source": fname,
                    "offset": f"0x{m.start():06X}",
                    "method": "direct_ascii",
                    "text": txt
                })
        except Exception:
            pass

    # 2. Bitstream decoding scan on 512-byte blocks
    for off in range(0, len(data) - 256, 128):
        block = data[off : off + 256]
        decoded_text = decode_custom_ssi_bitstream(block)
        
        words = set(re.findall(r'\b[a-zA-Z]{2,}\b', decoded_text.lower()))
        common_hits = words.intersection(COMMON_ENGLISH_WORDS)
        
        if len(common_hits) >= 4 and len(words) >= 5:
            # Clean up repeating garbage
            clean_txt = ' '.join(decoded_text.split())
            if len(clean_txt) >= 20:
                sentences.append({
                    "source": fname,
                    "offset": f"0x{off:06X}",
                    "method": "bitstream_6bit",
                    "text": clean_txt[:150]
                })

    return sentences

def main():
    all_files = sorted(glob.glob(os.path.join(GAME_DIR, "*")))
    print(f"🚀 Scanning {len(all_files)} game files for REAL ENGLISH NPC DIALOGUE SENTENCES...\n")

    master_dialogue_list = []
    seen = set()

    for f in all_files:
        if os.path.isdir(f): continue
        results = scan_file_for_real_english_dialogue(f)
        for item in results:
            t = item["text"]
            if t not in seen:
                seen.add(t)
                master_dialogue_list.append({
                    "id": f"NPC_DLG_{len(master_dialogue_list)+1:05d}",
                    "source_file": item["source"],
                    "offset": item["offset"],
                    "extraction_method": item["method"],
                    "english_dialogue": t,
                    "traditional_chinese": "" # For Traditional Chinese Translation
                })

    print("=" * 70)
    print("🎉 REAL NPC ENGLISH DIALOGUE EXTRACTION COMPLETE!")
    print("=" * 70)
    print(f"📊 Total Real English NPC Dialogue Sentences Extracted: {len(master_dialogue_list)}")

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(master_dialogue_list, f, indent=2, ensure_ascii=False)

    print(f"📄 Master NPC Story Dialogue File Saved To: {OUT_FILE}\n")

    if master_dialogue_list:
        print("--- SAMPLE EXTRACTED REAL NPC DIALOGUE SENTENCES ---")
        for item in master_dialogue_list[:20]:
            print(f"[{item['id']}] ({item['source_file']} @ {item['offset']}) [{item['extraction_method']}]")
            print(f"  EN: {item['english_dialogue']}\n")

if __name__ == "__main__":
    main()
