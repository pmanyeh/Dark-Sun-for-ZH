from __future__ import annotations

import json
import struct
import unittest
from pathlib import Path

from tools.build_cjk_display_staging import (
    build_native_height_scratch_font,
    build_native_height_scratch_font_slots,
    plan_dynamic_font_slots,
    predecode_name_to_dynamic_slots,
    scale_graphics_config,
    set_mouse_autolock,
)
from tools.cjk_localization_pipeline import encode_text, load_mapping, transport_for_id
from tools.build_name_slot_candidate_from_v33 import expand_v33_font
from tools.patch_dsun_scratch_cache import mz_relocation_file_offsets
from tools.plan_name_slot_consumers import (
    DECODER_OFFSET,
    DGROUP_FILE_BASE,
    FONT_CORE_PAYLOAD_OFFSET,
    FONT_RUNTIME_BASE_OFFSET,
    NAME_POINTER_SEQUENCE,
    ITEM_LINE_ADVANCE_PATCHES,
    LEGACY_HEIGHT_HELPER,
    POINTER_CELL_OFFSET,
    POINTER_INITIALIZER_HEIGHT_HELPER,
    PROVEN_CONSUMER_OFFSETS,
    RESIDENT_TRAMPOLINE_OFFSET,
    assemble_name_slot_cache,
    build_in_memory_v33_name_slot_executable,
    build_in_memory_v37_name_slot_executable,
    consumer_redirect_bytes,
    consumer_segment_relocations,
    ds_relative_consumer_redirect_bytes,
    CONSUMER_CONTINUATION_IPS,
    height_helper_redirect,
    resident_font_trampoline,
    verify_proven_consumer_sites,
)
class CjkDisplayStagingTests(unittest.TestCase):
    def test_native_height_font_preserves_legacy_bytes_and_appends_scratch(self) -> None:
        source_path = Path("scratch_test/FONT-100.clean-current.bin")
        if not source_path.exists():
            self.skipTest("clean extracted FONT-100 fixture is not present")
        source = source_path.read_bytes()
        scratch = b"\x0a\x00" + bytes(10 * 9)
        result, offset = build_native_height_scratch_font(source, scratch, 9)
        self.assertEqual(offset, len(source))
        self.assertEqual(result[:offset], source)
        self.assertEqual(result[offset:], scratch)

    def test_native_height_font_rejects_global_height_change(self) -> None:
        source_path = Path("scratch_test/FONT-100.clean-current.bin")
        if not source_path.exists():
            self.skipTest("clean extracted FONT-100 fixture is not present")
        with self.assertRaisesRegex(ValueError, "refusing to change global FONT height"):
            build_native_height_scratch_font(source_path.read_bytes(), b"\x10\x00" + bytes(240), 15)

    def test_independent_ten_row_cjk_record_preserves_nine_row_font(self) -> None:
        source_path = Path("scratch_test/FONT-100.clean-current.bin")
        if not source_path.exists():
            self.skipTest("clean extracted FONT-100 fixture is not present")
        source = source_path.read_bytes()
        scratch = b"\x0a\x00" + bytes(10 * 10)
        result, offset = build_native_height_scratch_font(source, scratch, 10)
        self.assertEqual(result[:offset], source)
        self.assertEqual(result[offset:], scratch)

    def test_seven_scratch_slots_are_contiguous_and_append_only(self) -> None:
        source_path = Path("scratch_test/FONT-100.clean-current.bin")
        if not source_path.exists():
            self.skipTest("clean extracted FONT-100 fixture is not present")
        source = source_path.read_bytes()
        records = tuple(
            b"\x0a\x00" + bytes([index]) * (10 * 10) for index in range(7)
        )
        result, offsets = build_native_height_scratch_font_slots(source, records, 10)
        self.assertEqual(
            offsets, tuple(len(source) + index * len(records[0]) for index in range(7))
        )
        self.assertEqual(result[: len(source)], source)
        for offset, record in zip(offsets, records):
            self.assertEqual(result[offset : offset + len(record)], record)
        self.assertEqual(len(result), len(source) + 7 * len(records[0]))
        self.assertEqual(offsets[0], 0x206B)
        self.assertEqual(len(records[0]), 102)
        self.assertEqual(len(result), 0x2335)

    def test_scratch_slot_builder_rejects_empty_record_set(self) -> None:
        source_path = Path("scratch_test/FONT-100.clean-current.bin")
        if not source_path.exists():
            self.skipTest("clean extracted FONT-100 fixture is not present")
        with self.assertRaisesRegex(ValueError, "at least one scratch record"):
            build_native_height_scratch_font_slots(source_path.read_bytes(), (), 9)

    def test_seven_control_codes_redirect_to_exact_scratch_records(self) -> None:
        source_path = Path("scratch_test/FONT-100.clean-current.bin")
        if not source_path.exists():
            self.skipTest("clean extracted FONT-100 fixture is not present")
        source = source_path.read_bytes()
        records = tuple(
            b"\x0a\x00" + bytes([0x40 + index]) * 100 for index in range(7)
        )
        payload, offsets = build_native_height_scratch_font_slots(source, records, 10)
        plan = plan_dynamic_font_slots(tuple(range(1, 8)), offsets)
        self.assertEqual(
            tuple(entry for _, entry, _ in plan), tuple(range(0x10A, 0x118, 2))
        )
        patched = bytearray(payload)
        for _, table_entry, scratch_offset in plan:
            patched[table_entry : table_entry + 2] = scratch_offset.to_bytes(2, "little")
        for index, (code, table_entry, scratch_offset) in enumerate(plan):
            self.assertEqual(code, index + 1)
            self.assertEqual(
                int.from_bytes(patched[table_entry : table_entry + 2], "little"),
                scratch_offset,
            )
            self.assertEqual(
                patched[scratch_offset : scratch_offset + 102], records[index]
            )

    def test_dynamic_slot_plan_rejects_unsafe_or_ambiguous_codes(self) -> None:
        for codes in ((0,), (0x80,), (1, 1)):
            with self.subTest(codes=codes), self.assertRaises(ValueError):
                plan_dynamic_font_slots(codes, (0x206B,) * len(codes))
        with self.assertRaisesRegex(ValueError, "counts do not match"):
            plan_dynamic_font_slots((1, 2), (0x206B,))

    def test_dynamic_slot_codes_do_not_collide_with_encoded_object_names(self) -> None:
        catalog = json.loads(
            Path("localization/NAME_objects_translated.json").read_text(encoding="utf-8")
        )
        mapping = load_mapping(Path("localization/cjk_mapping.json"))
        reserved = set(range(1, 8))
        for entry in catalog["entries"]:
            if not entry.get("zh"):
                continue
            encoded = encode_text(entry["zh"], mapping)
            self.assertTrue(
                reserved.isdisjoint(encoded),
                f"NAME id {entry['id']} uses a reserved dynamic slot code",
            )

    def test_name_predecoder_preserves_ascii_and_reuses_repeated_glyphs(self) -> None:
        payload = b"Bone " + transport_for_id(12) + transport_for_id(34) + transport_for_id(12)
        decoded, bindings = predecode_name_to_dynamic_slots(payload)
        self.assertEqual(decoded, b"Bone \x01\x02\x01")
        self.assertEqual(bindings, ((1, 12), (2, 34)))

    def test_all_translated_object_names_fit_seven_dynamic_slots(self) -> None:
        catalog = json.loads(
            Path("localization/NAME_objects_translated.json").read_text(encoding="utf-8")
        )
        mapping = load_mapping(Path("localization/cjk_mapping.json"))
        maximum = (0, None)
        for entry in catalog["entries"]:
            if not entry.get("zh"):
                continue
            encoded = encode_text(entry["zh"], mapping)
            decoded, bindings = predecode_name_to_dynamic_slots(encoded)
            self.assertNotIn(b"^", decoded)
            self.assertLessEqual(len(bindings), 7)
            maximum = max(maximum, (len(bindings), entry["id"]))
        self.assertEqual(maximum[0], 7)

    def test_name_predecoder_rejects_malformed_or_oversized_input(self) -> None:
        for payload in (b"^", b"^!", b"^ \x21", b"abc\x00"):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                predecode_name_to_dynamic_slots(payload)
        eight_distinct = b"".join(transport_for_id(value) for value in range(8))
        with self.assertRaisesRegex(ValueError, "more than 7"):
            predecode_name_to_dynamic_slots(eight_distinct)

    def test_rejected_direct_redirects_fit_but_are_not_main_mz_relocations(self) -> None:
        executable = Path(
            "scratch_test/cjk_display_staging_v33_dense_banks/GAME/DARKSUN/DSUN.EXE"
        )
        if not executable.exists():
            self.skipTest("stable v33 executable fixture is not present")
        image = executable.read_bytes()
        self.assertEqual(verify_proven_consumer_sites(image), PROVEN_CONSUMER_OFFSETS)
        replacement = consumer_redirect_bytes()
        self.assertEqual(len(replacement), len(NAME_POINTER_SEQUENCE))
        self.assertEqual(len(replacement), 14)
        self.assertEqual(replacement[:5], bytes.fromhex("9A F1 51 86 2E"))
        self.assertEqual(replacement[5:7], bytes.fromhex("52 50"))

        existing = mz_relocation_file_offsets(image)
        planned = consumer_segment_relocations()
        self.assertTrue(existing.isdisjoint(planned))
        header_paragraphs = int.from_bytes(image[8:10], "little")
        relocation_table = int.from_bytes(image[0x18:0x1A], "little")
        relocation_count = int.from_bytes(image[6:8], "little")
        available_entries = (header_paragraphs * 16 - relocation_table) // 4
        self.assertLessEqual(relocation_count + len(planned), available_entries)

    def test_name_slot_cache_assembles_inside_font_allocation(self) -> None:
        payload = assemble_name_slot_cache()
        self.assertLessEqual(DECODER_OFFSET + len(payload), 0x10000)
        self.assertEqual(
            DECODER_OFFSET,
            FONT_CORE_PAYLOAD_OFFSET + FONT_RUNTIME_BASE_OFFSET,
        )
        self.assertIn(b"C0\0C1\0C2\0C3\0C4\0C5\0", payload)
        self.assertIn(bytes.fromhex("CD 21"), payload)
        # GAS Intel syntax otherwise treats a bare label as a DS memory
        # operand.  These four sites must be explicit immediate addresses.
        # name_buffer follows the ten transport codes; dir_entry precedes
        # the six-word bank-name table.
        transport = payload.index(bytes.fromhex("22 23 26 3C 3E 5C 7E 60 5F 7C"))
        name_buffer = struct.pack("<H", DECODER_OFFSET + transport + 10)
        name_end = struct.pack("<H", DECODER_OFFSET + transport + 10 + 24)
        dir_entry = struct.pack("<H", DECODER_OFFSET + payload.index(b"C0\0") - 12 - 4)
        self.assertIn(b"\xBF" + name_buffer, payload)
        self.assertIn(b"\x81\xFF" + name_end, payload)
        self.assertIn(b"\xB8" + name_buffer, payload)
        self.assertIn(b"\xBA" + dir_entry, payload)
        redirect = height_helper_redirect()
        self.assertEqual(len(redirect), 11)
        self.assertEqual(redirect[0], 0xE9)
        self.assertEqual(
            resident_font_trampoline(),
            bytes.fromhex("06 C4 1E 78 A3 81 C3 9B 23 06 53 CB"),
        )

    def test_name_cache_font_layout_keeps_staging_separate_from_seven_slots(self) -> None:
        source = Path("scratch_test/FONT-100.clean-current.bin").read_bytes()
        records = tuple(b"\x0a\x00" + bytes([index]) * 100 for index in range(8))
        payload, offsets = build_native_height_scratch_font_slots(source, records, 10)
        self.assertEqual(offsets[0], 0x206B)  # legacy loader staging
        self.assertEqual(offsets[1], 0x20D1)  # dynamic code 0x01
        self.assertEqual(offsets[-1], 0x2335)  # dynamic code 0x07
        self.assertEqual(len(payload), 0x239B)
        plan = plan_dynamic_font_slots(range(1, 8), offsets[1:])
        self.assertEqual(tuple(item[2] for item in plan), offsets[1:])

    def test_v33_font_expansion_appends_only_seven_persistent_records(self) -> None:
        source = Path("scratch_test/FONT-100.clean-current.bin").read_bytes()
        staging = b"\x0a\x00" + bytes(range(100))
        current = source + staging
        expanded, offsets = expand_v33_font(current)
        self.assertEqual(expanded[: len(current)], current)
        self.assertEqual(expanded[len(current) :], staging * 7)
        self.assertEqual(offsets, tuple(range(0x20D1, 0x239B, 102)))
        self.assertEqual(len(expanded), 0x239B)

    def test_direct_far_call_v36_plan_is_hard_rejected(self) -> None:
        executable = Path(
            "scratch_test/cjk_display_staging_v33_dense_banks/GAME/DARKSUN/DSUN.EXE"
        )
        if not executable.exists():
            self.skipTest("stable v33 executable fixture is not present")
        source = executable.read_bytes()
        with self.assertRaisesRegex(ValueError, "overlay consumer segment words"):
            build_in_memory_v33_name_slot_executable(source)
        self.assertEqual(executable.read_bytes(), source)

    def test_v37_redirect_is_exactly_overlay_safe_and_relocation_free(self) -> None:
        redirect = ds_relative_consumer_redirect_bytes(0x2516)
        self.assertEqual(len(redirect), len(NAME_POINTER_SEQUENCE))
        self.assertEqual(
            redirect,
            bytes.fromhex("0E 68 16 25 8C DB 80 EF 10 53 68 14 07 CB"),
        )

    def test_v37_in_memory_patch_uses_dgroup_cell_without_new_relocations(self) -> None:
        executable = Path(
            "scratch_test/cjk_display_staging_v33_dense_banks/GAME/DARKSUN/DSUN.EXE"
        )
        if not executable.exists():
            self.skipTest("stable v33 executable fixture is not present")
        source = executable.read_bytes()
        before_relocations = mz_relocation_file_offsets(source)
        result, core = build_in_memory_v37_name_slot_executable(source)
        self.assertEqual(mz_relocation_file_offsets(result), before_relocations)
        height = 0x33C60 + LEGACY_HEIGHT_HELPER
        self.assertEqual(result[height : height + 11], source[height : height + 11])
        pointer = DGROUP_FILE_BASE + POINTER_CELL_OFFSET
        self.assertEqual(result[pointer : pointer + 4], source[pointer : pointer + 4])
        for offset, (original, replacement) in ITEM_LINE_ADVANCE_PATCHES.items():
            self.assertEqual(source[offset : offset + len(original)], original)
            self.assertEqual(result[offset : offset + len(replacement)], replacement)
        for offset in PROVEN_CONSUMER_OFFSETS:
            redirect = ds_relative_consumer_redirect_bytes(CONSUMER_CONTINUATION_IPS[offset])
            self.assertEqual(result[offset : offset + 14], redirect)
        self.assertGreater(len(core), 391)
        self.assertLessEqual(DECODER_OFFSET + len(core), 0x10000)
        self.assertEqual(executable.read_bytes(), source)

    def test_item_panel_complete_block_is_shifted_up_consistently(self) -> None:
        expected_y = {
            0x06F5A0: (53, 23),
            0x06F5E7: (53, 23),
            0x06F61A: (99, 69),
            0x06F62D: (99, 69),
            0x06F66E: (113, 83),
        }
        for offset, (source_y, shifted_y) in expected_y.items():
            original, replacement = ITEM_LINE_ADVANCE_PATCHES[offset]
            self.assertEqual(int.from_bytes(original[-2:], "little"), source_y)
            self.assertEqual(int.from_bytes(replacement[-2:], "little"), shifted_y)
            self.assertEqual(source_y - shifted_y, 30)

    def test_item_panel_weapon_origin_keeps_seven_10px_rows_above_controls(self) -> None:
        original, replacement = ITEM_LINE_ADVANCE_PATCHES[0x06F6A5]
        self.assertEqual(original, bytes.fromhex("66 68 EC 00 78 00"))
        self.assertEqual(replacement, bytes.fromhex("66 68 EC 00 63 00"))
        origin_y = int.from_bytes(replacement[4:6], "little")
        self.assertEqual(origin_y, 99)
        self.assertLessEqual(origin_y + 6 * 10 + 9, 170)

    def test_graphics_config_uses_integer_two_x_window(self) -> None:
        source = "[sdl]\nwindowresolution=original\noutput=overlay\n"
        result = scale_graphics_config(source, 2)
        self.assertIn("windowresolution=1280x960", result)

    def test_mouse_autolock_defaults_can_be_disabled(self) -> None:
        source = "[sdl]\nautolock=true\nsensitivity=100\n"
        self.assertIn("autolock=false", set_mouse_autolock(source, False))
        self.assertIn("autolock=true", set_mouse_autolock(source, True))


if __name__ == "__main__":
    unittest.main()
