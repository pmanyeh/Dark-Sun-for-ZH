"""
Real English Dialogue Deep Finder (find_real_dialogue.py)
Filters out binary noise (sprite tiles, height maps) and locates true English dialogue lines
"""
import os, sys, struct, re, glob, json
sys.stdout.reconfigure(encoding='utf-8')

GAME_DIR = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN"
OUT_DIR  = r"C:\Users\pmany\.gemini\antigravity-ide\brain\451cd7a2-e8a0-455b-9450-b4e9c8806586\scratch"

# Common Dark Sun & RPG English vocabulary to validate real dialogue
RPG_WORDS = {
    "the", "you", "are", "and", "that", "have", "for", "not", "with", "you",
    "arena", "gladiator", "templar", "sorcerer", "king", "tyrian", "slave",
    "guards", "sword", "shield", "magic", "psionic", "desert", "dune"
}

def find_real_dialogue_in_file(path):
    fname = os.path.basename(path)
    data = open(path, "rb").read()

    # Match printable ASCII sequences with spaces and punctuation
    # Real dialogue lines typically have spaces and standard English letters
    pattern = re.compile(rb'[\x20-\x7E\r\n]{10,}')
    matches = pattern.finditer(data)

    real_dialogue = []

    for m in matches:
        s_bytes = m.group().strip()
        try:
            s_text = s_bytes.decode('ascii', errors='ignore')
            
            # Semantic check: Must have spaces
            words = set(re.findall(r'\b[a-zA-Z]{2,}\b', s_text.lower()))
            
            # Must overlap with common RPG words OR have multi-word sentences
            overlap = words.intersection(RPG_WORDS)
            
            if len(words) >= 3 and (overlap or (' ' in s_text and len(s_text) > 20)):
                # Filter out obvious file paths, headers, or CSS/ASM noise
                if not s_text.startswith("GFF") and not s_text.endswith(".GFF") and not s_text.endswith(".oda"):
                    real_dialogue.append((m.start(), s_text))
        except Exception:
            pass

    return fname, len(data), real_dialogue

def main():
    gff_files = sorted(glob.glob(os.path.join(GAME_DIR, "*.GFF")))
    print(f"✅ Deep scanning {len(gff_files)} GFF files for REAL English dialogue...\n")

    total_real_lines = 0
    file_summary = {}

    for path in gff_files:
        fname, size, lines = find_real_dialogue_in_file(path)
        if lines:
            file_summary[fname] = lines
            total_real_lines += len(lines)
            print(f"  • {fname:<15} ({size:<9,} bytes): Found {len(lines):4d} REAL English dialogue candidates!")

    print("\n" + "=" * 70)
    print(f"TOTAL REAL ENGLISH DIALOGUE LINES FOUND: {total_real_lines}")
    print("=" * 70)

    # Output to real_dialogue_extracted.json
    out_dict = {}
    for fname, lines in file_summary.items():
        out_dict[fname] = [{"offset": f"0x{off:06X}", "text": text} for off, text in lines]

    out_file = os.path.join(OUT_DIR, "real_dialogue_extracted.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(out_dict, f, indent=2, ensure_ascii=False)

    print(f"📄 Saved clean dialogue to: {out_file}")

    # Preview sample real dialogue lines from the files
    print("\n--- SAMPLE REAL DIALOGUE LINES ---")
    count = 0
    for fname, lines in file_summary.items():
        print(f"\n[{fname}]")
        for off, text in lines[:5]:
            print(f"  0x{off:06X}: {text}")
            count += 1
            if count >= 15: break
        if count >= 15: break

if __name__ == "__main__":
    main()
