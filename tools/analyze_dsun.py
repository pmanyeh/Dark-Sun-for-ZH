import os, sys, struct, re
sys.stdout.reconfigure(encoding='utf-8')

EXE_PATH = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN\DSUN.EXE"
OUT_DIR  = r"C:\Users\pmany\.gemini\antigravity-ide\brain\451cd7a2-e8a0-455b-9450-b4e9c8806586\scratch"

def main():
    data = open(EXE_PATH, "rb").read()
    print(f"[OK] DSUN.EXE size: {len(data):,} bytes ({len(data)/1024:.1f} KB)")

    # ── 1. MZ Header ──
    print("\n== DOS MZ Header ==")
    sig = data[:2]
    last_bytes  = struct.unpack_from('<H', data, 2)[0]
    pages       = struct.unpack_from('<H', data, 4)[0]
    relocs      = struct.unpack_from('<H', data, 6)[0]
    hdr_para    = struct.unpack_from('<H', data, 8)[0]
    ss          = struct.unpack_from('<H', data, 14)[0]
    sp          = struct.unpack_from('<H', data, 16)[0]
    ip          = struct.unpack_from('<H', data, 20)[0]
    cs          = struct.unpack_from('<H', data, 22)[0]
    print(f"  Signature  : {sig}")
    print(f"  File pages : {pages}  ({pages*512} bytes total from header)")
    print(f"  Relocs     : {relocs}")
    print(f"  Header size: {hdr_para*16} bytes ({hdr_para} paragraphs)")
    print(f"  Initial CS:IP = {cs:04X}:{ip:04X}")
    print(f"  Initial SS:SP = {ss:04X}:{sp:04X}")

    # ── 2. String Extraction ──
    print("\n== String Extraction (min len=5) ==")
    all_strings = [(m.start(), m.group().decode('ascii','replace'))
                   for m in re.finditer(rb'[\x20-\x7E]{5,}', data)]
    print(f"  Total strings: {len(all_strings)}")

    strings_file = os.path.join(OUT_DIR, "dsun_strings.txt")
    with open(strings_file, "w", encoding="utf-8") as f:
        f.write(f"DSUN.EXE string dump — {len(all_strings)} strings\n\n")
        for off, s in all_strings:
            f.write(f"0x{off:06X}  {s}\n")
    print(f"  Written to : {strings_file}")

    # ── 3. Keyword Search ──
    print("\n== Keyword Search ==")
    keywords = {
        "GPL/Script" : ["GPL","script","Script","GPLDATA","opcode"],
        "GFF/Files"  : ["GFF",".GFF","RESOURCE","GPLDATA","RGN"],
        "Font/Text"  : ["FONT","font","CHAR","render","TEXT","text"],
        "File I/O"   : ["fopen","fread","fclose","FILE","open","read"],
        "Dialog/Talk": ["dialog","DIALOG","talk","TALK","speak","keyword","NAME"],
        "Compress"   : ["compress","LZW","lzw","pack","PACK","decomp","inflate"],
        "Error msgs" : ["Error","error","ERROR","failed","cannot","invalid","Unable"],
        "SSI/Engine" : ["SSI","DarkSun","DARKSUN","DSUN","Gold","Gold Box"],
        "D&D Stats"  : ["STR ","DEX ","CON ","INT ","WIS ","CHA ","THAC","armor"],
        "Sound"      : ["SOUND","MUSIC","MIDI","midi","GUS","SoundBlaster","AdLib"],
    }
    for cat, kws in keywords.items():
        hits = [(off, s) for off, s in all_strings if any(kw in s for kw in kws)]
        if hits:
            print(f"\n  [{cat}] — {len(hits)} hits:")
            for off, s in hits[:8]:
                print(f"    0x{off:06X}  {s[:90]}")
            if len(hits) > 8:
                print(f"    ... and {len(hits)-8} more")

    # ── 4. GFF Tag references inside EXE ──
    print("\n== GFF 4-char Tag References in EXE ==")
    tags = [b'GPL ', b'NAME', b'TEXT', b'SPIN', b'FONT', b'MAPS', b'TILE',
            b'ANIM', b'CINE', b'SOBJ', b'CHAR', b'ITEM', b'ROOM', b'REGN',
            b'BACK', b'SAVE', b'LSEQ', b'GSEQ', b'PSEQ']
    for tag in tags:
        positions = [i for i in range(len(data)) if data[i:i+4] == tag]
        if positions:
            print(f"  {tag.decode('ascii','replace'):5s} : {len(positions):3d} occurrences, first @ 0x{positions[0]:06X}")

    # ── 5. Long strings (likely game text) ──
    print("\n== Long Strings (len > 25) ==")
    long_s = [(off, s) for off, s in all_strings if len(s) > 25]
    print(f"  Total: {len(long_s)}")
    for off, s in long_s[:50]:
        print(f"  0x{off:06X}  {s[:110]}")

    # ── 6. Find potential jump/dispatch tables (GPL interpreter clue) ──
    print("\n== Potential Dispatch Tables (x86 word-sized jump tables) ==")
    candidates = []
    search_end = min(len(data)-64, 0x15000)
    for i in range(0x200, search_end, 2):
        words = struct.unpack_from('<16H', data, i)
        diffs = [words[j+1]-words[j] for j in range(15)]
        if all(0 < d < 800 for d in diffs):           # monotonically increasing, reasonable gaps
            avg = sum(diffs)/15
            if 20 < avg < 300:
                candidates.append((i, words[:8], avg))
    print(f"  Found {len(candidates)} candidate regions")
    for off, words, avg in candidates[:15]:
        print(f"  0x{off:06X}  avg_gap={avg:.0f}  [{', '.join(f'{w:04X}' for w in words)}]")

    # ── 7. Entropy scan of first 96 KB ──
    print("\n== Entropy Scan (256-byte chunks, first 96KB) ==")
    high_e_offsets = []
    for i in range(0, min(len(data), 96*1024), 256):
        chunk = data[i:i+256]
        uniq = len(set(chunk)) / 256.0
        if uniq > 0.92:
            high_e_offsets.append((i, uniq))
    print(f"  High-entropy blocks (>0.92): {len(high_e_offsets)}")
    for off, e in high_e_offsets[:10]:
        print(f"  0x{off:06X}  entropy={e:.3f}")

    print("\n== DONE ==")

main()
