"""Unicorn machine tests for the dialogue menu title decoder entry (tag FF81)."""
import struct
import unittest

from tools.plan_name_slot_consumers import assemble_name_slot_cache, self_relative_tag_redirect
from tools.view_ui_layer import VIEW_UI_EXE_PATCHES
import test_backpack_ui_candidate as backpack_tests

HAVE_UNICORN = backpack_tests.HAVE_UNICORN

if HAVE_UNICORN:
    from unicorn.x86_const import *

TITLE_BUFFER = 0x5504
# The formatter arguments the original overlay pushes after the title
# pointer, top of stack first: x=6, y, "%C%C%C%s" (DS:1F58) and the three
# %C colour dwords. English keeps the original y=4; Chinese draws at y=2 so
# its 10-row glyphs clear the first choice at y=13.
FORMATTER_TAIL = (0x1F58, 0x5000, 0x0000, 0x00FF, 0x00FE, 0x002F, 0x0014, 0x0011)


def triple(cjk_id):
    return bytes((0x5E, cjk_id // 94 + 0x21, cjk_id % 94 + 0x21))


class MenuTitlePatchTests(unittest.TestCase):
    def test_exe_redirect_is_the_35_byte_tag_ff81_stub(self):
        patches = {offset: bytes.fromhex(patched) for offset, _, patched, _ in VIEW_UI_EXE_PATCHES}
        self.assertEqual(patches[0x07D818], self_relative_tag_redirect(0xFF81, 35))
        self.assertEqual(patches[0x07D814], b"\xCF")


@unittest.skipUnless(HAVE_UNICORN and (backpack_tests.TOOLBIN / "as.exe").exists(), "requires Unicorn and GNU toolchain")
class MenuTitleMachineTests(backpack_tests.BackpackMachineTests):
    @classmethod
    def setUpClass(cls):
        cls.core = assemble_name_slot_cache(backpack_ids=(1303, 100), menu_titles=True)

    def dos_interrupt(self, cpu, interrupt, unused):
        if interrupt != 0x80:
            return super().dos_interrupt(cpu, interrupt, unused)
        self.stopped = True
        self.landed_sp = cpu.reg_read(UC_X86_REG_SP)
        cpu.emu_stop()

    def draw_title(self, title, helper_ip=0x1000):
        # Each run gets its own address: Unicorn keeps a cached translation
        # if code is rewritten in place.
        stub = self_relative_tag_redirect(0xFF81, 35)
        self.cpu.mem_write(0xA0000 + helper_ip, stub + bytes.fromhex("CD 80"))
        self.cpu.mem_write(0x50000 + TITLE_BUFFER, title + b"\0")
        # The strupr call's (segment, offset) arguments are still on the stack.
        self.cpu.mem_write(0x80000 + 0xEFFC, struct.pack("<HH", TITLE_BUFFER, 0x5000))
        regs = {UC_X86_REG_CS: 0xA000, UC_X86_REG_DS: 0x5000, UC_X86_REG_ES: 0x3333,
                UC_X86_REG_SS: 0x8000, UC_X86_REG_SP: 0xEFFC, UC_X86_REG_BP: 0x9000,
                UC_X86_REG_SI: 0x1111, UC_X86_REG_DI: 0x2222}
        for register, value in regs.items():
            self.cpu.reg_write(register, value)
        self.stopped = False
        self.cpu.emu_start(0xA0000 + helper_ip, 0x100000, count=200000)
        self.assertTrue(self.stopped, "did not reach the untouched formatter call")
        for register in (UC_X86_REG_BP, UC_X86_REG_SI, UC_X86_REG_DI, UC_X86_REG_DS,
                         UC_X86_REG_ES, UC_X86_REG_SS):
            self.assertEqual(self.cpu.reg_read(register), regs[register])
        # add sp,4 then 24 bytes of formatter arguments, exactly as before.
        self.assertEqual(self.landed_sp, 0xF000 - 24)
        words = struct.unpack("<12H", self.cpu.mem_read(0x80000 + self.landed_sp, 24))
        self.assertEqual(words[0], 6)
        self.last_y = words[1]
        self.assertEqual(words[2:10], FORMATTER_TAIL)
        offset, segment = words[10:]
        return offset, segment, bytes(self.cpu.mem_read(segment * 16 + offset, 25)).split(b"\0")[0]

    def test_chinese_title_decodes_into_name_slots(self):
        # 你怎麼說？ with ids chosen to hit five distinct slots.
        ids = (40, 300, 555, 777, 1200)
        offset, segment, text = self.draw_title(b"".join(triple(value) for value in ids))
        self.assertEqual(segment, 0x7000)
        self.assertEqual(self.last_y, 2)
        self.assertEqual(text, bytes([0x22, 0x23, 0x26, 0x3C, 0x3E]))
        for code, cjk_id in zip(text, ids):
            self.assertEqual(self.slot_record(code), self.glyph(cjk_id))

    def test_consecutive_titles_are_not_served_from_the_cache(self):
        self.draw_title(triple(40) + triple(300), helper_ip=0x1000)
        _, _, text = self.draw_title(triple(555) + b"?", helper_ip=0x1100)
        self.assertEqual(text, b'"?')
        self.assertEqual(self.slot_record(0x22), self.glyph(555))

    def test_english_title_is_upper_cased_and_passed_through(self):
        offset, segment, text = self.draw_title(b"What do you say?")
        self.assertEqual((offset, segment), (TITLE_BUFFER, 0x5000))
        self.assertEqual(text, b"WHAT DO YOU SAY?")
        self.assertEqual(self.last_y, 4)
        self.assertEqual(self.open_count, 0)


@unittest.skipUnless(HAVE_UNICORN and (backpack_tests.TOOLBIN / "as.exe").exists(), "requires Unicorn and GNU toolchain")
class WindowTextMachineTests(MenuTitleMachineTests):
    """The window text setter (overlay 0x704AB, tag FF82)."""

    @classmethod
    def setUpClass(cls):
        cls.core = assemble_name_slot_cache(backpack_ids=(1303, 100), status_texts=True)

    def set_text(self, text, helper_ip=0x2000, bp=0x9000):
        stub = (b"\xB8\x82\xFF\x0E\x68" + (helper_ip + 17).to_bytes(2, "little")
                + bytes.fromhex("8C DB 80 EF 10 53 68 14 07 CB"))
        self.cpu.mem_write(0xA0000 + helper_ip, stub + bytes.fromhex("CD 80"))
        self.cpu.mem_write(0x60000 + 0x0100, text + b"\0")
        self.cpu.mem_write(0x80000 + bp + 0x0C, struct.pack("<HH", 0x0100, 0x6000))
        self.cpu.mem_write(0x80000 + bp - 0x28, b"\xAA")
        regs = {UC_X86_REG_CS: 0xA000, UC_X86_REG_DS: 0x5000, UC_X86_REG_ES: 0x3333,
                UC_X86_REG_SS: 0x8000, UC_X86_REG_SP: 0xF000, UC_X86_REG_BP: bp,
                UC_X86_REG_SI: 0x4321, UC_X86_REG_DI: 0x2222}
        for register, value in regs.items():
            self.cpu.reg_write(register, value)
        self.stopped = False
        self.cpu.emu_start(0xA0000 + helper_ip, 0x100000, count=200000)
        self.assertTrue(self.stopped, "did not reach the untouched strncpy call")
        for register in (UC_X86_REG_BP, UC_X86_REG_SI, UC_X86_REG_DI, UC_X86_REG_DS,
                         UC_X86_REG_ES, UC_X86_REG_SS):
            self.assertEqual(self.cpu.reg_read(register), regs[register])
        # The span's own effects, then strncpy(ss:bp-28h, source, 1Fh).
        self.assertEqual(bytes(self.cpu.mem_read(0x50000 + 0x5435, 2)), b"\x21\x43")
        self.assertEqual(bytes(self.cpu.mem_read(0x80000 + bp - 0x28, 1)), b"\0")
        self.assertEqual(self.landed_sp, 0xF000 - 10)
        words = struct.unpack("<5H", self.cpu.mem_read(0x80000 + self.landed_sp, 10))
        self.assertEqual(words[0:2], (bp - 0x28, 0x8000))
        self.assertEqual(words[4], 0x1F)
        offset, segment = words[2], words[3]
        return offset, segment, bytes(self.cpu.mem_read(segment * 16 + offset, 25)).split(b"\0")[0]

    def test_chinese_window_text_becomes_slot_codes(self):
        ids = (40, 300, 555)
        _, segment, text = self.set_text(b"".join(triple(value) for value in ids))
        self.assertEqual(segment, 0x7000)
        self.assertEqual(text, b'"#&')
        for code, cjk_id in zip(text, ids):
            self.assertEqual(self.slot_record(code), self.glyph(cjk_id))
        self.assertFalse(any(0x61 <= code <= 0x7A for code in text))

    def test_english_window_text_is_passed_through(self):
        offset, segment, text = self.set_text(b"GAME SAVED", helper_ip=0x2100)
        self.assertEqual((offset, segment, text), (0x0100, 0x6000, b"GAME SAVED"))
        self.assertEqual(self.open_count, 0)

    def test_chinese_title_decodes_into_name_slots(self):
        pass

    def test_consecutive_titles_are_not_served_from_the_cache(self):
        pass

    def test_english_title_is_upper_cased_and_passed_through(self):
        pass


@unittest.skipUnless(HAVE_UNICORN and (backpack_tests.TOOLBIN / "as.exe").exists(), "requires Unicorn and GNU toolchain")
class DrawTextMachineTests(MenuTitleMachineTests):
    """The resident draw_text wrapper 191F:0A40 (tag FF84)."""

    @classmethod
    def setUpClass(cls):
        cls.core = assemble_name_slot_cache(backpack_ids=(1303, 100), text_draws=True)

    def draw(self, text, helper_ip=0x3000, bp=0x9000):
        stub = self_relative_tag_redirect(0xFF84, 30)
        self.cpu.mem_write(0xA0000 + helper_ip, stub + bytes.fromhex("CD 80"))
        self.cpu.mem_write(0x60000 + 0x0200, text + b"\0")
        # [bp+6] window, [bp+0A] text, [bp+0E] x, [bp+10] y, [bp+12]/[bp+14] colours
        self.cpu.mem_write(0x80000 + bp + 6, struct.pack("<HHHHHHHH", 0x1111, 0x2222, 0x0200, 0x6000,
                                                        0x0033, 0x0044, 0x0055, 0x0066))
        regs = {UC_X86_REG_CS: 0xA000, UC_X86_REG_DS: 0x5000, UC_X86_REG_ES: 0x3333,
                UC_X86_REG_SS: 0x8000, UC_X86_REG_SP: 0xF000, UC_X86_REG_BP: bp,
                UC_X86_REG_SI: 0x4321, UC_X86_REG_DI: 0x2222}
        for register, value in regs.items():
            self.cpu.reg_write(register, value)
        self.stopped = False
        self.cpu.emu_start(0xA0000 + helper_ip, 0x100000, count=200000)
        self.assertTrue(self.stopped, "did not reach the untouched formatter call")
        for register in (UC_X86_REG_BP, UC_X86_REG_SI, UC_X86_REG_DI, UC_X86_REG_DS,
                         UC_X86_REG_ES, UC_X86_REG_SS):
            self.assertEqual(self.cpu.reg_read(register), regs[register])
        # The span's 24 bytes of pushes, exactly as the original.
        self.assertEqual(self.landed_sp, 0xF000 - 24)
        words = struct.unpack("<12H", self.cpu.mem_read(0x80000 + self.landed_sp, 24))
        # top first: [bp+0E], [bp+10] (+2 for Chinese), 0D8F, ds, 0, 00FF, 00FE, [bp+12], 14h, [bp+14], text
        self.assertEqual(words[0], 0x0033)
        self.last_y = words[1]
        self.assertEqual(words[2:10], (0x0D8F, 0x5000, 0x0000, 0x00FF, 0x00FE, 0x0055, 0x0014, 0x0066))
        offset, segment = words[10:]
        return offset, segment, bytes(self.cpu.mem_read(segment * 16 + offset, 25)).split(b"\0")[0]

    def test_chinese_status_becomes_slot_codes(self):
        _, segment, text = self.draw(triple(40) + triple(300))
        self.assertEqual((segment, text), (0x7000, b'"#'))
        self.assertEqual(self.slot_record(0x23), self.glyph(300))
        self.assertEqual(self.last_y, 0x0046)

    def test_english_label_passes_through(self):
        self.assertEqual(self.draw(b"Okay", helper_ip=0x3100), (0x0200, 0x6000, b"Okay"))
        self.assertEqual(self.last_y, 0x0044)

    def width(self, pointer, text=b"", bp=0x9000):
        # The 17-byte redirect at 191F:0406 returns to the loop test at IP 042A,
        # or to the epilogue at 0437 for a null text.
        stub = bytes.fromhex("B8 86 FF 0E 68 2A 04 8C DB 80 EF 10 53 68 14 07 CB")
        self.cpu.mem_write(0xA0000 + 0x0406, stub)
        self.cpu.mem_write(0xA0000 + 0x042A, bytes.fromhex("CD 80"))
        self.cpu.mem_write(0xA0000 + 0x0437, bytes.fromhex("CD 80"))
        self.cpu.mem_write(0x60000 + 0x0300, text + b"\0")
        self.cpu.mem_write(0x80000 + bp + 6, struct.pack("<HH", *pointer))
        regs = {UC_X86_REG_CS: 0xA000, UC_X86_REG_DS: 0x5000, UC_X86_REG_ES: 0x3333,
                UC_X86_REG_SS: 0x8000, UC_X86_REG_SP: 0xF000, UC_X86_REG_BP: bp,
                UC_X86_REG_SI: 0x4321, UC_X86_REG_DI: 0x1234, UC_X86_REG_AX: 0x7777}
        for register, value in regs.items():
            self.cpu.reg_write(register, value)
        self.stopped = False
        self.cpu.emu_start(0xA0000 + 0x0406, 0x100000, count=200000)
        self.assertTrue(self.stopped)
        self.assertEqual(self.landed_sp, 0xF000)
        self.assertEqual((self.cpu.reg_read(UC_X86_REG_SI), self.cpu.reg_read(UC_X86_REG_DI)), (0, 0))
        for register in (UC_X86_REG_BP, UC_X86_REG_DS, UC_X86_REG_ES, UC_X86_REG_SS):
            self.assertEqual(self.cpu.reg_read(register), regs[register])
        landed_ip = self.cpu.reg_read(UC_X86_REG_IP) - 2
        return landed_ip, struct.unpack("<HH", self.cpu.mem_read(0x80000 + bp + 6, 4))

    def test_width_of_null_text_returns_zero(self):
        ip, _ = self.width((0, 0))
        self.assertEqual((ip, self.cpu.reg_read(UC_X86_REG_AX)), (0x0437, 0))

    def test_width_measures_the_decoded_slot_codes(self):
        ip, pointer = self.width((0x0300, 0x6000), triple(40) + triple(300))
        self.assertEqual(ip, 0x042A)
        self.assertEqual(pointer[1], 0x7000)
        self.assertEqual(bytes(self.cpu.mem_read(0x70000 + pointer[0], 3)), b'"#\0')

    def test_width_of_english_text_is_untouched(self):
        ip, pointer = self.width((0x0300, 0x6000), b"Okay")
        self.assertEqual((ip, pointer), (0x042A, (0x0300, 0x6000)))

    def test_chinese_title_decodes_into_name_slots(self):
        pass

    def test_consecutive_titles_are_not_served_from_the_cache(self):
        pass

    def test_english_title_is_upper_cased_and_passed_through(self):
        pass


if __name__ == "__main__":
    unittest.main()
