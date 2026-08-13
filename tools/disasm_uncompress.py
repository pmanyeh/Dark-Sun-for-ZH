"""
Uncompress Function Disassembler
Target: Loadgamefromdisk & Uncompress routine @ 0x049D00
"""
import os, sys, struct
from capstone import *

sys.stdout.reconfigure(encoding='utf-8')

EXE_PATH = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN\DSUN.EXE"

def main():
    data = open(EXE_PATH, "rb").read()
    md = Cs(CS_ARCH_X86, CS_MODE_16)

    # Search for "Failed Uncompress in Loadgamefromdisk" string
    pos = data.find(b'Failed Uncompress in Loadgamefromdisk')
    print(f"String 'Failed Uncompress' @ 0x{pos:06X}")

    # Search backward for the code referencing this string (near 0x049D00)
    print("\n--- Disassembling code around Uncompress error handler (0x049D00 - 0x049E00) ---")
    code = data[0x049C00:0x049E00]
    for insn in md.disasm(code, 0x49C00):
        bytes_hex = ' '.join(f'{b:02X}' for b in insn.bytes)
        print(f"  0x{insn.address:06X}: {bytes_hex:<16}  {insn.mnemonic:<8} {insn.op_str}")

if __name__ == "__main__":
    main()
