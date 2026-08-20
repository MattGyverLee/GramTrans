# The T028 tripwire fired, and its remedy

**Status:** closed. `tests/integration/test_object_census.py` only -- no
production code changed, which the old test predicted ("038's roster extension
flips this without touching census.py").

## What fired

`TestDuplicatePhonemesAreInertUntilT028::test_t028_has_not_yet_admitted_phphoneme_to_the_roster`
pinned 035's natural-key roster to exactly
`("WfiWordform", "ReversalIndex", "ReversalIndexEntry")` and asserted
`"PhPhoneme" not in admitted`. Its docstring says plainly: "THIS TEST FAILS THE
MOMENT T028 LANDS, and that is its job."

T028 landed on **2026-08-19 22:15** (commit `d8635d9`), appending six classes.
The tripwire has been red ever since -- roughly a day before this session
started, and it was not the task being worked, so it went unnoticed until the
full integration file was run during T048g.

Its remedy note was explicit: *"REGENERATE
`tests/integration/_snapshots/census-038-*.json` and move the duplicate
assertions in `TestDuplicatePhonemesAreInertUntilT028` from 'phase 1
unsatisfied' to `DUPLICATE_IDENTITY` / exit 3. Do not simply update this list."*

## Half of that remedy is impossible, and the reason matters

**The assertions moved. The snapshots were not regenerated, and cannot be.**

`roster_admitted` is not a measurement. `census._class_row` derives it at run
time as `name in roster_admitted_classes()` (`census.py:1810`), and
`roster_admitted_classes` reads the roster file for exactly this reason, stated
in its own docstring: "the six entries feature 038 proposes (T028) become
gate-failing the moment 035 merges them, with no edit here" (`census.py:1604`).
The stored flag is a cached derivation that went stale eight hours after the
snapshots were committed (13:47 vs 22:15, same day).

So the flag needs **re-deriving, not re-measuring** -- and re-measuring is
blocked three ways over:

* The source projects have moved. The T024 live block in the same file already
  skips itself because `Ejagham W Mini` (`5ad15c10...` vs recorded
  `c174f0b4...`) and `Ngoreme FLEx` no longer match their pinned digests.
* `Ngoreme Target` is pinned in `MEASURED_PROJECT_DIGESTS` as "irreplaceable
  evidence of a ruined transfer: it must never be write-enabled or restored".
* A real re-run would not reproduce these numbers anyway, and should not: under
  natural-key matching the transfer should now MATCH those phonemes instead of
  duplicating them, so the duplicates should largely disappear. That is
  `038-NK-P3` ("recovery verified by re-census"), already owned by **T082**.

`with_current_roster_admission()` re-derives the one derived field against the
current roster and refreshes the one total that reads it (`census.py:2708`),
leaving every measured count -- groups, extra objects, example GUIDs,
differences -- untouched. It is what a census would derive today from the same
observations, and its docstring says in as many words that it is not a stand-in
for a live re-census.

## The remedy note undercounted: it is not only PhPhoneme

T028 admitted **six** classes, and three of them carry duplicates in these
snapshots. Re-deriving admission moves the artifact-level total well past the
phoneme row:

| Pair | PhPhoneme | PhNCFeatures | PhNCSegments | `duplicate_extra_objects` |
|---|---|---|---|---|
| ejagham | 21 | 3 | 1 | 0 -> **25** |
| ngoreme | 20 | 21 (12 groups) | 1 | 0 -> **42** |

Ngoreme's `PhNCFeatures` contributes slightly MORE extra objects than its
phonemes do. Pinned in
`test_admission_moves_the_headline_total_past_the_phoneme_row`, because the
remedy note would have left it unmeasured.

Verified on both pairs after re-derivation: `duplicates_unaccounted` equals the
row's extra objects, `row_passes` False, `recompute_verdict`
**`DUPLICATE_IDENTITY`**, `exit_code_for` **3**, `gate_artifact().passed` False
-- exactly what T024's brief originally predicted and could not get.

## What the class looks like now

Renamed `TestDuplicatePhonemesAreInertUntilT028` ->
`TestDuplicatePhonemesWereInertUntilT028Landed`. Nine tests, in three groups:

* **unchanged observations** -- the 20/21 duplicate groups, their GUIDs and
  counts, which admission never touched.
* **the moved assertions** -- `DUPLICATE_IDENTITY` / exit 3 on the re-derived
  artifact, the headline-total table above, and phase 1's SC-002 wording
  asserted on BOTH readings (it reads `duplicates.extra_objects`, not
  admission, so it caught this before T028 and still does; kept so it cannot
  quietly become redundant now that the verdict fires too).
* **the before-picture, asserted deliberately** -- read raw, the snapshot still
  says `roster_admitted: false` / `duplicate_extra_objects: 0`. That is the
  reading the old tripwire existed to stop anyone taking as a clean result, and
  it is kept because it is the state the fix gets compared against.

`test_the_inertness_is_roster_gating_not_a_broken_detector` proved the
machinery by flipping the flag ON. With admission now real, its replacement
proves the same thing from the other side: force the flag OFF and the inertness
returns exactly. Neither reading is a rotted code path; both are the roster
speaking.

## The replacement tripwire

A spent tripwire is worse than none -- it reads as live coverage. The old one
asked "has T028 landed yet?", and that answer is now permanently yes.

`test_the_snapshots_predate_the_roster_landing` asks the question that stays
live: `artifact["generated_at"] < ROSTER_T028_LANDED_AT`. It fires if anyone
regenerates a snapshot, at which point `roster_admitted` arrives already True,
`with_current_roster_admission` silently becomes a no-op, and the before/after
split this class is built on has to be retired rather than quietly kept.

`test_t028_has_landed_and_admitted_all_six_proposed_classes` records the
outcome. It asserts 038's six as a SUBSET, not the roster's exact ordered
tuple -- pinning the exact list is what made the old test fire on a change that
was not about these fixtures, and a seventh class joining 035's roster is not
by itself a reason to revisit them. It does still pin that the original three
stay first and unchanged, matching the T028 journal's "512 insertions, 0
deletions".

## The second site, which was skipping rather than failing

`test_the_duplicates_do_NOT_raise_the_verdict_to_duplicate_identity` in the
T024 live block carried the identical stale premise, including its own
`assert "PhPhoneme" not in census.roster_admitted_classes(...)` with a remedy
note. It was invisible only because the whole T024 live block self-skips on the
changed source digests -- so it would have failed the next time anyone ran with
matching projects.

Inverted to `test_the_duplicates_DO_raise_the_verdict_now_that_t028_landed`.
Being a LIVE census, it needs no re-derivation helper: `roster_admitted` comes
from the roster at run time. Its total is asserted `>=` the phoneme count
rather than `==`, for the six-classes reason above. It cannot be executed here
(the digest guard skips it), so it is written to follow directly from the
hermetic counterpart
`test_admitting_phphoneme_to_the_roster_makes_the_duplicates_fail`, which
already proves the machinery with no live project.

## Verification

* `tests/integration/test_object_census.py`: 231 passed, 29 skipped, 0 failed.
* `tests/unit` + that file: 3583 passed, 108 skipped, 14 xfailed, 14 xpassed.
* Whole suite before this change: **25 failed**. After: **24 failed**. The one
  removed is the tripwire; nothing else moved.

## Unrelated, still open

The 24 residual failures are all
`tests/integration/test_affix_pos_picker_live.py` (`TestEsperantoInventory`).
They **skip when that file is run alone**, on the clean tree and with these
changes alike, and **fail only inside a full-suite run** -- a session-ordering
artifact in that file's skip guard, present before this change and untouched by
it. Not filed here; it needs its own look.

The recurring `Windows fatal exception: access violation` on stderr is likewise
pre-existing pythonnet interop noise, reproduced on the clean tree, and does not
fail any test.
