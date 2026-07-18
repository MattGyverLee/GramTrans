# Live proof — S2 (per-index category resolve) + S3 (WS gate) reversal fixtures

**Date:** 2026-07-18 | **Author:** attended session (main + FLExToolsMCP)
**Projects:** SOURCE `Ejagham025Src` (disposable copy of read-only `Ejagham Mini`),
TARGET `Target` (disposable; restored clean after the run).
**Status:** S3 live-PASS (Preview + Move). **S2 live-PASS at Preview, FAIL at Move —
real bug found (see Finding 1).** R5 held.

Closes the "not exercisable" gap for S2/S3 in
[../HANDOFF.md](../HANDOFF.md) "Scenario coverage status": Ejagham Mini had **0**
reversal entries with `PartOfSpeechRA`, **0** reversal categories, and its lone
non-`en` index (`fr`) had **0** entries (so it never reached the WS gate). We
planted the two missing data shapes on a disposable copy and ran the real
Preview/Move engine against them.

## Fixtures planted (scratchpad/build025_fixture.py)

On `Ejagham025Src` (`en` + `fr` reversal indexes; WS set = en, etu):

- **S2** — a 2-level custom category chain in the **`en` index's own**
  `PartsOfSpeechOA`: `Rev025 Parent` (`211cfd23-…`) → `Rev025 Child`
  (`e2039765-…`); existing `en` entry **"person"** (`03c39dc0-…`, senses=1)
  `PartOfSpeechRA` → the child. Target's `en` index has 0 categories, so a
  correct Move must **CREATE** the parent+child chain (hierarchical, GUID-
  preserving) into the **target index's** `PartsOfSpeechOA` — never
  `LangProject.PartsOfSpeechOA` (R5).
- **S3** — one entry added to the **`fr` index** linking a copied sense
  (`person`'s sense0). This pulls `fr` into closure scope so it reaches the WS
  gate. Target has no `fr` WS ⇒ expect exactly one `DroppedItemRecord`
  (owner_kind `ReversalIndex`, reason "writing system not mapped") + skip.

## Preview (scratchpad/run025_s2s3_live.py) — read-only, Target byte-unchanged

`compute_preview(Ejagham025Src → Target)` = `preview_ready`, 134 reversal decisions.

- **S2 PASS** — person decision: `target_ws=en`, `linked_senses=1`,
  `pos_action=create`. The custom child (absent from Target's `en` index)
  resolves to a hierarchical CREATE against the per-index list.
- **S3 PASS** — exactly one drop: `owner_kind=ReversalIndex owner_label=French
  field=WritingSystem item=fr reason='writing system not mapped'`.
  Reversal-owned dropped total = 1.

## Move (attended, destructive) — then Target restored clean

`execute_move`: `stems added=164` (reversal entries ride along), no errors.
Post-Move fresh read-only re-open of Target:

| Check | Result |
|---|---|
| S3 — `fr` index NOT created (skipped) | **PASS** — Target still has 1 index (`en`); `fr` absent |
| S1 (incidental) — reversal entries rode along | 134 `en` entries created |
| R5 — no `Rev025` category in `LangProject.PartsOfSpeechOA` | **PASS** — LP grew 4→18 from the *normal* grammar-category transfer; no `Rev025` name; the `Rev025` GUIDs appear **nowhere** in Target |
| S2 — parent+child CREATED in `en` index `PartsOfSpeechOA` | **FAIL** — list empty (top-level=0); `Rev025` GUIDs found nowhere |
| S2 — `person.PartOfSpeechRA` links the created child | **FAIL** — `PartOfSpeechRA=None`; **0 of 134** entries carry any `PartOfSpeechRA` |

## Finding 1 (P0, 025 US2 Move-apply) — reversal category CREATE never lands

**Root cause (confirmed live).** `Lib/references.py::apply_reference`'s CREATE arm
dispatches the item factory by the **target list's `ItemClsid`**:

```python
factory_by_item_clsid = {66: ..SemDom, 26: ..Anthro, 5042: ..MorphType,
                         5118: ..LexEntryType, 7: ..CmPossibility}
factory_iface = factory_by_item_clsid.get(item_clsid)   # -> None for 5049
if factory_iface is None:
    raise UnmappedItemClassError(...)                    # category reported-dropped
```

A reversal index's `PartsOfSpeechOA` has **`ItemClsid = 5049` (PartOfSpeech)**
(confirmed live on Target for both the reversal index list AND
`LangProject.PartsOfSpeechOA`). `5049` is **absent** from the map, so every
reversal-category CREATE raises `UnmappedItemClassError`;
`reversals.py::_apply_pos_decision` catches it and appends the dropped record —
so the loss is **reported, not silent** (never-silent holds) — but the category
is never created and the entry's `PartOfSpeechRA` is never linked.

Why it was never caught: the offline US2 tests (T021–T026) use fakes that don't
exercise the real `ItemClsid`→factory dispatch, and live S2 was "not exercisable"
in Ejagham Mini until these fixtures.

**Secondary problem for the fix.** `IPartOfSpeechFactory` exposes only
owner-taking overloads — `Create(Guid, ICmPossibilityList owner)` and
`Create(Guid, IPartOfSpeech owner)` — there is **no 1-arg `Create(Guid)`**. The
CREATE arm's generic pattern is `factory.Create(parsed_guid)` then
`_add_to_owner(new_obj, …PossibilitiesOS/…SubPossibilitiesOS, …)`. So simply
adding `5049: IPartOfSpeechFactory` is insufficient — the create-then-add idiom
fails for `IPartOfSpeech`. The fix must special-case the owner-taking overload
(root → `Create(guid, list)`, child → `Create(guid, parent_pos)`), exactly the
pattern `scratchpad/build025_fixture.py` uses.

**Proposed fix (needs worktree + TDD + QC per constitution):** teach the CREATE
arm to handle `5049` via `IPartOfSpeechFactory`'s owner-taking `Create`. Add a
live-shaped regression (not just a fake) that asserts the chain lands in the
**target reversal index's** `PartsOfSpeechOA` and never `LangProject`'s.

**Sweep-pattern audit (do before fixing):** `factory_by_item_clsid` is a closed
clsid→factory map. Any OTHER reference-field whose target list has an `ItemClsid`
not in `{66,26,5042,5118,7}` hits the same dead end. Enumerate every
`REFERENCE_FIELD_MAP` (024) + reversal `PartOfSpeechRA` (025) target list's real
`ItemClsid` and confirm each is either mapped or intentionally out of scope —
`5049` is the first confirmed miss; there may be siblings.

## Artifacts

- `scratchpad/build025_fixture.py` — fixture builder (MCP write module).
- `scratchpad/run025_s2s3_live.py` — read-only Preview + assertion driver.
- `Target.pre025bak` — filesystem backup used to restore Target clean post-Move.
- MCP write-caster note: the write-mode preflight crashes
  (`'str' object has no attribute 'get'`) when a cast-requiring property is
  chained into a mutating call; workaround = correct-cast-to-local +
  `getattr(obj, "set_String")(…)`. (Candidate MCP bug report.)

## Caveats / not-done

- The `UnmappedItemClassError` → dropped-record path is asserted from code, **not
  captured in this run's Move output** (the Move driver printed per-category
  counts only, not `dropped_items`). A confirming re-Move that surfaces the
  `"unmapped item class 5049 for CREATE"` record on `ReversalIndexEntry` would
  close that loop.
- **UI check still pending** — PyQt Preview-pane render of
  `render_reversal_decisions` / `render_config_view_records` (separate GUI run).
- S2's LINK+diverged and REPORT_DROPPED-absent-list arms remain fake-only
  (Target's `en` index has 0 categories, so only the CREATE arm was live-reachable).

---

## RESOLUTION (2026-07-18) — Finding 1 fixed + live-proven, merged @ `c490f90`

Finding 1 was fixed via a LEX crew cycle (worktree `025-fix-reversal-pos-create`):

- **Sweep audit** (`cycle1-domain.md`): 23/23 `REFERENCE_FIELD_MAP` rows safe; clsid
  5049 the only live miss, plus one latent 030 thesaurus dynamic-owner sibling the
  same patch covers.
- **Fix** (`752a60c`): `references.py` CREATE arm now dispatches clsid 5049 →
  `IPartOfSpeechFactory`'s **owner-taking** `Create` (root `Create(guid, list)`,
  child `Create(guid, parent)`), bypassing the create-then-add idiom. Chain lands in
  the target reversal index's own `PartsOfSpeechOA` (never `LangProject`'s / R5).
- **Gates**: offline suite 1719 passed / 22 pre-existing (no new); RED→GREEN with a
  revert tripwire (RED-on-revert confirmed); QC APPROVE 95/100 (`cycle2-qc.md`,
  `cycle2-verification.md`).
- **Attended live Move re-validation** (worktree build, provenance-guarded): the
  `Rev025 Parent → Rev025 Child` chain is now **CREATED by GUID** in the target
  `en`-index's own category list, `person` links the created child, **1/134** entries
  carry a category link (was **0/134**), R5 untouched, `fr` skipped. Target restored
  clean from `Target.pre025bak`.
- **Merged** `025-fix-reversal-pos-create` → `main` @ `c490f90`;
  `test_reference_create_paths.py` 7 passed on main post-merge.

**S2 is now live-proven end-to-end.** Remaining 025 backlog: the PyQt Preview-pane UI
render check (deferred).
