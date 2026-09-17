import struct
import unittest

from tools.build_ability_ui_candidate import (ability_redirect, LOOP_ORIGINAL, PATCHES,
    V57_LAYOUT, patch_executable)
from tools.audit_inventory_ui import layout_issues
from tools.plan_name_slot_consumers import assemble_name_slot_cache
import test_backpack_ui_candidate as backpack_tests

HAVE_UNICORN = backpack_tests.HAVE_UNICORN

if HAVE_UNICORN:
    from unicorn.x86_const import *


TEST_IDS = (93, 761, 1316, 1315, 855, 715, 354, 93, 354, 1314, 860, 93)


class AbilityGuardsTests(unittest.TestCase):
    def test_loop_replacement_is_equal_length(self):
        self.assertEqual(len(LOOP_ORIGINAL), 50)
        self.assertEqual(len(ability_redirect()), 50)

    def test_panel_has_no_overlap_and_attack_origin_unchanged(self):
        self.assertEqual(layout_issues(V57_LAYOUT), [])
        self.assertEqual(V57_LAYOUT[0].bottom, 67)
        self.assertEqual(V57_LAYOUT[-1].y, 99)
        self.assertEqual(V57_LAYOUT[-1].bottom, 168)

    def test_wrong_source_and_incomplete_ids_rejected(self):
        with self.assertRaises(ValueError):
            patch_executable(b"wrong")
        with self.assertRaises(ValueError):
            assemble_name_slot_cache(backpack_ids=(1303, 100), ability_ids=(1, 2))


# Inherited tests also execute the v56 backpack/NAME cases against the v57 core.
class AbilityMachineTests(backpack_tests.BackpackMachineTests):
    @classmethod
    def setUpClass(cls):
        cls.core = assemble_name_slot_cache(backpack_ids=(1303, 100), ability_ids=TEST_IDS)

    def dos_interrupt(self, cpu, interrupt, unused):
        if interrupt != 0x80:
            return super().dos_interrupt(cpu, interrupt, unused)
        sp = cpu.reg_read(UC_X86_REG_SP)
        args = struct.unpack("<14H", cpu.mem_read(0x80000 + sp, 28))
        self.assertEqual(args[:2], (0x1234, 0x2345))
        self.assertEqual(args[4:12], (0xE11, 0x5000, 0, 0xFF, 0xFE, 0x2F, 0x14, 0))
        text = self.text_at(args[12:14])
        records = [self.slot_record(code) for code in text[:2]] if text == b'"#:' else []
        self.draws.append((args[2], args[3], text, records))

    def stop_at_continuation(self, cpu, address, size, unused):
        if address == 0xA2000:
            self.stopped = True
            cpu.emu_stop()
        else:
            super().stop_at_continuation(cpu, address, size, unused)

    def run_label_loop(self, x=236, y=8, helper_ip=0x1000):
        prolog = bytes.fromhex("55 8B EC 56 33 F6")
        # Original formatter far call is substituted by an observable interrupt;
        # original stack cleanup, row increment, branch and epilog run unchanged.
        tail = bytes.fromhex("CD 80 90 90 90 83 C4 1C 46 83 FE 06 7C C0 5E 5D CB")
        self.cpu.mem_write(0xA0000 + helper_ip, prolog + ability_redirect() + tail)
        for i, label in enumerate((b"STR:", b"DEX:", b"CON:", b"INT:", b"WIS:", b"CHR:")):
            offset = 0x103B + 5 * i
            self.cpu.mem_write(0x50000 + 0xEF2 + 4 * i, struct.pack("<HH", offset, 0x5000))
            self.cpu.mem_write(0x50000 + offset, label + b"\0")
        self.cpu.mem_write(0x50000 + 0x326E, struct.pack("<HH", 0x2F, 0))
        regs = {UC_X86_REG_CS: 0xA000, UC_X86_REG_DS: 0x5000, UC_X86_REG_ES: 0x3333,
                UC_X86_REG_SS: 0x8000, UC_X86_REG_SP: 0xF000, UC_X86_REG_BP: 0xDADA,
                UC_X86_REG_SI: 0x1111, UC_X86_REG_DI: 0x2222}
        for register, value in regs.items():
            self.cpu.reg_write(register, value)
        self.cpu.mem_write(0x8F000, struct.pack("<6H", 0x2000, 0xA000, 0x1234, 0x2345, x, y))
        self.draws = []
        self.stopped = False
        self.cpu.emu_start(0xA0000 + helper_ip, 0x100000, count=100000)
        self.assertTrue(self.stopped)
        self.assertEqual(self.cpu.reg_read(UC_X86_REG_SP), 0xF004)
        for register in (UC_X86_REG_BP, UC_X86_REG_SI, UC_X86_REG_DI, UC_X86_REG_DS, UC_X86_REG_ES):
            self.assertEqual(self.cpu.reg_read(register), regs[register])
        self.assertEqual(len(self.draws), 6)
        return self.draws

    def test_six_translated_rows_use_correct_glyphs_and_ten_pixel_spacing(self):
        for i, (x, y, text, records) in enumerate(self.run_label_loop()):
            self.assertEqual((x, y, text), (236, 8 + 10 * i, b'"#:'))
            self.assertEqual(records, [self.glyph(value) for value in TEST_IDS[2 * i:2 * i + 2]])

    def test_non_inventory_origin_keeps_english_and_seven_pixel_spacing(self):
        for i, (x, y, text, _) in enumerate(self.run_label_loop(y=23)):
            self.assertEqual((x, y), (236, 23 + 7 * i))
            self.assertEqual(text, (b"STR:", b"DEX:", b"CON:", b"INT:", b"WIS:", b"CHR:")[i])
        self.assertEqual(self.open_count, 0)

    def test_other_x_origin_is_not_translated(self):
        self.assertEqual(self.run_label_loop(x=10)[0][2], b"STR:")
        self.assertEqual(self.open_count, 0)

    def test_redirect_is_independent_of_overlay_ip(self):
        self.assertEqual(self.run_label_loop(helper_ip=0x1100)[5][1], 58)

    def test_backpack_survives_ability_cache_and_reverse(self):
        self.invoke()
        self.run_label_loop()
        self.assertEqual(self.text_at(self.invoke()), b'"#')
        self.assertEqual(self.slot_record(0x22), self.glyph(1303))
        self.assertEqual(self.run_label_loop()[0][2], b'"#:')

    def test_number_machine_code_matches_label_coordinates(self):
        draws = self.run_label_loop()
        code = bytes.fromhex("8B C6") + PATCHES[0x6F5E7][1] + b"\x50" + PATCHES[0x6F5EE][1]
        self.cpu.mem_write(0xA3000, code)
        for row, draw in enumerate(draws):
            self.cpu.reg_write(UC_X86_REG_CS, 0xA000)
            self.cpu.reg_write(UC_X86_REG_SP, 0xF000)
            self.cpu.reg_write(UC_X86_REG_SI, row)
            self.cpu.emu_start(0xA3000, 0xA3000 + len(code), count=10)
            x, y = struct.unpack("<HH", self.cpu.mem_read(0x8EFFC, 4))
            self.assertEqual((x, y), (264, draw[1]))


if __name__ == "__main__":
    unittest.main()
