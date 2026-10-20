#!/usr/bin/env python3
"""Pick the DOSBox-X MIDI device that matches the game's music setting.

Run by the play launchers before DOSBox-X starts. Reads the music source the
player chose in the original sound setup (game_data/DARKSUN/SOUND.CFG) and
writes dosbox-x/zh_midi.conf:

  MT-32 (Roland LAPC-1 / MT-32) + ROMs in mt32-roms\\   -> mt32 emulation
  General MIDI + a SoundFont in soundfonts\\            -> FluidSynth
  anything else                                         -> Windows MIDI (default)

Paths are written relative to the dosbox-x folder so a package path with
Chinese characters still works. Standard library only.
"""

from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
SOUND_CFG = HERE / "game_data" / "DARKSUN" / "SOUND.CFG"
ROM_DIR = HERE / "mt32-roms"
SOUNDFONT_DIR = HERE / "soundfonts"
OUTPUT = HERE / "dosbox-x" / "zh_midi.conf"

# SOUND.CFG (59 bytes, written by SOUND_DS.EXE): the music driver name starts
# at 0x16 and the music source type is the byte at 0x32. Verified with the
# Steam setup program: 4 = General MIDI (Roland SCC-1), 3 = Roland LAPC-1 /
# MT-32, 2 = Sound Blaster FM.
DRIVER_OFFSET = 0x16
TYPE_OFFSET = 0x32
MUSIC_GM, MUSIC_MT32 = 4, 3
ROM_PAIRS = (("MT32_CONTROL.ROM", "MT32_PCM.ROM"), ("CM32L_CONTROL.ROM", "CM32L_PCM.ROM"))


def music_source(cfg: bytes) -> str:
    if len(cfg) <= TYPE_OFFSET:
        return "unknown"
    driver = cfg[DRIVER_OFFSET:DRIVER_OFFSET + 13].split(b"\0", 1)[0].lower()
    if driver != b"mt32mpu.adv":
        return "other"
    return {MUSIC_GM: "gm", MUSIC_MT32: "mt32"}.get(cfg[TYPE_OFFSET], "unknown")


def has_roms(folder: Path) -> bool:
    names = {path.name.upper() for path in folder.glob("*")} if folder.is_dir() else set()
    return any(control in names and pcm in names for control, pcm in ROM_PAIRS)


def first_soundfont(folder: Path) -> Path | None:
    if not folder.is_dir():
        return None
    fonts = sorted(path for path in folder.iterdir() if path.suffix.lower() in (".sf2", ".sf3"))
    return fonts[0] if fonts else None


def choose(source: str, roms: bool, soundfont: Path | None) -> tuple[list[str], str]:
    """Return the [midi] lines and a message for the player."""
    if source == "mt32":
        if roms:
            return ["mididevice=mt32", "mt32.romdir=..\\mt32-roms"], "音樂：MT-32 模擬"
        return ["mididevice=default"], ("音樂設定是 MT-32，但 mt32-roms 資料夾裡沒有 ROM，"
                                        "改用 Windows 內建音源播放（音色會不對）。詳見「音源設定說明.txt」。")
    if source == "gm":
        if soundfont is not None and not soundfont.name.isascii():
            return ["mididevice=default"], (f"SoundFont 檔名「{soundfont.name}」含有中文或全形字，DOSBox-X 讀不到，"
                                            "請改成英文檔名。這次先用 Windows 內建音源。")
        if soundfont is not None:
            return (["mididevice=fluidsynth", f"fluid.soundfont=..\\soundfonts\\{soundfont.name}"],
                    f"音樂：General MIDI（FluidSynth，{soundfont.name}）")
        return ["mididevice=default"], "音樂：General MIDI（Windows 內建音源）"
    return ["mididevice=default"], ""


def main() -> int:
    try:
        source = music_source(SOUND_CFG.read_bytes())
    except OSError:
        source = "unknown"
    lines, message = choose(source, has_roms(ROM_DIR), first_soundfont(SOUNDFONT_DIR))
    OUTPUT.write_text("[midi]\n" + "\n".join(lines) + "\n", encoding="ascii", errors="replace")
    if message:
        print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
