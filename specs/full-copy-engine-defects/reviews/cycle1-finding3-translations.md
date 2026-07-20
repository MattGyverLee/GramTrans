# Finding #3 root-cause confirmation — CmTranslation `.Translations` namespace

**Method note:** FLExToolsMCP tools were not present in this session's toolset
(no MCP server registered). Confirmed equivalently by reading the actual
flexicon source that backs the live `FLExProject` handle
(`D:\Github\_Projects\_LEX\flexicon\flexicon\code\FLExProject.py`, the editable
install backing `pyflexicon` 4.1.1) — this is the authoritative definition of
every attribute the live handle exposes, so grepping its `def <Name>(self):`
properties is equivalent to reflecting the live object.

## Confirmation: no `.Translations` namespace
`FLExProject.py` defines properties `Senses` (1233), `Examples` (1296),
`Pronunciations` (1449), `Etymology` (1517) — **no `Translations` or
`ExtendedNote` property exists anywhere in the file.** `getattr(source,
"Translations")` on a live handle raises `AttributeError`, exactly as Finding
#3 states.

## The real fix is NOT "find the right Translations ops" — there is none, and none is needed
`Lexicon/ExampleOperations.py` (`project.Examples`) already fully owns
`TranslationsOC` end-to-end inside its own `GetSyncableProperties`/
`ApplySyncableProperties` (lines 402-425, 475-549): it serializes each
`ICmTranslation`'s `Translation` multistring + `TypeRA` GUID, and on apply
does a clear-and-rebuild — creating each target `ICmTranslation` itself via
`ICmTranslationFactory` and setting its content. This runs automatically
whenever the *owning* `LexExampleSentence` is synced (i.e. whenever the
`LexSense.ExamplesOS` `OWNED_OBJECT_MAP` row's `_copy_one_owned_child` calls
`project.Examples.ApplySyncableProperties` on the new example).

`owned.py`'s `walk_owned_children` then **unconditionally recurses** into
every newly-created child (owned.py:861-862) regardless of `spec.recurse`,
which re-matches the `LexExampleSentence.TranslationsOC` row and creates a
**second, duplicate** `ICmTranslation` via `ICmTranslationFactory.Create(new_owner,
resolved_type, guid)` (owned.py:626) — this factory call auto-adds to
`TranslationsOC`, so the phantom shell is added to the collection *before*
the subsequent `getattr(source, "Translations")` sync-copy attempt raises and
gets reported dropped. Net effect: real translations are already copied
correctly by the Examples-level sync, but a duplicate near-empty
`ICmTranslation` (type set, no text) is left behind on the target, and a
false-positive "dropped" record is emitted.

**Exact fix:** delete the `LexExampleSentence`/`TranslationsOC`
`OwnedObjectSpec` row entirely (owned.py:119-129, plus its `_TRANSLATION_REF_SPECS`
wiring if unused elsewhere) — the row is redundant with, and actively conflicts
with, the Examples-level sync. No alternate "Translations ops" object should be
substituted.

## Sibling audit — `_sync_ops_name(owning_field)` vs. live `FLExProject` attribute

| owning_field | owner_class | derived name | live attr? | status |
|---|---|---|---|---|
| ExamplesOS | LexSense | Examples | YES | OK |
| TranslationsOC | LexExampleSentence | Translations | **NO** | Finding #3 — remove row (redundant) |
| PronunciationsOS | LexEntry | Pronunciations | YES | OK |
| EtymologyOS | LexEntry | Etymology | YES | OK |
| SensesOS | LexSense | Senses | YES | OK |
| ExtendedNoteOS | LexSense | ExtendedNote | **NO** | Latent sibling — genuine gap |
| ExamplesOS (LexExtendedNote row) | LexExtendedNote | Examples | YES | OK |

`ExtendedNoteOS` is a **different-flavored** sibling than `TranslationsOC`:
`LexSenseOperations.py` has no special-cased `ExtendedNoteOS` handling at all
(unlike `Examples`/`TranslationsOC`), so there is no existing flexicon
ops surface to fall back to. This one genuinely drops `LexExtendedNote`
content today and needs either a new ops-level sync method or an inline
dict-based copy inside `owned.py`'s `_copy_one_owned_child` — it cannot be
fixed by row deletion like `TranslationsOC`.
