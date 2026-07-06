#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LEDGER_HEADER = "# Track Ledger\n\n<!-- oracle-track-ledger-v1 -->\n\n"
DEFAULT_THRESHOLD_MINUTES = 15


@dataclass
class Entry:
    id: str
    owner: str
    dispatched: str
    expect: str
    status: str = "pending"
    threshold_minutes: int = DEFAULT_THRESHOLD_MINUTES
    got: list[str] = field(default_factory=list)
    stale_note: str = ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Track Oracle team work from maw messages.")
    parser.add_argument("--clear", action="store_true", help="Clear the active ledger.")
    sub = parser.add_subparsers(dest="command")

    dispatch = sub.add_parser("dispatch", help="Add a tracked dispatch entry.")
    dispatch.add_argument("id")
    dispatch.add_argument("owner")
    dispatch.add_argument("expect", nargs="+")
    dispatch.add_argument("--threshold-minutes", type=int, default=DEFAULT_THRESHOLD_MINUTES)

    sub.add_parser("pull", help="Pull outbound maw messages and close matched entries.")
    close = sub.add_parser("close", help="Manually close a tracked entry.")
    close.add_argument("id")
    sub.add_parser("status", help="Show the current ledger without polling.")

    args = parser.parse_args(argv)
    ledger = ledger_path()
    if args.clear:
        write_entries(ledger, [])
        print(f"cleared {ledger}")
        return 0

    command = args.command or "pull"

    if command == "dispatch":
        expect = " ".join(args.expect).strip()
        if not expect:
            print("expect token is required", file=sys.stderr)
            return 2
        return dispatch_entry(ledger, args.id, args.owner, expect, args.threshold_minutes)
    if command == "pull":
        return pull_entries(ledger)
    if command == "status":
        return show_status(ledger)
    if command == "close":
        return close_entry(ledger, args.id)
    parser.print_help()
    return 2


def resolve_psi(start: Path | None = None) -> Path:
    cwd = (start or Path.cwd()).resolve()
    git_root = run_text(["git", "rev-parse", "--show-toplevel"], cwd=cwd, check=False).strip()
    candidates = []
    if git_root:
        candidates.append(Path(git_root))
    candidates.append(cwd)
    candidates.extend(cwd.parents)
    for root in candidates:
        psi = root / "ψ"
        if (root / "CLAUDE.md").is_file() and psi.exists():
            return psi
    raise SystemExit("cannot resolve Oracle ψ root: run from an Oracle repo with CLAUDE.md + ψ/")


def ledger_path() -> Path:
    override = os.environ.get("TRACK_LEDGER")
    if override:
        return Path(override).expanduser()
    return resolve_psi() / "active" / "track-ledger.md"


def dispatch_entry(ledger: Path, entry_id: str, owner: str, expect: str, threshold_minutes: int) -> int:
    entries = read_entries(ledger)
    if any(entry.id == entry_id for entry in entries):
        print(f"track id already exists: {entry_id}", file=sys.stderr)
        return 1
    entry = Entry(
        id=entry_id,
        owner=normalize_owner(owner),
        dispatched=now_iso(),
        expect=expect,
        threshold_minutes=threshold_minutes,
    )
    entries.append(entry)
    write_entries(ledger, entries)
    print(f"tracking {entry.id}: owner={entry.owner} expect={entry.expect} dispatched={entry.dispatched}")
    print(f"ledger: {ledger}")
    return 0


def pull_entries(ledger: Path) -> int:
    entries = read_entries(ledger)
    if not entries:
        print(f"track ledger empty: {ledger}")
        return 0

    remaining: list[Entry] = []
    closed: list[tuple[Entry, dict[str, Any]]] = []
    for entry in entries:
        match = find_matching_message(entry)
        if match:
            entry.got.append(message_summary(match))
            entry.status = "done"
            closed.append((entry, match))
            continue
        entry.stale_note = stale_note(entry)
        remaining.append(entry)

    write_entries(ledger, remaining)
    for entry, message in closed:
        print(f"✅ {entry.id}: matched {entry.expect!r} from {entry.owner} at {message_ts(message)}")
        print(f"RRR_FEED: track {entry.id} closed; owner={entry.owner}; expect={entry.expect}; ack={message_summary(message)}")
    for entry in remaining:
        prefix = "🔴" if entry.stale_note else "⏳"
        suffix = f" · {entry.stale_note}" if entry.stale_note else ""
        print(f"{prefix} {entry.id}: owner={entry.owner} expect={entry.expect} since={entry.dispatched}{suffix}")
    print(f"ledger: {ledger}")
    return 0


def show_status(ledger: Path) -> int:
    entries = read_entries(ledger)
    if not entries:
        print(f"track ledger empty: {ledger}")
        return 0
    for entry in entries:
        print(f"⏳ {entry.id}: owner={entry.owner} expect={entry.expect} since={entry.dispatched}")
    print(f"ledger: {ledger}")
    return 0


def close_entry(ledger: Path, entry_id: str) -> int:
    entries = read_entries(ledger)
    remaining = [entry for entry in entries if entry.id != entry_id]
    if len(remaining) == len(entries):
        print(f"track id not found: {entry_id}", file=sys.stderr)
        return 1
    write_entries(ledger, remaining)
    print(f"closed {entry_id}")
    print(f"RRR_FEED: track {entry_id} manually closed")
    return 0


def find_matching_message(entry: Entry) -> dict[str, Any] | None:
    data = maw_messages(entry.owner)
    messages = data.get("messages", []) if isinstance(data, dict) else []
    dispatched = parse_ts(entry.dispatched)
    expect = entry.expect.casefold()
    for message in messages:
        ts = parse_ts(message_ts(message))
        if not ts or ts <= dispatched:
            continue
        text = str(message.get("text") or "")
        if expect in text.casefold():
            return message
    return None


def maw_messages(owner: str) -> dict[str, Any]:
    raw = run_text(
        ["maw", "messages", "--from", owner, "--direction", "outbound", "--json", "--limit", "20"],
        check=True,
    )
    return json.loads(raw)


def stale_note(entry: Entry) -> str:
    dispatched = parse_ts(entry.dispatched)
    age_minutes = (datetime.now(timezone.utc) - dispatched).total_seconds() / 60
    if age_minutes <= entry.threshold_minutes:
        return ""
    activity = maw_activity(entry.owner)
    if activity:
        return f"stale {int(age_minutes)}m; activity={activity}"
    return f"stale {int(age_minutes)}m; activity=unavailable"


def maw_activity(owner: str) -> str:
    candidates = [owner]
    if owner.startswith("CL1:"):
        candidates.append(owner.split(":", 1)[1])
    for candidate in candidates:
        try:
            output = run_text(["maw", "activity", candidate], check=True, timeout=8).strip()
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            continue
        if output:
            return " ".join(output.split())
    return ""


def read_entries(path: Path) -> list[Entry]:
    if not path.exists():
        return []
    lines = path.read_text().splitlines()
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if line.startswith("- id: "):
            if current:
                blocks.append(current)
            current = [line]
        elif current and (line.startswith("  ") or not line.strip()):
            current.append(line)
    if current:
        blocks.append(current)
    return [parse_block(block) for block in blocks]


def parse_block(block: list[str]) -> Entry:
    values: dict[str, str] = {}
    got: list[str] = []
    for line in block:
        if line.startswith("- id: "):
            values["id"] = line.removeprefix("- id: ").strip()
        elif line.startswith("  got:"):
            raw = line.removeprefix("  got:").strip()
            got = [] if raw in ("[]", "") else [raw]
        elif line.startswith("    - "):
            got.append(line.removeprefix("    - ").strip())
        else:
            match = re.match(r"^  ([a-z_]+):\s*(.*)$", line)
            if match:
                values[match.group(1)] = match.group(2).strip()
    return Entry(
        id=values.get("id", ""),
        owner=values.get("owner", ""),
        dispatched=values.get("dispatched", ""),
        expect=values.get("expect", ""),
        status=values.get("status", "pending"),
        threshold_minutes=int(values.get("threshold_minutes") or DEFAULT_THRESHOLD_MINUTES),
        got=got,
        stale_note=values.get("stale_note", ""),
    )


def write_entries(path: Path, entries: list[Entry]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = LEDGER_HEADER
    for entry in entries:
        body += format_entry(entry)
    path.write_text(body)


def format_entry(entry: Entry) -> str:
    lines = [
        f"- id: {entry.id}",
        f"  owner: {entry.owner}",
        f"  dispatched: {entry.dispatched}",
        f"  expect: {entry.expect}",
        f"  status: {entry.status}",
        f"  threshold_minutes: {entry.threshold_minutes}",
    ]
    if entry.stale_note:
        lines.append(f"  stale_note: {entry.stale_note}")
    if entry.got:
        lines.append("  got:")
        lines.extend(f"    - {item}" for item in entry.got)
    else:
        lines.append("  got: []")
    return "\n".join(lines) + "\n\n"


def normalize_owner(owner: str) -> str:
    return owner if owner.startswith("CL1:") else f"CL1:{owner}"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_ts(value: str) -> datetime:
    if not value:
        return datetime.fromtimestamp(0, timezone.utc)
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def message_ts(message: dict[str, Any]) -> str:
    return str(message.get("ts") or message.get("timestamp") or "")


def message_summary(message: dict[str, Any]) -> str:
    text = " ".join(str(message.get("text") or "").split())
    if len(text) > 120:
        text = text[:117] + "..."
    return f"{message_ts(message)} {message.get('to', '')}: {text}".strip()


def run_text(args: list[str], cwd: Path | None = None, check: bool = True, timeout: int | None = None) -> str:
    result = subprocess.run(args, cwd=cwd, check=check, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    return result.stdout


if __name__ == "__main__":
    raise SystemExit(main())
