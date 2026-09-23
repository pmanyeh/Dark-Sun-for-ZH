from pathlib import Path

import pytest

from tools.patch_dialogue_menu_wind import (
    CHOICE_RESTORE_CAVE,
    CHOICE_RESTORE_TEMPLATE,
    CHOICE_SET_TEXT,
    patch_dialogue_choice_paging,
)
from tools.patch_dsun_scratch_cache import mz_relocation_file_offsets

EXE = Path("from Steam/games/Dark Sun-ENG/GAME/DARKSUN/DSUN.EXE")


@pytest.mark.skipif(not EXE.is_file(), reason="original DSUN.EXE is not in this checkout")
def test_choice_restore_is_relocation_safe() -> None:
    patched = patch_dialogue_choice_paging(EXE.read_bytes())
    assert patched[CHOICE_SET_TEXT:CHOICE_SET_TEXT + 7] == bytes.fromhex("9A1697862EEB00")
    hook = (Path("tools/dialogue_choice_top_rows_hook.bin")).read_bytes()
    panel = (Path("tools/dialogue_choice_top_rows.bin")).read_bytes()
    assert patched[CHOICE_RESTORE_CAVE:CHOICE_RESTORE_CAVE + len(hook)] == hook
    assert patched[CHOICE_RESTORE_TEMPLATE:CHOICE_RESTORE_TEMPLATE + len(panel)] == panel
    return_site = CHOICE_RESTORE_CAVE + hook.rindex(bytes.fromhex("EA01081D2A")) + 3
    assert {CHOICE_SET_TEXT + 3, return_site} <= mz_relocation_file_offsets(patched)
