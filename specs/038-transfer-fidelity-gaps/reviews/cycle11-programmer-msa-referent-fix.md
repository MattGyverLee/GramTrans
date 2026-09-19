# Cycle 11 — T123(a) referent-wiring fix + test repair

Tree: `D:\Github\_Projects\_LEX\GramTrans-038-transfer-fidelity-gaps`, branch
`038-transfer-fidelity-gaps`, HEAD `73552e47231c4e40ddffaca7ce4da6a635e10d37`
(unchanged — NOT COMMITTED). Edits: `src/gramtrans/Lib/categories.py`,
`tests/unit/test_038_t123_msa_naturalkey_reuse.py`.

## Deliverable 1 — every path out of `_create_via_wrapper_or_reuse` now wires

Anchors (this HEAD): `_create_via_wrapper_or_reuse` def line 9870 (was 9854
pre-edit — line numbers shift with each edit); `_find_reusable_target_msa`
9823; `_create_msa_with_guid` 9748; `_create_msa_for_closure` 9948;
`_walk_lex_entry_closure` 8038.

Three creation legs, now all wiring `new_sense.MorphoSyntaxAnalysisRA`
before returning:
1. **GUID-preserving create** (`_create_msa_with_guid`) — already wired
   internally (pre-existing, unchanged).
2. **Fresh create via wrapper** (`create_fn()` succeeds inside
   `_create_via_wrapper_or_reuse`) — previously returned the wrapper's
   result and left wiring entirely to the caller. Now explicitly sets
   `new_sense.MorphoSyntaxAnalysisRA = new_msa` before returning.
3. **Legitimate reuse** (`_find_reusable_target_msa` match after a wrapper
   raise) — this was the unwired leg. Same explicit assignment now runs
   here too.

Added a `new_sense=None` parameter to `_create_via_wrapper_or_reuse`; all 4
call sites in `_create_msa_for_closure` (MoInflAffMsa/MoStemMsa/
MoDerivAffMsa/MoUnclassifiedAffixMsa) now pass `new_sense=new_sense`. If the
wiring assignment itself raises, it is reported via `_report_dropped_msa`
and the function returns `None` (never a silent success with a dangling
sense). Also hardened `_walk_lex_entry_closure`'s own post-call wiring
(same-guid cache-hit case, the only wiring step for two senses sharing one
literal source MSA guid): `except (AttributeError, TypeError): pass` →
reports a drop via `_report_dropped_msa` instead of swallowing.
`_POS_ABSENT`/`None` POS semantics and the 13 legitimately-null source
senses are untouched — no code path affecting POS resolution changed.

## Deliverable 2 — why the gate passed, and the repair

**Fake fidelity, not an unreached path.** The pinning test
`test_wrapper_raise_reuses_an_existing_match_instead_of_going_null` DID
call real production code (`_create_msa_for_closure` → `_create_via_wrapper_or_reuse`
→ `_find_reusable_target_msa`) and correctly exercised the reuse leg. But
after getting `out is existing`, the test itself executed
`sense.MorphoSyntaxAnalysisRA = out` and only then asserted it was set —
performing the wiring it claimed to verify. The assertion could not fail
regardless of what production code did to `sense`.

**Repair:** removed the self-wiring line; the test now reads
`sense.MorphoSyntaxAnalysisRA` untouched after `_create()` returns. Added a
second test, `test_reuse_wiring_failure_is_reported_not_silently_dropped`,
covering the new wiring-failure-must-report branch.

**Verified fail-then-pass**, isolating the test change from the code
change (`git show HEAD:src/gramtrans/Lib/categories.py` swapped in
temporarily, restored after):
- Against 73552e4's original `categories.py`: 2 failed
  (`test_wrapper_raise_reuses_an_existing_match_instead_of_going_null`,
  `test_reuse_wiring_failure_is_reported_not_silently_dropped`), 3 passed.
- Against this fix: 5/5 passed.

## Test counts (fixed code)

`tests/unit/test_038_t123_msa_naturalkey_reuse.py`: 5 passed.
`tests/unit/`: **3895 passed**, 79 skipped, 14 xfailed (comparand 3894 + 1
new test = 3895; no regressions).

## State

T123 acceptance still needs a **live re-census (tag t123d)** — this fix is
unverified against real LCM/flexicon behavior, only against duck-typed
fakes. T123 stays unchecked.
