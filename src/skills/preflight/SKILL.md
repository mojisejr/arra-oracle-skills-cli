---
name: preflight
description: "Read-only Oracle precondition checks before route, deploy, or assert work. Use when an Oracle needs /preflight, raw-before-read evidence, route/dispatch readiness checks, deploy/install prechecks, endpoint/env/host/native ABI probes, or a lightweight mechanical ladder before making a claim."
---

# /preflight

Run read-only precondition checks before routing, deploying, or asserting a large claim. This skill supports the Raw-Before-Read convention: collect raw probe output first, then interpret it.

Use the bundled helper for mechanical probes:

```bash
python3 "<this skill dir>/scripts/preflight.py" [--env PATH] [--endpoint URL] [--host HOST] [--node-abi MODULE]
```

The helper always exits 0. Treat failed checks as report data, not as script failure.

## Route / Dispatch Ladder

Before assigning work or claiming a route is ready:

1. Check required local env files exist.
2. Probe endpoints for real body content, not just HTTP 200.
3. Check peer/session state from the real source for the project.
4. Check external host resolution or native ABI if the task depends on them.
5. Paste raw output into the dispatch/update before interpreting.

Example:

```bash
python3 "$SKILL_DIR/scripts/preflight.py --env .env.local --endpoint http://127.0.0.1:3456/api/sessions --host localhost"
```

## Deploy / Install Ladder

Before deploy/install:

1. Identify the real runtime context: launchd, browser, PWA, CLI, tmux, or API.
2. Show config paths and current config before apply.
3. Confirm backup/rollback path exists.
4. Run only read-only probes here. The deploy command itself stays separate and operator-owned when required.
5. Paste raw probe output with proof labels: `offline`, `dry-run`, or `real-path`.

## Assert Ladder

Before making a large claim:

1. Point back to raw evidence: peer verdict, test output, PR/CI status, endpoint response, or real-path proof.
2. If evidence is missing, say what is missing instead of upgrading the claim.
3. Do not use this skill to justify paid/live calls or production mutation.

## Guardrails

- Read-only only. Do not mutate files, services, databases, settings, or hooks.
- Never print secret values. The env probe prints key names and presence only.
- Probe only local/localhost targets or endpoints explicitly supplied by the user.
- Exit 0 is intentional so preflight can be pasted into notes without breaking workflow.
- This is an optional helper, not a hook and not a replacement for project-specific verification.
