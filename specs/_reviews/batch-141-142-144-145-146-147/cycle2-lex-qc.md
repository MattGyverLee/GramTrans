# Cycle 2 QC: #146 (A) and render (B)

> Saved by the main session verbatim from the lex-qc hand-back (that agent had no Write/Bash tool; static read of worktree
> HEAD files; test counts are the programmer's claims, not re-run).

**A, fix-146-preview-cache-picture-dedup: 91/100. APPROVE; no P0 or P1.**
**B, fix-146-planned-link-render: 88/100. APPROVE with P2 follow-ups; no P0 or P1.**

## Checks

1. **Wordforms P1 is closed.**
   - `resolve_or_report_category` leaves no PlannedCreate behind (`wordforms.py:520-540`): it records which chain GUIDs
     were absent before the call; a `finally` deletes only PlannedCreates for those GUIDs that appeared during the call; a
     foreign pre-existing entry is untouched; a hit on an existing target POS is not a PlannedCreate, so it is kept.
   - N analyses give N drop records. The downgrade at `wordforms.py:543-546` covers CREATE, `planned`, and LINK with
     `target_item` None. The cache never keeps a planned POS and Move's cache is unmarked, so each analysis re-decides to
     CREATE and drops (matches the programmer's test name and RED evidence; not re-run).
   - No cache copy; only `_ancestor_chain` GUIDs are touched.
   - P2 `wordforms.py:531-532`: if the chain walk raises, `absent_before` becomes `[]` and planned entries leak unnoticed.
     Log at warning, or treat the chain as just the leaf.

2. **POS-cache-key answer: correct in substance, one gap.**
   - No `REFERENCE_FIELD_MAP` spec targets `LangProject.PartsOfSpeechOA` (`target_list_path` rows at references.py:76-284
     use LexDb and other lists; stem-name row returns None, references.py:250). Only `wordforms.py:221` points at that list.
     Reversals use the index's own list (`reversals.py:106,931`).
   - P2: the answer omits `resolve_thesaurus_item` (`references.py:1749`), which calls `decide_reference` with a dynamic
     mirrored list. It cannot hit POS today (thesaurus lists only); say so explicitly.
   - The cache has no per-list scoping, so a collision is possible in principle; the wordforms cleanup removes the hazard.

3. **Move-side guards are loud and never abort a Move.**
   - `apply_reference` LINK arm (`references.py:1030-1044`): warns, returns None, no raise.
   - `_apply_category` (`wordforms.py:1082-1099`): warns, appends a DroppedItemRecord, returns.
   - Effectively unreachable (plan-time already downgrades to a drop); cheap and correct.

4. **Texts rebind failure now produces a drop record.**
   - `_rebind_or_drop` (`texts.py:923-947`) catches an exception or None result, warns, appends a DroppedItemRecord, returns
     None; callers `continue` (`texts.py:957`, `:1011`). Move data outcome unchanged; only record + warning are new.
   - P2 `texts.py:956`: the genre drop uses `owner_kind="StText"` with the Text's source GUID (mislabelled).
   - A plan-time REPORT_DROPPED decision passes through the rebind unchanged (correct).

5. **`planned` set only on PlannedCreate-derived LINKs.**
   - Set at `references.py:807` via `is_planned_create(cached)`; carried in `categories.py:6568`.
   - Other `.target_item` readers: `references.py:1031,1051,1057`, `texts.py:1018` (after rebind), `wordforms.py:546,1078`
     -- all handled.
   - P2 `owned.py:943-950`: `_plan_child_ref_decisions` builds a ReferenceDecisionRecord without `planned`. No renderer
     consumes those fields today (filtered on `_SENSE_LIST_REF_FIELDS`), but it would mislabel a planned LINK if that
     changes. Carry `planned`, or route through `_reference_decision_record`.
   - `categories.py:9002` (`spec is None` row) is not a planned case.

6. **Renderer correctness (`preview.py:2078-2281`).**
   - N excludes planned items (collapse splits per field on `rows[k]["planned"]`); K == 0 omits the line
     (`preview.py:2169`); strings only in module constants (`preview.py:2081-2090`); stale "Later references" note and
     "Created once" text gone from src; #144 note fires only when a Create row and a planned Link row share a GUID.
   - P2 `preview.py:2272-2280`: the `+N more` cap can hide the Create row while the note still shows (edge case).
   - P2: tests still hardcode literals in `test_issue147_sense_list_row_cap.py:127-149`,
     `test_issue144_preview_pos_text_decisions.py:206,217`, live `test_issue147_sense_list_row_cap_live.py:204`. Only
     `test_integ_141_147_planned_link_render.py` and the new #144 tests import the constants. Convert the former.
   - Judgment calls 1-4 acceptable, particularly omitting the "0 items" line and the planned suffix on #144 rows.

7. **No Move behaviour change beyond added drop records and warnings.**
   - Move cache never marked, so `decide_reference` on Move is unchanged; new `planned` fields defaulted
     (`models.py:4195,4243`); texts guard and wordforms change on Move are reporting only.
   - Live evidence: programmer reports `FLEXLIBS_REQUIRE_LIVE=1`, 9 passed, 2 strict xfailed (#161). No
     `evidence/live-*.md` artifact with pre/post field values seen -- Gate 2 question for lex-verification, not a code
     defect. #146 touches the write path, so confirm the artifact exists before merge.

## Other P2s
- A: the strict xfail on the genre tests is unconditional (`test_issue146_preview_cache_picture_dedup_live.py`), so it will
  XPASS-fail once #161 lands. Add a tracking note on #161.
- B: the merge (f045f01) is clean and render commit 24f85b2 only touches preview and tests; no cross-branch risk.
