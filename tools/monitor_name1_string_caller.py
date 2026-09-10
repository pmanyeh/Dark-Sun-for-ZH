#!/usr/bin/env python3
"""Stop only on an unknown NAME-1 Long Sword `%s` caller in DOSBox-X.

This is a narrow runtime tracing helper for re_54.  It never injects input or
writes guest memory.  Known hover/right-panel callers and unrelated `%s`
strings are resumed automatically.  On timeout it removes its own breakpoint
and leaves the guest running.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


DEFAULT_CLIENT_DIR = Path(r"D:\git\DOSBox-X-AI\ai")
BREAKPOINT = "339E:02D7"
TARGET = bytes.fromhex("5E 29 43 5E 21 7C")
KNOWN_CALLERS = {"5B7C:1F4D", "2143:0A6A"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--poll", type=float, default=0.015)
    parser.add_argument("--client-dir", type=Path, default=DEFAULT_CLIENT_DIR)
    parser.add_argument(
        "--observe-only",
        action="store_true",
        help="log target callers and always resume instead of retaining an unknown hit",
    )
    return parser.parse_args()


def emit(kind: str, **fields: object) -> None:
    print(json.dumps({"kind": kind, **fields}, ensure_ascii=False), flush=True)


def word(raw: list[str], index: int = 0) -> int:
    return int(raw[index], 16) | (int(raw[index + 1], 16) << 8)


def delete_own_breakpoint(client: object) -> bool:
    for breakpoint in client.list_breakpoints():
        if str(breakpoint.get("address", "")).upper() == BREAKPOINT:
            client.delete_breakpoint(int(breakpoint["id"]))
            return True
    return False


def inspect_hit(client: object, status: dict[str, object]) -> dict[str, object]:
    segments = status["segments"]
    registers = status["registers"]
    ss = str(segments["ss"])
    bp = int(str(registers["ebp"])[-4:], 16)

    cursor_raw = client.read_memory(f"{ss}:{(bp - 6) & 0xFFFF:04X}", 2)["bytes"]
    cursor = word(cursor_raw)
    pointer_raw = client.read_memory(f"{ss}:{cursor:04X}", 4)["bytes"]
    offset = word(pointer_raw, 0)
    segment = word(pointer_raw, 2)
    source = f"{segment:04X}:{offset:04X}"

    try:
        payload_raw = client.read_memory(source, 32)["bytes"]
        payload = bytes(int(value, 16) for value in payload_raw)
    except Exception:
        payload = b""

    return_raw = client.read_memory(f"{ss}:{(bp + 2) & 0xFFFF:04X}", 4)["bytes"]
    return_offset = word(return_raw, 0)
    return_segment = word(return_raw, 2)
    caller = f"{return_segment:04X}:{return_offset:04X}"

    saved_bp_raw = client.read_memory(f"{ss}:{bp:04X}", 2)["bytes"]
    parent_bp = word(saved_bp_raw)
    parent_return_raw = client.read_memory(
        f"{ss}:{(parent_bp + 2) & 0xFFFF:04X}", 4
    )["bytes"]
    parent_offset = word(parent_return_raw, 0)
    parent_segment = word(parent_return_raw, 2)
    parent_caller = f"{parent_segment:04X}:{parent_offset:04X}"
    return {
        "source": source,
        "prefix_hex": payload[:16].hex(" "),
        "target": TARGET in payload,
        "caller": caller,
        "parent_frame_bp": f"{parent_bp:04X}",
        "parent_caller": parent_caller,
        "known_caller": caller in KNOWN_CALLERS,
    }


def main() -> int:
    args = parse_args()
    sys.path.insert(0, str(args.client_dir))
    from dosbox_client import DOSBoxBreakpointAlreadyExists, DOSBoxClient

    client = DOSBoxClient(request_timeout=15.0)
    status = client.get_debug_status()
    if status.get("stopped"):
        emit("refused", reason="debugger_already_stopped", status=status)
        return 2

    client.pause_execution()
    try:
        try:
            client.set_breakpoint(BREAKPOINT)
        except DOSBoxBreakpointAlreadyExists:
            pass
    finally:
        client.continue_execution()

    emit("armed", breakpoint=BREAKPOINT, known_callers=sorted(KNOWN_CALLERS))
    deadline = time.monotonic() + args.timeout
    event_count = 0

    while time.monotonic() < deadline:
        time.sleep(args.poll)
        status = client.get_debug_status()
        if not status.get("stopped"):
            continue

        location = status.get("location", {})
        current = f"{location.get('cs', '')}:{location.get('eip', '')}".upper()
        if current != BREAKPOINT:
            emit("foreign_stop", location=current, status=status)
            return 3

        event_count += 1
        event = inspect_hit(client, status)
        emit("hit", event_count=event_count, **event)
        if event["target"] and not event["known_caller"] and not args.observe_only:
            delete_own_breakpoint(client)
            emit("target_unknown_caller", event_count=event_count, **event)
            return 0

        client.continue_execution()

    status = client.get_debug_status()
    paused_by_us = False
    if not status.get("stopped"):
        client.pause_execution()
        paused_by_us = True
    try:
        delete_own_breakpoint(client)
    finally:
        if paused_by_us or client.get_debug_status().get("stopped"):
            client.continue_execution()
    emit("timeout", event_count=event_count, guest_running=True)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
