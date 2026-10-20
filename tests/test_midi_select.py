import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "release"))

from midi_select import choose, first_soundfont, has_roms, music_source  # noqa: E402

# SOUND.CFG files written by the Steam SOUND_DS.EXE (2026-10-20).
CFG_GM = bytes.fromhex(  # "Yes" to two cards, music A (Roland SCC-1, General Midi), effects A: the Steam default
    "30030200ffffffff780020020500010001007b0001006d7433326d70752e6164760000007362706469672e61647600000000040003000800020000")
CFG_MT32 = bytes.fromhex(  # "Yes" to two cards, music B (Roland LAPC 1, MT-32, MPU 401), effects A
    "3003ffffffffffff690020020500010001007b0001006d7433326d70752e6164760000007362706469672e61647600000000030003000800020000")
CFG_SB16 = bytes.fromhex(  # "No" to two cards, E (SoundBlaster Pro 16 ASP)
    "20020500010001007a0020020500010001007a00010073627032666d2e616476000000007362706469672e616476000000000200030008000b0000")


class MidiSelectTests(unittest.TestCase):
    def test_music_source_from_the_setup_program(self):
        self.assertEqual(music_source(CFG_GM), "gm")
        self.assertEqual(music_source(CFG_MT32), "mt32")
        self.assertEqual(music_source(CFG_SB16), "other")
        self.assertEqual(music_source(b""), "unknown")

    def test_steam_default_is_general_midi(self):
        steam = ROOT / "from Steam/games/Dark Sun-ENG/GAME/DARKSUN/SOUND.CFG"
        if not steam.is_file():
            self.skipTest("requires the Steam files")
        self.assertEqual(steam.read_bytes(), CFG_GM)

    def test_choose(self):
        font = Path("GeneralUser GS.sf2")
        self.assertEqual(choose("mt32", True, None)[0], ["mididevice=mt32", "mt32.romdir=..\\mt32-roms"])
        self.assertEqual(choose("mt32", False, font)[0], ["mididevice=default"])
        self.assertIn("ROM", choose("mt32", False, None)[1])
        self.assertEqual(choose("gm", False, font)[0],
                         ["mididevice=fluidsynth", "fluid.soundfont=..\\soundfonts\\GeneralUser GS.sf2"])
        self.assertEqual(choose("gm", True, None)[0], ["mididevice=default"])
        self.assertEqual(choose("gm", False, Path("音色.sf2"))[0], ["mididevice=default"])
        self.assertEqual(choose("other", True, font), (["mididevice=default"], ""))

    def test_player_folders(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            self.assertFalse(has_roms(folder))
            (folder / "mt32_control.rom").write_bytes(b"")
            self.assertFalse(has_roms(folder))
            (folder / "MT32_PCM.ROM").write_bytes(b"")
            self.assertTrue(has_roms(folder))
            self.assertIsNone(first_soundfont(folder))
            (folder / "b.SF3").write_bytes(b"")
            (folder / "a.sf2").write_bytes(b"")
            self.assertEqual(first_soundfont(folder).name, "a.sf2")
            self.assertIsNone(first_soundfont(folder / "missing"))


if __name__ == "__main__":
    unittest.main()
