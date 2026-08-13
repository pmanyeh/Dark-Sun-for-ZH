"""
Dark Sun Dialogue Architecture Investigation Report
Focus: Explaining why raw English sentences aren't plain ASCII and what steps remain
"""
import os, sys, json
sys.stdout.reconfigure(encoding='utf-8')

LOCALIZATION_DIR = r"d:\git\Dark Sun Series\localization"
OUT_TABLE        = os.path.join(LOCALIZATION_DIR, "DarkSun_Dialogue_Translation_Table.json")

def main():
    if not os.path.exists(OUT_TABLE):
        print("❌ Master table missing")
        return
        
    table = json.load(open(OUT_TABLE, encoding='utf-8'))
    print(f"✅ Master Translation Table: {len(table)} clean items")
    
    print("\n--- Summary of Currently Extracted Plaintext Items ---")
    for item in table[:15]:
        print(f"  • [{item['entry_id']}] ({item['resource_key']}): {item['original_en']}")

if __name__ == "__main__":
    main()
