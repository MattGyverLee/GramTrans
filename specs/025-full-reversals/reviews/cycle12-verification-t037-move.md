# T037 LIVE Validation -- Phase 2 (the DESTRUCTIVE Move) -- Verification Report

**Date:** 2026-07-13
**Scope:** Feature 025-full-reversals, task T037, PHASE 2 -- the authorized
destructive Move against a live disposable target. Source: Ejagham Mini
(read-only throughout). Target: `Target` (`C:\ProgramData\SIL\FieldWorks\Projects\Target`,
disposable, confirmed -restore-ready by the user).

**Status: FAIL (partial) -- Scenario 1 write-half is PASS for top-level
reversal entries but FAIL for sub-entries.** The Move ran to completion,
committed, and persisted (no crash, no partial write, no lock left behind).
134/134 planned top-level reversal entries were created with correct
structure, correct recursive sub-entry nesting, correct form text, correct
index reuse, and correct isolation from LangProject.PartsOfSpeechOA and the
config-view file. However, a genuine bug in Lib/reversals.py (feature
025's own code, not shared 024 code) silently drops the sense link on every
reversal SUB-entry -- every sub-entry sampled shows 0 linked senses on
fresh re-open, even where Preview correctly predicted 1. This is a real,
previously-undiscovered data-fidelity defect that should route back to the
programmer before this feature is considered release-ready. Two additional,
unrelated 024-era bugs were also exposed live during this run (see Findings
below) -- neither blocks the reversal verdict, but both are real gaps worth
tracking.

**Code under test:** worktree D:\Github\_Projects\_LEX\GramTrans-025-full-reversals
(branch 025-full-reversals @ b8d325d, includes the two Phase-1 Finding
1+2 fixes), run under the FLExTools py launcher (Python 3.13.12).
**Driver script (Phase 2, wires the Move that Phase 1's driver refused to run):**
C:\Users\thoua\AppData\Local\Temp\claude\d--Github--Projects--LEX-GramTrans\df5ecbb4-b4b3-4474-9c5e-34eda26728e4\scratchpad\t037_move_driver.py
**Full raw run log (includes the pre-write Preview dump, the write, and the
post-write persistence re-check):**
C:\Users\thoua\AppData\Local\Temp\claude\d--Github--Projects--LEX-GramTrans\df5ecbb4-b4b3-4474-9c5e-34eda26728e4\scratchpad\t037_move.log

## 1. Safety precheck

- No `.lock` file existed on Target at the start of the FIRST attempt; no
  FieldWorks/FLEx process was running (`Get-Process` showed only three
  `flextoolsmcp` server processes and a handful of unrelated `py`/`python`
  processes -- none named FieldWorks/FLEx).
- **The first driver attempt crashed** (see "Incident" below) mid-Preview-dump
  on a `UnicodeEncodeError` printing a non-ASCII gloss to the Windows cp1252
  console, **before `transfer.execute` was ever called** -- no write occurred.
  The crash bypassed the driver's own `target.CloseProject()` line, leaving an
  orphaned `Target.fwdata.lock` referencing the now-exited driver process's
  own PID (46236).
- The driver was patched (UTF-8-safe stdout/stderr reconfigure; a
  defense-in-depth `finally` that attempts an emergency `CloseProject()` if
  the normal one never ran; and a PID-aware lock precheck that reads the
  lock's JSON, checks `tasklist /FI "PID eq <pid>"`, and only refuses if the
  claimed PID is actually running) and re-run. The precheck correctly
  identified the leftover lock as stale (PID 46236 not running, matching
  Phase 1's own stale-lock precedent) and proceeded.
- The second attempt ran to completion (exit code 0), including a clean
  `target.CloseProject()` and a clean re-open.

## 2. Pre-Move Target state (second, successful attempt)

**Writing systems** (identity, unchanged from Phase 1): source `en`, `etu`;
target `en`, `etu`.

**Target reversal inventory (pre):**
| WS | Index GUID | Top-level entries |
|----|------------|--------------------|
| en | ab4d4345-85c4-49c4-9726-ef39ce155e64 | 0 |

Matches cycle9's Phase-1 pre-state exactly (same index GUID, same 0 count).

**Target ConfigurationSettings\ReversalIndex\en.fwdictconfig (pre):**
size=102418, mtime=1783803026.4696004 (same mtime as Phase 1's earlier
read -- confirming Phase 1 never touched it either).

**Target LangProject.PartsOfSpeechOA (pre):** count=13, GUIDs:
25b2ef8c-..., 30d07580-..., 46e4fe08-..., 65999a97-..., 6df1c8ee-...,
6e0682a7-..., 6e758bbc-..., 86ff66f6-..., 923e5aed-..., a4fc78d6-...,
a8d31dff-..., a8e41fd3-..., e680330e-... (full GUIDs in the raw log).

## 3. The Preview plan, shown BEFORE any write (Principle III)

Built via the SAME `preview.build_run_plan(context, selection, ws_mapping,
source, target)` call as Phase 1, `Selection(categories={STEMS: True})`,
identity `WSMapping(entries=())`:

- `plan.actions`: 164
- `plan.skips`: 0
- `plan.reversal_decisions` (top-level): 134 -- identical to cycle9
- `plan.config_view_records`: 1 (en.fwdictconfig -> Skip, byte-identical)
- `plan.dropped_items`: 265 (see Finding 3 below for why this is much larger
  than cycle9's 6 -- it is the Finding-1 fix from cycle11 correctly no
  longer swallowing real reference-decision divergences)

`render_preview_extra_lines(plan)` was printed via the driver in full
(the log's "SHOWN BEFORE WRITE" section) -- the same 134 Add entry lines as
cycle9, including the 7 sub-entry-bearing parents (three, two, they,
them, their, POSS, your, his, one) each showing their nested Add entry
sub-lines with predicted per-sub-entry sense counts (mostly 1, one
exception -- one's CLS8,14 sub -- correctly predicted 0).

## 4. The Move (transfer.execute) -- the write

```
report = gt_transfer.execute(plan, source, target, sink, tag)
```

- `execute()` returned in 1.63s.
- `report.mode`: RunMode.MOVE
- `report.per_category['stems']`: added=164, skipped=0 (this count is
  built from the plan, not from actual per-action success -- see the
  swallowed-exception note below; it does not by itself prove all 164
  entry-writes succeeded).
- `report.skips`: 0
- `report.dropped_items`: 337 (up from the Preview's 265 -- see Finding 3)

One swallowed exception occurred during leaf-dispatch, logged to console but
NOT surfaced as a dropped_items record (see Finding 2 below):
```
[WARN]   [stems] execute_action raised AttributeError: 'FLExProject' object
has no attribute 'get_object_by_guid'; skipping fe37d00b
```

## 5. Persistence -- close, then FRESH re-open (read-only)

target.CloseProject() completed in 1.07s (EndNonUndoableTask + Save +
Dispose, per flexicon.FLExProject.CloseProject). Target was then re-opened
fresh, writeEnabled=False, in a brand-new FLExProject() handle (not
the same in-memory object) to prove the write actually persisted to disk
rather than only existing in the write-session's in-memory cache.

**Target reversal inventory (post, fresh open):**
| WS | Index GUID | Top-level entries |
|----|------------|--------------------|
| en | ab4d4345-85c4-49c4-9726-ef39ce155e64 (SAME guid -- reused, not recreated) | 134 |

134/134 matches the plan exactly.

**Target en.fwdictconfig (post, fresh):** size=102418,
mtime=1783803026.4696004 -- byte-for-byte identical mtime to the pre-Move
read, confirming the SKIP decision held and no file write/.gtbak occurred.

**Target LangProject.PartsOfSpeechOA (post, fresh):** count=13, the
exact same 13 GUIDs as pre-Move (verified by full list comparison, not just
count) -- confirmed untouched, consistent with every pos_decision in
this corpus being None (no reversal entry in Ejagham Mini has
PartOfSpeechRA set).

### Sample of written top-level entries (first 10 alphabetical-by-GUID)

```
guid=003b5c9d-904b-48fb-8402-1fa5b502a971  form='dance, rhythm or music'  senses=1  subentries=0
guid=0386c477-13bf-43b4-b47b-85dd8a602d6c  form='twins'                   senses=1  subentries=0
guid=06162d6b-91b3-4d8d-b835-445618088bde  form='friend'                  senses=1  subentries=0
guid=0900c226-9ed8-4891-8048-f667284e378e  form='POSS 2P CLS9'            senses=1  subentries=0
guid=0b2e7aa8-149f-4997-b661-6d2cde12cd40  form='one:CLS9'                senses=1  subentries=0
guid=0c508e3e-be95-475c-a70e-2971397ad492  form='friendship'              senses=1  subentries=0
guid=0f38229a-72a4-4fe1-b2c8-abf980e44c20  form='paddle'                  senses=1  subentries=0
guid=0fbae16b-81b2-4de8-9387-5b7162b632d4  form='white yam'               senses=1  subentries=0
guid=12d94b6b-e67d-44d5-bc73-d6938eb39946  form='deep pool'               senses=1  subentries=0
guid=14869b9d-d4ac-4e7d-94a5-b45e83a69bc3  form='your:S CLS3'             senses=1  subentries=0
```

A supplementary targeted spot-check of the 3 multi-sense top-level entries
Preview predicted (foot, leg, palm frond, each "links 2 sense(s)")
confirms senses=2 for all three -- top-level multi-sense linking is
correct:
```
TOP form='leg'         guid=8e47f0af-...  senses=2  subentries=0
TOP form='palm frond'  guid=bbcd8e90-...  senses=2  subentries=0
TOP form='foot'        guid=e09d1bf1-...  senses=2  subentries=0
```

GUIDs on every written entry are new (not preserved from source) -- this
matches the documented US1 hedge: _create_top_level_entry's wrapper
(target.ReversalEntries.Create(...)) and _create_sub_entry's raw factory
path both have no GUID parameter, so source-GUID preservation was never
possible for reversal entries "where the create path allows" (it never
allows, here).

### Sub-entry recursion -- structure PASS, sense-linkage FAIL

All 7 known sub-entry-bearing parents were located and their sub-entry
COUNTS and NESTING exactly match the plan:

```
ENTRY form='two'                guid=17b36447-...  subentries=2
   sub form='CLS2,6'   guid=21aa55dd-...  senses=0
   sub form='CLS5,9'   guid=bce2e57f-...  senses=0
ENTRY form='his'                guid=451e0a54-...  subentries=1
   sub form='3S CLS5'  guid=022a16d9-...  senses=0
ENTRY form='they, them, their'  guid=69127ef9-...  subentries=1
   sub form='3p'       guid=c093c9ef-...  senses=0
ENTRY form='one'                guid=af1ec46c-...  subentries=2
   sub form='CLS2,CLS6' guid=6b86480b-...  senses=0
   sub form='CLS8,14'   guid=a0ec9a2d-...  senses=0
ENTRY form='your'               guid=b08d6e55-...  subentries=1
   sub form='2S CLS5'  guid=80c50b73-...  senses=0
ENTRY form='POSS'               guid=e02543c1-...  subentries=1
   sub form='2S CLS6'  guid=ffbef70a-...  senses=0
ENTRY form='three'              guid=ef9706a9-...  subentries=2
   sub form='CLS2,6'   guid=24d4f98b-...  senses=0
   sub form='CLS5,9'   guid=02846461-...  senses=0
```

A supplementary spot-check of the PARENT entries' own sense counts confirms
they correctly show senses=0 at their own level (their senses live on the
sub-entries, per Preview's "links 0 sense(s)" on the parent Add entry line):
```
TOP form='two'                guid=17b36447-...  senses=0  subentries=2
TOP form='his'                guid=451e0a54-...  senses=0  subentries=1
TOP form='they, them, their'  guid=69127ef9-...  senses=0  subentries=1
TOP form='one'                guid=af1ec46c-...  senses=0  subentries=2
TOP form='your'               guid=b08d6e55-...  senses=0  subentries=1
TOP form='POSS'               guid=e02543c1-...  senses=0  subentries=1
TOP form='three'              guid=ef9706a9-...  senses=0  subentries=2
```

But every one of the 10 sub-entries above shows senses=0, even though
Preview predicted links 1 sense(s) for 9 of them -- only one's
CLS8,14 sub was correctly predicted AND observed as 0 -- the other 9 are a
100% miss. Cross-referencing the pre-write Preview dump:

```
Add entry 'three' -- links 0 sense(s)
  Add entry 'CLS2,6' -- links 1 sense(s)      <- observed senses=0 (BUG)
  Add entry 'CLS5,9' -- links 1 sense(s)      <- observed senses=0 (BUG)
... (two, they/them/their, POSS, your, his: same pattern)
Add entry 'one' -- links 0 sense(s)
  Add entry 'CLS2,CLS6' -- links 1 sense(s)   <- observed senses=0 (BUG)
  Add entry 'CLS8,14' -- links 0 sense(s)     <- observed senses=0 (correct, predicted 0)
```

## 6. Root cause (Finding 1 -- feature 025's own code, P0)

Lib/reversals.py::_apply_one_entry drops the first linked sense for
every sub-entry, because it assumes the create call already linked it --
an assumption that is only true for top-level entries.

```python
target_senses = [...]                          # reversals.py:807-810
first_sense = target_senses[0] if target_senses else None   # :811
...
if parent_target_entry is None:
    new_entry = _create_top_level_entry(
        target, target_index, primary_text, first_sense, decision, dropped)   # :825-826
else:
    new_entry = _create_sub_entry(
        target, parent_target_entry, primary_ws_id, primary_text, decision, dropped)  # :828-829
...
remaining_senses = target_senses[1:] if first_sense is not None else target_senses    # :838
_link_remaining_senses(new_entry, remaining_senses)                                    # :839
```

- _create_top_level_entry calls target.ReversalEntries.Create(target_index,
  primary_text, first_sense) -- the wrapper's own sense parameter links
  first_sense as part of the create call (research.md R1's confirmed-live
  wrapper). For a top-level entry, remaining_senses = target_senses[1:] is
  therefore correct: sense #1 is already linked, so only #2+ need
  _link_remaining_senses.
- _create_sub_entry's signature is (target, parent_entry, primary_ws_id,
  primary_text, decision, dropped) -- it never receives first_sense at
  all, and its body (raw IReversalIndexEntryFactory.Create() +
  parent.SubentriesOS.Add(...) + _set_reversal_form_alt(...)) never links
  any sense to the new sub-entry.
- Line 838's remaining_senses = target_senses[1:] if first_sense is not
  None else target_senses is evaluated identically regardless of which
  branch created new_entry. For a sub-entry with exactly one linked
  sense, target_senses = [sense], so first_sense = sense and
  remaining_senses = target_senses[1:] = [] -- the one sense this
  sub-entry was supposed to carry is silently dropped, not linked by
  either the (nonexistent, for subs) create-time link OR by
  _link_remaining_senses (which receives an empty list). For a sub-entry
  with 0 linked senses the bug is invisible (both branches produce []
  regardless), which is exactly why one's CLS8,14 sub-entry looked
  correct while every other sampled sub-entry did not.

Impact: every reversal sub-entry that should carry exactly one linked
sense (the common case -- Ejagham Mini's sub-entries in this corpus are all
either 0- or 1-sense) loses that link entirely and silently -- no exception,
no DroppedItemRecord, no console warning; the entry is simply created with
an empty SensesRS. This is a genuine, previously-undiscovered violation of
Scenario 1's own contract for the recursive case, introduced in feature
025's own code (not inherited from 024).

Recommend: either (a) give _create_sub_entry a first_sense parameter
and link it as part of/immediately after the raw factory create (mirroring
_create_top_level_entry's contract), or (b) stop special-casing "sense #1
is already linked by Create()" at the _apply_one_entry level and instead
have _create_top_level_entry report back to the caller whether it actually
consumed first_sense, so remaining_senses can be computed correctly for
both branches. Add a regression test asserting a sub-entry with N linked
senses ends up with exactly N members in SensesRS after apply_reversals
(the current unit suite apparently didn't catch this, or exercises only
0-or top-level-sense sub-entry fixtures).

## 7. Two additional findings (informational -- NOT feature 025's scope,
## discovered live, NOT fixed here)

Finding 2 -- categories.py::_run_post_pass_a (STEMS tail block) calls a
non-existent flexicon API and its failure is invisible to the never-silent
channel. The traceback:
```
File "...categories.py", line 4750, in _run_post_pass_a
    target_entry = target.get_object_by_guid(src_entry_guid)
AttributeError: 'FLExProject' object has no attribute 'get_object_by_guid'
```
This is the tail block documented (categories.py, "cycle-16 lead
adjudication") as wiring LexEntryRef.ComponentLexemesRS/PrimaryLexemesRS
onto an EntryRef that "already exists" -- and ruled unreachable this cycle
because no LexEntryRef is ever created by the current transfer. This run
proves that ruling is not quite right: the tail block DOES get invoked and
DOES crash (on a nonexistent API, not on the "no EntryRef exists" no-op path
the ruling assumed), aborting whatever internal loop _run_post_pass_a runs
after its first entry. The exception is caught by transfer.execute's
per-action try/except (so it does not crash the whole Move) and logged via
report_sink.Warning -- but it is NOT converted into a DroppedItemRecord, so
it is invisible in report.dropped_items and would be silent to any caller
that doesn't capture console/log output. Recommend routing to the
programmer: fix or remove the dead get_object_by_guid call, and/or emit a
DroppedItemRecord from this catch site so the never-silent guarantee
actually covers it.

Finding 3 (informational) -- the Finding-1 fix from cycle11 (b8d325d) is
working as designed and now surfaces real MorphTypeRA/CmTranslation
"shared-default diverged" divergences and LexExampleSentence.TranslationsOC
copy failures that were previously silently swallowed. plan.dropped_items
grew from cycle9's 6 to this run's 265 (Preview) / 337 (post-Move report) --
almost all of the new records are owner_kind='MoForm' field='MorphTypeRA'
reason='shared-default diverged' and owner_kind='CmTranslation'
field='TypeRA' reason='shared-default diverged', i.e. real reference-field
divergences that Finding 1's fix (references._multistring_dict /
categories.py's catch-all) now correctly reports instead of swallowing. A
further ~72 are owner_kind='LexExampleSentence' field='TranslationsOC'
reason="child content not copied: 'FLExProject' object has no attribute
'Translations'" -- another flexicon-API-surface gap (this one IS correctly
surfaced as a DroppedItemRecord, unlike Finding 2). None of this is a
regression from this run; it is the never-silent channel doing its job
correctly on pre-existing 024-era gaps that Finding 1's fix stopped hiding.
Not blocking, but a real fidelity backlog item for
LexExampleSentence.TranslationsOC and the MorphTypeRA/CmTranslation.TypeRA
shared-default divergence paths.

## 8. Scenario 1 write-half verdict

PARTIAL FAIL.

| Aspect | Verdict | Evidence |
|---|---|---|
| Top-level entry count (134/134) | PASS | pre=0, post=134, matches plan exactly |
| Reversal index reuse (same GUID) | PASS | ab4d4345-... unchanged pre/post |
| Top-level ReversalForm text | PASS | sampled forms match plan's entry names |
| Top-level single-sense linking | PASS | sample: all show senses=1 |
| Top-level multi-sense linking (2 senses) | PASS | foot/leg/palm frond all senses=2 |
| Sub-entry recursion structure/count | PASS | all 7 known parents: exact sub-count match |
| Sub-entry sense linking | FAIL | 9/10 sampled sub-entries show senses=0 where 1 was planned (root-caused to Lib/reversals.py, Finding 1 above) |
| GUID preservation | PASS (as documented) | all new GUIDs -- matches the documented "does not preserve source GUID" hedge |
| LangProject.PartsOfSpeechOA untouched | PASS | 13/13 identical GUIDs pre and post |
| Config-view en.fwdictconfig SKIP (no write) | PASS | identical size+mtime pre/post |
| No crash / partial write / stuck lock (2nd attempt) | PASS | exit 0, clean CloseProject(), clean fresh re-open |

## 9. Recommendation

1. Restore Target before any further live testing (per the user's stated
   -restore-ready plan) -- this run's data is now in a partially-broken state
   (sub-entries with dropped senses) and should not be treated as a
   reference transfer.
2. Route Finding 1 (sub-entry sense-linking bug in Lib/reversals.py)
   back to the programmer as a blocking fix before feature 025 is
   considered release-ready -- this is a genuine, silent data-loss bug in
   the feature's own core write path, not a pre-existing 024 issue.
3. File Finding 2 (_run_post_pass_a's nonexistent get_object_by_guid
   call, and its invisibility to the never-silent channel) and Finding 3
   (the newly-surfaced MorphTypeRA/CmTranslation.TypeRA/
   LexExampleSentence.TranslationsOC gaps) as non-blocking backlog items --
   both are 024-era, out of 025's scope, and Finding 3 is arguably the
   never-silent channel working correctly, not a new defect.
4. Once Finding 1 is fixed, re-run this same Phase-2 driver (or an
   equivalent) against a freshly-restored Target to confirm sub-entry sense
   counts match the plan before signing off on Scenario 1's write half.

## Deliverables

- Phase 2 driver (the write is wired and DID run; includes the UTF-8 console
  fix and the PID-aware stale-lock precheck added after the first crashed
  attempt):
  C:\Users\thoua\AppData\Local\Temp\claude\d--Github--Projects--LEX-GramTrans\df5ecbb4-b4b3-4474-9c5e-34eda26728e4\scratchpad\t037_move_driver.py
- Full raw run log (successful 2nd attempt -- includes the pre-write Preview
  dump in full, the write, and the post-write persistence re-check):
  C:\Users\thoua\AppData\Local\Temp\claude\d--Github--Projects--LEX-GramTrans\df5ecbb4-b4b3-4474-9c5e-34eda26728e4\scratchpad\t037_move.log
- Supplementary read-only spot-check script (top-level multi-sense entries +
  parent-entry-own-sense-count confirmation):
  C:\Users\thoua\AppData\Local\Temp\claude\d--Github--Projects--LEX-GramTrans\df5ecbb4-b4b3-4474-9c5e-34eda26728e4\scratchpad\t037_post_spotcheck.py

---
**Verified By:** Verification Agent
**Date:** 2026-07-13
