# OpenDS extraction results

OpenDS revision `5f902cf89853e5750572aaaa7499097e2ebd3617` was tested against the Steam copy of *Dark Sun: Shattered Lands* in this workspace.

Verified results:

- `GPLDATA.GFF`: 217 `GPL ` chunks and 33 `MAS ` chunks.
- Dialog-bearing chunks: 215.
- Extracted strings: 17,699.
- Disassembly alignment failures: 0.
- LSTR reads: 255 total; 230 exact, 25 with possible writers, 0 without writers.
- `GPL-1` survives `gpl-disasm -> gpl-asm` byte-identically (5,265 bytes; SHA-256 `B50AD166F760CE4A9EA5688EAC3653BB76352CD96C60C72FDE88C60585B26484`).

Run the extraction again from the project root:

```powershell
.\tools\extract_opends_dialog.ps1
```

This creates `ds1-dialog.txt` and `ds1-dialog.json` in this directory. Both outputs are intentionally ignored by Git because they are reproducible extracts containing commercial game text. The original game files are also ignored and are never modified by this command.
