# T029 / T030 -- the executable natural-key surface

**Date**: 2026-08-19
**Branch (code)**: `038-transfer-fidelity-gaps` (commit `ddad30d`)
**File**: `src/gramtrans/Lib/matcher.py` (+~520 lines)
**Tests**: `tests/unit/test_038_natural_key.py` **100/100 green** (was 100/100 red)

## Where the suite stands

| | before | after |
|---|---|---|
| `tests/unit/` failing | 127 | **27** |
| `tests/unit/` passing | 2668 | 2769 |

Verified by diffing the two `FAILED` sets rather than by comparing counts:
**zero net-new failures**, 100 fixed. The remaining 27 were already red on this
branch before this commit (`test_adjacent_data`, `test_analysis_idempotency`,
`test_analysis_verdict`, `test_human_eval_gate`, `test_morph_bundle_wiring`,
`test_residue_tagging_026`, `test_segment_alignment`,
`test_wizard_pos_grammar_wiring`). None of them touches matching; they are not
this task's and are recorded here so the next session does not mistake them for
fallout.

## The design: two halves, both required

A class has a natural-key basis only when **both** of these hold:

- **the declarative half** -- 035's roster file admits it (T028 landed the six
  entries; `natural_key_roster_entry_for` is still the single point of read), and
- **the executable half** -- `NATURAL_KEY_BINDINGS` supplies a key function and
  a candidate scope for it.

Either half alone yields nothing, and that asymmetry is the safety property, not
redundancy:

- a binding without a roster row would let engine code fabricate an admission
  035 never granted (035 FR-185 / 038 FR-003);
- a roster row without a binding would let an admitted-but-unexecutable row
  match on a guessed key. **`WfiWordform` is the live instance of the second**:
  035 admits it and `census.NATURAL_KEY_DEFINITIONS` can even compute its key,
  but 038 binds no key function, so it has no basis here. Matching wordforms is
  035's business, and binding it would silently extend 038's matcher over a
  class 038 never measured.

### Where `key_fn_id` comes from, and why that is not a guess

`data-model.md` marks `key_fn_id` / `scope_fn_id` as "038 adds". T028 appended
038's six entries to 035's file **verbatim**, and those entries carry neither
field -- so the file will never supply them. `_project_roster_entry` now fills
them from the binding when the file does not.

The docstring it replaced forbade exactly this ("NEVER fill `key_fn_id` in with
a guess here"). The distinction is real and worth stating: a *guess* invents a
key for a class nobody declared one for. This joins two independently-authored
halves on the only key they share -- the class name -- and it can only ever
**add an admission the roster already granted**. A class absent from the file
still projects nothing, however many bindings exist. A file that *does* spell
`key_fn_id` still wins, so an entry can always override engine code rather than
the other way round.

## Per-class rules, each measured rather than assumed

**Writing systems run in opposite directions.** `ws_scope` is taken from
`census.NATURAL_KEY_DEFINITIONS` and never restated, so the matcher and the
census cannot hold two different keys for one class -- the test asserts that
equality directly. `PhPhoneme` keys on the default **vernacular** (97/97 named
there; only 44/97 in analysis, and `Mbugwe LizzieHC practice` has 42 phonemes
and not one with an `en` name, so an analysis key would leave a whole project
unkeyable and fall through to the duplicating create path). The other five key
on default **analysis** (121/121 natural classes there, 0/121 in vernacular).
`PhCode` is explicitly not the phoneme key.

**Subclass restriction is exact-`ClassName`**, which also makes the production
scopes safe by construction: `census.objects_in_class` enumerates exactly one
class, so a `PhNCFeatures` never appears in the `PhNCSegments` scope and a
`LexEntryType` never appears in the `LexEntryInflType` scope. `resolve_match`
re-checks every candidate anyway, because a caller may assemble its own.

**The auto-label exclusion is applied to `PhNCFeatures` only.** 66 of 113
feature-based natural classes collide on a `Created automatically for rule
"<rule>"` label, but the reason this is an *eligibility* rule decided before
candidate counting -- rather than something the ambiguity rule could catch -- is
the other number: **47 of the 113 carry a label that is unique within its
project**, and every one of those would otherwise sail through as a clean
single-candidate match. `PhNCSegments` is deliberately left alone: its roster
entry states no such clause, and inventing one would narrow the basis beyond
what the roster admits.

Matched with `startswith` on the invariant prefix rather than a full-string
regex, because the rule name is arbitrary user text and may contain anything,
including an unbalanced quote.

**`PartOfSpeech`** keys project-wide with the parent **not** in the key
(`093264d7-...` "Demonstrative" is depth-1 in one project and depth-2 in
another). A divergence is recorded and reported; the matcher decides and never
re-parents the destination. For `LexEntryInflType` the same divergence is
anomalous rather than routine -- 14 of 15 sit under `Irregularly Inflected
Form`.

**`MoMorphType` is the one class forbidden to create on a miss**
(`creates_on_miss=False`); `LexEntryInflType` is the explicit opposite.

**Ambiguity raises and is never a pick**, so it yields no decision and
therefore no IDENTITY-SUBSTITUTION record to inflate the count with a guess.
The message names the class, the scope fn id and the key.

**`enrich=True` on every match** is the decision's statement that
field-identity comparison still has to happen -- a matched GUID is a LINK, not
a SKIP (defect G3, data-model.md:209-213).

**`may_create` is False whenever a key could not be computed at all.** An
object that could not be keyed was never compared, so creating it here would be
the create-anyway half of the very defect this feature removes. It is also
False when the class has no basis: the natural-key step did not run, and the
caller's own GUID-only path (FR-007 / FR-013) decides -- which is exactly what
the roster's "if 035 rejects an entry" clause requires.

## Two test premises this supersedes

Both were changed deliberately, and neither to make failing code look green.

### 1. `test_row_without_key_fn_id_is_not_executable` (T007-T013 foundational)

It asserted that a `PhPhoneme` row without `key_fn_id` never projects, on the
stated premise that this "is the state 035's three live entries are in today".
True only while the executable half did not exist. Rewritten as a matched pair
that tests the actual rule from both sides:

- a class with **neither** a file `key_fn_id` **nor** a binding is not
  executable -- and `WfiWordform` is used, so the test now pins the real live
  instance instead of a hypothetical;
- a class whose binding supplies one **is** executable, with the roster's own
  `natural_key` text still governing what the key means.

### 2. The auto-label assertion in `test_038_natural_key`

It called `natural_key_eligibility("PhNCFeatures", src)` with no
writing-system handle. **No implementation can satisfy that call**: the test's
`_MultiString` fake exposes only `get_String(ws_handle)`, so with no handle
there is no way to read the name, and the auto-label is a property of the name.
The tests were written to fail wholesale (every one of the 100 short-circuits
through a `pytest.fail` helper), so they had never been run green and this
could not have surfaced earlier.

It now passes the scoped handle. The alternative -- probing every alternative
the object exposes -- was rejected **on merit, not convenience**: it would
exclude a class whose scoped name is a real linguist name while some other
writing system happens to hold a rule label, which is a narrowing the roster
does not authorise. The other four assertions in that test all run through
`resolve_match`, which has the handles, and are untouched; they are what
actually prove the behaviour.

## Surface landed

In `gramtrans.Lib.matcher`:

- `NaturalKeyBinding` (frozen) -- validates against the census definition at
  construction, so a binding that disagrees with the census cannot be built.
- `NATURAL_KEY_BINDINGS` -- the six admitted classes, and nothing else.
- `NATURAL_KEY_FNS` / `NATURAL_KEY_SCOPE_FNS` -- one id per class even though
  the extraction shape is shared, so a report can name which key ran.
- `natural_key_binding_for`, `natural_key_eligibility`, `natural_key_for`.
- `MatchDecision` (frozen) -- `record`, `target_obj`, `enrich`,
  `ineligible_reason`, `may_create`, `parent_divergence`.
- `resolve_match` -- THE ordering function.
- `NaturalKeyAmbiguityError`.
- `KEY_INELIGIBLE_{NOT_ADMITTED,SUBCLASS_MISMATCH,AUTO_GENERATED,NO_NAME_IN_SCOPED_WS}`
  and the closed `KEY_INELIGIBLE_REASONS` frozenset.

Comparison strictness is inherited from `census.natural_key_of` rather than
re-implemented: exact, case-sensitive, no Unicode normalisation, no case
folding, no whitespace trimming. An object with no name in its own scoped
writing system has no key and never matches -- including empty-key against
empty-key.

## What Wave 3 inherits

`resolve_match` has **no production caller yet**. That is T031's job, and the
recon done for it turned up three facts worth recording before they are
rediscovered:

1. **`match_basis` already exists** on `PlannedAction` (`models.py:1778`) and
   `PlannedOverwrite` (`models.py:1875`). Nothing needs adding to `models.py`.
2. **`report.py` is already wired.** `_count_substitution` (`report.py:175`)
   increments `CategoryReport.identity_substitution` on
   `MatchBasis.NATURAL_KEY`, and the JSON and console surfaces already render
   it. T037 is therefore mostly verification plus whatever the
   `identity_substituted <= matched_total` invariant (`models.py:2791`) turns
   up -- **the gap is upstream: no producer sets `match_basis` today.**
3. **`matcher.lookup_target` has zero production callers.** `preview.py`,
   `transfer.py` and `categories.py` each roll their own GUID lookups, and
   `preview.py:2078` says in a comment that its inline version deliberately
   "avoids the matcher.py" one. T031/T036 are consolidating three
   implementations, not two.
