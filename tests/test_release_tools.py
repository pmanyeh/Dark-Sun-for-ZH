import json
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "release"))

from darksun_gff import gff_chunks  # noqa: E402
from darksun_saves import migrate_creature_names, migrate_gstr  # noqa: E402

STEAM = ROOT / "from Steam/games/Dark Sun-ENG/GAME/DARKSUN"
BUILD = ROOT / "dist/_release_build"


def tiny_gff(chunks: list[tuple[bytes, int, bytes]]) -> bytes:
    """A GFF with indexed chunks only: header, data, TOC."""
    data = bytearray(28)
    records = []
    for kind, chunk_id, payload in chunks:
        records.append((kind, chunk_id, len(data), len(payload)))
        data += payload
    toc = len(data)
    kinds = sorted({kind for kind, *_ in records})
    body = bytearray(struct.pack("<H", len(kinds)))
    for kind in kinds:
        own = [record for record in records if record[0] == kind]
        body += kind + struct.pack("<I", len(own))
        for _, chunk_id, offset, length in own:
            body += struct.pack("<iII", chunk_id, offset, length)
    data += struct.pack("<II", 8, 8 + len(body)) + body
    struct.pack_into("<4sIIII", data, 0, b"GFFI", 0x30000, 28, toc, len(data) - toc)
    return bytes(data)


class ReleaseToolTests(unittest.TestCase):
    def test_creature_names_in_saves_are_migrated_once(self):
        record = bytearray(0x3A)
        record[0x28:0x2D] = b"Dinos"
        save = bytearray(tiny_gff([(b"SAVE", 5, bytes(record) * 2)]))
        field = "5e2121" + "00" * 13
        self.assertEqual(migrate_creature_names(save, {"Dinos": field}), 2)
        self.assertEqual(save.count(bytes.fromhex(field)), 2)
        self.assertEqual(migrate_creature_names(save, {"Dinos": field}), 0)

    def test_gstr_slots_are_migrated_once(self):
        slots = [b"What do you say?", b"END", b"CLOSE", b"What do you do?"]
        data = bytearray(b"xx" + b"".join(slot.ljust(42, b"\0") for slot in slots))
        gstr = {"1": ["What do you say?", "^!!?"], "4": ["What do you do?", "^!\"?"]}
        self.assertEqual(migrate_gstr(data, gstr), [1, 4])
        self.assertEqual(data[2:6], b"^!!?")
        self.assertEqual(migrate_gstr(data, gstr), [])

    @unittest.skipUnless(STEAM.is_dir(), "requires the Steam game files")
    def test_gff_reader_handles_segmented_types(self):
        chunks = gff_chunks((STEAM / "RESOURCE.GFF").read_bytes())
        self.assertGreater(len(chunks), 1000)
        self.assertTrue(all(offset > 0 and length >= 0 for _, _, offset, length in chunks))

    @unittest.skipUnless(STEAM.is_dir() and (BUILD / "release_manifest.json").is_file(),
                         "requires the Steam files and build_release_patches.py output")
    def test_installer_refuses_unknown_files_without_touching_them(self):
        with tempfile.TemporaryDirectory() as temporary:
            release = Path(temporary)
            for name in ("installer.py", "bspatch_apply.py", "darksun_gff.py", "darksun_saves.py"):
                shutil.copy2(ROOT / "tools/release" / name, release / name)
            for name in ("release_manifest.json", "save_migration.json"):
                shutil.copy2(BUILD / name, release / name)
            game = release / "game_data" / "DARKSUN"
            game.mkdir(parents=True)
            manifest = json.loads((BUILD / "release_manifest.json").read_text(encoding="utf-8"))
            for name in manifest["editions"]["steam"]:
                shutil.copy2(STEAM / name, game / name)
            shutil.copytree(BUILD / "patches", release / "patches")
            shutil.copytree(BUILD / "resources", release / "resources")
            exe = game / "DSUN.EXE"
            data = exe.read_bytes()
            exe.write_bytes(data[:-1] + bytes((data[-1] ^ 0xFF,)))
            before = {path.name: path.read_bytes() for path in game.iterdir()}
            result = subprocess.run([sys.executable, str(release / "installer.py")], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual({path.name: path.read_bytes() for path in game.iterdir()}, before)

    @unittest.skipUnless(STEAM.is_dir() and (BUILD / "release_manifest.json").is_file(),
                         "requires the Steam files and build_release_patches.py output")
    def test_installer_changes_nothing_when_a_font_bank_is_missing(self):
        with tempfile.TemporaryDirectory() as temporary:
            release = Path(temporary)
            for name in ("installer.py", "bspatch_apply.py", "darksun_gff.py", "darksun_saves.py"):
                shutil.copy2(ROOT / "tools/release" / name, release / name)
            for name in ("release_manifest.json", "save_migration.json"):
                shutil.copy2(BUILD / name, release / name)
            shutil.copytree(BUILD / "patches", release / "patches")
            game = release / "game_data" / "DARKSUN"
            game.mkdir(parents=True)
            manifest = json.loads((BUILD / "release_manifest.json").read_text(encoding="utf-8"))
            for name in manifest["editions"]["steam"]:
                shutil.copy2(STEAM / name, game / name)
            before = {path.name: path.read_bytes() for path in game.iterdir()}
            result = subprocess.run([sys.executable, str(release / "installer.py")], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual({path.name: path.read_bytes() for path in game.iterdir()}, before)


if __name__ == "__main__":
    unittest.main()
