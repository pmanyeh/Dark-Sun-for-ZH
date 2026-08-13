"""
DSUN.EXE Deep Analysis - Phase 2
Focus: GPL interpreter loop, VMEM system, GFF loading functions
"""
import os, sys, struct, re
sys.stdout.reconfigure(encoding='utf-8')

EXE_PATH = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN\DSUN.EXE"
OUT_DIR  = r"C:\Users\pmany\.gemini\antigravity-ide\brain\451cd7a2-e8a0-455b-9450-b4e9c8806586\scratch"

data = open(EXE_PATH, "rb").read()
print(f"[OK] DSUN.EXE size: {len(data):,} bytes")

def hex_dump(offset, length=64, label=""):
    """Display hex dump with ASCII"""
    chunk = data[offset:offset+length]
    print(f"\n--- HEX DUMP @ 0x{offset:06X} {label} ---")
    for i in range(0, len(chunk), 16):
        row = chunk[i:i+16]
        hex_part = ' '.join(f'{b:02X}' for b in row)
        asc_part = ''.join(chr(b) if 0x20 <= b < 0x7F else '.' for b in row)
        print(f"  {offset+i:06X}:  {hex_part:<47}  {asc_part}")

def find_context(search_offset, radius=128):
    """Print context around a found location"""
    start = max(0, search_offset - radius)
    end   = min(len(data), search_offset + radius)
    return data[start:end]

# ─────────────────────────────────────────────────────────
# 1. GPL 直譯器關鍵位置深挖
# ─────────────────────────────────────────────────────────
print("\n" + "="*70)
print("1. GPL INTERPRETER ANALYSIS")
print("="*70)

# fhGPLI and fhGPLX are function handles/pointers to GPL interpreter functions
gpl_locs = {
    "fhGPLI (0x069990)": 0x069990,
    "fhGPLI (0x0699BD)": 0x0699BD,
    "fhGPLI (0x069BA7)": 0x069BA7,
    "fhGPLI (0x069BD4)": 0x069BD4,
    "fhGPLX (0x06A3C8)": 0x06A3C8,
    "BAD GPL EXIT":       data.find(b'BAD GPL EXIT'),
    "GPLDATA.GFF":        data.find(b'GPLDATA.GFF'),
}

for label, off in gpl_locs.items():
    if off > 0:
        hex_dump(off, 80, label)

# ─────────────────────────────────────────────────────────
# 2. 找 GPL opcode dispatch 區域
#    GPL 直譯器通常有個大 switch() 或 dispatch table
#    在 x86 16-bit 中常是: JMP word ptr [BX+table_base]
# ─────────────────────────────────────────────────────────
print("\n" + "="*70)
print("2. LOOKING FOR GPL DISPATCH TABLE / SWITCH PATTERNS")
print("="*70)

# x86 patterns for switch dispatch:
#   FF 27        JMP  [BX]
#   FF A7 xx xx  JMP  [BX + disp16]
#   FF E3        JMP  BX
# Followed or preceded by a table of WORD offsets

dispatch_patterns = [
    b'\xFF\x27',         # JMP [BX]
    b'\xFF\xA7',         # JMP [BX+disp16]
    b'\xFF\xE3',         # JMP BX
    b'\xFF\x24',         # JMP [SI]
    b'\xFF\xE4',         # JMP SP (unusual but possible)
    b'\xEB',             # JMP short (loop head)
]

print("\n  Scanning for indirect JMP patterns (GPL interpreter dispatch)...")
dispatch_hits = []
for pat in dispatch_patterns:
    pos = 0
    while True:
        p = data.find(pat, pos)
        if p < 0 or p > len(data)-4:
            break
        dispatch_hits.append((p, pat.hex()))
        pos = p + 1

# Sort and deduplicate nearby hits (cluster them)
dispatch_hits.sort()
clusters = []
if dispatch_hits:
    cluster_start = dispatch_hits[0][0]
    cluster = [dispatch_hits[0]]
    for off, pat in dispatch_hits[1:]:
        if off - cluster[-1][0] < 200:
            cluster.append((off, pat))
        else:
            clusters.append(cluster)
            cluster = [(off, pat)]
    clusters.append(cluster)

print(f"  Total indirect JMPs found: {len(dispatch_hits)}")
print(f"  Clusters (within 200 bytes): {len(clusters)}")
print("\n  Top 10 largest clusters (most likely to be interpreter loops):")
clusters.sort(key=lambda c: -len(c))
for i, cluster in enumerate(clusters[:10]):
    start = cluster[0][0]
    end   = cluster[-1][0]
    print(f"  [{i+1:2d}] Offset 0x{start:06X}-0x{end:06X}  ({len(cluster)} JMPs, span={end-start} bytes)")

# Show hex around the top cluster
if clusters:
    top_off = clusters[0][0][0]
    hex_dump(top_off - 32, 128, f"Context around top JMP cluster @ 0x{top_off:06X}")

# ─────────────────────────────────────────────────────────
# 3. GFF 載入函式分析 — 找到 GFF 讀取後解包的程式碼
# ─────────────────────────────────────────────────────────
print("\n" + "="*70)
print("3. GFF LOADING FUNCTION ANALYSIS")
print("="*70)

gff_strings = [
    b'GPLDATA.GFF file not found',
    b'RESOURCE.GFF file not found',
    b'OBJEX.GFF file not found',
    b'RGNFF.GFF file not found',
]
for s in gff_strings:
    pos = data.find(s)
    if pos >= 0:
        # Look BEFORE the error string to find the actual function call sequence
        hex_dump(pos - 96, 192, f"Context: '{s[:30].decode()}'")

# ─────────────────────────────────────────────────────────
# 4. Uncompress / LZW 函式
# ─────────────────────────────────────────────────────────
print("\n" + "="*70)
print("4. DECOMPRESSION FUNCTION CLUES")
print("="*70)

uncomp_str = data.find(b'Failed Uncompress in Loadgamefromdisk')
if uncomp_str >= 0:
    print(f"  'Failed Uncompress' string @ 0x{uncomp_str:06X}")
    hex_dump(uncomp_str - 64, 180, "Loadgamefromdisk function area")

# ─────────────────────────────────────────────────────────
# 5. FONT rendering — FONT tag in EXE
# ─────────────────────────────────────────────────────────
print("\n" + "="*70)
print("5. FONT SYSTEM ANALYSIS")
print("="*70)

font_loc1 = 0x02A80B
font_loc2 = data.find(b'FONT', font_loc1+1)
for off in [font_loc1, font_loc2]:
    if off and off > 0:
        hex_dump(off - 32, 128, f"FONT tag @ 0x{off:06X}")

# ─────────────────────────────────────────────────────────
# 6. VCTALK — Voice/Character Talk system
# ─────────────────────────────────────────────────────────
print("\n" + "="*70)
print("6. VCTALK — DIALOGUE SYSTEM")
print("="*70)

vctalk = data.find(b'VCTALK')
if vctalk >= 0:
    print(f"  VCTALK found @ 0x{vctalk:06X}")
    hex_dump(vctalk - 64, 200, "VCTALK context")

# ─────────────────────────────────────────────────────────
# 7. Copyright & Compiler signature
# ─────────────────────────────────────────────────────────
print("\n" + "="*70)
print("7. COMPILER & COPYRIGHT INFO")
print("="*70)

borland = data.find(b'Borland C++')
ssi_cr  = data.find(b'Copyright 1993, SSI')
for label, off in [("Borland C++", borland), ("SSI Copyright", ssi_cr)]:
    if off >= 0:
        hex_dump(off, 80, label)

# ─────────────────────────────────────────────────────────
# 8. GPL opcode patterns — look for dense byte sequences
#    In the region near fhGPLI (0x069990 area)
# ─────────────────────────────────────────────────────────
print("\n" + "="*70)
print("8. GPL REGION DEEP SCAN (0x069000 - 0x06C000)")
print("="*70)

gpl_region = data[0x069000:0x06C000]
# Extract all strings in this region
gpl_strings = [(m.start()+0x069000, m.group().decode('ascii','replace'))
               for m in re.finditer(rb'[\x20-\x7E]{4,}', gpl_region)]
print(f"  Strings in GPL region: {len(gpl_strings)}")
for off, s in gpl_strings:
    print(f"  0x{off:06X}  {s[:100]}")

# Count unique bytes in GPL region (is it code or data?)
gpl_uniq = len(set(gpl_region))
print(f"\n  Unique bytes in GPL region: {gpl_uniq}/256 ({gpl_uniq/256*100:.0f}% entropy)")
print(f"  Region size: {len(gpl_region):,} bytes")

hex_dump(0x069970, 128, "Around fhGPLI references")
hex_dump(0x06A3A0, 128, "Around fhGPLX reference")

print("\n== PHASE 2 COMPLETE ==")
