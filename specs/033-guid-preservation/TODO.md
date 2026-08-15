# 033 — GUID preservation across transfer: TODO / handoff

**Invariant** (user-stated, 2026-08-14): *every transferred object keeps its source
GUID unless that GUID already exists in the target; a target object carrying the
source GUID is the same object, so link/dedup instead of minting a new one.* Any
GUID loss must be **justified and logged**, never silent.

**Branch**: `033-fix-affix-msa-guid-inflfeats`
**Worktree**: `D:\Github\_Projects\_LEX\GramTrans-033-affix-msa`
**Measuring tool**: `debug/audit_guid_preservation.py` (committed) — restores a
clean Target, full Move, then per-class `preserved` vs `minted` over
`ICmObjectRepository.AllInstances()`. `minted > 0` = invariant violated.

---

## DONE — verified live

- [x] **Affix MSA GUIDs preserved** (all 4 subclasses). Was 88/88 regenerated.
      `_create_msa_with_guid` uses the LCM factory `Create(Guid)`; flexicon
      wrappers are a logged fallback. Corrected the false docstring claiming
      "GUID is not preservable for MSAs" (contradicted by `_create_owned_msa`
      in the same file).
- [x] **`InflFeatsOA` transferred to affixes.** Was 17 source (feature, value)
      pairs -> 0 in target, silently (no `dropped_items` entry). Now 17 -> 17.
      Producer `preview._populate_msa_infl_feat_bindings`, consumer
      `categories._wire_msa_infl_feats` in the 17.1 sub-pass.
- [x] **Affix allomorph GUIDs preserved** (106/106). Was a bare `factory.Create()`.
- [x] **One canonical helper** `owned._create_owned_via_factory`, logs every
      fallback to a minted identity.
- [x] **flexicon extended** — PR MattGyverLee/flexicon#239, MERGED as `791569a`.
      `BaseOperations._CreateWithGuid` + optional `guid=` on `Texts.Create`
      (+`contents_guid=`), `Paragraphs.Create`, `Segments.AppendSentence`,
      `Wordforms.Create`, `WfiAnalyses.Create`, `WfiGlosses.Create`,
      `WfiMorphBundles.Create`. Live-verified: all 8 classes honour the GUID.

Commit `d8576e0` covers the GramTrans half of the above.

---

## AUDIT RE-RUN — DONE 2026-08-15. One offender left: `Segment`.

Ran `debug/audit_guid_preservation.py` (Ejagham Mini -> restored Target,
`PYTHONPATH`-shadowed flexicon). Move: 188 actions / 188 added / 213 dropped.
**Offenders 2 -> 1; total minted 225 -> 101.** Result:
`scratchpad/guid_audit.json` (prior run kept as `guid_audit_PREV.json`).

| class | new (prev -> now) | minted (prev -> now) | verdict |
|---|---|---|---|
| WfiWordform | 124 -> 124 | **124 -> 0** | FIXED |
| WfiAnalysis | 23 -> **143** | 0 -> 0 | genuine now |
| WfiGloss | 35 -> **231** | 0 -> 0 | genuine now |
| WfiMorphBundle | 46 -> **283** | 0 -> 0 | genuine now |
| StTxtPara / Text / StText | 119 / 9 / 9 | 0 | holds |
| MoAffixAllomorph | 106 | 0 | holds |
| **Segment** | 101 | **101** | **STILL MINTING** |

The stale-numbers trap is cleared: analyses/glosses/bundles now create at their
real counts (143/231/283, matching STATUS.md) **and** preserve every GUID, so
those `minted=0` rows are real rather than an artifact of suppressed creation.

### `Segment` — hypothesis CONFIRMED

`preserved=0` (not merely low) is the decisive evidence. flexicon #239 added
`guid=` to `Segments.AppendSentence` and live-verified it, so a single reached
call would have preserved at least one GUID. Zero preserved means the call
never fires: at `texts.py:1071-1075` the code reads
`tgt_segments = seg_ops.GetAll(new_para)` and only calls `AppendSentence(...,
guid=)` when `tgt_segments[idx] is None`. Setting the paragraph `Contents`
makes LCM auto-segment, so the slot is always already filled — by a
LCM-minted segment whose GUID is immutable post-create.

**Not yet decided** (see OPEN ITEMS): either build a create-segments-first path
(delete the auto-created segments, then `ISegmentFactory.Create(guid)` + own
under `SegmentsOS` with correct offsets), or accept it as a **justified,
logged** loss. Note the practical blast radius is bounded: text-level
idempotency is protected by a different mechanism — the `f4cfbee` guard that
skips a text already having paragraphs — not by segment GUID identity.

---

## IN FLIGHT — code written, **NOT yet re-verified live**

The texts/wordforms wiring is committed but its live numbers are **stale**: the only
completed audit ran while the wordform bug below was active, which suppressed
analysis/gloss/bundle creation and made the numbers look better than they were.

- [x] **RE-RUN THE AUDIT** — DONE 2026-08-15, see the section above. The
      texts/wordforms wiring is now live-verified: every class preserves its
      GUIDs, and `Segment` is the sole remaining offender.
      ```powershell
      cd D:\Github\_Projects\_LEX\GramTrans-033-affix-msa
      $env:PYTHONPATH="D:\Github\_Projects\_LEX\flexicon"
      $env:GT_BACKUP="D:\Github\_Projects\_LEX\GramTrans\backups\Target 2026-07-06 0218.fwbackup"
      python debug/audit_guid_preservation.py
      ```
      **Blocked 2026-08-14**: `Target.fwdata.lock` was 0.5 min old (4 FieldWorks
      processes running). Do NOT delete the lock or run against a held project —
      the audit restores Target as its first destructive step. Close FLEx first.

      **Status 2026-08-15**: 3 FieldWorks processes are still up, but they hold
      `Mbugwe LizzieHC practice`, `Claude-Swahili` and `Mayanau-Bena-Yungur Toy`
      — **none holds Target**. What remains is a STALE `Target.fwdata.lock`
      (~77 min old, no owning process). Still blocked on the **editable
      flexicon install** below: `import flexicon` resolves to site-packages,
      which lacks `_CreateWithGuid`, so a run without `PYTHONPATH` shadowing
      gets the old flexicon and every `guid=` kwarg raises `TypeError` —
      swallowed into a generic "create failed" drop.

      Confirm per class: `WfiWordform`, `WfiAnalysis`, `WfiGloss`,
      `WfiMorphBundle`, `Text`, `StText`, `StTxtPara`, `Segment`.
      Compare the **`new` column** against a prior run, not just `minted` — a
      class can show `minted=0` simply because it created almost nothing (that is
      exactly how the bug below hid).

### Last measured (STALE — bug active)

| class | minted | note |
|---|---|---|
| Text / StText / StTxtPara | 0 | preserved 9/9, 9/9, 119/119 |
| MoAffixAllomorph | 0 | preserved 106/106 |
| WfiAnalysis / WfiGloss / WfiMorphBundle | 0 | **but `new` was 23/35/46 vs 143/231/283 — suppressed by the bug** |
| WfiWordform | 124 | the bug |
| Segment | 101 | see below |

Offenders 8 -> 2, minted 1019 -> 225. Re-measure before trusting any of it.

---

## OPEN ITEMS

- [ ] **`Segment` GUIDs (101 minted).** Hypothesis **CONFIRMED 2026-08-15** —
      see the audit section above for the `preserved=0` reasoning. LCM
      auto-segments on `Contents` set, so `AppendSentence(..., guid=)` at
      `texts.py:1075` is never reached and LCM GUIDs are immutable
      post-create. **Decision still open**: build a create-segments-first path
      (delete the auto-created segments, then `ISegmentFactory.Create(guid)` +
      own under `SegmentsOS` at the correct offsets) — untried and it fights
      LCM's own segmentation, so it needs a live spike before committing —
      **or** accept it as a justified loss and emit the logged reason the
      invariant requires (currently the loss is silent, which is the part
      that is out of contract regardless of which way this goes).
- [ ] **`MoStemAllomorph` untested.** Audit shows `new=0 / missing=187` because
      STEMS is excluded from `build_full_selection()`. It routes through the same
      `_mk` helper that was fixed, so it *should* inherit the fix — unproven.
      Re-run with STEMS enabled to confirm.
- [ ] **Retire the structural-dedup workaround** at `wordforms.py` (the
      `_plan_analysis_fingerprint` / `_analysis_fp_index` path). It exists only
      because analysis GUIDs were being regenerated. GUID-first dedup now runs
      ahead of it. KEEP it for now as a legacy fallback: targets populated by
      earlier runs carry minted GUIDs and have no source identity to match on.
      Remove once no supported target predates GUID preservation.
- [x] **Sweep the remaining bare `.Create()` sites** — DONE, commit `8804a2a`
      (offline only; the live audit fixture still carries none of this data, so
      these legs remain **live-unproven**). Routed through
      `owned._create_owned_via_factory`: `pictures._create_picture_raw`
      (CmPicture **and** its backing CmFile, threaded from
      `_reproduce_one_picture` at all three raw call sites),
      `reversals._create_sub_entry`, `texts._raw_create_text_tag`,
      `transfer._create_allomorph_with_guid` (whose docstring falsely claimed
      allomorph factories take no Guid — the audit had already preserved
      106/106 through that same overload).
      New `SegmentPlan.tag_source_guids`, a **distinct** field parallel to
      `tag_decisions`: a tag decision identifies the referenced `TagRA`
      *possibility*, not the owning `ITextTag`, so reusing it would repeat the
      wordform/analysis GUID confusion below. 6 RED-first tests in
      `tests/unit/test_033_bare_create_guid_sweep.py`; suite 27 failed / 1989
      passed with the 27 IDs byte-identical to baseline (zero regressions).
      **Pattern audit:** `categories.py:6736`/`6766` and `texts.py:984` already
      preserve GUIDs (they hand-roll the same try-then-log-fallback logic —
      a consolidation opportunity, not a defect, and not mechanical because of
      their duck-path branches). `pictures.py:417` (the "Local Pictures"
      `CmFolder`) is EXEMPT and now commented as such: a target-side container
      with no source counterpart.
- [ ] **`_safe`/`except Exception` masks API mismatches.** A wrong kwarg against
      live flexicon surfaces as a generic "create failed" drop, not a loud error.
      This made the fake-signature break present as `IndexError: list index out of
      range`. Consider letting `TypeError` propagate.

---

## ENVIRONMENT — must fix before any of this works outside tests

- [ ] **flexicon install is NOT editable.** `pyflexicon 4.3.0` is a plain copy in
      `D:\Apps\anaconda3\Lib\site-packages\flexicon`, which does **not** have
      `_CreateWithGuid`. Every test so far used `PYTHONPATH` shadowing. Until
      this is fixed, a normal GramTrans run gets the old flexicon and the `guid=`
      kwargs raise `TypeError` — swallowed into generic drops (see above).
      ```powershell
      pip uninstall -y pyflexicon
      pip install -e D:/Github/_Projects/_LEX/flexicon
      python -c "import flexicon; print(flexicon.__file__)"   # must NOT be site-packages
      ```
- [ ] **`CLAUDE.md` is stale**: says install from `D:/Github/_Projects/_LEX/flexlibs2`
      and that the directory "MUST NOT be renamed to flexicon" — it *has* been
      renamed, so the documented command fails. Fix the path and drop the note.
- [ ] **`pyproject.toml`** pins `pyflexicon>=4.1.1`; needs a floor bump once a
      release carries `guid=`.

---

## LESSON — how the worst bug got in

`AnalysisPlan.source_guid` is the **analysis** GUID; the plan carried no wordform
GUID. Passing it to `wf_ops.Create(...)` stamped the analysis's identity onto the
wordform. The new GUID-first dedup then looked up the analysis GUID, found the
wordform wearing it, and skipped the analysis — **silently**. Live: 23 analyses
instead of 143, 35 glosses instead of 231, 46 bundles instead of 283.

Two guards now, either sufficient alone:
1. `AnalysisPlan.wordform_guid` — a distinct field; absent value **mints** rather
   than falling back to `source_guid` (the fallback was the bug).
2. `_resolve_by_guid(..., expect_class=)` — GUIDs are project-unique, so a
   type-blind lookup returns the wrong object whenever any path mis-assigns
   identity.

Covered by `tests/unit/test_033_wordform_guid_confusion.py` (5 tests).

**Takeaway for the next agent**: when a fix makes a "minted" count drop to zero,
check that the object is still being *created* at all. `minted=0` and
`created≈0` look identical in the offender list.
