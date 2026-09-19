# T100 / T101 — the null that was not a measurement

**Date**: 2026-08-22
**Tasks**: T100 (contract), T101 (invariant)
**Live projects opened**: none by this work. `Ngoreme FLEx` and `Ngoreme` are
opened read-only by a pre-existing test discussed at the end; nothing was
written, nothing restored.

---

## The pair, and why they were filed together

T099 needed a `not_evaluated_reason` token for a row whose repository accessor
did not resolve, and did not invent one. The closed vocabulary has 17 members
and none of them is true of an instrument failure, so the row went out as
`verdict_class: NOT_EVALUATED` with **no reason**, stating its cause in
`errors[]` instead. Schema-legal — `not_evaluated_reason` is not in
`$defs.classRow.required` and nothing enforces the `$comment` — and
contract-ambiguous, because that `$comment` said "**Required** when
verdict_class is NOT_EVALUATED".

T101 is what that ambiguity was hiding. A required row may carry a null count,
and a null count buys a pass.

## T100: the vocabulary was right; the prose was the defect

Two resolutions were admissible and they are not equivalent. **Appending an
18th token was rejected on evidence**, three facts, none of them about taste:

1. **`not_evaluated_reason` and `accountedLine.reason` are the SAME `$ref`**
   (`#/$defs/reasonToken`). A token minted to say "this class could not be
   counted" is immediately admissible as an **accounting line** — so a
   shortfall could be explained away by the fact that nobody measured it.
   That is T101's defect one field to the left, arriving through the door
   built to keep it out.
2. It would have to join `CENSUS_REASONS_NOT_REQUIRING_REPORT_REF`, since an
   unresolved accessor names no run-report content — growing from 4 to 5 the
   set of reasons that may account **without evidence**.
3. **The enum's own `$comment` already rules on the case**: *"A reason the
   census cannot classify is CENSUS_ERROR."* An unresolved accessor is an
   instrument failure, not a fact about the language data, and it already
   produces CENSUS_ERROR through a non-empty `errors[]`.

And the direction that was never in question: stamping
`ABSENT_BY_CONSTRUCTION` — the least-wrong member — asserts the class *cannot
exist*. It is what `MoForm` and `MoMorphSynAnalysis` correctly carry. Saying it
of a class whose repository name merely drifted is a **false statement in the
artifact**, which is the defect T099 had just closed, one field to the left.

So the prose was narrowed: a NOT_EVALUATED row names its reason **when there is
one**, and `errors[]` carries the rest. `schema_version` stays 1 — nothing was
added, removed or renamed, and the exact-match tripwire
`test_tokens_match_the_schema_enum_exactly` is untouched.

Narrowing alone is permissive. The half that makes it safe is T101.

## T101: the measurement

**The forgery.** One `gate_scope: required` row, `source_count` /
`destination_count_total` / `difference` all `null`, `errors[]` empty:

| | before | after |
|---|---|---|
| `validate_artifact` failures | **0** | **2** |
| `recompute_verdict` | `CENSUS_CLEAN` | `CENSUS_ERROR` |
| `gate_artifact().exit_code` | **0** | **7** |

**The mechanism, and every step of it is individually correct.**
`row_verdict_class(None, …)` is `NOT_EVALUATED` — right, an unmeasured row must
not read MATCHED. `row_passes` returns True on `NOT_EVALUATED` before reading
any count — right, a row nobody measured proves nothing. `unexplained_counts(
None, …)` returns `(0, 0)` so R-2's over-accounting check is skipped — right,
there is no difference to over-account against. Invariants 3, 4 and 11 are all
guarded `None not in (…)` — right, they cannot recompute what is not there.
**Composed**, they mean nulling a class is a way to retire its shortfall
without measuring anything.

That is why the fix is not in any of them. The refusal belongs where the
**corroboration** is: `census.uncorroborated_null_rows`, read by *both*
`validate_artifact` and `recompute_verdict` — the shape every other
CENSUS_ERROR-class rule in that file already has, and the reason the forgery
costs exit 7 rather than merely a non-passing gate.

**The fix not to make**, pinned from the other side. Failing `row_passes` on a
null would fail the two `excluded_not_measurable` rows every artifact carries —
`MoForm` and `MoMorphSynAnalysis`, abstract LCM bases with no factory. They pass
because they are **advisory**, a row that can neither fail a gate nor excuse
one, and *never* because a null is tolerated on a row that could. The test
promotes the same row to `required` and watches it get refused, so the
exemption is demonstrably scope and not the null.

`destination_count_net` is deliberately outside `NULLABLE_COUNT_FIELDS`: it is
derived from `destination_count_total`, so a null net beside integer counts is
an arithmetic defect (invariant 3), not an unmeasured class. Folding it in
would have made invariant 12 report a class nobody failed to measure.

## The before/after over the committed corpus

This is what T099 said the gate half needed and could not produce at the time,
and it is the reason the invariant could land at all — adding one changes what
the gate refuses about **every artifact already committed**.

Measured over every census artifact under `tests/integration/_snapshots/`:

| | value |
|---|---|
| artifacts | **18** |
| validator failures, before | **0** |
| validator failures, after | **0** |
| refused by invariant 12 | **0** |
| required rows carrying a null, anywhere in the corpus | **0** |
| advisory null rows, exempt by scope | **6** (3 artifacts × T099's 2 rows) |

Nothing already committed moves. The shape invariant 12 refuses does not occur
in anything this repo has measured — it is reachable only by hand or by a
producer bug, which is exactly what it is for. All six numbers are pinned in
`TestT101TheCommittedCorpusIsUnmovedByInvariant12`, including the corpus size,
so a corpus test that silently stopped finding artifacts cannot pass.

## The pin that was asked to fail

`test_the_gate_alone_does_not_yet_refuse_a_forged_null` said in its own
docstring: *"When T101 lands, THIS TEST FAILS and must be updated
deliberately."* It is edited, not deleted. It is now
`test_the_gate_now_refuses_a_forged_null`, and it asserts **two** failures
rather than one: `UNCORROBORATED_NULL`, and **invariant 8 firing as a
consequence** — the recomputed verdict moved to `CENSUS_ERROR`, so the stored
`CENSUS_CLEAN` stopped agreeing with the artifact's own evidence. Before T101
those two agreed, which is precisely why the forgery passed.

## Why the producer guard stays

`census_cli._refuse_uncorroborated_nulls` is not made redundant. It raises
**before** an artifact is written, so the operator gets the class name at the
console instead of a document to validate. It is also deliberately **tighter**:
it accepts only the two shapes that CLI can emit and cannot mint a
`not_evaluated_reason` for a required row, while the invariant accepts one as
corroboration. A tighter producer inside a looser format is the safe direction.
Its docstring stopped claiming the validator does not do this.

Accepting `errors[]` as corroboration is not a loophole: a non-empty `errors[]`
is CENSUS_ERROR on its own, so the admissible shape still exits 7. Corroboration
admits the ROW; it never admits the RUN.

## Suites

| suite | after T087 | after T100/T101 |
|---|---|---|
| `tests/unit` | 3587 passed, 79 skipped, 14 xfailed | **3587 passed, 79 skipped, 14 xfailed** |
| `tests/integration` | 434 passed, 0 failed, 76 skipped | **448 passed, 1 failed, 75 skipped** |

The `+14` is exactly this change's new tests (5 added to T099's class, 4 in
T101's corpus class, 5 in T100's). Still run separately — a combined invocation
fails collection on the `test_038_process_rules.py` basename collision.

## The one failure, and it is not this change's

`TestCorrectedPremiseNgoremeFlexIsTheSource::test_ngoreme_flex_holds_1949_and_ngoreme_holds_1945`
fails: `Ngoreme FLEx` measures `MoStemMsa` **1953**, against a hardcoded 1949.
`Ngoreme` still measures 1945/37 exactly.

**Verified not caused here**: the failure reproduces on the stashed,
pre-change tree. And the suite arithmetic says the same thing from the other
side — skipped went 76 → 75 while failed went 0 → 1, so this is a live test
that was **skipped** during the T087 pass and now runs, which is T090's shape
(a stale `.fwdata.lock` turning live coverage into skips) resolving in the
opposite direction. The project's digest has moved (`e10a44ef…` vs the recorded
`052243ea…`): a user edited it.

This is the *"pre-existing `Ngoreme FLEx` 1949 → 1952 pin — still not re-pinned,
still not decided"* item the last two resume reports carried forward, and the
count has now moved a third time. It is **not** re-pinned here. The premise the
test is named for still holds (FLEx is the source; 1953 > 1945); what has failed
three times is the decision to hardcode an exact count of a project a human
edits. Filed as **T103** so the choice — re-pin, assert the premise rather than
the number, or gate on the digest — gets made on its own evidence rather than
absorbed into a pass about census nulls.
