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

    def _menu_document(self, entry_texts: list[str]) -> dict[str, object]:
        params: list[list[dict[str, object]]] = [
            [{"kind": "variable", "var_kind": "gstring", "id": 1}]
        ]
        for text in entry_texts:
            params.append([{"kind": "immediate_string", "sub_type": "compressed", "value": text}])
            params.append([{"kind": "immediate14", "value": 40}])
            params.append([{"kind": "variable", "var_kind": "lflag", "id": 1}])
        return {
            "instructions": [
                {"offset": 0, "length": 40, "opcode": 0x48, "params": params},
                {"offset": 40, "length": 1, "opcode": 0x67, "params": []},
            ],
            "bytes_consumed": 41,
            "total_bytes": 41,
            "aligned": True,
            "cfg": {},
            "cross_chunk_calls": [],
        }

    def test_menu_accepts_multiple_option_text_edits_at_the_same_offset(self) -> None:
        """re_42 4.3: dialogue_occurrences.json records one occurrence per
        menu option but every option in a menu shares the instruction's
        single offset. relocate_json_strings must match each edit to its
        option by original text and rewrite the whole 0x48 instruction once,
        instead of raising 'multiple dialogue edits target the same
        instruction offset'."""
        document = self._menu_document(["Option A", "Option B", "Option C"])
        edits = [
            {
                "unit_id": "DLG_a", "occurrence_id": "DLOC_a", "offset": 0,
                "original": "Option A", "translation_zh_tw": "選項甲", "encoded": b"A" * 5,
            },
            {
                "unit_id": "DLG_c", "occurrence_id": "DLOC_c", "offset": 0,
                "original": "Option C", "translation_zh_tw": "選項丙", "encoded": b"C" * 9,
            },
        ]
        patched, applied = relocate_json_strings(document, edits)
        menu = patched["instructions"][0]
        self.assertEqual(menu["params"][1][0]["value"], "A" * 5)
        self.assertEqual(menu["params"][4][0]["value"], "Option B")
        self.assertEqual(menu["params"][7][0]["value"], "C" * 9)
        self.assertEqual({item["unit_id"] for item in applied}, {"DLG_a", "DLG_c"})
        delta_a = packed_string_bytes("A" * 5) - packed_string_bytes("Option A")
        delta_c = packed_string_bytes("C" * 9) - packed_string_bytes("Option C")
        self.assertEqual(menu["length"], 40 + delta_a + delta_c)
        self.assertEqual(patched["instructions"][1]["offset"], 40 + delta_a + delta_c)

    def test_menu_matches_duplicate_option_text_to_distinct_entries(self) -> None:
        """re_42 batch found 6 real menus with the same option text repeated
        (e.g. 'I want some information!' twice); since the dialogue unit_id
        is a hash of the text, both occurrences carry the same translation,
        so either entry may claim either edit as long as both get replaced."""
        document = self._menu_document(["Repeat", "Repeat", "Unique"])
        edits = [
            {
                "unit_id": "DLG_r", "occurrence_id": "DLOC_r1", "offset": 0,
                "original": "Repeat", "translation_zh_tw": "重複", "encoded": b"R" * 4,
            },
            {
                "unit_id": "DLG_r", "occurrence_id": "DLOC_r2", "offset": 0,
                "original": "Repeat", "translation_zh_tw": "重複", "encoded": b"R" * 4,
            },
        ]
        patched, applied = relocate_json_strings(document, edits)
        menu = patched["instructions"][0]
        self.assertEqual(menu["params"][1][0]["value"], "R" * 4)
        self.assertEqual(menu["params"][4][0]["value"], "R" * 4)
        self.assertEqual(menu["params"][7][0]["value"], "Unique")
        self.assertEqual(len(applied), 2)

    def test_cross_chunk_references_follow_relocated_targets(self) -> None:
        """MAS-41's talktotrigger into GPL-141 kept offset 2334 after GPL-141
        was translated and grew, so talking to the NPC did nothing."""
        from tools.compile_gpl_dialogue_patch import retarget_cross_chunk_references

        def document(talk_target: int, call_target: int) -> dict[str, object]:
            return {"instructions": [
                {"offset": 0, "opcode": 0x6E, "params": [
                    [{"kind": "immediate14", "value": talk_target}],
                    [{"kind": "immediate14", "value": 141}],
                ]},
                {"offset": 4, "opcode": 0x14, "params": [
                    [{"kind": "immediate14", "value": call_target}],
                    [{"kind": "immediate14", "value": 9}],
                ]},
            ]}

        baseline = document(2334, 50)
        current = document(2334, 50)
        maps = {141: {2334: 2482}}
        relocations = retarget_cross_chunk_references(baseline, current, maps, "MAS-41")
        self.assertEqual(current["instructions"][0]["params"][0][0]["value"], 2482)
        self.assertEqual(current["instructions"][1]["params"][0][0]["value"], 50)
        self.assertEqual(len(relocations), 1)
        # Running again on the corrected chunk changes nothing.
        self.assertEqual(retarget_cross_chunk_references(baseline, current, maps, "MAS-41"), [])
        with self.assertRaisesRegex(ValueError, "non-instruction"):
            retarget_cross_chunk_references(document(2335, 50), document(2335, 50), maps, "MAS-41")

    def test_tile_box_and_sight_triggers_relocate_their_real_target(self) -> None:
        """Box/tile triggers lead with map coordinates; the target is later."""
        from tools.compile_gpl_dialogue_patch import retarget_cross_chunk_references

        def imm(value: int) -> list[dict[str, object]]:
            return [{"kind": "immediate14", "value": value}]

        def byte(value: int) -> list[dict[str, object]]:
            return [{"kind": "immediate_byte", "value": value}]

        def document() -> dict[str, object]:
            return {"instructions": [
                {"offset": 0, "opcode": 0x6A,
                 "params": [byte(32), byte(1), byte(9), byte(1), imm(822), imm(80), byte(0)]},
                {"offset": 9, "opcode": 0x68,
                 "params": [byte(54), byte(21), imm(822), imm(80), byte(0)]},
                {"offset": 16, "opcode": 0x1B,
                 "params": [imm(822), imm(80), [{"kind": "name", "value": -1}], byte(25)]},
            ]}

        baseline, current = document(), document()
        relocations = retarget_cross_chunk_references(baseline, current, {80: {822: 900}}, "MAS-10")
        box, tile, sight = current["instructions"]
        self.assertEqual(box["params"][4], imm(900))
        self.assertEqual(box["params"][:4], [byte(32), byte(1), byte(9), byte(1)])
        self.assertEqual(tile["params"][2], imm(900))
        self.assertEqual(sight["params"][0], imm(900))
        self.assertEqual(len(relocations), 3)

    def test_menu_leaves_variable_and_introduce_options_untouched(self) -> None:
        """GPL-141's 0x0A98 menu ends with a GSTR[5] option and GPL-143's
        0x0797 menu starts with INTRODUCE. Neither is an inline literal, so
        they stay as they are while the literal options are still edited."""
        document = self._menu_document(["Option A", "Option B", "Option C"])
        params = document["instructions"][0]["params"]
        variable = [{"kind": "variable", "var_kind": "gstring", "id": 5}]
        introduce = [{"kind": "immediate_string", "sub_type": "introduce", "value": "<active_character_name>"}]
        params[1] = introduce
        params[7] = variable
        edits = [{
            "unit_id": "DLG_b", "occurrence_id": "DLOC_b", "offset": 0,
            "original": "Option B", "translation_zh_tw": "選項乙", "encoded": b"B" * 5,
        }]
        patched, applied = relocate_json_strings(document, edits)
        menu = patched["instructions"][0]
        self.assertEqual(menu["params"][1], introduce)
        self.assertEqual(menu["params"][4][0]["value"], "B" * 5)
        self.assertEqual(menu["params"][7], variable)
        self.assertEqual(len(applied), 1)
        # An edit can never be matched to a non-literal option.
        with self.assertRaisesRegex(ValueError, "no unclaimed menu entry text matches"):
            relocate_json_strings(document, [dict(edits[0], original="<active_character_name>")])

    def test_menu_rejects_edit_with_no_unclaimed_matching_entry(self) -> None:
        document = self._menu_document(["Option A", "Option B"])
        edits = [{
            "unit_id": "DLG_x", "occurrence_id": "DLOC_x", "offset": 0,
            "original": "Option X", "translation_zh_tw": "未知", "encoded": b"X" * 3,
        }]
        with self.assertRaisesRegex(ValueError, "no unclaimed menu entry text matches"):
            relocate_json_strings(document, edits)

    def test_menu_rejects_more_edits_than_matching_entries(self) -> None:
        document = self._menu_document(["Repeat", "Other"])
        edits = [
            {
                "unit_id": "DLG_r", "occurrence_id": "DLOC_r1", "offset": 0,
                "original": "Repeat", "translation_zh_tw": "重複", "encoded": b"R" * 4,
            },
            {
                "unit_id": "DLG_r", "occurrence_id": "DLOC_r2", "offset": 0,
                "original": "Repeat", "translation_zh_tw": "重複", "encoded": b"R" * 4,
            },
        ]
        with self.assertRaisesRegex(ValueError, "no unclaimed menu entry text matches"):
            relocate_json_strings(document, edits)

    def test_print_string_still_rejects_two_edits_at_the_same_offset(self) -> None:
        document = {
            "instructions": [
                {
                    "offset": 0, "length": 10, "opcode": 0x4F,
                    "params": [
                        [{"kind": "immediate14", "value": 115}],
                        [{"kind": "immediate_string", "sub_type": "compressed", "value": "Hello"}],
                    ],
                },
            ],
            "bytes_consumed": 10, "total_bytes": 10, "aligned": True,
            "cfg": {}, "cross_chunk_calls": [],
        }
        edits = [
            {
                "unit_id": "DLG_1", "occurrence_id": "DLOC_1", "offset": 0,
                "original": "Hello", "translation_zh_tw": "A", "encoded": b"A",
            },
            {
                "unit_id": "DLG_2", "occurrence_id": "DLOC_2", "offset": 0,
                "original": "Hello", "translation_zh_tw": "B", "encoded": b"B",
            },
        ]
        with self.assertRaisesRegex(
            ValueError, "multiple dialogue edits target string instruction"
        ):
            relocate_json_strings(document, edits)

    def test_string_copy_source_literal_is_translated(self) -> None:
        """MAS-99 seeds GSTR[5] = "Goodbye." with gpl string copy (0x0A);
        the destination variable must stay and only the literal changes."""
        document = {
            "instructions": [
                {
                    "offset": 0, "length": 13, "opcode": 0x0A,
                    "params": [
                        [{"kind": "variable", "var_kind": "gstring", "id": 5}],
                        [{"kind": "immediate_string", "sub_type": "compressed", "value": "Goodbye."}],
                    ],
                },
                {"offset": 13, "length": 1, "opcode": 0x67, "params": []},
            ],
            "bytes_consumed": 14, "total_bytes": 14, "aligned": True,
            "cfg": {}, "cross_chunk_calls": [],
        }
        edits = [{
            "unit_id": "DLG_bye", "occurrence_id": "DLOC_bye", "offset": 0,
            "original": "Goodbye.", "translation_zh_tw": "再見。", "encoded": b"B" * 12,
        }]
        patched, applied = relocate_json_strings(document, edits)
        copy_instruction = patched["instructions"][0]
        self.assertEqual(copy_instruction["params"][0][0]["id"], 5)
        self.assertEqual(copy_instruction["params"][1][0]["value"], "B" * 12)
        delta = packed_string_bytes("B" * 12) - packed_string_bytes("Goodbye.")
        self.assertEqual(patched["instructions"][1]["offset"], 13 + delta)
        self.assertEqual([item["unit_id"] for item in applied], ["DLG_bye"])

    def test_menu_withholds_an_inline_title(self) -> None:
        """GPL-29's menu carries "Do you drink the wine?" inline as its
        leading parameter, on the same offset as its options. The title
        renderer has no CJK path, so the title stays English while the
        options on the same offset are still translated."""
        document = self._menu_document(["Yes", "No"])
        document["instructions"][0]["params"][0] = [
            {"kind": "immediate_string", "sub_type": "compressed", "value": "Drink?"}
        ]
        edits = [
            {
                "unit_id": "DLG_t", "occurrence_id": "DLOC_t", "offset": 0,
                "original": "Drink?", "translation_zh_tw": "喝嗎？", "encoded": b"T" * 3,
            },
            {
                "unit_id": "DLG_y", "occurrence_id": "DLOC_y", "offset": 0,
                "original": "Yes", "translation_zh_tw": "是", "encoded": b"Y" * 2,
            },
        ]
        withheld: list[dict[str, object]] = []
        patched, applied = relocate_json_strings(document, edits, None, withheld)
        menu = patched["instructions"][0]
        self.assertEqual(menu["params"][0][0]["value"], "Drink?")
        self.assertEqual(menu["params"][1][0]["value"], "Y" * 2)
        self.assertEqual(menu["params"][4][0]["value"], "No")
        self.assertEqual([item["unit_id"] for item in applied], ["DLG_y"])
        self.assertEqual([(item["unit_id"], item["reason"]) for item in withheld],
                         [("DLG_t", "inline menu title")])

    def _string_copy_document(self, var_id: int, value: str) -> dict[str, object]:
        return {
            "instructions": [
                {
                    "offset": 0, "length": 10, "opcode": 0x0A,
                    "params": [
                        [{"kind": "variable", "var_kind": "gstring", "id": var_id}],
                        [{"kind": "immediate_string", "sub_type": "compressed", "value": value}],
                    ],
                },
            ],
            "bytes_consumed": 10, "total_bytes": 10, "aligned": True,
            "cfg": {}, "cross_chunk_calls": [],
        }

    def test_string_copy_withholds_engine_control_and_menu_title_strings(self) -> None:
        """DSUN.EXE compares printed text with "END"/"CLOSE" (MAS-99 seeds
        GSTR[2]/[3]), and GSTR[1]/[4] are menu titles with no CJK renderer;
        translating either broke v86's dialogue (it never closed and the
        title drew as garbage)."""
        for var_id, value, reason in (
            (2, "END", "engine control string"),
            (3, "CLOSE", "engine control string"),
            (1, "What do you say?", "menu title variable"),
            (4, "What do you do?", "menu title variable"),
        ):
            document = self._string_copy_document(var_id, value)
            withheld: list[dict[str, object]] = []
            patched, applied = relocate_json_strings(document, [{
                "unit_id": "DLG_x", "occurrence_id": "DLOC_x", "offset": 0,
                "original": value, "translation_zh_tw": "中", "encoded": b"Z" * 2,
            }], None, withheld)
            self.assertEqual(patched["instructions"][0]["params"][1][0]["value"], value)
            self.assertEqual(applied, [])
            self.assertEqual([item["reason"] for item in withheld], [reason])


    def test_cjk_join_spaces_are_dropped_only_next_to_wide_characters(self) -> None:
        """A split sentence's edge spaces showed as gaps ("我已經在 這裡")."""
        from tools.compile_gpl_dialogue_patch import tighten_cjk_join_spaces

        # Trailing space after a CJK character or full-width punctuation.
        self.assertEqual(tighten_cjk_join_spaces("我已經在 ", b"^!! ", False), b"^!!")
        self.assertEqual(tighten_cjk_join_spaces("等等…… ", b"^!!^!! ", False), b"^!!^!!")
        # A space after an ASCII word or number stays.
        self.assertEqual(tighten_cjk_join_spaces("提升 THAC0 ", b"^!! THAC0 ", True), b"^!! THAC0 ")
        # One leading space before CJK goes only when strip_leading is set.
        self.assertEqual(tighten_cjk_join_spaces(" 在城鎮裡。", b" ^!!", True), b"^!!")
        self.assertEqual(tighten_cjk_join_spaces(" 在城鎮裡。", b" ^!!", False), b" ^!!")
        # Menu indents (two spaces) and list indents (three) stay.
        self.assertEqual(tighten_cjk_join_spaces("  是的。 ", b"  ^!! ", True), b"  ^!!")
        self.assertEqual(tighten_cjk_join_spaces("   最近", b"   ^!!", True), b"   ^!!")
        # A leading space before ASCII stays.
        self.assertEqual(tighten_cjk_join_spaces(" 100", b" 100", True), b" 100")

    def test_print_string_edit_drops_cjk_join_spaces(self) -> None:
        document = {
            "instructions": [
                {
                    "offset": 0, "length": 10, "opcode": 0x4F,
                    "params": [
                        [{"kind": "immediate14", "value": 98}],
                        [{"kind": "immediate_string", "sub_type": "compressed", "value": "been in "}],
                    ],
                },
            ],
            "bytes_consumed": 10, "total_bytes": 10, "aligned": True,
            "cfg": {}, "cross_chunk_calls": [],
        }
        patched, applied = relocate_json_strings(document, [{
            "unit_id": "DLG_s", "occurrence_id": "DLOC_s", "offset": 0,
            "original": "been in ", "translation_zh_tw": " 在這裡 ", "encoded": b" ^!!^!\" ",
        }])
        self.assertEqual(patched["instructions"][0]["params"][1][0]["value"], "^!!^!\"")
        self.assertEqual(applied[0]["encoded_ascii"], "^!!^!\"")

if __name__ == "__main__":
    unittest.main()
