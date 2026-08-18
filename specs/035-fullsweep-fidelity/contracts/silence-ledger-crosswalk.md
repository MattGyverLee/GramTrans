# Contract: Anti-Silence Acceptance Surface -- S-01..S-65 Crosswalk

**Feature**: `035-fullsweep-fidelity`
**Authority**: `spec.md`, "Anti-Silence Acceptance Surface"; ledger source is
`reviews/cycle1-qc.md` Section 1 (S-01 through S-65)

The spec makes this an acceptance condition: before the feature is delivered,
**every one of the 65 rows must be verifiably satisfied by the delivered sweep,
or explicitly waived on the record**. A plan or task review that does not address
every row is incomplete.

**Waivers: none. All 65 rows are satisfied.**

Instrument abbreviations from the ledger: **RFL** = `scratchpad/run_fullcopy_live.py`
(retired), **RFV** = `debug/run_fullsweep_verify.py`, **AGP** =
`debug/audit_guid_preservation.py`, **FR:** = `tests/integration/harness/full_run.py`.

Module names are in `debug/fullsweep/` unless otherwise qualified.

---

## Block 1: the retired breadth driver (S-01..S-18)

| S | What it hid | Satisfied by | Where | Test |
|---|---|---|---|---|
| S-01 | Move #1 adding literally nothing | `BASELINE-DELTA` guard | `guards.py` | `test_035_guards.py` |
| S-02 | All loss, via exit-code collapse to 0 | Ten-verdict model; `DROPS_REPORTED` retired | `verdict.py` | `test_035_verdict_order.py` |
| S-03 | Drop buckets 21..N (`most_common(20)`) | `NO-TRUNCATION`; full buckets in artifact | `artifact.py`, `guards.py` | `test_035_guards.py` |
| S-04 | The whole persistence proof (`{}` substituted on failure) | `ACCESSOR-INTEGRITY`; accessor failure aborts the project | `guards.py`, `errors.py` | `test_035_guards.py` |
| S-05 | Change in any unmeasured class | `IDEMPOTENCY-IN-WRITTEN-CLASSES` over the derived written set | `moves.py`, `guards.py` | `test_035_guards.py` |
| S-06 | Every drop/gap introduced by Move #2 | Verdict aggregates both moves; move-2 drop set must equal move-1's | `moves.py`, `verdict.py` | `test_035_verdict_order.py` |
| S-07 | Duplicate adds (`got > planned` unchecked) | `PLAN-CONSERVATION`, both directions | `guards.py` | `test_035_guards.py` |
| S-08 | A changed result shape silently reporting 0 | Direct attribute access; `AttributeError` is a harness error | `moves.py`, `errors.py` | `test_035_guards.py` |
| S-09 | Actions with an unreadable category | Unresolvable category is a harness error, never a `""` bucket | `census.py`, `errors.py` | `test_035_compare.py` |
| S-10 | A wrong baseline silently restored | Baseline pinned by name + SHA-256; `--baseline-sha256` required; no glob | `baseline.py` | `test_035_sweep_safety.py` |
| S-11 | Unflushed writes read back as a stale count | `CLEAN-CLOSE`; close failure/timeout invalidates all later measurement | `guards.py` | `test_035_guards.py` |
| S-12 | A skipped project indistinguishable from a never-run one | Always write a `SKIPPED` artifact with reason before returning | `artifact.py` | `test_035_guards.py` |
| S-13 | The durable artifact, while reporting success | Artifact write failure is fatal and nonzero | `artifact.py`, `errors.py` | `test_035_guards.py` |
| S-14 | All evidence, on a mid-run crash | Flush after every phase; partial artifact names the last completed phase | `artifact.py` | `test_035_guards.py` |
| S-15 | Which phase failed | Per-phase try/except; every loud record names its `phase` | `errors.py`, `artifact.py` | `test_035_guards.py` |
| S-16 | Log lines, on a dead reporter | Retained for prose ONLY; asserted never to carry verdict data | `__init__.py` | `test_035_guards.py` |
| S-17 | Diagnostics silently off when the caller pre-set 0 | `--diagnostic-level` set explicitly; effective value recorded | `run_fullcopy_sweep.py`, `artifact.py` | `test_035_guards.py` |
| S-18 | 29,211 drops as a non-failure by definition | `DROPS_REPORTED` retired (FR-112); loss is allowlisted or it fails | `verdict.py` | `test_035_verdict_order.py` |

## Block 2: the deep verifier (S-19..S-38)

| S | What it hid | Satisfied by | Where | Test |
|---|---|---|---|---|
| S-19 | A pre-populated baseline yielding INTACT without any transfer | Target BEFORE-inventory; `after - before` must be non-empty | `moves.py`, `guards.py` | `test_035_guards.py` |
| S-20 | Duplicate/minted target objects in all 8 domains | `NO-EXTRA`; `extra` fails unless allowlisted target-native | `guards.py`, `allowlist.py` | `test_035_allowlist.py` |
| S-21 | All reported loss (drops collected, never read) | `TOTAL-ACCOUNTING`; the drop set gates the verdict | `guards.py` | `test_035_guards.py` |
| S-22 | Every GUID-read failure collapsing into one `None` key | GUID read failure is a harness error; inventories are never keyed by `None` | `census.py`, `errors.py` | `test_035_compare.py` |
| S-23 | A real name difference comparing `""` to `""` | Sentinel `<NAME-UNREADABLE>`, counted; nonzero is a harness error | `census.py` | `test_035_compare.py` |
| S-24 | Entire affix and feature domains empty, hence INTACT | `EMPTY-CORROBORATION`; an empty source domain must be corroborated | `guards.py` | `test_035_guards.py` |
| S-25 | Features empty, hence vacuous INTACT | Same as S-24; a null owning collection on the SOURCE is a harness error | `guards.py` | `test_035_guards.py` |
| S-26 | Complex-feature values never inventoried | `UNHANDLED-SUBTYPE`; cast failure classified and counted, never emptied | `compare.py` | `test_035_compare.py` |
| S-27 | Two different negated/complex values comparing equal | Concrete value representation recorded; unrepresentable counted `unreadable` | `census.py` | `test_035_compare.py` |
| S-28 | Source affixes never entering the inventory | Every skip counted by cause as `skipped_source_objects`; must be 0 | `census.py`, `guards.py` | `test_035_guards.py` |
| S-29 | An MSA whose feature read failed silently | Subtype classified up front; an unhandled subtype is a harness error | `compare.py` | `test_035_compare.py` |
| S-30 | Detail for losses 11..N | Full detail always in the artifact; console truncation only, with `(+N more)` | `artifact.py` | `test_035_guards.py` |
| S-31 | That the printed detail was meaningless (dead key) | Print the real source detail dict | `artifact.py` | `test_035_compare.py` |
| S-32 | Same as S-03 (`most_common(12)`) | Same as S-03 | `artifact.py` | `test_035_guards.py` |
| S-33 | Every LCM class outside a fixed 8-domain tuple | Domain set DERIVED from the enabled selection; `CATEGORY-COVERAGE` asserts cover | `coverage.py`, `guards.py` | `test_035_guards.py` |
| S-34 | Move #2 duplication in any unmeasured class | Idempotency over the written-class set | `moves.py`, `guards.py` | `test_035_guards.py` |
| S-35 | A dirty target and zero evidence on any exception | try/finally; always restore; always write the artifact, including on failure | `moves.py`, `artifact.py` | `test_035_sweep_safety.py` |
| S-36 | Which domain actually failed, in the console record | Real domain label printed | `artifact.py` | `test_035_compare.py` |
| S-37 | Move #2 drops, skips or gaps | Full move-2 comparison (see S-06) | `moves.py` | `test_035_guards.py` |
| S-38 | Writing-system data unavailable; unflushed handles | `HANDLE-INTEGRITY`; auxiliary-service init failure is a harness error | `guards.py` | `test_035_guards.py` |

## Block 3: the GUID auditor (S-39..S-49)

| S | What it hid | Satisfied by | Where | Test |
|---|---|---|---|---|
| S-39 | **`source_missing` never failing** -- the single most important row | `TOTAL-ACCOUNTING`: a missing source object fails unless allowlisted | `guards.py` | `test_035_guards.py` |
| S-40 | A Move that created nothing at all | `BASELINE-DELTA`, including the `>= 0.5 * plan.actions` floor | `guards.py` | `test_035_guards.py` |
| S-41 | Field-level loss on pre-existing target objects, by construction | The generic field census over classes present on BOTH sides | `census.py`, `compare.py` | `test_035_compare.py` |
| S-42 | A preserved GUID carrying an empty or garbage payload | `preserved` requires identity AND property equality | `compare.py`, `guards.py` | `test_035_compare.py` |
| S-43 | Objects whose class/GUID read throws vanishing from all three sides | Enumeration failures counted; nonzero is a harness error | `census.py`, `guards.py` | `test_035_guards.py` |
| S-44 | A dependency shape change quietly taking a different code path | Preflight pins the repository-access shape; no runtime branching | `preflight.py` | `test_035_sweep_safety.py` |
| S-45 | Planned-but-unexecuted actions | `PLAN-CONSERVATION`: `actions == added + skipped` | `guards.py` | `test_035_guards.py` |
| S-46 | A mixed minted/missing case losing its flag | Flag on `minted > 0 AND missing > 0`; both counts reported | `compare.py` | `test_035_compare.py` |
| S-47 | Which specific objects were regenerated | Full identifier lists in the artifact; sampling in the console only | `artifact.py` | `test_035_guards.py` |
| S-48 | A dirty target and zero evidence on any exception | Same as S-35 | `moves.py`, `artifact.py` | `test_035_sweep_safety.py` |
| S-49 | Unflushed writes invalidating the AFTER inventory | Same as S-11 and S-38 | `guards.py` | `test_035_guards.py` |

## Block 4: the integration harness (S-50..S-60)

| S | What it hid | Satisfied by | Where | Test |
|---|---|---|---|---|
| S-50 | The headline lexicon metric, permanently, in every run ever recorded | Accessor deleted with `reopen_and_count`; preflight pins `FLExProject.LexiconNumberOfEntries` (NOT `FLExProject.lexicon`) | `preflight.py`; deletion in `full_run.py` | `test_035_sweep_safety.py` |
| S-51 | Any accessor failing or returning a non-int, with no error field | Accessor failure is a harness error with label, type and traceback; the "survive API drift" posture is deleted | `guards.py`, `errors.py` | `test_035_guards.py` |
| S-52 | Loss in 26 of ~28 categories (3 accessors only) | One measurement per in-scope category, derived from the selection | `coverage.py`, `census.py` | `test_035_guards.py` |
| S-53 | Phonemes unmeasured on any project without a phoneme set | `EMPTY-CORROBORATION`: "collection absent" is an outcome distinct from "count == 0" | `guards.py` | `test_035_guards.py` |
| S-54 | That STEMS is never tested, with no artifact recording the exclusion | `--exclude-categories` is a required explicit argument, recorded; non-empty forces `COVERAGE_REDUCED` | `run_fullcopy_sweep.py`, `coverage.py` | `test_035_guards.py` |
| S-55 | A selection that silently walks nothing | `COMPARISONS-PERFORMED`: `len(plan.actions) > 0` per enabled category present in source | `guards.py` | `test_035_guards.py` |
| S-56 | Same as S-17 | Same as S-17 | `run_fullcopy_sweep.py` | `test_035_guards.py` |
| S-57 | Unflushed writes read back as loss or spurious equality | Same as S-11 | `guards.py` | `test_035_guards.py` |
| S-58 | A leaked source handle locking the project for the next iteration | `HANDLE-INTEGRITY`; a leaked handle fails the run before the next project starts | `guards.py`, `pool.py` | `test_035_guards.py` |
| S-59 | A loss in one metric offset by a gain in another | Aggregates are never compared; `BASELINE-DELTA` is per-label | `guards.py` | `test_035_guards.py` |
| S-60 | (GOOD) source open raising an actionable `RuntimeError` | **Adopted as house style** for the whole package, not kept as a local exception | `errors.py` (all modules) | `test_035_guards.py` |

## Block 5: engine and provenance (S-61..S-65)

| S | What it hid | Satisfied by | Where | Test |
|---|---|---|---|---|
| S-61 | A second, different failure on the same `(owner, field, item)` triple | Drop-record dedup key WIDENED to include `reason`; independently, `TOTAL-ACCOUNTING` reconciles source against target so drop records are corroborating detail, not the primary channel | `compare.py`, `guards.py` | `test_035_compare.py` |
| S-62 | API misuse becoming a loss statistic | Engine-bug signature roster: a matching reason is `ENGINE_BUG`, NOT allowlistable, forces nonzero (`NO-ENGINE-BUG-AS-LOSS`) | `allowlist.py`, `guards.py` | `test_035_allowlist.py` |
| S-63 | A project marked done with no artifact | Ledger `status` DERIVED from artifact presence and content, never hand-set; missing artifact is `INCOMPLETE` | `batch.py`, `guards.py` | `test_035_guards.py` |
| S-64 | That the instrument itself changed between runs; no provenance | The driver is TRACKED under `debug/fullsweep/`; every artifact records the driver git SHA plus a dirty-tree flag | `debug/fullsweep/` (all), `artifact.py` | `test_035_sweep_safety.py` |
| S-65 | Residue from a previous iteration persisting into the next baseline | Post-restore state verified against the backup's member list; baseline fingerprint recorded on the artifact | `baseline.py` | `test_035_sweep_safety.py` |

---

## Coverage summary

| Block | Rows | Satisfied | Waived |
|---|---|---|---|
| 1 -- retired breadth driver | S-01..S-18 (18) | 18 | 0 |
| 2 -- deep verifier | S-19..S-38 (20) | 20 | 0 |
| 3 -- GUID auditor | S-39..S-49 (11) | 11 | 0 |
| 4 -- integration harness | S-50..S-60 (11) | 11 | 0 |
| 5 -- engine and provenance | S-61..S-65 (5) | 5 | 0 |
| **Total** | **65** | **65** | **0** |

## How this is enforced, not just asserted

`tests/unit/test_035_silence_ledger.py` parses this document, asserts the row set
is exactly `S-01` through `S-65` with no gaps and no duplicates, and asserts every
row names a module that exists and a test file that exists. A row added to the
ledger without a satisfying module and test fails the suite -- so this crosswalk
cannot rot into a list of intentions.
