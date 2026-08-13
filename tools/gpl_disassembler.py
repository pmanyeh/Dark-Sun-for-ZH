"""
GPL Bytecode Disassembler (gpl_disassembler.py)
Converts 6-byte GPL records into human-readable GPL Assembly/Pseudocode
"""
import os, sys, struct, json
sys.stdout.reconfigure(encoding='utf-8')

GPLDATA_PATH = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN\GPLDATA.GFF"
OUT_DIR      = r"C:\Users\pmany\.gemini\antigravity-ide\brain\451cd7a2-e8a0-455b-9450-b4e9c8806586\scratch"

# Opcode Mapping Table (Inferred from DSUN.EXE analysis)
OPCODE_NAMES = {
    0x0001: "HEADER_HANDSHAKE",
    0x0010: "HEADER_CONFIG",
    0x000F: "HEADER_CONFIG_ALT",
    0x0002: "SET_VARIABLE",
    0x0003: "ADD_VARIABLE",
    0x0004: "SUB_VARIABLE",
    0x0005: "COMPARE_VAR",
    0x0006: "JUMP_IF_EQUAL",
    0x0007: "JUMP_IF_NOT_EQUAL",
    0x0008: "JUMP_ALWAYS",
    0x0009: "CALL_SUBROUTINE",
    0x000A: "RETURN",
    0x000B: "EXEC_SCRIPT",
    0x000C: "DISPLAY_TEXT",
    0x000D: "PROMPT_CHOICE",
    0x000E: "MOVE_ENTITY",
    0x0011: "PLAY_SOUND",
    0x0012: "GIVE_ITEM",
    0x0014: "TAKE_ITEM",
}

def read_gpl_entries(data):
    gpl_pos = data.find(b'GPL ')
    if gpl_pos < 0: return []
    table_start = gpl_pos + 28
    count = struct.unpack_from('<I', data, gpl_pos + 8)[0]
    entries = []
    for i in range(count):
        ep = table_start + i * 12
        if ep + 12 > len(data): break
        eid  = struct.unpack_from('<I', data, ep)[0]
        eoff = struct.unpack_from('<I', data, ep+4)[0]
        esz  = struct.unpack_from('<I', data, ep+8)[0]
        if eoff < len(data) and 0 < esz < 0x100000:
            entries.append((i, eid, eoff, esz))
    return entries

def disassemble_gpl_block(block, script_id):
    if len(block) < 4:
        return {
            "script_id": f"0x{script_id:08X}",
            "length": len(block),
            "record_count": 0,
            "text_ids": [],
            "instructions": []
        }
    hdr_len = struct.unpack_from('<I', block, 0)[0]
    payload = block[4:]
    rec_count = len(payload) // 6
    
    instructions = []
    text_ids_found = []
    
    for i in range(rec_count):
        off = i * 6
        rec = payload[off : off+6]
        w0, w1, w2 = struct.unpack('<HHH', rec)
        
        # Opcode interpretation
        flags = (w0 & 0xF000) >> 12
        op_code = w0 & 0x0FFF
        op_name = OPCODE_NAMES.get(op_code, f"OP_0x{op_code:04X}")
        
        # Track potential Text IDs
        if op_code == 0x000C or op_code == 0x000D or (w2 > 0x0100 and w2 < 0x8000):
            text_ids_found.append(w2)

        inst = {
            "index": i,
            "raw_hex": ' '.join(f'{b:02X}' for b in rec),
            "op_raw": f"0x{w0:04X}",
            "op_name": op_name,
            "flags": f"0x{flags:X}",
            "arg1": f"0x{w1:04X} ({w1})",
            "arg2": f"0x{w2:04X} ({w2})"
        }
        instructions.append(inst)
        
    return {
        "script_id": f"0x{script_id:08X}",
        "length": hdr_len,
        "record_count": rec_count,
        "text_ids": list(set(text_ids_found)),
        "instructions_sample": [f"{inst['op_name']} arg1={inst['arg1']} arg2={inst['arg2']}" for inst in instructions[:10]]
    }

def main():
    data = open(GPLDATA_PATH, "rb").read()
    entries = read_gpl_entries(data)
    print(f"✅ Disassembling {len(entries)} GPL scripts...")

    disassembled_all = {}
    total_text_ids = set()

    for idx, eid, eoff, esz in entries:
        block = data[eoff : eoff + esz]
        res = disassemble_gpl_block(block, eid)
        disassembled_all[res["script_id"]] = res
        total_text_ids.update(res["text_ids"])

    out_file = os.path.join(OUT_DIR, "gpl_disassembled.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(disassembled_all, f, indent=2, ensure_ascii=False)

    print(f"✅ Disassembly complete! Output saved to: {out_file}")
    print(f"📊 Total unique Text IDs referenced across all GPL scripts: {len(total_text_ids)}")

    # Sample output for Block 0
    b0_key = "0x00000000"
    if b0_key in disassembled_all:
        print(f"\n--- Disassembly Preview for {b0_key} (First 15 instructions) ---")
        for inst in disassembled_all[b0_key]["instructions"][:15]:
            print(f"  [{inst['index']:3d}] {inst['op_name']:<20} arg1={inst['arg1']:<14} arg2={inst['arg2']:<14} (hex: {inst['raw_hex']})")

if __name__ == "__main__":
    main()
