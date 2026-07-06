---
name: track
description: "Oracle orchestrator work tracking. Use when an Oracle needs to track dispatched team work, poll maw outbound acknowledgements without false-matching old messages, flag stale work, close completed ledger entries, or clear the active work ledger with commands such as /track, /track dispatch, /track close, or /track --clear."
---

# /track

Track dispatched team work from the coordinator/orchestrator side.

Use the bundled deterministic engine. Do not grep `maw messages` manually.

```bash
python3 "<this skill dir>/scripts/track.py" [args...]
```

## Commands

```bash
/track dispatch <id> <owner> <expect> [--threshold-minutes N]
/track
/track pull
/track close <id>
/track --clear
```

Examples:

```bash
python3 "$SKILL_DIR/scripts/track.py" dispatch pr29 too "LGTM"
python3 "$SKILL_DIR/scripts/track.py" pull
python3 "$SKILL_DIR/scripts/track.py" close pr29
```

## Behavior

- Resolve the Oracle `ψ` root like `/rrr`: git root with `CLAUDE.md` and `ψ/`, then write the active ledger at `ψ/active/track-ledger.md`.
- Store owners as `CL1:<owner>` unless already prefixed.
- Pull with `maw messages --from CL1:<owner> --direction outbound --json --limit 20`.
- Filter client-side by `message.ts > dispatched`; `maw messages` has no native `--since`.
- Match only the expected token inside timestamp-scoped messages from the tracked owner.
- When matched, remove the entry from the active ledger and print an `RRR_FEED:` line for retrospective capture.
- When pending longer than the threshold (default 15 minutes), run `maw activity` best-effort and flag stale before the human asks.

## Guardrails

- Do not commit `ψ/active/track-ledger.md`.
- Do not auto-poll in the background.
- Do not touch maw core.
- Treat activity output as advisory; acknowledgement matching comes only from owner + since + expected token.
