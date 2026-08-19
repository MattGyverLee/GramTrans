# T028 -- the roster gate, landed

**Date**: 2026-08-19
**Branch (specs)**: `main` (commit `d8635d9`)
**File written**: `specs/035-fullsweep-fidelity/contracts/natural-key-identity-roster.json`
**Gate**: `coordination.step_6` -- **SATISFIED**. Phase 4 is open.

## What T028 actually required, and who did which half

The task is a cross-feature coordination protocol
([contracts/natural-key-roster-extension.md](../contracts/natural-key-roster-extension.md)
section 5, lines 411-481), split deliberately across two features:

- **Step 1 -- 038's half**: commit the proposal to `main` so the 035 session can
  see it without a merge. Already done, at `36ae30f`.
- **Steps 2-5 -- 035's half**: claim the roster, append the six entries, record
  the op ids, re-run 035's checks, commit to `main`, release.
- **Step 6 -- 038's half**: do not begin matching code until the six entries are
  visible on `main`.

On resume, steps 2-5 had **not** happened. The roster carried 3 entries on `main`
*and* on 035's own branch (`a44cffe`), and no `lockout` claim was live, so no 035
session was mid-flight. Recorded decision (1) forbids 038 editing 035's file, so
the pipeline was genuinely stalled rather than merely slow, and every one of the
58 remaining tasks was downstream of it (Phase 5 "Depends on Phase 4", Phase 6 on
Phase 4 plus the affix merge, Phase 8 on Phase 7).

**The user authorised this session to act as the 035 session** and execute steps
2-5. That is an explicit override of recorded decision (1), and it is recorded
here as such rather than folded away: the decision still stands as the default,
and 038 has not otherwise touched anything under `specs/035-fullsweep-fidelity/`.

## What was written

Claimed the roster through `lockout` as team `fullsweep-fidelity-035`
(session `4207a8c4`, 60m TTL), edited, verified, committed, released.

**APPENDED**, verbatim and in the proposal's order, to the **end** of `entries`:
`PhPhoneme`, `PhNCSegments`, `PhNCFeatures`, `PartOfSpeech`, `MoMorphType`,
`LexEntryInflType`.

The proposal's seven op ids went under a **new sibling top-level key**
`live_confirmation_038`, which the protocol names as the recommended option
(step 4) precisely so the existing `live_confirmation` block -- whose narrative
is about WP-0 and the `reviews/cycle5-domain-identity.md` carry-over -- is not
retold. Alongside the ops it carries the method, the flexicon version, the three
projects measured, the two deliberately not opened, and the three pending
measurements reduced to `id` / `verdict` / `claim_not_confirmed`; the full text
of each stays in 038's proposal rather than being duplicated into 035's file.

### The edit was textual, not a reserialise

A `json.load` / `json.dump` round-trip would have reformatted all 13,767 bytes
and made "the original three entries stay byte-identical" unverifiable. The
script instead located the `entries` array by line anchor and spliced in
pre-indented blocks. Result: **512 insertions, 0 deletions**.

Zero deletions is worth a note, because the third entry's closing brace does
gain the comma JSON requires before a fourth element. Git reports no deletion
because it aligns the original `    }` line against the *sixth appended entry's*
closing brace and treats everything between as inserted -- so the diff is a pure
insertion in the strongest available sense.

## Verification -- protocol section 5's re-verify list, in full

| Check | Result |
|---|---|
| Roster still parses as JSON | PASS |
| `schema_version` still `1` (additive, not a bump) | PASS |
| `entries` went 3 -> 9 | PASS |
| Original three unchanged and still first | PASS |
| Six appended entries byte-identical to `proposed_entries`, in order | PASS |
| `deliberately_excluded` unchanged -- writing systems still excluded | PASS |
| `enforcement` and original `live_confirmation` unchanged | PASS |
| `live_confirmation_038` carries all seven op ids | PASS |
| Only one top-level key added | PASS |
| Every appended entry has `class` / `natural_key` / `reason` | PASS |
| Every appended entry sets `on_ambiguous_key=harness_error` | PASS |

## The predicted breakage does not exist

The protocol calls out "any 035 test pinning the roster to exactly three
entries, or enumerating the admitted class set" as **the most likely breakage**,
and gives it as a reason 035 rather than 038 should make the edit. Measured, it
is not there:

- 035's only consumer is `debug/fullsweep/identity.py`. `NaturalKeyRoster.load`
  keys entries by class name into a dict, requires `class` / `natural_key` /
  `reason` to be non-empty, and asserts only that the roster is **not empty** --
  there is no count assertion and no admitted-class enumeration.
- `tests/unit/test_035_compare.py` builds synthetic rosters in `tmp_path`
  (`_roster(tmp_path, _minimal(entries=[...]))`) rather than asserting against
  the tracked file.

Confirmed two ways rather than by reading alone:

1. Loaded the landed roster through 035's own loader with `contracts_dir` pointed
   at the main worktree. It admitted **9 classes**; the six new ones all report
   `key_unique_by_construction=False` and `on_ambiguous_key=harness_error`, and
   `deliberately_excluded` still reads `('writing systems',)`.
2. Ran 035's unit suite in the 035 worktree: `test_035_compare.py` **120 passed**;
   the whole `-k "035 or identity or roster"` selection **894 passed, 2 skipped,
   1 xpassed, 0 failed**.

## What this means for the code that follows

No entry was amended while landing, so the single-source-of-truth clause is
satisfied as written and 038's proposal needs no correction. **All six classes
were admitted -- none rejected** -- so the `if 035 rejects an entry` fallback
(no natural-key matching for that class, fall back to FR-007/FR-013) does not
fire for any class, and T029/T030 implement all six.

Two constraints the landed roster hands directly to T029/T030:

- Every one of the six sets `key_unique_by_construction=false`. The matcher may
  not shortcut candidate counting for any of them.
- Every one sets `on_ambiguous_key=harness_error`. Ambiguity is never a pick and
  never an IDENTITY-SUBSTITUTION record, which is what T026's tests already
  assert.

The 100 red tests in `tests/unit/test_038_natural_key.py` name the surface still
missing: `resolve_match` (75), `natural_key_for` (12), `NATURAL_KEY_BINDINGS`
(9), `NaturalKeyAmbiguityError` (2), `natural_key_eligibility` (1),
`KEY_INELIGIBLE_REASONS` (1). Their skip message pointed at this gate; it no
longer applies.

## Still open, and not closed by this task

`live_confirmation_038` carries the three pending measurements forward unchanged
-- **038-NK-P1** (blank-project starter baseline; corroborated by Esperanto's 23
phonemes but not measured), **038-NK-P2** (whether FLEx/LCM enforces name
uniqueness at all; only the absence of collisions in three projects was
observed), **038-NK-P3** (that the fallback recovers the measured losses; that is
a census diff, owned by T038/T039). None blocks admission, because every entry
already behaves as if uniqueness were absent.
