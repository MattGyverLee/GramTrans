# Cycle 1 QC -- adversarial audit of the existing fidelity instruments

Feature: 035-fullsweep-fidelity. Reviewer: QC (adversarial). Mode: READ-ONLY,
no code changed. ASCII only.

Instruments audited (abbreviations used throughout):

| Abbrev | File | Tracked? |
|---|---|---|
| RFL | `scratchpad/run_fullcopy_live.py` | NO (`.gitignore:117 scratchpad/`) |
| RFV | `debug/run_fullsweep_verify.py` | yes |
| AGP | `debug/audit_guid_preservation.py` | yes |
| FR  | `tests/integration/harness/full_run.py` | yes |

Evidence read: `scratchpad/fullcopy_results/{Ejagham Mini,Esperanto,Mbugwe
Lizzie}.json` (all mtime 2026-07-20), `scratchpad/fullcopy_FINDINGS.md`,
`scratchpad/fullcopy_manifest.json`, `src/gramtrans/Lib/models.py`,
`src/gramtrans/Lib/texts.py`, `src/gramtrans/Lib/owned.py`,
`tests/integration/harness/restore.py`, and the flexicon working tree.

Headline: **none of the four instruments can fail on data loss alone.** RFL
exits 0 with 29,211 drops; RFV's verdict never reads `dropped_items`; AGP's
verdict never reads `source_missing`. All three PASS on an empty measurement.

---

## 0. Seed verification (all eight confirmed; two are worse than reported)

| Seed | Verdict | Citation and correction |
|---|---|---|
| a | CONFIRMED, WORSE | `full_run.py:251-255` `except Exception: continue`. But `full_run.py:226` is `p.lexicon.LexiconNumberOfEntries()` and flexicon's `FLExProject` has **no `lexicon` attribute at all** (`FLExProject.py:263-264` defines `self.lp` / `self.lexDB`; `LexiconNumberOfEntries` is a method **on FLExProject**, `FLExProject.py:3230`). So `entries` has NEVER resolved in ANY run, on any project, ever -- it is permanently dead, not intermittently failing. RFV's own docstring already knows this (`run_fullsweep_verify.py:89-91`) and nobody propagated it. `Ejagham Mini.json` and `Mbugwe Lizzie.json` also show only `pos`+`phonemes`. |
| b | CONFIRMED | `Esperanto.json:45-56` -- the entire persistence proof is `pos`+`phonemes`, 2 ints, against `dropped_items: 29211`. Of ~28 `GrammarCategory` members (`models.py:27-65`), 2 have any count metric. |
| c | CONFIRMED | `run_fullcopy_live.py:257` `b, p1, p2 = (result["counts_post1"] or {}), (result["counts_post1"] or {}), (result["counts_post2"] or {})`. `b` is bound to `counts_post1`, not `counts_base`, and is never read again. Nothing anywhere verifies Move #1 increased any count. |
| d | CONFIRMED, x2 | `run_fullcopy_live.py:188` `most_common(20)`; also `run_fullsweep_verify.py:316` `most_common(12)`. Neither records the residual count or the number of buckets cut. `Esperanto.json` shows exactly 10 buckets, so nothing was cut *there*, but the JSON cannot prove that -- there is no `dropped_breakdown_truncated` field. |
| e | CONFIRMED | `run_fullcopy_live.py:304` `return 0 if result["verdict"] in ("CLEAN", "DROPS_REPORTED") else 1`, with `:294` setting `DROPS_REPORTED` whenever `dropped > 0`. |
| f | CONFIRMED | `Esperanto.json:6` verdict `SILENT_FAIL`, `:7-44` move1 == move2 byte-for-byte, `:57-60` `move2_added: 146` with `count_deltas: {}`. Root cause of the blindness: `count_deltas` is computed (`:258-261`) only over keys in `counts_post1 | counts_post2`, i.e. `pos` and `phonemes` -- neither of which is in the 146 written categories. |
| g | CONFIRMED (bug since fixed upstream of the artifact) | `Esperanto.json:18`. The swallow chain is `texts.py:1370-1378` `_safe` -> `_log.debug` -> `return None`, then the caller converts it to a `DroppedItemRecord`. `Lib/owned.py:11-27` documents that the `TranslationsOC` row was later REMOVED as the fix. So the tracked artifact now asserts a defect that no longer exists -- staleness cuts both ways. |
| h | CONFIRMED, WORSE | Results mtime 2026-07-20; HEAD is post-034. Coverage is **3 of 77 projects**: `fullcopy_manifest.json` stage `pilot` = 3 (2 done, 1 silent), stage `expansion` = 74 all `pending`. 96% of the corpus has never been run, and nothing in RFL makes an unrun project a failure. |

Two additional findings that outrank several seeds:

* **RFV never inventories the TARGET before the Move** (`run_fullsweep_verify.py:341-351`
  restores then goes straight to Move #1). If the baseline backup already
  contained the source GUIDs, all 8 domains report INTACT and the driver PASSes
  without the transfer having copied anything. There is no BEFORE/AFTER delta
  anywhere in RFV.
* **`DroppedItemRecord` dedup drops distinct reasons** -- `models.py:1042-1046`:
  the identity key is `(owner_guid, field_name, item_guid)` and "deliberately
  EXCLUDES `reason`". A second, *different* failure on the same triple is
  discarded. Drop counts are therefore a lower bound on distinct failures, and
  every instrument treats them as exact.

---

## 1. SILENCE LEDGER

Format: ID | file:line | mechanism | what it can hide | REPLACEMENT RULE.

### 1a. RFL -- `scratchpad/run_fullcopy_live.py`

| ID | file:line | Mechanism | Can hide | Replacement rule |
|---|---|---|---|---|
| S-01 | RFL:257 | wrong variable binding (`b` = post1, never read) | Move #1 adding literally nothing | Delete `b`; assert `total(counts_post1) > total(counts_base)` per VG-01. |
| S-02 | RFL:304 | exit-code collapse (`DROPS_REPORTED` -> 0) | all loss | Exit code from verdict table in Sec. 3; any unallowlisted drop -> 1. |
| S-03 | RFL:188 | `most_common(20)` truncation | drop buckets 21..N | Emit ALL buckets; add `dropped_breakdown_buckets_total` and `..._omitted` (must be 0) or write full breakdown to a sidecar file. |
| S-04 | RFL:192-198 | `_count` swallows `reopen_and_count` failure, returns `{}` | total loss of the persistence proof; `{}` then makes every delta `{}` | Accessor/reopen failure = `HARNESS_ERROR`, abort the project, record the traceback, nonzero exit. Never substitute `{}`. |
| S-05 | RFL:258-261 | deltas only over keys present in the count dicts | any change in an unmeasured class (the 146 of seed f) | Idempotency must be measured over the SAME class set the transfer wrote (VG-05), not over 2 hand-picked accessors. |
| S-06 | RFL:284,288 | verdict reads `move1` only | every drop, gap and regression introduced by Move #2 | Verdict aggregates BOTH moves; move2 drop-set must equal move1's or fail. |
| S-07 | RFL:169-177 | gap test is `got < planned` only | `got > planned`, i.e. duplicate adds | Assert `accounted == planned` exactly; both directions fail. |
| S-08 | RFL:155-161 | `getattr(cr, "added", 0)` / `getattr(cr, "skipped", 0)` defaults | a renamed/changed `CategoryResult` shape silently reporting 0 | Access attributes directly; `AttributeError` = `HARNESS_ERROR`. Defensive defaults forbidden on measurement paths. |
| S-09 | RFL:104-105 | `_cat_name` double `getattr(..., "")` default | actions with an unreadable category collapsing into the `""` bucket | Unresolvable category = `HARNESS_ERROR`. |
| S-10 | RFL:89-101 | `_resolve_backup` falls back to the newest of **any** `*.fwbackup` | a WRONG baseline silently restored; a pre-populated baseline masks loss | Baseline must be pinned by name + SHA-256 in config; a mismatch or absence = `HARNESS_ERROR`, never a glob fallback. |
| S-11 | RFL:136-142 | target `CloseProject` failure downgraded to `[WARN]` | unflushed writes, making the reopen count a stale-file read | Close failure/timeout = `HARNESS_ERROR` for that project (the measurement that follows is invalid). |
| S-12 | RFL:205-207, 208-211 | `return 2` / `return 1` with NO result JSON written | a skipped project being indistinguishable from a never-run one | Always write a `verdict: SKIPPED` artifact with the reason before returning; skipped forces nonzero (Sec. 3). |
| S-13 | RFL:223-227 | `_flush` swallows its own write error | total loss of the durable artifact while the run reports success | Artifact write failure = fatal, nonzero, message to stderr. |
| S-14 | RFL:297 | `_flush()` called once, after everything | a host crash mid-run leaving no evidence at all | Flush after every phase (restore, move1, count1, move2, count2) so a crash leaves a partial artifact with the last completed phase. |
| S-15 | RFL:265-270 | one blanket `except Exception` around the entire 5-phase pipeline | *which phase* failed; phase-level partial success | Per-phase try/except with a `phase` field on every loud record. |
| S-16 | RFL:73-80 | `_say` swallows reporter failure | log lines vanishing (host reporter dead) | Acceptable for prose only; never used for verdict data (already true -- keep it that way and assert it). |
| S-17 | RFL:117 | `os.environ.setdefault(DEBUG_ENV, "1")` | diagnostics silently OFF when the caller pre-set `0` (the Ralph bootstrap does exactly this, `fullcopy_FINDINGS.md:96`) | Set the debug level explicitly and RECORD the effective value in the artifact. |
| S-18 | RFL:294 | `DROPS_REPORTED` framed as "review advisable, not a bug per se" (`fullcopy_FINDINGS.md:9`) | 29,211 drops as a non-failure by definition | Retire the verdict. Loss is either allowlisted or a failure. |

### 1b. RFV -- `debug/run_fullsweep_verify.py`

| ID | file:line | Mechanism | Can hide | Replacement rule |
|---|---|---|---|---|
| S-19 | RFV:341-351 | no TARGET BEFORE-inventory | a baseline that already contains the source GUIDs -> INTACT without any transfer | Inventory target BEFORE and AFTER; require `after - before` to be non-empty and to account for every source object (VG-01, VG-04). |
| S-20 | RFV:246-247 | `intact = not missing and not mismatched` -- `extra` computed then IGNORED | duplicate/minted target objects in all 8 domains | `extra` must fail unless every extra GUID is allowlisted (a target-native object) -- see `EXTRA_ALLOWED` allowlist kind. |
| S-21 | RFV:313-317 + 374-392 | `dropped_items` collected but never enters `ok` | ALL reported loss; 29,211 drops still PASS | Drop set gates the verdict (Sec. 3). |
| S-22 | RFV:63-68 | `_g` returns `None` on failure; used as a dict KEY | every GUID-read failure collapsing into one `None` key, shrinking counts on both sides symmetrically | GUID read failure = `HARNESS_ERROR`. Never key an inventory by `None`. |
| S-23 | RFV:71-84 | `_name` returns `""` after all 5 casts fail | a real name difference comparing `"" == ""` (vacuous equality) | Return a sentinel (`"<NAME-UNREADABLE>"`) and count it; >0 unreadable names = `HARNESS_ERROR`. |
| S-24 | RFV:87-99 | `_iter_entries` returns `[]` when `LexDbOA` is None or both attrs absent | the ENTIRE D2 affix + D4 feature domains empty -> `{}` vs `{}` -> INTACT | Empty source domain must trip VG-02 (comparisons-performed > 0) and be a hard error when the project demonstrably has entries. |
| S-25 | RFV:138 | `list(fs.FeaturesOC) if fs is not None else []` | D1 features empty -> vacuous INTACT | Same as S-24; a `None` owning collection on the SOURCE is a `HARNESS_ERROR`. |
| S-26 | RFV:142-144 | `except -> vals = []` on `IFsClosedFeature(feat).ValuesOC` | complex-feature values never inventoried, so their loss is invisible | Cast failure must be classified (complex feature = expected, recorded as `not_applicable` with a count) not silently emptied. |
| S-27 | RFV:179-184 | `_feat_pairs` except-branch appends `[feature_guid, None]` | two different negated/complex values comparing equal | Record the concrete value representation; unrepresentable = counted `unreadable`, nonzero fails. |
| S-28 | RFV:190-196 | two `continue`s (no lexeme form; MorphType cast fails) | source affixes never entering the inventory, hence never checked | Count every `continue` by cause; publish as `skipped_source_objects`; must be 0 or allowlisted (VG-04). |
| S-29 | RFV:212-220 | nested `except ... except ... pass` on the MSA branch | an inflectional MSA whose `InflFeatsOA` read failed silently having no D4 row | Classify MSA subtype up front by `ClassName`; an unhandled subtype = `HARNESS_ERROR`. |
| S-30 | RFV:258-275 | `[:10]` truncation on missing and mismatched | detail for losses 11..N | Full detail to the JSON always; console truncation only, with `(+N more)`. |
| S-31 | RFV:271 | `d.get("_", "")` -- dead key, prints `src=''` for every MISSING row | that the printed detail is meaningless | Print the source detail dict. (Latent bug: `diff_domain` never sets `_`.) |
| S-32 | RFV:316 | `most_common(12)` | same as S-03 | Same as S-03. |
| S-33 | RFV:251-255 | fixed 8-domain tuple | every LCM class outside those 8 (senses, texts, wordforms, reversals, config views, custom fields...) | Domain set must be DERIVED from the enabled `GrammarCategory` set and asserted to cover it (VG-03). |
| S-34 | RFV:366-367 | idempotency = `tgt1[k] == tgt2[k]` over the same 8 domains | Move #2 duplication in any unmeasured class -- exactly seed f | Idempotency measured over the written-class set (VG-05). |
| S-35 | RFV:331-392 | `main()` has NO try/except and no post-restore | on any exception: TARGET left dirty AND `OUT_JSON` (line 389) never written -- zero evidence | Wrap in try/finally; always restore; always write the artifact, including on failure. |
| S-36 | RFV:374-378 | every one of the 8 domains printed as `"D1 intact after Move #1"` | which domain actually failed, in the console record | Print the real domain label. |
| S-37 | RFV:384-387 | only `move2_added == 0` gates idempotency | Move #2 drops, skips or gaps | Full move-2 comparison (S-06). |
| S-38 | RFV:113-115, 222-226 | `except Exception: pass` on Sldr init and `CloseProject` | writing-system data unavailable; unflushed/locked handles | Sldr failure = `HARNESS_ERROR`. Close failure = `HARNESS_ERROR` (see S-11). |

### 1c. AGP -- `debug/audit_guid_preservation.py`

| ID | file:line | Mechanism | Can hide | Replacement rule |
|---|---|---|---|---|
| S-39 | AGP:182, 214 | `offenders = [r for r in rows if r["minted"]]`; `return 0 if not offenders` | **`source_missing` never fails.** N source objects that never arrived, with 0 minted, is a PASS | `source_missing > 0` fails unless every missing GUID maps to an allowlist entry. This is the single most important change in the file. |
| S-40 | AGP:161-180 | no baseline-delta guard; empty `rows` -> empty `offenders` -> PASS | a Move that created nothing at all (the defect-c class, second instance) | VG-01: require `len(after_all - before_all) > 0` and `>= 0.5 * plan.actions`. |
| S-41 | AGP:169-170 | `if not new_guids and not missing: continue` | classes whose objects were MODIFIED rather than created -- field-level loss on pre-existing target objects is invisible **by construction** | Add a field-level comparison pass for in-scope classes present in BOTH (VG-02); GUID-set equality is necessary, not sufficient. |
| S-42 | AGP (whole file) | comparison is GUID-set only | a preserved GUID carrying an empty or garbage payload counts as `preserved` | Same as S-41: `preserved` must mean identity AND syncable-property equality. |
| S-43 | AGP:82-86 | `except Exception: continue` inside the `AllInstances()` loop | objects whose `ClassName`/`Guid` read throws vanish from BEFORE, SOURCE and AFTER alike, hiding both loss and minting | Count and report enumeration failures; >0 = `HARNESS_ERROR`. |
| S-44 | AGP:79-81 | `hasattr(...GetInstance)` ternary fallback on the service locator | a flexicon/LCM shape change quietly taking a different code path | Preflight (Sec. 4) pins the repository-access shape; no runtime branching. |
| S-45 | AGP:120-124 | move summary omits `skipped` and plan/report gaps; `move` is recorded (`:209`) but never asserted | planned-but-unexecuted actions | Assert `actions == added + skipped` (VG-06). |
| S-46 | AGP:178 | `regeneration_signature` requires `minted == missing` exactly | a mixed case (e.g. minted 5, missing 7) losing its flag | Flag on `minted > 0 AND missing > 0`; report both counts. |
| S-47 | AGP:179 | `sample_minted[:3]` | which specific objects were regenerated | Full GUID lists in the artifact (they are cheap); sampling in the console only. |
| S-48 | AGP:138-215 | no try/except, no post-restore, `OUT_JSON` written only at `:208` | on any exception: dirty TARGET and zero evidence | Same as S-35. |
| S-49 | AGP:70-73, 87-91, 125-135 | `except: pass` on Sldr, `CloseProject` (x2), source close; target close = `[WARN]` | unflushed writes invalidating the AFTER inventory | Same as S-11 / S-38. |

### 1d. FR -- `tests/integration/harness/full_run.py`

| ID | file:line | Mechanism | Can hide | Replacement rule |
|---|---|---|---|---|
| S-50 | FR:226 | `p.lexicon.LexiconNumberOfEntries()` -- `lexicon` does not exist on flexicon's `FLExProject` (`FLExProject.py:263-264`, `:3230`) | the headline lexicon metric, permanently, in every run ever recorded | Fix to `p.LexiconNumberOfEntries()`; and per S-51, an accessor that raises must be fatal so this class of rot cannot survive a single run. |
| S-51 | FR:251-259 | `except Exception: continue` + `except (TypeError, ValueError): continue` | any accessor failing or returning a non-int -- with NO error field in the result | Accessor failure = `HARNESS_ERROR`: abort the project, nonzero exit, record `label`, exception type, and traceback. Contract must state "every declared accessor MUST resolve"; the docstring's "silently omitted so the harness survives flexicon API drift" (`FR:22-24`, `:235`) is exactly the wrong posture and must be deleted. |
| S-52 | FR:223-227 | only 3 count accessors for ~28 `GrammarCategory` members | loss in 26 categories | One measurement per in-scope category, derived from the selection (VG-03). |
| S-53 | FR:225 | `PhonemeSetsOS[0]` -- `IndexError` on an empty set, caught by S-51 | phonemes silently unmeasured on any project without a phoneme set | Explicit "collection absent" outcome distinct from "count == 0"; both recorded. |
| S-54 | FR:43-58 | `build_full_selection(exclude=frozenset({STEMS}))` -- coverage reduction in a DEFAULT ARG; all three drivers call it with no argument | that STEMS is never tested; no artifact records the exclusion | The excluded set must be an explicit caller argument, recorded in the artifact, and any non-empty exclusion forces `COVERAGE_REDUCED` (nonzero, Sec. 3). |
| S-55 | FR:51-58 | empty pick-sets, "so the engine walks all POSes and transfers all leaf items" -- asserted in a comment, never verified | a selection that silently walks nothing | Assert `len(plan.actions) > 0` per enabled category present in source (VG-02). |
| S-56 | FR:150 | `os.environ.setdefault(DEBUG_ENV, "1")` | same as S-17 | Same as S-17. |
| S-57 | FR:200-208 | target close failure -> `[WARN] ... failed/timed out` and execution continues to the reopen/count | unflushed writes read back as loss (or as spurious equality) | Same as S-11. |
| S-58 | FR:209-212 | source `CloseProject` in a bare `except: pass` | a leaked source handle locking the project for the next iteration | Log and record; a leaked handle must fail the run before the next project starts. |
| S-59 | FR:268-270 | `total_count` sums heterogeneous metrics | a loss in one metric offset by a gain in another | Never compare aggregates. Compare per-label; VG-01 requires per-label non-regression. |
| S-60 | FR:96-101 | (GOOD) source open raises `RuntimeError` with an actionable message | -- | Keep. This is the only fail-loud pattern in the four files; make it the house style. |

### 1e. Cross-cutting (engine surface the sweep consumes)

| ID | file:line | Mechanism | Can hide | Replacement rule |
|---|---|---|---|---|
| S-61 | `models.py:1042-1046` | `DroppedItemRecord` dedup key excludes `reason` | a second, DIFFERENT failure on the same `(owner, field, item)` triple | The sweep must not treat `len(dropped_items)` as the failure count. Either widen the key to include `reason`, or have the sweep independently reconcile source objects against target objects (VG-04) so drop records are corroborating detail, not the primary channel. |
| S-62 | `texts.py:1370-1378` | `_safe(thunk)` -> `_log.debug` -> `return None`, ~30 call sites in `texts.py` + `wordforms.py` | API misuse becoming a STATISTIC: seed g's `'FLExProject' object has no attribute 'Translations'` x37 was an `AttributeError` degraded into a drop reason | Sweep-side rule: any drop `reason` matching an API-error signature (`has no attribute`, `TypeError`, `FP_ParameterError`, `object is not callable`, `NoneType`) is classified `ENGINE_BUG`, is NOT allowlistable, and forces nonzero. `_safe` may keep the walk alive but must not launder a programming error into permitted loss. |
| S-63 | `fullcopy_manifest.json` (stages) | hand-editable `status`/`verdict` with `result_file: null` allowed | a project marked `done` with no artifact | Status must be DERIVED from the presence and content of the per-project artifact, never hand-set. Missing artifact = `INCOMPLETE`, nonzero. |
| S-64 | RFL is untracked and gitignored (`.gitignore:117`) | the breadth driver -- the one that produced the only cross-project evidence -- is not in version control | that the instrument itself changed between runs; no provenance for any result | The fullsweep driver must be TRACKED, and every artifact must record the driver's git SHA plus a dirty-tree flag. |
| S-65 | `restore.py:190-206` | restore deletes only the `.fwdata` and 3 known subdirs, leaving "unrelated files alone" | residue from a previous iteration persisting into the next baseline | Verify post-restore state: assert the restored tree matches the backup's member list, or restore into a fresh directory. Record a baseline fingerprint in the artifact. |

---

## 2. VACUITY GUARD SET

Each guard runs per project. `HARNESS_ERROR` aborts that project immediately.
No guard may be skipped; a guard that cannot be evaluated is itself a failure
(`VACUOUS`), never a pass.

| ID | Guard | Assertion | Failure message | Verdict / exit |
|---|---|---|---|---|
| VG-01 | BASELINE-DELTA | `len(after_guids - before_guids) > 0` AND per-label `counts_post1[l] >= counts_base[l]` for every label AND at least one label strictly greater AND `len(new_objects) >= 0.5 * len(plan.actions)` | `[VACUOUS] Move #1 produced no measurable change in TARGET: new_objects=0, plan.actions=N. The run proves nothing.` | `VACUOUS` / 4 |
| VG-02 | COMPARISONS-PERFORMED | for every enabled `GrammarCategory` with >=1 source object: `field_comparisons_performed[cat] > 0` and `objects_compared[cat] > 0` | `[VACUOUS] category=<C> has <N> source objects but 0 field comparisons were performed -- the domain was empty or the accessor failed.` | `VACUOUS` / 4 |
| VG-03 | CATEGORY-COVERAGE | the measured-domain set covers the enabled selection set; `excluded_categories` is recorded and empty | `[COVERAGE] categories enabled but unmeasured: {...}; categories excluded from the selection: {STEMS}.` | `COVERAGE_REDUCED` / 3 |
| VG-04 | TOTAL-ACCOUNTING | every source object GUID in scope is in exactly one bucket: `transferred` (present in target with equal payload), `already_present`, `dropped_reported`, `allowlisted`, `out_of_scope` -- and `unaccounted == 0` | `[LOSS] <N> source objects are in NO bucket: neither found in target, nor reported as dropped, nor allowlisted. Sample: <guids>.` | `LOSS_UNEXPLAINED` / 1 |
| VG-05 | IDEMPOTENCY-IN-WRITTEN-CLASSES | the class set used for the Move#1-vs-Move#2 comparison is exactly the set of classes Move #1 wrote (from the AFTER-minus-BEFORE delta), not a hand-picked list; for each: `after2[cls] == after1[cls]` and `move2.added == 0` | `[NON-IDEMPOTENT] Move #2 added <N> objects; classes changed: {...}. (Measured over the <M> classes Move #1 actually wrote.)` | `NON_IDEMPOTENT` / 2 |
| VG-06 | PLAN-CONSERVATION | `len(plan.actions) == added + skipped` exactly, per category and in total (both directions) | `[LOSS] category=<C>: planned <P> actions, accounted <A> (added <X> + skipped <Y>). Delta <P-A>.` | `LOSS_UNEXPLAINED` / 1 |
| VG-07 | NO-EXTRA | every target GUID not in `before` is in `source_guids`, or is allowlisted as `EXTRA_ALLOWED` | `[LOSS] <N> objects minted in TARGET under fresh identities (class=<C>). Sample: <guids>.` | `LOSS_UNEXPLAINED` / 1 |
| VG-08 | ACCESSOR-INTEGRITY | every declared count accessor and every declared inventory accessor resolves; `unreadable_guids == 0`, `unreadable_names == 0`, `enumeration_failures == 0`, `skipped_source_objects == 0` | `[HARNESS_ERROR] accessor '<label>' raised <Type>: <msg>\n<traceback>` | `HARNESS_ERROR` / 5 |
| VG-09 | NO-TRUNCATION | `dropped_breakdown_omitted == 0` and `detail_omitted == 0` in the artifact; full lists present | `[HARNESS_ERROR] report truncated: <N> drop buckets and <M> detail rows were omitted.` | `HARNESS_ERROR` / 5 |
| VG-10 | ARTIFACT-INTEGRITY | the artifact was written for EVERY project in the manifest, contains driver SHA, flexicon fingerprint, baseline SHA-256, effective debug level, excluded categories, and a `guards` block with all VG-xx results | `[INCOMPLETE] no artifact for project '<P>' (status in manifest: <S>).` | `INCOMPLETE` / 7 |
| VG-11 | NO-ENGINE-BUG-AS-LOSS | no drop `reason` matches the API-error signature set (S-62) | `[ENGINE_BUG] drop reason '<R>' x<N> is an API error, not a permitted loss. Not allowlistable.` | `LOSS_UNEXPLAINED` / 1 |
| VG-12 | CLEAN-CLOSE | every `CloseProject` returned without error or timeout before any reopen/count | `[HARNESS_ERROR] target CloseProject failed/timed out; every measurement after this point is invalid.` | `HARNESS_ERROR` / 5 |

Vacuity meta-rule: the artifact must carry a `guards` block enumerating all
VG-xx with `pass|fail|not_evaluated`. Any `not_evaluated` maps to `VACUOUS`.
A PASS with fewer than the full guard list present is itself a failure -- this
prevents a future edit from silently dropping a guard.

---

## 3. VERDICT + EXIT-CODE MODEL

Exit 0 requires: zero harness errors, zero unaccounted source objects, zero
extras, idempotent, full category coverage, every project in the manifest run,
and 100% of any remaining loss matched to a valid, unexpired allowlist entry.

| Verdict | Meaning | Exit |
|---|---|---|
| `PASS` | zero loss, zero extras, all guards pass, no allowlist entry consumed | 0 |
| `PASS_WITH_ALLOWLIST` | as `PASS`, but 1..N losses each matched to a valid allowlist entry within its cap | 0 |
| `LOSS_UNEXPLAINED` | VG-04 / VG-06 / VG-07 / VG-11 failure, or a loss with no matching entry, or a count over an entry's `max_count` | 1 |
| `NON_IDEMPOTENT` | VG-05 failure | 2 |
| `COVERAGE_REDUCED` | VG-03 failure -- any excluded category (e.g. STEMS), any unmeasured enabled category | 3 |
| `VACUOUS` | VG-01 / VG-02 failure, or any guard `not_evaluated` | 4 |
| `HARNESS_ERROR` | VG-08 / VG-09 / VG-12, accessor failure, restore failure, close failure, artifact-write failure, unhandled exception | 5 |
| `PREFLIGHT_MISMATCH` | Sec. 4 capability fingerprint differs from the pinned expectation | 6 |
| `INCOMPLETE` | VG-10 -- any manifest project not run, skipped, or artifact-less | 7 |
| `ALLOWLIST_INVALID` | an entry is malformed, expired, unowned, capless, over-broad, or STALE (unmatched for 2 consecutive sweeps) | 8 |

Retired verdicts: `DROPS_REPORTED` (loss is allowlisted or it fails) and
`CLEAN` (renamed `PASS`, and now means something). `SILENT_FAIL` splits into
`LOSS_UNEXPLAINED` / `NON_IDEMPOTENT` / `VACUOUS`.

Aggregation across the corpus: the suite's exit code is the MAXIMUM
per-project code (never the last, never the first). A corpus run where any
project is `INCOMPLETE` cannot report 0 even if every project that ran passed.

### Baseline allowlist entry schema

Git-tracked at `specs/035-fullsweep-fidelity/baseline-allowlist.yaml`.
Reviewed like source. One YAML document per entry:

```
id:            AL-0001                 # stable, never reused
owner:         matthew_lee@sil.org     # a PERSON, required, must be a repo contributor
issue:         MattGyverLee/flexicon#241   # required; must be OPEN at sweep time
scope:
  projects:    ["Esperanto"]           # explicit list; "*" requires lead sign-off + a note
  owner_kind:  "MoForm"                # required, exact
  field_name:  "Form"                  # required, exact ("" only if the drop record has none)
  reason:      "shared-default diverged"   # EXACT string match; regex forbidden
max_count:     72                      # hard cap; actual > max_count -> LOSS_UNEXPLAINED
first_seen:    2026-07-20               # date the loss was first observed
expires:       2026-11-20               # <= 120 days after first_seen; past expiry -> exit 8
justification: |                        # >= 200 chars; must say WHY this is acceptable
  ...
accepted_by:   lex-lead                 # who signed off
```

Anti-dumping-ground rules (all enforced by the sweep, all exit 8 on violation):

1. **Exact reason match, no regex, no wildcard.** A `reason` of `*`, `.*`, or
   an empty string is rejected. One entry cannot cover two failure modes.
2. **Mandatory `max_count`.** No uncapped entry. `actual > max_count` is
   `LOSS_UNEXPLAINED` (1), not a widened allowance.
3. **Mandatory expiry, <= 120 days from `first_seen`.** An expired entry is
   exit 8, not a silent pass. Renewal requires re-editing the file (a diff a
   reviewer sees) and cannot be automated.
4. **Mandatory OPEN issue.** The sweep resolves `issue` via `gh`; a closed or
   missing issue is exit 8 -- so a fixed bug cannot keep excusing loss.
5. **Anti-stale.** An entry that matches 0 losses in 2 consecutive full-corpus
   sweeps is `ALLOWLIST_STALE` -> exit 8, forcing removal. An entry whose
   `max_count` exceeds the observed count by >25% for 2 consecutive sweeps
   must be tightened (same exit).
6. **No `ENGINE_BUG` entries.** A reason matching the API-error signature set
   (S-62) is unallowlistable by construction (VG-11).
7. **Cap on the whole file.** Total allowlisted objects <= 1% of source
   objects for that project AND total entry count <= 25. Exceeding either is
   exit 8: the answer is fixing the engine, not growing the file.
8. **Every consumed entry is echoed into the artifact** (`allowlist_hits`)
   with its `id`, matched count, and remaining headroom -- so a `PASS` always
   discloses exactly what it forgave.

---

## 4. UPSTREAM-DRIFT TRIPWIRE (capability preflight)

Confirmed drift: `flexicon/flexicon/code/FLExProject.py:164` is now
`def OpenProject(self, projectName, writeEnabled=False, undoable=True, ui=None)`
-- commit `c2bf8fb feat(write-path)!: default OpenProject to undoable=True
(DEF)` -- while `flexicon/flexicon/__init__.py:15` still says
`version = "4.3.1"` and GramTrans pins `pyflexicon>=4.3.1`
(`pyproject.toml:30`). A breaking default changed under a floor that cannot
express it. All three instruments open projects positionally/by keyword
without passing `undoable`, so every read-only inventory open in RFV
(`:125`), AGP (`:76`) and FR (`:96`, `:242`) silently changed unit-of-work
semantics with no version signal.

**PREFLIGHT (runs once at sweep startup, before any restore; failure =
`PREFLIGHT_MISMATCH`, exit 6, no writes attempted).**

Introspect and compare against a git-tracked
`specs/035-fullsweep-fidelity/contracts/flexicon-capability.json`:

1. **Identity / provenance:** `flexicon.version`, `flexicon.__file__` (must
   NOT contain `site-packages`), and the flexicon working-tree git SHA +
   dirty flag. Record all three in every artifact.
2. **Signatures with defaults** via `inspect.signature`, compared parameter
   name AND default value, for at least:
   `FLExProject.OpenProject` (expect `writeEnabled=False`, `undoable=<pinned>`,
   `ui=None`), `FLExProject.CloseProject`, `BaseOperations.ApplySyncableProperties`
   (expect `(item, props, ws_map=None)`), `BaseOperations.GetSyncableProperties`.
3. **GUID-preserving create surface (feature 033 dependency):** presence of
   `BaseOperations._CreateWithGuid`, and a `guid` parameter in the signature of
   each of `Texts.Create`, `Paragraphs.Create`, `Segments.AppendSentence`,
   `Wordforms.Create`, `WfiAnalyses.Create`, `WfiGlosses.Create`,
   `WfiMorphBundles.Create`. A MISSING `guid=` kwarg must fail here, loudly --
   at runtime it raises `TypeError` which `_safe` (S-62) launders into a
   generic "create failed" drop, exactly the failure mode CLAUDE.md warns
   about.
4. **Accessors the sweep depends on:** every attribute/method chain used by
   the count and inventory layers must resolve on a real handle, by name, on
   an open read-only project -- e.g. `FLExProject.lp`,
   `FLExProject.LexiconNumberOfEntries` (NOT `FLExProject.lexicon`, S-50),
   `ICmObjectRepository` access shape (S-44). An unresolvable accessor is
   exit 6, and this check alone would have caught S-50 on day one.
5. **The 8 Grammar Operations `ApplySyncableProperties` overrides** listed in
   CLAUDE.md must all be present (they are load-bearing for MCP visibility).

**Fingerprint + report.** Hash the normalized introspection result into
`capability_fingerprint` (sha256). Compare to the pinned value. On mismatch,
emit a field-by-field DIFF -- `symbol`, `expected`, `actual`, `kind`
(`missing` / `added` / `default_changed` / `renamed`) -- to stderr and to
`preflight.json`, then exit 6 without touching a database. Message shape:

```
[PREFLIGHT_MISMATCH] flexicon capability drift (version reported 4.3.1, unchanged):
  FLExProject.OpenProject   default_changed  undoable: expected False, actual True
  Texts.Create              missing          kwarg 'guid'
  fingerprint expected 9f2c... actual 41ab...
Refusing to run: a version string cannot be trusted to signal this. Update
specs/035-fullsweep-fidelity/contracts/flexicon-capability.json deliberately,
with a note, if the change is intended.
```

Never degrade, never "survive API drift" (the posture in `FR:22-24` and
`FR:235`). Drift is a finding, not weather.

---

## 5. REUSE VERDICT

| Instrument | Verdict | One-line reason |
|---|---|---|
| `debug/audit_guid_preservation.py` | **PROMOTE** (to the fullsweep core) | Its `ICmObjectRepository.AllInstances()` BEFORE/SOURCE/AFTER triangulation is the only mechanism in the repo capable of total accounting (VG-04); it needs its verdict fixed (S-39 `source_missing` must fail), a baseline-delta guard (S-40), a field-level pass (S-41/S-42), and try/finally + post-restore (S-48) -- but the measurement design is right. |
| `debug/run_fullsweep_verify.py` | **EXTEND** (as the deep-fidelity layer over AGP's inventory) | Its GUID-keyed, order-sensitive, payload-comparing domain diff is exactly the field-level comparison AGP lacks; extend it to derive domains from the selection (S-33), add a target BEFORE-inventory (S-19), make `extra` and `dropped_items` fail (S-20/S-21), and remove the `None`/`""`/`[]` collapses (S-22..S-29). |
| `tests/integration/harness/full_run.py` | **EXTEND**, with `reopen_and_count` **RETIRED** | `build_full_selection` + `run_full_transfer` are the correct shared engine entry point (keep, with the exclusion set made explicit per S-54); but `reopen_and_count` / `_COUNT_ACCESSORS` / `total_count` (FR:223-270) must be deleted outright -- 3 accessors, one permanently dead, a defensive `continue`, and a meaningless sum are the direct cause of seeds a, b, c and f. Replace with AGP's class inventory. |
| `scratchpad/run_fullcopy_live.py` | **RETIRE** (fold its manifest/corpus loop into the promoted driver) | Untracked and gitignored (S-64), its verdict cannot fail on loss (S-02), its baseline resolution is a glob fallback (S-10), and it double-swallows the only persistence proof it has (S-04, S-01) -- but its Ralph-loop corpus iteration, per-project artifact and restore-before-and-after discipline are worth porting into the promoted driver as a TRACKED module. |

Net: extend AGP + RFV + `full_run`'s selection/transfer half, port RFL's
corpus loop, delete `reopen_and_count`. No fourth driver.
