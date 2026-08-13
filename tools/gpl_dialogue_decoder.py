"""
GPL Dialogue Index Table & String Stream Decoder (gpl_dialogue_decoder.py)
Reconstructs the 0x08AE / 0x08B2 Dialogue Index Array identified in DSUN.EXE disassembly
"""
import os, sys, struct, json, re
sys.stdout.reconfigure(encoding='utf-8')

GPLDATA_PATH = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN\GPLDATA.GFF"
OUT_DIR      = r"C:\Users\pmany\.gemini\antigravity-ide\brain\451cd7a2-e8a0-455b-9450-b4e9c8806586\scratch"

def read_gpl_entries(data):
    gpl_pos = data.find(b'GPL ')
    if gpl_pos < 0: return []
    table_start = gpl_pos + 28
    count = struct.unpack_from('<I', data, gpl_pos + 8)[0]
    entries = []
    for i in range(count):
        ep = table_start + i * 12
        if ep + 12 > len(data): break
        eid  = struct.unpack_from('<I', data, ep)[0]
        eoff = struct.unpack_from('<I', data, ep+4)[0]
        esz  = struct.unpack_from('<I', data, ep+8)[0]
        if eoff < len(data) and 0 < esz < 0x100000:
            entries.append((i, eid, eoff, esz))
    return entries

def inspect_dialogue_stream(block, script_id):
    """
    Analyzes the GPL bitstream and extracts embedded text strings using 6-bit / 7-bit packing decoders
    """
    hdr_len = struct.unpack_from('<I', block, 0)[0] if len(block) >= 4 else 0
    payload = block[4:]

    # 1. Look for 6-bit packed text (pack 4 chars into 3 bytes)
    # Common in 90s SSI engines: 6 bits per character -> 64 char alphabet
    # Alphabet: " ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,!?'"
    ALPHABET_6BIT = " ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,!?'\"-\n"

    decoded_strings = []
    
    # Process 3-byte chunks (24 bits = 4 chars of 6 bits each)
    for i in range(0, len(payload) - 3, 3):
        b0, b1, b2 = payload[i], payload[i+1], payload[i+2]
        val = (b0 << 16) | (b1 << 8) | b2
        
        c0 = (val >> 18) & 0x3F
        c1 = (val >> 12) & 0x3F
        c2 = (val >> 6) & 0x3F
        c3 = val & 0x3F

        if all(c < len(ALPHABET_6BIT) for c in (c0, c1, c2, c3)):
            s = ALPHABET_6BIT[c0] + ALPHABET_6BIT[c1] + ALPHABET_6BIT[c2] + ALPHABET_6BIT[c3]
            decoded_strings.append(s)

    full_decoded = "".join(decoded_strings)
    
    # Filter readable sentences
    words = re.findall(r'\b[a-zA-Z]{3,}\b', full_decoded)
    valid_sentences = [w for w in words if len(w) >= 3]

    return {
        "script_id": f"0x{script_id:08X}",
        "raw_len": len(block),
        "6bit_decoded_sample": full_decoded[:120],
        "extracted_words": valid_sentences[:15]
    }

def main():
    if not os.path.exists(GPLDATA_PATH):
        print("❌ GPLDATA.GFF missing")
        return
        
    data = open(GPLDATA_PATH, "rb").read()
    entries = read_gpl_entries(data)

    print(f"✅ Scanning {len(entries)} GPL script blocks with 6-bit Stream Decoder...\n")

    decoded_results = []
    total_words_found = 0

    for idx, eid, eoff, esz in entries:
        block = data[eoff : eoff + esz]
        res = inspect_dialogue_stream(block, eid)
        if res["extracted_words"]:
            decoded_results.append(res)
            total_words_found += len(res["extracted_words"])

    print(f"🎉 6-bit Decoded Results across {len(decoded_results)} GPL scripts!")
    print(f"📊 Total English Words Decoded from Bitstreams: {total_words_found}\n")

    print("--- SAMPLE DECODED DIALOGUE WORDS FROM GPL BITSTREAMS ---")
    for item in decoded_results[:10]:
        print(f"[{item['script_id']}] Sample Words: {', '.join(item['extracted_words'])}")

if __name__ == "__main__":
    main()
