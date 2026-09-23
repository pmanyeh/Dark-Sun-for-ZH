"""The inventory / VIEW CHARACTER layer merged into the main display build."""
import unittest
from pathlib import Path

from tools.cjk_localization_pipeline import DEFAULT_RESOURCE_GFF, load_mapping
from tools.plan_name_slot_consumers import (
    ABILITY_UNITS,
    BACKPACK_UNITS,
    LABEL_UNITS,
    TOOLBIN,
    UI_TEXT_TABLES,
    assemble_name_slot_cache,
    fixed_ui_pair_ids,
    load_fixed_ui_ids,
    name_slot_ui_text_include,
)
from tools.view_ui_layer import (
    DAMAGE_MULTIPLIER_OFFSETS,
    FONT_OFFSET_TABLE,
    MATERIAL_CODES,
    MATERIAL_TABLE,
    MATERIAL_TABLE_OFFSET,
    MATERIAL_UNITS,
    NATURAL_ATTACK_BRACKETS,
    VIEW_UI_EXE_PATCHES,
    apply_view_ui_exe_patches,
    build_view_ui_font,
    material_table_bytes,
    view_ui_patch_ranges,
    word_glyph_record,
)

HAVE_AS = (TOOLBIN / "as.exe").exists()
PRISTINE_EXE = DEFAULT_RESOURCE_GFF.parent / "DSUN.EXE"
MAIN_MAPPING = Path("localization/cjk_mapping.json")


def synthetic_banks(bank_count=12, height=10):
    """10-pixel-wide records whose every byte is the glyph's bank index."""
    return {
        bank: {"height": height, "records": {
            index: b"\x0a\x00" + bytes([index]) * (10 * height) for index in range(256)
        }}
        for bank in range(bank_count)
    }

# The cjk-mapping-v57 IDs cjk_name_slot_cache.asm still carries as its legacy
# tables (v75 wording, Thief = 盜賊).
V57_UI_IDS = {
    "UI_material_wooden": (367, 691), "UI_material_bone": (849, 691),
    "UI_material_stone": (544, 691), "UI_material_obsidian": (871, 544, 691),
    "UI_material_metal": (762, 222, 691), "UI_material_leather": (528, 691),
    "UI_gender_male": (512, 269), "UI_gender_female": (189, 269),
    "UI_race_human": (27, 838), "UI_race_dwarf": (543, 27), "UI_race_elf": (586, 822),
    "UI_race_half_elf": (106, 586, 822), "UI_race_half_giant": (106, 227, 27),
    "UI_race_halfling": (106, 724, 27), "UI_race_mul": (1317, 484, 27),
    "UI_race_thri_kreen": (1319, 1318, 289, 1004),
    "UI_alignment_lg": (198, 1321, 1320, 1323), "UI_alignment_ln": (198, 1321, 11, 1322),
    "UI_alignment_le": (198, 1321, 753, 276), "UI_alignment_ng": (11, 1322, 1320, 1323),
    "UI_alignment_tn": (1168, 213, 11, 1322), "UI_alignment_ne": (11, 1322, 753, 276),
    "UI_alignment_cg": (453, 18, 1320, 1323), "UI_alignment_cn": (453, 18, 11, 1322),
    "UI_alignment_ce": (453, 18, 753, 276),
    "UI_class_cleric": (1325, 232), "UI_class_druid": (261, 1329, 36),
    "UI_class_fighter": (289, 1004), "UI_class_gladiator": (697, 857, 1004),
    "UI_class_preserver": (51, 709, 617), "UI_class_psionicist": (822, 629, 232),
    "UI_class_ranger": (1240, 1324), "UI_class_thief": (1326, 1328),
}
V75_OPTIONS = dict(
    backpack_ids=(1303, 100),
    ability_ids=(93, 761, 1316, 1315, 855, 715, 354, 93, 354, 1314, 860, 93),
    view_character=True,
    view_y_origin=63,
    label_ids=(794, 560, 822, 629, 507, 139, 822, 629),
    identity=True,
    alignment_position=(44, 149),
    class_names=True,
)


@unittest.skipUnless(HAVE_AS, "requires the GNU toolchain")
class NameSlotTextGenerationTests(unittest.TestCase):
    def test_generated_tables_match_the_legacy_v57_tables(self):
        legacy = assemble_name_slot_cache(**V75_OPTIONS)
        generated = assemble_name_slot_cache(**V75_OPTIONS, ui_text_ids=V57_UI_IDS)
        self.assertEqual(generated, legacy)

    def test_bank_table_follows_bank_count(self):
        six = assemble_name_slot_cache(**V75_OPTIONS)
        twelve = assemble_name_slot_cache(**V75_OPTIONS, bank_count=12)
        self.assertIn(b"C0\0C1\0C2\0C3\0C4\0C5\0\"", six)
        self.assertIn(b"C5\0C6\0C7\0C8\0C9\0C10\0C11\0\"", twelve)
        # glyph_loader: mov al,ah; cmp al,bank_count
        self.assertIn(bytes.fromhex("88 E0 3C 06"), six)
        self.assertIn(bytes.fromhex("88 E0 3C 0C"), twelve)

    def test_ids_beyond_the_banks_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "within the 6 CJB1 banks"):
            assemble_name_slot_cache(backpack_ids=(1536, 0))
        assemble_name_slot_cache(backpack_ids=(3002, 0), bank_count=12)
        with self.assertRaisesRegex(ValueError, "outside the 6 banks"):
            assemble_name_slot_cache(**V75_OPTIONS, ui_text_ids={**V57_UI_IDS, "UI_class_ranger": (3002,)})


class FixedUiLabelTests(unittest.TestCase):
    def test_main_mapping_resolves_every_label(self):
        ids = load_fixed_ui_ids(load_mapping(MAIN_MAPPING))
        units = {unit for _, _, _, rows in UI_TEXT_TABLES.values() for _, unit in rows}
        self.assertLessEqual(units | set(BACKPACK_UNITS + ABILITY_UNITS + LABEL_UNITS), set(ids))
        self.assertEqual(len(fixed_ui_pair_ids(ids, ABILITY_UNITS)), 12)
        self.assertEqual(len(fixed_ui_pair_ids(ids, LABEL_UNITS)), 8)
        self.assertIn(".macro ui_text_classes", name_slot_ui_text_include(ids))

    def test_fixed_stride_lengths_are_enforced(self):
        ids = dict(V57_UI_IDS, UI_gender_male=(512, 269, 1))
        with self.assertRaisesRegex(ValueError, "exactly 2 characters"):
            name_slot_ui_text_include(ids)
        ids = dict(V57_UI_IDS, UI_alignment_tn=(1168, 213, 11))
        with self.assertRaisesRegex(ValueError, "exactly 4 characters"):
            name_slot_ui_text_include(ids)


class ViewUiExePatchTests(unittest.TestCase):
    def test_patch_runs_are_sorted_and_disjoint(self):
        ranges = view_ui_patch_ranges()
        self.assertEqual(ranges, sorted(ranges))
        for (_, end), (start, _) in zip(ranges, ranges[1:]):
            self.assertLessEqual(end, start)
        for _, original, patched, _ in VIEW_UI_EXE_PATCHES:
            self.assertEqual(len(bytes.fromhex(original)), len(bytes.fromhex(patched)))

    @unittest.skipUnless(PRISTINE_EXE.exists(), "pristine DSUN.EXE is not present")
    def test_applies_to_pristine_and_refuses_conflicts(self):
        image = PRISTINE_EXE.read_bytes()
        patched = apply_view_ui_exe_patches(image)
        for offset, _, replacement, _ in VIEW_UI_EXE_PATCHES:
            expected = bytes.fromhex(replacement)
            self.assertEqual(patched[offset : offset + len(expected)], expected)
        table = patched[MATERIAL_TABLE_OFFSET : MATERIAL_TABLE_OFFSET + len(MATERIAL_TABLE)]
        self.assertEqual(table, material_table_bytes())
        self.assertEqual(bytes(patched[offset] for offset in DAMAGE_MULTIPLIER_OFFSETS), b"xxx")
        self.assertEqual(bytes(patched[offset] for offset, _, _ in NATURAL_ATTACK_BRACKETS), b"()")
        with self.assertRaisesRegex(ValueError, "found modified bytes"):
            apply_view_ui_exe_patches(patched)

    def test_material_words_keep_their_table_slots(self):
        table = material_table_bytes()
        self.assertEqual(len(table), len(MATERIAL_TABLE))
        starts = [0] + [index + 1 for index, value in enumerate(MATERIAL_TABLE) if value == 0][:-1]
        self.assertEqual([table[start] for start in starts], list(MATERIAL_CODES))
        self.assertTrue(all(table[start + 1] == 0 for start in starts))


@unittest.skipUnless(HAVE_AS, "requires the GNU toolchain")
class ViewUiFontTests(unittest.TestCase):
    def test_font_gets_slots_decoder_and_material_words(self):
        staging = b"\x0a\x00" + bytes(100)
        font = bytes(0x206B) + staging
        mapping = load_mapping(MAIN_MAPPING)
        result, info = build_view_ui_font(font, mapping, synthetic_banks())
        self.assertEqual(result[len(font) : 0x239B], staging * 7)
        self.assertEqual(info["decoder_bank_count"], 12)
        # Only the six material entries of the offset table change.
        changed = {i for i in range(len(font)) if result[i] != font[i]}
        entries = {FONT_OFFSET_TABLE + code * 2 + half for code in MATERIAL_CODES for half in (0, 1)}
        self.assertLessEqual(changed, entries)
        ids = load_fixed_ui_ids(mapping)
        cursor = 0x239B + info["decoder_bytes"]
        for code, unit in zip(MATERIAL_CODES, MATERIAL_UNITS):
            entry = FONT_OFFSET_TABLE + code * 2
            self.assertEqual(int.from_bytes(result[entry : entry + 2], "little"), cursor)
            self.assertEqual(int.from_bytes(result[cursor : cursor + 2], "little"), 10 * len(ids[unit]))
            cursor += 2 + 100 * len(ids[unit])
        self.assertEqual(len(result), cursor)

    def test_word_glyph_joins_rows_side_by_side(self):
        record = word_glyph_record((3, 7), synthetic_banks(bank_count=1, height=2), 2)
        self.assertEqual(record, b"\x14\x00" + (bytes([3]) * 10 + bytes([7]) * 10) * 2)

    def test_font_layout_is_checked(self):
        with self.assertRaisesRegex(ValueError, "expected 8401"):
            build_view_ui_font(bytes(100), load_mapping(MAIN_MAPPING), synthetic_banks())


if __name__ == "__main__":
    unittest.main()
