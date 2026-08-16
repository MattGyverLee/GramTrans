# `build/` — packaging the standalone Windows application

Everything needed to turn the source tree into the two shipped artifacts of
feature [034](../specs/034-standalone-windows-app/). Normative contract:
[contracts/build-and-release.md](../specs/034-standalone-windows-app/contracts/build-and-release.md).

## Entry points

`build.py` is the only supported way to build. It takes exactly four forms
(contract §1):

| Command | Produces |
|---|---|
| `python build\build.py` | both artifacts |
| `python build\build.py --installer` | onedir + Inno Setup only |
| `python build\build.py --portable` | onefile only |
| `python build\build.py --lock` | regenerate `requirements.lock` |

Each of the first three runs the same seven ordered steps: fresh
`build\.venv-build` (any prior one deleted); `PYTHONNOUSERSITE=1` with
`PYTHONPATH`/`PYTHONHOME` cleared for every child; `pip install
--require-hashes --no-cache-dir -r build\requirements.lock`; stamp
`src\gramtrans\_buildinfo.py`; freeze via `gramtrans.spec`; smoke-test each
artifact; emit a per-artifact manifest.

A build that cannot satisfy the install step **from the lock alone** fails.
It never falls back to the build machine's environment (FR-042).

## Files

| File | Role |
|---|---|
| `requirements.lock` | hash-pinned, build-only dependency set (FR-019/FR-041) |
| `gramtrans.spec` | the single PyInstaller definition — one `Analysis`, two targets (FR-046) |
| `hiddenimports.py` | globs `src/gramtrans/Lib/**/*.py` into flat + package names (research R6) |
| `rthook_isolate.py` | PyInstaller runtime hook: scrub `PYTHON*` env, assert bundle prefix (FR-043) |
| `installer.iss` | Inno Setup over the onedir tree — the **supported** artifact |
| `smoke/run_smoke.py` | the eight post-build checks (FR-047/FR-048) |

## Artifacts

| Artifact | Kind | Support status |
|---|---|---|
| `GramTrans-Setup-<version>.exe` | installer | **supported** |
| `GramTrans-<version>.exe` | portable | best-effort |

An artifact whose smoke verdict is `FAIL` is not released. A failing
`portable` does not block the `installer` (FR-047, SC-010).
