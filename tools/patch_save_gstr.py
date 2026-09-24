"""Rewrite English GSTR values saved in old save games with their Chinese encoding.

usage: patch_save_gstr.py <GAME/DARKSUN dir> <gpl-dialogue-patch.json>
MAS-99 seeds the global strings; each GSTR[n] lives at base + (n-1)*42 in the
save, where base is the first slot (GSTR[1] "What do you say?").
"""
import json
import shutil
import sys
from pathlib import Path

SLOT = 42
# GSTR index -> MAS-99 string copy offset (from the compiled package edits)
GSTR_SOURCES = {1: 0, 5: 20, 6: 33, 7: 66, 4: 96}

game = Path(sys.argv[1])
package = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
values = {}
for edit in package["edits"]:
    if edit["kind"] == "MAS" and edit["chunk_id"] == 99:
        values[edit["original_offset"]] = (edit["original"].encode("ascii"), edit["encoded_ascii"].encode("ascii"))
for path in sorted(game.glob("SAVE0*.SAV")) + [game / "DARKRUN.GFF"]:
    data = bytearray(path.read_bytes())
    base = -1
    for index, source in GSTR_SOURCES.items():
        english, chinese = values[source]
        for candidate in (english, chinese):
            at = data.find(candidate + b"\0" * (SLOT - len(candidate)))
            if at >= 0:
                base = at - (index - 1) * SLOT
                break
        if base >= 0:
            break
    if base < 0 or data[base + SLOT:base + SLOT + 4] != b"END\0":
        sys.exit(f"{path.name}: GSTR table not found")
    changed = []
    for index, source in sorted(GSTR_SOURCES.items()):
        english, chinese = values[source]
        start = base + (index - 1) * SLOT
        slot = bytes(data[start:start + SLOT])
        if slot == chinese.ljust(SLOT, b"\0"):
            continue
        if slot != english.ljust(SLOT, b"\0"):
            sys.exit(f"{path.name}: GSTR[{index}] holds neither the English nor the Chinese value: {slot!r}")
        data[start:start + SLOT] = chinese.ljust(SLOT, b"\0")
        changed.append(index)
    if changed:
        backup = path.with_name(path.name + ".orig")
        if not backup.exists():
            shutil.copy2(path, backup)
        path.write_bytes(bytes(data))
    print(f"{path.name}: GSTR table at 0x{base:X}, rewrote {changed}")
