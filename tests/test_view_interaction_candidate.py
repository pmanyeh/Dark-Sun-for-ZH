import struct
import unittest
from unittest.mock import patch

from tools.build_view_interaction_candidate import (
    ACTIVE, DISPLACED, PARENT_WINDOW_HASH, overlaps, patch_window, shifted_coordinates,
)
from tools.plan_name_slot_consumers import assemble_name_slot_cache
import test_view_character_candidate as view_tests
import test_ability_ui_candidate as ability_tests


class ViewInteractionGuardsTests(unittest.TestCase):
    def test_wrong_parent_rejected(self):
        with self.assertRaisesRegex(ValueError, "not v58b"):
            patch_window(b"wrong")

    def test_all_active_slots_clear_other_small_equipment_controls(self):
        window = bytearray(2841)
        offsets = {}
        for index, ident in enumerate(range(0x2BCD, 0x2BE2)):
            offset = 0x109 + index * 30
            offsets[ident] = offset + 8
            xy = ACTIVE.get(ident, DISPLACED.get(ident, ((100, 20), None))[0])
            window[offset:offset + 12] = b"APFM" + struct.pack("<Ihh", ident, *xy)
        before = bytes(window)
        with patch("tools.build_view_interaction_candidate.sha256", return_value=PARENT_WINDOW_HASH):
            result = patch_window(before)
        allowed = {i for ident in DISPLACED for i in range(offsets[ident], offsets[ident] + 4)}
        self.assertTrue(all(a == b or i in allowed for i, (a, b) in enumerate(zip(before, result))))
        for ident, xy in ACTIVE.items():
            self.assertEqual(struct.unpack_from("<hh", result, offsets[ident]), xy)
            for other in offsets:
                if other != ident:
                    self.assertFalse(overlaps(xy, struct.unpack_from("<hh", result, offsets[other])))
        # Unknown overlap must fail, even if outside the five targeted placeholders.
        struct.pack_into("<hh", window, offsets[0x2BCD], 260, 43)
        with patch("tools.build_view_interaction_candidate.sha256", return_value=PARENT_WINDOW_HASH):
            with self.assertRaisesRegex(ValueError, "still overlaps"):
                patch_window(bytes(window))

    def test_three_pixel_shift_keeps_twelve_pixel_pitch(self):
        # v63 reflowed the ability grid to three columns of two rows, so the
        # y sequence is now two distinct values repeated three times each
        # (one per column), not six ascending rows.
        self.assertEqual([shifted_coordinates(i)[2] for i in range(6)], [43, 43, 43, 55, 55, 55])
        for i in range(6):
            self.assertLessEqual(shifted_coordinates(i)[2] + 10, 86)

    def test_view_origin_rejects_unsupported_and_clipping_values(self):
        with self.assertRaises(ValueError):
            assemble_name_slot_cache(view_y_origin=43)
        for y in (-1, 65):
            with self.assertRaises(ValueError):
                assemble_name_slot_cache(backpack_ids=(1303, 100), ability_ids=ability_tests.TEST_IDS,
                                         view_character=True, view_y_origin=y)


class ShiftedViewMachineTests(view_tests.ViewMachineTests):
    @classmethod
    def setUpClass(cls):
        cls.core = assemble_name_slot_cache(backpack_ids=(1303, 100), ability_ids=ability_tests.TEST_IDS,
                                            view_character=True, view_y_origin=43)

    def test_view_label_loop_has_two_columns_and_preserves_caller(self):
        with patch.object(view_tests, "coordinates", shifted_coordinates):
            super().test_view_label_loop_has_two_columns_and_preserves_caller()

    def test_view_numbers_keep_format_and_value_in_both_columns(self):
        with patch.object(view_tests, "coordinates", shifted_coordinates):
            super().test_view_numbers_keep_format_and_value_in_both_columns()


if __name__ == "__main__":
    unittest.main()
