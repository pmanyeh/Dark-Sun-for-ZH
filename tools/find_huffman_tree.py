"""
Huffman Tree & Character Dictionary Scanner (find_huffman_tree.py)
Scans DSUN.EXE, GPLDATA.GFF, and RESOURCE.GFF for the official SSI Huffman Tree & Symbol Table
Goal: Extract 100% human-readable English dialogue sentences
"""
import os, sys, struct, json
sys.stdout.reconfigure(encoding='utf-8')

EXE_PATH     = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN\DSUN.EXE"
GPLDATA_PATH = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN\GPLDATA.GFF"
RES_PATH     = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN\RESOURCE.GFF"
OUT_DIR      = r"C:\Users\pmany\.gemini\antigravity-ide\brain\451cd7a2-e8a0-455b-9450-b4e9c8806586\scratch"

def scan_huffman_tree_in_file(filepath):
    fname = os.path.basename(filepath)
    data = open(filepath, "rb").read()

    print(f"\n{'='*70}")
    print(f"SCANNING FOR HUFFMAN TREE & SYMBOL TABLES: {fname} ({len(data):,} bytes)")
    print('='*70)

    # Huffman tree nodes in 16-bit DOS executables are typically array of structs:
    # struct HuffmanNode { uint16_t symbol; uint16_t left_child; uint16_t right_child; } (6 bytes each, 256-512 nodes = 1.5KB - 3KB)
    # or array of child pointers: uint16_t left[256], right[256] (512 bytes each)

    possible_trees = []

    # Search for contiguous word arrays where values range between 0 and 512
    for i in range(0, len(data) - 1024, 16):
        # Read 256 shorts
        shorts = struct.unpack_from('<256H', data, i)
        
        # Check if they form a valid Huffman binary tree structure:
        # 1. Values are bounded (0 <= val <= 512)
        # 2. Contains root node index and child references
        valid_indices = sum(1 for s in shorts if 0 <= s <= 512)
        unique_vals   = len(set(shorts))
        
        if valid_indices > 240 and unique_vals > 80:
            possible_trees.append((i, valid_indices, unique_vals, shorts))

    print(f"Found {len(possible_trees)} Huffman tree candidate tables in {fname}")
    for off, val_cnt, uniq, shorts in possible_trees[:5]:
        print(f"  • Candidate @ Offset 0x{off:06X}: Valid Nodes={val_cnt}/256, Unique Symbols={uniq}")

    return possible_trees

def main():
    for path in [EXE_PATH, GPLDATA_PATH, RES_PATH]:
        if os.path.exists(path):
            scan_huffman_tree_in_file(path)

if __name__ == "__main__":
    main()
