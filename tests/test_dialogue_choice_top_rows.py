from pathlib import Path

import pytest

from tools.patch_dialogue_menu_wind import (
    CHOICE_RESTORE_CAVE,
    CHOICE_RESTORE_IP,
    CHOICE_RESTORE_LIMIT,
    CHOICE_RETURN_JUMP,
    CHOICE_SET_TEXT,
    assemble_choice_restore,
    patch_dialogue_choice_paging,
)
from tools.patch_dsun_scratch_cache import mz_relocation_file_offsets

EXE = Path("from Steam/games/Dark Sun-ENG/GAME/DARKSUN/DSUN.EXE")
PANEL = Path("tools/dialogue_choice_top_rows.bin")


def _stamped_rows(hook: bytes) -> list[bytes]:
    """Replay the hook's per-plane decode and return row 0 and row 1 per plane."""
    source = hook[hook.index(CHOICE_RETURN_JUMP) + len(CHOICE_RETURN_JUMP):]
    rows = []
    for plane in range(4):
        record = source[plane * 20:(plane + 1) * 20]
        values = [((byte >> (bit * 2)) & 3) + 0x18 for byte in record[:19] for bit in range(4)]
        values[0] = record[19]
        rows.append(bytes(values))
    return rows


def test_hook_stamps_the_verified_panel_row() -> None:
    hook = assemble_choice_restore()
    panel = PANEL.read_bytes()
    assert CHOICE_RESTORE_IP + len(hook) <= CHOICE_RESTORE_LIMIT
    rows = _stamped_rows(hook)
    for plane in range(4):
        assert rows[plane] == panel[plane * 76:(plane + 1) * 76]
        assert rows[plane] == panel[(4 + plane) * 76:(5 + plane) * 76]


@pytest.mark.skipif(not EXE.is_file(), reason="original DSUN.EXE is not in this checkout")
def test_choice_restore_is_relocation_safe() -> None:
    original = EXE.read_bytes()
    patched = patch_dialogue_choice_paging(original)
    assert patched[CHOICE_SET_TEXT:CHOICE_SET_TEXT + 7] == bytes.fromhex("9A10007D14EB00")
    hook = assemble_choice_restore()
    assert not any(original[CHOICE_RESTORE_CAVE:CHOICE_RESTORE_CAVE + len(hook)])
    assert patched[CHOICE_RESTORE_CAVE:CHOICE_RESTORE_CAVE + len(hook)] == hook
    return_site = CHOICE_RESTORE_CAVE + hook.index(CHOICE_RETURN_JUMP) + 3
    relocations = mz_relocation_file_offsets(patched)
    assert {CHOICE_SET_TEXT + 3, return_site} <= relocations
    assert relocations - mz_relocation_file_offsets(original) == {CHOICE_SET_TEXT + 3, return_site}
