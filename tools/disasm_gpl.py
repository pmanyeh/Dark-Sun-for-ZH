"""
DSUN.EXE GPL Interpreter Disassembler & Control Flow Tracer
Uses Capstone (16-bit x86 Mode)
Focus: 0x069900 - 0x06A500 (GPL Handler & Execution Routines)
"""
import os, sys, struct
from capstone import *

sys.stdout.reconfigure(encoding='utf-8')

EXE_PATH = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN\DSUN.EXE"
OUT_DIR  = r"C:\Users\pmany\.gemini\antigravity-ide\brain\451cd7a2-e8a0-455b-9450-b4e9c8806586\scratch"

def disasm_region(data, start_offset, length, base_addr=0x0000):
    """Disassemble binary range using Capstone in 16-bit mode"""
    md = Cs(CS_ARCH_X86, CS_MODE_16)
    md.detail = True
    
    code = data[start_offset : start_offset + length]
    print(f"\n{'='*70}")
    print(f"DISASSEMBLY @ File Offset 0x{start_offset:06X} - 0x{start_offset+length:06X}")
    print(f"{'='*70}")
    
    lines = []
    for insn in md.disasm(code, base_addr):
        file_pos = start_offset + (insn.address - base_addr)
        bytes_hex = ' '.join(f'{b:02X}' for b in insn.bytes)
        line = f"0x{file_pos:06X} (CS:{insn.address:04X}):  {bytes_hex:<18}  {insn.mnemonic:<8} {insn.op_str}"
        print(line)
        lines.append(line)
        
    return lines

def main():
    if not os.path.exists(EXE_PATH):
        print("❌ EXE file not found")
        return
        
    data = open(EXE_PATH, "rb").read()
    print(f"✅ Read DSUN.EXE ({len(data):,} bytes)")
    
    # Target 1: Around fhGPLI (0x069950 - 0x069A50)
    print("\n--- TARGET 1: fhGPLI Handler (0x069950) ---")
    disasm_region(data, 0x069950, 0x100, base_addr=0x9950)

    # Target 2: Around fhGPLX (0x06A3A0 - 0x06A4A0)
    print("\n--- TARGET 2: fhGPLX Handler (0x06A3A0) ---")
    disasm_region(data, 0x06A3A0, 0x100, base_addr=0xA3A0)

if __name__ == "__main__":
    main()
