#!/usr/bin/env python3
"""Read-only v55 fixed-UI source and CJK layout preflight; never patches a game."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

try:
    from .cjk_localization_pipeline import encode_text, load_mapping
    from .plan_name_slot_consumers import ITEM_LINE_ADVANCE_PATCHES
except ImportError:
    from cjk_localization_pipeline import encode_text, load_mapping
    from plan_name_slot_consumers import ITEM_LINE_ADVANCE_PATCHES


ROOT = Path(__file__).resolve().parents[1]
V55_EXE = ROOT / "scratch_test/cjk_display_staging_v55_shifted_item_panel_30px/GAME/DARKSUN/DSUN.EXE"
V55_SHA256 = "c27f6f2105099a993f3b2171ef4aa47c5a739053697ca73f4bdd6c4fc7753b07"


@dataclass(frozen=True)
class FixedText:
    key: str
    offset: int
    original: str
    draft: str
    context: str


# Drafts are deliberately NOT imported into the translation catalog: the
# static-string callers do not yet have a verified CJK decode/render path.
FIXED_TEXT = (
    FixedText("backpack", 0x4A1B3, "BACKPACK", "背包", "bottom_hover"),
    FixedText("str", 0x4999B, "STR:", "力量:", "ability_labels"),
    FixedText("dex", 0x499A0, "DEX:", "敏捷:", "ability_labels"),
    FixedText("con", 0x499A5, "CON:", "體質:", "ability_labels"),
    FixedText("int", 0x499AA, "INT:", "智力:", "ability_labels"),
    FixedText("wis", 0x499AF, "WIS:", "智慧:", "ability_labels"),
    FixedText("chr", 0x499B4, "CHR:", "魅力:", "ability_labels"),
    FixedText("psi", 0x4A3AC, "%C%C%CPSI:", "%C%C%C靈能:", "psi_format"),
    FixedText("ac", 0x497C0, "AC: %2d", "防禦: %2d", "ac_format"),
    FixedText("bone", 0x4A109, "Bone", "骨製", "material_table"),
)


@dataclass(frozen=True)
class TextBlock:
    name: str
    y: int
    rows: int
    advance: int
    glyph_height: int

    @property
    def bottom(self) -> int:
        """Inclusive last painted pixel, not the next row's origin."""
        return self.y + (self.rows - 1) * self.advance + self.glyph_height - 1


V55_LAYOUT = (
    TextBlock("abilities", 23, 6, 7, 7),
    TextBlock("psi", 69, 1, 7, 7),
    TextBlock("ac", 83, 1, 7, 7),
    TextBlock("attacks", 99, 7, 10, 10),
)
# Arithmetic proposal only. Both ability LABEL and NUMBER origins/advances
# must be verified independently at runtime before building this layout.
CJK_PROPOSED_LAYOUT = (
    TextBlock("abilities", 8, 6, 10, 10),
    TextBlock("psi", 72, 1, 10, 10),
    TextBlock("ac", 84, 1, 10, 10),
    TextBlock("attacks", 99, 7, 10, 10),
)


def layout_issues(blocks: tuple[TextBlock, ...], top: int = 4, bottom: int = 173) -> list[str]:
    """Check same-column blocks against an exclusive lower frame boundary."""
    if top >= bottom:
        raise ValueError("invalid panel bounds")
    issues = []
    for block in blocks:
        if min(block.rows, block.advance, block.glyph_height) < 1:
            raise ValueError(f"{block.name}: nonpositive dimensions")
        if block.rows > 1 and block.advance < block.glyph_height:
            issues.append(f"{block.name}: glyph height exceeds row advance")
        if block.y < top or block.bottom >= bottom:
            issues.append(f"{block.name}: outside panel [{top}, {bottom})")
    for index, left in enumerate(blocks):
        for right in blocks[index + 1:]:
            if max(left.y, right.y) <= min(left.bottom, right.bottom):
                issues.append(f"{left.name}/{right.name}: block overlap")
    return issues


def verify_sources(image: bytes) -> None:
    for item in FIXED_TEXT:
        expected = item.original.encode("ascii") + b"\0"
        if image[item.offset:item.offset + len(expected)] != expected:
            raise ValueError(f"{item.key}: source mismatch at 0x{item.offset:X}")
    evidence = {
        # BACKPACK immediate argument at the inventory hover branch.
        0x6CF99: bytes.fromhex("68 53 18 EB D4"),
        # Six ability label pointers; 4356 is the on-disk segment word.
        0x49852: bytes.fromhex("3B 10 56 43 40 10 56 43 45 10 56 43 4A 10 56 43 4F 10 56 43 54 10 56 43"),
        0x40A84: bytes.fromhex("A9 17 56 43"),
    }
    evidence.update({offset: pair[1] for offset, pair in ITEM_LINE_ADVANCE_PATCHES.items()})
    for offset, expected in evidence.items():
        if image[offset:offset + len(expected)] != expected:
            raise ValueError(f"v55 evidence mismatch at 0x{offset:X}")


def text_preflight(item: FixedText, mapping: dict[str, object]) -> dict[str, object]:
    # Printable Base94 uses three bytes per CJK character, PLUS the terminator.
    required = 1 + sum(1 if ord(char) < 128 else 3 for char in item.draft)
    capacity = len(item.original.encode("ascii")) + 1
    try:
        encoded = encode_text(item.draft, mapping)
        encoding_error = None
    except ValueError as error:
        encoded = None
        encoding_error = str(error)
    return {
        "key": item.key,
        "file_offset": f"0x{item.offset:05X}",
        "source": item.original,
        "draft_zh_tw": item.draft,
        "context": item.context,
        "capacity_with_nul": capacity,
        "base94_bytes_with_nul": required,
        "fits_original_storage": required <= capacity,
        "encoded_hex": encoded.hex() if encoded is not None else None,
        "encoding_error": encoding_error,
        "runtime_decoder_verified": False,
        "ready_to_patch": False,
    }


def build_report(image: bytes, mapping: dict[str, object]) -> dict[str, object]:
    digest = hashlib.sha256(image).hexdigest()
    if digest != V55_SHA256:
        raise ValueError("DSUN.EXE is not the accepted v55 baseline")
    verify_sources(image)
    return {
        "status": "read_only_preflight_not_a_translated_build",
        "exe_sha256": digest,
        "text": [text_preflight(item, mapping) for item in FIXED_TEXT],
        "layout": {
            "coordinates": "native game pixels; lower boundary 173 is screenshot-derived",
            "v55_issues": layout_issues(V55_LAYOUT),
            "proposed_cjk_issues": layout_issues(CJK_PROPOSED_LAYOUT),
            "proposed_cjk_blocks": [dict(name=b.name, y=b.y, rows=b.rows, advance=b.advance,
                                          glyph_height=b.glyph_height, bottom=b.bottom)
                                    for b in CJK_PROPOSED_LAYOUT],
            "runtime_verified": False,
            "horizontal_fit_verified": False,
        },
        "excluded": {
            "DROP@0x4A516": "character-removal menu; not proven inventory drop button",
            "SPLIT": "no ASCII match in EXE; resource/render source unresolved",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, default=V55_EXE)
    parser.add_argument("--mapping", type=Path, default=ROOT / "localization/cjk_mapping.json")
    args = parser.parse_args()
    print(json.dumps(build_report(args.exe.read_bytes(), load_mapping(args.mapping)),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
