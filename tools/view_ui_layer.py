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

import hashlib

try:
    from .cjk_localization_pipeline import glyph_record_for_id
    from .creation_icon_layer import CLASS_LIST_BUTTONS
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
    from creation_icon_layer import CLASS_LIST_BUTTONS
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
    # Spell learning scroll (overlay segment 45, function 0x85CC9, re_104 §16):
    # its two centred lines, and the erases of the previous two, draw through
    # 339E:016D without decoding Base94. Each argument block becomes
    # "push bx; tag-FF89 redirect" returning to the block's own lcall.
    (0x085D23, "66 FF 36 7E 9B FF 76 12 6A 14 FF 76 12 66 68 FF 00 FE 00 6A 00 1E 68 18 30 FF 76 0A 53 66 FF 76 06", "53 B8 89 FF 0E 68 E4 07 8C DB 80 EF 10 53 68 14 07 CB 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90", "v118 spell scroll erase line 1 redirect"),
    (0x085D8B, "66 FF 76 14 FF 76 10 6A 14 FF 76 0E 66 68 FF 00 FE 00 6A 00 1E 68 18 30 FF 76 0A 53 66 FF 76 06", "53 B8 89 FF 0E 68 4B 08 8C DB 80 EF 10 53 68 14 07 CB 90 90 90 90 90 90 90 90 90 90 90 90 90 90", "v118 spell scroll draw line 1 redirect"),
    (0x085DFB, "66 FF 36 7A 9B FF 76 12 6A 14 FF 76 12 66 68 FF 00 FE 00 6A 00 1E 68 18 30 8B 46 0A 05 07 00 50 53 66 FF 76 06", "53 B8 89 FF 0E 68 C0 08 8C DB 80 EF 10 53 68 14 07 CB 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90", "v118 spell scroll erase line 2 redirect"),
    (0x085E67, "66 FF 76 18 FF 76 10 6A 14 FF 76 0E 66 68 FF 00 FE 00 6A 00 1E 68 18 30 8B 46 0A 05 07 00 50 53 66 FF 76 06", "53 B8 89 FF 0E 68 2B 09 8C DB 80 EF 10 53 68 14 07 CB 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90 90", "v118 spell scroll draw line 2 redirect"),
    # The function then copies only rows y+2..y+16 of its buffer to the
    # screen (0188:0BE0(x0, y0, x1, y1) at 0x85ED4), sized for two seven-row
    # English lines. Chinese lines span y-3..y+17 (see scroll_text_entry),
    # so the rows above y+2 kept the previous text's top on screen (v119).
    (0x085EB4, "05 10 00", "05 12 00", "v120 spell scroll screen update: bottom y+16 -> y+18"),
    (0x085EC8, "05 02 00", "05 FD FF", "v120 spell scroll screen update: top y+2 -> y-3"),
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


# Smart walk cursor (re_104 §9-§11, §18), in the resident left-click
# dispatcher 1587:06D8 (file 1B348). Its look path's two checks, "no line
# of sight" and "too far", each read the Shift keys (3015:000B, int 16h
# AH=2) and only let the look through with the debug flag [11B0] set
# (-k911) and Shift held. Their tails move into
# the FONT core, which runs them exactly as before in debug mode and walks
# towards the object otherwise; the 18 bytes at 1B483 hold the tag-FF88
# redirect (the relocated segment words at 1B481/1B4ED stay untouched
# behind the new jumps). Every other original key and debug command keeps
# its code: the markers and the cursor-mode hotkeys live in bytes freed by
# rewriting the map key handler's table search below.
SMART_CURSOR_STUB = 0x1B483
SMART_CURSOR_EXE_PATCHES = (
    # The map key handler (1587:0B70, file 1B7E0) searches its 26-key table
    # (cs:0FEB, targets at +34h) with a 32-byte loop. The same search as
    # "repne scasw" takes 20 bytes: [bp-6] only ever held the key for that
    # loop, and no handler reads BX, CX, DI or ES before setting them. The
    # freed bytes hold two markers: an unknown key goes to the core (CX =
    # BEF2h), which takes Z/X/D (--cursor-hotkeys) and sends every other
    # key on to the original fallback at 1BB92; and the no-line-of-sight
    # marker (CX = BEF3h) at 1B80B.
    (0x1B7F1, "8B 46 12 89 46 FA B9 1A 00 BB EB 0F 2E 8B 07 3B 46 FA 74 08 83 C3 02 E2 F3 E9 85 03 2E FF 67 34",
     "8B 46 12 0E 07 BF EB 0F B9 1A 00 FC F2 AF 74 06 B9 F2 BE E9 7C FC 2E FF 65 32 B9 F3 BE E9 72 FC",
     "map key table search as repne scasw; unknown-key and no-sight markers"),
    # line of sight blocked: "jmp 1B80B" replaces "lcall 3015:000B"
    (0x1B47E, "9A 0B 00", "E9 8A 03", "no line of sight -> core"),
    (SMART_CURSOR_STUB, "A9 03 00 75 03 E9 E4 01 83 3E B0 11 00 75 03 E9 DA",
     "B8 88 FF 0E 68 26 07 8C DB 80 EF 10 53 68 14 07 CB", "look path debug check -> tag FF88"),
    # too far: "jmp 1B4EF" replaces "lcall 3015:000B"
    (0x1B4EA, "9A 0B 00", "E9 02 00", "too far -> core"),
    # mov cx, BEEFh; jmp 1B483
    (0x1B4EF, "A9 03 00 74 49 83", "B9 EF BE E9 8E FF", "too-far marker"),
    # left-click mode table cs:0B64, walk (mode 1): 1B396 -> the stub
    (0x1B7D4, "26 07", "13 08", "walk click -> smart cursor"),
    # attack (mode 4): 1B67B -> the stub; the core tells the modes apart by
    # [11B8] and resumes 1B67B unless the target is out of reach
    (0x1B7DA, "0B 0A", "13 08", "attack click -> smart cursor"),
    # Stage B arrival check. The rest of the dead debug check after the
    # marker becomes "mov cx, BEF0h; jmp 1B483", and the non-combat frame
    # update's near call (push cs; call 1C3C4) at 1C9DE calls it instead; the
    # core tail-jumps to 1C3C4 itself.
    (0x1B4F5, "3E B0 11 00 74 42", "B9 F0 BE E9 88 FF", "frame hook -> tag FF88"),
    (0x1C9DE, "E8 E3 F9", "E8 14 EB", "non-combat frame update -> frame hook"),
    # Hover icon. After find_object, icon_at's walk branch runs "mov dx,ax;
    # mov cx,BEF1h; jmp 1B483" instead of "add sp,8; cmp ax,-1; jne 2C26";
    # the core drops the call's 8 argument bytes itself.
    (0x1D86C, "83 C4 08 3D FF FF 75 22", "8B D0 B9 F1 BE E9 0F DC", "walk icon object test -> hover hook"),
)


# Character creation (CREATE CHARACTERS -> NEW, re_105). DGROUP:0F62 holds
# the lower-left panel's ten field rectangles (x0, y0, x1, y1); the screen
# erases a field with its rectangle, draws it at (x0, y0 - 2) and places the
# alignment/HP boxes at x0 - 7 and the ability boxes at x0 - 30. The English
# rows are 7px apart; the Chinese layout uses 10px rows, draws Chinese at y0
# (the decoder's char_creation entries) and puts HP and PSP on one row.
CREATION_RECTS_OFFSET = DGROUP_FILE_BASE + 0x0F62
CREATION_RECTS_ORIGINAL = (
    (33, 137, 48, 178),    # ability values
    (86, 137, 190, 143),   # gender and race
    (86, 144, 180, 150),   # alignment
    (86, 151, 250, 157),   # class
    (86, 158, 121, 164),   # level
    (122, 158, 258, 164),  # EXP
    (86, 172, 140, 178),   # HP
    (86, 179, 140, 185),   # PSP
    (86, 165, 121, 171),   # AC
    (122, 165, 243, 171),  # DAM
)
CREATION_RECTS = (
    (41, 138, 56, 194),
    (86, 133, 190, 142),
    (86, 144, 180, 153),
    (86, 155, 250, 164),
    (86, 166, 121, 172),
    (122, 166, 258, 172),
    (86, 185, 150, 194),
    (158, 185, 240, 194),
    (86, 174, 127, 183),
    (130, 176, 243, 182),
)
CREATION_ABILITY_PITCH = 10


def _rects_hex(rects) -> str:
    return b"".join(value.to_bytes(2, "little") for rect in rects for value in rect).hex(" ").upper()


# The HP/PSP helpers' pushes after the sprintf'd buffer pointer (whose
# segment word is relocated) become tag-FF8A/FF8B redirects back to the far call.
_STAT_ARGUMENTS = "FF 36 70 32 6A 14 FF 36 6E 32 68 FE 00 A0 58 1A B4 00 50 6A 00 1E 68 11 0E FF 76 14 56 66 FF 76 06"


def _stat_redirect(tag: int) -> str:
    return f"0E E8 00 00 58 05 1D 00 50 B8 {tag:02X} FF 8C DB 80 EF 10 53 68 14 07 CB" + " 90" * 11


CREATION_EXE_PATCHES = (
    (CREATION_RECTS_OFFSET, _rects_hex(CREATION_RECTS_ORIGINAL), _rects_hex(CREATION_RECTS), "v122 character creation field rectangles"),
    (0x065001, "07", "0A", "v122 character creation ability boxes: 10px rows"),
    (0x065015, "07", "0A", "v122 character creation ability boxes: 10px rows"),
    (0x065030, "07", "0A", "v122 character creation ability box shadows: 10px rows"),
    (0x06504A, "07", "0A", "v122 character creation ability box shadows: 10px rows"),
    (0x0651C2, "07", "0A", "v122 character creation ability values: 10px rows"),
    (0x064CC1, _STAT_ARGUMENTS, _stat_redirect(0x8A), "v122 HP numbers redirect (character creation label)"),
    (0x064D44, _STAT_ARGUMENTS, _stat_redirect(0x8B), "v122 PSP numbers redirect (character creation label)"),
    # WIND-3012/3013 titles: the pushes after the window's surface was
    # returned in DX:AX become tag-FF8C/FF8D redirects to the far call.
    # Selection diamond rows of the PSI/sphere lists (far data 0338:01AB,
    # window y 88 + 15 + 8i): the list rows are 10px apart now.
    # "NAME:" (overlay 0x65FD9, push dword 007D0004h) moves up with the
    # name box (WIND-3011 EBOX 4003) to give the 10px ability rows room.
    (0x065FDD, "7D", "7A", "v128 character creation NAME row 3px higher"),
    # Text button labels (DROP, SPLIT, EXIT... in BUTN chunks) are centred
    # by the layout at resident 0x2F8C0 with the width sum 2847:00B9, which
    # counts a Base94 triple as three characters. Its identical twin 2847:00ED
    # (one caller, 0x30441, moved to 00B9) becomes a tag-FF8E entry that
    # measures the decoded label and returns into 00B9's loop; the layout's
    # two width calls then use 00ED. The relocated words at 0x2D96A and
    # 0x2D97B stay untouched: a short jump skips the first, the second lies
    # in the now unused tail.
    (0x030442, "ED", "B9", "v138 2847:00ED's only caller uses the identical 00B9"),
    (0x02D95D, "55 8B EC 56 39 26 9C 00 72 05 9A", "55 8B EC 56 B8 8E FF 0E 68 DF 00", "v138 decoding label width entry (2847:00ED)"),
    (0x02D968, "0B 23", "EB 02", "v138 decoding label width entry: skip the relocated word"),
    (0x02D96C, "33 F6 EB 13 C4 5E 06 26 8A 07", "8C DB 80 EF 10 53 68 14 07 CB", "v138 decoding label width entry: FONT trampoline"),
    (0x02F969, "B9", "ED", "v138 text button label centring uses the decoding width"),
    (0x02F97E, "B9", "ED", "v138 text button label right-alignment uses the decoding width"),
    # VIEW CHARACTER HP numbers are centred on x (push dword 007F00BDh); a
    # three-digit "106/106" centred on 189 reached back over the 生命: label
    # (149..174). Centred on 196 it starts at 175 and still ends before 靈能:.
    (0x08A2D1, "BD", "C4", "v134 VIEW CHARACTER HP numbers centred 7px right"),
    # Combat info card (resident 0x1EA9A): name, HP, status and move were
    # centred 6px apart at y 6/12/18/24 inside a 26px-tall panel. Chinese
    # status and "移動:%d" need 10px rows (drawn 2px low by the FF84 path),
    # so the move count joins the HP row (HP centred 23px left of the card's
    # centre, move 21px right) and the status gets the last row alone.
    (0x01EAEE, "06", "04", "v130 combat card: name row y 6 -> 4"),
    (0x01EB8C, "D7 00", "C0 00", "v130 combat card: HP centred 23px left"),
    (0x01EC13, "12", "16", "v130 combat card: status row y 18 -> 22"),
    (0x01EC7B, "18", "0B", "v130 combat card: move shares the HP row"),
    (0x01EC7F, "D7 00", "EC 00", "v130 combat card: move centred 21px right"),
    # Class list selection diamond rows (far data 0338:019B), the class
    # buttons' y: 10 + 8i in English, 4 + 10i with the Chinese ICONs.
    (0x03E2DB, "0A 00 12 00 1A 00 22 00 2A 00 32 00 3A 00 42 00",
     "04 00 0E 00 18 00 22 00 2C 00 36 00 40 00 4A 00", "v129 class list diamond rows: 10px"),
    (0x03E2EB, "67 00 6F 00 77 00 7F 00", "67 00 71 00 7B 00 85 00", "v127 PSI/sphere list diamond rows: 10px"),
    (0x067C0D, "1E 68 DB 10 66 68 14 00 3C 00 66 68 FE 00 FE 00 66 68 00 00 FF 00 1E 68 D2 10 66 68 0E 00 06 00 52 50",
     "0E E8 00 00 58 05 1E 00 50 B8 8C FF 8C DB 80 EF 10 53 68 14 07 CB" + " 90" * 12, "v127 PSI DISCIPLINES title redirect"),
    (0x06414D, "1E 68 1A 0E 66 68 14 00 3C 00 66 68 FE 00 FE 00 66 68 00 00 FF 00 1E 68 11 0E 66 68 0E 00 06 00 52 50",
     "0E E8 00 00 58 05 1E 00 50 B8 8D FF 8C DB 80 EF 10 53 68 14 07 CB" + " 90" * 12, "v127 CLERICAL SPHERE title redirect"),
)
VIEW_UI_EXE_PATCHES = VIEW_UI_EXE_PATCHES + CREATION_EXE_PATCHES

# WIND-3011 is the character creation window. Its buttons store only their
# top-left corner; the size (ability 50x5, alignment 82x7, HP 58x5) comes
# with the button, so moving the corner moves the clickable area.
CREATION_WIND_SHA256 = "9b623e841703b2ef4ea4b81abf43d07cd146ea85293f597a3872db3ac617077b"
CREATION_WIND_BUTTONS = {
    0x07DB: ((79, 145), (79, 146)),  # alignment
    **{0x07DC + row: ((4, 139 + 7 * row), (11, 138 + CREATION_ABILITY_PITCH * row)) for row in range(6)},
    0x07E2: ((79, 174), (79, 187)),  # HP
    **CLASS_LIST_BUTTONS,  # the Chinese class ICONs are 10px tall
}


# The player name box (EBOX 4003, 95x8) and the NAME: label sit 3px higher.
CREATION_NAME_BOX = ((40, 125), (40, 122))
CREATION_WIND_CHILDREN = {
    **{(b"BUTN", button_id): corners for button_id, corners in CREATION_WIND_BUTTONS.items()},
    (b"EBOX", 0x0FA3): CREATION_NAME_BOX,
}


def patch_creation_wind(source: bytes) -> bytes:
    """Move the ability, alignment and HP buttons onto the new rows."""
    if hashlib.sha256(source).hexdigest() != CREATION_WIND_SHA256:
        raise ValueError("WIND-3011 source fingerprint does not match the verified layout")
    patched = bytearray(source)
    for (kind, button_id), (old, new) in CREATION_WIND_CHILDREN.items():
        marker = kind + button_id.to_bytes(4, "little")
        if source.count(marker) != 1:
            raise ValueError(f"WIND-3011 needs exactly one {kind.decode()} {button_id:#06x}")
        offset = source.index(marker) + 8
        if (int.from_bytes(source[offset:offset + 2], "little"), int.from_bytes(source[offset + 2:offset + 4], "little")) != old:
            raise ValueError(f"WIND-3011 {kind.decode()} {button_id:#06x} is not at its original position")
        patched[offset:offset + 2] = new[0].to_bytes(2, "little")
        patched[offset + 2:offset + 4] = new[1].to_bytes(2, "little")
    return bytes(patched)


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
    """Walk clicks on map objects look; too-far/no-sight looks walk there.

    The same patches route unknown map keys to the core, where
    --cursor-hotkeys picks up Z/X/D, so that option needs no EXE patch.
    """
    return _apply_checked_patches(image, SMART_CURSOR_EXE_PATCHES, "smart cursor")


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
        scroll_texts=True,
        cursor_hotkeys=cursor_hotkeys,
        smart_cursor=smart_cursor,
        char_creation=True,
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
