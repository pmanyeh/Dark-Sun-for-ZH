#!/usr/bin/env python3
"""Inventory and VIEW CHARACTER Chinese UI layer for the main display build.

The v33 -> v75 candidate chain (re_56..re_95) built this layer one parent
staging directory at a time on top of the old six-bank, cjk-mapping-v57
build. This module applies the same result to any build from
``build_cjk_display_staging.py``:

* ``VIEW_UI_EXE_PATCHES`` is the exact v33 -> v75 DSUN.EXE difference. Every
  original run is pristine DSUN.EXE, none of it overlaps the main build's own
  patches, and none of it touches an MZ or overlay relocation.
* The FONT-100 part appends seven NAME glyph slots and the FONT-local
  NAME-slot decoder (``cjk_name_slot_cache.asm``). The decoder's label text
  comes from ``localization/catalog/fixed_ui_labels.csv`` through the main
  CJK mapping, and it opens as many ``C<n>`` banks as the main build ships.
* Item material words are pre-rendered FONT-100 glyphs behind six otherwise
  unused codes, written into the resident English material table.
"""

from __future__ import annotations

try:
    from .cjk_localization_pipeline import glyph_record_for_id
    from .patch_dsun_scratch_cache import mz_relocation_file_offsets
    from .plan_name_slot_consumers import (
        ABILITY_UNITS,
        BACKPACK_UNITS,
        FONT_CORE_PAYLOAD_OFFSET,
        LABEL_UNITS,
        assemble_name_slot_cache,
        fixed_ui_pair_ids,
        load_fixed_ui_ids,
        verify_overlay_relocations,
    )
except ImportError:
    from cjk_localization_pipeline import glyph_record_for_id
    from patch_dsun_scratch_cache import mz_relocation_file_offsets
    from plan_name_slot_consumers import (
        ABILITY_UNITS,
        BACKPACK_UNITS,
        FONT_CORE_PAYLOAD_OFFSET,
        LABEL_UNITS,
        assemble_name_slot_cache,
        fixed_ui_pair_ids,
        load_fixed_ui_ids,
        verify_overlay_relocations,
    )


# The FONT-100 layout both the v33 line and the main build share: the
# original 8299-byte font followed by one 102-byte 10x10 staging record.
STAGING_OFFSET = 0x206B
RECORD_BYTES = 102
NAME_GLYPH_SLOTS = 7
# The v75 layout values (re_95); the decoder draws with these directly.
VIEW_Y_ORIGIN = 63
ALIGNMENT_POSITION = (44, 149)
# VIEW CHARACTER lower half (re_102): four rows 10px apart. v75 left them at
# 106/115/125/138; the class row sits 2px lower so it clears the panel edge.
# Each (file offset of the Y byte in a "push dword Y:X", v75 value) pair
# belongs to one row; the class row is moved by the decoder instead.
CLASS_ROW = (106, 108)
LEVEL_ROW_Y = 118
STAT_ROW_Y = 128
ARMOUR_ROW_Y = 138
VIEW_ROW_SITES = (
    (0x8A218, 115, LEVEL_ROW_Y),   # level digits
    (0x8A285, 115, LEVEL_ROW_Y),   # EXP
    (0x8A2D3, 125, STAT_ROW_Y),    # HP value (the labels are in the decoder)
    (0x8A349, 125, STAT_ROW_Y),    # PSI value
    (0x8A390, 138, ARMOUR_ROW_Y),  # AC
    (0x8A3C5, 138, ARMOUR_ROW_Y),  # DAM
)

# (file offset, original bytes, patched bytes, origin). Origins name the
# candidate that introduced each run; see re_56..re_95 for the reasoning.
VIEW_UI_EXE_PATCHES = (
    (0x039074, "00 00 00 00 00 00 00 00 00 00 00 00", "06 C4 1E 78 A3 81 C3 9B 23 06 53 CB", "v55 resident FONT trampoline (2E86:5414)"),
    (0x064B68, "26 8A 47 19 98 C1 E0 02 8B D8 FF B7 A6 0E", "C7 46 FE 18 00 EB 14 90 90 90 90 90 90 90", "v64-v66 identity row: skip the original gender push"),
    (0x064B83, "C4 5E 0A 26 8A 47 19 98 C1 E0 02 8B D8 66 FF B7 A6 0E FF 36 70 32", "0E E8 00 00 58 05 12 00 50 B8 CD FF 8C DB 80 EF 10 53 68 14 07 CB", "v64-v66 gender label redirect"),
    (0x064BB9, "C4 5E 0A 26 8A 47 18 98 C1 E0 02 8B D8 66 FF B7 AE 0E FF 36 70 32", "0E E8 00 00 58 05 12 00 50 B8 CC FF 8C DB 80 EF 10 53 68 14 07 CB", "v64 race label redirect"),
    (0x064BFB, "C4 5E 0A 26 8A 47 1A 98 C1 E0 02 8B D8 66 FF B7 06 0F FF 36 70 32 6A 14 FF 36 6E 32 66 68 FF 00 FE 00 6A 00 1E 68 11 0E FF 76 10 FF 76 0E 66 FF 76 06", "0E E8 00 00 58 05 2E 00 50 B8 CB FF 8C DB 80 EF 10 53 68 14 07 CB 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90", "v66 alignment label redirect"),
    (0x064D8A, "16 8D 46 B0 50 FF 36 70 32 6A 14 FF 36 6E 32 66 68 FF 00 FE 00 6A 00 1E 68 11 0E FF 76 0E FF 76 0C 66 FF 76 06", "0E E8 00 00 58 05 21 00 50 B8 E9 FF 8C DB 80 EF 10 53 68 14 07 CB 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90", "v61 inventory AC label redirect"),
    (0x065125, "8B DE C1 E3 02 66 FF B7 F2 0E FF 36 70 32 6A 14 FF 36 6E 32 66 68 FF 00 FE 00 6A 00 1E 68 11 0E 8B C6 6B C0 07 8B 56 0C 03 D0 52 FF 76 0A 66 FF 76 06", "0E E8 00 00 58 05 2E 00 50 B8 ED FF 8C DB 80 EF 10 53 68 14 07 CB 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90", "v57 ability label loop redirect"),
    (0x06E111, "55 8B EC 66 FF 76 06 68 06 2C 66 FF 36 A4 11", "0E 68 A0 23 8C DB 80 EF 10 53 68 14 07 CB 90", "v56 BACKPACK label redirect"),
    (0x06E288, "6B C0 19 8B 16 6D 16 03 D0 FF 36 6F 16 52", "0E 68 16 25 8C DB 80 EF 10 53 68 14 07 CB", "v55 NAME consumer: bottom hover"),
    # Inventory portrait column (overlay 0x6BFAC): per portrait si the HP
    # line sits at y = si*48+38 and the status at +44, 6px apart, too tight
    # for 10px CJK status words. The two-character status moves into the
    # bottom of the portrait frame (+26, drawn 2px lower as Chinese) and 4px
    # right; HP keeps its row, where three-digit values still fit.
    (0x06BFB2, "2C", "1A", "v106 inventory portrait status inside the frame, 1px above its bottom edge"),
    (0x06BFB6, "01", "05", "v105 inventory portrait status 4px right"),
    (0x06F5A4, "35", "08", "v55/v57 inventory panel 10px line grid and 30px shift"),
    (0x06F5E9, "07 05 35 00 50 68 04", "0A 05 08 00 50 68 08", "v55/v57 inventory panel 10px line grid and 30px shift"),
    (0x06F60E, "66 68 FF 00 FE 00 6A 00 1E 68 4C 1A 66 68 EC 00 63 00 66 FF 36 A4 11", "0E E8 00 00 58 05 13 00 50 B8 EA FF 8C DB 80 EF 10 53 68 14 07 CB 90", "v61 inventory PSI label redirect"),
    (0x06F631, "63", "45", "v55/v57 inventory panel 10px line grid and 30px shift"),
    (0x06F672, "71", "53", "v55/v57 inventory panel 10px line grid and 30px shift"),
    (0x06F6A9, "78", "63", "v55/v57 inventory panel 10px line grid and 30px shift"),
    (0x072775, "07", "0A", "v55/v57 inventory panel 10px line grid and 30px shift"),
    (0x072955, "6B C0 19 8B 16 6D 16 03 D0 FF 36 6F 16 52", "0E 68 93 2B 8C DB 80 EF 10 53 68 14 07 CB", "v55 NAME consumer: right-click card"),
    (0x072972, "07", "0A", "v55/v57 inventory panel 10px line grid and 30px shift"),
    (0x072C26, "C4 5E 0A 26 8A 47 23 98 48 C1 E0 02 8B D8 66 FF 30", "B8 92 FF 0E 68 67 2E 8C DB 80 EF 10 53 68 14 07 CB", "v71 multiclass name redirect"),
    (0x072C42, "8B 5E 0A 26 8A 47 22 98 48 C1 E0 02 8B D8 66 FF 30", "B8 91 FF 0E 68 83 2E 8C DB 80 EF 10 53 68 14 07 CB", "v71 multiclass name redirect"),
    (0x072C60, "8B 5E 0A 26 8A 47 21 98 48 C1 E0 02 8B D8 66 FF 30", "B8 90 FF 0E 68 A1 2E 8C DB 80 EF 10 53 68 14 07 CB", "v71 multiclass name redirect"),
    (0x072C99, "C4 5E 0A 26 8A 47 22 98 48 C1 E0 02 8B D8 66 FF 30", "B8 91 FF 0E 68 DA 2E 8C DB 80 EF 10 53 68 14 07 CB", "v71 multiclass name redirect"),
    (0x072CB7, "8B 5E 0A 26 8A 47 21 98 48 C1 E0 02 8B D8 66 FF 30", "B8 90 FF 0E 68 F8 2E 8C DB 80 EF 10 53 68 14 07 CB", "v71 multiclass name redirect"),
    (0x072CEF, "C4 5E 0A 26 8A 47 21 98 48 C1 E0 02 8B D8 66 FF 30", "B8 90 FF 0E 68 30 2F 8C DB 80 EF 10 53 68 14 07 CB", "v68b class name slot 1 redirect"),
    (0x08A0E8, "8B DE C1 E3 02 66 FF B7 F2 0E FF 36 70 32 6A 14 FF 36 6E 32 66 68 FF 00 FE 00 6A 00 1E 68 51 33 8B C6 6B C0 07 05 28 00 50 68 95 00", "0E E8 00 00 58 05 28 00 50 B8 EC FF 8C DB 80 EF 10 53 68 14 07 CB 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90", "v58b VIEW CHARACTER ability label redirect"),
    (0x08A149, "FF 36 70 32 6A 14 FF 36 6E 32 66 68 FF 00 FE 00 6A 00 1E 68 5A 33 8B C6 6B C0 07 05 28 00 50 68 AD 00", "0E E8 00 00 58 05 1E 00 50 B8 EB FF 8C DB 80 EF 10 53 68 14 07 CB 90 90 90 90 90 90 90 90 90 90 90 90", "v58b VIEW CHARACTER ability number redirect"),
    (0x08A218, "71", "73", "v71-v75 VIEW lower-half layout position"),
    (0x08A283, "95 00 78", "BF 00 73", "v71-v75 VIEW lower-half layout position"),
    (0x08A2AA, "66 68 FF 00 FE 00 6A 00 1E 68 63 33 66 68 95 00 7F 00", "B8 C9 FF 0E 68 4C 04 8C DB 80 EF 10 53 68 14 07 CB 90", "v67 VIEW HP label redirect"),
    (0x08A2D3, "7F", "7D", "v71-v75 VIEW lower-half layout position"),
    (0x08A320, "66 68 FF 00 FE 00 6A 00 1E 68 6D 33 66 68 95 00 86 00", "B8 CA FF 0E 68 C2 04 8C DB 80 EF 10 53 68 14 07 CB 90", "v67 VIEW PSI label redirect"),
    (0x08A347, "BD 00 86", "06 01 7D", "v71-v75 VIEW lower-half layout position"),
    (0x08A390, "8D", "8A", "v71-v75 VIEW lower-half layout position"),
    (0x08A3C5, "8D", "8A", "v71-v75 VIEW lower-half layout position"),
    (0x08A925, "6B C0 19 8B 16 6D 16 03 D0 FF 36 6F 16 52", "0E 68 C3 0A 8C DB 80 EF 10 53 68 14 07 CB", "v60 VIEW CHARACTER hover name"),
    (0x08BE7E, "07", "0A", "v55/v57 inventory panel 10px line grid and 30px shift"),
    (0x08BECF, "6B C0 19 8B 16 6D 16 03 D0 FF 36 6F 16 52", "0E 68 FD 0F 8C DB 80 EF 10 53 68 14 07 CB", "v55 NAME consumer: right panel branch 1"),
    (0x08BF00, "6B C0 19 8B 16 6D 16 03 D0 FF 36 6F 16 52", "0E 68 2E 10 8C DB 80 EF 10 53 68 14 07 CB", "v55 NAME consumer: right panel branch 2"),
    (0x08BF3C, "07", "0A", "v55/v57 inventory panel 10px line grid and 30px shift"),
    (0x08C07F, "07", "0A", "v55/v57 inventory panel 10px line grid and 30px shift"),
    (0x08C0FD, "07", "0A", "v55/v57 inventory panel 10px line grid and 30px shift"),
    (0x08C134, "07", "0A", "v55/v57 inventory panel 10px line grid and 30px shift"),
    # Dialogue menu title ("WHAT DO YOU SAY?"). The overlay upper-cases the
    # DGROUP:5504 title with strupr (0:39AC) and draws it through
    # 0150:016D, which cannot decode Base94. strupr's call now lands on its
    # own retf at 0:39CF (only the offset word changes; the segment word is
    # an overlay relocation), and the argument pushes after it become a
    # tag-FF81 redirect whose decoder entry decodes Chinese titles into NAME
    # glyph slots, upper-cases English ones itself, and re-pushes the same
    # formatter arguments before returning to the untouched far call.
    (0x07D814, "AC", "CF", "v91 menu title: strupr call returns at once"),
    (0x07D818, "83 C4 04 1E 68 04 55 66 68 14 00 11 00 66 68 FE 00 2F 00 66 68 00 00 FF 00 1E 68 58 1F 66 68 06 00 04 00", "0E E8 00 00 58 05 1F 00 50 B8 81 FF 8C DB 80 EF 10 53 68 14 07 CB 90 90 90 90 90 90 90 90 90 90 90 90 90", "v91 menu title redirect"),
    # One-line window text (message boxes, "SAVING GAME"): the setter at
    # overlay 0x7045D (entry 0580:005C) strncpy's the text into a stack
    # buffer, upper-cases it and draws it one byte per glyph. The argument
    # setup before strncpy becomes a tag-FF82 redirect that returns to the
    # untouched strncpy call at overlay IP 06EE (file 0x704BE).
    (0x0704AB, "89 36 35 54 C6 46 D8 00 6A 1F 66 FF 76 0C 16 8D 46 D8 50", "B8 82 FF 0E 68 EE 06 8C DB 80 EF 10 53 68 14 07 CB 90 90", "v97 window text redirect"),
    # Resident draw_text wrapper 191F:0A40 (portrait status, item panel
    # labels...): its argument pushes become a tag-FF84 redirect that
    # returns to the untouched push dword [bp+6] / lcall 339E:016D at 1F051.
    # 191F:0401, the string width used to centre the VIEW/USE portrait status:
    # tag-FF86 redirect back to its loop test at IP 042A.
    (0x01E9F6, "66 83 7E 06 00 75 04 33 C0 EB 26 33 F6 33 FF EB 13", "B8 86 FF 0E 68 2A 04 8C DB 80 EF 10 53 68 14 07 CB", "v102 text width redirect"),
    (0x01F033, "66 FF 76 0A FF 76 14 6A 14 FF 76 12 66 68 FF 00 FE 00 6A 00 1E 68 8F 0D FF 76 10 FF 76 0E", "0E E8 00 00 58 05 1A 00 50 B8 84 FF 8C DB 80 EF 10 53 68 14 07 CB 90 90 90 90 90 90 90 90", "v102 draw_text wrapper redirect"),
)


# Item material adjectives (re_84). Both the bottom hover label and the
# right-click card copy the English word byte for byte from one resident
# DGROUP table, and neither path decodes Base94. So each word becomes a
# single byte whose FONT-100 glyph is the whole Chinese word, pre-rendered
# at build time. These six codes appear in no game text (all catalogs, the
# withheld English and EXE strings were checked; '@' only ever stood in for
# '%' in untranslated SPIN originals).
MATERIAL_TABLE_OFFSET = 0x4A102  # DGROUP:17A2, reached through 0x40A80
MATERIAL_TABLE = b"Wooden\0Bone\0Stone\0Obsidian\0Metal\0Leather\0"
MATERIAL_UNITS = (
    "UI_material_wooden", "UI_material_bone", "UI_material_stone",
    "UI_material_obsidian", "UI_material_metal", "UI_material_leather",
)
MATERIAL_CODES = (0x2A, 0x40, 0x5B, 0x5D, 0x7B, 0x7D)  # * @ [ ] { }
FONT_OFFSET_TABLE = 8 + 256
# '*' was only ever drawn as the damage multiplier ("1.5*1D6+12"): the VIEW
# CHARACTER DAM piece at DGROUP:0E71 and the two inventory damage formats
# "%d%s*%dD%d%+d" / "%d%s*%dD%d". They switch to 'x' so '*' is free.
# Natural attacks (thri-kreen claws/bite) are listed as "<1D4+8>", with the
# brackets written as byte immediates. '<' and '>' are NAME-slot transport
# codes, so they drew whatever CJK glyph those slots last held; the
# brackets become '(' and ')'. (offset of the immediate, original, new)
NATURAL_ATTACK_BRACKETS = ((0x727E8, 0x3C, 0x28), (0x72839, 0x3E, 0x29))
DGROUP_FILE_BASE = 0x48960
DAMAGE_MULTIPLIER_OFFSETS = tuple(
    DGROUP_FILE_BASE + offset for offset in (0x0E71, 0x1D46 + 4, 0x1D57 + 4)
)


# Cursor-mode hotkeys (re_104), in the overlay hotkey dispatcher (overlay
# segment 25, file 71153; its 33-key table at 71C1B, jump targets at 71C5D).
# T's debug handler (dead: [11B0] is never set in play) becomes a tag-FF87
# redirect back to the dispatcher epilogue (IP 1DD0), between the overlay
# relocations at 711CD and 711FD. The FONT core then drives the game's own
# right-click cycle: Space = walk, A = attack, S = look (S was a debug key
# too). T takes over A's animation toggle, which F6 also still has.
CURSOR_HOTKEY_STUB = 0x711D0
CURSOR_HOTKEY_STUB_IP = CURSOR_HOTKEY_STUB - 0x6FDD0
CURSOR_HOTKEY_TARGETS = 0x71C5D
ANIMATION_TOGGLE_IP = 0x17FD
CURSOR_HOTKEY_EXE_PATCHES = (
    # The resident map key handler (file 1B7E0) keeps Space for itself: it
    # calls 4251:00D9 (clears bit 20h of each party member's +21h byte) and
    # returns. Its closing jump now continues to the forward-to-dispatcher
    # path at 1BC36 instead of the exit at 1BC55, so Space still does that.
    (0x1BB8F, "E9 C3 00", "E9 A4 00", "map Space handler -> hotkey dispatcher"),
    (CURSOR_HOTKEY_STUB, "C0 26 8B 87 37 0C 6B C0 3A C4 1E 65 16 03 D8 26 8B",
     "B8 87 FF 0E 68 D0 1D 8C DB 80 EF 10 53 68 14 07 CB", "T debug handler -> tag FF87"),
    # (key index in the table, original target, new target)
    *(
        (CURSOR_HOTKEY_TARGETS + index * 2, f"{old & 0xFF:02X} {old >> 8:02X}", f"{new & 0xFF:02X} {new >> 8:02X}", key)
        for index, old, new, key in (
            (11, 0x13C8, ANIMATION_TOGGLE_IP, "T -> animation toggle"),
            (12, 0x13C8, ANIMATION_TOGGLE_IP, "t -> animation toggle"),
            (13, 0x17FD, CURSOR_HOTKEY_STUB_IP, "A -> attack cursor"),
            (14, 0x17FD, CURSOR_HOTKEY_STUB_IP, "a -> attack cursor"),
            (15, 0x13AC, CURSOR_HOTKEY_STUB_IP, "S -> look cursor"),
            (16, 0x13AC, CURSOR_HOTKEY_STUB_IP, "s -> look cursor"),
            (26, 0x150D, CURSOR_HOTKEY_STUB_IP, "Space -> walk cursor"),
        )
    ),
)


# Smart walk cursor, stage A (re_104 §9), in the resident left-click
# dispatcher 1587:06D8 (file 1B348). Its look path's two random checks only
# differ from "refuse" with the debug flag [11B0] set, so their tails are
# dead code in play: the no-line-of-sight check now jumps straight on, and
# its dead 18 bytes at 1B483 hold a tag-FF88 redirect (the relocated segment
# words at 1B481/1B4ED stay untouched behind the new jumps).
SMART_CURSOR_STUB = 0x1B483
SMART_CURSOR_EXE_PATCHES = (
    # line of sight blocked: "jmp 1B4EF" (walk towards) replaces "lcall 3015:000B"
    (0x1B47E, "9A 0B 00", "E9 6E 00", "no line of sight -> walk towards"),
    (SMART_CURSOR_STUB, "A9 03 00 75 03 E9 E4 01 83 3E B0 11 00 75 03 E9 DA",
     "B8 88 FF 0E 68 26 07 8C DB 80 EF 10 53 68 14 07 CB", "dead debug check -> tag FF88"),
    # too far: "jmp 1B4EF" replaces "lcall 3015:000B"
    (0x1B4EA, "9A 0B 00", "E9 02 00", "too far -> walk towards"),
    # mov cx, BEEFh; jmp 1B483
    (0x1B4EF, "A9 03 00 74 49 83", "B9 EF BE E9 8E FF", "walk-towards marker"),
    # left-click mode table cs:0B64, walk (mode 1): 1B396 -> the stub
    (0x1B7D4, "26 07", "13 08", "walk click -> smart cursor"),
    # Stage B arrival check. The rest of the dead debug check after the
    # marker becomes "mov cx, BEF0h; jmp 1B483", and the non-combat frame
    # update's near call (push cs; call 1C3C4) at 1C9DE calls it instead; the
    # core tail-jumps to 1C3C4 itself.
    (0x1B4F5, "3E B0 11 00 74 42", "B9 F0 BE E9 88 FF", "frame hook -> tag FF88"),
    (0x1C9DE, "E8 E3 F9", "E8 14 EB", "non-combat frame update -> frame hook"),
    # Hover icon. F6 in the map key handler's table (cs:0FEB, target at
    # +34h, index 12) only ran a debug command gated by [11B0]; it now
    # leaves through the handler's exit, and its dead code at 1B81E holds
    # "mov dx,ax; mov cx,BEF1h; jmp 1B483". icon_at's walk branch jumps
    # there with find_object's result instead of testing it for -1.
    (0x1BCA7, "AE 0B", "E5 0F", "F6 (debug only) -> key handler exit"),
    (0x1B81E, "83 3E B0 11 00 75 03 E9", "89 C2 B9 F1 BE E9 5D FC", "dead F6 code -> hover hook"),
    (0x1D86F, "3D FF FF", "E9 AC DF", "walk icon object test -> hover hook"),
)


def _apply_checked_patches(image: bytes, patches, label: str) -> bytes:
    ranges = [(offset, offset + len(bytes.fromhex(original))) for offset, original, _, _ in patches]
    for offset, original, _, origin in patches:
        expected = bytes.fromhex(original)
        if image[offset : offset + len(expected)] != expected:
            raise ValueError(f"{label} patch 0x{offset:06X} ({origin}) found modified bytes")
    relocations = mz_relocation_file_offsets(image)
    if any(start < site + 2 and end > site for site in relocations for start, end in ranges):
        raise ValueError(f"{label} patch overlaps an MZ relocation")
    verify_overlay_relocations(image, ranges)
    result = bytearray(image)
    for offset, _, patched, _ in patches:
        replacement = bytes.fromhex(patched)
        result[offset : offset + len(replacement)] = replacement
    return bytes(result)


def apply_smart_cursor_exe_patches(image: bytes) -> bytes:
    """Walk clicks on map objects look; too-far/no-sight looks walk there."""
    return _apply_checked_patches(image, SMART_CURSOR_EXE_PATCHES, "smart cursor")


def apply_cursor_hotkey_exe_patches(image: bytes) -> bytes:
    """Point Space/A/S at the FONT core's cursor-mode entry and T at animations."""
    return _apply_checked_patches(image, CURSOR_HOTKEY_EXE_PATCHES, "cursor hotkey")


def material_table_bytes() -> bytes:
    """Each English word keeps its slot; it now holds one code and NULs."""
    result = bytearray()
    for word, code in zip(MATERIAL_TABLE.split(b"\0")[:-1], MATERIAL_CODES):
        result += bytes((code,)) + bytes(len(word))
    return bytes(result)


def view_ui_patch_ranges() -> list[tuple[int, int]]:
    ranges = [(offset, offset + len(bytes.fromhex(original))) for offset, original, _, _ in VIEW_UI_EXE_PATCHES]
    ranges.append((MATERIAL_TABLE_OFFSET, MATERIAL_TABLE_OFFSET + len(MATERIAL_TABLE)))
    ranges += [(offset, offset + 1) for offset in DAMAGE_MULTIPLIER_OFFSETS]
    ranges += [(offset, offset + 1) for offset, _, _ in NATURAL_ATTACK_BRACKETS]
    return sorted(ranges)


def word_glyph_record(ids: tuple[int, ...], banks: dict[int, dict[str, object]], height: int) -> bytes:
    """Join single-character CJB1 records side by side into one wide record."""
    records = [glyph_record_for_id(value, banks) for value in ids]
    widths = [int.from_bytes(record[:2], "little") for record in records]
    for record, width in zip(records, widths):
        if len(record) != 2 + width * height:
            raise ValueError("CJB1 record does not match the bank glyph height")
    rows = b"".join(
        record[2 + row * width : 2 + (row + 1) * width]
        for row in range(height)
        for record, width in zip(records, widths)
    )
    return sum(widths).to_bytes(2, "little") + rows


def apply_view_ui_exe_patches(image: bytes) -> bytes:
    """Apply the v75 layer to a main-build DSUN.EXE, refusing any conflict."""
    ranges = view_ui_patch_ranges()
    for offset, original, _, origin in VIEW_UI_EXE_PATCHES:
        expected = bytes.fromhex(original)
        if image[offset : offset + len(expected)] != expected:
            raise ValueError(f"VIEW UI patch 0x{offset:06X} ({origin}) found modified bytes")
    relocations = mz_relocation_file_offsets(image)
    for site in relocations:
        if any(start < site + 2 and end > site for start, end in ranges):
            raise ValueError(f"VIEW UI patch overlaps MZ relocation at 0x{site:X}")
    verify_overlay_relocations(image, ranges)
    result = bytearray(image)
    for offset, _, patched, _ in VIEW_UI_EXE_PATCHES:
        replacement = bytes.fromhex(patched)
        result[offset : offset + len(replacement)] = replacement
    table_end = MATERIAL_TABLE_OFFSET + len(MATERIAL_TABLE)
    if image[MATERIAL_TABLE_OFFSET:table_end] != MATERIAL_TABLE:
        raise ValueError("material string table found modified bytes")
    result[MATERIAL_TABLE_OFFSET:table_end] = material_table_bytes()
    for offset in DAMAGE_MULTIPLIER_OFFSETS:
        if image[offset] != ord("*"):
            raise ValueError(f"damage multiplier at 0x{offset:X} found modified bytes")
        result[offset] = ord("x")
    for offset, v75_row, row in VIEW_ROW_SITES:
        if result[offset] != v75_row:
            raise ValueError(f"VIEW CHARACTER row at 0x{offset:X} is not the v75 layout")
        result[offset] = row
    for offset, original, replacement in NATURAL_ATTACK_BRACKETS:
        if image[offset] != original:
            raise ValueError(f"natural attack bracket at 0x{offset:X} found modified bytes")
        result[offset] = replacement
    final = bytes(result)
    if mz_relocation_file_offsets(final) != relocations:
        raise ValueError("VIEW UI patches changed the MZ relocation table")
    allowed = {index for start, end in ranges for index in range(start, end)}
    if any(a != b and index not in allowed for index, (a, b) in enumerate(zip(image, final))):
        raise AssertionError("VIEW UI patches changed bytes outside their ranges")
    return final


def build_view_ui_font(
    font: bytes,
    mapping: dict[str, object],
    banks: dict[int, dict[str, object]],
    *,
    cursor_hotkeys: bool = False,
    smart_cursor: bool = False,
) -> tuple[bytes, dict[str, object]]:
    """Append NAME slots, the decoder and material words to the main FONT-100."""
    bank_count = len(banks)
    if len(font) != STAGING_OFFSET + RECORD_BYTES:
        raise ValueError(f"FONT-100 is {len(font)} bytes, expected {STAGING_OFFSET + RECORD_BYTES}")
    staging = font[STAGING_OFFSET:]
    if int.from_bytes(staging[:2], "little") != 10:
        raise ValueError("FONT-100 staging record is not the 10x10 layout the decoder expects")
    expanded = font + staging * NAME_GLYPH_SLOTS
    if len(expanded) != FONT_CORE_PAYLOAD_OFFSET:
        raise AssertionError("NAME glyph slots do not end at the decoder offset")
    ids = load_fixed_ui_ids(mapping)
    core = assemble_name_slot_cache(
        backpack_ids=fixed_ui_pair_ids(ids, BACKPACK_UNITS),
        ability_ids=fixed_ui_pair_ids(ids, ABILITY_UNITS),
        view_character=True,
        view_y_origin=VIEW_Y_ORIGIN,
        label_ids=fixed_ui_pair_ids(ids, LABEL_UNITS),
        identity=True,
        alignment_position=ALIGNMENT_POSITION,
        class_names=True,
        bank_count=bank_count,
        ui_text_ids=ids,
        class_row=CLASS_ROW,
        stat_row_y=STAT_ROW_Y,
        menu_titles=True,
        status_texts=True,
        text_draws=True,
        cursor_hotkeys=cursor_hotkeys,
        smart_cursor=smart_cursor,
    )
    result = bytearray(expanded + core)
    height = next(iter(banks.values()))["height"]
    materials: dict[str, int] = {}
    for unit, code in zip(MATERIAL_UNITS, MATERIAL_CODES):
        offset = len(result)
        result += word_glyph_record(ids[unit], banks, height)
        result[FONT_OFFSET_TABLE + code * 2 : FONT_OFFSET_TABLE + code * 2 + 2] = offset.to_bytes(2, "little")
        materials[chr(code)] = offset
    if len(result) > 0x10000:
        raise ValueError("FONT-100 with the VIEW UI layer exceeds its 16-bit allocation")
    return bytes(result), {
        "name_glyph_slots": NAME_GLYPH_SLOTS,
        "decoder_offset": FONT_CORE_PAYLOAD_OFFSET,
        "decoder_bytes": len(core),
        "decoder_bank_count": bank_count,
        "material_word_offsets": materials,
        "labels": "localization/catalog/fixed_ui_labels.csv",
        "cursor_hotkeys": cursor_hotkeys,
        "smart_cursor": smart_cursor,
    }
