"""
Manifest Summary Generator
Displays top statistics of dialogue_manifest.json
"""
import os, sys, json
sys.stdout.reconfigure(encoding='utf-8')

MANIFEST_PATH = r"C:\Users\pmany\.gemini\antigravity-ide\brain\451cd7a2-e8a0-455b-9450-b4e9c8806586\scratch\dialogue_manifest.json"

def main():
    if not os.path.exists(MANIFEST_PATH):
        print("❌ Manifest not found")
        return
        
    manifest = json.load(open(MANIFEST_PATH, encoding='utf-8'))
    print("=" * 70)
    print(f"DARK SUN: SHATTERED LANDS — UNIFIED DIALOGUE MANIFEST SUMMARY")
    print("=" * 70)
    print(f"Total Region Maps Analyzed: {len(manifest)}\n")
    
    print(f"{'Region':<12} {'Total Entities':<16} {'Interactive Nodes':<20} {'Text IDs Mapped'}")
    print("-" * 75)
    
    total_nodes = 0
    total_texts = 0
    
    for rgn_name, rgn_data in manifest.items():
        interactive = len(rgn_data["interactive_nodes"])
        text_count = sum(len(node["text_ids"]) for node in rgn_data["interactive_nodes"])
        total_nodes += interactive
        total_texts += text_count
        print(f"{rgn_name:<12} {rgn_data['entity_count']:<16} {interactive:<20} {text_count}")
        
    print("-" * 75)
    print(f"TOTALS: {len(manifest)} Regions | {total_nodes} Interactive Dialogue Nodes | {total_texts} Text ID Links Mapped!\n")

if __name__ == "__main__":
    main()
