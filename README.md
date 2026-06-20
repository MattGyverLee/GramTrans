# GramTrans

A FlexTools-compatible module that transfers FieldWorks Language Explorer (FLEx)
grammar pieces — phonology, morphology, lexicon scaffolding, and templates — from a
"toy" source project (typically the project used for FLExTrans / parser bring-up) to
a target production project.

**Status**: Phase 0 (Additive) — see [STATUS.md](STATUS.md) for the latest session's
validated work and [specs/001-phase0-additive-transfer/](specs/001-phase0-additive-transfer/)
for the spec / plan / tasks.

## Documentation

- **[Constitution v5.0.0](.specify/memory/constitution.md)** — governing principles
- **[Spec](specs/001-phase0-additive-transfer/spec.md)** — Phase 0 functional requirements
- **[Plan](specs/001-phase0-additive-transfer/plan.md)** — implementation plan
- **[Tasks](specs/001-phase0-additive-transfer/tasks.md)** — task list
- **[Research](specs/001-phase0-additive-transfer/research.md)** — design decisions
- **[Data Model](specs/001-phase0-additive-transfer/data-model.md)** — in-module data shapes
- **[Contracts](specs/001-phase0-additive-transfer/contracts/)** — UI/engine boundary
- **[Quickstart](specs/001-phase0-additive-transfer/quickstart.md)** — end-to-end validation scenarios
- **[CLAUDE.md](CLAUDE.md)** — agent context + flexlibs2 fork install instructions

## flexlibs2 fork dependency

GramTrans runtime depends on the **MattGyverLee/flexlibs2 fork**, not stock flexlibs2.
The fork carries two patches required by GramTrans:

1. A fix to `GetSyncableProperties` so it enumerates writing systems via
   `project.WritingSystems.GetAll()` instead of the nonexistent
   `ws_factory.WritingSystems` attribute (stock flexlibs2 crashes on every call).
2. A new `ApplySyncableProperties(item, props, ws_map=None)` method on
   `BaseOperations` plus the 8 Grammar Operations subclasses — symmetric inverse of
   `GetSyncableProperties`, generic dict → multistring / string apply.

### Install (developer workflow)

```powershell
# 1. Clone / locate the patched fork (already present at this path locally):
#    D:\Github\_Projects\_LEX\flexlibs2

# 2. Install GramTrans's own deps + the fork:
pip install -e D:/Github/_Projects/_LEX/flexlibs2
pip install -e .

# 3. Copy or symlink src/gramtrans/ into your FlexTools modules directory
#    (the path depends on your FlexTools install).
```

`pyproject.toml` declares `flexlibs2>=2.0`; the fork is installed manually until the
patches are upstreamed.

See [CLAUDE.md](CLAUDE.md#flexlibs2-fork-dependency) for the full patch inventory
(9 files modified in the fork) and the per-file change summary.

## Architecture

Per constitution v5.0.0 Principle II:

- **No `flavors/` adapter contract.** Module files (`gramtrans.py` entry + `Lib/*.py`
  helpers) import flexlibs2 directly.
- **LibLCM-direct implementation lives in a separate sibling repository**, not in this
  tree. The two repos share spec artifacts (spec.md, data-model.md, contracts/), not
  source.
- **Layout follows the FLExTrans module convention**: flat `gramtrans.py` entry file
  with `docs = {...}` + `MainFunction`, plus a `Lib/` sibling directory of helpers
  loaded via `site.addsitedir(r"Lib")`.

```
src/gramtrans/
├── gramtrans.py              # FlexTools entry: docs dict + MainFunction
└── Lib/                      # Helpers loaded via site.addsitedir
    ├── residue.py            # Import Residue tag (dual carrier)
    ├── closure.py            # Dependency-closure traversal
    ├── ws_mapping.py         # Writing-system mapping validation + materialization
    ├── selection.py          # Selection model
    ├── preview.py            # Plan builder (Preview Mode — never mutates)
    ├── transfer.py           # Plan executor (Move Mode)
    ├── report.py             # Run-report aggregation
    ├── categories.py         # Leaf-category transfer functions
    ├── categories_affixes.py
    ├── categories_templates.py
    ├── categories_msas.py
    └── ui/                   # PyQt widgets
        ├── main_window.py
        ├── target_picker.py
        ├── ws_mapping_dialog.py
        ├── affix_tree_picker.py
        └── stats_panel.py
```

## Phasing

- **Phase 0 (this repo, in progress)** — Additive transfer. Add new things
  unconditionally; duplicates allowed; new entries tagged in Import Residue.
- **Phase 1 (future)** — Overwrite. Match by GUID first, fingerprint second.
- **Phase 2 (future)** — Interactive merge.
- **Phase 3 (future sibling repo)** — LibLCM-direct re-implementation against raw LCM,
  re-using this repo's spec/plan/contracts artifacts.

See [constitution Principle IV](.specify/memory/constitution.md) for the full phasing
discipline.

## Live test projects

The Ejagham fixture pair (see [STATUS.md](STATUS.md) and
[tasks.md T014/T015](specs/001-phase0-additive-transfer/tasks.md)):

- **Source**: `Ejagham Mini` at `C:\ProgramData\SIL\FieldWorks\Projects\Ejagham Mini`
- **Target**: `Ejagham Full GT-Test` at `C:\ProgramData\SIL\FieldWorks\Projects\Ejagham Full GT-Test`
  (throwaway, restored from `backups/Ejagham Full.fwbackup` before each run)

Backups live at `backups/Ejagham Mini.fwbackup` and `backups/Ejagham Full.fwbackup`.

## License

TBD.
