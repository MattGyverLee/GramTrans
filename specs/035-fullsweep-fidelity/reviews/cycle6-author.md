# Cycle 6 — Original Author Review: census.py reorg (T045d)

**Date:** 2026-09-24
**Reviewer:** Original Author Agent (lex-author)
**Score:** 5/10 — CONCERNS (part b blocks approval as written)

> **Filing note (main session, 2026-09-24):** lex-author has no Write tool; this file
> was saved verbatim from its hand-back. **Context gap, recorded deliberately:** the
> dispatch prompt this reviewer received did NOT include the six live measurements
> (ops `op-133436809-002`, `op-133459014-003`) that motivated the proposal -- in
> particular measurement 6 (the engine calls Get/ApplySyncableProperties through only
> 12 accessors; the other 57 classes are copied by other code paths) and measurements
> 3-4 (syncable keys are not model field names; surfaces are sparse per object). The
> review's central premise -- that `model - syncable` is a *measurement of what the
> engine carries* -- is the premise those measurements dispute. Weigh it accordingly.

## 1. Does the reorg preserve FR-051/FR-052/FR-066 intent?

**(a) Field set from LCM metadata, not GetSyncableProperties keys — PRESERVES intent, and is not actually a change.** The worktree's `census.py` already sources `model_fields` from an injected `field_source` documented as "the LCM metadata enumeration" (module docstring, lines 16-17), separate from `syncable_fields` (the `GetSyncableProperties` keys). `class_field_coverage` already computes `engine_omitted = model - syncable` and raises `CensusContractError` on `unknown = syncable - model` (lines 229-237). So (a) is a documentation correction to research.md D-02, which currently reads as if the census itself is "driven by ... GetSyncableProperties" — ambiguous against the code's actual two-surface design. Low risk; recommend it as a D-02a addendum, not a code change.

**(b) `engine_omitted` → declared `engine_not_carried` in expected-divergent.json — DOES NOT preserve intent.** This is the substantive regression. FR-052/FR-066's "growth MUST be reported, never silently absorbed" is built on `engine_omitted` being *measured every run* by diffing two live surfaces (model vs. syncable). Under (b), the omitted set becomes a static, git-tracked, hand-authored list — checked only when a human edits it. That breaks the self-discovering property the FRs require: if the engine begins silently dropping a field it used to carry, `omitted_growth` today catches it automatically on the next run because `syncable_fields` shrinks. Under (b) nothing computes the engine's actual live syncable surface anymore for comparison purposes — `compared = model - roster_excluded - not_carried` is driven entirely by the two static roster sections plus the model enumeration. A regression in the engine's real coverage would go undetected unless someone happens to already know to edit `not_carried`. That is precisely backwards from what FR-052/FR-066 ask for ("growth ... MUST be reported").

It is also the exact mechanism research.md's own D-02 rejected: *"A hand-maintained per-class field list — rejected outright: it is exactly the 'hand-picked set' the spec bans (SC-004, FR-045, S-05, S-33, S-52)."* `engine_not_carried` with `(class, field, rationale, evidence)` entries is structurally identical to that rejected alternative, just relocated into expected-divergent.json next to the (legitimately hand-curated, because it documents *host*-driven exclusions like timestamps) EXPECTED_DIVERGENT roster. FR-051 already independently bans "a hand-listed set of domains or fields chosen per class" for the census itself; extending the roster file to also hand-list *engine* omissions conflates two different kinds of exclusion that FR-052 deliberately keeps separate (roster = what the *host*/design legitimately diverges on; engine_omitted = what the *tool* happens not to carry, which should shrink over time as flexicon/GramTrans improve).

Net effect if adopted as proposed: **reject part (b).** Part (a) is fine as a wording clarification.

## 2. Exact replacement text

**FR-052** (unchanged from current spec.md — do not reword; (b) is rejected):
> A field is excluded from comparison only if it appears on the EXPECTED_DIVERGENT roster (E.2) or is a field the transfer engine's own syncable-properties surface deliberately omits for that class, as MEASURED per run by diffing that class's LCM-metadata field enumeration against `GetSyncableProperties`; no other exclusion mechanism is permitted, and no exclusion may be satisfied by a hand-maintained declaration standing in for that measurement. The measured omitted set MUST be enumerated in every artifact, and any growth of it between runs MUST be reported as reduced coverage, never silently absorbed.

**FR-056 last sentence** — keep as-is; do not append engine_not_carried language. Current text already correctly routes "newly encountered field" classification to "the transfer engine's own syncable-properties surface" (measured), which (b) would sever.

**FR-065** — keep as-is (no change needed); it already conditions EXPECTED_DIVERGENT status on what "the transfer engine's own syncable-properties surface omits ... by design," which must stay a measured fact, not a declared one.

**FR-066** (unchanged, do not reword to reference a declaration section):
> The complete EXPECTED_DIVERGENT roster for a given class MUST be exactly this document's enumerated exclusions plus whatever the transfer engine's own syncable-properties surface is MEASURED to omit for that class; a comparator implementation MUST NOT substitute, in whole or in part, the interactive merge-preview UI's exclusion set, or a hand-declared engine-omission list, for this measurement. The omitted-for-that-class set MUST be enumerated per class in every artifact, and any growth of that set between runs MUST be reported as reduced coverage, never silently absorbed.

**D-02a** (supersedes D-02's ambiguous phrasing only, on point (a)):
> **D-02a.** The per-object field census enumerates `model_fields` from the class's own LCM metadata (field ids/names via the injected `field_source`, per CensusContractError's "an unenumerable class is not an empty one" guard), and separately reads `syncable_fields` as the exact key set `GetSyncableProperties` returns for that class. `engine_omitted = model_fields - syncable_fields` is computed fresh every run from these two live surfaces; it is never read from, or reconciled against, a static declaration. This supersedes D-02's "driven by ... GetSyncableProperties" phrasing, which read as if the census walks only the syncable surface — the implemented design (and this decision) instead treats the LCM metadata surface as the ground truth of "every field obtainable" (FR-051) and the syncable surface as a strict subset checked for subset-consistency (`class_field_coverage`'s `unknown` raise).

## 3. Test changes needed
- None, if (b) is rejected — `test_035_compare.py` TestClassFieldCoverage/TestCensusFields/TestOmittedGrowth (lines ~271-374) already test the measured-diff design and should be left as-is.
- If any part of (a)'s D-02a wording change is adopted, add one docstring-only assertion or comment-level test noting `model_fields` provenance is LCM metadata (optional, not required — behavior is unchanged).
- Do NOT add tests for an `engine_not_carried` roster section — that would be testing the rejected mechanism into permanence.

## 4. Risk that the declaration becomes a banned hand-listed field set (SC-004/FR-045)
**Confirmed, high.** `engine_not_carried` as proposed is structurally the same shape as the EXPECTED_DIVERGENT roster's `entries` (class/field/rationale/evidence) but applied to a fact (what the engine's code currently carries) that should be *derived from the engine's own introspectable surface*, not asserted by a person. SC-004/FR-045 forbid this exact substitution pattern for the idempotency class set ("never a fixed, hand-picked set"); FR-051 states it directly for fields ("rather than a hand-listed set of domains or fields chosen per class"); and D-02's own rejected-alternatives paragraph names this precise design and rejects it "outright." Recommend REJECT part (b) in full; keep `engine_omitted` measured as it is today in `census.py`.

---
**Reviewed By:** Original Author Agent
**Recommendation:** APPROVE part (a) as a D-02a wording addendum only; REJECT part (b) — request rework so `engine_not_carried` remains measured, not declared.

Files consulted (no edits made): `debug/fullsweep/census.py`; `tests/unit/test_035_compare.py` (lines 255-374); `specs/035-fullsweep-fidelity/spec.md` (FR-051..FR-068, FR-045, SC-004); `research.md` (D-02, lines 69-95); `data-model.md` (FieldCensus, lines 90-123); `contracts/artifact-schema.md` (line ~79); `contracts/expected-divergent.json` (header/derivation, lines 1-18).
