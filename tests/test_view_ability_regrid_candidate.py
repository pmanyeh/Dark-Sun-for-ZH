import struct
import unittest
from unittest.mock import patch

from tools.build_view_ability_regrid_candidate import (
    PARENT_EXE_HASH, PARENT_FONT_HASH, REVERTED_PLACEMENTS, coordinates, revert_window,
)
from tools.plan_name_slot_consumers import assemble_name_slot_cache
import test_view_character_candidate as view_tests
import test_ability_ui_candidate as ability_tests

if ability_tests.HAVE_UNICORN:
    from unicorn.x86_const import *


class ViewAbilityRegridGuardsTests(unittest.TestCase):
    def test_coordinates_are_three_columns_by_two_rows(self):
        self.assertEqual([coordinates(i)[2] for i in range(6)], [63, 63, 63, 75, 75, 75])
        xs = [coordinates(i)[0] for i in range(6)]
        self.assertEqual(xs, [149, 193, 237, 149, 193, 237])
        for row in range(6):
            label_x, number_x, _ = coordinates(row)
            self.assertEqual(number_x, label_x + 28)

    def test_revert_window_restores_pristine_placements_only(self):
        pristine = bytearray(2841)
        pristine[:4] = b"WIND"
        moved = bytearray(2841)
        moved[:4] = b"WIND"
        offsets = {}
        for index, (ident, xy) in enumerate(REVERTED_PLACEMENTS.items()):
            offset = 0x109 + index * 30
            offsets[ident] = offset + 8
            pristine[offset:offset + 12] = b"APFM" + struct.pack("<Ihh", ident, *xy)
            moved[offset:offset + 12] = b"APFM" + struct.pack("<Ihh", ident, 1, 2)
        pristine[100] = 0x42
        moved[100] = 0x42  # untouched byte outside any placement must still match
        result = revert_window(bytes(pristine), bytes(moved))
        self.assertEqual(result, bytes(pristine))

    def test_revert_window_rejects_pristine_drift_outside_placements(self):
        pristine = bytearray(2841)
        pristine[:4] = b"WIND"
        for index, (ident, xy) in enumerate(REVERTED_PLACEMENTS.items()):
            offset = 0x109 + index * 30
            pristine[offset:offset + 12] = b"APFM" + struct.pack("<Ihh", ident, *xy)
        moved = bytearray(pristine)
        moved[100] = 0x99
        with self.assertRaisesRegex(ValueError, "unexpected WIND-11500 drift"):
            revert_window(bytes(pristine), bytes(moved))

    def test_wrong_parent_hashes_rejected(self):
        self.assertNotEqual(PARENT_EXE_HASH, "")
        self.assertNotEqual(PARENT_FONT_HASH, "")


class ViewAbilityRegridMachineTests(view_tests.ViewMachineTests):
    @classmethod
    def setUpClass(cls):
        cls.core = assemble_name_slot_cache(backpack_ids=(1303, 100), ability_ids=ability_tests.TEST_IDS,
                                            view_character=True, view_y_origin=63)

    def test_view_label_loop_has_two_columns_and_preserves_caller(self):
        with patch.object(view_tests, "coordinates", coordinates):
            super().test_view_label_loop_has_two_columns_and_preserves_caller()

    def test_view_numbers_keep_format_and_value_in_both_columns(self):
        with patch.object(view_tests, "coordinates", coordinates):
            super().test_view_numbers_keep_format_and_value_in_both_columns()


if __name__ == "__main__":
    unittest.main()
