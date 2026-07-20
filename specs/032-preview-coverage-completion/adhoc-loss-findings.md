# US5 Findings: Ad hoc / Compound Rule Transfer Loss (read-only investigation)

**Feature**: 032-preview-coverage-completion | **Tasks**: T030–T033
**Contract**: [contracts/adhoc-loss-probe.md](contracts/adhoc-loss-probe.md)
**Probe**: `debug/probe_adhoc_loss.py` (read-only; writes nothing to any FLEx project)
**Date**: 2026-07-19

Per FR-016 this is an **investigation with a decision gate**, not a reproduction
deliverable. The probe characterizes the loss, tests the leading root-cause
hypothesis, and this document records the scope decision.

## What was run

`debug/probe_adhoc_loss.py` opened a source and target project **read-only** via
flexicon, enumerated every leaf ad hoc / compound rule in the source (reusing
`categories._rules_enumerate_all`, so subclass-only reference slots are visible
via `_cast_rule_concrete`), and for each rule recorded:

- whether the rule is present on the target by GUID;
- how many of its member-reference **dependencies** (morphemes / allomorphs /
  MSA→POS, via `categories.adhoc_compound_rules_dependencies`) resolve to a real
  target object (checked through the target `ICmObjectRepository.IsValidObjectId`)
  vs are absent;
- the **WS-drop hypothesis (R5)**: which source writing systems actually carry a
  value on the rule's `Name` multistring (resolved by WS *handle*, not tag), and
  which of those have no counterpart in the target — i.e. the WSs that
  `to_ws_map_dict` / `ApplySyncableProperties` would silently drop
  (`Lib/ws_mapping.py` ~66–85).

Evidence JSON: [adhoc-loss-evidence.json](adhoc-loss-evidence.json).

### Live evidence

| Source → Target | Leaf rules | Present by GUID | With unresolved deps | Name WSs dropped |
|---|---|---|---|---|
| `Ejagham Mini` → `Ejagham Full GT-Test` | 0 | 0 | 0 | — (no rules) |
| `Esperanto` → `Ejagham Full GT-Test` | 5 (all `MoEndoCompound`) | 0 | 5 | 0 |

`Mbugwe Lizzie HCPractice` (cited in research.md as an ad-hoc-bearing project) had
no `.fwdata` on this machine, so `Esperanto`'s five compound rules are the live
sample. All five carry **no** `Name`-multistring content (compound rules are
structural), so the WS-drop check has nothing to drop; their entire material
content is the **owned/reference MSA wiring**, which is exactly what shows up as
`deps_absent` when the target never received the source morphemes.

## Root cause

**The leading hypothesis (R5) is REFUTED for the ad-hoc/compound path.** The
`to_ws_map_dict` silent-WS-drop is real for WS-bearing multilingual string
fields, but it is **not the material loss mechanism for ad hoc / compound
rules**:

- Compound rules (`MoEndoCompound` / `MoExoCompound`) carry no user-facing
  `Name`; their content is `Left/Right/To/OverridingMsaOA` + `PartOfSpeechRA`.
- Ad hoc prohibitions (`MoMorphAdhocProhib` / `MoAlloAdhocProhib`) reference
  morphemes / allomorphs (`MorphemesRS` / `AllomorphsRS` / `FirstMorphemeRA`).

For both, the material content is **GUID-wired references to other objects**, not
WS-tagged strings. The observed loss vector is therefore an **unresolved
reference** — a member the rule points at that is absent from the target closure
— not a dropped writing system.

## Is that loss silent? No.

The reference vector is **already never-silent** through category-agnostic
channels that ad hoc / compound rules flow through unchanged:

- Closure planning walks `adhoc_compound_rules_dependencies` (`Lib/preview.py`
  ~805) and emits per-dependency actions; an unresolved dependency becomes a
  `Skip(DEPENDENCY_UNRESOLVED)` or an `EXCLUDED_LOSSY` warning.
- `Lib/report.py.render_text_summary` renders **every** skip
  (`[<category>] <guid> <reason>: <detail>`), every `excluded_lossy` warning, and
  every `dropped_items` entry regardless of category — so an ad hoc rule that
  loses a reference is reported on the post-run statistics/report surface, not
  silently transferred in a broken state (Constitution Principle V).

## Scope decision

**(b) No new in-scope silent-loss path is confirmed → documented known
limitation; no new reporting wiring required (T033 = no-op).**

- The WS-drop mechanism (R5) does not apply materially to this path (refuted
  above). Where a rule *did* carry a `Name` WS with no target counterpart, US4's
  related-languages WS defaulting (this feature) now maps it to a real target WS
  before write, further shrinking even the cosmetic exposure.
- The reference-loss vector is already surfaced by the existing never-silent
  channels (`skips` / `excluded_lossy` / `dropped_items`); adding a bespoke
  ad-hoc reporting path would duplicate them (T033 not needed).

### Known limitation (recorded)

An ad hoc / compound rule whose referenced morpheme, allomorph, or MSA is **not
in the transfer closure** on the target will transfer with that reference
omitted, and the omission is **reported** (never silent) via the standard
skip/dropped-item channels. Fully reproducing such rules end-to-end (materializing
missing referents) is **out of scope for feature 032** (FR-016).

### Follow-up recommendation

If end-to-end reproduction of ad hoc / compound rules against a fresh target is
later desired, it warrants a **separate feature** that (1) pulls the full
member-reference closure for selected rules and (2) verifies OA-ownership
persistence through commit (the deferred live write round-trip noted in
`categories.py` ~2845). This document is the read-only evidence that such work is
a net-new deliverable, not a bug fix within 032.
