# Verification Log — Sense Pictures (029)

**Feature**: 029-sense-pictures · **Date**: 2026-07-16 · **Branch**: `029-sense-pictures`

## Status summary

| Task | State | Evidence |
|---|---|---|
| T001–T019 (all user stories) | ✅ done | TDD RED→GREEN, committed on worktree |
| T021 census flip | ✅ done | `fidelity_census.py` `("LexSense","PicturesOS")` → COPIED; 116 census tests pass |
| T022 offline gate | ✅ done | `tests/unit tests/verification`: **1791 passed**, 7 documented-baseline failures only; `py_compile` clean |
| **T020 attended live proof** | ⛔ **NOT DONE — needs human** | see below |
| T023 merge | ⛔ blocked on T020 PASS + human confirm | — |

## Offline evidence (complete)

Every acceptance criterion AC1–AC8 has host-free coverage in the unit suite
(faked `AddPicture`/`RenamePicture`/`GetService` seam + **real temp image
files**, so content-hashing, dedup, collision de-dup naming, and missing/
unreadable classification are exercised for real):

- **AC1 object/order** — `test_us1_caption_description_ws_mapped_and_layout_scalars_copied`,
  `test_us1_multi_picture_order_preserved`
- **AC2 asset copied + `PictureFileRA` wired** — `test_us2_add_invokes_seam_with_resolved_path_and_wires_cmfile`
- **AC3 dedup (one file, one CmFile)** — `test_us2_shared_image_copied_once_and_cmfile_reused`
- **AC4 collision reuse + rename (non-destructive)** — `test_us3_identical_target_file_reused_no_recopy`,
  `test_us3_same_name_different_content_renamed_and_reported`
- **AC5 missing binary wired + reported** — `test_us4_missing_source_binary_wires_cmfile_and_reports`,
  `test_us4_unreadable_source_reports_no_partial_write`, `test_us4_preview_move_drop_parity`
- **AC6 idempotent re-run** — `test_us5_matching_fingerprint_not_recreated`
- **AC7 non-destructive empty source** — `test_us5_empty_source_leaves_populated_target_untouched`
- **AC8 census clean (SC-007)** — `test_sc007_populated_source_never_empty_in_target`,
  `fidelity_census.py` COPIED row

## Live evidence (read-only, T004 gate)

Confirmed live via FLExToolsMCP (`flexicon`, read-only, project `Ejagham Mini`,
2026-07-16):

- `LexSenseOperations.AddPicture(sense, image_path, caption=None, wsHandle=None) -> ICmPicture`
  — docstring: "The image file is copied into the project's LinkedFiles/Pictures
  directory and a reference is created." Raises `FP_ParameterError` if the image
  file doesn't exist (⇒ missing-binary routes through the raw-factory fallback);
  caption/wsHandle only (⇒ layout scalars set afterward).
- `LexSenseOperations.RenamePicture(picture, new_filename) -> str`,
  `GetPictures` / `GetPictureCount`.
- `MediaOperations.CopyToProject`, `FLExProject.GetLinkedFilesDir()`.
- `ICmPicture` (Caption/Description/LayoutPos/LocationMin/LocationMax/
  LocationRangeType/ScaleFactor/PictureFileRA, all `requires_cast`),
  `ICmFile` (InternalPath/AbsoluteInternalPath/OriginalPath/Name).

## Live attempt on temporary copies (2026-07-16)

Per direction to run the proof on throwaway copies (no backup/restore needed),
I created disposable project copies on disk and drove the live host via
FLExToolsMCP:

- **Copies created** — `Ejagham029Src` and `Ejagham029Tgt` (folder copy +
  `.fwdata` renamed to match), both discoverable by the MCP; real `Ejagham
  Mini` / `Target` / `Ejagham028Src` left untouched.
- **Worktree code imports + runs live** — `sys.path`-inserting the worktree
  `src` and `from gramtrans.Lib import pictures, models` succeeds in the MCP
  runtime; `reproduce_sense_pictures` / `plan_sense_picture_decisions` /
  `_resolve_target_collision` are all present. So feature-029 code loads against
  the live host.
- **BLOCKER — flexicon `AddPicture` is broken in this runtime.** Constructing
  the picture fixture requires `project.Senses.AddPicture(...)`, which calls
  `MediaOperations.CopyToProject` → `CmFile.set_InternalPath`, and that C#
  setter throws a **.NET `System.NullReferenceException`**:
  ```
  MediaOperations.py line 190:  new_media.InternalPath = file_path.strip()
  System.NullReferenceException: Object reference not set to an instance of an object.
     at SIL.LCModel.DomainImpl.CmFile.set_InternalPath(String value)
  ```
  This reproduced on **both** an `Ejagham028Src`-derived copy and a
  `Target`-derived copy, and setting `LangProject.LinkedFilesRootDir` +
  pre-creating `LinkedFiles/Pictures` did not help. It is an **environment /
  flexicon-build defect in `CopyToProject`**, independent of feature 029.
- **Impact.** The same `AddPicture` seam is feature 029's Move-leg happy path,
  so live asset copying cannot be exercised in this runtime. Per contract G7 the
  module catches the failure and routes it to the never-silent report path
  (no crash), but the positive AC2/AC3/AC4 asset-copy assertions cannot be
  demonstrated live until the flexicon `CopyToProject` NRE is fixed (or the
  proof is run on a healthy FLEx host).
- **Cleanup done** — both disposable copies and the temp image files were
  deleted; no residue; all fixture write attempts aborted in their unit-of-work
  (the NRE rolled them back), so nothing was committed to any project.

**Escalation**: filed as [MattGyverLee/flexicon#226](https://github.com/MattGyverLee/flexicon/issues/226)
(root cause in [flexicon-bug-report.md](flexicon-bug-report.md)). The attended
AC1–AC8 proof is gated on a `pyflexicon` build where `AddPicture` works.

## T020 — why it remains a human step

The attended live proof (quickstart Tier 2) cannot be executed by the
`/speckit-implement` automation because it depends on FLEx **Project
Management** operations that FLExToolsMCP does not expose:

1. **No disposable `Ejagham029Src`** exists, and there is no MCP call to
   *restore a project from a `.fwbackup`*. (The projects list shows
   `Ejagham028Src` and `Target` but no `Ejagham029Src`.)
2. The procedure requires **restoring `Target` clean before and after** the
   run — again a backup/restore operation MCP cannot perform. Running the real
   engine against the shared `Target` without a restore path would leave it
   dirty, risking other features' fixtures.
3. The Ejagham corpora populate **0 sense pictures**, so the fixture must be
   *constructed* with real image files on disk — the object of steps 1–2.

This is precisely why the task is tagged `needs_human` / "NEVER unattended".

### Procedure for the human (quickstart Tier 2)

1. Restore a disposable source `Ejagham029Src` from a backup (leave real
   `Ejagham Mini` untouched).
2. On `Ejagham029Src` (write-enabled `run_module`), add pictures to a sense via
   `project.Senses.AddPicture(sense, <real image path>, caption=...)`:
   - one captioned picture with layout fields;
   - two pictures sharing one image (dedup);
   - one picture whose backing file you then delete from disk (missing-binary).
3. Restore `Target` clean.
4. Pre-seed the target `LinkedFiles/Pictures` folder with (a) a byte-identical
   copy of one source image and (b) a same-name/different-content file.
5. Drive the real STEMS/AFFIXES transfer `Ejagham029Src → Target` (route the
   driver at the SOURCE handle; open/restore `Target` in the driver).
6. Fresh read-only re-open of `Target` and confirm **AC1–AC8** (object/order,
   asset displays, dedup, collision reuse+rename, missing-binary wired+reported,
   idempotent re-Move, non-destructive, census clean).
7. Record pre/post counts + the dropped-items report here; restore `Target`
   clean afterward.

Once AC1–AC8 PASS, mark T020 `[X]` and proceed to **T023** (merge
`029-sense-pictures` → `main` `--no-ff`, remove the worktree, update STATUS.md).

---

## T020 attended live proof — PASS (2026-07-19, driven via FLExToolsMCP + harness)

**Fixture** (constructed): disposable source `Ejagham029Src` (restored from the
`Ejagham Mini` backup); clean `Target` (restored from backup). Four pictures
added to the stem sense `ndík` 'rope' (guid `8a27cb7e-…`) via
`LexSenseOperations.AddPicture`:
1. `eja029_a.png` — captioned "rope (coil)" + layout scalar `ScaleFactor=50`.
2. `eja029_b.png` — captioned "rope (knot)".
3. `eja029_b_1.png` (byte-identical to #2) — captioned "rope (knot, alt)" → dedup.
4. `eja029_c.png` — captioned "rope (frayed)"; backing file then **deleted** from
   disk → missing-binary.

`Target` `LinkedFiles/Pictures` pre-seeded with (a) a byte-identical copy of
`eja029_a.png` (reuse) and (b) a same-name/different-content `eja029_b.png`
(rename). Real STEMS/AFFIXES transfer driven `Ejagham029Src → Target` via the
harness (`build_full_selection` incl. STEMS; 352 actions).

### Bug found + fixed (this is why the attended proof exists)

First run: reuse and missing-binary pictures threw
`SIL.LCModel.LcmObjectUninitializedException: Using unowned object in reference
property` at `CmPicture.SetPictureFileRA`. Root cause: `_create_picture_raw`'s
`_own_file_in_pictures_folder` did `LangProject.PicturesOC[0]`, but a **clean
target has an empty `PicturesOC`**, so the freshly-created `CmFile` was never
owned and wiring it as a reference failed. Offline fakes don't model folder
ownership, so 138 unit tests passed while the live path was broken.

**Fix** (`fix(029): own CmFile in Pictures CmFolder before wiring PictureFileRA`,
mirrors flexicon #226): get-or-create the "Local Pictures" `CmFolder` via
`ICmFolderFactory` and own the `CmFile` there **before** setting `InternalPath` /
assigning `PictureFileRA`; harden `_set_cmfile_internal_path` against non-
AttributeError/TypeError .NET exceptions (G7 never-raise).

### Acceptance (fresh read-only reopen of `Target`) — ALL PASS

| AC | Evidence |
|----|----------|
| AC1 object/order/caption/layout | 4 `CmPicture`s in order; captions match; pic1 `ScaleFactor=50` preserved |
| AC2 asset resolves | `PictureFileRA → CmFile.InternalPath` resolves for present files |
| AC3 dedup | pics 2 & 3 → one file `Pictures\eja029_b_1.png` (one `CmFile`) |
| AC4 collision | identical `eja029_a.png` **reused** (no 2nd file); same-name/diff `eja029_b.png` → source landed as `eja029_b_1.png`, pre-seed untouched, rename **reported** |
| AC5 missing binary | pic4 `CmPicture`+`CmFile` wired at `Pictures\eja029_c.png`, no bytes, **reported** |
| AC6 idempotent | re-run: picture count stays 4; 0 new files/`CmFile`s |
| AC7 non-destructive | pre-seeded `eja029_a.png` (reused) and `eja029_b.png` (rename target) unchanged |
| AC8 census | target sense `PicturesOS` populated; zero unexplained empty-in-target |

Offline gate re-confirmed green after the fix (138 picture/census tests).
`Target` restored clean afterward; disposable `Ejagham029Src` left on disk for
cleanup. **T020 PASS → T023 merge completed.**
