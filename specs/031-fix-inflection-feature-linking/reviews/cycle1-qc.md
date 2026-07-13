# QC Report — 031-fix-inflection-feature-linking (cycle 1)

**Date:** 2026-07-13
**Quality Score:** 74/100
**Status:** ISSUES — Pattern-Audit Gate BLOCK

## Pattern-Audit Gate
- Sweep present in commit/PR body: NO — T022's `pattern-audit.md` sweep covers the
  WS-handle-copy class only, and predates T024's live run. The two NEW bug shapes
  actually fixed in `9e41a1f` (unguarded `target.get_object_by_guid`; unguarded
  `IFsClosedFeature(src_feat)` cast) have no formal sweep-pattern section anywhere
  — only an informal note in STATUS.md naming `_run_post_pass_a` and
  `_run_171_subpass` as "out of scope" follow-ups.
- Spot-check on a listed sibling: real — confirmed unguarded
  `target.get_object_by_guid(...)` at categories.py:4887, 4898 (`_run_171_subpass`)
  and :4947, 4965 (`_run_post_pass_a`).
- **Gate status: BLOCK.** Recognisable shape (typed/duck-typed live-attribute
  assumption). Run `sweep-pattern` for the `get_object_by_guid`-on-live-target class
  and the `IFsClosedFeature`-bare-cast class, record results under "Pattern audit"
  (4 sites: categories.py:4887,4898,4947,4965).

## Code Quality: 19/25
Well-commented, traceable to research.md. `_run_tail_once` uses narrow
`except (AttributeError, TypeError)` — good contrast to the broad excepts elsewhere.
Issue: `_resolve_target_by_guid` (~5006-5015) and the type-guard (~675-677) both fold
heterogeneous failure modes into one outcome, undermining the file's fail-loud posture
(contrast the explicit `raise RuntimeError` at ~716-719).

## Standards Compliance: 20/25
Consistent with file conventions. Minor: `noqa: BLE001` inconsistently applied and
inert — `pyproject.toml` ruff `select` has no BLE rule, so the pragma suppresses nothing.

## Error Handling: 16/25
**P1** ~5014 — bare `except Exception` in `_resolve_target_by_guid` folds
`ImportError`/bad-Guid/`GetObject` failure into `return None` → `Skip(DEPENDENCY_UNRESOLVED)`.
An infra break (renamed `ICmObjectRepository` accessor) would silently look like "GUID
absent" with zero diagnostic signal.
**P1** ~676-677 — the `IFsClosedFeature(src_feat)` guard catches bare `Exception`, not the
specific cast-failure; a non-type-related failure gets mislabeled `UNSUPPORTED_LCM_TYPE`.

## Best Practices: 19/25
Cast-and-discard type-probe idiom is acceptable for pythonnet/LCM interop (matches
`diag_infl_features.py`). Skip detail strings mix `key=value` with prose (cosmetic P2).
**P1** `TestResolveTargetByGuid` — 2 of 3 tests re-exercise the pre-existing fake-getter
dispatch; none use a fake `ICmObjectRepository` double, so the new logic (`Guid.Parse` →
`IsValidObjectId` → `GetObject`) is proven only by the attended, unrepeatable
`scratchpad/run031_live.py`. A cheap fake repo class would close this.
**P2** `scratchpad/run031_live.py` fine to keep (matches t037 convention) but hardcodes a
dated backup filename + `Target` path — confirm backup exists before reuse; not a blocker.

## Final Assessment
**Overall Score:** 74/100
**Recommendation:** FIX ISSUES — Pattern-Audit Gate BLOCK takes precedence. Require:
(1) sweep-pattern output for the `get_object_by_guid` and bare-cast shapes, with an
explicit fix-now-or-ticket decision for `_run_171_subpass`/`_run_post_pass_a`;
(2) narrow or log the two broad excepts (P1); (3) add a fake-repo unit test for
`_resolve_target_by_guid`'s live branch (P1).

---
**Reviewed By:** QC Agent (report persisted by main session; agent lacked Write tool)
