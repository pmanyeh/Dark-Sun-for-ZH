from __future__ import annotations

import unittest
from pathlib import Path

from tools.build_cjk_display_staging import build_native_height_scratch_font, scale_graphics_config
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

    def test_graphics_config_uses_integer_two_x_window(self) -> None:
        source = "[sdl]\nwindowresolution=original\noutput=overlay\n"
        result = scale_graphics_config(source, 2)
        self.assertIn("windowresolution=1280x960", result)


if __name__ == "__main__":
    unittest.main()
