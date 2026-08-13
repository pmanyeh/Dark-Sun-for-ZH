"""
DSUN.EXE Decompression Routine Analyzer & C-Reconstructor
Disassembles the exact functions around LCALL 0001:05AB (0x069996) and LCALL 0520:0034 (0x08A53E)
"""
import os, sys, struct
from capstone import *

sys.stdout.reconfigure(encoding='utf-8')

EXE_PATH = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN\DSUN.EXE"

def disassemble_func(data, start_off, size, name=""):
    md = Cs(CS_ARCH_X86, CS_MODE_16)
    md.detail = True
    
    print(f"\n==================================================")
    print(f"FUNCTION DISASSEMBLY: {name} @ 0x{start_off:06X} ({size} bytes)")
    print(f"==================================================")
    
    code = data[start_off : start_off + size]
    lines = []
    for insn in md.disasm(code, start_off):
        bytes_hex = ' '.join(f'{b:02X}' for b in insn.bytes)
        line = f"  0x{insn.address:06X}: {bytes_hex:<18}  {insn.mnemonic:<8} {insn.op_str}"
        print(line)
        lines.append(line)
    return lines

def main():
    if not os.path.exists(EXE_PATH):
        print("❌ DSUN.EXE missing")
        return
        
    data = open(EXE_PATH, "rb").read()
    
    # 1. Function 1: GFF Tag Lookup & Script Buffer Resolver (0x069980 - 0x069A80)
    disassemble_func(data, 0x069978, 0x120, "GPL_Script_Buffer_Resolver (0x069978)")
    
    # 2. Function 2: Text Display & String Unpacker Entry (0x08A520 - 0x08A620)
    disassemble_func(data, 0x08A520, 0x100, "Text_Display_Unpacker_Entry (0x08A520)")
    
    # 3. Function 3: Core Bitstream Decompressor Loop (0x069A80 - 0x069B80)
    disassemble_func(data, 0x069A80, 0x100, "Core_Bitstream_Loop (0x069A80)")

if __name__ == "__main__":
    main()
