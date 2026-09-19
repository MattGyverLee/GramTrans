# Resume report — T100 → T101

**Date**: 2026-08-22
**Feature**: 038-transfer-fidelity-gaps
**Worktree (code)**: `D:\Github\_Projects\_LEX\GramTrans-038-transfer-fidelity-gaps`,
branch `038-transfer-fidelity-gaps`, `3dc5bde` → `85a2919`
**Root (`main`, specs)**: `d205e51` → `05fa2eb` → `44c5fdc`

---

## Where this pass resumed, and why not where the resolver said

`status-context.py` resolves `nextTask: T064`. T064 is deliberately parked
("RUN AND MEASURED 2026-08-21, NOT PASSED") and its unmet half —
`MoAffixProcess` MATCHED — is owned by **T076/T077**, not by T064. Three passes
have now left it parked on purpose.

Unlike the T087 pass, the worktree was **clean** at `3dc5bde`, so there was no
half-landed work to finish first. The actual next actionable pair was the one
the T087 report named: **T100 → T101**, in that order, both offline-verifiable
over the committed `_snapshots/` corpus.

## Headline

| task | status | measurement |
|---|---|---|
| **T100** | **CLOSED** | Resolution **(b)**: the `$comment` was narrowed and the vocabulary stays **closed at 17**. An 18th token was rejected on three measured facts, the deciding one being that `not_evaluated_reason` and `accountedLine.reason` are the **same `$ref`** — so a token minted for an uncountable class would be immediately admissible as an accounting line. `schema_version` stays 1; the exact-match tripwire is untouched. |
| **T101** | **CLOSED** | The forged artifact went from **0 validator failures / `CENSUS_CLEAN` / exit 0** to **2 failures / `CENSUS_ERROR` / exit 7**. Over the committed corpus: **18 artifacts, 0 refused before, 0 refused after**. |
| **T103** | **FILED** | `Ngoreme FLEx`'s hardcoded `MoStemMsa` count has moved a third time (1949 → 1952 → **1953**) and the test carrying it now runs instead of skipping. |

Full reasoning:
`journal/T100-T101-the-null-that-was-not-a-measurement.md`.

## The one thing to read if you read nothing else

The vocabulary question and the null question turned out to be **the same
question**, which is why T099 filed them together and why they had to land in
that order.

An 18th `not_evaluated_reason` token would have been usable as an
**`accounted_for` line reason** — the two fields share `#/$defs/reasonToken` —
so "this class could not be counted" would have become a way to *account for* a
shortfall. That is precisely T101's defect: retiring units nobody measured. The
enum's own `$comment` had already ruled on it (*"A reason the census cannot
classify is CENSUS_ERROR"*), so T100 is the contract catching up to itself, and
T101 is the enforcement that stops the narrowed prose from being permissive.

## Why the invariant went where it did

Every step of the path T101 closes is **individually correct**:
`row_verdict_class(None, …)` → `NOT_EVALUATED`; `row_passes` True on
`NOT_EVALUATED` before reading a count; `unexplained_counts(None, …)` →
`(0, 0)`; invariants 3, 4, 11 all guarded `None not in (…)`. Composed, they
mean nulling a class retires its shortfall. So the refusal is not in any of
them — it is at the one place the **corroboration** lives, and it is read by
*both* `validate_artifact` and `recompute_verdict`, which is why the forgery
costs exit 7 and not merely a non-passing gate.

`row_passes` was **not** changed. The two `excluded_not_measurable` rows every
artifact carries are exempt because they are `advisory`; the test proves that by
promoting the same row to `required` and watching it get refused.

## The before/after that let it land

| | value |
|---|---|
| census artifacts under `_snapshots/` | **18** |
| validator failures, before / after | **0 / 0** |
| refused by invariant 12 | **0** |
| required rows carrying a null, anywhere in the corpus | **0** |
| advisory null rows, exempt by scope | **6** |

All six pinned in `TestT101TheCommittedCorpusIsUnmovedByInvariant12`, corpus
size included, so a corpus test that silently stopped finding artifacts cannot
pass.

## Suites

| suite | after T087 | after T100/T101 |
|---|---|---|
| `tests/unit` | 3587 passed, 79 skipped, 14 xfailed | **3587 passed, 79 skipped, 14 xfailed** |
| `tests/integration` | 434 passed, 0 failed, 76 skipped | **448 passed, 1 failed, 75 skipped** |

The `+14` is exactly this change's new tests. Still run separately — a combined
invocation fails collection on the `test_038_process_rules.py` basename
collision.

### The one failure is not this change's — and it is worth reading

`test_ngoreme_flex_holds_1949_and_ngoreme_holds_1945` fails: `Ngoreme FLEx`
measures `MoStemMsa` **1953** against a hardcoded 1949 (`Ngoreme` is still
1945/37 exactly).

**Verified not caused here** two independent ways: it reproduces on the
stashed, pre-change tree; and the suite arithmetic says the same thing — skipped
went 76 → 75 while failed went 0 → 1, so this is a live test that was *skipped*
during the T087 pass and now runs. That is **T090's shape resolving in the
opposite direction**: a stale `.fwdata.lock` had been turning live coverage into
skips, the lock is gone, and the coverage came back carrying a stale number.

Not re-pinned, and deliberately so. This is the *"pre-existing `Ngoreme FLEx`
1949 → 1952 pin — still not decided"* item the last two reports carried forward,
and the count has now moved a third time. The premise the test is named for
still holds (1953 > 1945); what keeps failing is the decision to hardcode an
exact count of a project a human edits. **T103** carries the three candidate
directions.

## Live-project discipline

**Nothing was opened by this work.** T100 and T101 are contract and instrument
changes, verified offline over the committed `_snapshots/` corpus. `Ngoreme
FLEx` and `Ngoreme` are opened read-only by the pre-existing test discussed
above, which proves its own read-only-ness by digest before/after; nothing was
written, nothing restored, and no lock files were created. `Esperanto`,
`Ngoreme Target`, `Mbugwe LizzieHC practice`, `Ejagham Mini` and `Target` were
not opened at all.

## Commits

| repo | commit | subject |
|---|---|---|
| `main` | `05fa2eb` | `spec(038): T100 -- the vocabulary stays closed at 17; the prose was the defect` |
| feature | `accd761` | (cherry-pick of `05fa2eb`) |
| feature | `85a2919` | `fix(038): T101 -- a null count was a way to retire a shortfall without measuring it` |
| `main` | `44c5fdc` | `docs(038): T100 and T101 closed -- the vocabulary held; the null did not` |

**Note on the contract commit.** It landed on `main` first (spec artifacts go to
`main` per the repo protocol) and was **cherry-picked** onto the branch rather
than merged: `git merge main` conflicts in
`tests/integration/harness/full_run.py`, because `main` has moved on with other
features' code since the branch's merge-base at `4a319af`. That merge is
T085's business, not this pass's.

## Not done, deliberately

* **T064** — still parked. Owned by T076/T077.
* **T090** — still open. Its subject is now visible from the other side: the
  stale-lock skip that was hiding `Ngoreme FLEx` coverage has lifted on its own,
  which is why T103 surfaced at all.
* **T102** — still filed, not fixed. Needs three live driver re-runs.
* **T103** — filed this pass, not fixed.

## Suggested next pass

**T090**, then **T103**. T090 is now the one with fresh evidence — this pass
watched a stale lock's disappearance change a suite's shape, which is exactly
the effect T090 predicts and the strongest argument yet for making
`_open_or_skip` distinguish a stale lock from a live one. T103 is one decision
downstream of it and touches the same file, so the two are cheaper together than
apart.

Alternatives, unchanged in priority: **T076 → T077** if the next pass wants live
work and can restore a target (it is what finally moves T064's P4), or **T074**
(affix-to-template-column linking, measured baseline 0 of 110).
