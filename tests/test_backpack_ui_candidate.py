"""Binary guards plus optional 16-bit execution tests (pip install unicorn)."""
import struct
import unittest

from tools.build_backpack_ui_candidate import WRAPPER_REDIRECT, patch_executable, patch_font
from tools.plan_name_slot_consumers import (
    DECODER_OFFSET, TOOLBIN, assemble_name_slot_cache, resident_font_trampoline,
    ds_relative_consumer_redirect_bytes,
)

try:
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_16, UC_HOOK_INTR, UC_HOOK_CODE
    from unicorn.x86_const import *
    HAVE_UNICORN = True
except ImportError:
    HAVE_UNICORN = False


class BackpackGuardsTests(unittest.TestCase):
    def test_only_full_v55_inputs_accepted(self):
        with self.assertRaises(ValueError):
            patch_executable(b"wrong")
        with self.assertRaises(ValueError):
            patch_font(b"wrong", (1303, 100))

    def test_invalid_bank_ids_rejected(self):
        with self.assertRaises(ValueError):
            assemble_name_slot_cache(backpack_ids=(1536, 100))

    def test_redirect_fits_original_wrapper(self):
        self.assertEqual(len(WRAPPER_REDIRECT), 15)
        self.assertEqual(WRAPPER_REDIRECT[-1], 0x90)


@unittest.skipUnless(HAVE_UNICORN and (TOOLBIN / "as.exe").exists(), "requires Unicorn and GNU toolchain")
class BackpackMachineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.core = assemble_name_slot_cache(backpack_ids=(1303, 100))

    def setUp(self):
        self.cpu = Uc(UC_ARCH_X86, UC_MODE_16)
        self.cpu.mem_map(0, 0x200000)
        self.cpu.mem_write(0x70000 + DECODER_OFFSET, self.core)
        self.cpu.mem_write(0x50000 + 0xA378, struct.pack("<HH", 4, 0x7000))
        self.cpu.mem_write(0x50000 + 0x11A4, struct.pack("<HH", 0x1234, 0x2345))
        self.cpu.mem_write(0x50000 + 0x166D, struct.pack("<HH", 0x100, 0x9000))
        # NAME record 0 contains CJK ID 300; record 1 is plain ASCII.
        self.cpu.mem_write(0x90100, (b"^$3\0").ljust(25, b"\0") + b"Sword\0".ljust(25, b"\0"))
        self.cpu.mem_write(0x40714, resident_font_trampoline())
        self.cpu.mem_write(0x60000 + 0x2391, WRAPPER_REDIRECT)
        self.cpu.mem_write(0x60000 + 0x2508, ds_relative_consumer_redirect_bytes(0x2516))
        self.open_count = 0
        self.current_bank = 0
        self.file_position = 0
        self.stopped = False
        self.cpu.hook_add(UC_HOOK_INTR, self.dos_interrupt)
        self.cpu.hook_add(UC_HOOK_CODE, self.stop_at_continuation)

    @staticmethod
    def glyph(cjk_id):
        return b"\x0a\0" + bytes([cjk_id % 251]) * 100

    def bank_bytes(self, bank):
        return bytes(16) + b"".join(struct.pack("<HH", i, 1040 + 102 * i) for i in range(256)) + b"".join(self.glyph(bank * 256 + i) for i in range(256))

    def dos_interrupt(self, cpu, interrupt, unused):
        self.assertEqual(interrupt, 0x21)
        ax = cpu.reg_read(UC_X86_REG_AX)
        address = cpu.reg_read(UC_X86_REG_DS) * 16 + cpu.reg_read(UC_X86_REG_DX)
        if ax == 0x3D00:
            filename = bytes(cpu.mem_read(address, 3))
            self.assertEqual(filename[:1], b"C")
            self.current_bank = filename[1] - ord("0")
            self.file_position = 0
            self.open_count += 1
            cpu.reg_write(UC_X86_REG_AX, 7)
        elif ax == 0x4200:
            self.file_position = (cpu.reg_read(UC_X86_REG_CX) << 16) | cpu.reg_read(UC_X86_REG_DX)
            cpu.reg_write(UC_X86_REG_AX, self.file_position & 0xFFFF)
            cpu.reg_write(UC_X86_REG_DX, self.file_position >> 16)
        elif ax >> 8 == 0x3F:
            size = cpu.reg_read(UC_X86_REG_CX)
            payload = self.bank_bytes(self.current_bank)[self.file_position:self.file_position + size]
            self.file_position += len(payload)
            cpu.mem_write(address, payload)
            cpu.reg_write(UC_X86_REG_AX, len(payload))
        elif ax >> 8 == 0x3E:
            cpu.reg_write(UC_X86_REG_AX, 0)
        else:
            self.fail(f"unexpected DOS function {ax:04X}")
        cpu.reg_write(UC_X86_REG_EFLAGS, cpu.reg_read(UC_X86_REG_EFLAGS) & ~1)

    def stop_at_continuation(self, cpu, address, size, unused):
        if address in (0x623A0, 0x62516):
            self.stopped = True
            cpu.emu_stop()

    def invoke(self, pointer=(0x1853, 0x5000), name_id=None):
        registers = {UC_X86_REG_CS: 0x6000, UC_X86_REG_DS: 0x5000, UC_X86_REG_ES: 0x3333,
                     UC_X86_REG_SS: 0x8000, UC_X86_REG_SP: 0xF000, UC_X86_REG_BP: 0xDADA,
                     UC_X86_REG_SI: 0x1111, UC_X86_REG_DI: 0x2222, UC_X86_REG_AX: name_id or 0}
        for register, value in registers.items():
            self.cpu.reg_write(register, value)
        self.cpu.mem_write(0x8F000, struct.pack("<HHHH", 0x9999, 0x8888, *pointer))
        self.stopped = False
        self.cpu.emu_start(0x62391 if name_id is None else 0x62508, 0x100000, count=10000)
        self.assertTrue(self.stopped, "did not return to original overlay continuation")
        for register in (UC_X86_REG_DS, UC_X86_REG_ES, UC_X86_REG_SI, UC_X86_REG_DI):
            self.assertEqual(self.cpu.reg_read(register), registers[register])
        sp = self.cpu.reg_read(UC_X86_REG_SP)
        if name_id is None:
            self.assertEqual(sp, 0xEFF4)
            self.assertEqual(self.cpu.reg_read(UC_X86_REG_BP), 0xEFFE)
            words = struct.unpack("<9H", self.cpu.mem_read(0x80000 + sp, 18))
            self.assertEqual(words[:3], (0x1234, 0x2345, 0x2C06))
            self.assertEqual(words[5:], (0xDADA, 0x9999, 0x8888, pointer[0]))
            return words[3:5]
        self.assertEqual(sp, 0xEFFC)
        self.assertEqual(self.cpu.reg_read(UC_X86_REG_BP), 0xDADA)
        return struct.unpack("<HH", self.cpu.mem_read(0x80000 + sp, 4))

    def text_at(self, pointer):
        return bytes(self.cpu.mem_read(pointer[1] * 16 + pointer[0], 25)).split(b"\0")[0]

    def slot_record(self, code):
        offset = struct.unpack("<H", self.cpu.mem_read(0x70004 + 0x108 + code * 2, 2))[0]
        return bytes(self.cpu.mem_read(0x70004 + offset, 102))

    def test_backpack_returns_two_ten_pixel_glyphs(self):
        self.assertEqual(self.text_at(self.invoke()), b'"#')
        self.assertEqual(self.slot_record(0x22), self.glyph(1303))
        self.assertEqual(self.slot_record(0x23), self.glyph(100))
        self.assertEqual(self.open_count, 2)

    def test_other_pointer_and_foreign_segment_passthrough(self):
        for pointer in ((0x1845, 0x5000), (0x1853, 0x6000)):
            self.assertEqual(self.invoke(pointer), pointer)
        self.assertEqual(self.open_count, 0)

    def test_repeat_backpack_reuses_cache(self):
        self.invoke()
        self.invoke()
        self.assertEqual(self.open_count, 2)

    def test_backpack_name_backpack_reload_and_ascii(self):
        self.invoke()
        self.assertEqual(self.text_at(self.invoke(name_id=0)), b'"')
        self.assertEqual(self.slot_record(0x22), self.glyph(300))
        self.invoke()
        self.assertEqual(self.slot_record(0x22), self.glyph(1303))
        self.assertEqual(self.slot_record(0x23), self.glyph(100))
        self.assertEqual(self.open_count, 5)
        self.assertEqual(self.text_at(self.invoke(name_id=1)), b"Sword")


if __name__ == "__main__":
    unittest.main()
