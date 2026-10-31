# QC cycle 4: PR #152 (#133), head 69b5577, cycle-3 delta

> Saved by the main session. The lex-qc agent had no Write tool and returned this report as its final message.
> Read-only review of GramTrans-qc-69b5577 and the cycle-3 delta diff. Nothing was run. The dedent comparison (item 5) was done by eye, without a whitespace-insensitive diff.

**Verdict: PASS-with-P2. Score: 88/100.**

## 1. Cycle-2 findings

| Finding | Status | Where |
|---|---|---|
| P1: deferred pairs reported nowhere | Fixed | categories.py `_reconcile_deferred_infl_pairs` (~13194-13239); transfer.py:341-380; deferred list recorded at transfer.py:3401-3406 |
| WRITE_FAILED Skip mislabelled | Fixed | categories.py:13166-13172, now POS_INFLECTABLE_FEATS / NOT_REPRODUCIBLE |
| Absent feature reported twice | Fixed on that path | categories.py:13121-13135 (drop when a collector exists, otherwise Skip) |
| No #107 end-to-end test | Fixed | `test_created_pos_deferred_pair_is_written_by_the_pass` |
| Dead `finally: pass` | Fixed | Dedent in `inflection_features_execute_action` |
| Stale `_run_tail_once` comments | Fixed | models.py:3641; categories.py:5757 |
| `_resolve_target_by_guid` has no type check | Not fixed | Carried over; low severity |
| Brittle `inspect.getsource` tests | Not fixed | One more added (`test_the_link_pass_has_no_feature_creation_surface`) |
| Add raises after a partial apply, but the read-back finds the pair | Not fixed | Unchanged |
| Preview "Link" rows over-promise | Not fixed | Unchanged |
| Live evidence | Partial | See P2-3 |

## 2. Reconciliation coverage

Each loss path is covered:

| Loss path | How it is handled |
|---|---|
| Pair not in the map | The drop reason names the leaf-pick filter and closure (13221-13226) |
| `_run_plan` is None | `cause` is set (transfer.py:344), and reconcile still runs |
| The pass raises, including mid-pass | `_infl_pairs_settled` is attached before the loop (13064-13070), so settled pairs stay settled and the rest become named drops; a test covers this |
| POS unresolved, or the RC is unavailable | The pass `continue`s without settling the pair (13088-13112), so reconcile reports it |

Every deferred pair ends up settled (linked, already-linked, absent-feature or write-failed) or dropped. Two theoretical escapes remain, and neither is realistic:
- `_dropped` is None, which causes an early return. But `execute` always attaches it.
- `object.__setattr__` fails on the context. That does not happen on RunContext.

Reconcile is idempotent: `_append_dropped_once` plus a local `seen` set. A failure in reconcile is wrapped separately and logged; it is never raised out of `execute`.

## 3. Double report

Real, but across buckets only.
- On the POS-unresolved path (13088) and the RC-unavailable path (13106), the pass emits one Skip per POS.
- Reconcile then also adds one DroppedItemRecord per deferred pair.
- Skips and `dropped_items` are separate outcome buckets (report.py:681-682, 732, 737), so the same loss is counted in both tallies.

Both entries are named, so nothing is silent. **P2-1.**

## 4. Entry-ref import guard

Correct.
- It logs with `_log.exception`.
- It appends a DroppedItemRecord with `owner_label="(run)"` and an empty GUID. An empty GUID is allowed for GUID-less owners (#76).
- It then returns, so the failure is neither silent nor raised out of `execute`.

## 5. Dedent

No hidden logic change was found. The complex, open, cast-failure and closed branches and the value loop match line for line. The only differences are the removed `try:`/`finally: pass`. There is also a harmless trailing comment after the final `return` (cosmetic).

## 6. Tests

Most of the 13 tests fail without the fix:
- `deferred_pairs=` and `_reconcile_deferred_infl_pairs` do not exist before it.
- The mid-pass and raising tests depend on `settled`.
- The import-guard test would raise out of `execute`.

They are not tautological, but two are weak:
- `test_without_inflection_features...` builds a Selection that nothing reads, and its "Feat/Fs" substring check on service requests is brittle.
- The `inspect.getsource` test is brittle.

## P2 list

1. **Cross-bucket double count.** The Skip at categories.py:13088-13112 duplicates the drop at 13194-13239. Suppress the Skip when `_dropped` is present, as 13121 already does.
2. **A mid-pass raise loses counts.** Affected code: transfer.py ~355-365 and the accumulation at categories.py:13179.
   - Links written before the raise are not counted in `_infl_feature_link_writes`, and their skips are lost.
   - The Preview/Move link-row tally drifts on that rare path.
3. **Live evidence covers only the absent-feature path.**
   - The 14 drops come from the pass itself (those pairs were settled), not from reconcile.
   - The reconcile paths (not in map, no plan, raise) have unit coverage only.
   - The evidence does not name the SHA it ran.
4. Carried-over cycle-2 P2s (see the table above).

**P0/P1:** none.

**Merge recommendation:** merge #152. P2-1 is a quick optional fix; the rest can go to follow-up.
