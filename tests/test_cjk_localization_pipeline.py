from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

from tools.cjk_localization_pipeline import (
    BANK_HEADER,
    BANK_MAGIC,
    TRIPLE_CAPACITY,
    TRIPLE_RESERVED_ID,
    build_bank,
    compile_gff_text_replacements,
    encode_text,
    eten_rasterizer,
    eten_slot,
    glyph_record_for_id,
    insert_spin_title_newline,
    make_inventory,
    mapping_fingerprint,
    read_bank,
    rasterizer,
    sha256,
    transport_for_id,
    update_mapping,
    verify_extracted_gff_chunks,
)


class CjkLocalizationPipelineTests(unittest.TestCase):
    def test_inventory_keeps_visible_non_ascii_only(self) -> None:
        self.assertEqual(make_inventory(["中A文\n中　"]), {"中": 2, "文": 1})

    def test_mapping_is_append_only(self) -> None:
        original = {
            "format": "darksun-cjk-map",
            "version": 1,
            "entries": [{"id": 7, "character": "文"}],
        }
        updated = update_mapping(original, make_inventory(["中文"]), [])
        by_character = {entry["character"]: entry["id"] for entry in updated["entries"]}
        self.assertEqual(by_character, {"文": 7, "中": 8})

    def test_printable_triples_are_unique_and_ascii_safe(self) -> None:
        ids = [value for value in range(94 * 94) if value != TRIPLE_RESERVED_ID]
        triples = {transport_for_id(value) for value in ids}
        self.assertEqual(len(triples), TRIPLE_CAPACITY)
        for value in triples:
            self.assertEqual(value[:1], b"^")
            self.assertTrue(all(0x21 <= byte <= 0x7E for byte in value[1:]))
        self.assertNotIn(b"^^^", triples)

    def test_bank_uses_u16_relative_records(self) -> None:
        entries = [{"id": 0, "index": 0, "character": "中"}, {"id": 1, "index": 1, "character": "文"}]

        def render(_character: str) -> tuple[int, bytes]:
            return 2, bytes(2 * 3)

        payload = build_bank(0, entries, 3, render)
        magic, version, bank_id, height, count, directory = BANK_HEADER.unpack_from(payload)
        self.assertEqual((magic, version, bank_id, height, count), (BANK_MAGIC, 1, 0, 3, 2))
        first_index, first_offset = struct.unpack_from("<HH", payload, directory)
        self.assertEqual((first_index, first_offset), (0, BANK_HEADER.size + 8))
        self.assertEqual(struct.unpack_from("<H", payload, first_offset)[0], 2)

    def test_encode_text_preserves_engine_ascii_and_encodes_boundaries(self) -> None:
        mapping = {
            "entries": [
                {"id": 255, "character": "中"},
                {"id": 256, "character": "文"},
            ]
        }
        self.assertEqual(encode_text("中%S\t文\n", mapping), b"^#d%S\t^#e\n")

    def test_encode_text_rejects_reserved_and_unmapped_input(self) -> None:
        mapping = {"entries": []}
        with self.assertRaisesRegex(ValueError, "literal"):
            encode_text("a^b", mapping)
        with self.assertRaisesRegex(ValueError, "NUL"):
            encode_text("a\0b", mapping)
        with self.assertRaisesRegex(ValueError, "U\\+4E2D"):
            encode_text("中", mapping)

    def test_compile_gff_text_preserves_crlf_and_expands_locations(self) -> None:
        mapping = {"entries": [{"id": 0, "character": "中"}]}
        manifest = {
            "units": [
                {
                    "unit_id": "LOC_test",
                    "category": "spin",
                    "original": "Test",
                    "translation_zh_tw": "中!",
                    "locations": [
                        {"container": "RESOURCE.GFF", "kind": "SPIN", "chunk_id": 1, "length": 6, "terminator": "CRLF"},
                        {"container": "RESOURCE.GFF", "kind": "SPIN", "chunk_id": 7, "length": 6, "terminator": "CRLF"},
                    ],
                },
                {
                    "unit_id": "LOC_name",
                    "category": "name",
                    "original": "Sling",
                    "translation_zh_tw": "中",
                    "locations": [{"container": "GPLDATA.GFF", "kind": "NAME", "chunk_id": 1, "chunk_offset": 0, "length": 5}],
                },
            ]
        }
        replacements, records, skipped = compile_gff_text_replacements(manifest, mapping)
        self.assertEqual(replacements[("RESOURCE.GFF", "SPIN", 1)], b"^!!\x21\r\n")
        self.assertEqual(len(records), 2)
        self.assertEqual(skipped, {"name": 1})

    def test_compile_gff_text_can_put_description_after_title(self) -> None:
        mapping = {
            "entries": [
                {"id": 0, "character": "："},
                {"id": 1, "character": "中"},
            ]
        }
        manifest = {
            "units": [{
                "unit_id": "LOC_spell",
                "category": "spin",
                "original": "A: B",
                "translation_zh_tw": "A：中",
                "locations": [{
                    "container": "RESOURCE.GFF",
                    "kind": "SPIN",
                    "chunk_id": 1,
                    "length": 6,
                    "terminator": "CRLF",
                }],
            }]
        }
        replacements, records, _ = compile_gff_text_replacements(
            manifest, mapping, title_newline=True
        )
        self.assertEqual(insert_spin_title_newline("A： 中"), "A：\r\n中")
        self.assertEqual(replacements[("RESOURCE.GFF", "SPIN", 1)], b"A^!!\r\n^!\x22\r\n")
        self.assertTrue(records[0]["title_newline"])

    def test_compile_gff_text_rejects_embedded_spin_location(self) -> None:
        manifest = {
            "units": [{
                "unit_id": "LOC_bad", "category": "spin", "original": "A", "translation_zh_tw": "B",
                "locations": [{"container": "R.GFF", "kind": "SPIN", "chunk_id": 1, "chunk_offset": 0, "length": 3, "terminator": "CRLF"}],
            }]
        }
        with self.assertRaisesRegex(ValueError, "not a supported whole chunk"):
            compile_gff_text_replacements(manifest, {"entries": []})

    def test_extracted_gff_verifier_allows_only_targets_and_gffi(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original, patched = root / "original", root / "patched"
            original.mkdir()
            patched.mkdir()
            for directory, spin, gffi in ((original, b"old", b"index-a"), (patched, b"new", b"index-b")):
                (directory / "SPIN-1.bin").write_bytes(spin)
                (directory / "DATA-2.bin").write_bytes(b"same")
                (directory / "GFFI-1.bin").write_bytes(gffi)
            result = verify_extracted_gff_chunks(
                original,
                patched,
                [{"kind": "SPIN", "chunk_id": 1, "sha256": sha256(b"new"), "encoded_byte_length": 3}],
            )
            self.assertEqual(result["target_chunks"], 1)
            self.assertEqual(result["changed_target_chunks"], 1)
            self.assertEqual(result["unchanged_non_target_chunks"], 1)

    def test_extracted_gff_verifier_accepts_explicit_container_index(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            original, patched = root / "original", root / "patched"
            original.mkdir()
            patched.mkdir()
            for directory, spin, gffi in (
                (original, b"old", b"index-a"),
                (patched, b"new", b"index-b"),
            ):
                (directory / "GPL-2.bin").write_bytes(spin)
                (directory / "GFFI-8.bin").write_bytes(gffi)
            result = verify_extracted_gff_chunks(
                original,
                patched,
                [{"kind": "GPL", "chunk_id": 2, "sha256": sha256(b"new"), "encoded_byte_length": 3}],
                {"GFFI-8.bin"},
            )
            self.assertEqual(result["allowed_container_metadata"], ["GFFI-8.bin"])

    def test_built_bank_round_trips_through_loader_contract(self) -> None:
        entries = [{"id": 256, "index": 0, "character": "示"}]

        def render(_character: str) -> tuple[int, bytes]:
            return 2, bytes(range(6))

        payload = build_bank(1, entries, 3, render)
        banks = {1: read_bank(payload, expected_bank=1)}
        self.assertEqual(glyph_record_for_id(256, banks), b"\x02\x00\x00\x01\x02\x03\x04\x05")
        with self.assertRaisesRegex(ValueError, "missing CJK ID 257"):
            glyph_record_for_id(257, banks)

    def test_bank_reader_rejects_truncated_record(self) -> None:
        entries = [{"id": 0, "index": 0, "character": "中"}]
        payload = build_bank(0, entries, 3, lambda _character: (2, bytes(6)))
        with self.assertRaisesRegex(ValueError, "invalid size"):
            read_bank(payload[:-1])

    def test_mapping_fingerprint_ignores_metadata_but_not_identity(self) -> None:
        first = {"format": "darksun-cjk-map", "version": 1, "status": "old", "entries": [{"id": 0, "character": "中"}]}
        second = {**first, "status": "new"}
        self.assertEqual(mapping_fingerprint(first), mapping_fingerprint(second))
        second["entries"] = [{"id": 0, "character": "文"}]
        self.assertNotEqual(mapping_fingerprint(first), mapping_fingerprint(second))

    def test_formal_bank_records_fit_one_scratch_slot(self) -> None:
        package_path = Path("scratch_test/formal_cjk_pipeline/cjk-bank-set.json")
        if not package_path.exists():
            self.skipTest("formal generated bank set is not present")
        import json

        package = json.loads(package_path.read_text(encoding="utf-8"))
        banks = {}
        for item in package["banks"]:
            payload = (package_path.parent / item["file"]).read_bytes()
            banks[item["bank"]] = read_bank(payload, item["bank"])
        sizes = {len(record) for bank in banks.values() for record in bank["records"].values()}
        self.assertEqual(sizes, {242})
        self.assertNotEqual(glyph_record_for_id(255, banks), glyph_record_for_id(256, banks))

    def test_scratch_resolver_calls_resident_cache(self) -> None:
        from tools.patch_dsun_scratch_cache import (
            CACHE,
            CACHE_RUNTIME_LIMIT,
            CODE_BASE,
            CJK_HEIGHT_HELPER,
            COMMON,
            EBOX_ADVANCE_HELPER,
            EBOX_NEXT_PAGE_DELTA_FILE_OFFSETS,
            EBOX_STORE_LINE_HEIGHT,
            GLYPH_HEIGHT_LOAD,
            ITEM_FORMAT_LOOP,
            ITEM_FORMAT_POST_HELPER,
            ITEM_FORMAT_POST_HELPER_ALIAS,
            ITEM_FORMAT_WRAPPER,
            ITEM_TEXT_FILE_BASE,
            EBOX_LAYOUT_LOCALS,
            NAMES,
            assemble_cache,
            cjk_height_helper,
            ebox_cjk_width_body,
            item_format_loop,
            item_format_post_helper,
            item_format_wrapper,
            ebox_page_step,
            ebox_store_line_height,
            ebox_layout_advance_call,
            ebox_layout_locals_and_helper,
            glyph_height_call,
            mz_relocation_file_offsets,
            patch_executable,
            patches,
            resolver,
        )

        payload = resolver()
        call = payload.index(b"\xE8")
        displacement = struct.unpack_from("<h", payload, call + 1)[0]
        self.assertEqual(COMMON + call + 3 + displacement, CACHE)
        self.assertIn(b"\x3D\xA3\x16", payload)  # reserved ID 5795
        small = assemble_cache(0x206B, 92)
        self.assertIn(b"\x81\xC7\x6B\x20", small)  # add di, scratch offset
        self.assertIn(b"\xB9\x5C\x00", small)  # mov cx, fixed record bytes
        self.assertIn(b"\x83\xF8\x5C", small)  # cmp ax, fixed record bytes
        self.assertEqual(CACHE + len(small), CACHE_RUNTIME_LIMIT)
        self.assertEqual(len(ebox_cjk_width_body()), 0x023A - 0x0214)
        self.assertEqual(len(item_format_wrapper()), 4)
        self.assertEqual(len(item_format_post_helper()), 21)
        self.assertIn(bytes.fromhex("01 46 F2"), item_format_post_helper())
        self.assertNotIn(bytes.fromhex("00 46 F2"), item_format_post_helper())
        self.assertEqual(len(item_format_loop()), 0x0306 - 0x02EB)
        self.assertIn(bytes.fromhex("50 30 E4 50 9A C1 59 80 09 59 58"), item_format_loop())
        post_call = item_format_loop().index(b"\xE8")
        post_displacement = struct.unpack_from("<h", item_format_loop(), post_call + 1)[0]
        self.assertEqual(
            ITEM_FORMAT_LOOP + post_call + 3 + post_displacement,
            ITEM_FORMAT_POST_HELPER_ALIAS,
        )
        layout = ebox_layout_locals_and_helper()
        self.assertEqual(len(layout), 0x0297 - EBOX_LAYOUT_LOCALS)
        self.assertEqual(
            EBOX_LAYOUT_LOCALS + layout.index(bytes.fromhex("80 7E F6 5E")),
            EBOX_ADVANCE_HELPER,
        )
        call = ebox_layout_advance_call()
        displacement = struct.unpack_from("<h", call, 1)[0]
        self.assertEqual(0x04A6 + 3 + displacement, EBOX_ADVANCE_HELPER)
        self.assertEqual(len(ebox_store_line_height(2)), 11)
        self.assertEqual(ebox_store_line_height(2)[:2], b"\x41\x41")
        self.assertEqual(ebox_page_step(0), 5)
        self.assertEqual(ebox_page_step(2), 3)
        self.assertEqual(len(cjk_height_helper(10)), 11)
        self.assertIn(bytes.fromhex("80 7E 06 7F 75 01 40"), cjk_height_helper(10))
        height_call = glyph_height_call()
        height_displacement = struct.unpack_from("<h", height_call, 1)[0]
        self.assertEqual(GLYPH_HEIGHT_LOAD + 3 + height_displacement, CJK_HEIGHT_HELPER)
        source = Path(r"from Steam/games/Dark Sun-ENG/GAME/DARKSUN/DSUN.EXE").read_bytes()
        relocations = mz_relocation_file_offsets(source)
        self.assertNotIn(0x31390 + 0x0214, relocations)
        self.assertIn(0x31390 + 0x0212, relocations)  # preserved stack-check segment
        self.assertNotIn(0x31390 + EBOX_STORE_LINE_HEIGHT, relocations)
        line_gap_exe, _ = patch_executable(source, 0x206B, 92, line_gap=2)
        self.assertEqual(
            line_gap_exe[
                0x31390 + EBOX_STORE_LINE_HEIGHT : 0x31390 + EBOX_STORE_LINE_HEIGHT + 11
            ],
            ebox_store_line_height(2),
        )
        for offset in EBOX_NEXT_PAGE_DELTA_FILE_OFFSETS:
            self.assertEqual(line_gap_exe[offset : offset + 5], bytes.fromhex("6A FD 90 90 90"))
        menu_gap_exe, _ = patch_executable(
            source, 0x206B, 92, line_gap=2, menu_line_gap=5
        )
        self.assertEqual(menu_gap_exe[0x2C716 : 0x2C719], bytes.fromhex("05 05 00"))
        self.assertEqual(
            [offset for offset, (before, after) in enumerate(zip(line_gap_exe, menu_gap_exe)) if before != after],
            [0x2C717],
        )
        with self.assertRaisesRegex(ValueError, "menu layout line gap"):
            patch_executable(source, 0x206B, 92, menu_line_gap=1)
        # The four original SI=5 assignments remain byte-identical because SI
        # is shared with the control feedback path.
        for offset in (0x7CD58, 0x7CD8F, 0x7DABA, 0x7DB76):
            self.assertEqual(line_gap_exe[offset : offset + 3], bytes.fromhex("BE 05 00"))
        ten_row_exe, ten_row_cache = patch_executable(
            source, 0x206B, 102, line_gap=2, cjk_draw_height=10
        )
        self.assertEqual(len(ten_row_cache), len(small))
        self.assertEqual(
            ten_row_exe[CODE_BASE + CJK_HEIGHT_HELPER : CODE_BASE + CJK_HEIGHT_HELPER + 11],
            cjk_height_helper(10),
        )
        self.assertEqual(
            ten_row_exe[CODE_BASE + GLYPH_HEIGHT_LOAD : CODE_BASE + GLYPH_HEIGHT_LOAD + 11],
            glyph_height_call(),
        )
        # A vocabulary that outgrows four 256-glyph banks needs a fifth
        # CJB1 bank; the resident cache's bank-name table must grow to match
        # without colliding with the cache code that follows it.
        five_bank_names = patches(small, bank_count=5)[CODE_BASE + NAMES][1]
        self.assertEqual(
            five_bank_names,
            b"".join(
                struct.pack("<H", NAMES + 5 * 2 + bank * 3) for bank in range(5)
            )
            + b"C0\0C1\0C2\0C3\0C4\0",
        )
        self.assertLessEqual(NAMES + len(five_bank_names), ITEM_FORMAT_WRAPPER)
        five_bank_exe, five_bank_cache = patch_executable(
            source,
            0x206B,
            102,
            line_gap=2,
            cjk_draw_height=10,
            bank_count=5,
            experimental_item_text_fix=True,
        )
        # Same code size; only the embedded bank-count bound (cmp al, N) differs.
        self.assertEqual(len(five_bank_cache), len(ten_row_cache))
        differing = [i for i in range(len(five_bank_cache)) if five_bank_cache[i] != ten_row_cache[i]]
        self.assertEqual(len(differing), 1)
        self.assertEqual(ten_row_cache[differing[0]], 4)
        self.assertEqual(five_bank_cache[differing[0]], 5)
        self.assertEqual(
            five_bank_exe[CODE_BASE + NAMES : CODE_BASE + NAMES + len(five_bank_names)],
            five_bank_names,
        )
        self.assertEqual(
            five_bank_exe[
                CODE_BASE + ITEM_FORMAT_POST_HELPER :
                CODE_BASE + ITEM_FORMAT_POST_HELPER + len(item_format_post_helper())
            ],
            item_format_post_helper(),
        )
        five_bank_relocations = mz_relocation_file_offsets(five_bank_exe)
        self.assertNotIn(ITEM_TEXT_FILE_BASE + 0x02F3, five_bank_relocations)
        self.assertIn(ITEM_TEXT_FILE_BASE + 0x02EE, five_bank_relocations)
        self.assertIn(ITEM_TEXT_FILE_BASE + 0x02F7, five_bank_relocations)
        with self.assertRaisesRegex(ValueError, "1..16"):
            patches(small, bank_count=17)
        with self.assertRaisesRegex(ValueError, "1..16"):
            patches(small, bank_count=0)

    def test_bank_names_beyond_eight_move_to_the_147d_cave(self) -> None:
        from tools.patch_dsun_scratch_cache import (
            BANK_NAMES_CAVE_FILE_OFFSET,
            BANK_NAMES_CAVE_LIMIT,
            BANK_NAMES_CAVE_SEGMENT,
            BANK_NAMES_CAVE_TABLE,
            CACHE,
            CACHE_RUNTIME_LIMIT,
            CODE_BASE,
            NAMES,
            mz_relocation_file_offsets,
            patch_executable,
            patches,
        )

        source = Path(r"from Steam/games/Dark Sun-ENG/GAME/DARKSUN/DSUN.EXE").read_bytes()
        exe, cache = patch_executable(source, 0x3640, 242, bank_count=12)
        # The resident cache must still fit exactly inside its fixed
        # 0x5534 boundary (bytes at and beyond it are a runtime work area
        # the spell UI overwrites) -- the >8-bank branch must cost no more
        # than the inline table it replaces.
        self.assertEqual(CACHE + len(cache), CACHE_RUNTIME_LIMIT)
        self.assertNotIn(CODE_BASE + NAMES, patches(cache, bank_count=12))
        twelve_bank_names = struct.pack(
            "<12H",
            *(BANK_NAMES_CAVE_TABLE + 12 * 2 + sum(len(f"C{b}\0") for b in range(bank)) for bank in range(12)),
        ) + b"".join(f"C{bank}\0".encode("ascii") for bank in range(12))
        self.assertLessEqual(BANK_NAMES_CAVE_TABLE + len(twelve_bank_names), BANK_NAMES_CAVE_LIMIT)
        self.assertEqual(
            exe[BANK_NAMES_CAVE_FILE_OFFSET : BANK_NAMES_CAVE_FILE_OFFSET + len(twelve_bank_names)],
            twelve_bank_names,
        )
        # The cache's cache_open routine loads DS from a literal segment
        # word before reading the table; that word must be in the MZ
        # relocation table so the loader biases it like every other far
        # reference in this module.
        marker = bytes([0x68]) + BANK_NAMES_CAVE_SEGMENT.to_bytes(2, "little")
        self.assertEqual(cache.count(marker), 1)
        relocation = CODE_BASE + CACHE + cache.index(marker) + 1
        self.assertIn(relocation, mz_relocation_file_offsets(exe))
        self.assertNotIn(relocation, mz_relocation_file_offsets(source))
        with self.assertRaisesRegex(ValueError, "beyond the verified-dead limit"):
            patches(cache, bank_count=16)

    def test_pixel_aligned_rasterizer_keeps_fixed_record_size(self) -> None:
        font = Path(r"C:\Windows\Fonts\NotoSansTC-VF.ttf")
        if not font.exists():
            self.skipTest("Noto Sans TC test font is not installed")
        render = rasterizer(font, 15, 15, 15, 16, 64, "pixel-aligned")
        width, pixels = render(chr(0x5F92))
        self.assertEqual((width, len(pixels)), (16, 240))
        self.assertGreater(pixels.count(0xFE), 20)

    def test_item_format_v35_instruction_contract(self) -> None:
        from tools.patch_dsun_scratch_cache import (
            ITEM_FORMAT_LOOP,
            ITEM_FORMAT_POST_HELPER_ALIAS,
            item_format_loop,
            item_format_post_helper,
            item_format_wrapper,
        )

        # Far resolver returns AX=00xx for ASCII or AX=017F for CJK.  The loop
        # saves that complete value, clears AH only in FONT's argument copy,
        # then restores the original AX for the post-render helper.
        loop = item_format_loop()
        self.assertEqual(loop[:16], bytes.fromhex(
            "9A 14 54 86 2E 50 30 E4 50 9A C1 59 80 09 59 58"
        ))
        self.assertEqual(loop.count(b"\x50"), 2)  # push AX twice
        self.assertEqual(loop[14:16], b"\x59\x58")  # pop glyph, pop flag
        self.assertEqual(item_format_wrapper()[-1], 0xCB)  # retf

        call_position = 16
        self.assertEqual(loop[call_position], 0xE8)
        displacement = struct.unpack_from("<h", loop, call_position + 1)[0]
        self.assertEqual(
            ITEM_FORMAT_LOOP + call_position + 3 + displacement,
            ITEM_FORMAT_POST_HELPER_ALIAS,
        )
        self.assertEqual(loop[19:23], bytes.fromhex("75 EB EB 6A"))

        helper = item_format_post_helper()
        self.assertEqual(helper, bytes.fromhex(
            "03 F7 8A C4 D0 E0 FE C0 30 E4 01 46 F2 "
            "C4 5E F2 26 80 3F 00 C3"
        ))

        # Model the exact MOV/SHL/INC/XOR/ADD sequence above.  These boundary
        # cases distinguish v35's word addition from v34's rejected byte add.
        def advance(offset: int, returned_ax: int) -> int:
            al = (returned_ax >> 8) & 0xFF  # mov al,ah
            al = ((al << 1) + 1) & 0xFF    # shl al,1; inc al
            ax = al                         # xor ah,ah
            return (offset + ax) & 0xFFFF  # add word [bp-0E],ax

        self.assertEqual(advance(0x00FF, 0x0041), 0x0100)
        self.assertEqual(advance(0x00FE, 0x017F), 0x0101)
        self.assertEqual(advance(0xFFFE, 0x017F), 0x0001)

    def test_ttf_rasterizer_can_disable_drop_shadow(self) -> None:
        font = Path("Fonts/Fusion_Pixel_10px.ttf")
        with_shadow = rasterizer(font, 10, 10, 9, 10, 64, "pixel-aligned", True)
        without_shadow = rasterizer(font, 10, 10, 9, 10, 64, "pixel-aligned", False)
        _, shadowed = with_shadow("今")
        _, plain = without_shadow("今")
        self.assertIn(0x14, shadowed)
        self.assertNotIn(0x14, plain)
        self.assertEqual(shadowed.count(0xFE), plain.count(0xFE))

    def test_ttf_rasterizer_can_clamp_last_row_shadow(self) -> None:
        font = Path("Fonts/Fusion_Pixel_10px.ttf")
        regular = rasterizer(font, 10, 10, 9, 10, 64, "pixel-aligned", True, False)
        clamped = rasterizer(font, 10, 10, 9, 10, 64, "pixel-aligned", True, True)
        _, regular_pixels = regular("今")
        _, clamped_pixels = clamped("今")
        self.assertEqual(regular_pixels.count(0xFE), clamped_pixels.count(0xFE))
        self.assertGreater(clamped_pixels[-10:].count(0x14), regular_pixels[-10:].count(0x14))

    def test_eten_big5_partition_oracles(self) -> None:
        self.assertEqual(eten_slot(chr(0x3002)), ("spc", 3))  # 。 A143
        self.assertEqual(eten_slot(chr(0x4E00)), ("std", 0))  # 一 A440
        self.assertEqual(eten_slot(chr(0x4E2D)), ("std", 66))  # 中 A4A4

    def test_eten_rasterizer_reads_native_16x15_bits(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            std = bytearray(13094 * 30)
            spc = bytearray(408 * 30)
            std[0] = 0x80
            spc[3 * 30 + 29] = 0x01
            (directory / "STDFONT.15").write_bytes(std)
            (directory / "SPCFONT.15").write_bytes(spc)
            render = eten_rasterizer(directory / "STDFONT.15", directory / "SPCFONT.15", 16, False)
            width, one = render(chr(0x4E00))
            _, stop = render(chr(0x3002))
            self.assertEqual((width, len(one), one[0]), (16, 240, 0xFE))
            self.assertEqual(stop[-1], 0xFE)


if __name__ == "__main__":
    unittest.main()
