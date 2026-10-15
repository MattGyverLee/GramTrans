# QC cycle 1 -- PR #82 (213b3a5)

Score: 80/100. Recommendation: FIX ISSUES (minor). 0 P0, 3 P1, 4 P2.

(Saved by the main session: lex-qc had no Write/shell tool. lex-qc therefore
did NOT run pytest or `gh issue view`; issue criteria judged from code + brief.
Note from main session: the brief's mention of additions to
`test_ensure_writing_systems.py` / `test_ws_path_followup.py` was inaccurate --
PR #82 adds only `tests/unit/test_ws_followups_75_80.py` and
`tests/integration/test_ws_followups_live.py`. The PR body has no explicit
"Pattern audit" section.)

Limits: no live-LCM evidence reviewed by QC; orchestrator to confirm.

| Issue | Status | Note |
|---|---|---|
| #75 enum coercion | Resolved | models.py:295 `coerce_enum` by `.value`; used models.py:608, 3676; ws_mapping.py:591. Unknown values fall through to validation. |
| #76 GUID-less dedupe | Resolved (P1-1) | models.py:3843 `dropped_identity` falls back to kind:label / item_name; used api.py:859, report.py:832. |
| #77 lazy api import | Resolved (P2-1) | gramtrans.py:594-596 flat then package fallback; Phase 2 plan warnings logged 550-552. |
| #78 severity | Resolved | validated in `__post_init__` (models.py:3834); [WARN] render report.py:2005-2017; reversals.py:514, 667 warnings; preflight shared via ws_mapping. |
| #80 target collision | Resolved (P1-3) | config_views.py:669 keep name-match else first; losers dropped + warning record. |

## Questions
- Distinct drops collapse? One case (P1-1). Key omits reason/severity by contract; GUID-less records now distinct by label.
- JSON consumers break from omitting severity="info"? Not existing ones (unchanged output). New consumers must default missing severity to "info" -- document in schema/contract.
- Lazy import swallows real errors? No: only ImportError; second import raises its own. Residual risk P2-1.

## P0
None.

## P1
1. api.py:859-864 / models.py:3843 -- an existing "info" record with the same key silently swallows a later "warning" record. Upgrade severity on collision (or include severity in the merge rule). Add a test.
2. Cross-module dedupe inconsistency -- categories.py:6049, owned.py:355, pictures.py:101 still key on raw `(owner_guid, field_name, item_guid)`; GUID-less records through those paths still collapse. Delegate to `dropped_identity` or document the exemption.
3. config_views.py:690-692 -- winner when no name match depends on listing order from `_list_fwdictconfig`; confirm it is sorted (or sort the group). Test: three-way collision; cross-kind (key is full path, likely fine); kept record's `missing_refs` mutated in place -- confirm records are not shared across runs.

## P2
1. gramtrans.py:595 -- any ImportError (including a genuine missing transitive dependency inside `api`) triggers the fallback; the real cause shows only in the chained traceback. Consider logging the first failure.
2. report.py:2009-2017, gramtrans.py:550 -- `getattr(d, "severity", "info")` on a typed dataclass is defensive noise unless stubs need it.
3. report.py:832 `_dropped_dedup_key` is now a one-line passthrough; inline or delete.
4. models.py:3840 `DROP_SEVERITIES` defined after the class using it (works only because `__post_init__` runs later); move above the class.

## Test quality
- Good behaviour tests: #75 fold/validation, #76 identity/dedupe, #80 collisions with tmp_path (test_ws_followups_75_80.py:397-446).
- test_ws_followups_75_80.py:202, 220 are AST/structure-only; replace with a behavioural test forcing the flat import to raise ImportError and asserting the package path is used.
- Preflight tests monkeypatch `flexicon.WritingSystemOperations` -- mock-only, acceptable at unit scope.
- Missing: info-then-warning severity on collision (P1-1).

Reviewed by: lex-qc
