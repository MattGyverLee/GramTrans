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
