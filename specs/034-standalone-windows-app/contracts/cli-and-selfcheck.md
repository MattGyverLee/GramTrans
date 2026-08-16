# Contract: Application Surface and Self-Check Output

**Feature**: 034-standalone-windows-app | **Date**: 2026-08-16

---

## 1. Command line

```
GramTrans.exe                 launch the application
GramTrans.exe --self-check    print the prerequisite report and exit
GramTrans.exe --version       print the stamped version and exit
```

`--self-check` and `--version` are the **only** accepted flags. There is no
`--source`, no `--target`, no `--move`, no `--preview`, no read-only switch
(FR-011); the developer harness's `--source` / `--move` toggles are deliberately
not carried over. Any other argument is an error naming the two valid flags.

The self-check is also reachable from **Help → Self-check…** in the running
application, which is the route that matters for the users FR-036 is written for
(research R12). Both routes render the same block.

Exit codes: `0` self-check passed / normal exit; `1` self-check failed;
`2` invalid arguments.

## 2. Self-check output

One plain-text block, copyable and savable as a unit (FR-037), no colour, no box
drawing, ASCII only. Line prefixes are `[PASS]`, `[FAIL]`, `[UNKNOWN]`.

```
GramTrans self-check
  Application version : 0.1.0+g1a2b3c4 (built 2026-08-16T14:22:05Z)
  Generated           : 2026-08-16T14:31:57

[PASS] FieldWorks installed
         detected: C:\Program Files\SIL\FieldWorks 9\
         expected: a directory containing FieldWorks.exe
[PASS] FieldWorks version
         detected: 9.3.10.1
         expected: major version 9
[PASS] FieldWorks projects location
         detected: C:\ProgramData\SIL\FieldWorks\Projects\
         expected: an existing directory
[PASS] Language-model runtime
         detected: initialised (pythonnet 3.0.5, .NET Framework 4.8)
         expected: initialises without error
[PASS] UI toolkit
         detected: PyQt6 6.7.1
         expected: importable and constructible
[PASS] Bundled components
         detected: pyflexicon 4.3.1, PyQt6 6.7.1, pythonnet 3.0.5,
                   flextoolslib 2025.8.26
         expected: the versions in build/requirements.lock
[PASS] Log location
         detected: C:\Users\<user>\AppData\Local\GramTrans\logs
         expected: writable

VERDICT: PASS (7 of 7)
Log file: C:\Users\<user>\AppData\Local\GramTrans\logs\gramtrans-GT-20260816-143157.log
```

A `[FAIL]` line MUST be followed by a `remedy:` line naming the concrete next
step — install FieldWorks 9, close the project in FLEx, and so on (FR-036,
SC-006). No check may fail without one.

**Reading rule (normative)**: every FieldWorks value is read from the
`flexicon.code.FLExGlobals` **module attribute**, at call time, after
`FLExInitialize()`, and through `standalone/fwglobals.py` — which is the only
module permitted to name those symbols (`tests/unit/test_034_fwglobals_only.py`
enforces it in the regression gate).

Research R1 justified this by predicting the `flexicon.FWProjectsDir` /
`flexicon.FWCodeDir` re-exports stay `None`. **They do not**: measured on
flexicon 4.3.1 they are populated before `FLExInitialize()` is called, because
`InitialiseFWGlobals()` runs at import scope. The rule is unchanged — the
re-exports are snapshots bound once at package import, and the accessor is what
makes the FR-031 / FR-033 split enforceable — but the failure it guards against
is staleness, not `None`. What R1 got backwards matters more: on a machine
without FieldWorks, `import flexicon` **raises**, so the FieldWorks-missing
check happens at the import, not at the initialise. See
[probe-results.md](../probe-results.md) §T012.

A FieldWorks value that reads back `None` or empty after initialisation is
reported as the **language-model runtime** failure (FR-033), never as
"FieldWorks is not installed" (FR-031).

## 3. Prerequisite failure messages (FR-031 to FR-034)

Each is a plain-language modal, never a traceback, and each names the log file.

| Condition | Message shape |
|---|---|
| FieldWorks not installed | "GramTrans needs FieldWorks 9, which does not appear to be installed on this computer. Install FieldWorks 9 and run GramTrans again." |
| Unsupported FieldWorks version | "This computer has FieldWorks `<detected>`. GramTrans supports FieldWorks `<supported range>`." Then stop. |
| Language-model runtime failed | Names the component that failed, points at Help → Self-check and the log file path. |
| Target locked | Names **which** project is locked and that it must be closed in FLEx. No raw `TargetUnavailable` text (FR-029). |
| One project cannot be opened | Attributed to that project by name; the picker stays usable and other projects remain selectable (FR-034). |
| Project needs a data-model migration | Told **before** anything proceeds; the application does not migrate as a side effect (FR-035). `flexicon` raises `FP_MigrationRequired`, which the shell catches by type. |

## 4. Log file

- Path: `%LOCALAPPDATA%\GramTrans\logs\gramtrans-<run_id>.log`, one per run,
  retained across runs (FR-038).
- `<run_id>` is the same `GT-<YYYYmmdd-HHMMSS>` string as the run's Import
  Residue tag, so FR-026's "identify the run so its residue tag can be searched
  in FLEx" is one instruction, not two.
- The path is shown in the application (status bar and the report view's header)
  and repeated in the self-check block.
- Content is the report sink's stream plus prerequisite results and exception
  detail. It MUST NOT carry project content beyond what identifies the objects
  in the run — GUIDs and short summaries, which is what the engine's report lines
  already emit (FR-039).

## 5. Partial-failure reporting (FR-026)

When a Move fails partway, the application states, in one message:

1. that the target **may be partially modified**;
2. the `run_id`, described as the tag to search for in FLEx's Import Residue;
3. the full path to the log file.

It MUST NOT offer, imply, or document a rollback (FR-027).
