from dataclasses import replace
import unittest

from tools.audit_inventory_ui import (
    CJK_PROPOSED_LAYOUT, FIXED_TEXT, V55_LAYOUT, TextBlock,
    build_report, layout_issues, text_preflight, verify_sources,
)


class InventoryUiPreflightTests(unittest.TestCase):
    def test_v55_and_proposal_fit(self):
        self.assertEqual(layout_issues(V55_LAYOUT), [])
        self.assertEqual(layout_issues(CJK_PROPOSED_LAYOUT), [])
        self.assertEqual(CJK_PROPOSED_LAYOUT[-1].bottom, 168)
        self.assertEqual(CJK_PROPOSED_LAYOUT[-1], V55_LAYOUT[-1])

    def test_direct_chinese_on_seven_pixel_rows_is_rejected(self):
        blocks = (replace(V55_LAYOUT[0], glyph_height=10),) + V55_LAYOUT[1:]
        self.assertIn("abilities: glyph height exceeds row advance", layout_issues(blocks))

    def test_expanding_ability_rows_without_reflow_overlaps_psi(self):
        blocks = (replace(V55_LAYOUT[0], advance=10, glyph_height=10),) + V55_LAYOUT[1:]
        self.assertIn("abilities/psi: block overlap", layout_issues(blocks))

    def test_frame_boundary_is_exclusive(self):
        self.assertEqual(layout_issues((TextBlock("x", 163, 1, 10, 10),)), [])
        self.assertTrue(layout_issues((TextBlock("x", 164, 1, 10, 10),)))

    def test_order_does_not_hide_overlap(self):
        self.assertTrue(layout_issues((TextBlock("b", 30, 1, 10, 10),
                                       TextBlock("a", 25, 1, 10, 10))))

    def test_nonpositive_dimensions_rejected(self):
        with self.assertRaises(ValueError):
            layout_issues((TextBlock("bad", 8, 0, 10, 10),))

    def test_chinese_ability_needs_more_than_original_five_bytes(self):
        result = text_preflight(FIXED_TEXT[1], {"entries": []})
        self.assertEqual(result["capacity_with_nul"], 5)
        self.assertEqual(result["base94_bytes_with_nul"], 8)
        self.assertFalse(result["fits_original_storage"])
        self.assertIsNotNone(result["encoding_error"])

    def test_fitting_backpack_is_not_permission_to_patch(self):
        mapping = {"entries": [{"character": "背", "id": 0}, {"character": "包", "id": 1}]}
        result = text_preflight(FIXED_TEXT[0], mapping)
        self.assertEqual(result["base94_bytes_with_nul"], 7)
        self.assertTrue(result["fits_original_storage"])
        self.assertIsNone(result["encoding_error"])
        self.assertFalse(result["runtime_decoder_verified"])
        self.assertFalse(result["ready_to_patch"])

    def test_reject_wrong_executable(self):
        with self.assertRaisesRegex(ValueError, "baseline"):
            build_report(b"not v55", {"entries": []})
        with self.assertRaisesRegex(ValueError, "source mismatch"):
            verify_sources(b"")


if __name__ == "__main__":
    unittest.main()
