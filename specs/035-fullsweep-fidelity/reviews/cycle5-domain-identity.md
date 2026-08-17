# Domain Expert Review — Cycle 5 Identity Rulings

**Date:** 2026-08-18
**Domain:** FLEx/LCM object identity, evaluation state, and structural fidelity
**Feature:** 035-fullsweep-fidelity
**Scope:** FR-183, FR-184, FR-185/186/187 (+FR-090), wordform-identity substitution, and a new degree/depth principle

> Provenance note: authored by the lex-domain agent, which has no Write tool in
> its definition; the main session persisted this content verbatim.
> The agent also reports that FLExToolsMCP was not exposed to its toolset in this
> session (only Read/Grep/Glob/WebFetch), so the verification below rests on
> documented LCM/FLEx domain semantics rather than a live MCP query. Points where
> a live check would be prudent before final sign-off are flagged inline.

## 1. TOOL-OWNED IDENTITY (FR-183) — PASS

Correct. FLEx records human-vs-machine evaluation of an analysis via `CmAgent`/`CmAgentEvaluation` objects, and a freshly created target project (from the stock template) already ships default agent instances. Reusing the *source's* live agent identity in the target is wrong on two counts: (a) it asserts that another project's own judgments/acts belong to this target's evaluator, misattributing provenance; (b) it can collide — object identity is unique-by-construction within a project, so writing a second instance under a duplicated identity either fails outright or silently merges two provenance streams into one. A name-based lookup as a substitute is also unsafe (can miss an existing instance and mint a duplicate). Pinning to one fixed, tool-owned constant that is measured (never exempted) is the only construction that avoids both failure modes. Confirm at implementation time whether the constant should be the template's built-in agent GUID or a GramTrans-specific one; either is defensible domain-wise, but this should be a deliberate choice, not accidental.

## 2. EVALUATION STATE VS AGENT IDENTITY (FR-184) — PASS

Correct FLEx semantics. Human-approval of a `WfiAnalysis` is a derived tri-state — approved / disapproved / no human evaluation recorded ("parser-only") — read off the set of `CmAgentEvaluation` records attached to it, keyed by *which kind* of agent (human vs. parser) made the call and its accept/reject flag, not by that agent object's own identity matching across projects. Two independently created projects' "human" agents are not guaranteed to share a GUID; comparing by agent identity instead of evaluation state will misclassify a genuinely approved analysis as a mismatch whenever the target's local agent instance differs from the source's — exactly the mechanism behind the cited 219-analysis regression. FR-184 correctly separates "was this act performed" from "who performed it."

## 3. NATURAL-KEY IDENTITY — reversal roster — PASS, with one flagged gap

The one-container-per-writing-system invariant for the reversal index, and form-keyed deduplication of the top-level reversal entry (and its owned sub-entries), are real, operationally-enforced LCM/FLEx properties — FLEx's reversal-index lookup and editing surfaces treat writing-system tag and entry form as natural keys, not merely UI conventions, and sub-entries nest recursively under the same form-keyed discipline. The Yi Sichuan figures (7 indexes, 25,116 entries at two nesting levels) are consistent with, and corroborate, both claims being live at production scale.

On "any other class currently missing": writing systems themselves are the other classic one-per-tag natural-key case in FLEx, but they are **not** missing from anywhere — they are already handled by a separate, adequate mechanism (the explicit pre-run WS mapping of Section E.3/FR-069–072), and folding them into FR-185/187 instead would be redundant, not corrective. The gap worth flagging is not a new class for *this* roster but rather **wordform** (see #4) — it fits FR-185's own definition (stable identifier, but constrained by a natural key unique by construction) at least as strongly as the reversal classes, and should be confirmed as a roster entry when the Natural-Key Identity Roster artifact is actually authored, even though spec.md's class-agnostic register (correctly) declines to name it.

## 4. WORDFORM IDENTITY SUBSTITUTION — PASS

Confirmed: `WfiWordform` is deduplicated by its surface form together with writing system (`FindOrCreateWordform`-style lookup) — the pair (WS, exact string) is the natural key, not the object's own GUID. Two distinct wordform objects legitimately sharing identical *text* is possible only when the writing systems differ (e.g., orthographically identical strings in two vernacular WSs); under the same WS, the lookup path is designed to prevent two objects from coexisting with the same form. Reusing a pre-existing target wordform when a source wordform's text matches is therefore correct behavior, not object substitution to be penalized — it must land in FR-097's IDENTITY-SUBSTITUTION bucket, never as unexplained loss or as a masked "already present" pass. Recommend making explicit (in the roster artifact, not spec.md) that wordform is admitted on the (WS, form) natural key, since it is likely the single highest-volume class this mechanism exists to cover.

## 5. COMPLEXITY PRESERVATION (degree/depth) — deserves its own requirement; not fully implied

Per-collection membership, applied recursively and honestly, gets most of the way there: an owned reference-*sequence* field (senses, components, slots) already requires equal-length, equal-order comparison (FR-059/079/082/083), which structurally guarantees degree for those fields; and FR-060 makes a genuine owner mismatch a distortion, which catches most re-parenting. But two concrete FLEx-user-facing gaps survive a pure per-object walk:

- **Comparator recursion depth is self-blind.** If the walker that enumerates a self-referential owned hierarchy (reversal sub-entries, sub-senses, possibility-list sub-items) stops one level early due to an implementation bug, both sides report "0 objects at that depth" and the category-level vacuity guards (FR-095/096) — defined per *class*, not per *nesting depth* — see nothing wrong, because the aggregate counts are dominated by shallower levels. A dictionary entry that should show 5 senses (or 3 levels of sub-entries) can silently render fewer to a linguist while every object that *was* visited compares clean.
- **Per-parent count is a different, cheaper signal than per-child identity**, and catches defects (recursion bugs, silent re-parenting under a wrong grandparent) that a per-object identity walk can miss precisely where the walk itself is where the bug lives — the same rationale already used to justify independent corroboration in FR-094 and FR-098.

Recommendation: add a first-class requirement that (a) any recursive owned hierarchy's census must continue until no further children exist in *source* at any node, with maximum depth reached recorded per class as an artifact discriminator, and (b) per-parent child-count comparison is checked independently of per-child identity matching. This is not redundant with per-collection membership — it is the corroborating check that catches the case where per-collection membership's own machinery is the thing that's broken.
