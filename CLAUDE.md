<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
at specs/029-sense-pictures/plan.md
<!-- SPECKIT END -->

## Git Workflow Protocol (specs → main, work → worktree)

**Spec artifacts are committed directly to `main`.** Anything under a `specs/`
feature folder — `spec.md`, `plan.md`, `research.md`, `data-model.md`,
`contracts/`, `quickstart.md`, `probe-results.md`, `checklists/`, `tasks.md`,
amendments, and any other planning doc — goes straight to `main`, not onto a
feature branch.

- **Why:** spec files on a feature branch are invisible to other agents/sessions
  until merged. That created a backlog where the specs that most needed work
  could not be seen. Keeping them on `main` means every session sees the full,
  current queue of what needs doing.
- Spec artifacts are additive-per-feature (each lives in its own `specs/NNN-*/`
  folder), so committing them to `main` should **not conflict** with other
  branches. Keep it that way: do not edit another feature's spec files from an
  unrelated worktree.
- The `.specify/feature.json` pointer and the `<!-- SPECKIT -->` block in this
  file are spec-adjacent bookkeeping and also commit to `main`.
- This applies to `/speckit-specify`, `/speckit-plan`, `/speckit-tasks`,
  `/speckit-clarify`, `/speckit-analyze`, and any manual spec edits.

**Implementation / work files are committed on a worktree**, not `main`.
Once a feature is actually being *implemented* (source under `src/`, tests under
`tests/`, and any non-spec change), do that work in a dedicated git worktree on a
feature branch (e.g. `../GramTrans-NNN-<short-name>` on branch `NNN-<short-name>`),
and merge back to `main` when the work is validated.

- Rule of thumb: **if it lives under `specs/`, commit it to `main`; otherwise
  commit it on the feature worktree.**
- A single `/speckit-plan` run may create the worktree *and* write spec files —
  commit the spec files to `main` and keep code changes on the worktree.

## flexicon dependency

GramTrans runtime depends on **flexicon** (dist name `pyflexicon`), a standalone
independent package — it is NOT a fork or patch of stock `flexlibs`
(cdfarrow/flexlibs, the upstream the constitution calls "flexlibs1"). flexicon natively
provides both the `GetSyncableProperties` writing-system enumeration (via
`project.WritingSystems.GetAll()`) and the `ApplySyncableProperties(item, props,
ws_map=None)` method on `BaseOperations`.

The 8 Grammar Operations subclasses each declare an override of `ApplySyncableProperties`
for MCP-indexer visibility (the indexer's static analysis doesn't follow inheritance):

- `Grammar/POSOperations.py`
- `Grammar/MorphRuleOperations.py`
- `Grammar/GramCatOperations.py`
- `Grammar/InflectionFeatureOperations.py`
- `Grammar/NaturalClassOperations.py`
- `Grammar/EnvironmentOperations.py`
- `Grammar/PhonologicalRuleOperations.py`
- `Grammar/PhonemeOperations.py`

### Install

`pyproject.toml` declares `pyflexicon>=4.5.2` — the floor carrying both:

- the GUID-preserving create surface feature 033 depends on
  (`BaseOperations._CreateWithGuid` plus the optional `guid=` kwarg on
  `Texts.Create`/`Paragraphs.Create`/`Segments.AppendSentence`/`Wordforms.Create`/
  `WfiAnalyses.Create`/`WfiGlosses.Create`/`WfiMorphBundles.Create`, flexicon
  PR #239), and
- (feature 037, current floor) `NaturalClassOperations.GetSyncableProperties`/
  `ApplySyncableProperties` FeaturesOA wiring for feature-based natural
  classes (`IPhNCFeatures`) -- `GetSyncableProperties` now emits
  `FeaturesGuid` + `Features` (a list of `{"FeatureGuid", "ValueGuid"}`
  specs) and `ApplySyncableProperties` rewires them against the target's
  `PhFeatureSystemOA` by GUID, mirroring what `PhonemeOperations` already
  does for phonemes (flexicon issue #222).

> **The floor is 4.5.2, not 4.5.0 or 4.5.1 -- do not lower it.** Each of the
> three releases looks equivalent by changelog and is not:
>
> - **4.5.0** wired FeaturesOA behind `hasattr(nc, "FeaturesOA")`, which is
>   *unconditionally False*: pythonnet resolves attributes against the STATIC
>   wrapper type, and `NaturalClasses.GetAll()` yields base-`IPhNaturalClass`
>   proxies on which the `IPhNCFeatures`-only `FeaturesOA` is invisible. The
>   feature was 100% dead while all 1467 flexicon tests passed, because they
>   built factory-fresh CONCRETE-typed objects. Verified live: 41/41 natural
>   classes still hollow.
> - **4.5.1** discriminates on `.ClassName` and casts (`IPhNCFeatures(nc)`).
>   This is the fix that actually transfers features. It gates the apply on
>   `if features:`, so a class whose `FeatureSpecsOC` is genuinely EMPTY gets
>   `Features == []`, which is falsy -- its `FeaturesOA` stays null and
>   GramTrans's source-aware guard reports a loss that did not happen.
> - **4.5.2** gates on key presence (`features or features_guid`) instead of
>   truthiness, so an empty-but-present feature structure round-trips as an
>   empty-but-present structure.
>
> Practical consequence: on 4.5.1 the transfer is correct for the 38 Ngoreme
> classes that carry specs and reports 3 phantom losses; on 4.5.0 it silently
> loses all 41. Only 4.5.2 is clean.

Install from the local directory:

```powershell
pip install -e D:/Github/_Projects/_LEX/flexicon
```

Verify it resolves to the working tree rather than a stale site-packages copy:

```powershell
python -c "import flexicon; print(flexicon.__file__)"   # must NOT be site-packages
```

> **Why the floor matters (GUID-preserving create):** on an older flexicon
> every `guid=` kwarg raises `TypeError`, which the engine's `_safe`/
> `except Exception` wrappers swallow into a generic "create failed" drop. A
> too-low flexicon therefore makes the transfer *silently* regenerate
> identities instead of failing loudly.

> **Why the floor matters (natural-class features, feature 037):** below
> flexicon 4.5.0, `NaturalClassOperations.GetSyncableProperties` returns only
> `Name`/`Abbreviation`/`Description`/`PhonemeGuids` -- it never touches
> `FeaturesOA` at all, and `ApplySyncableProperties` just delegates to
> `BaseOperations`, which has no feature-structure handling. Every
> feature-based natural class (`IPhNCFeatures`) therefore transferred as an
> empty shell: correct Name, correct GUID, `FeaturesOA` silently null.
> Measured against two live projects: 0 of 34 `PhNCFeatures` arrived with a
> feature structure in one (source: 41 of 41), 0 of 11 in the other (source:
> 15 of 15) -- silently breaking 14 of 21 and 1 of 6 phonological rules
> respectively, since a rule referencing a feature-based natural class with
> no features can no longer match anything. `Lib/categories.py`'s
> `natural_classes_execute_action` now raises `RuntimeError` instead of
> reporting a transfer with this defect as successful; the flexicon floor
> bump is what makes the non-raising, fully-correct path possible at all.

### Constitution authority

Per [constitution v5.1.0 Principle II](.specify/memory/constitution.md), module code
imports flexicon modules **directly**. There is no `flavors/` adapter contract in this
repo. The LibLCM-direct implementation is a separate post-Phase-2 sibling repository,
not an in-tree deliverable. See the constitution Sync Impact Report for the v4.0.0 →
v5.0.0 rationale.

## Session handoff

See [STATUS.md](STATUS.md) for the most recent session's validated work (Layer 1+2
done against the Ejagham Mini → Ejagham Full GT-Test pair) and the pickup checklist.
The next session's blocking task is **T-Spike** in
[specs/001-phase0-additive-transfer/tasks.md](specs/001-phase0-additive-transfer/tasks.md):
refactor `gramtrans.py.transfer_verb_vertical()` into the `Lib/preview.py` +
`Lib/transfer.py` Preview/Move split required by constitution v5.1.0 Principle III
closing clause before Layer 3 begins.

## Rules

When working and referencing flexicon or liblcm, ALWAYS use FLExToolsMCP instead of using direct code inspection. This allows lookup and testing. `Ejagham Mini` and `Esperanto`, `Mbugwe LizzieHC practice` are good (read-only) test projects for many phenomena.

> **`Esperanto` is READ-ONLY in the strong sense: it is not a project you can
> edit.** Read it freely; never select it as a transfer *target*, and never
> plan a write against it. "Read-only test project" above is a statement of
> fact about what is possible, not merely a convention to observe.
>
> For anything that WRITES, use the throwaway `Target`
> (`C:\ProgramData\SIL\FieldWorks\Projects\Target`), restored from a known
> backup first — `tests/integration/harness/restore.py` does this headlessly,
> e.g. from `backups/Target 2026-07-06 0218.fwbackup`. Restore-before-write is
> what makes a live verification repeatable *and* keeps real language data out
> of the blast radius.

> Exact project name, verified 2026-08-17: `Mbugwe LizzieHC practice` (note the
> spacing — "LizzieHC practice", not "Lizzie HCPractice"). A directory named
> `Mbugwe Lizzie HCPractice` also exists on disk but is an EMPTY SHELL with no
> `.fwdata`, so opening it fails. Do not "correct" the name back.
