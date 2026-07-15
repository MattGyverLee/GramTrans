# Research: Fix Inflection-Feature Linking to Grammatical Categories

**Feature**: 031-fix-inflection-feature-linking | **Date**: 2026-07-13

This document resolves the open technical questions behind the two defects. Each
finding below is grounded in the current code; hypotheses marked **(confirm live)** are
verified by the read-only diagnosis (US3) before the corresponding fix is written.

---

## R1 — How to write the feature → category link (Defect 1)

**Decision**: Add the link as a **wiring post-pass** that runs during Move after all
features and Parts of Speech exist, modeled on `_run_post_pass_a` (categories.py:4725)
invoked via `_run_tail_once` (categories.py:4789). Plan-time gathers the source
`POS.InflectableFeatsRC` membership into a plan binding
(`{target_pos_guid: [feature_guid, ...]}`) and emits one preview-visible row per link;
Move-time resolves both endpoints by GUID and calls `InflectableFeatsRC.Add(feature)`
guarded by a membership check.

**Rationale**:
- The link is a many-to-one cross-reference whose two endpoints (feature, POS) are both
  created earlier in the same run. A post-pass is the established pattern in this
  codebase for "wire references after both objects are stable" (used for
  `ILexEntryRef.ComponentLexemesRS`). It cleanly solves **ordering** (features may plan
  after their POS or vice-versa) and **deferral** (FR-007: only wire when both endpoints
  exist; otherwise emit `Skip(DEPENDENCY_UNRESOLVED)`).
- It keeps the change additive to the leaf-dispatch architecture: no execute_action has
  to know about the other category's creation order.
- Idempotency (FR-002) falls out of the membership guard (`any(existing is feat or
  guid-equal)` before `.Add`), identical to `_run_post_pass_a`.

**Source of truth for membership**: the source project's own `POS.InflectableFeatsRC`
(selection.py already reads this at 1786-1804 for closure display). The plan mirrors it
rather than inventing associations (spec Assumption).

**Alternatives considered**:
- *Inline in `gram_categories_execute_action`*: populate `InflectableFeatsRC` right
  after creating each POS. Rejected — the referenced features may not have been created
  yet (leaf-dispatch order lists `GRAM_CATEGORIES` before `INFLECTION_FEATURES`), so it
  would need its own deferral anyway, duplicating the post-pass logic.
- *Inline in `inflection_features_execute_action`*: add the feature to every referencing
  POS as the feature is created. Rejected — a feature does not know which target POSes
  reference it without re-deriving the reverse map; the POS may not exist yet; and it
  splits the link logic across two engines.

**Preview surfacing**: the link binding is rendered as a distinct preview item
(proposed action **Link**, per Principle III's action vocabulary) so SC-004 (preview
count == committed count) is verifiable.

---

## R2 — Why features land nameless (Defect 2, primary root cause)

**Decision**: Route the feature and value `Name`/`Abbreviation`/`Description` copy
through writing-system mapping — either `project.InflectionFeature.ApplySyncableProperties(..., ws_map=ws_mapping)`
(mirroring the POS path at categories.py:468-469) or an explicit source-handle →
target-handle translation via the `WSMapping` already passed into
`inflection_features_execute_action`.

**Rationale / evidence**: `inflection_features_execute_action` (categories.py:595-604,
633-641) builds `all_ws = {ws_obj.Id: ws_obj.Handle for ws_obj in
source.WritingSystems.GetAll()}` and then calls
`tgt_prop.set_String(ws_handle, TsStringUtils.MakeString(text, ws_handle))` using the
**source** writing-system *handle* to write into the **target** object. LCM writing-
system handles are per-project integers; the source handle for a given WS Id is not
guaranteed to equal the target handle for the same WS Id. Writing with the wrong handle
lands the string on a target writing system the FLEx UI does not display for that field
(or one that does not exist), producing a feature/value that shows as a **bare GUID**.
The POS path avoids this by delegating to `ApplySyncableProperties(..., ws_map=...)`,
which is exactly why POSes transfer with correct names while features do not. This is
also a **Principle I** violation ("writing-system identity … MUST be … explicitly
mapped before any string-bearing field is written").

**(confirm live)**: the diagnosis reports, for a known transferred feature, which target
WS handle actually carries the name — confirming the handle mismatch before the fix.

**Alternatives considered**:
- *Keep hand-rolled copy but translate handles*: acceptable, but re-implements what
  `ApplySyncableProperties` already does correctly for POS. Preference is to reuse the
  Operations-class method (Principle II: Operations API is the canonical surface) unless
  the feature classes lack a suitable `GetSyncableProperties`/`ApplySyncableProperties`
  surface — confirmed in Phase 0.

---

## R3 — Why the target accumulates DUPLICATE features on re-run (Defect 2, dedup)

**Decision**: (a) Reconcile the closure-status classifier and (b) confirm plan-vs-execute
dedup consistency so a feature already present by GUID is recognized on re-run.

**Findings**:
- `_gather_target_infl_feat_guids` (selection.py:3302) walks `FeatureGetAll()` →
  `IFsClosedFeature.ValuesOC` and returns **value-level** GUIDs. Closure status for a
  **feature** row is classified against this set (selection.py `_dep_status_feat`), so a
  feature whose *feature* GUID is present in the target but whose *value* GUIDs are what
  got collected will still be labelled **"new"** — matching the screenshot where present
  features render as `NEW`. Fix: classify feature rows against a **feature-level** GUID
  set and value rows against the value-level set (two sets, not one).
- Plan dedup: `inflection_features_plan_action` uses `_plan_gold_reserved_edit` with a
  `_target_iter` of `FeatureGetAll()` and GUID-equality lookup — feature-level, correct
  in principle. **(confirm live)** whether it actually matches on re-run, or whether the
  execute step's create path (`inflection_features_execute_action` creates
  unconditionally once planned as ADD) is producing new GUIDs when
  `factory.Create(parsed_guid, …)` silently falls back to a no-GUID create.

**Rationale**: the two-set reconciliation is a small, well-scoped correctness fix that
directly targets the "everything shows NEW" symptom; the create-path confirmation
prevents fixing the label while leaving a real duplicate-create bug underneath.

**Alternatives considered**: relying on FLEx to de-dupe — rejected, LCM does not
de-duplicate on GUID collision; a bad create either throws or creates a fresh-GUID
twin.

---

## R4 — GUID preservation & idempotency validation

**Decision**: Validate idempotency empirically — transfer into a clean target, snapshot
the feature/value/link inventory (count + GUIDs + names), re-run the identical transfer,
and assert zero deltas (SC-003). Use the reference pair `Ejagham Mini` →
restored/clean `Ejagham Full GT-Test`.

**Rationale**: Defect 2 is fundamentally an idempotency failure; a before/after count
diff on a real re-run is the definitive test and satisfies the "verification on a toy →
target pair with pre/post residue artifacts" quality gate.

---

## R5 — Remediation scope (settled)

**Decision**: **Prevention-only** (spec FR-011, user-confirmed 2026-07-13). No code path
in this feature modifies or deletes existing broken records. The current polluted target
is restored from a clean backup (or cleaned out of band) before validation. The
diagnosis is strictly read-only.

**Rationale**: keeps the change small and non-destructive; avoids an attended
destructive-write remediation pass in the critical path.

---

## Open items carried into Phase 1

- Confirm whether the flexicon `InflectionFeature` Operations surface exposes
  `GetSyncableProperties` / `ApplySyncableProperties` for `IFsClosedFeature` &
  `IFsSymFeatVal`, or whether an explicit handle-mapping copy is required (drives the R2
  implementation choice). Verify via FLExTools MCP against `Ejagham Mini`.
- Confirm the exact plan binding field name / location on the run-plan object
  (`models.py`) for the feature→POS link, consistent with `lexentry_ref_bindings`.

---

## T004 — Live-probe results (RESOLVED 2026-07-13, FLExToolsMCP, read-only)

Probed `flexicon` API mode against `Ejagham Mini` (source) and `Ejagham Full GT-Test`
(target). All runs certified read-only (0 target modifications).

**A. Syncable-properties surface (R2 open item — RESOLVED).**
`InflectionFeatureOperations.GetSyncableProperties(feature)` returns a dict with keys
`['Abbreviation', 'Description', 'Name']` for `IFsClosedFeature`; the class also exposes
`ApplySyncableProperties(item, props, ws_map=None, fill_gaps=False)`. **Decision: use the
`ApplySyncableProperties(..., ws_map=ws_mapping)` path for features** (mirrors the POS
path), which is the R2 preferred approach.
  - **Value caveat**: every feature in `Ejagham Mini` is an `IFsFeatDefn` with
    `ValuesOC` count = 0, so `GetSyncableProperties` on an `IFsSymFeatVal` could not be
    exercised empirically in this pair. The C3 implementation MUST therefore keep the
    explicit source→target handle-translation fallback for values (do not assume the
    Operations surface accepts an `IFsSymFeatVal` until proven on a project that has
    symbolic values).

**B. WS-handle divergence (R2 root-cause — CONFIRMED, smoking gun).**
  - Source `Ejagham Mini`: `en=999000001`, `etu=999000003`.
  - Target `Ejagham Full GT-Test`: `en=999000001`, `etu=999000002`.
  - The vernacular `etu` handle differs (source 999000003 vs target 999000002). The
    current code writes names with the **source** handle 999000003, which does not
    address `etu` in the target → the string lands on a wrong/absent WS and the
    feature/value shows as a bare GUID. `en` happens to coincide (999000001 in both),
    which is why analysis-WS names can survive while vernacular names are lost. This
    empirically confirms the R2 hypothesis and mandates ws-mapped writes (C3).

**C. `IPartOfSpeech.InflectableFeatsRC` accessor + `.Add` idiom (RESOLVED).**
  - Property is `ILcmReferenceCollection[IFsFeatDefn]`; exposes `Add`, `Contains`,
    `Remove`. Accessing it on a `p` typed as `ICmObject`/`ICmPossibility` fails the
    MCP casting validator — **must cast `IPartOfSpeech(p)` first** (validates T011).
  - Source `Ejagham Mini` currently holds **13** feature←POS reference-collection
    memberships across 20 POSes (C1 COUNT baseline for the reference pair).

**D. models.py binding (second open item — decided in T005).**
Field named `feature_category_links`, shape `{target_pos_guid: [feature_guid, ...]}`,
mirroring `lexentry_ref_bindings`. See data-model.md `FeatureCategoryLink`.
