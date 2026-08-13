"""
GPL Script Brute-Force Decryptor / Heuristic Analyzer
Target: 217 GPL script blocks in GPLDATA.GFF
Goal: Discover encryption algorithm or compression header
"""
import os, sys, struct, re
from collections import Counter
sys.stdout.reconfigure(encoding='utf-8')

GPLDATA_PATH = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN\GPLDATA.GFF"
OUT_DIR      = r"C:\Users\pmany\.gemini\antigravity-ide\brain\451cd7a2-e8a0-455b-9450-b4e9c8806586\scratch"

def read_gpl_entries(data):
    """Parse the 217 GPL entries from GPLDATA.GFF"""
    gpl_pos = data.find(b'GPL ')
    if gpl_pos < 0:
        return []
    
    # Entry table starts at gpl_pos + 28 (0x150CB0)
    table_start = gpl_pos + 28
    count = struct.unpack_from('<I', data, gpl_pos + 8)[0]  # 0xD9 = 217
    
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

def score_ascii(buf):
    """Calculate percentage of printable ASCII characters"""
    if not buf: return 0.0
    printable = sum(1 for b in buf if (0x20 <= b <= 0x7E) or b in (0x09, 0x0A, 0x0D))
    return printable / len(buf)

def try_xor_decryption(block):
    """Try single-byte XOR keys 0x00..0xFF"""
    best_score = 0.0
    best_key = 0
    best_text = b""
    
    for key in range(256):
        decrypted = bytes(b ^ key for b in block)
        score = score_ascii(decrypted)
        if score > best_score:
            best_score = score
            best_key = key
            best_text = decrypted
            
    return best_key, best_score, best_text

def try_shift_decryption(block):
    """Try ADD/SUB byte offsets -128..127"""
    best_score = 0.0
    best_shift = 0
    best_text = b""
    
    for shift in range(-128, 128):
        decrypted = bytes((b + shift) & 0xFF for b in block)
        score = score_ascii(decrypted)
        if score > best_score:
            best_score = score
            best_shift = shift
            best_text = decrypted
            
    return best_shift, best_score, best_text

def analyze_compression_headers(block):
    """Check for common DOS compression magic numbers"""
    if len(block) < 4: return None
    
    magic2 = block[:2]
    magic4 = block[:4]
    
    if magic2 == b'PK': return "ZIP / PKZIP"
    if magic2 in (b'LZ', b'SZ'): return "LZSS / DOS LZ"
    if magic2 == b'\x1f\x8b': return "GZIP"
    if magic2 == b'BZh': return "BZIP2"
    
    # Check if first 2 or 4 bytes represent decompressed size
    sz_16 = struct.unpack_from('<H', block, 0)[0]
    sz_32 = struct.unpack_from('<I', block, 0)[0]
    
    return f"FirstWord={sz_16} (0x{sz_16:04X}), FirstDWord={sz_32} (0x{sz_32:08X})"

def main():
    print("=" * 70)
    print("GPL BLOCK DECRYPTION & ANALYSIS TEST")
    print("=" * 70)
    
    if not os.path.exists(GPLDATA_PATH):
        print(f"❌ File not found: {GPLDATA_PATH}")
        return
        
    data = open(GPLDATA_PATH, "rb").read()
    entries = read_gpl_entries(data)
    print(f"✅ Found {len(entries)} GPL entries in GPLDATA.GFF\n")
    
    # Sample first 20 blocks
    results = []
    high_ascii_count = 0
    
    print(f"{'Idx':<4} {'ID':<10} {'Size':<6} {'Orig ASCII%':<12} {'Best XOR':<10} {'XOR ASCII%':<12} {'Best Shift':<12} {'Shift ASCII%':<12}")
    print("-" * 90)
    
    for idx, eid, eoff, esz in entries[:30]:
        block = data[eoff:eoff+esz]
        orig_score = score_ascii(block)
        
        xor_key, xor_score, xor_text = try_xor_decryption(block)
        shift_val, shift_score, shift_text = try_shift_decryption(block)
        
        print(f"{idx:<4} 0x{eid:08X} {esz:<6} {orig_score*100:<12.1f} 0x{xor_key:02X} ({xor_key:<3}) {xor_score*100:<12.1f} {shift_val:<12} {shift_score*100:<12.1f}")
        
        if orig_score > 0.6 or xor_score > 0.6 or shift_score > 0.6:
            high_ascii_count += 1
            
        results.append((idx, eid, eoff, esz, block, xor_key, xor_score, xor_text))

    print("-" * 90)
    print(f"Summary: Analyzed 30 sample blocks. High ASCII candidates: {high_ascii_count}\n")
    
    # Show detail for Block 0 (Main script)
    print("=" * 70)
    print("DETAILED SCAN FOR BLOCK 0 (id=0x00000000, size=608 bytes)")
    print("=" * 70)
    b0 = data[entries[0][2] : entries[0][2] + entries[0][3]]
    
    print("Header info:", analyze_compression_headers(b0))
    print("\nRaw Hex Dump (First 64 bytes):")
    for i in range(0, min(64, len(b0)), 16):
        row = b0[i:i+16]
        h = ' '.join(f'{b:02X}' for b in row)
        a = ''.join(chr(b) if 0x20<=b<=0x7E else '.' for b in row)
        print(f"  {i:04X}:  {h:<47}  {a}")

    # Test rolling XOR or multi-byte XOR
    print("\nTesting 2-byte XOR patterns...")
    best_2b_score = 0.0
    best_2b_k = (0, 0)
    for k1 in range(256):
        for k2 in range(256):
            dec = bytes(b0[i] ^ (k1 if i%2==0 else k2) for i in range(len(b0)))
            sc = score_ascii(dec)
            if sc > best_2b_score:
                best_2b_score = sc
                best_2b_k = (k1, k2)
    print(f"Best 2-byte XOR: key=({best_2b_k[0]:02X},{best_2b_k[1]:02X}), ASCII={best_2b_score*100:.1f}%")
    if best_2b_score > 0.4:
        dec = bytes(b0[i] ^ (best_2b_k[0] if i%2==0 else best_2b_k[1]) for i in range(len(b0)))
        print("Decrypted sample:", dec[:100])

if __name__ == "__main__":
    main()
