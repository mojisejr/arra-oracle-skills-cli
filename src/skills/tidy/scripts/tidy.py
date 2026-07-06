#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


ACK_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\brrr\s+done\b",
        r"\blgtm\b",
        r"\bpass\b",
        r"\bmerged\b",
        r"\bready\b",
        r"\bdone\b",
        r"\bverified\b",
        r"\bdeployed\b",
        r"blocked\s*(?:→|->)\s*resolved",
    )
)

OPEN_ASK_PATTERNS = (
    "?",
    "please advise",
    "directive",
    "ต้องตัดสิน",
    "ตัดสินใจ",
    "รอ",
)


@dataclass
class TidyResult:
    archived: list[Path]
    preserved: list[Path]
    unread_remaining: int
    processed_dir: Path
    committed: bool = False
    pushed: bool = False


def run(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check)


def resolve_oracle_root(cwd: Path) -> tuple[Path, Path]:
    override = os.environ.get("TIDY_PSI") or os.environ.get("ORACLE_PSI")
    if override:
        psi = Path(override).expanduser().resolve()
        return psi.parent, psi

    git_root = run(["git", "rev-parse", "--show-toplevel"], cwd, check=False).stdout.strip()
    if git_root:
        root = Path(git_root).resolve()
        psi = root / "ψ"
        if (root / "CLAUDE.md").exists() and psi.exists():
            return root, psi

    here = cwd.resolve()
    if (here / "CLAUDE.md").exists() and (here / "ψ").exists():
        return here, here / "ψ"

    raise SystemExit("could not find Oracle root with CLAUDE.md + ψ; set TIDY_PSI")


def top_level_inbox_files(inbox: Path) -> list[Path]:
    if not inbox.exists():
        return []
    return sorted(path for path in inbox.glob("*.md") if path.is_file())


def first_line(path: Path) -> str:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            return handle.readline().strip()
    except OSError:
        return ""


def text_sample(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def is_open_ask(path: Path) -> bool:
    line = first_line(path).lower()
    return any(pattern.lower() in line for pattern in OPEN_ASK_PATTERNS)


def is_consumed_ack(path: Path) -> bool:
    text = text_sample(path)
    return any(pattern.search(text) for pattern in ACK_PATTERNS)


def is_older_than(path: Path, threshold_hours: float, now: datetime) -> bool:
    modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    age_seconds = (now - modified).total_seconds()
    return age_seconds >= threshold_hours * 3600


def unique_destination(dest_dir: Path, name: str) -> Path:
    candidate = dest_dir / name
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    index = 2
    while True:
        next_candidate = dest_dir / f"{stem}-{index}{suffix}"
        if not next_candidate.exists():
            return next_candidate
        index += 1


def select_files(files: list[Path], all_mode: bool, threshold_hours: float, now: datetime) -> tuple[list[Path], list[Path]]:
    if all_mode:
        return files, []

    archived: list[Path] = []
    preserved: list[Path] = []
    for path in files:
        if is_open_ask(path):
            preserved.append(path)
            continue
        if is_older_than(path, threshold_hours, now) and is_consumed_ack(path):
            archived.append(path)
        else:
            preserved.append(path)
    return archived, preserved


def relative_to_root(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        raise SystemExit(f"refusing to stage path outside oracle root: {path}")


def commit_inbox(root: Path, psi: Path, message: str) -> bool:
    inbox_rel = relative_to_root(psi / "inbox", root)
    run(["git", "add", "--", inbox_rel], root)
    status = run(["git", "status", "--short", "--", inbox_rel], root).stdout.strip()
    if not status:
        return False
    run(["git", "commit", "-m", message, "--", inbox_rel], root)
    return True


def push_inbox(root: Path) -> bool:
    run(["git", "push"], root)
    return True


def git_status_for_inbox(root: Path, psi: Path) -> str:
    inbox_rel = relative_to_root(psi / "inbox", root)
    status = run(["git", "status", "--short", "--", inbox_rel], root, check=False).stdout.strip()
    return status or "clean"


def tidy(root: Path, psi: Path, all_mode: bool, confirm: bool, threshold_hours: float, should_commit: bool, should_push: bool, now: datetime | None = None) -> TidyResult:
    if all_mode and not confirm:
        raise SystemExit("--all requires --confirm")

    now = now or datetime.now(timezone.utc)
    inbox = psi / "inbox"
    processed_dir = inbox / "processed" / now.date().isoformat()
    files = top_level_inbox_files(inbox)
    to_archive, preserved = select_files(files, all_mode, threshold_hours, now)

    if to_archive:
        processed_dir.mkdir(parents=True, exist_ok=True)
    moved: list[Path] = []
    for path in to_archive:
        dest = unique_destination(processed_dir, path.name)
        shutil.move(str(path), str(dest))
        moved.append(dest)

    result = TidyResult(
        archived=moved,
        preserved=preserved,
        unread_remaining=len(top_level_inbox_files(inbox)),
        processed_dir=processed_dir,
    )

    if moved and should_commit:
        result.committed = commit_inbox(root, psi, f"vault: tidy inbox {now.date().isoformat()}")
        if should_push:
            result.pushed = push_inbox(root)
    elif should_push:
        raise SystemExit("--push requires a commit; nothing archived")

    return result


def print_result(root: Path, psi: Path, result: TidyResult) -> None:
    print(f"archived: {len(result.archived)}")
    print(f"processed: {result.processed_dir}")
    print(f"remaining unread: {result.unread_remaining}")
    print(f"committed: {'yes' if result.committed else 'no'}")
    print(f"pushed: {'yes' if result.pushed else 'no'}")
    print(f"git inbox state: {git_status_for_inbox(root, psi)}")
    for path in result.archived:
        print(f"moved: {path.name}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Archive consumed top-level Oracle inbox messages.")
    parser.add_argument("--all", action="store_true", help="archive all top-level inbox markdown files")
    parser.add_argument("--confirm", action="store_true", help="required with --all")
    parser.add_argument("--threshold-hours", type=float, default=4.0, help="safe-mode minimum file age")
    parser.add_argument("--commit", dest="should_commit", action="store_true", default=True, help="commit ψ/inbox changes (default)")
    parser.add_argument("--no-commit", dest="should_commit", action="store_false", help="move files without committing")
    parser.add_argument("--push", action="store_true", help="push after committing")
    args = parser.parse_args(argv)

    root, psi = resolve_oracle_root(Path.cwd())
    result = tidy(
        root=root,
        psi=psi,
        all_mode=args.all,
        confirm=args.confirm,
        threshold_hours=args.threshold_hours,
        should_commit=args.should_commit,
        should_push=args.push,
    )
    print_result(root, psi, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
