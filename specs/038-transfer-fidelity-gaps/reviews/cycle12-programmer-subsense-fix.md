# Cycle 12 — T123(a) root-cause fix: MSA wiring now recurses into subsenses

Tree: `D:\Github\_Projects\_LEX\GramTrans-038-transfer-fidelity-gaps`
(branch `038-transfer-fidelity-gaps`), HEAD `3ef3c5b0971bdfbc03452067dd65299f5e7f695f`
(uncommitted working-tree edit only, per instructions — not committed).

## The fix

`categories.py:8038 _create_and_wire_sense_msa` — the old inline per-sense
MSA create-and-wire block extracted verbatim (unchanged logic, only its
reach changed). `categories.py:8122 _wire_subsense_msas` — new: recurses
into `src_parent_sense.SensesOS` at any depth, looks up each subsense's
already-created target object via `copy_set` (never creates one itself —
`owned.walk_owned_children`'s `recurse=True` leg already did that and
registered it), and hands it to `_create_and_wire_sense_msa`, sharing the
entry's one `msa_by_src_guid` cache.

`_walk_lex_entry_closure`'s sense loop (`:8173`) now calls, per top-level
sense: `_owned.walk_owned_children(src_sense, new_sense, ...)` then
`_wire_subsense_msas(...)` (`:8342`) — creates+registers subsenses, then
wires their MSAs — followed later in the same iteration by
`_create_and_wire_sense_msa(src_sense, ...)` (`:8392`) for the top-level
sense itself. Same shared `msa_by_src_guid`, so one source MSA guid is
created once regardless of depth or visit order.

## Hardening backstop (`_create_entry_owned_msas_without_sense`, `:10290`)

Chose **exclude, with a defense-in-depth flag** rather than exclude-only:
`msa_by_src_guid` now legitimately contains every sense-reachable MSA
before this pass runs, so the existing `if m_guid in msa_by_src_guid:
continue` already excludes them. Added
`_entry_sense_reachable_msa_guids` (`:10261`) — an INDEPENDENT recursive
scan of the source sense tree, not a re-read of `msa_by_src_guid` — so a
future regression reintroducing a non-recursive sense walk can never again
present as a clean count: an MSA that IS sense-reachable but reaches this
backstop unclaimed is now logged (`.error`) and reported via
`_report_dropped_msa` before being created parentless. Docstring corrected:
the old "MEASURED EMPTY" claim was false on this corpus (the one true
instance was this defect's own object); replaced with an explicit
retraction and a note that true emptiness is a claim for the pending t123e
re-census, not this commit.

## Tests — `tests/unit/test_038_t123a_subsense_msa_wiring.py` (3 new)

Drive the REAL, unmodified `owned.walk_owned_children` plus the two new
production functions `categories._wire_subsense_msas` and
`categories._create_and_wire_sense_msa`, in the exact order
`_walk_lex_entry_closure` runs them (confirmed by reading the call sites
above — no unit test drives `_walk_lex_entry_closure` itself anywhere in
this repo; it is LCM-bound end-to-end, documented precedent in
`test_038_t123_msa_naturalkey_reuse.py`/`test_038_t123_msa_entry_owned_no_sense_latent.py`).

- `test_subsense_own_msa_is_created_and_wired` (acceptance a)
- `test_shared_msa_across_depths_creates_exactly_one` (acceptance b)
- `test_subsense_with_no_source_msa_stays_null` (acceptance c)

**Fail-against-3ef3c5b**: `git stash push -- src/gramtrans/Lib/categories.py`
(isolates categories.py only), ran the file → all 3
`AttributeError: module 'gramtrans.Lib.categories' has no attribute
'_wire_subsense_msas'` — genuinely falsifiable, and this failure mode
proves the RECURSION MECHANISM itself is new, not just a create-path
detail (the cycle-11 gap). `git stash pop` restored the fix.

**Pass-against-fix**: all 3 green (`pytest
tests/unit/test_038_t123a_subsense_msa_wiring.py -v` → `3 passed`).

## Full suite

`pytest tests/unit/ -q` → **3898 passed, 79 skipped, 14 xfailed** (comparand
3895 passed + 3 new = 3898, exact match). One unrelated `Windows fatal
exception: access violation` appeared inside `test_034_prereq_report.py`'s
live `FLExInitialize` probe on one run (pre-existing environmental hazard,
unrelated file, both runs still reported the same final pass count with
exit 0).

## Status

T123 stays **unchecked**. Acceptance requires a live restore-bounded
re-census (tag **t123e**): destination null-`MsaRA` == source's 13,
`MoStemMsa` 1954 = 1954 not regressing, destination extra 0.
