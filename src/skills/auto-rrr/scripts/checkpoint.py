#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write Oracle task-boundary checkpoints.")
    sub = parser.add_subparsers(dest="command")

    boundary = sub.add_parser("boundary", help="Flush /track and write a fresh handoff checkpoint.")
    boundary.add_argument("--note", default="", help="Short task-state note to include in the handoff.")

    sub.add_parser("latest", help="Print the newest handoff checkpoint path.")

    args = parser.parse_args(argv)
    command = args.command or "boundary"
    if command == "boundary":
        path = write_boundary_checkpoint(args.note)
        print(f"checkpoint: {path}")
        print(f"RRR_FEED: auto-rrr boundary checkpoint written; file={path}")
        return 0
    if command == "latest":
        latest = latest_handoff()
        if latest:
            print(latest)
            return 0
        print("no handoff checkpoints found", file=sys.stderr)
        return 1
    parser.print_help()
    return 2


def resolve_psi(start: Path | None = None) -> Path:
    override = os.environ.get("AUTO_RRR_PSI")
    if override:
        return Path(override).expanduser().resolve()

    cwd = (start or Path.cwd()).resolve()
    git_root = run_text(["git", "rev-parse", "--show-toplevel"], cwd=cwd, check=False).strip()
    candidates: list[Path] = []
    if git_root:
        candidates.append(Path(git_root))
    candidates.append(cwd)
    candidates.extend(cwd.parents)
    for root in candidates:
        psi = root / "ψ"
        if (root / "CLAUDE.md").is_file() and psi.exists():
            return psi
    raise SystemExit("cannot resolve Oracle ψ root: run from an Oracle repo with CLAUDE.md + ψ/")


def write_boundary_checkpoint(note: str) -> Path:
    psi = resolve_psi()
    handoff_dir = psi / "inbox" / "handoff"
    handoff_dir.mkdir(parents=True, exist_ok=True)
    ts = timestamp()
    path = handoff_dir / f"boundary-checkpoint-{ts}.md"
    track_output = flush_track()
    ledger = read_text(psi / "active" / "track-ledger.md")

    content = "\n".join(
        [
            "# Boundary Checkpoint",
            "",
            f"- created: {ts}",
            f"- cwd: {Path.cwd()}",
            f"- git_branch: {git_branch()}",
            f"- note: {note or '(none)'}",
            "",
            "## Git Status",
            "",
            fenced(git_status() or "(clean)"),
            "",
            "## Track Flush",
            "",
            fenced(track_output or "(track unavailable or no pending entries)"),
            "",
            "## Track Ledger Snapshot",
            "",
            fenced(ledger or "(empty)"),
            "",
            "## Resume",
            "",
            "Read this checkpoint, then continue the last active task from the newest concrete state.",
            "",
        ]
    )
    atomic_write(path, content)
    return path


def latest_handoff() -> Path | None:
    psi = resolve_psi()
    handoff_dir = psi / "inbox" / "handoff"
    if not handoff_dir.exists():
        return None
    files = [path for path in handoff_dir.iterdir() if path.is_file()]
    if not files:
        return None
    return max(files, key=lambda path: path.stat().st_mtime)


def flush_track() -> str:
    track_script = Path(__file__).resolve().parents[2] / "track" / "scripts" / "track.py"
    if not track_script.exists():
        return "track engine not installed beside auto-rrr"
    try:
        return run_text([sys.executable, str(track_script), "pull"], check=False).strip()
    except Exception as exc:  # noqa: BLE001 - checkpoint must not fail just because track is unavailable.
        return f"track flush failed: {exc}"


def git_branch() -> str:
    return run_text(["git", "branch", "--show-current"], check=False).strip() or "(unknown)"


def git_status() -> str:
    return run_text(["git", "status", "--short"], check=False).strip()


def run_text(args: list[str], cwd: Path | None = None, check: bool = True) -> str:
    try:
        completed = subprocess.run(
            args,
            cwd=str(cwd) if cwd else None,
            check=check,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        return exc.stdout or ""
    return completed.stdout or ""


def read_text(path: Path) -> str:
    try:
        return path.read_text()
    except FileNotFoundError:
        return ""


def atomic_write(path: Path, content: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content)
    os.replace(tmp, path)


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def fenced(text: str) -> str:
    return f"```text\n{text.rstrip()}\n```"


if __name__ == "__main__":
    raise SystemExit(main())
