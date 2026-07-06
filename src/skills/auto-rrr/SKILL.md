---
name: auto-rrr
description: "Boundary checkpoint handoffs for Oracle long-run work. Use when an Oracle needs to write a task-boundary handoff, flush /track close-loop output into a retrospective feed, preserve current task state before compaction, or create a fresh handoff for /recap and oracle-bootstrap to read after resume."
---

# /auto-rrr

Create fresh handoffs at task boundaries before context can disappear. This skill pairs with `/track`.

Use the bundled deterministic helper:

```bash
python3 "<this skill dir>/scripts/checkpoint.py" boundary [--note "..."]
python3 "<this skill dir>/scripts/checkpoint.py" latest
```

## Boundary Checkpoint

Run at clean task boundaries or every few autonomous iterations:

```bash
python3 "$SKILL_DIR/scripts/checkpoint.py" boundary --note "PR ready; waiting for review"
```

Behavior:

- Resolve the Oracle `ψ` root like `/track`.
- Run the installed `/track` engine in `pull` mode, if available, and capture any `RRR_FEED:` close-loop output.
- Write `ψ/inbox/handoff/boundary-checkpoint-<ts>.md`.
- Include cwd, git branch, git status, track output, and the current track ledger snapshot.

## Resume Pattern

After compaction or resume, read the newest handoff through the normal Oracle recovery path:

```bash
ls -t "$PSI/inbox/handoff" | head -1
```

Then continue with `/recap`, `oracle-bootstrap`, and the latest boundary checkpoint.

Hook-based compaction recovery is intentionally not part of this skill: Claude Code build v2.1.197 does not expose the needed compaction lifecycle hooks in `/hooks`. The supported, canonical CLI pattern here is: write handoff at boundary, then re-read it after resume.

## Guardrails

- Do not rely on agent-forced `/compact`.
- Do not rely on Claude hooks for compaction recovery in this build.
- Do not auto-poll in the background.
- Do not touch maw core.
- Do not commit generated `ψ/inbox/handoff/boundary-checkpoint-*` files unless explicitly asked.
