# T004 — lockout claims (Phase 1)

**Team:** `transfer-fidelity-gaps-038`
**Session ID:** `be0d143d-ac1a-415e-b4d1-9f53bb4a1f8d`  (needed by T084 to release)
**TTL:** 480 minutes, expires `2026-08-19T10:29:32Z`. Re-heartbeat before then:
`python ~/.claude/skills/lockout/lockout.py heartbeat --team transfer-fidelity-gaps-038 --session be0d143d-ac1a-415e-b4d1-9f53bb4a1f8d`

## Claimed paths — MAIN worktree, deliberately

Claimed against `D:/Github/_Projects/_LEX/GramTrans/src/gramtrans/Lib/`, **not**
the `..\GramTrans-038-transfer-fidelity-gaps\` copies:

- `categories.py`
- `transfer.py`
- `models.py`
- `report.py`
- `preview.py`

`models.py` and `report.py` are on this list because tasks.md:57-62 flags them as
hazards `plan.md` omits: 037 modified both (+56 / +30, adding `LeafExecutionFailure`,
`RunReport.leaf_execution_failures`, `leaf_failed`) and nobody had claimed them.

## Why the main-worktree path is the only claim that means anything

`lockout` claims are **path-scoped strings**, not content-scoped. A claim taken from
`..\GramTrans-038-transfer-fidelity-gaps\src\gramtrans\Lib\categories.py` names a
different absolute path than 037's `...\GramTrans-037-phon-nc-features\...\categories.py`,
so the two can never collide and the claim would be theatre (tasks.md:63-67).

## Conflict check against 037's absolute paths — result: NO LIVE CONFLICT

`lockout status --file` was run against all five of 037's absolute worktree paths
(`D:/Github/_Projects/_LEX/GramTrans-037-phon-nc-features/src/gramtrans/Lib/*.py`)
**before** acquiring. Every one returned `[LOCKOUT] No active locks.`, and a bare
`lockout status` likewise returned `No active locks` registry-wide.

tasks.md:63-64 describes "all seven of 037's live claims" — **that is now stale**.
037 merged to `main` at `a824b8d` and its session ended; its claims have expired out
of the registry. The path-scoping caveat above still stands as the reason to claim
main paths, but there is no 037 contention left to avoid.
