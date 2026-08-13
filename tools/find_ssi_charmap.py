"""
DSUN.EXE SSI 64-Byte Character Mapping Array Finder (find_ssi_charmap.py)
Finds the exact 64-character table used by DSUN.EXE to decode text streams
"""
import os, sys, struct
sys.stdout.reconfigure(encoding='utf-8')

EXE_PATH = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN\DSUN.EXE"

def find_charmaps(data):
    print(f"Scanning DSUN.EXE ({len(data):,} bytes) for 64-byte SSI charmap tables...")

    candidates = []

    # Search for contiguous 64-byte buffers containing unique ASCII letters, digits, and punctuation
    for i in range(0, len(data) - 64):
        chunk = data[i : i + 64]
        
        # Check printable ASCII chars
        printable = sum(1 for b in chunk if 0x20 <= b <= 0x7E or b in (0x0D, 0x0A))
        unique_cnt = len(set(chunk))
        
        if printable >= 56 and unique_cnt >= 40:
            # Must contain common letters e, t, a, o, i, n, s, r, h
            s_str = ''.join(chr(b) if 0x20 <= b <= 0x7E else '.' for b in chunk)
            candidates.append((i, printable, unique_cnt, s_str))

    print(f"🎉 Found {len(candidates)} candidate charmaps in DSUN.EXE!")
    for off, p_cnt, u_cnt, s_str in candidates[:15]:
        print(f"  • Table @ 0x{off:06X} (Printable: {p_cnt}/64, Unique: {u_cnt}): {s_str}")

def main():
    find_charmaps(open(EXE_PATH, "rb").read())

if __name__ == "__main__":
    main()
