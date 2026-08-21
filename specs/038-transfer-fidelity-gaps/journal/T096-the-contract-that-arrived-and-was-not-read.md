# T096 - the contract that arrived and was not read

**Date**: 2026-08-21
**Task**: T096 (out of band). Filed and closed in one pass.
**Branch**: `038-transfer-fidelity-gaps`, worktree
`D:\Github\_Projects\_LEX\GramTrans-038-transfer-fidelity-gaps`, commit
`da5975f` on `c7123d5`.
**Specification**: contract commit `b2cb356` on `main` (2026-08-20),
*"spec(038): add SOURCE_REFERENT_ABSENT to the closed reason vocabulary"*.
Its message is the argument for this change and is not restated in full here.
**Artifacts**: `tests/integration/_snapshots/census-038-t096-ngoreme.json`,
`before-after-038-t096-ngoreme.json` (live run GT-20260821-200656).

## The one-line version

The code left a `TODO(contract)` waiting for a token. The contract delivered
the token. The branch was 48 commits behind and never saw it, so for a day
the fix existed and the code that asked for it did not know. A rebase, not a
wave and not a live run, is what connected them.

## How it surfaced

`tests/integration/test_object_census.py::TestReasonVocabulary::test_tokens_match_the_schema_enum_exactly`
failed immediately after the rebase: the schema enum held 17 members,
`EXPECTED_REASON_TOKENS` held 16, and the extra member was
`SOURCE_REFERENT_ABSENT`. That is the tripwire working exactly as designed -
it was written to fire *when the contract closes the gap*, and it did. It was
not relaxed.

## What the substitute was actually costing

The `TODO` said the token was "least-wrong and still wrong". That undersells
it. `SOURCE_REFERENT_ABSENT_TOKEN` held the string `"DEPENDENCY_UNRESOLVED"`,
and two rows of `census_cli.DROP_REASON_TOKENS` classify a missing referent:

| needle | token, before | token, after |
|---|---|---|
| `"is empty on source"` | `DEPENDENCY_UNRESOLVED` | `SOURCE_REFERENT_ABSENT` |
| `"not resolvable in target"` | `DEPENDENCY_UNRESOLVED` | `DEPENDENCY_UNRESOLVED` |

Two different causes, one token. `dropped_by_class_from_report` groups by
token, so source-side and destination-side losses **collapsed into one
accounting line per class** and the artifact could no longer say which was
which. Worse, `accounted_for_drops` selects the explanatory `detail` with
`if token == SOURCE_REFERENT_ABSENT_TOKEN` - which, while that constant WAS
`"DEPENDENCY_UNRESOLVED"`, matched *every* destination-side line too and
stamped them with a `PROVISIONAL TOKEN: the referent was absent ON THE
SOURCE` explanation that was simply false for them.

READ (not measured now) from the committed `census-038-t091-ngoreme.json`,
run GT-20260821-184426:

| class | accounted items | detail carried |
|---|---|---|
| `MoDerivAffMsa` | 3 | `PROVISIONAL TOKEN ... absent ON THE SOURCE` |
| `MoInflAffMsa` | 98 | same |
| `MoStemMsa` | 1787 | same |
| `MoUnclassifiedAffixMsa` | 2 | same |

1890 items, every one asserting a side of the transfer that the artifact has
no way to confirm - because the collision destroyed the distinction before
the artifact was written. **A least-wrong token is not a smaller version of
the right one; it is a collision.** That is the sentence the `TODO` should
have carried, and the reason a "provisional, auditable" substitution is less
safe than it reads.

## What changed

**One declaration.** `Lib/census.py:20` states the rule in its own words:
*"THE VOCABULARIES ARE RE-EXPORTS, NEVER RE-DECLARATIONS"*. The literal lives
at `Lib/models.py CENSUS_REASON_TOKENS`, and `census.REASON_TOKENS` is bound
to it; the dependency direction is census -> models and never the reverse,
because `ClassCensusRow` must reject an out-of-vocabulary token at
construction and cannot import from `census.py`. `SOURCE_REFERENT_ABSENT` was
**appended** there, in `$defs.reasonToken.enum` order, and nowhere else. No
second declaration was created.

**`schema_version` stays 1.** Not an oversight - `b2cb356` argues it
explicitly, following the precedent at
`journal/T016-T020-census-engine.md:263-267`: the EVOLUTION RULE's bump clause
governs a *shipped* version, this format has not shipped, and a bump would
contradict the `CENSUS_SCHEMA_VERSION == 1` pin at
`tests/integration/test_object_census.py:687`. Re-verified live below.

**`SOURCE_REFERENT_ABSENT_DETAIL` was REWRITTEN, not deleted.** This was the
one genuine choice in the task and it is worth stating why. Its entire text
explained a *substitution*, and there is no longer a substitution to explain;
leaving it verbatim would have written a false statement into every artifact
line the token produces - the same defect one layer down, which is precisely
the shape this feature keeps meeting. Deleting it outright was the other
candidate and was rejected: the `detail` slot is the only place a reviewer
holding **only the artifact** learns which side of the transfer the referent
was missing from, and that is worth saying in the artifact rather than only in
the source. So it now says what is true:

> the referent was absent ON THE SOURCE, so the dependent object was never
> transferable; distinct from DEPENDENCY_UNRESOLVED, which is absence in the
> destination (fidelity-census.md 7.1)

**`DROP_REASON_TOKENS` ordering re-verified.** "Most specific first" still
holds, and now by construction rather than by luck: the three needles are
mutually exclusive on the reasons `Lib/categories.py` actually emits
(`_resolve_or_none` picks `"is empty on source"` XOR
`"not resolvable in target"` for the same slot, `_null_pos_fallback_blocked`
extends the former and matches only it, and
`"is not reproducible by this engine"` comes from a different producer), and
no needle is a substring of another. Pinned in
`test_no_needle_shadows_another`.

## The uncomfortable finding: a correct token with no live producer

The task asked for a live run that actually stamps the new token. **It does
not, and it cannot on any corpus available today.** Stated plainly rather than
dressed up.

MEASURED, read-only, this session (`scratchpad/probe_t096_null_pos.py`, four
projects opened `writeEnabled=False`, none written):

| source | `MoInflAffMsa` null POS | `MoDerivAffMsa` null POS | `MoStemMsa` null POS *(legal)* |
|---|---|---|---|
| `Ngoreme FLEx` | 0 / 134 | 0 / 3 | 10 / 1952 |
| `Ejagham W Mini` | 0 / 111 | 0 / 0 | 2 / 153 |
| `Mbugwe LizzieHC practice` | 0 / 126 | 0 / 17 | 1 / 139 |
| `Esperanto` | 0 / 41 | 0 / 31 | 364 / 15284 |

`MoInflAffMsa` and `MoDerivAffMsa` are the *only* subclasses where a null
required POS is a DROP. They hold none, anywhere. The right-hand column is a
near miss and not a producer: a null POS on `MoStemMsa` /
`MoUnclassifiedAffixMsa` is legal FLEx (Category = "Not Sure") and is
**reproduced, not dropped** - `_resolve_or_none(empty_is_legal=True)`.

And that is the whole story of this token. The drop that motivated it -
`MoStemMsa.PartOfSpeechRA (POS guid=empty) is empty on source` - was a
`MoStemMsa` drop, and **T043b stopped dropping those**: its own docstring
names the counts, "2 of 164 `MoStemMsa` on the T038 pair, 9 on the Ngoreme
pair". The table above finds 2 and 10 - the same objects, the Ngoreme figure
having drifted with the source. So the contract closed a gap in the vocabulary
while the engine was closing the condition underneath it, and the two closures
never met. The only surviving producer is `_null_pos_fallback_blocked`, which
needs the GUID-preserving create to fail - and on flexicon >= 4.5.2 it does
not.

MEASURED, live: run **GT-20260821-200656**, `Ngoreme FLEx` ->
`GT038 Ngoreme After` (restored from `Target 2026-07-06 0218.fwbackup` first;
neither `Ngoreme Target` nor `Ejagham W Target` nor `Esperanto` was touched).
11,066 `dropped_items`. Classifiable MSA drops:

| | lines carrying the token | items |
|---|---|---|
| before (old constant, same report re-classified) | 0 | 0 |
| after (new constant) | 0 | 0 |

Both numbers MEASURED over the same live run report, not read from a snapshot.
The artifact validates: `census.validate_artifact` returns no failures,
`jsonschema.validate` against `contracts/census-artifact.schema.json` PASSES,
`schema_version` is 1.

Because a live run cannot exercise the emit path, the emit path is pinned in a
test instead -
`TestReasonVocabulary::test_the_source_side_token_is_emittable_and_schema_valid`
builds a full artifact carrying `SOURCE_REFERENT_ABSENT` and asserts it
validates against the real schema at version 1. **A vocabulary member nothing
can emit is not a vocabulary member; it is a comment in an enum** - which is
T094's lesson ("a deferred sweep with no producer is invisible, not latent")
arriving from the opposite direction, on a contract rather than a sweep.

## Pins deliberately moved

| site | was | now |
|---|---|---|
| `test_object_census.py` `EXPECTED_REASON_TOKENS` | 16 members | 17, appended in enum order |
| `test_object_census.py::test_exactly_sixteen_tokens` | `== 16` | renamed `..._seventeen_tokens`, `== 17` |
| `test_038_census_report_evidence.py::test_the_substitution_is_flagged_for_the_contract` | `TOKEN == "DEPENDENCY_UNRESOLVED"`, `"PROVISIONAL" in DETAIL` | renamed `test_the_contract_token_is_used_not_the_least_wrong_substitute`; `== "SOURCE_REFERENT_ABSENT"`, `"PROVISIONAL" not in DETAIL` |
| same file, `test_the_provisional_token_is_stated_in_the_artifact` | line reason `DEPENDENCY_UNRESOLVED` + `PROVISIONAL TOKEN` in detail | renamed `test_the_side_of_the_transfer_is_stated_in_the_artifact`; `SOURCE_REFERENT_ABSENT`, no `PROVISIONAL` |
| same file, `test_two_reasons_on_one_class_are_two_lines` | `["DEPENDENCY_UNRESOLVED", "UNSUPPORTED_SUBTYPE"]` | `["SOURCE_REFERENT_ABSENT", "UNSUPPORTED_SUBTYPE"]` |

Every one is a pin that had become backwards, not a test relaxed to fit. The
exact-match and count assertions in `TestReasonVocabulary` are fully green.

Prose counts ("closed 16-token", "a 17th token") were updated in
`Lib/models.py`, `Lib/census.py`, `census_cli.py` and the two test modules;
the parametrized `test_every_other_token_without_a_report_ref_is_census_error`
gained one case (12 -> 13 non-exempt tokens), which is why integration gained
two passes rather than one.

## One tool change

`debug/run038_before_after_pairs.py` gained `--tag NAME`. Without it a re-run
overwrites the committed `census-038-<pair>-after.json` **in place**, which is
how a committed measurement quietly becomes a different measurement under the
same filename. The `t091` / `t094` artifacts already in `_snapshots` have
exactly this shape and were produced by hand; the flag makes them
reproducible. The destination and the restore-first discipline are unchanged.

## Test counts

| suite | before | after |
|---|---|---|
| `tests/unit` | 3531 passed, 79 skipped, 14 xfailed | 3534 passed, 79 skipped, 14 xfailed |
| `tests/integration` | 405 passed, **2 failed**, 75 skipped | 409 passed, **1 failed**, 75 skipped |

The one remaining integration failure is
`TestCorrectedPremiseNgoremeFlexIsTheSource::test_ngoreme_flex_holds_1949_and_ngoreme_holds_1945`
- pre-existing live-data drift (`Ngoreme FLEx` now holds 1952 against 1949
pinned), reproducing at `c738b47`, untouched here. Whether it should be
re-pinned is filed, not decided.

`test_038_phon_empty_drop_live.py` (T090's stale-lock canary): **12 passed, 0
skipped both before and after** the live run. The run created no new
`.fwdata.lock`; the read-only probe in fact *released* a pre-existing stale
`Esperanto.fwdata.lock` by opening and closing cleanly. T090 is untouched.

## What this adds to the feature's ledger

This feature has now met the same defect eleven times - *something that exists
and is read at a level where it cannot do its job*. T096 is the first where
the thing that exists is a **contract**, and the level it was read at is **the
branch's git history**. The `TODO(contract)` was a correct, well-written note
pointing at a fix that had already shipped; nothing in the tree could tell it
so, because the branch had not seen the commit. The tripwire is what caught
it, and the tripwire only fired because someone rebased. That is a new
discovery channel for this feature - not a wave, not a live run, but a merge -
and it is worth recording that the branch was 48 commits behind for a day
while the answer sat on `main`.
