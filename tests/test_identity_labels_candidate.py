"""Unicorn machine tests for the gender/race FONT-local decoder entries."""
import unittest

from tools.plan_name_slot_consumers import assemble_name_slot_cache
import test_backpack_ui_candidate as backpack_tests
from unittest.mock import patch as mock_patch

HAVE_UNICORN = backpack_tests.HAVE_UNICORN

if HAVE_UNICORN:
    from unicorn.x86_const import *

# (record byte at +0x19, expected decoded text, expected glyph ids) -- gender
GENDERS = (
    (1, bytes([0x22, 0x23]), (512, 269)),  # MALE -> 男性
    (2, bytes([0x22, 0x23]), (189, 269)),  # FEMALE -> 女性
)

# (record byte at +0x18, expected decoded text, expected glyph ids) -- race
RACES = (
    (1, bytes([0x22, 0x23]), (27, 838)),                 # HUMAN -> 人類
    (2, bytes([0x22, 0x23]), (543, 27)),                 # DWARF -> 矮人
    (3, bytes([0x22, 0x23]), (586, 822)),                # ELF -> 精靈
    (4, bytes([0x22, 0x23, 0x26]), (106, 586, 822)),      # HALF-ELF -> 半精靈
    (5, bytes([0x22, 0x23, 0x26]), (106, 227, 27)),       # HALF-GIANT -> 半巨人
    (6, bytes([0x22, 0x23, 0x26]), (106, 724, 27)),       # HALFLING -> 半身人
    (7, bytes([0x22, 0x23, 0x26]), (1317, 484, 27)),      # MUL -> 穆爾人
    (8, bytes([0x22, 0x23, 0x26, 0x3C]), (1319, 1318, 289, 1004)),  # THRI-KREEN -> 螳螂戰士 (re_95)
)


@unittest.skipUnless(HAVE_UNICORN and (backpack_tests.TOOLBIN / "as.exe").exists(), "requires Unicorn and GNU toolchain")
class IdentityLabelsMachineTests(backpack_tests.BackpackMachineTests):
    @classmethod
    def setUpClass(cls):
        cls.core = assemble_name_slot_cache(
            backpack_ids=(1303, 100),
            ability_ids=(93, 761, 1316, 1315, 855, 715, 354, 93, 354, 1314, 860, 93),
            view_character=True,
            view_y_origin=63,
            label_ids=(794, 560, 822, 629, 507, 139, 822, 629),
            identity=True,
            gender_position=(44, 149),
        )

    def dos_interrupt(self, cpu, interrupt, unused):
        if interrupt != 0x80:
            return super().dos_interrupt(cpu, interrupt, unused)
        self.stopped = True
        self.landed_sp = cpu.reg_read(UC_X86_REG_SP)
        cpu.emu_stop()

    def run_identity(self, tag, record_field_offset, record_byte, helper_ip=0x1000, bp=0x9000):
        # Build the same 22-byte self_relative_tag_redirect a real build
        # would install, at a helper address (this only checks the FONT-local
        # decoder's own behavior, not the redirect's placement in the EXE).
        from tools.plan_name_slot_consumers import self_relative_tag_redirect
        stub = self_relative_tag_redirect(tag, 22)
        trap = bytes.fromhex("CD 80")
        self.cpu.mem_write(0xA0000 + helper_ip, stub + trap)
        record_seg, record_off = 0x7000, 0x0040
        regs = {UC_X86_REG_CS: 0xA000, UC_X86_REG_DS: 0x5000, UC_X86_REG_ES: 0x3333,
                UC_X86_REG_SS: 0x8000, UC_X86_REG_SP: 0xF000, UC_X86_REG_BP: bp,
                UC_X86_REG_SI: 0x1111, UC_X86_REG_DI: 0x2222}
        for register, value in regs.items():
            self.cpu.reg_write(register, value)
        # [bp+0xA] = far pointer (offset, segment) to the record.
        self.cpu.mem_write(0x80000 + bp + 0xA, record_off.to_bytes(2, "little") + record_seg.to_bytes(2, "little"))
        self.cpu.mem_write(record_seg * 16 + record_off + record_field_offset, bytes([record_byte]))
        # ds:[0x3270] is re-pushed verbatim by the decoded tail; any marker works.
        self.cpu.mem_write(0x50000 + 0x3270, b"\x77\x55")
        self.stopped = False
        self.cpu.emu_start(0xA0000 + helper_ip, 0x100000, count=100000)
        self.assertTrue(self.stopped, "did not reach the untouched continuation")
        for register in (UC_X86_REG_BP, UC_X86_REG_SI, UC_X86_REG_DI, UC_X86_REG_DS, UC_X86_REG_SS):
            self.assertEqual(self.cpu.reg_read(register), regs[register])
        # Stack (top to bottom, after the CD 80 trap's own nothing-pushed
        # state): [const 0x3270][offset][segment] were pushed by the decoder
        # before falling through to the trap.
        sp = self.landed_sp
        const_word = self.cpu.mem_read(0x80000 + sp, 2)
        offset_word = self.cpu.mem_read(0x80000 + sp + 2, 2)
        segment_word = self.cpu.mem_read(0x80000 + sp + 4, 2)
        self.assertEqual(bytes(const_word), b"\x77\x55")
        far_offset = int.from_bytes(offset_word, "little")
        far_segment = int.from_bytes(segment_word, "little")
        return bytes(self.cpu.mem_read(far_segment * 16 + far_offset, 0x20))

    def test_each_gender_decodes_correct_glyphs(self):
        # v66 returned gender to race's short redirect shape (only the string
        # pointer span), so it leaves the same three words as race does.
        for record_byte, text, ids in GENDERS:
            with self.subTest(record_byte=record_byte):
                buffer = self.run_identity(0xFFCD, 0x19, record_byte)
                terminator = buffer.index(0)
                self.assertEqual(buffer[:terminator], text)
                for code, cjk_id in zip(text, ids):
                    self.assertEqual(self.slot_record(code), self.glyph(cjk_id))

    def test_each_race_decodes_correct_glyphs(self):
        for record_byte, text, ids in RACES:
            with self.subTest(record_byte=record_byte):
                buffer = self.run_identity(0xFFCC, 0x18, record_byte)
                terminator = buffer.index(0)
                self.assertEqual(buffer[:terminator], text)
                for code, cjk_id in zip(text, ids):
                    self.assertEqual(self.slot_record(code), self.glyph(cjk_id))


if __name__ == "__main__":
    unittest.main()
