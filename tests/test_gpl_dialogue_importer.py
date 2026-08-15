from __future__ import annotations

import unittest

from tools.compile_gpl_dialogue_patch import (
    escape_gpl_listing_string,
    packed_string_bytes,
    relocate_json_strings,
    replace_listing_strings,
)


class GplDialogueImporterTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
