import random
import struct
import unittest

from tools.creation_icon_layer import decode_icon
from tools.intro_scroll_layer import encode_frame, replace_frame0


def _chunk(frames: list[bytes], header_word: int) -> bytes:
    offsets, position = [], 6 + 4 * len(frames)
    for body in frames:
        offsets.append(position)
        position += len(body)
    return struct.pack("<IH", header_word, len(frames)) + struct.pack(f"<{len(frames)}I", *offsets) + b"".join(frames)


class IntroScrollLayerTest(unittest.TestCase):
    def test_frame_round_trips_through_the_decoder(self):
        rnd = random.Random(7)
        image = [[rnd.choice((121, 122, 186)) if x % 9 else 126 for x in range(320)] for _ in range(4)]
        frame = encode_frame(image)
        width, height, decoded = decode_icon(_chunk([frame], 0))[0]
        self.assertEqual((width, height), (320, 4))
        self.assertEqual(decoded, image)

    def test_replacement_keeps_chunk_layout(self):
        image = [[126] * 320 for _ in range(4)]
        original_frame = encode_frame([[x % 200 + 1 for x in range(320)] for _ in range(4)])
        later = b"\x10\x00\x01\x00\xff"
        chunk = _chunk([original_frame, later], 0xBEEF)
        replaced = replace_frame0(chunk, encode_frame(image))
        self.assertEqual(len(replaced), len(chunk))
        self.assertEqual(replaced[:6 + 8], chunk[:6 + 8])
        self.assertTrue(replaced.endswith(later))
        self.assertEqual(decode_icon(replaced)[0][2], image)

    def test_replacement_refuses_a_longer_frame(self):
        chunk = _chunk([encode_frame([[126] * 320]), b"\x01\x00\x01\x00\xff"], 0)
        noisy = encode_frame([[x % 250 + 1 for x in range(320)]])
        with self.assertRaises(ValueError):
            replace_frame0(chunk, noisy)


if __name__ == "__main__":
    unittest.main()
