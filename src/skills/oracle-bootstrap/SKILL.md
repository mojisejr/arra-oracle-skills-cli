---
name: oracle-bootstrap
description: Oracle bootstrap overlay — read CLAUDE.md and psi root, recover role/team/hard rules, and prevent model/team transport drift after resume, compact, or skill install. Use at session start, after model switch, after compact/resume, or when Oracle identity/team routing feels wrong.
argument-hint: "[--quick]"
---

# /oracle-bootstrap — Oracle Bootstrap Overlay

Use this skill to recover the local Oracle contract before acting. It is a lightweight overlay for forked Oracle environments; it does not replace `/recap`.

## Goal

Load the project-local identity and operating rules from `CLAUDE.md` plus the resolved `psi` root, then state the active constraints in one compact block.

This prevents three common drift modes:

- acting as a generic upstream assistant instead of the local Oracle;
- using Claude internal teams/subagents when the repo says team transport is `maw`/`webgang`;
- losing local hard rules after model switches, `/compact`, resume, or skill reinstall.

## Step 0: Detect Oracle Root

Run this before reading or writing anything:

```bash
ORACLE_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
if [ -n "$ORACLE_ROOT" ] && [ -f "$ORACLE_ROOT/CLAUDE.md" ] && { [ -d "$ORACLE_ROOT/ψ" ] || [ -L "$ORACLE_ROOT/ψ" ]; }; then
  PSI="$ORACLE_ROOT/ψ"
elif [ -f "$(pwd)/CLAUDE.md" ] && { [ -d "$(pwd)/ψ" ] || [ -L "$(pwd)/ψ" ]; }; then
  ORACLE_ROOT="$(pwd)"
  PSI="$ORACLE_ROOT/ψ"
else
  ORACLE_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
  PSI="$ORACLE_ROOT/ψ"
  echo "WARN: no CLAUDE.md + psi root detected at git root; using pwd/git root as fallback."
fi

echo "ORACLE_ROOT=$ORACLE_ROOT"
echo "PSI=$PSI"
test -f "$ORACLE_ROOT/CLAUDE.md" && sed -n '1,260p' "$ORACLE_ROOT/CLAUDE.md"
test -e "$PSI" && ls -ld "$PSI"
```

## Step 1: Extract The Contract

From `CLAUDE.md`, identify and preserve:

- Oracle name/role and any self-identity notes.
- Human/team names and reporting expectations.
- Hard rules, especially git flow, deploy ownership, no-destructive-actions rules, and completion ping/reporting rules.
- Team transport. If `CLAUDE.md` mentions `maw`, `webgang`, `maw hey`, `maw reply`, or pane/session routing, treat team transport as `maw/webgang`.
- Whether internal subagents or Claude team tools are explicitly allowed for this repo/session.
- Where memory lives: resolved `$PSI`, including whether it is a symlink.

Do not infer missing hard rules. If a field is absent, say `not specified`.

## Step 2: Output Bootstrap Block

Return a short block like:

```markdown
## Oracle Bootstrap

- root: /absolute/path
- psi: /absolute/path/ψ
- identity: <oracle role/name from CLAUDE.md, or not specified>
- team: <maw/webgang | local | not specified>
- transport: <maw/webgang if CLAUDE.md says so; otherwise not specified>
- hard rules: <3-6 bullets, exact local constraints>
- subagents: <explicitly allowed | explicit only | not specified>
- completion ping/reporting: <rule from CLAUDE.md, or not specified>
```

Keep it factual. Do not start `/recap`, `/rrr`, team creation, branch work, or file edits unless the user asked for that separately.

## Transport Guard

If `CLAUDE.md` says the Oracle is part of a `maw`/`webgang` team:

- Use `maw hey`/`maw reply` or the app's approved routing for cross-Oracle communication.
- Do not substitute Claude internal TeamCreate/SendMessage for webgang routing unless the user explicitly asks for internal subagents/team-agents.
- Do not create hidden background subagents just because a global skill suggests it. Local CLAUDE.md wins.

## Subagent Guard

Default to main-agent work. Use internal subagents only when one of these is true:

- the user explicitly asks for subagents/team-agents/parallel agents;
- the active skill explicitly requires them and `CLAUDE.md` does not forbid them;
- the user approves a plan that includes them.

If the repo says team transport is `maw/webgang`, internal subagents are implementation helpers only; they are not the team communication layer.

## Relationship To /recap

Use `/oracle-bootstrap` for identity/rules/transport recovery. Use `/recap` for session state, handoffs, and next actions. If both are needed, run bootstrap first, then recap.
