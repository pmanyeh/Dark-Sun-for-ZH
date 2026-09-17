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
    (8, bytes([0x22, 0x23, 0x26]), (1319, 1318, 27)),     # THRI-KREEN -> 螳螂人
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
            label_ids=(794, 560, 822, 629),
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

    def run_gender(self, record_byte, helper_ip=0x1000, bp=0x9000):
        # v65's gender_decoded pushes the whole remainder of the original
        # argument list itself (color escape, template id, the new fixed
        # position, and the passthrough surface pointer), stopping right
        # before the still-untouched "call 339E:016D" draw -- so this
        # capture reads a much longer stack than run_identity's.
        from tools.plan_name_slot_consumers import self_relative_tag_redirect
        stub = self_relative_tag_redirect(0xFFCD, 22)
        trap = bytes.fromhex("CD 80")
        self.cpu.mem_write(0xA0000 + helper_ip, stub + trap)
        record_seg, record_off = 0x7000, 0x0040
        regs = {UC_X86_REG_CS: 0xA000, UC_X86_REG_DS: 0x5000, UC_X86_REG_ES: 0x3333,
                UC_X86_REG_SS: 0x8000, UC_X86_REG_SP: 0xF000, UC_X86_REG_BP: bp,
                UC_X86_REG_SI: 0x1111, UC_X86_REG_DI: 0x2222}
        for register, value in regs.items():
            self.cpu.reg_write(register, value)
        self.cpu.mem_write(0x80000 + bp + 0xA, record_off.to_bytes(2, "little") + record_seg.to_bytes(2, "little"))
        self.cpu.mem_write(record_seg * 16 + record_off + 0x19, bytes([record_byte]))
        self.cpu.mem_write(0x80000 + bp + 6, (0x2345).to_bytes(2, "little") + (0x1234).to_bytes(2, "little"))
        self.cpu.mem_write(0x50000 + 0x3270, (0x2F).to_bytes(2, "little"))
        self.cpu.mem_write(0x50000 + 0x326E, (0x30).to_bytes(2, "little"))
        self.stopped = False
        self.cpu.emu_start(0xA0000 + helper_ip, 0x100000, count=100000)
        self.assertTrue(self.stopped, "did not reach the untouched continuation")
        for register in (UC_X86_REG_BP, UC_X86_REG_SI, UC_X86_REG_DI, UC_X86_REG_DS, UC_X86_REG_SS):
            self.assertEqual(self.cpu.reg_read(register), regs[register])
        sp = self.landed_sp
        import struct
        # words[0] is the shallowest surviving word (right after lret's own
        # two pops), in the exact order the untouched draw call still
        # expects to find them -- see the inline comment below for the
        # full push-order derivation.
        words = struct.unpack_from("<14H", bytes(self.cpu.mem_read(0x80000 + sp, 28)))
        far_offset, far_segment = words[12], words[13]
        buffer = bytes(self.cpu.mem_read(far_segment * 16 + far_offset, 0x20))
        return buffer, words

    def test_each_gender_decodes_correct_glyphs_and_new_position(self):
        # Push order (deepest to shallowest): segment, offset, 0x3270,
        # 0x14, [326E], dword 0x00FE00FF, 0, ds, 0x0E11, GENDER_Y,
        # GENDER_X, dword ss:[bp+6], then bx/cx (consumed by lret). Reading
        # from SP upward therefore surfaces them in reverse.
        for record_byte, text, ids in GENDERS:
            with self.subTest(record_byte=record_byte):
                buffer, words = self.run_gender(record_byte)
                terminator = buffer.index(0)
                self.assertEqual(buffer[:terminator], text)
                for code, cjk_id in zip(text, ids):
                    self.assertEqual(self.slot_record(code), self.glyph(cjk_id))
                self.assertEqual(words[0:2], (0x2345, 0x1234))  # dword ss:[bp+6], untouched passthrough
                self.assertEqual(words[2], 149)      # GENDER_X
                self.assertEqual(words[3], 44)       # GENDER_Y
                self.assertEqual(words[4], 0x0E11)
                self.assertEqual(words[5], 0x5000)   # ds
                self.assertEqual(words[6], 0)
                self.assertEqual(words[7:9], (0x00FF, 0x00FE))  # dword 0x00FE00FF
                self.assertEqual(words[9], 0x30)     # ds:[0x326E]
                self.assertEqual(words[10], 0x14)
                self.assertEqual(words[11], 0x2F)    # ds:[0x3270]

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
