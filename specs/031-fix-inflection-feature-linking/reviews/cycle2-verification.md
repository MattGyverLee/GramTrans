# Cycle 2 Verification Report — Feature 031 (fix-inflection-feature-linking)

**Date:** 2026-07-13
**Worktree:** D:\Github\_Projects\_LEX\GramTrans-031-fix-inflection-feature-linking
**Commit under review:** b5cd49b ("031 cycle-1 review Actions 2-3: log broad excepts, add live-repo GUID test")
**Status:** PASS

## 1. Offline suite regression check

Command: `python -m pytest tests/unit -q -m "not integration"` (run from the worktree).

Result: **1535 passed, 1 failed, 1 skipped, 8 deselected, 14 xfailed, 14 xpassed**.

- Matches expectation: baseline 1532 passed + 3 new tests = 1535 passed. Confirmed.
- The sole failure is `tests/unit/test_wizard_pos_grammar_wiring.py::TestPosClosureWalksPickedPos::test_plan_emits_pos_action_for_picked_pos` (`assert len(pos_actions) == 1` -> `assert 0 == 1`). This is the same module/test named as the pre-existing baseline failure — no new failures introduced, count of failures is exactly 1 as before.

**Status: PASS** — no regressions.

## 2. New fake-repo test: `TestResolveTargetByGuidLiveRepo`

Location: `tests/unit/test_031_infl_feature_linking.py` lines 241-325.

Read the test body directly. It stubs `sys.modules["SIL.LCModel"]` (fake `ICmObjectRepository`) and `sys.modules["System"]` (fake `Guid.Parse`) via an autouse fixture, then defines `_FakeLiveTarget` (exposes only `ObjectRepository(iface)`, no `get_object_by_guid` — mirroring the live flexicon `FLExProject` and forcing execution past the offline-fake short-circuit) and `_FakeRepo` (controllable `IsValidObjectId` / `GetObject`).

Three sub-tests, each confirmed to exercise the intended branch of `_resolve_target_by_guid` in `src/gramtrans/Lib/categories.py`:
- `test_invalid_object_id_returns_none` — repo `IsValidObjectId=False` -> asserts return is `None` AND `repo.get_calls == []` (proves `GetObject` is never called on the invalid-id path).
- `test_valid_id_returns_get_object_result` — repo `IsValidObjectId=True` -> asserts returned object `is expected` (the exact object `GetObject` returns) and `repo.get_calls == [("parsed", "aaaa")]` (proves `Guid.Parse` result is what's passed to `GetObject`).
- `test_guid_parse_raising_returns_none` — monkeypatches `Guid.Parse` to raise `ValueError` -> asserts return is `None` and `repo.get_calls == []` (proves the outer `except Exception` in `_resolve_target_by_guid` catches the parse failure before any `GetObject` call).

All three ran green in the Section 1 pytest invocation above (part of the +3 new tests / 1535 total).

**Status: PASS** — all three branches (invalid-id, valid-id, Guid.Parse-raises) are genuinely exercised, not just declared.

## 3. Log-before-swallow calls in categories.py do not alter control flow

Diff reviewed via `git show b5cd49b -- src/gramtrans/Lib/categories.py`.

**Site A — `_resolve_target_by_guid`** (around line 5021):
```python
except Exception as exc:  # noqa: BLE001 -- absent repo / bad guid -> unresolved
    import logging as _logging
    _logging.getLogger("gramtrans.Lib.categories").warning(
        "_resolve_target_by_guid: live LCM resolution failed for guid %s "
        "-- treating as unresolved: %s",
        guid, exc, exc_info=True,
    )
    return None
```
Prior behavior (`except Exception: return None`) is unchanged — the only addition is the `warning(...)` call before the pre-existing `return None`. Exception variable capture (`as exc`) does not change which exceptions are caught (still bare `Exception`).

**Site B — `inflection_features_execute_action`** (around line 674-690):
```python
except Exception as _cast_exc:
    ...
    _logging.getLogger("gramtrans.Lib.categories").warning(
        "inflection_features_execute_action: IFsClosedFeature(src_feat) "
        "cast failed for source feature %s (class=%s) -- treating as "
        "UNSUPPORTED_LCM_TYPE: %s",
        src_guid, _src_cls, _cast_exc, exc_info=True,
    )
    exec_skips = getattr(context, "_exec_skips", None)
    if exec_skips is not None:
        exec_skips.append(Skip(... reason=SkipReason.UNSUPPORTED_LCM_TYPE ...))
```
Prior behavior (compute `_src_cls`, append `Skip(UNSUPPORTED_LCM_TYPE)` to `exec_skips`) is unchanged — the log call is inserted between computing `_src_cls` and appending the Skip; the Skip append logic and its `reason=UNSUPPORTED_LCM_TYPE` are untouched.

**Status: PASS** — both additions are strictly log-only insertions before the pre-existing `return None` / `Skip(UNSUPPORTED_LCM_TYPE)` outcomes; no control-flow, return-value, or Skip-reason changes. No live LCM run was needed or performed for this check (static diff review sufficient).

## Overall Assessment

**Overall Status: PASS**

All three verification items confirmed:
1. Offline suite green: 1535 passed, exactly 1 pre-existing failure (`test_wizard_pos_grammar_wiring.py`), no new failures.
2. `TestResolveTargetByGuidLiveRepo` genuinely exercises all three target branches (invalid-id->None, valid-id->GetObject, Parse-raises->None) with call-count assertions proving branch discrimination, not just line coverage.
3. Both new logging calls are pure log-before-swallow insertions; control flow, return values, and Skip reasons are identical to before.

**Recommendation:** APPROVE.

---
**Verified By:** Verification Agent
**Date:** 2026-07-13
