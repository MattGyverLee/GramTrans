# Cycle 1 — Domain sweep-pattern audit: ItemClsid vs `factory_by_item_clsid`

**Date:** 2026-07-18 | **Agent:** lex-domain (read-only) | **Scope:** every target
list the resolver can drive to `references.py::apply_reference`'s CREATE arm.

> Authored by the main session from lex-domain's inline findings (the lex-domain
> subagent has no Write tool). Content is the domain agent's audit.

The CREATE arm (references.py ~1008-1169) dispatches the LCM factory by the TARGET
list's `ItemClsid` via the closed map at lines 1041-1047:
`{66: SemDom, 26: Anthro, 5042: MorphType, 5118: LexEntryType, 7: CmPossibility}`.
Any list whose real `ItemClsid` is outside `{66,26,5042,5118,7}` raises
`UnmappedItemClassError` → reported-dropped, never created.

## (a) REFERENCE_FIELD_MAP (references.py 68-285) — 23 rows

| Field(s) | ItemClsid | Status | Note |
|---|---|---|---|
| SenseTypeRA, UsageTypesRC, DomainTypesRC, DialectLabelsRS (Sense+Entry), StatusRA, PublishIn, DoNotPublishInRC, DoNotShowMainEntryInRC (Sense+Entry), ShowComplexFormsInRS, TypeRA (CmTranslation), LanguageRS, ExtendedNoteTypeRA | 7 | MAPPED | generic CmPossibility (confirmed via inline comments) |
| AnthroCodesRC | 26 | MAPPED | CmAnthroItem |
| SemanticDomainsRC | 66 | MAPPED | CmSemanticDomain |
| MorphTypeRA | 5042 | MAPPED | MoMorphType |
| VariantEntryTypesRS, ComplexEntryTypesRS | 5118 | MAPPED | LexEntryType |
| MoForm.PhoneEnvRC | — | OUT-OF-SCOPE | flat OS, not a list; excluded via `categories._MOFORM_DEFERRED_FIELDS` |
| MoForm.StemNameRA | — | OUT-OF-SCOPE | `target_list_path=None` (per-POS); deferred |

## (b) Reversal PartOfSpeechRA (reversals.py ~97-104)

| List-accessor | Field | ItemClsid | Status | Note |
|---|---|---|---|---|
| `tgt_index.PartsOfSpeechOA` | ReversalIndexEntry.PartOfSpeechRA | **5049** | **MISS** | PartOfSpeech; confirmed live (0/134 entries got a PartOfSpeechRA after Move). The P0. |

## (c) 030 dynamic-owner thesaurus (references.py ~1191-1413)

`discover_owning_possibility_list` / `mirror_possibility_list_to_target` impose **no
clsid constraint** — `ThesaurusItemsRC`'s field type is `CmPossibility` (supertype),
so it can structurally resolve to ANY possibility list in the project, including a
`PartsOfSpeechOA` (clsid 5049) if a thesaurus reference ever pointed at a POS-derived
item. **Vacuous-live everywhere today** (030 research.md Finding 1: 0 populated across
all 79 on-disk projects), so **not live-reachable now**, but a **latent structural MISS
sibling** to 5049 — should be covered by the same owner-taking-`Create` patch, not
assumed safe.

## Verdict

- **MISSES TO FIX:** `5049` (confirmed live — reversal `PartOfSpeechRA`) + `5049`
  latent via the 030 thesaurus dynamic-owner path (same fix covers both).
- **CONFIRMED SAFE:** 23/23 REFERENCE_FIELD_MAP rows (21 dispatchable + 2 correctly
  out-of-scope). No other clsid is missing.
- **Fix scope is bounded:** a single owner-taking `IPartOfSpeechFactory.Create`
  special-case for clsid 5049 in the CREATE arm closes both the live and latent misses.
