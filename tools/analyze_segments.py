"""
DSUN.EXE Segment & Relocation Table Analyzer
Resolves FAR CALL targets like 0x0520:0034, 0x0100:05AB, etc. to exact File Offsets
"""
import os, sys, struct
from capstone import *

sys.stdout.reconfigure(encoding='utf-8')

EXE_PATH = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN\DSUN.EXE"

def main():
    data = open(EXE_PATH, "rb").read()
    print(f"✅ Read DSUN.EXE ({len(data):,} bytes)")

    # MZ Header parsing
    hdr_para = struct.unpack_from('<H', data, 8)[0]
    hdr_bytes = hdr_para * 16
    reloc_count = struct.unpack_from('<H', data, 6)[0]
    reloc_off   = struct.unpack_from('<H', data, 24)[0]

    print(f"Header Paragraphs: {hdr_para} -> Header Size = 0x{hdr_bytes:04X} ({hdr_bytes} bytes)")
    print(f"Relocation Count : {reloc_count}")
    print(f"Relocation Offset: 0x{reloc_off:04X}")

    # Read relocation entries (far pointer offsets)
    relocs = []
    for i in range(reloc_count):
        off = reloc_off + i * 4
        if off + 4 > hdr_bytes: break
        r_off, r_seg = struct.unpack_from('<HH', data, off)
        relocs.append((r_seg, r_off))

    print(f"Loaded {len(relocs)} relocation entries from header.")

    # Unique segment values in relocation table
    seg_set = sorted(set(r_seg for r_seg, r_off in relocs))
    print(f"\nUnique Relocated Segments in EXE ({len(seg_set)} segments):")
    print(', '.join(f"0x{s:04X}" for s in seg_set[:30]))

    # Analyze segment boundaries in load module (starts at hdr_bytes = 0x5400)
    # Search for functions around string display (0x1591 call)
    md = Cs(CS_ARCH_X86, CS_MODE_16)
    md.detail = True

    # Search for PUSH 0x1591 (68 91 15) or LCALL 0x520, 0x34 across the load module
    print("\n--- Searching for PUSH 0x1591 & LCALL 0x0520:0034 in Code ---")
    pos = 0
    lcall_hits = []
    while True:
        p = data.find(b'\x9A\x34\x00', pos)
        if p < 0: break
        lcall_hits.append(p)
        pos = p + 1

    print(f"Found {len(lcall_hits)} LCALL xxxx:0034 hits in load module:")
    for p in lcall_hits:
        print(f"  • File Offset 0x{p:06X}:")
        code = data[max(0, p-16) : min(len(data), p+24)]
        for insn in md.disasm(code, max(0, p-16)):
            bytes_hex = ' '.join(f'{b:02X}' for b in insn.bytes)
            print(f"    0x{insn.address:06X}: {bytes_hex:<16}  {insn.mnemonic:<8} {insn.op_str}")

if __name__ == "__main__":
    main()
