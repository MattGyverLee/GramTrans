# Cycle 1 Explore -- fullsweep fidelity ground truth

> Provenance note: authored by the Explore agent, which runs in enforced
> read-only mode; the main session persisted this content verbatim from the
> agent's report.

## 1. PROJECT INVENTORY

Root: `C:\ProgramData\SIL\FieldWorks\Projects` (95 directories). Registry
`HKLM:\SOFTWARE\SIL\FieldWorks\9\ProjectsDir` = that same path; `RootDataDir` empty.
No second projects root exists (`C:\ProgramData\SIL\FieldWorks` holds only
`Projects` and `DownloadedUpdates`).

Totals: 95 dirs, **84 have `<name>.fwdata`**, 11 are empty shells (only
`SharedSettings`, no fwdata -- these are NOT transferable projects).
Sum of all `.fwdata` = **1761 MB**, median 7.58 MB.
Two loose files sit in the root: `cleandub.xsl`, `keepdub.xsl`, plus
`Sichuan Yi old.fwdata.old` (88.6 MB, a stray orphan).

Table sorted by size (MB of `<name>.fwdata`), locks noted:

| Project | MB | fwdata mtime | lock | role |
|---|---|---|---|---|
| Esperanto | 179.54 | 2026-03-06 23:25 | - | known-good test src |
| blx-flex | 97.08 | 2023-08-08 05:49 | - | |
| Yi Sichuan | 89.21 | 2026-03-26 23:22 | - | |
| Tlachichilco Tepehua-Speedtest | 77.40 | 2024-09-03 01:00 | - | |
| Tlachichilco Tepehua-NT Noparse | 77.40 | 2024-08-28 03:19 | - | |
| Ngoreme | 76.85 | 2026-08-11 16:49 | - | |
| Tlachichilco Tepehua | 74.13 | 2024-08-12 18:38 | - | |
| Tlachichilco Tepehua-NT orthography | 73.69 | 2026-01-20 20:57 | - | |
| Ngoreme Johnny | 73.62 | 2023-08-17 09:47 | - | |
| Xinaliq | 68.60 | 2024-08-12 16:40 | - | |
| Quechua qxh | 67.16 | 2024-08-22 08:42 | - | |
| Claude-Swahili | 56.54 | 2026-08-17 17:13 | - | |
| Sena 3 | 53.33 | 2026-08-16 19:52 | - | |
| Sena_InterlinearTraining | 52.09 | 2026-07-01 23:15 | - | |
| Naami dub | 33.71 | 2024-02-07 13:27 | - | |
| Nchani | 32.40 | 2023-03-07 13:39 | - | |
| Isenye Nora | 27.62 | 2023-08-09 19:00 | - | |
| Mbugwe Lizzie | 21.23 | 2026-02-26 09:21 | - | pilot src (done) |
| Ejagham Full | 17.62 | 2026-08-10 19:19 | **YES** | large, flagged in manifest |
| SwissGerman | 16.90 | 2025-05-09 07:57 | - | |
| Hdi | 16.14 | 2024-09-25 21:54 | - | |
| Nomaande | 15.85 | 2024-02-06 13:26 | - | |
| Mbugwe LizzieHC parsecrash | 14.17 | 2025-07-01 20:57 | - | |
| IndonesianHC-Start | 11.89 | 2025-07-17 19:16 | - | |
| Test | 11.42 | 2026-08-16 17:17 | - | disposable fixture |
| EjaghamCfgSrc | 11.19 | 2026-07-16 23:36 | - | fixture src |
| Ejagham Mini | 11.19 | 2026-07-03 21:30 | **YES** | known-good test src |
| Ejagham025Src | 11.19 | 2026-07-18 08:30 | **YES** | fixture src |
| Ejagham029Src | 11.19 | 2026-07-20 04:13 | - | fixture src |
| IndonesianHC-Complete | 11.04 | 2024-07-30 09:22 | - | |
| IndonesianHC | 10.99 | 2026-08-16 20:46 | - | |
| Indonesian-preclean | 10.94 | 2025-07-17 19:20 | - | |
| Aweti | 10.80 | 2026-08-16 17:17 | - | |
| Mbugwe LizzieHC practice | 10.60 | 2024-08-22 17:24 | **YES** | the REAL HCPractice project |
| Indonesian Problem | 9.43 | 2023-08-18 04:41 | - | |
| arz-flex | 9.25 | 2024-06-10 19:55 | - | |
| Mbugwe Lizzie FLExTrans RA-01 | 8.18 | 2025-11-20 21:20 | - | |
| Mbugwe Lizzie FLExTrans | 8.15 | 2023-11-15 15:15 | - | |
| French-FLExTrans-Demo2025 | 7.71 | 2025-08-12 10:17 | - | |
| Lex Training Sample Project 1 | 7.65 | 2021-09-29 20:04 | - | |
| ResembliO-Delete | 7.58 | 2022-02-07 18:51 | - | disposable |
| ResembliO | 7.58 | 2022-02-07 18:51 | - | |
| Vanaw | 7.49 | 2025-08-19 00:23 | - | |
| Resembli | 7.49 | 2023-05-02 16:41 | - | |
| Quenya | 7.46 | 2024-10-11 19:04 | - | |
| Nepali flextrans experiment | 7.44 | 2023-11-13 21:53 | - | |
| Resembli Original | 7.38 | 2019-07-01 19:25 | - | |
| French-FLExTrans-Exp5 | 7.34 | 2026-05-15 21:29 | **YES** | |
| French-FLExTrans | 7.27 | 2023-11-14 00:38 | - | |
| French-FLExTrans-Exp4 | 7.27 | 2023-11-15 18:00 | - | |
| SpanishParsing | 7.24 | 2023-05-16 16:04 | - | |
| Takwane-Jeff | 7.23 | 2023-07-08 06:00 | - | |
| Indonesian-FLExTrans | 7.18 | 2023-11-15 20:53 | - | |
| Malay Parsing-20230810withHC | 7.09 | 2023-08-15 05:12 | - | |
| Spanish-FLExTrans-Demo2025 | 6.99 | 2025-07-22 23:23 | - | |
| Circumsanity | 6.87 | 2026-02-07 01:57 | - | |
| Spanish-FLExTrans-Exp5 | 6.79 | 2024-09-27 05:07 | - | |
| Spanish-FLExTrans-Exp4 | 6.78 | 2023-11-01 18:28 | - | |
| Korean-GIAL | 6.73 | 2023-07-14 18:37 | - | |
| Swahili Andreas | 6.67 | 2023-07-08 06:11 | - | |
| Mayanau-Bena-Yungur Toy | 6.47 | 2026-08-14 11:17 | - | |
| Nyika | 6.42 | 2026-08-11 13:59 | - | |
| Malay Project | 6.29 | 2023-08-17 04:39 | - | |
| Mayanau-Bena-Yungur Salvage | 6.12 | 2026-08-14 08:07 | - | |
| Turkish | 5.92 | 2025-09-10 22:01 | - | |
| Lamkang flextrans experiment | 5.65 | 2023-11-13 21:46 | - | |
| Rangi Lizzie FLExTrans | 5.61 | 2023-11-12 18:22 | - | |
| German-FLExTrans-Sample | 5.60 | 2024-09-27 04:47 | - | |
| morphboundary | 5.58 | 2024-08-28 02:21 | - | |
| NotOnClitic | 5.56 | 2026-05-08 23:13 | - | |
| IndonesianRelated-FLExTrans | 5.56 | 2023-11-15 21:02 | - | |
| Swedish-FLExTrans-Sample | 5.56 | 2026-02-17 16:07 | - | |
| Egyptian Arabic Template | 5.53 | 2023-08-08 03:21 | - | |
| feat-swahili | 5.51 | 2026-07-15 15:52 | - | |
| Claude-Turkish | 5.28 | 2026-06-02 07:49 | **YES** | |
| Iceve-Maci Test-Iceve | 5.23 | 2023-11-10 16:19 | - | |
| Iceve-Maci Test-Ici | 5.18 | 2023-11-08 19:36 | - | |
| Meetto -Flextrans | 5.12 | 2024-04-23 15:51 | - | |
| TAK-Flextrans | 5.11 | 2024-02-18 18:05 | - | |
| Ejaw | 5.01 | 2026-07-06 08:53 | - | |
| Kenyang-M | 4.95 | 2025-12-05 07:09 | - | |
| Puguli | 4.93 | 2026-08-12 13:46 | **YES** | |
| **Ejagham Full GT-Test** | 4.92 | 2026-08-11 09:21 | - | additional working dir (2nd target) |
| **Target** | 4.92 | 2026-08-16 19:52 | - | **the disposable Target** |

Shells with NO `.fwdata` (must be skipped by enumeration): `Mbugwe Lizzie HCPractice`,
`Target.pre025bak`, `Target.pre029bak`, `TestLangProj`, `SampleLexicon`,
`SampleLexicon3`, `Sichuan Yi`, `Proj_no_pop`, `Pere`, `_`, `__flexlibs_testing`.

Flags:
- **CORRECTION to the brief:** `Mbugwe Lizzie HCPractice` is an EMPTY shell (only a
  `SharedSettings` dir, no fwdata). The real known-good project is
  **`Mbugwe LizzieHC practice`** (10.60 MB, note the different spacing/case).
  Do not name the former in a sweep list -- it will register as unopenable.
- Known-good read-only test set present: `Ejagham Mini`, `Esperanto`,
  `Mbugwe LizzieHC practice` (+ `Mbugwe Lizzie` used by the pilot).
- Disposable Target: `Target` (4.92 MB). `Target.pre025bak` / `Target.pre029bak`
  are archived Target snapshots (contain `Target.fwdata` + a
  `Target.fwdata.partialmove-evidence` file), not projects of their own names.
- Additional working directory `Ejagham Full GT-Test` is a real project (4.92 MB)
  and is explicitly EXCLUDED in `scratchpad/fullcopy_manifest.json` alongside Target.

## 2. LOCK DETECTION

Observed artifact patterns inside project dirs:

| Pattern | Meaning | Count seen |
|---|---|---|
| `<name>.fwdata.lock` | live/stale open marker; JSON `{"__type":"FileLockContent:#Palaso.IO.FileLock","PID":n,"ProcessName":...,"Timestamp":...}` | 7 |
| `<name>.bak` | FLEx's own previous-save copy of the fwdata (same order of size as fwdata) | ~70 |
| `WritingSystemStore\badldml.log` | LDML parse complaints written on open | 9 |
| `Temp\` subdir | FLEx scratch dir, mtime moves on open | several |
| `<name>.fwdata.old` | orphan (root-level `Sichuan Yi old.fwdata.old`) | 1 |
| `Target.fwdata.partialmove-evidence` | forensic copy from a past partial move | 2 |
| `Lexicon.fwstub`, `Lexicon.fwstub.ChorusNotes` | Send/Receive stubs (harmless) | many |
| `SharedSettings\LexiconSettings.plsx` | the projectSharing flag that forces the SharedXML backend (see api.py `_disable_project_sharing`) | many |

No `~`-prefixed temp files, no `WriteEnabled` marker files, no journal files exist.

Currently-present locks, with owner from lock content -- all 7 are **STALE**
(none of the recorded PIDs is alive; live processes are only pythons
10292/22332/41956/46312 and `afwServ` 7648):

| Lock | mtime | PID | ProcessName | stale? |
|---|---|---|---|---|
| Ejagham025Src | 2026-08-17 21:31:18 | 18712 | GramTrans-portable | stale |
| Claude-Turkish | 2026-08-17 21:31:03 | 18712 | GramTrans-portable | stale |
| Ejagham Full | 2026-08-17 21:21:01 | 13364 | GramTrans-portable | stale |
| Ejagham Mini | 2026-08-17 21:20:51 | 13364 | GramTrans-portable | stale |
| Mbugwe LizzieHC practice | 2026-08-17 20:45:04 | 55704 | python | stale |
| French-FLExTrans-Exp5 | 2026-08-12 09:32:58 | 53812 | FieldWorks | stale (5 days) |
| Puguli | 2026-08-12 08:30:28 | 66616 | FieldWorks | stale (5 days) |

Design consequence: a lock file's JSON carries PID + ProcessName, so staleness can
be decided precisely (PID not alive OR PID alive but ProcessName mismatch) without
guessing from timestamps. Nothing was killed or deleted.

## 3. BACKUP / RESTORE MECHANICS

`GT_BACKUP` default (both drivers) = `backups\Target 2026-07-06 0218.fwbackup`:
- `debug/run_fullsweep_verify.py:52`
- `debug/audit_guid_preservation.py:51`
- also hardcoded at `debug/run_configview_live.py:57`
- `scratchpad/run_fullcopy_live.py:90` instead resolves `GT_BACKUP` or newest.

`D:\Github\_Projects\_LEX\GramTrans\backups\` (9.49 MB total):

| File | MB | mtime |
|---|---|---|
| Ejagham Full.fwbackup | 4.80 | 2026-06-15 22:02:18 |
| Ejagham Mini.fwbackup | 3.44 | 2026-06-15 22:02:26 |
| Target 2026-07-06 0218.fwbackup | 1.26 | 2026-07-06 10:18:31 |

Note: `newest_backup()` (mtime order) returns the **Target** backup, so the
`backup_path=None` default is currently safe.

Restore implementation -- `D:\Github\_Projects\_LEX\GramTrans\tests\integration\harness\restore.py`:
- `restore.py:54  newest_backup(backups_dir=<repo>/backups) -> Path`
- `restore.py:139 restore_target(project_name, backup_path=None, projects_root=None) -> None`
- Mechanism is a **headless zip extract**, NOT a FieldWorks CLI call. A `.fwbackup`
  is a zip; the code deliberately avoids `FieldWorks.exe -restore` because that
  launches the GUI and blocks unattended runs (docstring `restore.py:5-8`).
- Destructive steps inside the named project dir (`restore.py:190-206`):
  deletes every `*.lock`, deletes `<name>.fwdata`, and `shutil.rmtree`s
  `WritingSystemStore`, `ConfigurationSettings`, `SharedSettings`; then extracts
  every member except the `BackupSettings` top dir (`_SKIP_TOP_DIRS`,
  `restore.py:41`), renaming the archived root `*.fwdata` to `<project_name>.fwdata`
  (`_dest_for_member`, `restore.py:118`).
- Legacy GUI fallback exists but is unused: `_resolve_fw_exe` (`restore.py:74`) plus
  `_FW_EXE_CANDIDATES` = `C:\Program Files\SIL\FieldWorks 9\FieldWorks.exe`.
- Env overrides: `GRAMTRANS_FW_EXE`, `GRAMTRANS_PROJECTS_ROOT`.

Call sites: `debug/run_fullsweep_verify.py:332,343`, `debug/run_configview_live.py:185,271`,
`scratchpad/run_fullcopy_live.py:237,275` (restore before AND after each iteration).

**SAFETY, load-bearing:** `restore_target` takes an arbitrary `project_name` and
unconditionally wipes fwdata + three settings dirs there. If a sweep ever passes a
source name (or an fwbackup whose contents differ), it silently destroys that
project. The sweep must hard-assert `project_name == "Target"` (or an explicit
allowlist) before every call.

No document anywhere claims a restore duration. Empirically the payload is a
1.26 MB zip expanding to a ~4.92 MB fwdata plus a handful of small settings files,
so a restore is I/O-bound and sub-second to ~2 s on local disk.

## 4. RUNTIME BUDGET

Recorded timings: none inside the JSONs (no `elapsed`/`duration` keys). The only
wall-clock evidence is artifact creation times from the pilot Ralph loop, one
project per iteration, each iteration = restore + Move#1 + Move#2 + restore + verify:

| Artifact | created | delta |
|---|---|---|
| fullcopy_results/Ejagham Mini.json | 2026-07-20 10:29:40 | - |
| fullcopy_results/Esperanto.json | 2026-07-20 10:34:34 | 4 m 54 s |
| fullcopy_results/Mbugwe Lizzie.json | 2026-07-20 10:40:08 | 5 m 34 s |
| fullcopy_manifest.json (checkpoint) | 2026-07-20 10:41:01 | 53 s |

Assumptions:
- ~5.5 min per project for the double-Move variant, and note it is NOT strongly
  size-driven: Esperanto (179 MB) took 4 m 54 s while Mbugwe Lizzie (21 MB) took
  5 m 34 s -- cost tracks action/drop volume and open/close, not fwdata bytes.
- Restores are ~1-2 s each (2 per project) -> negligible, < 0.1% of the budget.
- Sources come only from the 84 dirs that have an fwdata; minus `Target` and
  `Ejagham Full GT-Test` = **82 transferable sources** (manifest lists 3 pilot + 74
  expansion = 77, i.e. it predates 5 newer projects: Ngoreme, Sena 3, Nyika,
  Mayanau x2 etc.).
- Ralph iteration overhead (MCP discovery call + manifest bookkeeping) ~30-60 s if
  the sweep is agent-driven; a single in-process driver loop avoids it.

Estimates:
- Double-Move (idempotency) sweep, 82 projects x 5.5 min = **~7.5 h**; with a 1.5x
  allowance for the ten 50-180 MB projects and per-iteration overhead, **8-12 h**.
- Single-Move + verify only (~3 min/project) = **~4-5 h**.
- Add ~5 min for the whole sweep's restores in total.
- Unknown risk: 11 shells + any project needing a data migration will burn the
  1800 s `run_module` timeout each if not pre-filtered (worst case +5.5 h).

## 5. EXISTING DISCOVERY CODE

Yes -- reuse it, do not glob:

- `D:\Github\_Projects\_LEX\GramTrans\src\gramtrans\Lib\api.py:428`
  `def list_source_candidates(projects_root: str = "", exclude_names: Tuple[str, ...] = (), exclude_paths: Tuple[str, ...] = ()) -> List[SourceCandidate]`
- `...\src\gramtrans\Lib\api.py:406`
  `def list_target_candidates(stub: RunContextStub, projects_root: str = _DEFAULT_PROJECTS_ROOT) -> List[TargetCandidate]`
- `...\src\gramtrans\Lib\api.py:463`
  `def _walk_flex_projects(root: str) -> List[Tuple[str, str]]` -- the single place
  that defines "a FLEx project on disk" = a directory containing a same-named
  `.fwdata`; sorted by name. This is exactly the shell-dir filter the sweep needs.
- Dataclasses: `SourceCandidate` (`api.py:330`) and `TargetCandidate` (`api.py:319`),
  both `project_name: str, project_path: str`.
- Path identity helper: `_same_project_path(a, b)` at `api.py:483` (normcase +
  trailing-sep insensitive) -- use for the "never equal to Target" assertion.
- Projects root from FieldWorks itself: `...\src\gramtrans\standalone\fwglobals.py:176`
  `def projects_dir() -> str` (reads `FWProjectsDir`).
- LCM-level enumeration used by the prereq smoke check: `flexicon.AllProjectNames()`
  at `...\src\gramtrans\standalone\prereq.py:283` (inside `_check_projects_enumerated`).
  Requires a live runtime, so prefer the filesystem walk for a sweep planner.
- UI-side (reported from grep only, file not opened, per instruction):
  `src\gramtrans\Lib\ui\source_picker.py:119  def project_names(...)` and
  `:161  def mark_unopenable(project_name, reason="")` -- the latter is the existing
  precedent for recording a project that cannot be opened.
- Restore-side root resolution: `tests\integration\harness\restore.py:106`
  `_resolve_projects_root` (arg -> `GRAMTRANS_PROJECTS_ROOT` -> Windows default).

## 6. TAMPER GUARD FEASIBILITY

Viable, with one caveat. Fingerprinting `(size, mtime)` of `<name>.fwdata` before and
after each iteration is cheap (one `stat` per project; a full 84-project pass is
milliseconds) and the on-disk evidence supports it:

- `Ejagham Mini.fwdata` still shows mtime 2026-07-03 21:30 despite being opened
  read-only as recently as 2026-08-17 21:20 (its `.lock` timestamp). Read-only opens
  therefore do NOT touch the fwdata mtime or size.
- Same for `Mbugwe LizzieHC practice` (fwdata 2024-08-22, lock 2026-08-17) and
  `Claude-Turkish` (fwdata 2026-06-02, lock 2026-08-17).

Legitimate ways the fingerprint can still change on a read-only open:
1. **Data-model migration.** FLEx migrates a project on open and rewrites the
   fwdata; called out as a hazard in `specs\034-standalone-windows-app\spec.md:268`
   ("The application must not silently migrate a user's project as a side effect").
   Any project last saved by an older FW version will legitimately trip the guard --
   and that is itself a finding worth recording, not a false positive to suppress.
2. **`.bak` rotation** if a write path is ever reached (FLEx writes `<name>.bak`
   next to the fwdata on save) -- fingerprint the `.bak` too as a secondary tell.
3. **Non-fwdata writes are normal and expected**, so do NOT fingerprint the whole
   directory: opens touch `<name>.fwdata.lock` (created/deleted),
   `WritingSystemStore\` (e.g. `Ejagham Mini\WritingSystemStore\badldml.log`,
   2026-08-17 01:29), `Temp\`, and `SharedSettings\`. A folder-level hash would
   alarm on every run.
4. Project sharing: `api._disable_project_sharing` (`api.py:491`) deliberately
   rewrites `SharedSettings\LexiconSettings.plsx` for the **target** -- confirm the
   sweep never invokes it against a source, or the guard must whitelist that file.

Recommended guard: per source, record `(fwdata size, fwdata mtime_ns, bak size,
bak mtime_ns)` pre/post; fail loud on any delta. Optionally add SHA-256 of the
fwdata only for the ~10 projects under 12 MB used as regression sources (hashing all
1761 MB costs roughly 10-20 s per pass, acceptable once per sweep but not per
project). Complement it with an assertion that the only path handed to
`restore_target` is `Target`, since that function is the one code path in the repo
that deletes project files.
