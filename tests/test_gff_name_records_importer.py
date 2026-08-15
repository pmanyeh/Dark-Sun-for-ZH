from __future__ import annotations

import unittest

from tools.cjk_localization_pipeline import MAPPING_FORMAT, MAPPING_VERSION
from tools.compile_gff_name_records import (
    RECORD_BYTES,
    build_patched_chunk,
    parse_records,
    record_name,
)


def make_record(name: bytes, tail: bytes) -> bytes:
    record = name + b"\x00" + tail
    assert len(record) == RECORD_BYTES, len(record)
    return record


def make_mapping() -> dict[str, object]:
    return {
        "format": MAPPING_FORMAT,
        "version": MAPPING_VERSION,
        "entries": [
            {"character": "投", "id": 0},
            {"character": "石", "id": 1},
            {"character": "索", "id": 2},
        ],
    }


class GffNameRecordsImporterTests(unittest.TestCase):
    def test_parse_records_splits_fixed_width_slots(self) -> None:
        first = make_record(b"Sling", b"g" * (RECORD_BYTES - 6))
        second = make_record(b"Bow", b"h" * (RECORD_BYTES - 4))
        records = parse_records(first + second)
        self.assertEqual(len(records), 2)
        self.assertEqual(record_name(records[0]), "Sling")
        self.assertEqual(record_name(records[1]), "Bow")

    def test_parse_records_rejects_misaligned_chunk(self) -> None:
        with self.assertRaisesRegex(ValueError, "not a multiple"):
            parse_records(b"short")

    def test_record_name_requires_terminator(self) -> None:
        with self.assertRaisesRegex(ValueError, "no NUL terminator"):
            record_name(b"x" * RECORD_BYTES)

    def test_build_patched_chunk_preserves_trailing_bytes_and_length(self) -> None:
        tail = (b"te\\NAMEIX\\*.oda\x00\xd8\x00\xff\xff\xff\xff\xff")[: RECORD_BYTES - 6]
        original = make_record(b"Sling", tail)
        records = [original]
        patched, edits = build_patched_chunk(records, {"Sling": "投石索"}, make_mapping())
        self.assertEqual(len(patched), RECORD_BYTES)
        self.assertEqual(patched[:9], b"^!!^!\"^!#")
        self.assertEqual(patched[9], 0)
        self.assertEqual(patched[10:], original[10:])
        self.assertEqual(edits, [{"slot": 0, "en": "Sling", "zh": "投石索", "encoded_hex": "5e21215e21225e2123", "encoded_bytes": 9}])

    def test_build_patched_chunk_leaves_untranslated_and_blank_records_unchanged(self) -> None:
        blank = b"\x00" * RECORD_BYTES
        untranslated = make_record(b"Bow", b"x" * (RECORD_BYTES - 4))
        patched, edits = build_patched_chunk([blank, untranslated], {"Sling": "投石索"}, make_mapping())
        self.assertEqual(patched, blank + untranslated)
        self.assertEqual(edits, [])

    def test_build_patched_chunk_rejects_translation_too_long_for_the_fixed_record(self) -> None:
        records = [make_record(b"Sling", b"g" * (RECORD_BYTES - 6))]
        with self.assertRaisesRegex(ValueError, "usable bytes"):
            build_patched_chunk(records, {"Sling": "投石索投石索投石索投石索"}, make_mapping())


if __name__ == "__main__":
    unittest.main()
