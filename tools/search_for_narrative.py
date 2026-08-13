"""
Dark Sun Complete Story Dialogue Search (search_for_narrative.py)
Scans ALL GFF files and DSUN.EXE for long sentences matching common English dialogue punctuation and words.
"""
import os, sys, glob, re
sys.stdout.reconfigure(encoding='utf-8')

GAME_DIR = r"d:\git\Dark Sun Series\from Steam\games\Dark Sun-ENG\GAME\DARKSUN"
EXE_PATH = os.path.join(GAME_DIR, "DSUN.EXE")

def scan_text_sentences(data, label):
    # Match readable ASCII sentences (length >= 15) with spaces and standard words
    pattern = re.compile(rb'[\x20-\x7E\r\n]{15,}')
    hits = []
    for m in pattern.finditer(data):
        s_bytes = m.group().strip()
        try:
            s_text = s_bytes.decode('ascii', errors='ignore')
            words = set(re.findall(r'\b[a-zA-Z]{2,}\b', s_text.lower()))
            if len(words) >= 4 and ' ' in s_text and not s_text.endswith(".GFF") and not s_text.endswith(".oda"):
                hits.append((m.start(), s_text))
        except Exception:
            pass
    return hits

def main():
    files = sorted(glob.glob(os.path.join(GAME_DIR, "*.GFF"))) + [EXE_PATH]
    print(f"🔍 Searching {len(files)} game files for readable English sentences...\n")

    total_hits = 0
    for f in files:
        fname = os.path.basename(f)
        data = open(f, "rb").read()
        hits = scan_text_sentences(data, fname)
        if hits:
            total_hits += len(hits)
            print(f"=== {fname} ({len(hits)} readable sentences) ===")
            for pos, text in hits[:5]:
                print(f"  0x{pos:06X}: {text[:90]}")
            print()

    print(f"📊 Total Readable Sentences Found: {total_hits}")

if __name__ == "__main__":
    main()
