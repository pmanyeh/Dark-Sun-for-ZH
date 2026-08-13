"""
DSUN.EXE Huffman / Bitstream Decompressor Reverse Engineering Script
Uses Capstone (16-bit x86 Mode) to locate and reconstruct the exact text decompression function
"""
import os, sys, struct
from capstone import *

sys.stdout.reconfigure(encoding='utf-8')

EXE_PATH = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN\DSUN.EXE"

def find_decompression_loops(data):
    md = Cs(CS_ARCH_X86, CS_MODE_16)
    md.detail = True

    print(f"🔍 Scanning {len(data):,} bytes of DSUN.EXE for bitstream reading loops & bit-shift decoders...")

    # In x86 16-bit real/protected mode, a Huffman/Bitstream decompression loop has these distinct patterns:
    # 1. Bit shifts (SHL, SHR, ROL, ROR, RCL, RCR) to pull bits out of AX/BX/CX/DX or a byte buffer
    # 2. Table lookups using array indexing: MOV AL, [BX + SI] or MOV AX, [BX + SI*2]
    # 3. Inner loop jumping back (JMP, JNZ, LOOP, JB, JNB)
    
    candidates = []

    # Loop over 16-bit instruction boundaries
    for off in range(0x1000, len(data) - 200, 16):
        chunk = data[off : off + 128]
        
        # Count bit-manipulation and indirect indexing instructions in this 128-byte block
        bit_op_count = 0
        indirect_lookups = 0
        has_loop_jmp = False
        
        try:
            for insn in md.disasm(chunk, off):
                mnem = insn.mnemonic.lower()
                op_str = insn.op_str.lower()
                
                if mnem in ('shl', 'shr', 'sar', 'rol', 'ror', 'rcl', 'rcr', 'and', 'or', 'xor'):
                    if 'cl' in op_str or '1' in op_str or '0x' in op_str:
                        bit_op_count += 1
                if 'ptr [' in op_str and ('bx' in op_str or 'si' in op_str or 'di' in op_str):
                    indirect_lookups += 1
                if mnem in ('jmp', 'jnz', 'jne', 'jb', 'jnb', 'loop'):
                    has_loop_jmp = True

            # A classic bit-decompressor loop has high density of bit ops + indirect lookups + loop
            if bit_op_count >= 4 and indirect_lookups >= 4 and has_loop_jmp:
                candidates.append((off, bit_op_count, indirect_lookups))
        except Exception:
            pass

    print(f"\n🎉 Located {len(candidates)} Bit-Decompression Function Candidates in DSUN.EXE!")
    
    # Sort by bit-operation density
    candidates.sort(key=lambda x: -(x[1] + x[2]))

    for idx, (off, b_ops, i_lookups) in enumerate(candidates[:8]):
        print(f"\n{'='*70}")
        print(f"CANDIDATE #{idx+1} @ File Offset 0x{off:06X} (Bit Ops={b_ops}, Array Lookups={i_lookups})")
        print(f"{'='*70}")
        
        code = data[off : off + 96]
        for insn in md.disasm(code, off):
            bytes_hex = ' '.join(f'{b:02X}' for b in insn.bytes)
            print(f"  0x{insn.address:06X}: {bytes_hex:<18}  {insn.mnemonic:<8} {insn.op_str}")

def main():
    if not os.path.exists(EXE_PATH):
        print("❌ DSUN.EXE missing")
        return
    data = open(EXE_PATH, "rb").read()
    find_decompression_loops(data)

if __name__ == "__main__":
    main()
