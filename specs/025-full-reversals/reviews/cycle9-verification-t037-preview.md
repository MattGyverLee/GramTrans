# T037 LIVE Validation -- Phase 1 (Read-Only Preview) -- Verification Report

**Date:** 2026-07-12
**Scope:** Feature 025-full-reversals, task T037, PHASE 1 ONLY (read-only Preview
evidence + a reusable headless driver). No write/Move performed. Phase 2 (the
destructive Move) is explicitly NOT run here and is gated by separate human
go-ahead.

**Status:** PHASE 1 PASS (read-only guarantee verified) with two notable
findings that should feed back to the programmer/lex-lead before Phase 2 is
authorized (see "Findings requiring follow-up" below).

**Source project:** Ejagham Mini (read-only, `writeEnabled=False`)
**Target project:** Target (`C:\ProgramData\SIL\FieldWorks\Projects\Target`),
opened `writeEnabled=False` for this phase -- NOT via `Lib/api.py.bind_target`
(which always opens the target `writeEnabled=True` and can flip the on-disk
`.plsx` projectSharing flag); `RunContext` was built by hand instead so this
phase touches nothing in Target's project folder.
**Code under test:** worktree `D:\Github\_Projects\_LEX\GramTrans-025-full-reversals`
(branch `025-full-reversals` @ `1a1849c`), run under the FLExTools `py`
launcher (Python 3.13.12).
**Driver script (reusable, has a `--move` flag that currently refuses to run):**
`C:\Users\thoua\AppData\Local\Temp\claude\d--Github--Projects--LEX-GramTrans\df5ecbb4-b4b3-4474-9c5e-34eda26728e4\scratchpad\t037_driver.py`
**Full raw run log:**
`C:\Users\thoua\AppData\Local\Temp\claude\d--Github--Projects--LEX-GramTrans\df5ecbb4-b4b3-4474-9c5e-34eda26728e4\scratchpad\t037_run1.log`

## Pre-run environment check

- `Target.fwdata.lock` existed on disk, referencing PID 1916 / "FieldWorks".
  Confirmed **stale**: PID 1916 is currently `fontdrvhost.exe` (PID reused by
  Windows), not FieldWorks -- Target was NOT open in FieldWorks during this
  run. `FLExProject.OpenProject(..., writeEnabled=False)` succeeded on the
  first attempt with no `FP_FileLockedError`, corroborating this.

## Pre-state evidence

**Writing systems** (identity match -- no WS mapping needed for this pair):
- Source (Ejagham Mini): `en`, `etu`
- Target: `en`, `etu`

**Source (Ejagham Mini) reversal inventory:**
| WS  | Index GUID | Top-level entries |
|-----|------------|--------------------|
| en  | 6a23951b-fe33-4a33-8b61-a98090d750bd | 135 |
| fr  | fcd28c0d-517d-4721-bacd-5f1f336d5519 | 0 |

**Target reversal inventory (pre):**
| WS  | Index GUID | Top-level entries |
|-----|------------|--------------------|
| en  | ab4d4345-85c4-49c4-9726-ef39ce155e64 | 0 |

**ConfigurationSettings `.fwdictconfig` listing (pre):**
| Project | Dictionary/ | ReversalIndex/ |
|---------|-------------|-----------------|
| Source  | 0 files | 1 file: `en.fwdictconfig` (size 102418) |
| Target  | 0 files | 1 file: `en.fwdictconfig` (size 102418, same size, different mtime) |

Source `ConfigurationSettings/{Dictionary,ReversalIndex}` directories both
already existed pre-run (`True`/`True`) -- relevant to the P0-1 no-new-source-
directories assertion below.

## Selection used (headless equivalent of the wizard)

`Selection(categories={GrammarCategory.STEMS: True})` -- the Phase 3c STEMS
leaf category with no `leaf_item_picks` filter enumerates every non-affix
`LexEntry` in the source (`stems_enumerate_source`), which registers every
top-level sense into `context._copy_set` during `build_run_plan`. This is a
superset of "senses referenced by reversal entries" (the Scenario 1 closure
in quickstart.md), but `reversals._gather_in_scope_entries` only ever plans
an index/entry that actually links >=1 copied sense, so selecting more than
the strict minimal closure introduces no spurious reversal decisions.
`WSMapping(entries=())` (identity) was used -- sufficient here since source
and target share WS ids `en`/`etu` (see Finding 2 below for why this choice
mattered more than expected).

Live check confirmed every reversal-linked sense in this corpus belongs to a
`MoStemAllomorph`-headed (stem) entry, not an affix entry, so STEMS alone was
a complete closure for this corpus -- AFFIXES was not needed.

## Run plan output (`preview.build_run_plan`, READ-ONLY, SC-006)

- `plan.actions`: 164
- `plan.skips`: 0
- `plan.reversal_decisions` (top-level): **134**
- `plan.config_view_records`: 1
- `plan.dropped_items`: 6

### Reversal decisions (`render_reversal_decisions`)

```
Reversal index [en] (Link):
  Add entry 'POSS 2P CLS8' -- links 1 sense(s)
  ... (132 more top-level Add entries) ...
  Add entry 'three' -- links 0 sense(s)
    Add entry 'CLS2,6' -- links 1 sense(s)
    Add entry 'CLS5,9' -- links 1 sense(s)
  ... (identical sub-entry-recursion shape also on 'two', 'they, them,
       their', 'POSS', 'your', 'his', 'one') ...
```

- `(Link)` on the `[en]` group header is correct: `target_index_ref=EXISTS`
  for every decision -- the target's pre-existing empty `en` reversal index
  (0 top-level entries, GUID `ab4d4345-...`) is correctly reused per R4
  ("if the target has a reversal index for the mapped WS, reuse it") rather
  than a second `en` index being planned for creation.
- `pos_decision=None` on every single decision -- confirmed this is because
  **no** reversal entry in this corpus has `PartOfSpeechRA` set at all (not a
  bug); see Scenario 2 mapping below.
- Sub-entry recursion (R6, `SubentriesOS`) is exercised and correctly
  indented/nested: 7 top-level entries (`three`, `two`, `they, them, their`,
  `POSS`, `your`, `his`, `one`) each carry 1-2 sub-entries, rendered as
  nested `Add entry` lines at +2 indent, matching `_render_one_reversal_
  decision`'s recursive contract.
- **134 vs 135 explained, not a bug:** Ejagham Mini's `en` index has 135
  top-level entries; exactly one (GUID `bda357d5-525a-43ed-9e17-eb6b017dfd2a`)
  has 0 `SensesRS` members and 0 `SubentriesOS` -- i.e. it is genuinely
  scope-empty at every depth. `_entry_has_scope`/`_gather_in_scope_entries`
  (R0.1/R3) correctly excluded it, silently (by design -- an empty-scope
  entry is not a mapping failure, so no `DroppedItemRecord` is expected or
  emitted for it). Verified directly against the live source data.
- The `fr` index (0 top-level entries in the source) never appears in the
  render -- correctly excluded before it would even reach the WS gate (R0.1).

### Config-view records (`render_config_view_records` / raw)

```
Configuration views:
  ReversalIndex:
    Skip (already up to date) 'en.fwdictconfig'
```

Raw: `kind=ReversalIndex filename='en.fwdictconfig' action=skip
src=...\Ejagham Mini\ConfigurationSettings\ReversalIndex\en.fwdictconfig
tgt=...\Target\ConfigurationSettings\ReversalIndex\en.fwdictconfig
missing_refs=0`. `filecmp` correctly determined the source and target files
are byte-identical content (same size, different mtime) and planned SKIP,
not OVERWRITE. No `Dictionary/*.fwdictconfig` exists on either side (0 files
both), so the Dictionary kind never appears -- expected, not a gap.

### Dropped items (never-silent report, all 6)

All 6 are pre-existing/out-of-scope, NOT reversal-specific: `owner_kind=
'LexEntry'`, `field='EntryRefsOS'`, each a variant-type `LexEntryRef` whose
reason is `"LexEntryRef (variant) is not reproduced by feature 024's
lexicon transfer -- no ILexEntryRefFactory create site exists (routed to
027-complex-forms-variants)"`. No `ReversalIndex`/`ReversalIndexEntry`-kind
dropped items occurred in this run (no unmapped WS, no partial-`SensesRS`-
member case in this corpus -- every `dropped_sense_members` count in the raw
dump above is 0).

## Read-only confirmation (post-state vs pre-state)

After `build_run_plan` returned, the driver re-collected every pre-state
metric and diffed:

```
[PASS] target WritingSystems unchanged: True
[PASS] target reversal inventory unchanged: True
[PASS] target ConfigurationSettings file listing unchanged: True
[PASS] source ConfigurationSettings dirs-exist unchanged (no new dirs, P0-1): True
```

Target's reversal inventory diff compares full recursive entry signatures
(`guid`, sorted linked-sense guids, recursively-signed sub-entries) not just
counts, so this also proves no entry/sense/sub-entry was created, linked, or
mutated anywhere in Target. `transfer.execute` was never called (confirmed
by code inspection of the driver -- there is no call site). **Confirmed:
Target is unchanged; no ConfigurationSettings directories were newly created
on the source (P0-1).**

## Findings requiring follow-up (discovered during live validation, both
## pre-existing in shared 024 code, exposed by this run -- NOT fixed here
## per the read-only guardrail)

**Finding 1 -- silent loss of reference decisions on ~89% of STEM entries
(latent bug, `Lib/references.py::divergence_fingerprint`).** 164 of ~165
enumerated STEM entries hit `TypeError: '<' not supported between instances
of 'int' and 'str'` inside `divergence_fingerprint`'s `sorted(snapshot.
items())` (references.py:505), caught by a broad `except (AttributeError,
TypeError, KeyError)` in `categories.py::_plan_entry_reference_decisions`
(categories.py:3480-3488) that logs a warning and **returns `()` with no
`DroppedItemRecord`**. Root cause: `_multistring_dict(ms, handle_to_id)`
produces an `{id: text}` snapshot whose keys are a MIX of resolved `str` WS
ids and unresolved raw `int` handles (when a multistring's WS handle is
absent from `handle_to_id`) -- `sorted()` over mixed-type keys raises. Net
effect: for the overwhelming majority of this corpus's stem entries (already
present in Target by GUID, since Target was evidently seeded from earlier
Ejagham content), **any real reference-field divergence/creation decision on
those entries is silently discarded** -- not shown in Preview, not in
`dropped_items`. This directly contradicts the never-silent contract (FR-010
/ Principle III) Scenario 5 is meant to guarantee, though it is a 024-era
code path, not part of 025's own reversal walk. It did **not** corrupt the
reversal-decision results above (reversal decisions are computed by a wholly
separate call, `plan_reversal_decisions` -> `reversals.plan_reversals`, which
only reads `context._copy_set`; copy_set registration for an entry's GUID and
all its top-level senses happens *before* the code that raises, per
`categories.py`'s own ordering), but it is a real completeness gap in the
STEMS closure this same run exercised. **Recommend:** route back to the
programmer to (a) fix `_multistring_dict`/`divergence_fingerprint` to fall
back consistently (all-`str` or all-`int` keys, never mixed) and (b) emit a
`DroppedItemRecord` from the catch-all in `_plan_entry_reference_decisions`
instead of silently swallowing.

**Finding 2 -- Preview never threads a non-identity WS mapping into the
reversal walk (`context._ws_map` is never set in `Lib/preview.py`).**
`reversals.plan_reversals` resolves each reversal index's target WS via
`ws_map = getattr(ctx, "_ws_map", None) or {}` (reversals.py:443), i.e. it
depends on `context._ws_map`. Move mode (`transfer.execute`, transfer.py:353)
sets `object.__setattr__(exec_ctx, '_ws_map', ws_map)` from the resolved
`WSMapping` before executing -- but `Lib/preview.py.build_run_plan` **never
sets `context._ws_map` anywhere** (confirmed by exhaustive grep of
`preview.py`); the `ws_mapping` parameter `build_run_plan` receives is
threaded to leaf-category `plan_action` calls and stored on the returned
`RunPlan`, but never applied to the reversal walk. Consequence: **Preview's
reversal Add/Link decisions and the R4 WS-gate are ALWAYS computed under an
identity WS mapping**, regardless of what non-trivial `WSMapping` the user
configured in the WS wizard -- a genuine Preview/Move parity gap specific to
reversals. It happened not to matter in this run only because source and
target already share WS ids `en`/`etu` (identity is correct here by
coincidence, not because the mapping was actually threaded through).
**Recommend:** `build_run_plan` should set `object.__setattr__(context,
'_ws_map', to_ws_map_dict(ws_mapping))` before calling `plan_reversal_
decisions`, mirroring `transfer.execute`'s own convention, so Preview and
Move agree on WS resolution for reversals in every case, not only the
identity case.

## Scenario mapping (quickstart.md Scenarios 1-5)

**Scenario 1 -- Reversal entries ride along with copied senses (Part A
closure): SUPPORTED-BY-THIS-DATA, exercised end-to-end at Preview level.**
134 top-level Add decisions with correct per-WS grouping (`[en] (Link)`,
reusing the target's existing empty index per R4), correct linked-sense
counts, correct `ReversalForm` alt carry (`form_alts={'en': '...'}`), and
correct `SubentriesOS` recursion (7 entries with nested sub-entry trees,
1-2 levels deep observed). The one silent (by-design) exclusion was verified
against live data to be a genuinely scope-empty entry, not a bug. Actually
writing these entries into Target (the Move-mode half of Scenario 1) is
explicitly out of scope for Phase 1 and untested here.

**Scenario 2 -- Reversal categories resolve against the per-index list:
NOT-EXERCISABLE-WITH-THIS-CORPUS.** Every one of the 134 reversal decisions
has `pos_decision=None` because **no** reversal entry in Ejagham Mini has
`PartOfSpeechRA` set at all (confirmed, not a bug in the resolver -- there is
simply nothing to resolve). Exercising the custom-create / diverged-shared-
default paths requires the dedicated fixture quickstart.md already calls for
("a reversal entry whose `PartOfSpeechRA` is a custom reversal category
absent from the target index, and a renamed default present-but-diverged")
-- this does not exist in either project today and was not fabricated per
this task's guardrail against faking data.

**Scenario 3 -- Writing-system gate: NOT-EXERCISABLE-WITH-THIS-CORPUS.**
Source and target share WS ids `en`/`etu` identically, so no index is ever
unmapped. The only other source index (`fr`) has 0 top-level entries and is
excluded at the R0.1 closure-scope gate *before* it would ever reach the WS
gate -- so it cannot exercise R4's "writing system not mapped" dropped-record
path either. Needs a dedicated fixture (a reversal index, with >=1 in-scope
entry, whose WS has no target counterpart). Note Finding 2 above also means
this scenario cannot currently be validated as PARITY between Preview and
Move even with such a fixture, since Preview's WS gate always runs under
identity regardless of the configured `WSMapping`.

**Scenario 4 -- Config views copied: PARTIALLY-SUPPORTED-BY-THIS-DATA.** The
enumerate/ADD-OVERWRITE-SKIP decision path and the file listing/`filecmp`
comparison are exercised and correct (`ReversalIndex/en.fwdictconfig` ->
SKIP, byte-identical). NOT exercised: an actual ADD (target missing the
file) or OVERWRITE (target has a diverged file) case, a `Dictionary/*.
fwdictconfig` file (source has none), and any `missing_refs` (custom
field/WS/style referenced by the config but absent from target) -- this
corpus's source and target share the same custom fields/WS/styles closely
enough that none were triggered. Needs a fixture target missing/diverging
the file, and/or a target lacking a WS/custom field/style the config
references, to exercise ADD/OVERWRITE and `missing_refs`.

**Scenario 5 -- Never-silent report (unified): PARTIALLY-SUPPORTED, WITH A
GENUINE GAP SURFACED (see Finding 1).** The unified `dropped_items` channel
correctly fired for the 6 out-of-scope `LexEntryRefsOS` variant cases (a
known 024/027 boundary, not a reversal concern) -- confirming the channel
itself works and reversal-owner-kind records (`ReversalIndexEntry`/
`ReversalIndex`/`ConfigView`) would land in the SAME list if triggered (none
were, in this corpus: 0 unmapped WS, 0 partial-`SensesRS`-member cases, 0
missing config refs). However, Finding 1 shows the never-silent guarantee is
**currently violated** for a large class of pre-existing-by-GUID entries
during a STEMS closure walk (the `_plan_entry_reference_decisions` catch-all)
-- this should block treating Scenario 5 as fully verified until Finding 1 is
fixed, even though it is not itself part of 025's own code.

## Fidelity census / unit tests

Not run in this task (T037 scope is the LIVE headless Preview validation and
driver; `pytest tests/verification/fidelity_census.py` and the unit suite
listed in quickstart.md are separate, already-covered by prior cycles'
automated CI/verification passes per the review history in this directory).

## Deliverables

- Reusable headless driver (Phase 1 read-only; `--move` flag present but
  hard-refuses until Phase 2 is wired up and authorized):
  `C:\Users\thoua\AppData\Local\Temp\claude\d--Github--Projects--LEX-GramTrans\df5ecbb4-b4b3-4474-9c5e-34eda26728e4\scratchpad\t037_driver.py`
- Full raw run log (includes the Finding 1 tracebacks, in full, for the
  programmer):
  `C:\Users\thoua\AppData\Local\Temp\claude\d--Github--Projects--LEX-GramTrans\df5ecbb4-b4b3-4474-9c5e-34eda26728e4\scratchpad\t037_run1.log`
- No blocker to reporting THIS phase as PASS: the read-only guarantee (SC-006,
  P0-1) held completely, and Scenario 1 (the feature's core Part-A claim) is
  confirmed working against live data. Findings 1 and 2 above should be
  triaged before Phase 2 (Move) is authorized against a real target, since
  Finding 1 is an active fidelity-completeness violation and Finding 2 means
  Preview cannot currently be trusted to predict Move's reversal behavior
  whenever a real (non-identity) WS mapping is in play.

---
**Verified By:** Verification Agent
**Date:** 2026-07-12
