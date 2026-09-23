"""Binary guards plus optional 16-bit execution tests (pip install unicorn)."""
import unittest

from tools.build_material_labels_candidate import (
    CONTINUATION_IP,
    GAP_1,
    GAP_2,
    MATERIAL_ORIGINAL,
    MATERIAL_SITE,
    TAIL_BYTES,
    ZONE_1_LEN,
    ZONE_1_SITE,
    ZONE_2_LEN,
    ZONE_2_SITE,
    PARENT_EXE_HASH,
    patch_executable,
    split_material_redirect,
)
from tools.build_fixed_labels_candidate import LABEL_IDS
from tools.plan_name_slot_consumers import (
    DECODER_OFFSET,
    TOOLBIN,
    assemble_name_slot_cache,
    resident_font_trampoline,
)
import test_backpack_ui_candidate as backpack_tests
from unittest.mock import patch as mock_patch

HAVE_UNICORN = backpack_tests.HAVE_UNICORN

if HAVE_UNICORN:
    from unicorn.x86_const import *

# (material index, expected decoded transport-code text, expected glyph ids)
MATERIALS = (
    (0, bytes([0x22, 0x23]), (367, 691)),          # Wooden -> 木製
    (1, bytes([0x22, 0x23]), (849, 691)),          # Bone -> 骨製
    (2, bytes([0x22, 0x23]), (544, 691)),          # Stone -> 石製
    (3, bytes([0x22, 0x23, 0x26]), (871, 544, 691)),  # Obsidian -> 黑石製
    (4, bytes([0x22, 0x23, 0x26]), (762, 222, 691)),  # Metal -> 金屬製
    (5, bytes([0x22, 0x23]), (528, 691)),          # Leather -> 皮製
)


class MaterialLabelsGuardsTests(unittest.TestCase):
    def test_wrong_source_rejected(self):
        with self.assertRaisesRegex(ValueError, "not v61"):
            patch_executable(b"wrong")

    def test_split_stub_lengths_and_gaps_are_untouched(self):
        zone1, zone2 = split_material_redirect()
        self.assertEqual(len(zone1), ZONE_1_LEN)
        self.assertEqual(len(zone2), ZONE_2_LEN)
        # zone2 must start exactly after zone1 + the first (unwritten) gap.
        self.assertEqual(ZONE_2_SITE, ZONE_1_SITE + ZONE_1_LEN + len(GAP_1))
        # The full original span is zone1 + gap1 + zone2 + gap2 + tail.
        self.assertEqual(
            len(MATERIAL_ORIGINAL),
            ZONE_1_LEN + len(GAP_1) + ZONE_2_LEN + len(GAP_2) + len(TAIL_BYTES),
        )
        self.assertEqual(CONTINUATION_IP, MATERIAL_SITE + len(MATERIAL_ORIGINAL))

    def test_redirect_replaces_only_the_two_safe_zones(self):
        image = bytearray(MATERIAL_SITE + len(MATERIAL_ORIGINAL) + 16)
        image[MATERIAL_SITE:MATERIAL_SITE + len(MATERIAL_ORIGINAL)] = MATERIAL_ORIGINAL
        with (
            mock_patch("tools.build_material_labels_candidate.sha256", return_value=PARENT_EXE_HASH),
            mock_patch("tools.build_material_labels_candidate.verify_overlay_relocations") as guard,
            mock_patch("tools.build_material_labels_candidate.mz_relocation_file_offsets", return_value=frozenset({0x1234})),
        ):
            result = patch_executable(bytes(image))
        guard.assert_called_once_with(
            bytes(image),
            [(ZONE_1_SITE, ZONE_1_SITE + ZONE_1_LEN), (ZONE_2_SITE, ZONE_2_SITE + ZONE_2_LEN)],
        )
        zone1, zone2 = split_material_redirect()
        self.assertEqual(result[ZONE_1_SITE:ZONE_1_SITE + ZONE_1_LEN], zone1)
        self.assertEqual(result[ZONE_2_SITE:ZONE_2_SITE + ZONE_2_LEN], zone2)
        # Both relocated gaps and the dead tail keep their original bytes.
        gap1_at = ZONE_1_SITE + ZONE_1_LEN
        self.assertEqual(result[gap1_at:gap1_at + len(GAP_1)], GAP_1)
        gap2_at = ZONE_2_SITE + ZONE_2_LEN
        self.assertEqual(result[gap2_at:gap2_at + len(GAP_2)], GAP_2)
        tail_at = gap2_at + len(GAP_2)
        self.assertEqual(result[tail_at:tail_at + len(TAIL_BYTES)], TAIL_BYTES)
        self.assertEqual(result[:MATERIAL_SITE], image[:MATERIAL_SITE])
        end = MATERIAL_SITE + len(MATERIAL_ORIGINAL)
        self.assertEqual(result[end:], image[end:])

    def test_consumer_mismatch_rejected(self):
        image = bytes(MATERIAL_SITE + len(MATERIAL_ORIGINAL) + 1)
        with mock_patch("tools.build_material_labels_candidate.sha256", return_value=PARENT_EXE_HASH):
            with self.assertRaisesRegex(ValueError, "consumer differs"):
                patch_executable(image)


@unittest.skipUnless(HAVE_UNICORN and (TOOLBIN / "as.exe").exists(), "requires Unicorn and GNU toolchain")
class MaterialLabelsMachineTests(backpack_tests.BackpackMachineTests):
    @classmethod
    def setUpClass(cls):
        cls.core = assemble_name_slot_cache(
            backpack_ids=(1303, 100),
            ability_ids=(93, 761, 1316, 1315, 855, 715, 354, 93, 354, 1314, 860, 93),
            # v67 added VIEW CHARACTER HP:/PSI: (生命/靈能) after the v61 pair.
            label_ids=LABEL_IDS + (507, 139, 822, 629),
            materials=True,
        )

    def dos_interrupt(self, cpu, interrupt, unused):
        if interrupt != 0x80:
            return super().dos_interrupt(cpu, interrupt, unused)
        self.stopped = True
        self.landed_sp = cpu.reg_read(UC_X86_REG_SP)
        cpu.emu_stop()

    def run_material(self, material_index, helper_ip=0x1000, bp=0x9000, prefix_flags=0x00):
        zone1, zone2 = split_material_redirect()
        # Reassemble the exact 32-byte on-disk layout: real stub bytes in
        # the two safe zones, int3 filler standing in for the two relocated
        # gaps and the dead "add sp,8" tail this redirect never falls
        # through to -- if the jump/skip math is off by even one byte,
        # landing on an int3 fails the test loudly instead of silently
        # reading garbage.
        blob = zone1 + b"\xCC" * len(GAP_1) + zone2 + b"\xCC" * len(GAP_2) + b"\xCC" * len(TAIL_BYTES)
        assert len(blob) == len(MATERIAL_ORIGINAL)
        trap = bytes.fromhex("CD 80")
        self.cpu.mem_write(0xA0000 + helper_ip, blob + trap)
        regs = {UC_X86_REG_CS: 0xA000, UC_X86_REG_DS: 0x5000, UC_X86_REG_ES: 0x3333,
                UC_X86_REG_SS: 0x8000, UC_X86_REG_SP: 0xF000, UC_X86_REG_BP: bp,
                UC_X86_REG_SI: 0x1111, UC_X86_REG_DI: 0x2222,
                UC_X86_REG_DX: prefix_flags | material_index}
        for register, value in regs.items():
            self.cpu.reg_write(register, value)
        # Poison the destination buffer so a short copy is easy to notice.
        self.cpu.mem_write(0x80000 + bp - 0x28, b"\xAA" * 0x28)
        self.stopped = False
        self.expected_sp_before = 0xF000
        self.cpu.emu_start(0xA0000 + helper_ip, 0x100000, count=100000)
        self.assertTrue(self.stopped, "did not reach the untouched continuation")
        self.assertEqual(self.landed_sp, self.expected_sp_before, "stack was not fully unwound")
        for register in (UC_X86_REG_BP, UC_X86_REG_SI, UC_X86_REG_DI, UC_X86_REG_DS, UC_X86_REG_ES):
            self.assertEqual(self.cpu.reg_read(register), regs[register])
        return bytes(self.cpu.mem_read(0x80000 + bp - 0x28, 0x28))

    def test_each_material_decodes_correct_glyphs_and_terminates(self):
        for index, text, ids in MATERIALS:
            with self.subTest(material_index=index):
                buffer = self.run_material(index)
                terminator = buffer.index(0)
                self.assertEqual(buffer[:terminator], text)
                for code, cjk_id in zip(text, ids):
                    self.assertEqual(self.slot_record(code), self.glyph(cjk_id))
                # Nothing past the NUL was touched (still poisoned 0xAA).
                self.assertEqual(buffer[terminator + 1:], b"\xAA" * (len(buffer) - terminator - 1))

    def test_high_flag_bits_above_the_index_are_ignored(self):
        buffer = self.run_material(1, prefix_flags=0x40)
        self.assertEqual(buffer[:buffer.index(0)], bytes([0x22, 0x23]))

    def test_repeated_material_reuses_cache(self):
        self.run_material(3)
        self.assertEqual(self.open_count, 3)
        self.run_material(3)
        self.assertEqual(self.open_count, 3)


if __name__ == "__main__":
    unittest.main()
