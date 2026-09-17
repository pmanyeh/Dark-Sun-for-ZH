import struct
import unittest
from unittest.mock import patch

from tools.build_view_character_candidate import (
    LABEL_ORIGINAL, NUMBER_ORIGINAL, PLACEMENTS, coordinates, patch_executable, patch_window, redirect, verify_overlay_relocations,
)
from tools.plan_name_slot_consumers import assemble_name_slot_cache
import test_ability_ui_candidate as ability_tests

if ability_tests.HAVE_UNICORN:
    from unicorn.x86_const import *


class ViewGuardsTests(unittest.TestCase):
    def test_equal_length_redirects(self):
        self.assertEqual(len(redirect(44, 0xFFEC)), len(LABEL_ORIGINAL))
        self.assertEqual(len(redirect(34, 0xFFEB)), len(NUMBER_ORIGINAL))
        with self.assertRaises(ValueError):
            redirect(10, 0xFFEC)

    def test_wrong_executable_rejected(self):
        with self.assertRaises(ValueError):
            patch_executable(b"wrong")

    def test_overlay_fixup_guard_protects_both_operand_bytes(self):
        data = bytearray(0x202)
        struct.pack_into("<H", data, 0x200, 0x20)
        parser = {"parse_mz": lambda _: {"image_end": 0},
                  "parse_fbov": lambda *_: {"exeinfo": 0, "overlay_base": 0},
                  "find_table": lambda *_: 0,
                  "parse_table": lambda *_: [{"file_start": 0x100, "file_end": 0x200, "relocation_count": 1}]}
        with patch("tools.build_view_character_candidate.runpy.run_path", return_value=parser):
            verify_overlay_relocations(data, [(0x100, 0x120)])
            verify_overlay_relocations(data, [(0x122, 0x130)])
            for region in ((0x120, 0x121), (0x121, 0x122)):
                with self.assertRaisesRegex(ValueError, "overlay relocation"):
                    verify_overlay_relocations(data, [region])

    def test_layout_has_room_for_labels_numbers_and_equipment(self):
        # v63 reflowed this to three columns of two rows and moved the
        # equipment slots back off to the side, so the ability grid no
        # longer needs to dodge them at x=259; it still must clear the race
        # row underneath and each number must land 4px after its label.
        for row in range(6):
            label_x, number_x, y = coordinates(row)
            self.assertEqual(number_x - (label_x + 24), 4)
            self.assertLess(number_x + 12, 290)
            self.assertLess(y + 10, 86)  # race row remains at 86
        self.assertEqual([coordinates(i)[2] for i in range(6)], [40, 40, 40, 52, 52, 52])
        # PLACEMENTS itself still documents v58b's own (now-reverted) move;
        # this only re-checks that v58b's three rects didn't overlap each
        # other, which is unrelated to the ability grid's layout.
        rects = [(x, y, x + 18, y + 18) for _, (x, y) in PLACEMENTS.values()]
        self.assertTrue(all(r[2] <= 281 and r[3] <= 100 for r in rects))
        self.assertLessEqual(rects[0][3], rects[1][1])
        self.assertLessEqual(rects[1][3], rects[2][1])

    def test_window_patch_changes_only_three_coordinate_pairs(self):
        window = bytearray(2841)
        window[:4] = b"WIND"
        struct.pack_into("<I", window, 8, 11500)
        offsets = (0x64F, 0x66D, 0x68B)
        for offset, (ident, (before, _)) in zip(offsets, PLACEMENTS.items()):
            window[offset:offset + 12] = b"APFM" + struct.pack("<Ihh", ident, *before)
        result = patch_window(bytes(window))
        for offset, (_, after) in zip(offsets, PLACEMENTS.values()):
            self.assertEqual(struct.unpack_from("<hh", result, offset + 8), after)
        allowed = {i for o in offsets for i in range(o + 8, o + 12)}
        self.assertTrue(all(a == b or i in allowed for i, (a, b) in enumerate(zip(window, result))))
        window[0x657] = 0
        with self.assertRaises(ValueError):
            patch_window(bytes(window))


class ViewMachineTests(ability_tests.AbilityMachineTests):
    @classmethod
    def setUpClass(cls):
        cls.core = assemble_name_slot_cache(backpack_ids=(1303, 100), ability_ids=ability_tests.TEST_IDS, view_character=True)

    def dos_interrupt(self, cpu, interrupt, unused):
        if interrupt not in (0x81, 0x82):
            return super().dos_interrupt(cpu, interrupt, unused)
        sp = cpu.reg_read(UC_X86_REG_SP)
        count = 14 if interrupt == 0x81 else 13
        args = struct.unpack(f"<{count}H", cpu.mem_read(0x80000 + sp, count * 2))
        self.assertEqual(args[:2], (0x4567, 0x5678))
        if interrupt == 0x81:
            self.assertEqual(args[4:12], (0x3351, 0x5000, 0, 0xFF, 0xFE, 0x2F, 0x14, 0))
            self.assertEqual(self.text_at(args[12:14]), b'"#:')
            self.view_draws.append((args[2], args[3], self.slot_record(0x22), self.slot_record(0x23)))
        else:
            self.assertEqual(args[4:], (0x335A, 0x5000, 0, 0xFF, 0xFE, 0x2F, 0x14, 0, 19))
            self.number_args = args
            cpu.emu_stop()

    def view_registers(self, row=0):
        self.cpu.mem_write(0x4300, struct.pack("<HH", 0x4567, 0x5678))
        self.cpu.mem_write(0x50000 + 0x326E, struct.pack("<HH", 0x2F, 0))
        for register, value in {UC_X86_REG_CS: 0xA000, UC_X86_REG_DS: 0x5000, UC_X86_REG_ES: 0x3333,
                UC_X86_REG_SS: 0x8000, UC_X86_REG_SP: 0xF000, UC_X86_REG_BP: 0xDADA,
                UC_X86_REG_SI: row, UC_X86_REG_DI: 0x2222}.items():
            self.cpu.reg_write(register, value)

    def test_view_label_loop_has_two_columns_and_preserves_caller(self):
        code = bytes.fromhex("55 8B EC 56 33 F6") + redirect(44, 0xFFEC)
        code += bytes.fromhex("B8 30 04 8E C0 66 26 FF 36 00 00")
        code += bytes.fromhex("CD 81 90 90 90 83 C4 1C 46 83 FE 06 7C BB 5E 5D CB")
        self.cpu.mem_write(0xA4000, code)
        self.view_registers(row=0x1111)
        self.cpu.mem_write(0x8F000, struct.pack("<HH", 0x2000, 0xA000))
        self.view_draws = []
        self.stopped = False
        self.cpu.emu_start(0xA4000, 0x100000, count=100000)
        self.assertTrue(self.stopped)
        self.assertEqual(self.cpu.reg_read(UC_X86_REG_SP), 0xF004)
        self.assertEqual(self.cpu.reg_read(UC_X86_REG_BP), 0xDADA)
        self.assertEqual(self.cpu.reg_read(UC_X86_REG_SI), 0x1111)
        self.assertEqual(self.cpu.reg_read(UC_X86_REG_DI), 0x2222)
        self.assertEqual(self.cpu.reg_read(UC_X86_REG_ES), 0x430)  # matches original surface setup
        self.assertEqual(len(self.view_draws), 6)
        for row, (x, y, first, second) in enumerate(self.view_draws):
            label_x, _, expected_y = coordinates(row)
            self.assertEqual((x, y), (label_x, expected_y))
            self.assertEqual((first, second), tuple(self.glyph(i) for i in ability_tests.TEST_IDS[row * 2:row * 2 + 2]))

    def test_view_numbers_keep_format_and_value_in_both_columns(self):
        code = redirect(34, 0xFFEB) + bytes.fromhex("B8 30 04 8E C0 66 26 FF 36 00 00 CD 82")
        self.cpu.mem_write(0xA5000, code)
        for row in range(6):
            self.view_registers(row)
            # Only the numeric value is prepared before the revised hook.
            self.cpu.mem_write(0x8F000, struct.pack("<H", 19))
            self.number_args = None
            self.cpu.emu_start(0xA5000, 0x100000, count=1000)
            _, x, y = coordinates(row)
            self.assertEqual(self.number_args[2:4], (x, y))
            self.assertEqual(self.cpu.reg_read(UC_X86_REG_SP), 0xEFE8)
            self.assertEqual(self.cpu.reg_read(UC_X86_REG_SI), row)


if __name__ == "__main__":
    unittest.main()
