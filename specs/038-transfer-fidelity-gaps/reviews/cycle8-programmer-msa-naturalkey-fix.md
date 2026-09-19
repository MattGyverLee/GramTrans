# Cycle 8 — T123(a) fix: MSA create-or-reuse, never a silent null

Tree: `D:\Github\_Projects\_LEX\GramTrans-038-transfer-fidelity-gaps`
(`038-transfer-fidelity-gaps`). HEAD unchanged, **not committed**:
`5cf155c39b3b78ddea9333d65b469aaf1ba603b0`. Edits are uncommitted worktree
diffs on top.

## Mechanism found (by reading, not assumption)

`_create_msa_for_closure`'s flexicon-wrapper fallback (`categories.py`, now
~9994–10099; was ~9897–9952 pre-edit) — `target.MSA.CreateStem`/
`CreateInflAff`/`CreateDerivAff`/`CreateUnclassifiedAffix` — was called BARE,
no try/except, whenever `_create_msa_with_guid` returned None. Those
wrappers have their own duplicate-avoidance behaviour and can refuse to mint
a second content-identical MSA on one entry (`omoona`'s two `MoStemMsa`
differ only by GUID). Left unguarded, that refusal propagates uncaught out
of `_walk_lex_entry_closure`'s per-sense loop (also had no try/except) to
`Lib/transfer.py`'s per-ACTION swallow-and-record handler (line 658) —
recorded only as a `LeafExecutionFailure`, never a `DroppedItemRecord`
(confirmed: `_run_reports/038-t123b-ngoreme-report.json`'s 11,080
`dropped_items` has zero hits for guid `8617b725...` or entry
`e2cd79ef...`). Everything already written before the raise (entry, sense,
first MSA) stays live — no rollback exists anywhere in `Lib/*.py`.

## Both halves, and how each is enforced

**Half 1 — a distinct-GUID create is never skipped.** `_walk_lex_entry_closure`'s
per-sense cache (`msa_by_src_guid`, ~8239–8291) was already keyed by the
REAL source guid, not content — confirmed correct by reading and by the new
happy-path test. Hardened: the cache is now only trusted when `m_guid` is
non-empty (an unreadable guid can no longer coalesce two unrelated MSAs),
and the create call is now wrapped in try/except so ANY exception is
reported via `_report_dropped_msa` and processing continues to the REST of
the entry's senses/allomorphs/refs instead of aborting the whole closure.

**Half 2 — the referent never ends null when a resolution exists.** New
`_create_via_wrapper_or_reuse` (categories.py, before `_create_msa_for_closure`,
~9791–9858) wraps all four wrapper calls. On exception: try
`_find_reusable_target_msa` (~9751–9789) — scans `new_entry.MorphoSyntaxAnalysesOC`
for an existing MSA matching by subclass + every `pos_fields` GUID; if found,
reuse it (records `identity_remap[src_g] = reused_guid` via the existing
post-branch code, unchanged). Only when nothing matches does it call
`_report_dropped_msa` and return None. `_create_msa_for_closure` itself
never raises past this point; `_walk_lex_entry_closure`'s unconditional
`new_sense.MorphoSyntaxAnalysisRA = new_msa` (unchanged, ~8306) then wires
whatever came back. The `_POS_ABSENT` sentinel path (`_null_pos_fallback_blocked`)
is untouched — still returns None+report before reaching the wrapper,
correctly distinct from a resolved-POS wrapper failure.

## Siblings swept

- Grepped all `target.MSA.Create*`/`MSAOperations` call sites in
  `Lib/categories.py`: the four just fixed were the ONLY unguarded ones.
- `_create_owned_msa` (compound-rule member/result MSAs, ~4785–4818):
  reviewed — different shape (owned-attribute `Create(Guid)` + generic
  `except Exception: pass`), no natural-key/content dedup involved. Not this
  family. **LATENT, claimed as nothing** — not swept, not counted.
- `_walk_entry_allomorphs._mk` (~9525–9613): reviewed — 1:1 GUID-preserving
  create per allomorph, no cross-object cache, no wrapper-fallback dedup.
  `except Exception: return` there is a separate, pre-existing silent-drop
  shape (worth a future task) but not a match-by-key skip. Not this family.
- `_resolve_target_lex_ref_type` (T123's own recent LexRefType work, HEAD
  commit `5cf155c`): already reports on ambiguity/absence via `_append_dropped_once`,
  already raises loudly if `dropped is None`. Not a sibling — already closed.

## Tests

`tests/unit/test_038_t123_msa_naturalkey_reuse.py` (new, 4 tests):
- `test_two_content_identical_msas_both_arrive_under_their_own_guid` — (a):
  two GUID-distinct, content-identical `MoStemMsa` both create, both
  non-null, `is not` each other.
- `test_wrapper_raise_reuses_an_existing_match_instead_of_going_null` — (b):
  create leg fails, wrapper raises, existing match reused, non-null.
- `test_wrapper_raise_with_no_match_anywhere_reports_rather_than_crashes`:
  no match anywhere → reported drop, no exception escapes.
- `test_reuse_requires_matching_pos_not_just_matching_subclass`: guards
  against a wrong-POS false-positive reuse.

`tests/unit/ -q`: **3892 passed, 79 skipped, 14 xfailed** (comparand 3888 +
4 new = 3892; skip/xfail counts unchanged). Full unit dir, not bare
`pytest tests/`.

## Acceptance (unchecked — needs a live re-census, not yet authorized)

T123 stays unchecked until measured: `MoStemMsa` 1951 = 1951 **and** zero
senses with a null `MsaRA` whose source counterpart had one **and**
destination extra count = 0. This session made no live LCM writes, ran no
transfer, opened no FLEx project.
