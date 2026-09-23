"""Binary guards plus optional 16-bit execution tests (pip install unicorn)."""
import struct
import unittest

from tools.build_fixed_labels_candidate import (
    AC_ORIGINAL,
    AC_SITE,
    AC_TAG,
    LABEL_IDS,
    PARENT_EXE_HASH,
    PSI_ORIGINAL,
    PSI_SITE,
    PSI_TAG,
    patch_executable,
)
from tools.plan_name_slot_consumers import (
    DECODER_OFFSET,
    TOOLBIN,
    assemble_name_slot_cache,
    resident_font_trampoline,
    self_relative_tag_redirect,
)
import test_backpack_ui_candidate as backpack_tests
from unittest.mock import patch as mock_patch

HAVE_UNICORN = backpack_tests.HAVE_UNICORN

if HAVE_UNICORN:
    from unicorn.x86_const import *


class FixedLabelsGuardsTests(unittest.TestCase):
    def test_wrong_source_rejected(self):
        with self.assertRaisesRegex(ValueError, "not v60"):
            patch_executable(b"wrong")

    def test_missing_ability_ids_rejected(self):
        with self.assertRaisesRegex(ValueError, "ability support"):
            assemble_name_slot_cache(backpack_ids=(1303, 100), label_ids=LABEL_IDS)

    def test_stub_needs_at_least_twenty_two_bytes(self):
        with self.assertRaises(ValueError):
            self_relative_tag_redirect(AC_TAG, 14)

    def test_redirect_replaces_only_the_two_reviewed_spans(self):
        image = bytearray(PSI_SITE + len(PSI_ORIGINAL) + 32)
        image[AC_SITE:AC_SITE + len(AC_ORIGINAL)] = AC_ORIGINAL
        image[PSI_SITE:PSI_SITE + len(PSI_ORIGINAL)] = PSI_ORIGINAL
        with (
            mock_patch("tools.build_fixed_labels_candidate.sha256", return_value=PARENT_EXE_HASH),
            mock_patch("tools.build_fixed_labels_candidate.verify_overlay_relocations") as guard,
            mock_patch("tools.build_fixed_labels_candidate.mz_relocation_file_offsets", return_value=frozenset({0x1234})),
        ):
            result = patch_executable(bytes(image))
        guard.assert_called_once_with(bytes(image), [
            (AC_SITE, AC_SITE + len(AC_ORIGINAL)),
            (PSI_SITE, PSI_SITE + len(PSI_ORIGINAL)),
        ])
        self.assertEqual(result[AC_SITE:AC_SITE + len(AC_ORIGINAL)], self_relative_tag_redirect(AC_TAG, len(AC_ORIGINAL)))
        self.assertEqual(result[PSI_SITE:PSI_SITE + len(PSI_ORIGINAL)], self_relative_tag_redirect(PSI_TAG, len(PSI_ORIGINAL)))
        untouched = bytearray(image)
        untouched[AC_SITE:AC_SITE + len(AC_ORIGINAL)] = result[AC_SITE:AC_SITE + len(AC_ORIGINAL)]
        untouched[PSI_SITE:PSI_SITE + len(PSI_ORIGINAL)] = result[PSI_SITE:PSI_SITE + len(PSI_ORIGINAL)]
        self.assertEqual(result, bytes(untouched))

    def test_consumer_mismatch_rejected(self):
        image = bytes(PSI_SITE + len(PSI_ORIGINAL) + 1)
        with mock_patch("tools.build_fixed_labels_candidate.sha256", return_value=PARENT_EXE_HASH):
            with self.assertRaisesRegex(ValueError, "consumer differs"):
                patch_executable(image)


@unittest.skipUnless(HAVE_UNICORN and (TOOLBIN / "as.exe").exists(), "requires Unicorn and GNU toolchain")
class FixedLabelsMachineTests(backpack_tests.BackpackMachineTests):
    @classmethod
    def setUpClass(cls):
        cls.core = assemble_name_slot_cache(
            backpack_ids=(1303, 100),
            ability_ids=(93, 761, 1316, 1315, 855, 715, 354, 93, 354, 1314, 860, 93),
            # v67 added VIEW CHARACTER HP:/PSI: (生命/靈能) after the v61 pair.
            label_ids=LABEL_IDS + (507, 139, 822, 629),
        )

    def dos_interrupt(self, cpu, interrupt, unused):
        if interrupt != 0x80:
            return super().dos_interrupt(cpu, interrupt, unused)
        sp = cpu.reg_read(UC_X86_REG_SP)
        self.captured_sp = sp
        self.captured = bytes(cpu.mem_read(0x80000 + sp, 28))
        self.stopped = True
        cpu.emu_stop()

    def run_span(self, tag, original, helper_ip=0x1000):
        stub = self_relative_tag_redirect(tag, len(original))
        trap = bytes.fromhex("CD 80")
        self.cpu.mem_write(0xA0000 + helper_ip, stub + trap)
        regs = {UC_X86_REG_CS: 0xA000, UC_X86_REG_DS: 0x5000, UC_X86_REG_ES: 0x3333,
                UC_X86_REG_SS: 0x8000, UC_X86_REG_SP: 0xF000, UC_X86_REG_BP: 0x9000,
                UC_X86_REG_SI: 0x1111, UC_X86_REG_DI: 0x2222}
        for register, value in regs.items():
            self.cpu.reg_write(register, value)
        self.cpu.mem_write(0x50000 + 0x3270, struct.pack("<H", 0x2F))
        self.cpu.mem_write(0x50000 + 0x326E, struct.pack("<H", 0x30))
        self.stopped = False
        self.captured = None
        self.cpu.emu_start(0xA0000 + helper_ip, 0x100000, count=100000)
        self.assertTrue(self.stopped, "did not reach the untouched continuation")
        for register in (UC_X86_REG_BP, UC_X86_REG_SI, UC_X86_REG_DI, UC_X86_REG_DS, UC_X86_REG_ES):
            self.assertEqual(self.cpu.reg_read(register), regs[register])
        return self.captured

    def test_ac_overwrites_only_the_two_prefix_bytes(self):
        self.cpu.mem_write(0x80000 + 0x9000 - 0x50, b"AC: 12\0\0")
        self.cpu.mem_write(0x80000 + 0x9000 + 6, struct.pack("<HH", 0x1234, 0x2345))
        self.cpu.mem_write(0x80000 + 0x9000 + 0xC, struct.pack("<H", 99))
        self.cpu.mem_write(0x80000 + 0x9000 + 0xE, struct.pack("<H", 236))
        args = self.run_span(AC_TAG, AC_ORIGINAL)
        # Captured memory is read low-to-high address, i.e. last-pushed-first.
        words = struct.unpack_from("<14H", args, 0)
        self.assertEqual(words[0:2], (0x1234, 0x2345))  # dword ptr ss:[bp+6], untouched passthrough
        self.assertEqual(words[2:4], (99, 236))  # word ss:[bp+0xc], word ss:[bp+0xe]
        self.assertEqual(words[4:12], (0x0E11, 0x5000, 0, 0x00FF, 0x00FE, 0x30, 0x14, 0x2F))
        buffer_off, buffer_seg = words[12:14]
        self.assertEqual((buffer_seg, buffer_off), (0x8000, 0x9000 - 0x50))
        buffer = bytes(self.cpu.mem_read(buffer_seg * 16 + buffer_off, 8))
        self.assertEqual(buffer, bytes([0x22, 0x23]) + b": 12\0\0")
        self.assertEqual(self.slot_record(0x22), self.glyph(794))
        self.assertEqual(self.slot_record(0x23), self.glyph(560))

    def test_psi_keeps_color_escape_and_replaces_label(self):
        # Unlike AC, this span starts mid-argument-list: the untouched code
        # immediately before it already pushed word ds:[0x3270]/0x14/word
        # ds:[0x326e]. Those three words are genuinely on the caller's stack
        # by the time this redirect runs but are never simulated here, so
        # this harness only captures what psi_decoded itself pushes.
        args = self.run_span(PSI_TAG, PSI_ORIGINAL)
        words = struct.unpack_from("<9H", args, 0)
        self.assertEqual(words[0:2], (0x1234, 0x2345))  # dword ptr ds:[0x11A4], untouched passthrough
        self.assertEqual(words[2:4], (236, 69))  # packed x, y
        buffer_off, buffer_seg = words[4:6]
        self.assertEqual(buffer_seg, 0x7000)  # FONT-local segment (this test's font_pointer/cs base)
        self.assertEqual(words[6:9], (0, 0x00FF, 0x00FE))
        buffer = bytes(self.cpu.mem_read(buffer_seg * 16 + buffer_off, 10))
        self.assertEqual(buffer, b"%C%C%C" + bytes([0x22, 0x23]) + b":\0")
        self.assertEqual(self.slot_record(0x22), self.glyph(822))
        self.assertEqual(self.slot_record(0x23), self.glyph(629))


if __name__ == "__main__":
    unittest.main()
