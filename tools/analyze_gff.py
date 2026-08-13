"""
GPLDATA.GFF Deep Parser
Goal: Understand the binary structure of GPL scripts
"""
import os, sys, struct, re
sys.stdout.reconfigure(encoding='utf-8')

GFF_PATH = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN\GPLDATA.GFF"
RGN02    = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN\RGN02.GFF"
OUT_DIR  = r"C:\Users\pmany\.gemini\antigravity-ide\brain\451cd7a2-e8a0-455b-9450-b4e9c8806586\scratch"

def hex_dump(data, offset=0, length=64, label=""):
    print(f"\n--- {label} @ +0x{offset:06X} ---")
    chunk = data[offset:offset+length]
    for i in range(0, len(chunk), 16):
        row = chunk[i:i+16]
        h = ' '.join(f'{b:02X}' for b in row)
        a = ''.join(chr(b) if 0x20<=b<0x7F else '.' for b in row)
        print(f"  {offset+i:06X}:  {h:<47}  {a}")

def find_all(data, pattern):
    positions = []
    pos = 0
    while True:
        p = data.find(pattern, pos)
        if p < 0: break
        positions.append(p)
        pos = p + 1
    return positions

def parse_gff_header(data, label=""):
    print(f"\n{'='*70}")
    print(f"GFF FILE: {label} ({len(data):,} bytes)")
    print('='*70)

    # GFF header structure (from JohnGlassmyer's dsun_music analysis)
    # First 4 bytes: signature or file type?
    hex_dump(data, 0, 64, "GFF Header (first 64 bytes)")

    # Find all 4-char tags in the file
    print("\n-- All 4-char tag occurrences --")
    known_tags = [b'GPL ', b'NAME', b'TEXT', b'SPIN', b'FONT', b'MAPS',
                  b'ANIM', b'CHAR', b'ITEM', b'BACK', b'SAVE', b'GMAP',
                  b'RDFF', b'BMP ', b'IT1R', b'RGTP']
    for tag in known_tags:
        positions = find_all(data, tag)
        if positions:
            print(f"  {tag.decode('ascii','replace')!r:8s}: {len(positions):4d} hits | "
                  f"first={positions[0]:06X} | last={positions[-1]:06X}")

    # Extract all readable strings
    strings = [(m.start(), m.group().decode('ascii','replace'))
               for m in re.finditer(rb'[\x20-\x7E]{5,}', data)]
    print(f"\n-- Readable strings: {len(strings)} --")
    for off, s in strings[:60]:
        print(f"  0x{off:06X}  {s[:100]}")

    return strings

def analyze_gpl_blocks(data, label=""):
    """Find and analyze GPL blocks in a GFF file"""
    print(f"\n{'='*70}")
    print(f"GPL BLOCK ANALYSIS in {label}")
    print('='*70)

    # Find all GPL occurrences (4-char tag with space: b'GPL ')
    # Also try without space
    for tag_variant in [b'GPL ', b'GPL\x00', b'GPL\x01', b'GPL\x02']:
        positions = find_all(data, tag_variant)
        if positions:
            print(f"\n  Tag {tag_variant!r}: {len(positions)} hits")
            for pos in positions[:5]:
                hex_dump(data, max(0,pos-16), 80, f"GPL block @ {pos:06X}")

    # The GFF format: look for the directory/index structure
    # GFF files typically have a table of (tag, offset, size) triples
    # Try to find such structures
    print("\n-- Looking for GFF directory structure --")

    # Try first 256 bytes as a potential header/directory
    hex_dump(data, 0, 256, "First 256 bytes of GFF")

    # Check if the file starts with a count
    if len(data) >= 4:
        count_word = struct.unpack_from('<H', data, 0)[0]
        count_dword = struct.unpack_from('<I', data, 0)[0]
        print(f"\n  First 2 bytes as count: {count_word}")
        print(f"  First 4 bytes as count: {count_dword}")

        # If it's a directory count, try to parse entries
        if 1 <= count_word <= 1000:
            print(f"\n  Trying to parse as {count_word}-entry directory:")
            offset = 2
            for i in range(min(count_word, 20)):
                if offset + 8 > len(data):
                    break
                # Each entry might be: tag(4) + offset(2) + size(2) = 8 bytes
                # or: tag(4) + offset(4) + size(4) = 12 bytes
                tag_b = data[offset:offset+4]
                off1  = struct.unpack_from('<H', data, offset+4)[0]
                sz1   = struct.unpack_from('<H', data, offset+6)[0]
                off2  = struct.unpack_from('<I', data, offset+4)[0]
                sz2   = struct.unpack_from('<I', data, offset+8)[0] if offset+12<=len(data) else 0
                tag_s = ''.join(chr(b) if 0x20<=b<0x7F else '.' for b in tag_b)
                print(f"    [{i:3d}] tag={tag_s!r}  8-byte: off={off1:04X} sz={sz1:04X} | "
                      f"12-byte: off={off2:08X} sz={sz2:08X}")
                offset += 8

        if 1 <= count_dword <= 10000:
            print(f"\n  Trying 4-byte count = {count_dword} (12-byte entries):")
            offset = 4
            for i in range(min(count_dword, 20)):
                if offset + 12 > len(data):
                    break
                tag_b = data[offset:offset+4]
                entry_off = struct.unpack_from('<I', data, offset+4)[0]
                entry_sz  = struct.unpack_from('<I', data, offset+8)[0]
                tag_s = ''.join(chr(b) if 0x20<=b<0x7F else '.' for b in tag_b)
                print(f"    [{i:3d}] tag={tag_s!r}  off=0x{entry_off:08X}  sz={entry_sz:08X}")
                offset += 12

def analyze_gpl_content(data, gff_label):
    """Try multiple GFF format interpretations"""
    print(f"\n{'='*70}")
    print(f"DEEP GPL CONTENT ANALYSIS: {gff_label}")
    print('='*70)

    # Try to find the start-of-data area
    # Often GFF files have: [4-byte magic] [4-byte count] [entries...]
    hex_dump(data, 0, 128, "First 128 bytes")

    # Look for repeating structures (could be entry table)
    # Find regions where every N bytes has similar structure
    print("\n-- Byte frequency in first 512 bytes --")
    first_512 = data[:512]
    freq = {}
    for b in first_512:
        freq[b] = freq.get(b, 0) + 1
    # Show top bytes
    top = sorted(freq.items(), key=lambda x: -x[1])[:16]
    for byte, count in top:
        bar = '#' * (count // 2)
        print(f"  0x{byte:02X} ({chr(byte) if 0x20<=byte<0x7F else ' '}): {count:4d} {bar}")

    # Check for null-terminated string blocks
    print("\n-- Null-terminated strings in first 4KB --")
    offset = 0
    chunk = data[:4096]
    while offset < len(chunk):
        end = chunk.find(b'\x00', offset)
        if end < 0: break
        s = chunk[offset:end]
        if len(s) >= 4 and all(0x20 <= b < 0x7F for b in s):
            print(f"  0x{offset:04X}: {s.decode('ascii','replace')}")
        offset = end + 1

def main():
    # Analyze GPLDATA.GFF
    if os.path.exists(GFF_PATH):
        gdata = open(GFF_PATH, "rb").read()
        parse_gff_header(gdata, "GPLDATA.GFF")
        analyze_gpl_blocks(gdata, "GPLDATA.GFF")
        analyze_gpl_content(gdata, "GPLDATA.GFF")
    else:
        print(f"[MISSING] {GFF_PATH}")

    # Analyze RGN02.GFF (smallest region, good for testing)
    if os.path.exists(RGN02):
        rdata = open(RGN02, "rb").read()
        parse_gff_header(rdata, "RGN02.GFF")
        analyze_gpl_content(rdata, "RGN02.GFF")
    else:
        print(f"[MISSING] {RGN02}")

    print("\n== GFF ANALYSIS COMPLETE ==")

main()
