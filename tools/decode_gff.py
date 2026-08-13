"""
GFF Format Decoder - Based on actual file analysis
Key finding: GFFI signature, GPL tag at 0x150C94 and 0x151084
"""
import os, sys, struct, re
sys.stdout.reconfigure(encoding='utf-8')

GPLDATA = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN\GPLDATA.GFF"
RGN02   = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN\RGN02.GFF"
OUT_DIR = r"C:\Users\pmany\.gemini\antigravity-ide\brain\451cd7a2-e8a0-455b-9450-b4e9c8806586\scratch"

def hex_dump(data, offset=0, length=64, label=""):
    if label: print(f"\n--- {label} ---")
    chunk = data[offset:offset+length]
    for i in range(0, len(chunk), 16):
        row = chunk[i:i+16]
        h = ' '.join(f'{b:02X}' for b in row)
        a = ''.join(chr(b) if 0x20<=b<0x7F else '.' for b in row)
        print(f"  {offset+i:06X}:  {h:<47}  {a}")

def analyze_gff_structure(data, filename):
    print(f"\n{'='*70}")
    print(f"GFF STRUCTURE DECODE: {filename} ({len(data):,} bytes)")
    print('='*70)

    # GFF magic: b'GFFI'
    if data[:4] != b'GFFI':
        print(f"  [!] Not a GFFI file! Header: {data[:4]!r}")
        return

    print(f"  Magic: GFFI confirmed")

    # Bytes 4-7: unknown (00 00 03 00 in both files -> might be version 3?)
    ver = struct.unpack_from('<I', data, 4)[0]
    print(f"  Version/Flags @ 4: 0x{ver:08X}")

    # Bytes 8-11: 0x0000001C = 28 -> likely the header size or first entry offset
    hdr_field = struct.unpack_from('<I', data, 8)[0]
    print(f"  Field @ 8: 0x{hdr_field:08X} (decimal: {hdr_field})")

    # In GPLDATA.GFF: bytes 12-15 = BE 09 15 00 = 0x001509BE = 1,378,750
    # That's close to the file size (1,383,098), likely total data size or end of data
    field_c = struct.unpack_from('<I', data, 12)[0]
    print(f"  Field @ C: 0x{field_c:08X} (decimal: {field_c})")

    # Bytes 16-19: F4 02 00 00 = 0x2F4 = 756 (GPLDATA) / 78 00 00 00 = 120 (RGN02)
    field_10 = struct.unpack_from('<I', data, 16)[0]
    print(f"  Field @10: 0x{field_10:08X} (decimal: {field_10})")

    # At offset 0x1C (28 = hdr_field): entry table starts?
    print(f"\n  Trying entry table at offset 0x{hdr_field:X}:")
    hex_dump(data, hdr_field, 64, f"Potential entry table start @ 0x{hdr_field:X}")

    # For GPLDATA.GFF: GPL tags are at 0x150C94 and 0x151084
    # Analyze what's at GPL block @ 0x150C94
    gpl_pos = data.find(b'GPL ')
    if gpl_pos >= 0:
        print(f"\n{'='*50}")
        print(f"  GPL tag found at 0x{gpl_pos:06X}")
        hex_dump(data, gpl_pos - 32, 200, f"Full GPL block context @ 0x{gpl_pos:06X}")

        # Analyze structure around GPL tag
        # From the dump:
        # -16: 26 00 00 00 = 0x26 = 38
        # -12: 08 00 00 00 = 8
        # -8:  63 00 00 00 = 99
        # -4:  01 00 00 00 = 1
        # +0:  47 50 4C 20 = 'GPL '
        # +4:  D9 00 00 80 = 0x800000D9 (flag + offset?)
        # +8:  D9 00 00 00 = 0xD9 = 217
        # +12: 08 00 00 00 = 8
        # +16: 01 00 00 00 = 1
        # +20: 01 00 00 00 = 1
        # +24: D9 00 00 00 = 217

        p = gpl_pos
        tag   = data[p:p+4].decode('ascii','replace')
        f1    = struct.unpack_from('<I', data, p+4)[0]
        f2    = struct.unpack_from('<I', data, p+8)[0]
        f3    = struct.unpack_from('<I', data, p+12)[0]
        f4    = struct.unpack_from('<I', data, p+16)[0]
        f5    = struct.unpack_from('<I', data, p+20)[0]
        f6    = struct.unpack_from('<I', data, p+24)[0]

        print(f"\n  GPL Entry Structure:")
        print(f"    tag     = {tag!r}")
        print(f"    field+4 = 0x{f1:08X} ({f1})")
        print(f"    field+8 = 0x{f2:08X} ({f2})")
        print(f"    field+C = 0x{f3:08X} ({f3})")
        print(f"    field+10= 0x{f4:08X} ({f4})")
        print(f"    field+14= 0x{f5:08X} ({f5})")
        print(f"    field+18= 0x{f6:08X} ({f6})")

        # The GPL data seems to be a table of (id, offset, size) triples after the header
        # GPL block +28: 28 E8 11 00 60 02 00 00 12 10 00 00
        # These look like: offset=0x11E828, size=0x260, id=0x1012
        # Let's try:
        table_start = p + 28
        print(f"\n  Trying to parse GPL entry table at +0x{table_start:06X}:")
        print(f"  (each row: entry_id(4) + data_offset(4) + data_size(4) = 12 bytes)")
        print(f"  Count from field+C = {f2} entries?\n")

        # How many entries? field+8 or field+C might be count
        # f2 = 0xD9 = 217... let's try that
        count = min(f2, 300)
        total_text_found = 0
        for i in range(count):
            ep = table_start + i*12
            if ep + 12 > len(data): break
            eid  = struct.unpack_from('<I', data, ep)[0]
            eoff = struct.unpack_from('<I', data, ep+4)[0]
            esz  = struct.unpack_from('<I', data, ep+8)[0]

            # Sanity check: valid offset and size?
            if eoff < len(data) and esz < 0x100000 and esz > 0:
                # Peek at data
                chunk = data[eoff:eoff+min(esz,64)]
                strings = [m.group().decode('ascii','replace')
                           for m in re.finditer(rb'[\x20-\x7E]{4,}', chunk)]
                text = ' | '.join(strings[:3]) if strings else ''
                total_text_found += len(strings)
                if i < 20 or strings:
                    print(f"    [{i:3d}] id=0x{eid:08X}  off=0x{eoff:08X}  sz=0x{esz:06X}  {text[:60]}")
            else:
                if i < 5:
                    print(f"    [{i:3d}] id=0x{eid:08X}  off=0x{eoff:08X}  sz=0x{esz:06X}  [invalid]")
                break

        print(f"\n  Total text strings found in entries: {total_text_found}")

    # Check second GPL block
    gpl2 = data.find(b'GPL ', gpl_pos+1)
    if gpl2 >= 0:
        print(f"\n{'='*50}")
        print(f"  Second GPL tag at 0x{gpl2:06X}")
        hex_dump(data, gpl2 - 16, 200, f"Second GPL block @ 0x{gpl2:06X}")

        p2 = gpl2
        f1 = struct.unpack_from('<I', data, p2+4)[0]
        f2 = struct.unpack_from('<I', data, p2+8)[0]
        f3 = struct.unpack_from('<I', data, p2+12)[0]
        print(f"\n  Second GPL Entry: count_candidate={f2}, f3={f3}")

        # Try parsing this table too
        table2 = p2 + 28
        print(f"  Trying table at +0x{table2:06X} with up to {min(f2,20)} entries:")
        for i in range(min(f2, 20)):
            ep = table2 + i*12
            if ep + 12 > len(data): break
            eid  = struct.unpack_from('<I', data, ep)[0]
            eoff = struct.unpack_from('<I', data, ep+4)[0]
            esz  = struct.unpack_from('<I', data, ep+8)[0]
            if eoff < len(data) and esz < 0x100000:
                chunk = data[eoff:eoff+min(esz,64)]
                strings = [m.group().decode('ascii','replace')
                           for m in re.finditer(rb'[\x20-\x7E]{4,}', chunk)]
                text = ' | '.join(strings[:3]) if strings else ''
                print(f"    [{i:3d}] id=0x{eid:08X}  off=0x{eoff:08X}  sz=0x{esz:06X}  {text[:70]}")
            else:
                print(f"    [{i:3d}] id=0x{eid:08X}  off=0x{eoff:08X}  sz=0x{esz:06X}  [invalid range]")
                break

def main():
    for path, name in [(GPLDATA, "GPLDATA.GFF"), (RGN02, "RGN02.GFF")]:
        if os.path.exists(path):
            d = open(path, "rb").read()
            analyze_gff_structure(d, name)
        else:
            print(f"[MISSING] {path}")

    print("\n== DONE ==")

main()
