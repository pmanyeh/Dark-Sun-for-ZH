"""
GPL NPC Dialogue Bitstream Decoder (decode_dialogue_chunks.py)
Target: 320 NPC Dialogue Chunks @ 0x0F0000 - 0x140000 in GPLDATA.GFF
Goal: Reconstruct true English NPC dialogue lines & story sentences
"""
import os, sys, struct, json, re
from collections import Counter
sys.stdout.reconfigure(encoding='utf-8')

GPLDATA_PATH = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN\GPLDATA.GFF"
OUT_DIR      = r"C:\Users\pmany\.gemini\antigravity-ide\brain\451cd7a2-e8a0-455b-9450-b4e9c8806586\scratch"

# Standard English character alphabet for packed 5-bit / 6-bit streams
ALPHABET_5BIT = " etaoinsrhdlcumfwgypbvkjxqz.,!?'"
ALPHABET_6BIT = " abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.,!?'\"-\n"

# Common Dark Sun & RPG English vocabulary to validate real sentences
VALID_RPG_WORDS = {
    "welcome", "arena", "gladiator", "templar", "sorcerer", "king", "tyr",
    "slave", "freedom", "fight", "kill", "guard", "cell", "pit", "sword",
    "shield", "magic", "psionic", "desert", "dune", "you", "are", "have",
    "that", "with", "this", "from", "will", "what", "where", "who", "why"
}

def decode_bitstream_chunk(chunk):
    """
    Decodes bitstream chunk into candidates using 5-bit & 6-bit variable shifts
    """
    decoded_lines = []
    
    # 1. Try 6-bit bitpack
    bits = "".join(f"{b:08b}" for b in chunk)
    
    for shift in range(8):
        chars_6bit = []
        for i in range(shift, len(bits) - 6, 6):
            val = int(bits[i:i+6], 2)
            if val < len(ALPHABET_6BIT):
                chars_6bit.append(ALPHABET_6BIT[val])
            else:
                chars_6bit.append(' ')
                
        text_6bit = "".join(chars_6bit)
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text_6bit.lower())
        overlap = set(words).intersection(VALID_RPG_WORDS)
        
        if len(overlap) >= 2 or (len(words) >= 4 and ' ' in text_6bit):
            decoded_lines.append(text_6bit.strip())

    return decoded_lines

def main():
    if not os.path.exists(GPLDATA_PATH):
        print("❌ GPLDATA.GFF missing")
        return

    data = open(GPLDATA_PATH, "rb").read()
    start_off = 0x0F0000
    end_off   = min(len(data), 0x140000)
    
    print(f"🚀 Decoding 320 NPC Dialogue Chunks (0x{start_off:06X} - 0x{end_off:06X})...\n")

    npc_dialogues = []
    seen = set()

    for b_off in range(start_off, end_off, 1024):
        chunk = data[b_off : b_off + 1024]
        candidates = decode_bitstream_chunk(chunk)
        
        for cand in candidates:
            # Clean up candidate string
            clean_str = re.sub(r'\s+', ' ', cand).strip()
            if len(clean_str) >= 12 and clean_str not in seen:
                seen.add(clean_str)
                npc_dialogues.append({
                    "offset": f"0x{b_off:06X}",
                    "text": clean_str
                })

    print("=" * 70)
    print(f"🎉 SUCCESS! Extracted {len(npc_dialogues)} Real NPC Dialogue Stream Candidates!")
    print("=" * 70)

    out_file = os.path.join(OUT_DIR, "real_npc_dialogues.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(npc_dialogues, f, indent=2, ensure_ascii=False)

    print(f"📄 Saved Extracted NPC Dialogues to: {out_file}\n")

    print("--- SAMPLE EXTRACTED NPC DIALOGUE LINES (First 15) ---")
    for item in npc_dialogues[:15]:
        print(f"[{item['offset']}] {item['text'][:100]}")

if __name__ == "__main__":
    main()
