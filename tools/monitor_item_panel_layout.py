#!/usr/bin/env python3
"""Capture one burst of item-panel text layout calls from DOSBox-X.

The monitor is intentionally narrow: it observes the shared object-text
wrapper at 2143:0A40 and its formatter return at 2143:0A6A.  It never writes
guest memory or injects input.  Its own breakpoints are removed on success,
timeout, or interruption, and a guest stopped by the monitor is resumed.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


DEFAULT_CLIENT_DIR = Path(r"D:\git\DOSBox-X-AI\ai")
ENTRY = "2143:0A40"
RETURN = "2143:0A6A"
BREAKPOINTS = {ENTRY, RETURN}
RIGHT_PANEL_CALLER_OFFSETS = {
    # Main inventory panel: compact attack summary and item name/value rows.
    0x2A85,
    0x2B9C,
    0x2CD4,
    # Alternate item-detail overlay mapped in re_64.
    0x0E7A,
    0x0F99,
    0x1057,
    0x1121,
    0x1194,
    0x1212,
    0x12BE,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--quiet", type=float, default=0.75)
    parser.add_argument("--max-events", type=int, default=200)
    parser.add_argument("--poll", type=float, default=0.01)
    parser.add_argument("--client-dir", type=Path, default=DEFAULT_CLIENT_DIR)
    parser.add_argument(
        "--all-callers",
        action="store_true",
        help="include non-right-panel object-text calls",
    )
    return parser.parse_args()


def word(raw: list[str], index: int = 0) -> int:
    return int(raw[index], 16) | (int(raw[index + 1], 16) << 8)


def emit(kind: str, **fields: object) -> None:
    print(json.dumps({"kind": kind, **fields}, ensure_ascii=False), flush=True)


def delete_own_breakpoints(client: object) -> None:
    while True:
        own = [
            item
            for item in client.list_breakpoints()
            if str(item.get("address", "")).upper() in BREAKPOINTS
        ]
        if not own:
            return
        client.delete_breakpoint(int(own[0]["id"]))


def read_text(client: object, segment: int, offset: int) -> list[str]:
    try:
        return client.read_memory(f"{segment:04X}:{offset:04X}", 32)["bytes"]
    except Exception:
        return []


def inspect_entry(client: object, status: dict[str, object]) -> dict[str, object]:
    segments = status["segments"]
    registers = status["registers"]
    ss = str(segments["ss"])
    sp = int(str(registers["esp"])[-4:], 16)
    raw = client.read_memory(f"{ss}:{sp:04X}", 22)["bytes"]
    text_offset = word(raw, 8)
    text_segment = word(raw, 10)
    return {
        "at": "entry",
        "caller": f"{word(raw, 2):04X}:{word(raw, 0):04X}",
        "x": word(raw, 12),
        "y": word(raw, 14),
        "bound_1": word(raw, 16),
        "bound_2": word(raw, 18),
        "text_pointer": f"{text_segment:04X}:{text_offset:04X}",
        "text_hex": " ".join(read_text(client, text_segment, text_offset)),
    }


def inspect_return(client: object, status: dict[str, object]) -> dict[str, object]:
    segments = status["segments"]
    registers = status["registers"]
    ss = str(segments["ss"])
    bp = int(str(registers["ebp"])[-4:], 16)
    raw = client.read_memory(f"{ss}:{bp:04X}", 24)["bytes"]
    return {
        "at": "return",
        "x": word(raw, 14),
        "y": word(raw, 16),
        "bound_1": word(raw, 18),
        "bound_2": word(raw, 20),
        "ax": int(str(registers["eax"])[-4:], 16),
    }


def main() -> int:
    args = parse_args()
    sys.path.insert(0, str(args.client_dir))
    from dosbox_client import DOSBoxBreakpointAlreadyExists, DOSBoxClient

    client = DOSBoxClient(request_timeout=15.0)
    if client.get_debug_status().get("stopped"):
        emit("refused", reason="debugger_already_stopped")
        return 2

    armed = False
    try:
        client.pause_execution()
        try:
            for address in (ENTRY, RETURN):
                try:
                    client.set_breakpoint(address)
                except DOSBoxBreakpointAlreadyExists:
                    pass
            armed = True
        finally:
            client.continue_execution()
        emit("armed", breakpoints=sorted(BREAKPOINTS))

        deadline = time.monotonic() + args.timeout
        last_hit: float | None = None
        events: list[dict[str, object]] = []
        keep_return = False
        skipped_entries = 0
        while time.monotonic() < deadline and len(events) < args.max_events:
            time.sleep(args.poll)
            status = client.get_debug_status()
            if not status.get("stopped"):
                if last_hit is not None and time.monotonic() - last_hit >= args.quiet:
                    break
                continue

            location = status.get("location", {})
            current = f"{location.get('cs', '')}:{location.get('eip', '')}".upper()
            if current == ENTRY:
                event = inspect_entry(client, status)
                caller_offset = int(str(event["caller"]).split(":", 1)[1], 16)
                keep_return = args.all_callers or caller_offset in RIGHT_PANEL_CALLER_OFFSETS
                if not keep_return:
                    skipped_entries += 1
                    client.continue_execution()
                    continue
            elif current == RETURN:
                if not keep_return:
                    client.continue_execution()
                    continue
                event = inspect_return(client, status)
                keep_return = False
            else:
                emit("foreign_stop", location=current, events=events)
                return 3
            events.append(event)
            last_hit = time.monotonic()
            client.continue_execution()

        emit(
            "captured" if events else "timeout",
            events=events,
            skipped_entries=skipped_entries,
        )
        return 0 if events else 1
    finally:
        status = client.get_debug_status()
        stopped_by_monitor = bool(status.get("stopped"))
        if not stopped_by_monitor:
            client.pause_execution()
        try:
            if armed:
                delete_own_breakpoints(client)
            remaining = client.list_breakpoints()
        finally:
            if stopped_by_monitor or client.get_debug_status().get("stopped"):
                client.continue_execution()
        emit(
            "cleanup",
            remaining_breakpoints=remaining,
            final_status=client.get_debug_status(),
        )


if __name__ == "__main__":
    raise SystemExit(main())
