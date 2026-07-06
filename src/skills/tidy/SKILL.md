---
name: tidy
description: "Oracle inbox housekeeping. Use when an Oracle needs to archive consumed top-level ψ/inbox markdown messages into processed/YYYY-MM-DD, run safe closeout tidy from /rrr or /forward, or sweep all inbox messages with explicit confirmation."
---

# /tidy

Archive consumed Oracle inbox messages without deleting anything.

Use the bundled deterministic helper:

```bash
python3 "<this skill dir>/scripts/tidy.py" [--all --confirm] [--threshold-hours 4] [--commit|--no-commit] [--push]
```

## Modes

```bash
# Safe default: old consumed acknowledgements only.
python3 "$SKILL_DIR/scripts/tidy.py"

# Sweep every top-level inbox markdown file. Requires explicit confirmation.
python3 "$SKILL_DIR/scripts/tidy.py --all --confirm"
```

## Behavior

- Move top-level `$PSI/inbox/*.md` to `$PSI/inbox/processed/YYYY-MM-DD/`.
- Move, never delete. This follows Nothing-is-Deleted and keeps the operation reversible.
- Never touch `handoff/`, `processed/`, or any inbox subdirectory.
- Default safe mode archives only messages older than the threshold, default 4 hours, and matching our consumed-ack vocabulary:
  `rrr done`, `LGTM`, `PASS`, `merged`, `ready`, `done`, `verified`, `deployed`, `blocked→resolved`.
- Safe mode preserves anything that looks like an open ฟีม ask: first-line `?`, `please advise`, `directive`, `ต้องตัดสิน`, `ตัดสินใจ`, or `รอ`.
- After moving files, commit only `$PSI/inbox/` by default. Use `--no-commit` for fixtures/tests. Use `--push` only when explicitly requested.

## Guardrails

- Scope is vault inbox only. The helper stages and commits only the detected `$PSI/inbox/` path. It must never stage code files or push a code repo.
- This overlay exists because upstream `maw inbox drain --safe` has hardcoded safe-drain vocabulary from another project and matched none of our team inbox backlog. Our team vocabulary is different, so this skill is local overlay policy.
- Do not make this another daily command Фีม must remember. Fold safe `/tidy` into `/rrr` and `/forward` closeout; call `--all --confirm` only for explicit session-end sweeps.

## Skill Qualification

A new overlay skill qualifies only when it is a recurring operation we have done by hand and felt the pain at least 2-3 times. `/tidy` qualifies because inbox archive accumulated hundreds of messages and needed a manual workaround.

## Convention — session-close tidy

At session close (`/rrr` or `/forward`), the coordinator runs `/tidy` (safe mode)
so consumed inbox messages archive incrementally instead of piling up.

- This is a **convention, not enforced wiring.** `/rrr` and `/forward` are
  arra-managed skills and are deliberately left untouched (overlay principle:
  never edit upstream).
- **Drift is acceptable by design.** If a close is missed and the inbox
  accumulates, running `/tidy` (or `/tidy --all --confirm` for a full sweep)
  cleans it up. The point of this skill is that cleanup is now cheap, so we
  don't need hard enforcement.
