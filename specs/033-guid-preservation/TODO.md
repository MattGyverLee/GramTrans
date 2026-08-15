# 033 — GUID preservation across transfer: TODO / handoff

**Invariant** (user-stated, 2026-08-14): *every transferred object keeps its source
GUID unless that GUID already exists in the target; a target object carrying the
source GUID is the same object, so link/dedup instead of minting a new one.* Any
GUID loss must be **justified and logged**, never silent.

**Branch**: `033-fix-affix-msa-guid-inflfeats`
**Worktree**: `D:\Github\_Projects\_LEX\GramTrans-033-affix-msa`
**Measuring tool**: `scratchpad/audit_guid_preservation.py` (committed) — restores a
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

## IN FLIGHT — code written, **NOT yet re-verified live**

The texts/wordforms wiring is committed but its live numbers are **stale**: the only
completed audit ran while the wordform bug below was active, which suppressed
analysis/gloss/bundle creation and made the numbers look better than they were.

- [ ] **RE-RUN THE AUDIT.** This is the blocking next step.
      ```powershell
      cd D:\Github\_Projects\_LEX\GramTrans-033-affix-msa
      $env:PYTHONPATH="D:\Github\_Projects\_LEX\flexicon"
      $env:GT_BACKUP="D:\Github\_Projects\_LEX\GramTrans\backups\Target 2026-07-06 0218.fwbackup"
      python scratchpad/audit_guid_preservation.py
      ```
      **Blocked 2026-08-14**: `Target.fwdata.lock` was 0.5 min old (4 FieldWorks
      processes running). Do NOT delete the lock or run against a held project —
      the audit restores Target as its first destructive step. Close FLEx first.

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

- [ ] **`Segment` GUIDs (101 minted).** Hypothesis, UNCONFIRMED: setting paragraph
      `Contents` makes LCM auto-segment, so `seg_ops.AppendSentence` is never
      reached (the code only calls it when `tgt_seg is None`) and the `guid=`
      never applies. LCM GUIDs are immutable post-create, so if confirmed this
      may be unfixable through this path. Either find a create-segments-first
      path, or document it as a **justified** loss with a logged reason.
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
- [ ] **Sweep the remaining bare `.Create()` sites** not covered by the audit
      because the fixture has no such data:
      `pictures.py:415,434,443` (CmFolder/CmPicture/CmFile), `reversals.py:714`,
      `texts.py` TextTag (`_raw_create_text_tag`), `transfer.py:1548` (allomorph).
      Each should route through `owned._create_owned_via_factory`.
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
