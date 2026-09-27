import struct
import unittest
from pathlib import Path

from tools.creation_icon_layer import decode_icon
from tools.ending_poem_layer import (
    ENDING_CASE,
    FONT_PATH,
    POEMS,
    START_GAME_CASE,
    SWITCH_TARGETS,
    encode_transparent_frame,
    preview_ending_on_start,
    render_poem,
    single_frame_chunk,
)

EXE = Path(__file__).resolve().parents[1] / "from Steam/games/Dark Sun-ENG/GAME/DARKSUN/DSUN.EXE"


class EndingPoemLayerTests(unittest.TestCase):
    def test_transparent_frame_round_trips(self):
        image = [[0] * 320 for _ in range(200)]
        image[12][5:9] = [109, 109, 179, 109]
        image[40][300:320] = [179] * 20
        chunk = single_frame_chunk(struct.pack("<IHI", 400, 1, 10) + bytes(390), encode_transparent_frame(image))
        self.assertEqual(len(chunk), 400)
        self.assertEqual(decode_icon(chunk)[0][2], image)

    @unittest.skipUnless(FONT_PATH.is_file(), "requires Microsoft JhengHei Bold")
    def test_poems_stay_on_screen(self):
        for _, _, lines in POEMS:
            image = render_poem(lines)
            self.assertTrue(any(any(row) for row in image))
            self.assertFalse(any(row[319] for row in image))

    @unittest.skipUnless(EXE.exists(), "requires the original DSUN.EXE")
    def test_preview_only_retargets_start_game(self):
        image = EXE.read_bytes()
        patched = preview_ending_on_start(image)
        diff = [index for index, (a, b) in enumerate(zip(image, patched)) if a != b]
        self.assertTrue(all(SWITCH_TARGETS + 2 <= index < SWITCH_TARGETS + 4 for index in diff))
        self.assertEqual(struct.unpack_from("<H", image, SWITCH_TARGETS + 2)[0], START_GAME_CASE)
        self.assertEqual(struct.unpack_from("<H", patched, SWITCH_TARGETS + 2)[0], ENDING_CASE)
        with self.assertRaises(ValueError):
            preview_ending_on_start(patched)


if __name__ == "__main__":
    unittest.main()
