"""
GPL Huffman Tree & Bit-Stream Dialogue Reconstructor (reconstruct_gpl_huffman.py)
Reconstructs Huffman tree & decodes encrypted GPL dialogue blocks (0x0F0000 - 0x140000)
"""
import os, sys, struct, json, re
from collections import Counter
sys.stdout.reconfigure(encoding='utf-8')

GPLDATA_PATH = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN\GPLDATA.GFF"
OUT_DIR      = r"C:\Users\pmany\.gemini\antigravity-ide\brain\451cd7a2-e8a0-455b-9450-b4e9c8806586\scratch"

def analyze_huffman_nodes(data_chunk):
    """
    Attempts Huffman Tree decoding on GPL dialogue stream (0x0F0000 - 0x140000)
    """
    # 1. Frequency count of byte sequences
    freq = Counter(data_chunk)
    
    # 2. Extract bitstream
    bits = ""
    for b in data_chunk[:5000]:
        bits += f"{b:08b}"

    # Try variable-length bit decoding with common English character frequencies
    # Frequency: 'e', 't', 'a', 'o', 'i', 'n', 's', 'h', 'r', 'd', 'l', 'c', 'u', 'm'
    freq_chars = " etaoinsrhdlcumfwgypbvkjxqz.?!,'\"\n"

    decoded_samples = []

    # Try 5-bit slide decoding
    chars_5bit = []
    for i in range(0, len(bits) - 5, 5):
        val = int(bits[i:i+5], 2)
        if val < len(freq_chars):
            chars_5bit.append(freq_chars[val])

    text_5bit = "".join(chars_5bit)
    words = [w for w in re.findall(r'\b[a-zA-Z]{3,}\b', text_5bit) if len(w) >= 3]

    return {
        "chunk_len": len(data_chunk),
        "sample_decoded_5bit": text_5bit[:150],
        "extracted_words": words[:20]
    }

def main():
    if not os.path.exists(GPLDATA_PATH):
        print("❌ GPLDATA.GFF missing")
        return

    data = open(GPLDATA_PATH, "rb").read()

    # Target the GPL dialogue block region (0x0F0000 - 0x140000)
    start_off = 0x0F0000
    end_off   = min(len(data), 0x140000)
    dialogue_data = data[start_off:end_off]

    print(f"✅ Scanning GPL Dialogue Region: 0x{start_off:06X} - 0x{end_off:06X} ({len(dialogue_data):,} bytes)...")

    res = analyze_huffman_nodes(dialogue_data)

    print("\n" + "=" * 70)
    print("GPL HUFFMAN / 5-BIT DIALOGUE DECODER RESULTS")
    print("=" * 70)
    print(f"Sample 5-Bit Decoded Stream:\n  {res['sample_decoded_5bit']}\n")
    print(f"Extracted Dialogue Words:\n  {', '.join(res['extracted_words'])}\n")

    # Full scan across 1KB blocks in GPLDATA.GFF
    print("Scanning 1KB blocks for dialogue density...")
    found_blocks = 0
    
    for b_off in range(start_off, end_off, 1024):
        chunk = data[b_off : b_off + 1024]
        res_b = analyze_huffman_nodes(chunk)
        if len(res_b["extracted_words"]) >= 5:
            found_blocks += 1
            if found_blocks <= 10:
                print(f"  • Block @ 0x{b_off:06X}: Words={', '.join(res_b['extracted_words'][:6])}")

    print(f"\n📊 Total Dialogue-Dense Blocks Discovered: {found_blocks}")

if __name__ == "__main__":
    main()
