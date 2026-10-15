# QC cycle 2 -- PR #82 (b22a99b)

Score: 92/100. No P0/P1. All cycle-1 P1s resolved; checks (b), (c), (d) pass.

(Saved by the main session: lex-qc had no Bash/Write tool, so it could not diff
against 213b3a5 and reviewed files at HEAD.)

## (a) Cycle-1 P1s
- P1-1 resolved: models.py:3861 `merge_dropped_records` upgrades info -> warning in either order; used at api.py:864; test test_ws_followups_75_80.py:187.
- P1-2 resolved: categories.py:6051, owned.py:357, pictures.py:103 return `_dropped_identity`. Programmer states GUID'd keys are unchanged.
- P1-3 resolved: three-way collision tests at test_ws_followups_75_80.py:576, :598.

## (b) #77 import fallback
Behavioural now (test_ws_followups_75_80.py:208): `sys.modules["api"]=None`, asserts `calls==["ws","execute"]` and the ImportError debug log. Skips if host imports are unavailable.

## (c) WS state model
- ws_mapping.py:694: four states -- WS_ACTIVE, WS_ACTIVATE, WS_CREATE, WS_UNDETERMINED.
- Missing ExistsInStore raises RuntimeError naming 4.8.0 (ws_mapping.py:725); no fallback. Move calls ws_create_state outside any try, so it propagates (api.py:946).
- Preview (`preflight_ws_creates`) is read-only (the fake Create asserts), dedupes per tag, emits an info activate notice or an undetermined warning.
- Move re-checks activity after Create via `ws_is_active`.
- _fakes_ws.py matches real flexicon: Exists active-only, ExistsInStore store-wide, Create activates a stored tag.

## (d) Floor and docs
pyproject.toml:53 `pyflexicon>=4.8.0`; the pyproject comment and the worktree CLAUDE.md:62-82 match #250.

## P0
None.

## P1
None.

## P2
- ws_mapping.py:711-725: the floor check only trips when a tag is not active, so on a pre-4.8.0 flexicon with every WS active the loud failure never fires. Consider a one-time `hasattr` check up front.
- preview.py:1401-1403: stale comment still describes "stored but not active cannot be created -> warning"; it is now an info activate notice.
- report.py:340-342: enrichment dedupe skips the info->warning upgrade (already flagged by the programmer).
- ws_mapping.py:728: when ExistsInStore raises, returns WS_CREATE and the reason is only debug-logged. Acceptable.
- categories.py:13738, 14183, 14216: still cite `>=4.5.x`. Historical, not wrong.
- About 138 ruff findings remain; pre-existing, unaddressed.

## Live-evidence gate
Write path (Create/activate). The live test was not run by QC and no evidence/live-*.md exists; approval is CONDITIONAL on lex-verification's FLEXLIBS_REQUIRE_LIVE=1 run.

Reviewed by: lex-qc
