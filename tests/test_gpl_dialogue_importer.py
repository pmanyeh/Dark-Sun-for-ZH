from __future__ import annotations

import unittest

from tools.compile_gpl_dialogue_patch import (
    escape_gpl_listing_string,
    parse_external_entry_listing,
    parse_fixed_entry_requirement,
    packed_string_bytes,
    relocate_gpli_event_targets,
    verify_external_entry_boundaries,
    relocate_json_strings,
    replace_listing_strings,
    verify_fixed_entry_requirements,
)


class GplDialogueImporterTests(unittest.TestCase):
    def test_gpli_event_targets_only_relocate_known_instruction_boundaries(self) -> None:
        source = bytes.fromhex(
            "18 00 2C 09 05 00"  # known GPL-5 instruction boundary
            "1A 00 82 19 05 00"  # another known GPL-5 boundary
            "1B 00 2D 09 05 00"  # not an instruction boundary
            "1C 00 2C 09 06 00"  # another GPL chunk
        )
        patched, records = relocate_gpli_event_targets(
            source, {5: {0x092C: 0x093E, 0x1982: 0x195D}}
        )
        self.assertEqual(
            patched,
            bytes.fromhex(
                "18 00 3E 09 05 00"
                "1A 00 5D 19 05 00"
                "1B 00 2D 09 05 00"
                "1C 00 2C 09 06 00"
            ),
        )
        self.assertEqual(
            [(record["event_id"], record["original_offset"], record["relocated_offset"])
            for record in records],
            [(0x18, 0x092C, 0x093E), (0x1A, 0x1982, 0x195D)],
        )

    def test_external_entry_listing_parser_is_strict(self) -> None:
        self.assertEqual(
            parse_external_entry_listing("0x0000\n0x0001\n0x07C0\n"),
            [0, 1, 0x07C0],
        )
        with self.assertRaisesRegex(ValueError, "invalid gpl-disasm entry"):
            parse_external_entry_listing("not-an-entry\n")

    def test_fixed_external_entry_requirement_accepts_matching_opcode(self) -> None:
        requirement = parse_fixed_entry_requirement("GPL:3:0x0002:0x2A")
        verify_fixed_entry_requirements("GPL", 3, b"\x00\x00\x2A", [requirement])

    def test_fixed_external_entry_requirement_rejects_shift_or_truncation(self) -> None:
        requirement = parse_fixed_entry_requirement("GPL:3:0x0002:0x2A")
        with self.assertRaisesRegex(ValueError, "fixed external entry 0x0002"):
            verify_fixed_entry_requirements("GPL", 3, b"\x00\x00\x00", [requirement])
        with self.assertRaisesRegex(ValueError, "past end of chunk"):
            verify_fixed_entry_requirements("GPL", 3, b"\x00", [requirement])

    def test_external_entry_must_remain_an_instruction_boundary(self) -> None:
        requirements = [("GPL", 5, 4, 0x2A)]
        document = {
            "instructions": [
                {"offset": 0, "opcode": 0x00},
                {"offset": 5, "opcode": 0x2A},
            ]
        }
        with self.assertRaisesRegex(ValueError, "not an instruction boundary"):
            verify_external_entry_boundaries("GPL", 5, document, requirements)
        document["instructions"][1]["offset"] = 4
        verify_external_entry_boundaries("GPL", 5, document, requirements)

    def test_listing_escape_is_lossless_for_base94_bytes(self) -> None:
        self.assertEqual(
            escape_gpl_listing_string('^!"^\\~\r\n\t'),
            '^!\\"^\\\\~\\r\\n\\t',
        )

    def test_replace_listing_uses_offset_and_source_fingerprint(self) -> None:
        listing = (
            '0000  4f  gpl print string        115, "Hello "\n'
            '0008  51  gpl printnl\n'
        )
        patched, records = replace_listing_strings(
            listing,
            [{
                "unit_id": "DLG_test",
                "occurrence_id": "DLOC_test",
                "offset": 0,
                "original": "Hello ",
                "translation_zh_tw": "測試",
                "encoded": b'^!"^\\~',
            }],
        )
        self.assertIn('"^!\\"^\\\\~"', patched)
        self.assertEqual(records[0]["encoded_ascii"], '^!"^\\~')

    def test_replace_listing_rejects_wrong_source(self) -> None:
        with self.assertRaisesRegex(ValueError, "fingerprint mismatch"):
            replace_listing_strings(
                '0000  4f  gpl print string        115, "Actual"\n',
                [{
                    "unit_id": "DLG_test",
                    "occurrence_id": "DLOC_test",
                    "offset": 0,
                    "original": "Expected",
                    "translation_zh_tw": "測試",
                    "encoded": b"test",
                }],
            )

    def test_json_edit_relocates_instruction_and_branch_offsets(self) -> None:
        document = {
            "instructions": [
                {
                    "offset": 0,
                    "length": 10,
                    "opcode": 0x4F,
                    "params": [
                        [{"kind": "immediate14", "value": 115}],
                        [{"kind": "immediate_string", "sub_type": "compressed", "value": "Hello"}],
                    ],
                },
                {
                    "offset": 10,
                    "length": 3,
                    "opcode": 0x3E,
                    "params": [[{"kind": "immediate14", "value": 13}]],
                },
                {"offset": 13, "length": 1, "opcode": 0x67, "params": []},
            ],
            "bytes_consumed": 14,
            "total_bytes": 14,
            "aligned": True,
            "cfg": {},
            "cross_chunk_calls": [],
        }
        replacement = b"A" * 13
        patched, records = relocate_json_strings(
            document,
            [{
                "unit_id": "DLG_test",
                "occurrence_id": "DLOC_test",
                "offset": 0,
                "original": "Hello",
                "translation_zh_tw": "測試",
                "encoded": replacement,
            }],
        )
        delta = packed_string_bytes(replacement.decode("ascii")) - packed_string_bytes("Hello")
        self.assertEqual(patched["instructions"][1]["offset"], 10 + delta)
        self.assertEqual(patched["instructions"][1]["params"][0][0]["value"], 13 + delta)
        self.assertEqual(patched["total_bytes"], 14 + delta)
        self.assertEqual(records[0]["packed_length_delta"], delta)


    def test_json_edit_relocates_self_referencing_global_sub(self) -> None:
        """gpl_global_sub (0x14) is (offset, chunk_id) and is normally a
        cross-chunk call left untouched, but re_42 found it can legally
        target its OWN chunk -- that offset must still move with everything
        else. A call to a genuinely different chunk must stay untouched."""
        document = {
            "instructions": [
                {
                    "offset": 0,
                    "length": 10,
                    "opcode": 0x4F,
                    "params": [
                        [{"kind": "immediate14", "value": 115}],
                        [{"kind": "immediate_string", "sub_type": "compressed", "value": "Hello"}],
                    ],
                },
                {
                    "offset": 10,
                    "length": 4,
                    "opcode": 0x14,
                    "params": [
                        [{"kind": "immediate14", "value": 14}],
                        [{"kind": "immediate14", "value": 2}],
                    ],
                },
                {
                    "offset": 14,
                    "length": 4,
                    "opcode": 0x14,
                    "params": [
                        [{"kind": "immediate14", "value": 999}],
                        [{"kind": "immediate14", "value": 7}],
                    ],
                },
                {"offset": 18, "length": 1, "opcode": 0x67, "params": []},
            ],
            "bytes_consumed": 19,
            "total_bytes": 19,
            "aligned": True,
            "cfg": {},
            "cross_chunk_calls": [],
        }
        replacement = b"A" * 13
        patched, _ = relocate_json_strings(
            document,
            [{
                "unit_id": "DLG_test",
                "occurrence_id": "DLOC_test",
                "offset": 0,
                "original": "Hello",
                "translation_zh_tw": "測試",
                "encoded": replacement,
            }],
            chunk_id=2,
        )
        delta = packed_string_bytes(replacement.decode("ascii")) - packed_string_bytes("Hello")
        # Same-chunk self-reference: offset relocates, chunk id is untouched.
        same_chunk_call = patched["instructions"][1]
        self.assertEqual(same_chunk_call["params"][0][0]["value"], 14 + delta)
        self.assertEqual(same_chunk_call["params"][1][0]["value"], 2)
        # Genuine cross-chunk reference (chunk 7): left byte-for-byte alone.
        cross_chunk_call = patched["instructions"][2]
        self.assertEqual(cross_chunk_call["params"][0][0]["value"], 999)
        self.assertEqual(cross_chunk_call["params"][1][0]["value"], 7)

    def test_json_edit_relocates_same_chunk_talk_trigger_target(self) -> None:
        document = {
            "instructions": [
                {"offset": 0, "length": 10, "opcode": 0x4F, "params": [
                    [{"kind": "immediate14", "value": 115}],
                    [{"kind": "immediate_string", "sub_type": "compressed", "value": "Hello"}],
                ]},
                {"offset": 10, "length": 8, "opcode": 0x6E, "params": [
                    [{"kind": "immediate14", "value": 18}],
                    [{"kind": "immediate14", "value": 5}],
                    [{"kind": "immediate_name", "value": -280}],
                ]},
                {"offset": 18, "length": 1, "opcode": 0x67, "params": []},
                {"offset": 19, "length": 8, "opcode": 0x6E, "params": [
                    [{"kind": "immediate14", "value": 100}],
                    [{"kind": "immediate14", "value": 7}],
                    [{"kind": "immediate_name", "value": -280}],
                ]},
            ],
            "bytes_consumed": 27, "total_bytes": 27, "aligned": True,
            "cfg": {}, "cross_chunk_calls": [],
        }
        replacement = b"A" * 13
        patched, _ = relocate_json_strings(document, [{
            "unit_id": "DLG_test", "occurrence_id": "DLOC_test", "offset": 0,
            "original": "Hello", "translation_zh_tw": "測試", "encoded": replacement,
        }], chunk_id=5)
        delta = packed_string_bytes(replacement.decode("ascii")) - packed_string_bytes("Hello")
        self.assertEqual(patched["instructions"][1]["params"][0][0]["value"], 18 + delta)
        self.assertEqual(patched["instructions"][3]["params"][0][0]["value"], 100)

    def test_json_edit_relocates_orelse_branch_target(self) -> None:
        """0x29 (gpl orelse) was missing from BRANCH_PARAMETER (re_42);
        confirm its single immediate14 target is relocated like other
        single-target branch opcodes."""
        document = {
            "instructions": [
                {
                    "offset": 0,
                    "length": 10,
                    "opcode": 0x4F,
                    "params": [
                        [{"kind": "immediate14", "value": 115}],
                        [{"kind": "immediate_string", "sub_type": "compressed", "value": "Hello"}],
                    ],
                },
                {
                    "offset": 10,
                    "length": 3,
                    "opcode": 0x29,
                    "params": [[{"kind": "immediate14", "value": 13}]],
                },
                {"offset": 13, "length": 1, "opcode": 0x67, "params": []},
            ],
            "bytes_consumed": 14,
            "total_bytes": 14,
            "aligned": True,
            "cfg": {},
            "cross_chunk_calls": [],
        }
        replacement = b"A" * 13
        patched, _ = relocate_json_strings(
            document,
            [{
                "unit_id": "DLG_test",
                "occurrence_id": "DLOC_test",
                "offset": 0,
                "original": "Hello",
                "translation_zh_tw": "測試",
                "encoded": replacement,
            }],
        )
        delta = packed_string_bytes(replacement.decode("ascii")) - packed_string_bytes("Hello")
        self.assertEqual(patched["instructions"][1]["params"][0][0]["value"], 13 + delta)
        self.assertEqual(patched["instructions"][2]["offset"], 13 + delta)

    def test_json_edit_relocates_menu_entry_targets(self) -> None:
        """gpl_menu (0x48) hides a branch target inside each 3-expression
        entry rather than as a dedicated branch instruction; re_42 found that
        an earlier edit shifting everything after it silently left those
        targets pointing at the pre-shift offset."""
        document = {
            "instructions": [
                {
                    "offset": 0,
                    "length": 10,
                    "opcode": 0x4F,
                    "params": [
                        [{"kind": "immediate14", "value": 115}],
                        [{"kind": "immediate_string", "sub_type": "compressed", "value": "Hello"}],
                    ],
                },
                {
                    "offset": 10,
                    "length": 20,
                    "opcode": 0x48,
                    "params": [
                        [{"kind": "variable", "var_kind": "gstring", "id": 1}],
                        [{"kind": "immediate_string", "sub_type": "compressed", "value": "Option A"}],
                        [{"kind": "immediate14", "value": 30}],
                        [{"kind": "variable", "var_kind": "lflag", "id": 1}],
                        [{"kind": "immediate_string", "sub_type": "compressed", "value": "Option B"}],
                        [{"kind": "immediate14", "value": 30}],
                        [{"kind": "variable", "var_kind": "lflag", "id": 2}],
                    ],
                },
                {"offset": 30, "length": 1, "opcode": 0x67, "params": []},
            ],
            "bytes_consumed": 31,
            "total_bytes": 31,
            "aligned": True,
            "cfg": {},
            "cross_chunk_calls": [],
        }
        replacement = b"A" * 13
        patched, _ = relocate_json_strings(
            document,
            [{
                "unit_id": "DLG_test",
                "occurrence_id": "DLOC_test",
                "offset": 0,
                "original": "Hello",
                "translation_zh_tw": "測試",
                "encoded": replacement,
            }],
        )
        delta = packed_string_bytes(replacement.decode("ascii")) - packed_string_bytes("Hello")
        self.assertNotEqual(delta, 0)
        menu = patched["instructions"][1]
        self.assertEqual(menu["offset"], 10 + delta)
        entry_a_target = menu["params"][2]
        entry_b_target = menu["params"][5]
        self.assertEqual(entry_a_target[0]["value"], 30 + delta)
        self.assertEqual(entry_b_target[0]["value"], 30 + delta)
        self.assertEqual(patched["instructions"][2]["offset"], 30 + delta)


if __name__ == "__main__":
    unittest.main()
