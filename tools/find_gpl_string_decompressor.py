"""
GPL String Decompressor & Bit-Shift Decoder Tracer (find_gpl_string_decompressor.py)
Uses Capstone (16-bit x86 Mode) to scan DSUN.EXE for bit-packing / text decompression loops
"""
import os, sys, struct
from capstone import *

sys.stdout.reconfigure(encoding='utf-8')

EXE_PATH = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN\DSUN.EXE"
OUT_DIR  = r"C:\Users\pmany\.gemini\antigravity-ide\brain\451cd7a2-e8a0-455b-9450-b4e9c8806586\scratch"

def scan_text_decoders(data):
    md = Cs(CS_ARCH_X86, CS_MODE_16)
    md.detail = True

    print(f"✅ Scanning {len(data):,} bytes of DSUN.EXE for Bit-Shift & Text Decompression Loops...")

    # Bit shifts and character offsets often used in 5-bit / 6-bit packed text decoders:
    #   AND AL, 0x1F (or AND AX, 0x3F)
    #   ADD AL, 0x41 / ADD AL, 0x61 ('A' / 'a')
    #   SHR / SHL by 5

    potential_decoder_locs = []

    # Scan code section for AND reg, 0x1F or 0x3F followed by ADD reg, 0x41/0x61
    for i in range(0, len(data) - 100, 2):
        chunk = data[i:i+64]
        # Look for AND al, 1F (24 1F) or AND ax, 1F (25 1F 00) or SHL/SHR
        if b'\x24\x1F' in chunk or b'\x25\x1F\x00' in chunk or b'\x24\x3F' in chunk:
            # Check if there is an ADD instruction nearby
            if any(b in chunk for b in [b'\x04\x41', b'\x04\x61', b'\x05\x41\x00', b'\x05\x61\x00']):
                potential_decoder_locs.append(i)

    print(f"\n🎉 Found {len(potential_decoder_locs)} Potential Bit-Packed Text Decoder Locations!")

    for loc in potential_decoder_locs[:10]:
        print(f"\n--- Disassembly @ 0x{loc:06X} ---")
        code = data[loc : loc + 48]
        for insn in md.disasm(code, loc):
            bytes_hex = ' '.join(f'{b:02X}' for b in insn.bytes)
            print(f"  0x{insn.address:06X}: {bytes_hex:<16}  {insn.mnemonic:<8} {insn.op_str}")

def main():
    if not os.path.exists(EXE_PATH):
        print("❌ DSUN.EXE missing")
        return
    data = open(EXE_PATH, "rb").read()
    scan_text_decoders(data)

if __name__ == "__main__":
    main()
