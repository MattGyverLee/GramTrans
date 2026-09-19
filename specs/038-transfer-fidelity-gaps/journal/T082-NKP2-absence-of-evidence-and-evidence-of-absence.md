# T082 / 038-NK-P2 — absence of evidence, and evidence of absence

**Settled** 2026-08-26 at the resume gate, by user decision. `038-NK-P2` moves
from PENDING to **REFUTED**. **T082 itself stays open** — its other half,
`038-NK-P3`, needs the live re-census this feature cannot currently reproduce.

## The question, as filed

> That FLEx or the LCM enforces name/representation uniqueness for
> `PhPhoneme`, `PartOfSpeech`, `MoMorphType` or `LexEntryInflType` at any level
> — UI validation, list constraint, or factory guard.

What had actually been measured was the *observable consequence*: zero
collisions across 97 phonemes, 50 keyed categories, 57 morph types and 15
inflection types in three projects. The roster said so plainly — *"absence of a
collision in three projects is not enforcement"* — and every entry already set
`key_unique_by_construction=false` on that basis.

The item's own constraint on the test is worth restating, because it is
stricter than "use a throwaway": **"never in a sanctioned read-only project and
never in `Target`"**. So the probe ran in `GT038 NKP2 Throwaway`, restored
headlessly from `backups/Target 2026-07-06 0218.fwbackup` — a project created
for this measurement and nothing else.

## Two layers, because the claim names FLEx and GramTrans reaches it through flexicon

The claim is about **FLEx or the LCM**. GramTrans never touches either
directly; it goes through flexicon. Probing only the layer GramTrans uses would
answer a different question than the one asked, and probing only the LCM would
miss what GramTrans's own writes can actually do. So both.

### Layer 1 — the flexicon Operations surface

| attempt | result |
|---|---|
| `PhonemeOperations.Create("a")` | **REFUSED** — `FP_ParameterError: Phoneme 'a' already exists` |
| `POSOperations.Create("Noun", "Nx")` | **REFUSED** — `FP_ParameterError: Part of Speech 'Noun' already exists` |
| `MoMorphType` | **no create surface at all** — flexicon exposes no `MorphTypeOperations` |
| `LexEntryInflType` | **no create surface at all** — no variant-inflection-type create |

Two refusals and two absences. On the two classes with no create path there is
nothing to refuse, which is a different fact from a guard and is recorded as
one.

### Layer 2 — the raw LCM factories, which is what the claim is about

| attempt | result |
|---|---|
| `IPhPhonemeFactory` → `PhonemesOC`, `Name`(vern) = `"a"` | **SILENTLY ACCEPTED** |
| `IPartOfSpeechFactory` → top-level `PossibilitiesOS`, `Name` = `"Noun"` | **SILENTLY ACCEPTED** |
| `IMoMorphTypeFactory` → `MorphTypesOA`, `Name` = `"stem"` | **SILENTLY ACCEPTED** |
| `ILexEntryInflTypeFactory` → under `Irregularly Inflected Form`, `Name` = `"Plural"` | **SILENTLY ACCEPTED** |

Not refused, not warned, not renamed. **And they persisted**, which is the half
that makes it a measurement rather than an observation about a cache — the
verification is a *fresh read-only session*, re-opening the project from disk:

| class | before | after | duplicate group |
|---|---|---|---|
| `PhPhoneme` | 23 | **25** | `'a'` × 3 |
| `PartOfSpeech` | 5 | **7** | `'Noun'` × 3 (top-level siblings) |
| `MoMorphType` | 19 | **21** | `'stem'` × 3 |
| Variant Entry Types | 7 | **9** | `'Plural'` × 3 (siblings under one parent) |

(× 3 rather than × 2 because the runner executed `Main` twice — once on its own
and once from the trailing call. Two independent duplicates of each, which is a
stronger result than one and was left as measured rather than tidied.)

Ops: `op-144922929-004` (baseline), `op-145059498-007` (probe),
`op-145120606-008` (verification), `op-145158674-009` (follow-on).

## The follow-on that did NOT reproduce

Layer 1's guard is **writing-system-scoped by signature** —
`Create(representation, wsHandle)` — so naming a different writing system was
the obvious way past it, and it is the obvious candidate mechanism for
census-evidence.md's 21 duplicate phoneme names. Tested:
`Create("a", default ANALYSIS ws)` was **also refused**. The starter phoneme
carries `'a'` in *both* writing systems, so `Exists('a', anal)` is True too.

The guard held. **How those 21 duplicates arose is still unexplained**, and is
not claimed here — they did not come from the path tested. Recorded as a
negative result because that is the point of having run it.

## What changes, and what deliberately does not

**No roster entry moves.** Every one already sets
`key_unique_by_construction=false` and relies on
`on_ambiguous_key=harness_error`. The measurement **confirms** that setting; it
was chosen to be safe under either outcome and it was.

What changes is the *standing* of the claim, and the direction matters. The
item said a later confirmation *"could only RELAX an entry from `false` to
`true`, never tighten one"* — an escape hatch left open because nobody had
looked. It is now **closed by measurement**. "Zero collisions in three
projects" was absence of evidence; this is evidence of absence.

**A Layer-1 guard is not an enforcement claim, and must not be recorded as
one.** flexicon refusing a duplicate on the two classes where it *has* a create
surface means GramTrans's own writes cannot mint one *through those two calls*.
That is a property of the wrapper GramTrans happens to use — not of FLEx, not
of the LCM — and it says nothing whatever about what a project already
**contains**. census-evidence.md's 21 duplicate phoneme names and the
66-of-113 `PhNCFeatures` name collisions in `Mbugwe LizzieHC practice` are the
standing proof that duplicates arrive by other paths. Reading the wrapper guard
as enforcement would be exactly the inversion this feature keeps catching: a
check that covers one direction being read as a guarantee about the other.

## Why T082 is still unchecked

`038-NK-P3` — *"that the natural-key fallback actually recovers the measured
losses"* — is unmoved. T098 narrowed it from four claims to one class
(`PhNCFeatures` duplicates, 12 groups / 21 extra on ngoreme, 1 / 3 on ejagham),
and its acceptance is *a census diff, not a file*. That needs a live re-census
of pairs whose source projects have moved off their pinned digests, with
`Ngoreme Target` never to be restored. One half of T082 is settled; the task is
not.

## The throwaway project

`GT038 NKP2 Throwaway` is left on disk beside the other `GT038 *` targets this
feature created, so the measurement can be re-checked rather than only
re-read. It holds deliberately corrupted data — four duplicate-name groups —
and must never be used as anything but this probe's evidence.
