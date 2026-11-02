# Issue #177 — lex-lead cycle 1 (final)

## Diagnosis

Open P0/P1 bugs without an open PR: none (#22 is P1 but PR #225 is open; #61 is closed).

Selected **#177** (P3 test-infrastructure bug, no open PR).

Live integration modules under `tests/integration/*_live.py` only carried `pytest.mark.integration`, so `pytest -m requires_live_project` collected nothing — crews had to run live gates by file path only (batch 128–136 verification notes). That breaks the intended live-selection contract and makes it easy to add a new `*_live.py` without opting into the gate.

Secondary gaps from the same issue: #154’s live gate prints the STEMS `DEPENDENCY_UNRESOLVED` skip count (2) but never asserts it; #156’s equal-set OVERWRITE no-op is unit-proven only.

## Resolution

- Register `requires_live_project` in `pyproject.toml` and skip those tests unless `FLEXLIBS_REQUIRE_LIVE=1` (centralized in root `conftest.py`).
- Mark every `tests/integration/*_live.py` module with `integration` + `requires_live_project`; remove redundant per-module `FLEXLIBS_REQUIRE_LIVE` module skips where the hook replaces them.
- Add `tests/unit/test_issue177_live_module_markers.py` to fail if any `*_live.py` omits the marker.
- Assert `len(stem_skips) == 2` in `test_issue128_affixes_only_live.py`.
- Add `test_equal_membership_overwrite_is_noop` in `test_issue130_overwrite_slots_live.py` for live equal-set behaviour.

## Verification

- `python -m pytest tests/unit/test_issue177_live_module_markers.py -q`
- `python -m pytest tests/unit/test_issue128_affixes_only.py tests/unit/test_issue130b_unwrap_root.py -q`

Live gates (when FieldWorks + `FLEXLIBS_REQUIRE_LIVE=1`):

- `tests/integration/test_issue128_affixes_only_live.py`
- `tests/integration/test_issue130_overwrite_slots_live.py` (new test)

**Verdict: GO** — closes #177.
