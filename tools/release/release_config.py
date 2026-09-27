"""Shared settings for the portable Chinese release package (tools/release)."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RELEASE_VERSION = "0.9.0"
RELEASE_LABEL = f"v{RELEASE_VERSION} 公測版"
RELEASE_DIR = REPO_ROOT / "dist" / f"darksun_zh_release_v{RELEASE_VERSION}"
BUILD_DIR = REPO_ROOT / "dist" / "_release_build"
TEMPLATES = Path(__file__).resolve().parent / "templates"

# The staging package every release file is diffed against (already verified in game).
STAGING = REPO_ROOT / "scratch_test" / "cjk_display_staging_v153_use_messages"
STAGING_GAME = STAGING / "GAME" / "DARKSUN"
# Dialogue package the staging was built from (the GSTR values for old saves).
GPL_PACKAGE = REPO_ROOT / "scratch_test" / "gpl_full_from_pristine_v13_creatures2" / "gpl-dialogue-patch.json"

# Original game files the patches apply to, per supported edition. Only files the
# localization changes are listed; every other file of the edition is left alone.
SOURCE_EDITIONS = {
    "steam": REPO_ROOT / "from Steam" / "games" / "Dark Sun-ENG" / "GAME" / "DARKSUN",
}
PATCHED_FILES = ("DSUN.EXE", "RESOURCE.GFF", "GPLDATA.GFF", "CINE.GFF", "SEGOBJEX.GFF")
FONT_BANKS = tuple(f"C{index}" for index in range(12))
