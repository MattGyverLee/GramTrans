# Feature 024 — Live-Validation Status (T037)

**As of:** 2026-07-12 (024 merge).

All 024 fidelity paths are **unit/fakes-proven** and green in the offline suite. This
document records which paths have additionally been **live-confirmed** against a real
FieldWorks project (read-only, via FlexTools MCP on `Ejagham Mini`) and which remain
**fakes-only / vacuous-live** — i.e. the path is correct in tests but the primary test
project contains no populated data to exercise it live, so a **constructed fixture** is
needed for end-to-end live proof.

## Live-confirmed on Ejagham Mini

- **US1 referenced-possibility resolver** — proven via a real
  `PossibilityListOperations.ApplySyncableProperties` write on the disposable
  `Ejagham Full GT-Test`: a non-default-WS (`etu`) alternative landed by Id-match; an
  absent Id (`fr`) was silently skipped (confirming the need for the never-silent
  pre-check). Temp item created + deleted; project left clean.
- **LexEntryRef presence** — 6 variant `LexEntryRef`s exist on `Ejagham Mini` (all
  `RefType=0` variant; 0 complex-form), owned by 6 of 252 entries, so the
  variant-relationship **DROP_REPORTED** path is partially live-reachable.

## Fakes-only / vacuous-live — need a constructed fixture for live proof

| Path | Why not live-proven on Ejagham Mini |
|------|-------------------------------------|
| Lexical relations (FR-008) | 0 `LexReference`s populated |
| Affix-allomorph `MsEnv` (+ `PhoneEnvRC` / `StemNameRA`) | 0 populated across 106 `MoAffixAllomorph` |
| `LexExtendedNote` / `LexAppendix` / `ThesaurusItems` possibilities | 0 populated; `LexDb.AppendixesOC` = 0 |
| `LexReference` TREE-type root = `TargetsRS[0]` | no tree-type relation to exercise (carried domain assumption) |
| `LexEntryRef` variant/complex-form **full** drop coverage | variant entries exist (partial), but complex-form = 0 |
| `CmPicture` / `CmFile` (`LexSense.PicturesOS`) | 0 populated |
| Multi-WS UPDATE (3+ writing systems) | Ejagham projects register only `en` + `etu` |

## Convention

A path staying on this list is **not** a defect — it means the offline suite proves the
logic and the live gap is a fixture-availability limitation. Constructing the fixtures
(a project deliberately populated with the above) is a maintenance/QA task; the
follow-on features (025–030) that reproduce the deferred data will each need their own
live fixtures regardless.
