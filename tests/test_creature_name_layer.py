import unittest
from pathlib import Path

from tools.cjk_localization_pipeline import DEFAULT_GFF_CAT, DEFAULT_MAPPING, encode_text, load_mapping
from tools.creature_name_layer import (
    COMBAT_RECORD,
    NAME_BYTES,
    NAME_OFFSET,
    changed_ranges_are_names,
    encoded_name,
    gff_chunks,
    load_creature_names,
    patch_save_records,
    patch_segobjex,
)

SEGOBJEX = Path(__file__).resolve().parents[1] / "from Steam/games/Dark Sun-ENG/GAME/DARKSUN/SEGOBJEX.GFF"


class CreatureNameLayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mapping = load_mapping(DEFAULT_MAPPING)
        cls.names = load_creature_names()

    def test_every_translation_fits_the_name_field(self):
        for english, chinese in self.names.items():
            self.assertEqual(len(encoded_name(chinese, self.mapping)), NAME_BYTES, english)

    def test_joinable_characters_stay_english(self):
        for english in ("Gerakis", "Cermak", "Cilla", "K'ratchek"):
            self.assertNotIn(english, self.names)

    def test_save_records_are_rewritten_once(self):
        record = bytearray(COMBAT_RECORD)
        record[NAME_OFFSET : NAME_OFFSET + 5] = b"Dinos"
        party = bytearray(COMBAT_RECORD)
        party[NAME_OFFSET : NAME_OFFSET + 6] = b"Cermak"
        chunk = bytes(record + party)
        data = b"HEAD" + chunk
        chunks = [("SAVE", 5, 4, len(chunk))]
        patched, renamed = patch_save_records(data, chunks, self.names, self.mapping)
        self.assertEqual([(english, chinese) for _, _, english, chinese in renamed], [("Dinos", "迪諾斯")])
        start = 4 + NAME_OFFSET
        self.assertEqual(patched[start : start + NAME_BYTES].rstrip(b"\0"), encode_text("迪諾斯", self.mapping))
        self.assertIn(b"Cermak", patched)
        self.assertTrue(changed_ranges_are_names(data, patched, [start]))
        self.assertEqual(patch_save_records(patched, chunks, self.names, self.mapping)[1], [])

    @unittest.skipUnless(SEGOBJEX.exists() and DEFAULT_GFF_CAT.exists(), "requires the original SEGOBJEX.GFF")
    def test_segobjex_changes_only_name_fields(self):
        data = SEGOBJEX.read_bytes()
        patched, renamed = patch_segobjex(data, gff_chunks(DEFAULT_GFF_CAT, SEGOBJEX), self.names, self.mapping)
        self.assertEqual(len(patched), len(data))
        self.assertTrue(changed_ranges_are_names(data, patched, [start for start, *_ in renamed]))
        self.assertEqual({english for _, _, english, _ in renamed}, set(self.names))
        for english in ("Gerakis", "Cermak", "Cilla", "K'ratchek"):
            self.assertEqual(data.count(english.encode() + b"\0"), patched.count(english.encode() + b"\0"))


if __name__ == "__main__":
    unittest.main()
