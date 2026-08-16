# Probe results — 034 Standalone Windows Application

Evidence recorded against the tasks that require it. Each entry states what was
run, on what, and what it means for the plan.

**Machine**: Windows 11 Pro 10.0.26200, FieldWorks 9.3.10.1448 (64-bit) at
`C:\Program Files\SIL\FieldWorks 9\`, projects at
`C:\ProgramData\SIL\FieldWorks\Projects\`, LibLCM 11.0.0, Python 3.12.7.

---

## T011 — packaging spike: pythonnet under PyInstaller (research R7)

**Date**: 2026-08-17 · **Verdict**: **PASS** — the R7 risk is retired; Phase 5
proceeds as planned.

### What was run

A throwaway program (`spike_open.py`) doing nothing but the shell's startup
sequence: `import flexicon`, `FLExInitialize()`, `AllProjectNames()`, open one
project read-only, read one fact from it, `CloseProject()`, `FLExCleanup()`.

Built in a **fresh venv** (`python -m venv`, no access to the machine's
Anaconda environment) holding only what `pip install pyinstaller
D:/Github/_Projects/_LEX/flexicon` resolved:

| Component | Version |
|---|---|
| pyinstaller | 6.22.1 |
| pyinstaller-hooks-contrib | 2026.6 |
| pyflexicon | 4.3.1 |
| pythonnet | 3.0.5 |
| clr_loader | 0.2.10 |

Frozen with `pyinstaller --onedir --console`, then the produced `.exe` was run.

### Result

Both the unfrozen script and the frozen `dist/spike_open/spike_open.exe`
printed `VERDICT: PASS`, with identical values:

```
[spike] frozen      : True
[spike] sys.prefix  : ...\dist\spike_open\_internal
[spike] pre-init  G.FWCodeDir     : 'C:\\Program Files\\SIL\\FieldWorks 9\\'
[spike] FLExInitialize() OK
[spike] post-init G.FWShortVersion: '9.3.10'
[spike] AllProjectNames() count   : 84
[spike] opened project            : Ejagham Mini
[spike] lexicon entry count       : 252
[spike] CloseProject() OK
[spike] FLExCleanup() OK
```

### `clr_loader` native collection behaviour (the specific R7 question)

`pyinstaller-hooks-contrib` collects the native payload with **no
configuration on our part**. Present in the bundle:

```
_internal/clr_loader/ffi/dlls/amd64/ClrLoader.dll
_internal/clr_loader/ffi/dlls/x86/ClrLoader.dll
_internal/pythonnet/runtime/Python.Runtime.dll
```

**No `.runtimeconfig.json` is collected, and none needs to be.** No such file
exists anywhere in `clr_loader` 0.2.10 or `pythonnet` 3.0.5 as installed —
`.runtimeconfig.json` is a .NET **Core**/5+ (`coreclr`) hosting artifact, and
this stack does not use `coreclr`. Measured at runtime:

```
FRAMEWORK: .NET Framework 4.8.9337.0
RUNTIME  : .NET Framework
```

R7's concern about runtimeconfig collection is therefore moot for the netfx
path flexicon takes. `build/gramtrans.spec` (T041) needs no special handling
for it; the smoke test (T045) should still assert the two `ClrLoader.dll`
files and `Python.Runtime.dll` are present, since their absence is what a
hook regression would look like.

### Two incidental findings that matter downstream

**FR-045 is satisfied by construction.** No FieldWorks or LibLCM assembly
appears anywhere in the bundle (`find` for `SIL.*`, `*LibLCM*`, `FieldWorks*`,
`FwUtils*` returns nothing). `clr.AddReference` resolves them at runtime from
the `sys.path` entry `InitialiseFWGlobals()` appends. T045 check 7 should stay
in the smoke test as a regression guard, but nothing has to be *done* to make
it pass.

**PyInstaller emits 62 "missing module" warnings, and they are all benign.**
They name CLR namespaces — `SIL.FieldWorks`, `SIL.LCModel`, `SIL.WritingSystems`,
`System`, `System.Reflection`, `Microsoft` — which pythonnet resolves at
runtime and PyInstaller's static analysis cannot see. Recording this because
it is exactly the noise that would hide a *real* missing import in a later
build: `warn-gramtrans.txt` should be diffed against this expected set rather
than eyeballed.

**Size**: 25 MB onedir, without PyQt6.

---

## T056 — final success-criteria sweep (SC-001 .. SC-014)

**Date**: 2026-08-17. One row per criterion, each pointing at the evidence
rather than restating the claim. Two criteria are **not measurable by the
implementer** and say so plainly rather than being marked green.

| # | Verdict | Evidence |
|---|---|---|
| SC-001 | **NOT MEASURED** | "Download to completed preview in under 10 minutes, unassisted" is a user-observation criterion and needs a real user who has not seen this before. What exists to support it: the installer produces a Start Menu entry, the source chooser is the first screen after the prerequisite checks, and `build/RELEASE-NOTES.md` covers the SmartScreen warning that is the most likely place a first-time user stalls. **Owner action before release.** |
| SC-002 | **PASS** | §T029. Identical plan fingerprints (16 actions / 0 skips), identical `RunReport` counts and identical 83-name candidate lists from a FlexTools-shaped stub and a `HostSession` stub over the same selection, live against `Ejagham Mini` → `Ejagham Full GT-Test`. |
| SC-003 | **PASS** | `tests/integration/test_034_move_gate_live.py`, driving the real `_PageFinish`: a Move reaches `gt_api.execute_move` only after `confirm()` returned `True`, in that order; a refusal writes nothing; Preview never consults the gate. Plus the near-miss table in `test_034_standalone_gate.py`. |
| SC-004 | **PASS** | §T029 (target `.fwdata` sha256 identical before and after both hosts' Preview runs) and smoke check 5, re-verified on every build. |
| SC-005 | **PASS** | §T029. The source's `.fwdata.lock` is absent after normal close, a doubled `release()`, a mid-run failure, and the context-manager exit; a fresh subprocess re-opens the project write-enabled. |
| SC-006 | **PASS** | Enforced in the type, not in review: `PrerequisiteCheck.__post_init__` refuses to construct a `FAIL` without a non-empty remedy (`tests/unit/test_034_prereq_report.py`). Every prerequisite failure maps to a plain-language message in `standalone/errors.py`, dispatched **by exception type** so the FR-031/FR-033 split cannot be got wrong by a string match. |
| SC-007 | **NOT MEASURED** | "90% of support cases resolved without a round-trip" needs real support cases. What exists: the self-check names the failing prerequisite, its detected and expected values, and a concrete remedy; it is reachable from Help → Self-check… as well as `--self-check`; and every message carries the log-file path. Re-assess after the first support cases. |
| SC-008 | **PASS** | §T047. Two builds of commit `80baab1`, identical 18-component sets, `built_at` the only differing manifest field. |
| SC-009 | **PASS** | Measured. The frozen `GramTrans.exe` run with `PYTHONPATH`, `PYTHONHOME` and `PYTHONSTARTUP` all pointing at a directory containing hostile `api.py`, `models.py`, `report.py`, `preview.py`, `selection.py`, `transfer.py`, `texts.py` (each raising on import) and a `startup.py` that prints. Result: `[GramTrans] Ignoring environment variable(s) from the host system: PYTHONPATH, PYTHONHOME, PYTHONSTARTUP`, then `VERDICT: PASS (9 of 9)`. No hostile module imported, `PYTHONSTARTUP` never executed. This is the flat-name shadowing risk of research R6/R9, shown contained. |
| SC-010 | **PASS (mechanism)** | `build.py` step 7: a `FAIL` verdict blocks that artifact, and a failing `portable` returns 0 with a warning so it cannot block the `installer`. No release has been published, so there is nothing to violate yet; the rule is in code rather than in a checklist. |
| SC-011 | **PASS, with a caveat stated** | The suite does not regress: 2164 passed, 27 failed — and those 27 fail identically on a clean `main` (features 026/029 plus one wizard test, none related to this feature). They are pinned in `.github/known-failures.txt` and the gate fails on any *new* failure **and** on any baseline entry that starts passing. SC-011 as literally worded ("the existing suite passes") was **already false before this feature began**; see the note below. |
| SC-012 | **PASS (locally), UNVERIFIED in CI** | Every commit on this branch was gated locally against all four steps before being made. The workflow itself has **never executed on GitHub** — the branch has not been pushed and this repository had no Actions history. **Owner action: push the branch and confirm the workflow goes green** before treating SC-012 as measured. |
| SC-013 | **PASS** | `tests/unit/test_034_flextools_contract.py`: `MainFunction` keeps its three positional parameters, both new parameters are keyword-only with defaults, the `docs` dict is unchanged, the wizard's leading parameters are unmoved, and the Finish-page subtitle with no gate supplied is byte-identical to the pre-feature literal. The default gate returns `True` with no dialog and no I/O, proven in a subprocess with PyQt6 blocked at the meta-path. |
| SC-014 | **PASS** | Five shared files changed — `Lib/api.py`, `Lib/gate.py`, `Lib/ui/selection_wizard.py`, `Lib/ui/target_picker.py`, `gramtrans.py` — and `.github/scripts/check_shared_exceptions.py` confirms all five are in the plan's exception table. The check is a gate step, so a sixth would fail the build. |

### The SC-011 caveat, stated rather than buried

SC-011 says "the existing test suite passes". It did not pass when this feature
started: 27 tests under features 026 (texts/wordforms) and 029 (sense pictures),
plus one wizard POS-closure test, fail on a clean checkout of `main` at commit
`c2e1101`. Fixing them is another feature's work.

A gate whose first step is red from commit one enforces nothing and gets
ignored, so the gate enforces the enforceable thing instead: **no new failure,
and no silent rot**. `.github/scripts/check_suite_baseline.py` fails on any
failure outside the baseline *and* on any baseline entry that starts passing,
so the list can only shrink and only deliberately.

The substantive half of SC-011 — "the FlexTools-hosted module produces
identical results before and after this feature" — is what
`test_034_flextools_contract.py` and the §T029 parity run establish, and both
are green.

### Not done, and blocking release

* **T054 landed** (constitution v8.0.0), so the governance blocker is cleared.
* **Inno Setup is not installed on this machine**, so the *supported* artifact
  (`GramTrans-Setup-<version>.exe`) has never been produced. The onedir program
  it wraps is fully verified; the wrapper is not.
* **SC-012 is unverified in CI** — see the table.
* **SC-001 and SC-007 need a person**, not a test.

---

## T047 — SC-008: two builds of one commit, identical dependency sets

**Date**: 2026-08-17 · **Verdict**: **PASS**.

`python build\build.py` run twice against a clean checkout of commit
`80baab1`, both producing both artifacts and both smoke-testing them.

```
A  version 80baab1  commit 80baab1  built 2026-08-16T23:20:38Z   smoke PASS
B  version 80baab1  commit 80baab1  built 2026-08-16T23:24:39Z   smoke PASS

components identical      : True  (18 entries)
differing components      : none
manifest fields differing : ['built_at']
```

`built_at` is the wall clock and is expected to differ; it is the only field
that does. The 18-component set — `pyflexicon 4.3.1`, `PyQt6 6.7.1`,
`PyQt6-Qt6 6.7.3`, `pythonnet 3.0.5`, `clr-loader 0.2.10`, `flextoolslib
2026.5.5`, `flexlibs 1.2.8`, `cdfutils 1.1.2` and the rest — is byte-identical
between the two runs, which is what SC-008 asks for. The mechanism is the fresh
venv plus `--require-hashes --no-cache-dir`: run B deleted run A's venv and
re-resolved from the lock alone.

## T042 / T045 / T046 — the release build and its smoke verdicts

**Date**: 2026-08-17 · **Verdict**: **PASS** for both artifacts.

```
GramTrans.exe (onedir / installer, SUPPORTED)      VERDICT: PASS (8 of 8, 0 skipped)
  1 starts and exits cleanly            PASS
  2 --self-check returns PASS           PASS
  3 project list populated              PASS   84 projects
  4 no-interface fallback unreachable   PASS
  5 Preview; target unchanged           PASS   sha256 13c5a96fba560ae8... unchanged
  6 locked components at locked vers.   PASS   11 runtime components
  7 no FieldWorks/LibLCM assembly       PASS
  8 no flat-name collision              PASS

GramTrans-portable.exe (onefile, best-effort)      VERDICT: PASS (5 of 8, 3 skipped)
  6, 7, 8 SKIP — a onefile artifact has no inspectable tree until it unpacks
  at runtime. Reported as SKIP, never counted as a pass. This is part of why
  the portable build is best-effort rather than supported.
```

**Inno Setup is not installed on this machine**, so `GramTrans-Setup-<version>.exe`
was not produced; `build.py` reports that and continues. The onedir program the
installer wraps is fully verified. A release build must run where ISCC.exe is
available.

### Four defects the first two real builds found

Recorded because none of them was visible from reading the code, and three
would have shipped.

**1. PyQt6 6.11.0 does not load on this platform at all.**
`ImportError: DLL load failed while importing QtCore: The specified procedure
could not be found.` Measured in a clean venv **unfrozen**, so not a packaging
fault; and with the matched `PyQt6-Qt6 6.11.0` as well as the `6.11.1` that
PyQt6's own too-loose pin (`>=6.11.0,<6.12.0`) resolves to — so not a version
mismatch either. Qt 6.11 appears to need a platform component this machine
lacks. `requirements.in` now carries a `<6.8` ceiling with the measurement
written beside it and locks `6.7.1`/`6.7.3`, the versions every unit test and
every live parity run in this feature actually used. `pyproject.toml` keeps its
`PyQt6>=6.4` floor: the ceiling constrains the **artifact**, not FlexTools
installs.

**2. PyInstaller does not collect `.dist-info` metadata by default.**
`importlib.metadata.version()` therefore raised inside the bundle and the
self-check reported *"Bundled components: none found"* on a perfectly good
artifact — precisely the false negative FR-036 exists to prevent, and visible
only in a frozen build. The spec now calls `copy_metadata()` for all eleven
runtime distributions.

**3. Smoke check 6 was asking for something impossible.** It demanded every
*locked* component be present in the bundle, but the lock's roots include
`pyinstaller` — the freezer cannot ship inside its own output. Split into an
explicitly enumerated `BUILD_ONLY` set (enumerated rather than inferred, so a
new runtime dependency cannot be silently absorbed as build-only), and the
check now also fails if a build-only distribution *leaks into* the artifact.
Its `dist-info` version parse was separately wrong — it produced `"1.1.2.dist"`
— and generated a screen of spurious mismatches.

**4. Smoke check 7 raised a false FR-045 alarm.** Its `icu*.dll` pattern
flagged the bundle's `icudt73.dll` / `icuuc.dll`, which come from the build
machine's Python distribution (ICU 73). FieldWorks ships ICU **68**
(`icudt68.dll`, `icuuc68.dll`), so those files have nothing to do with it. The
pattern is now the versioned FieldWorks names plus the managed `SIL.*` /
`icu.net` / `ICU4NET` assemblies. **No FieldWorks or LibLCM assembly is
bundled** — confirmed, and it falls out for free because `clr.AddReference`
resolves them at runtime from the `sys.path` entry flexicon appends.

### And one the regression gate caught in our own test

After a build has run, `test_034_fwglobals_only.py` was walking into
`build/.venv-build/Lib/site-packages/` and failing on flexicon, flexlibs and
flextoolslib reading their own FieldWorks globals — which is their job. The
scan now excludes generated and vendored trees by name; `build/*.py` is still
covered. Worth recording as evidence the gate works on the person who wrote it.

---

## T029 — US1 live parity, `Ejagham Mini` → `Ejagham Full GT-Test` (SC-002, SC-004, SC-005)

**Date**: 2026-08-17 · **Verdict**: **PASS**.

`tests/integration/test_034_standalone_preview_live.py` — 4 passed. Numbers
from the same run, captured directly:

```
projects_root (FWProjectsDir) : C:\ProgramData\SIL\FieldWorks\Projects\
FieldWorks                    : 9.3.10 | Version: 9.3.10.1448  2026-07-09 (64 bit)

path A  (FlexTools-shaped stub)   stub.projects_root = ''
        candidates=83  actions=16  skips=0
        per-category (added, skipped) = affix_templates (7, 0), slots (9, 0)

path B  (HostSession stub)        stub.projects_root = 'C:\ProgramData\SIL\FieldWorks\Projects\'
        candidates=83  actions=16  skips=0
        per-category (added, skipped) = affix_templates (7, 0), slots (9, 0)

PLAN FINGERPRINTS EQUAL   : True      (16 actions compared by category+GUID+summary)
REPORT COUNTS EQUAL       : True
CANDIDATE LISTS EQUAL     : True      (83 names, identical)
SOURCE OFFERED AS TARGET  : False     (US1 acceptance scenario 3)
```

**SC-002 (parity)**: the two hosts planned the identical transfer. The *only*
input that differed is `projects_root` — empty on the FlexTools path, so
`list_target_candidates` walked its historical
`C:\ProgramData\SIL\FieldWorks\Projects` literal; registry-derived on the
standalone path. On this machine those resolve to the same directory, which is
why the candidate lists match exactly; a relocated install is what the
injection exists for, and is covered by unit test
`test_034_projects_root_injection.py`.

**SC-004 (a Preview writes nothing)**: `Ejagham Full GT-Test.fwdata` sha256

```
before : 13c5a96fba560ae86b29893798f5bcf1cd0d631d19d36f50bef9a1ecfad74c7f
after  : 13c5a96fba560ae86b29893798f5bcf1cd0d631d19d36f50bef9a1ecfad74c7f
```

byte-for-byte identical across both hosts' Preview runs.

**SC-005 (both projects released)**: the source's `.fwdata.lock` is absent
after every exit path tested — normal close, a doubled `release()`, a failure
between bind and release, and the context-manager exit — and a **fresh
subprocess** re-opened the source write-enabled afterwards.

### Two measurement notes that changed the implementation

**Re-opening write-enabled in-process is not a valid release check.** The
first version of the SC-005 test re-opened the source with `writeEnabled=True`
after `release()` and failed. A fresh process opens the same project
write-enabled without complaint, and the `.fwdata.lock` file is gone — so
nothing was leaked. LCM keeps per-process state that refuses a second
write-open of an already-used project. The test now checks the lock file
(process-independent, and exactly what "FLEx can open it again" means) plus a
subprocess re-open.

**`FLExCleanup()` is process-global.** A second call throws
`System.InvalidOperationException: The SLDR has not been initialized` from
`Sldr.Cleanup()`. Production runs one session per process, so this never
fires there — but it is why `HostSession.release()` wraps the call in
try/except rather than letting it propagate through the one code path that
must always complete.

**Unrelated noise, recorded so nobody chases it**: pytest reports
`Windows fatal exception: access violation` on any run that touches flexicon.
It is pre-existing and nothing to do with this feature — a bare
`python -c "import faulthandler; faulthandler.enable(); import flexicon;
flexicon.FLExInitialize()"` reproduces it with no GramTrans code loaded. It is
faulthandler observing an access violation the CLR handles internally; exit
code is 0 and every test passes.

---

## T012 — research R1 is wrong for flexicon 4.3.1 (correction)

**Date**: 2026-08-17 · **Verdict**: the predicted trap does **not** exist; a
different, more consequential one does.

R1 states that `flexicon/__init__.py` binds `FWCodeDir`, `FWProjectsDir`,
`FWExecutable`, `FWShortVersion` and `FWLongVersion` at package-import time,
before `FLExInitialize()` runs, so the package re-exports are `None` and stay
`None` — and that a self-check reading them would report "FieldWorks not
detected" on a healthy machine.

**Measured on flexicon 4.3.1** (both in the machine environment and in the
spike's clean venv):

```
pre-init flexicon.FWCodeDir      = 'C:\\Program Files\\SIL\\FieldWorks 9\\'
pre-init flexicon.FWProjectsDir  = 'C:\\ProgramData\\SIL\\FieldWorks\\Projects\\'
pre-init flexicon.FWShortVersion = <System.Version object ...>
flexicon.FWCodeDir is flexicon.code.FLExGlobals.FWCodeDir  ->  True
```

The re-exports are populated **before** `FLExInitialize()` is called. Why:

- `flexicon/code/FLExInit.py` calls `FLExGlobals.InitialiseFWGlobals()` at
  **module scope** — line 44, indentation 0 — so it runs on *import*, not on
  `FLExInitialize()`.
- `flexicon/__init__.py` imports `.code.FLExInit` (char 3575) **before**
  `.code.FLExGlobals` (char 3644), so the globals are already rebound by the
  time the re-exports are taken.

### The real trap, which R1 inverted

`InitialiseFWGlobals()` **raises** when the registry key is absent
(`GetFWRegKey()` → `Exception("... FieldWorks 9 not found")`) or when
`FieldWorks.exe` is not under the code directory, and **nothing guards the
call**. So on a machine without FieldWorks:

> `import flexicon` itself raises. `FLExInitialize()` is never reached.

That reverses the contract's assumed detection point. **FR-031 ("FieldWorks is
not installed") must be detected around the `import`, not around the
initialise** — which is what `standalone/fwglobals.probe()` does. Contract
[host-shell.md](contracts/host-shell.md) §6 step 2 and
[cli-and-selfcheck.md](contracts/cli-and-selfcheck.md) §2's reading rule have
been corrected to match.

### What T012 keeps, and why

The accessor and its AST ban are kept in full, for reasons that survive the
correction:

1. The re-exports are **snapshots**. They are correct today only because
   nothing re-runs `InitialiseFWGlobals()`. Reading the module attribute at
   call time is correct under both the observed and the predicted behaviour.
2. Funnelling every read through one module is what lets the FR-031 / FR-033
   split be stated once and enforced. A `None` read post-init raises
   `FieldWorksRuntimeUnavailable` (FR-033, "the runtime did not come up"), never
   `FieldWorksNotDetected` (FR-031, "install FieldWorks") — so even a total
   bypass produces an honest failure rather than a lie about the user's machine.
3. `tests/unit/test_034_fwglobals_only.py` makes it a CI failure rather than a
   review habit, and it guards phases 3–6 as they are written.

The upstream fix R1 suggested (a PEP 562 `__getattr__` in `flexicon/__init__.py`)
is **not** needed for the re-export staleness, but a related upstream
improvement is worth filing: `InitialiseFWGlobals()` at import scope means a
library import can fail for an environmental reason, which is hostile to any
caller that wants to *detect* rather than *crash*. Neither affects this
feature, which works against the declared `pyflexicon>=4.3.1` floor as-is.
