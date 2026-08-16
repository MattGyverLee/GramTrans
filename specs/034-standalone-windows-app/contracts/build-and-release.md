# Contract: Build, Artifacts, and Release Gate

**Feature**: 034-standalone-windows-app | **Date**: 2026-08-16

---

## 1. Build entry point

```
python build\build.py                 # both artifacts
python build\build.py --installer     # onedir + Inno Setup only
python build\build.py --portable      # onefile only
python build\build.py --lock          # regenerate requirements.lock
```

`build.py` MUST, in order:

1. Create a **fresh** venv under `build\.venv-build`, deleting any prior one.
2. Set `PYTHONNOUSERSITE=1` and clear `PYTHONPATH` / `PYTHONHOME` for every
   child process.
3. `pip install --require-hashes --no-cache-dir -r build\requirements.lock`.
   No other install source, no `-e`, no fallback to the machine's environment
   (FR-042).
4. Stamp `src\gramtrans\_buildinfo.py` from `git describe --tags --always
   --dirty` + short SHA + ISO timestamp (FR-049). Gitignored.
5. Run PyInstaller against `build\gramtrans.spec` for the requested targets.
6. Run `build\smoke\run_smoke.py` against each produced artifact.
7. Emit a manifest per artifact: kind, support status, source commit, smoke
   verdict, and the resolved component/version list.

A build that cannot satisfy step 3 from the lock alone **fails**; it does not
fall back.

## 2. Single packaging definition (FR-046)

`build\gramtrans.spec` holds exactly one `Analysis`, feeding both a `COLLECT`
(onedir) and a onefile `EXE`. Divergence between the two artifacts' contents is
a defect.

| Artifact | Kind | Support status | Produced by |
|---|---|---|---|
| `GramTrans-Setup-<version>.exe` | installer | **supported** | Inno Setup over the onedir tree; Start Menu entry + uninstaller |
| `GramTrans-<version>.exe` | portable | best-effort | onefile `EXE` |

`hiddenimports` is **generated**, not hand-listed: `build\hiddenimports.py`
globs `src/gramtrans/Lib/**/*.py` and emits each module under both its flat
top-level name and its `gramtrans.Lib.…` package name (research R6). A new
helper module therefore needs no build-file edit — and a hand-maintained list
would silently rot, which is the failure this generation exists to prevent.

`build\rthook_isolate.py` runs as a PyInstaller runtime hook before any
application import: scrub `PYTHONPATH` / `PYTHONHOME` / `PYTHONSTARTUP` from
`os.environ`, assert `sys.prefix` is inside the bundle, and fail with a clear
message rather than a traceback (FR-043, SC-009).

## 3. Dependency lock (FR-019, FR-041)

- `build\requirements.lock` — fully pinned, `--generate-hashes`, checked in.
- Roots: `pyflexicon`, `PyQt6`, `flextoolslib`, `pyinstaller`.
- `flextoolslib` drags in `flexlibs` (stock flexlibs1) and `cdfutils`
  transitively. They are inert at runtime but **are** shipped components, and so
  fall under the FR-053 amendment's "components it bundles" clause and the
  FR-052 licence statement.
- `pyproject.toml` is **not** edited. Its `pyflexicon>=4.3.1` and `PyQt6>=6.4`
  floors stay floors, so FlexTools installs are unconstrained by this feature.

## 4. Smoke test (FR-047, FR-048)

`build\smoke\run_smoke.py <artifact-path>` runs the same checks against either
artifact and returns `0` / non-zero:

| # | Check | Requirement |
|---|---|---|
| 1 | The application starts and exits cleanly | FR-048 |
| 2 | `--self-check` returns `PASS` on a machine with FieldWorks present | FR-048 |
| 3 | The project list is populated (≥1 project enumerated) | FR-048 |
| 4 | The no-interface fallback is unreachable: PyQt6 imports and a `QApplication` constructs inside the bundle; `DEFAULT_SOURCE_PROJECT` never appears in any output | FR-048, FR-005, FR-006 |
| 5 | A Preview against a known project pair produces the expected result, and the target is byte-for-byte unchanged before and after | FR-048, SC-004 |
| 6 | Every locked component is present in the bundle at exactly the locked version | US3-2 |
| 7 | No FieldWorks or LibLCM assembly is bundled | FR-045 |
| 8 | No flat-name collision: no bundled third-party distribution provides a top-level module whose name matches one of ours | research R6 |

**Release rule**: an artifact whose smoke verdict is `FAIL` is not released. A
failing `portable` MUST NOT block the `installer` (FR-047, SC-010).

## 5. Regression gate (FR-021, SC-012)

`.github/workflows/regression.yml` — the repository's first workflow — runs on
**every push to the feature branch**, not at release:

1. `pytest -m "not integration"` — the existing suite must stay green (SC-011).
2. FlexTools-path contract check (`tests/unit/test_034_flextools_contract.py`):
   - `import gramtrans.gramtrans` succeeds;
   - `docs` carries all six `FTM_*` keys with their current values;
   - `MainFunction` accepts three positional arguments, and
     `confirmation_gate` is keyword-only with default `None`;
   - the default gate's `confirm()` returns `True` with no UI and no I/O;
   - the default gate's `finish_page_subtitle()` equals today's literal;
   - nothing under `gramtrans.py` or `Lib/` imports `gramtrans.standalone`
     (FR-016), checked by AST scan over the import statements.
3. The shared-code exception check: the set of files modified under
   `src/gramtrans/Lib/` and `src/gramtrans/gramtrans.py` on this branch must be
   a subset of the plan's enumerated exception list (SC-014).

Live-LCM integration tests are **not** in this gate — a hosted runner has no
FieldWorks. They run locally against the `Ejagham Mini` → `Ejagham Full GT-Test`
pair and are the evidence for US1's parity scenario (SC-002).

## 6. Release documentation (FR-051, FR-052)

The release notes MUST state:

- that the artifact is **unsigned**, what the resulting SmartScreen / antivirus
  warning looks like, and how to proceed — until code signing is arranged;
- the licence under which the **binary** is distributed, which is stricter than
  the project's own MIT source licence because of bundled components (PyQt6 is
  GPL-or-commercial; flextoolslib pulls flexlibs1 and cdfutils);
- the prerequisite: FieldWorks 9, installed by the user, never bundled (FR-045);
- that the target project must be closed in FLEx **even for a Preview**
  (FR-030);
- that a Move **cannot be undone from within the application**, with the backup
  and Send/Receive recovery guidance (FR-027, FR-054).
