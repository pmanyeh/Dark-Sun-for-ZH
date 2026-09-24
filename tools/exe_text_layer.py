#!/usr/bin/env python3
"""Chinese text for strings that live in DSUN.EXE itself (DGROUP).

Each ``TextRegion`` is a run of the original DGROUP bytes that is rewritten as
a whole. Its strings are Base94-encoded through the main CJK mapping; a string
may move inside its region (Chinese is shorter than most English, but not every
string fits its own slot), and every ``push ds; push <old offset>`` in the code
is then rewritten to the new offset. The rest of the region is zero-filled.

A string only belongs here once its draw path is known to decode Base94 (the
resident GgPrintString at 36AA:0864, window controls filled through the
set-text calls, or the dialogue title decoder in the view UI layer). The layer
needs the view UI layer, so the display build applies it only with --view-ui.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

try:
    from .cjk_localization_pipeline import encode_text
    from .patch_dsun_scratch_cache import mz_relocation_file_offsets
    from .plan_name_slot_consumers import verify_overlay_relocations
except ImportError:
    from cjk_localization_pipeline import encode_text
    from patch_dsun_scratch_cache import mz_relocation_file_offsets
    from plan_name_slot_consumers import verify_overlay_relocations


DGROUP_FILE_BASE = 0x48960
DGROUP_FILE_END = DGROUP_FILE_BASE + 0x6000


@dataclass(frozen=True)
class TextRegion:
    start: int  # DGROUP offset of the first original byte
    original: bytes
    # (original DGROUP offset, new DGROUP offset, Chinese text)
    strings: tuple[tuple[int, int, str], ...]
    note: str


def _same(*items: tuple[int, str]) -> tuple[tuple[int, int, str], ...]:
    return tuple((offset, offset, text) for offset, text in items)


TEXT_REGIONS = (
    # --- dialogue yes/no prompt -------------------------------------------
    # Overlay 0x6B7BD builds a menu from "Answer Yes or No" (1600), "Yes"
    # (1611) and "No" (160E, the prompt's tail). The prompt is drawn through
    # the dialogue title decoder, the options through the menu's GgPrintString.
    TextRegion(
        0x1600, b"Answer Yes or No\0Yes\0",
        ((0x1600, 0x1600, "是或否？"), (0x160E, 0x160D, "否"), (0x1611, 0x1611, "是")),
        "yes/no prompt and its two options",
    ),
    # The dialogue handler recognises the prompt with
    # stricmp(title, "answer yes or no") (overlay 0x7DA2D/0x7DA44), so this
    # copy must stay byte-identical to the prompt at 1600.
    TextRegion(0x1F61, b"answer yes or no\0", _same((0x1F61, "是或否？")),
               "yes/no prompt as compared by the dialogue handler"),
    # --- message boxes (overlay segment 3, 0x54D90) ------------------------
    # Callers far-call stub segment 41B4 (written 04D0 in overlay code):
    # 41B4:0020 -> 0x561D7 "please wait" box, :0025 -> 0x54F21 box with
    # buttons, :002A -> 0x5536E one-line message. The text goes into window
    # control 2C06 through the set-text call 0580:005C.
    TextRegion(0x038D, b"NO MEMORY\0NO CHARACTERS AVAILABLE\0",
               ((0x038D, 0x038D, "記憶體不足"), (0x0397, 0x039D, "無可用角色")), "out of memory / no characters"),
    TextRegion(0x03B2, b"DELETE THIS PERSON?\0YES\0NO\0CANCEL\0",
               ((0x03B2, 0x03B2, "清除此角色？"), (0x03C6, 0x03C5, "是"), (0x03CA, 0x03C9, "否"),
                (0x03CD, 0x03CD, "取消")), "delete character confirmation"),
    TextRegion(0x05B4, b"Out of ammo\0", _same((0x05B4, "無彈藥")), "out of ammunition"),
    TextRegion(0x05F6, b"NOTHING HAPPENS\0", _same((0x05F6, "毫無反應")), "use item: nothing happens"),
    TextRegion(0x0DC5, b"THERE'S A SECRET DOOR!\0THE DOOR IS LOCKED\0THE DOOR WON'T OPEN\0",
               _same((0x0DC5, "這裡有暗門！"), (0x0DDC, "門鎖住了"), (0x0DEF, "門打不開")), "doors"),
    TextRegion(0x147C, b"Disk Space Low !!!\0Disk Space Very Low !!!\0",
               _same((0x147C, "存檔空間不多"), (0x148F, "存檔空間極少！")), "disk space warnings"),
    TextRegion(0x14B3, b"PLEASE WAIT\0", _same((0x14B3, "請稍候")), "please wait"),
    TextRegion(0x1837, b"BACKPACK FULL\0", _same((0x1837, "背包已滿")), "backpack full"),
    TextRegion(0x191D, b"I can't hear you\0I've got a banana in my ear\0",
               _same((0x191D, "我聽不見"), (0x192E, "我耳朵裡有根香蕉")), "easter egg"),
    TextRegion(0x1AF5, b"CAN'T CHANGE LEADER IN COMBAT\0", _same((0x1AF5, "戰鬥中無法更換隊長")),
               "leader change in combat"),
    TextRegion(0x1B5D, b"CAN'T ADD CHARS IN COMBAT\0", _same((0x1B5D, "戰鬥中不能加人")),
               "add character in combat"),
    TextRegion(0x1B86, b"MAXIMUM CHARACTERS:\0DELETE CHARS\0",
               _same((0x1B86, "人數上限："), (0x1B9A, "清除角色")), "party full"),
    TextRegion(0x1BC0, b"LAST ONE: CAN'T DROP\0OKAY\0DROP THIS CHARACTER?\0YES\0NO\0",
               # OKAY stays put: the overlay relocation table lists its push
               # immediate (0x70E8B), so that reference is never rewritten.
               ((0x1BC0, 0x1BC0, "至少要留一人"), (0x1BD5, 0x1BD5, "好"), (0x1BDA, 0x1BDA, "移除此角色？"),
                (0x1BEF, 0x1BED, "是"), (0x1BF3, 0x1BF1, "否")), "drop character"),
    TextRegion(0x1C84, b"SOUND EFFECTS ON\0SOUND EFFECTS OFF\0ANIMATIONS ON\0ANIMATIONS OFF\0",
               _same((0x1C84, "音效：開"), (0x1C95, "音效：關"), (0x1CA7, "動畫：開"), (0x1CB5, "動畫：關")),
               "sound and animation toggles"),
    TextRegion(0x1DE7, b"SAVING GAME\0", _same((0x1DE7, "儲存中")), "saving"),
    TextRegion(0x1E0C, b"GAME SAVED\0LOADING GAME\0", _same((0x1E0C, "已存檔"), (0x1E17, "讀取中")), "saved / loading"),
    TextRegion(0x1E89, b"Failed, weapon in hand\0", _same((0x1E89, "失敗，手持武器")), "weapon in hand"),
    TextRegion(0x2524, b"NO RESTING DURING COMBAT\0THE PARTY RESTS\0",
               _same((0x2524, "戰鬥中無法休息"), (0x253D, "隊伍休息")), "resting"),
    TextRegion(0x2F05, b"I COULDN'T SELL THAT\0", _same((0x2F05, "那個賣不掉")), "shop"),
    TextRegion(0x2F2C, b"TAKE IT\0LEAVE IT\0", _same((0x2F2C, "拿走"), (0x2F34, "留下")), "take or leave"),
    TextRegion(0x2FF9, b"YOU HAVEN'T CHOSEN\0EXIT\0CANCEL\0",
               ((0x2FF9, 0x2FF9, "你尚未選擇"), (0x300C, 0x3009, "離開"), (0x3011, 0x3010, "取消")),
               "unfinished choice"),
    TextRegion(0x303C, b"YOU HAVE MORE\0", _same((0x303C, "尚有剩餘")), "choices remaining"),
    TextRegion(0x3075, b"NO OTHER CLASSES AVAILABLE\0", _same((0x3075, "沒有其他職業可選")), "class choice"),
    TextRegion(0x30A5, b"SPHERE: AIR\0EARTH\0FIRE\0WATER\0",
               ((0x30A5, 0x30A5, "領域：風"), (0x30B1, 0x30B2, "土"), (0x30B7, 0x30B6, "火"),
                (0x30BC, 0x30BA, "水")), "cleric sphere choice"),
    TextRegion(0x3195, b"ONLY ACTIVE CHAR CAN CAST\0", _same((0x3195, "僅限當前角色施法")), "casting"),
    TextRegion(0x3440, b"CANNOT LEARN FROM THIS ITEM\0", _same((0x3440, "無法從此物品學習")), "scroll learning"),
)

# Strings that the engine compares with stricmp must translate identically.
MATCHED_STRINGS = ((0x1600, 0x1F61),)


def region_bytes(region: TextRegion, mapping: dict[str, object]) -> bytes:
    payload = bytearray(len(region.original))
    end_of_previous = region.start
    for _, offset, text in sorted(region.strings, key=lambda item: item[1]):
        if offset < end_of_previous:
            raise ValueError(f"DGROUP:{offset:04X} overlaps the previous string in {region.note}")
        encoded = encode_text(text, mapping) + b"\0"
        position = offset - region.start
        if position + len(encoded) > len(payload):
            raise ValueError(
                f"DGROUP:{offset:04X} {text!r} needs {len(encoded)} bytes, "
                f"past the end of {region.note}"
            )
        payload[position : position + len(encoded)] = encoded
        end_of_previous = offset + len(encoded)
    return bytes(payload)


def string_push_sites(image: bytes, offset: int) -> list[int]:
    """File offsets of every `push ds; push <offset>` outside DGROUP (the push imm16)."""
    pattern = re.escape(b"\x1e\x68" + offset.to_bytes(2, "little"))
    return [
        match.start() + 1
        for match in re.finditer(pattern, image)
        if not DGROUP_FILE_BASE <= match.start() < DGROUP_FILE_END
    ]


def code_patches(image: bytes) -> list[tuple[int, bytes, bytes, str]]:
    """Rewrite the push of every moved string; refuse references into a region's interior."""
    patches = []
    for region in TEXT_REGIONS:
        originals = {old for old, _, _ in region.strings}
        for inner in range(region.start, region.start + len(region.original)):
            if inner not in originals and string_push_sites(image, inner):
                raise ValueError(f"DGROUP:{inner:04X} inside {region.note} is referenced but not placed")
        for old, new, _ in region.strings:
            sites = string_push_sites(image, old)
            if not sites:
                raise ValueError(f"DGROUP:{old:04X} ({region.note}) has no push ds reference")
            if old == new:
                continue
            for site in sites:
                patches.append((
                    site + 1,
                    old.to_bytes(2, "little"),
                    new.to_bytes(2, "little"),
                    f"{region.note}: DGROUP:{old:04X} -> {new:04X}",
                ))
    return patches


def exe_text_ranges(image: bytes) -> list[tuple[int, int]]:
    ranges = [
        (DGROUP_FILE_BASE + region.start, DGROUP_FILE_BASE + region.start + len(region.original))
        for region in TEXT_REGIONS
    ]
    ranges += [(offset, offset + len(original)) for offset, original, _, _ in code_patches(image)]
    return sorted(ranges)


def apply_exe_text_patches(image: bytes, mapping: dict[str, object]) -> bytes:
    """Write the Chinese DGROUP strings and their moved references."""
    ranges = exe_text_ranges(image)
    for (_, end), (start, _) in zip(ranges, ranges[1:]):
        if start < end:
            raise ValueError("EXE text patch ranges overlap")
    relocations = mz_relocation_file_offsets(image)
    for site in relocations:
        if any(start < site + 2 and end > site for start, end in ranges):
            raise ValueError(f"EXE text patch overlaps MZ relocation at 0x{site:X}")
    verify_overlay_relocations(image, ranges)
    result = bytearray(image)
    texts: dict[int, str] = {}
    for region in TEXT_REGIONS:
        start = DGROUP_FILE_BASE + region.start
        if image[start : start + len(region.original)] != region.original:
            raise ValueError(f"DGROUP:{region.start:04X} ({region.note}) found modified bytes")
        result[start : start + len(region.original)] = region_bytes(region, mapping)
        texts.update({old: text for old, _, text in region.strings})
    for first, second in MATCHED_STRINGS:
        if texts[first] != texts[second]:
            raise ValueError(f"DGROUP:{first:04X} and {second:04X} are compared and must match")
    for offset, original, patched, reason in code_patches(image):
        if image[offset : offset + len(original)] != original:
            raise ValueError(f"EXE text code patch 0x{offset:X} ({reason}) found modified bytes")
        result[offset : offset + len(original)] = patched
    final = bytes(result)
    if mz_relocation_file_offsets(final) != relocations:
        raise ValueError("EXE text patches changed the MZ relocation table")
    allowed = {index for start, end in ranges for index in range(start, end)}
    if any(a != b and index not in allowed for index, (a, b) in enumerate(zip(image, final))):
        raise AssertionError("EXE text patches changed bytes outside their ranges")
    return final
