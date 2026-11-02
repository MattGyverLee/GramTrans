# Issue #132 — key-matched PhNCSegments SegmentsRC — lex-lead cycle 1 (final)

## Diagnosis

**Issue selection:** No open **P0** bugs. The only open **P1** without an open PR is **#22** (conflict-mode epic — not a bounded fix). Selected **#132** (P2 never-silent audit; issue closed, acceptance still lists open sites) — **`_wire_matched_nc_segments` `SegmentsRC.Add` with no failure channel** (`impl-111` §5).

After phoneme create, the pass unions source members into key-matched starter `PhNCSegments`. Unresolvable phonemes already emit `DroppedItemRecord`. A resolved phoneme whose `SegmentsRC.Add` raises (`TypeError` from pythonnet, etc.) used to bubble to `_ensure_matched_nc_segments` as a whole-pass failure—or, on a no-op Add, leave the class short a member with no drop.

## Resolution

- Add `_try_add_nc_segments_rc_member`: warning log + deduped `DroppedItemRecord` on `Add` failure; read-back via `_collection_already_has` so a no-op Add is not counted as success.
- Route `_wire_matched_nc_segments` member wiring through the helper.

## Verification

- `tests/unit/test_issue132_nc_segments_add.py` (2 tests, new)

**Verdict: GO** — refs #132.
