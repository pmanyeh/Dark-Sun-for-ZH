import unittest
from pathlib import Path

from tools.cjk_localization_pipeline import DEFAULT_MAPPING, encode_text, load_mapping
from tools.exe_text_layer import (
    DGROUP_FILE_BASE,
    MATCHED_STRINGS,
    TEXT_REGIONS,
    TextRegion,
    apply_exe_text_patches,
    region_bytes,
    string_push_sites,
)

PRISTINE = Path(__file__).resolve().parents[1] / "from Steam/games/Dark Sun-ENG/GAME/DARKSUN/DSUN.EXE"


class ExeTextLayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mapping = load_mapping(DEFAULT_MAPPING)

    def test_strings_are_nul_terminated_inside_their_region(self):
        for region in TEXT_REGIONS:
            payload = region_bytes(region, self.mapping)
            self.assertEqual(len(payload), len(region.original))
            for _, offset, _ in region.strings:
                self.assertIn(0, payload[offset - region.start :])

    def test_overflowing_or_overlapping_strings_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "past the end"):
            region_bytes(TextRegion(0, b"Yes\0", ((0, 0, "是否"),), "test"), self.mapping)
        with self.assertRaisesRegex(ValueError, "overlaps"):
            region_bytes(TextRegion(0, bytes(12), ((0, 0, "是"), (4, 2, "否")), "test"), self.mapping)

    @unittest.skipUnless(PRISTINE.exists(), "requires the original DSUN.EXE")
    def test_yes_no_prompt_matches_its_stricmp_copy_and_moves_no(self):
        image = PRISTINE.read_bytes()
        patched = apply_exe_text_patches(image, self.mapping)

        def string_at(offset):
            start = DGROUP_FILE_BASE + offset
            return patched[start : patched.index(0, start)]

        for first, second in MATCHED_STRINGS:
            self.assertEqual(string_at(first), string_at(second))
        self.assertEqual(patched[0x6B7E6:0x6B7E9], bytes.fromhex("68 0D 16"))
        self.assertTrue(string_at(0x160D).startswith(b"^"))
        self.assertTrue(string_at(0x1611).startswith(b"^"))
        with self.assertRaises(ValueError):
            apply_exe_text_patches(patched, self.mapping)

    @unittest.skipUnless(PRISTINE.exists(), "requires the original DSUN.EXE")
    def test_every_moved_string_keeps_all_its_references(self):
        image = PRISTINE.read_bytes()
        patched = apply_exe_text_patches(image, self.mapping)
        redirected = {}
        for region in TEXT_REGIONS:
            for old, target in region.redirects:
                redirected.setdefault(target, []).extend(string_push_sites(image, old))
        for region in TEXT_REGIONS:
            for old, new, _ in region.strings:
                before = sorted(string_push_sites(image, old) + redirected.get(new, []))
                after = string_push_sites(patched, new)
                self.assertEqual(before, after, f"DGROUP:{old:04X}")

    @unittest.skipUnless(PRISTINE.exists(), "requires the original DSUN.EXE")
    def test_exit_dialog_buttons_point_at_spilled_strings(self):
        image = PRISTINE.read_bytes()
        patched = apply_exe_text_patches(image, self.mapping)

        def string_at(offset):
            start = DGROUP_FILE_BASE + offset
            return patched[start : patched.index(0, start)]

        # 0x716E4 push ds; push QUIT, 0x716F9 mov ax, SAVE, 0x71711 mov ax, EXIT: SAVE GAME?
        for site, text in ((0x716E5, "直接離開"), (0x716FA, "存檔並離開"), (0x71713, "離開前存檔嗎?")):
            offset = int.from_bytes(patched[site : site + 2], "little")
            self.assertEqual(string_at(offset), encode_text(text, self.mapping))
        # Item and look cards: the pushes of USEABLE BY:/NO ONE/LEVEL/2 handed.
        for site, text in ((0x5F5EE, "可使用者:"), (0x5F69F, "無"), (0x8C1E2, "可使用者:"),
                           (0x8C274, "無"), (0x5FC93, "等級: %d"), (0x8BE52, "雙手")):
            offset = int.from_bytes(patched[site : site + 2], "little")
            self.assertEqual(string_at(offset), encode_text(text, self.mapping), hex(site))
        # The game menu's exit dialog shares ESC's strings; its SAVE saves and exits,
        # while the load/save dialog's SAVE (same DGROUP string) only saves.
        for site, text in ((0x61756, "離開遊戲?"), (0x6175B, "離開前存檔嗎?"), (0x61742, "存檔並離開"),
                           (0x6172D, "直接離開"), (0x61729, "取消"), (0x6181D, "讀取/存檔"),
                           (0x61818, "讀取/重新開始"), (0x61805, "讀取"), (0x61800, "存檔"), (0x617EB, "重新開始")):
            offset = int.from_bytes(patched[site : site + 2], "little")
            self.assertEqual(string_at(offset), encode_text(text, self.mapping), hex(site))
        # Party member portrait menu buttons.
        for site, text in ((0x70D3E, "改名"), (0x70D43, "修改"), (0x70D20, "離隊"), (0x70D05, "雙職業"),
                           (0x70D0A, "取消")):
            offset = int.from_bytes(patched[site : site + 2], "little")
            self.assertEqual(string_at(offset), encode_text(text, self.mapping), hex(site))


if __name__ == "__main__":
    unittest.main()
