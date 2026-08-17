# Cycle 2 -- Parallel-Sweep Safety Audit (adversarial)

Scope: the planned 82-source x N-worker sweep. Read-only audit; no source file modified,
no FLEx project opened. P0 count: 8. P1: 1. Disk facts confirmed: 96 dirs under
`C:\ProgramData\SIL\FieldWorks\Projects`; `Target`, `Target.pre025bak`,
`Target.pre029bak` all present, both `.pre0*bak` dirs holding `Target.fwdata`,
`Target.bak`, `Target.fwdata.partialmove-evidence`, `WritingSystemStore`,
`ConfigurationSettings`, `SharedSettings`, `LinkedFiles`, `Temp`. Repo `backups/` holds
3 files, newest by mtime `Target 2026-07-06 0218.fwbackup` -- so `newest_backup()` is
benign only by accident of mtime.

## 1. DESTRUCTIVE-PATH INVENTORY

The "only path" claim is **FALSE**: `restore_target` is the only path that
*deletes* project files, but three others *overwrite or add* files under the
projects root, one of them in production `src/`.

| # | file:line | destroys / writes | name constraint today |
|---|-----------|-------------------|-----------------------|
| D1 | `tests\integration\harness\restore.py:193-194` | `glob("*.lock")` -> `unlink()`, unconditional | none; any `project_name` string |
| D2 | `restore.py:195-197` | `<name>.fwdata` -> `unlink()` | none |
| D3 | `restore.py:198-201` | `rmtree` of `WritingSystemStore`, `ConfigurationSettings`, `SharedSettings` | none. **Irrecoverable** -- no backup taken first |
| D4 | `restore.py:210-218` | writes every zip member via `open(dest,"wb")`; `dest` from `_dest_for_member` (`:118-136`) | **no path containment**: `norm` is archive-controlled, `proj_dir / norm` escapes on `..` or a drive-absolute member (pathlib join with an absolute part replaces the base) |
| D5 | `restore.py:191` | `mkdir(parents=True, exist_ok=True)` -- silently creates a dir for a typo'd name | none |
| D6 | `restore.py:106-115` | chooses the root D1-D5 act in | arg > `GRAMTRANS_PROJECTS_ROOT` > literal; only `is_dir()` |
| D7 | `restore.py:54-71` `newest_backup()` | chooses the *content* D4 writes | newest `*.fwbackup` mtime in repo `backups/`; no name/content correlation |
| D8 | `src\gramtrans\Lib\api.py:513-526` `_disable_project_sharing` | rewrites `SharedSettings/LexiconSettings.plsx` in place, no backup | `choice.project_path` only; called from `bind_target` (`:575`) before `OpenProject`, wrapped in `except Exception -> warning` so failure never blocks |
| D9 | `src\gramtrans\Lib\config_views.py:424-434` | `copy2` into `<target>/ConfigurationSettings/{Dictionary,ReversalIndex}` | `tgt_path` from `_project_dir(tgt_project)` (`:79,390`) = wherever the write handle points. OVERWRITE keeps `.gtbak`; ADD is unbounded |
| D10 | `src\gramtrans\Lib\pictures.py:485-620` | copies image assets into `target.GetLinkedFilesDir()/Pictures` | collision logic is non-destructive (`:580-596`), but `GetLinkedFilesDir()` comes from the restored fwdata and is **unverified** to sit inside the target dir |
| D11 | LCM, `api.py:578-604` | `OpenProject(writeEnabled=True)` rewrites `<name>.fwdata`, creates `.lock`, may migrate | resolves by *name* via registry `FWProjectsDir` (`standalone\fwglobals.py:183`), **not** `GRAMTRANS_PROJECTS_ROOT` |

Out of scope, verified: `build\build.py:108,203`; `write-context.py`;
`run_configview_live.py:145-148`; `pictures.py:614` (`mkdtemp`). No FieldWorks CLI is
invoked anywhere, but `_resolve_fw_exe` (`restore.py:74-103`) is dead latent
legacy-fallback code.

**Existing `restore_target` call sites (19).** `debug\` (13):
`audit_guid_preservation.py:147`, `coverage_report.py:164`, `run031_live.py:111`,
`run_configview_live.py:184` **(restores a SOURCE)**, `:185`, `:271`,
`run27_live.py:231`, `run028_live.py:162`, `run_inflclass_live.py:156`,
`run_partB_live.py:259`, `:329`, `run_msa_slot_live.py:164`,
`run_fullsweep_verify.py:343`. `tests\integration\` (6):
`test_custom_fields_live.py:77`, `test_e2e_all_categories.py:72`,
`test_full_workflow_e2e.py:179`, `:216`, `test_guid_preservation.py:56`,
`test_target_preserved.py:53`. `scratchpad\`: none (dir exists, no calls). Every
`debug\` site takes `GT_TARGET` from the environment (default `"Target"`)
-- an unvalidated env string reaching D1-D5. Integration sites hard-code
`TARGET_NAME`: five use `"Ejagham Full GT-Test"`, `test_028_affix_msenv_live.py:55` uses
`"Target"`. So a bare `^Target([0-9]+)?$` guard inside `restore_target` **turns five
existing tests red** and will get reverted -- see assertion 3.

Guard search: no `fullmatch`, no anchored regex, no `startswith("Target")`, no
allowlist, no `is_disposable` anywhere in the repo -- protection today is
**zero**. The only precedent is the GUI Move gate
(`tests\unit\test_034_standalone_gate.py`); its near-miss table is the model.

## 2. ATTACK LIST

**A1 Loose pattern destroys the archives (P0).** Trigger: `startswith`,
`Target*` glob, or `re.match` (anchors only the start). Blast radius, exactly: per bak
dir, D3 `rmtree`s `WritingSystemStore`, `ConfigurationSettings`, `SharedSettings` --
present in no `.fwbackup`, so the loss is permanent; D2 finds no
`Target.pre025bak.fwdata` so `Target.fwdata`, `Target.bak` and `.partialmove-evidence`
survive; D4 lands a new `Target.pre025bak.fwdata`.
**Escalation:** that file makes the dir satisfy `_walk_flex_projects`'s
`<name>/<name>.fwdata` rule (`api.py:463-481`), promoting the wrecked archive into the
target *and* source candidate lists for every later run. Stopped: no.

**A2 Zip-slip (P0).** Trigger: a `.fwbackup` (or any zip renamed so) with a member
`../Ejagham Mini/Ejagham Mini.fwdata`, or a drive-absolute member. `_dest_for_member`
normalizes separators then joins with no `resolve()` / `is_relative_to` check. Radius:
arbitrary overwrite of any writable path, including real `.fwdata`. **Fires even with a
perfect name guard** -- the destination never passes through `project_name`. Stopped:
no.

**A3 Scheduler hands a source name to a worker as its target (P0).** Trigger:
mis-ordered `zip(sources, targets)`, worker id indexing the source list, a retry
re-queuing with a stale closure variable. Radius: D1-D5 wipe a real project, D11 opens
it write-enabled, D8 rewrites its `.plsx`. Stopped today: **partially, and by luck.**
`bind_target` (`api.py:555-565`) refuses source==target by name and by path -- but the
path branch is `if stub.source_project_path and ...` and both harness callers pass
`source_project_path=""` (`full_run.py:158`, `run_fullsweep_verify.py:295`), so **the
by-path check is dead in every harness run**; names differing by one character defeat
the by-name check; and nothing guards the restore, which runs *before* `bind_target`.

**A4 Two workers share a target (P0).** Trigger: id reuse after a crash-restart,
`f"Target{i%N}"`, a stale pool file. Radius: worker B's D1 unlinks A's live `.lock` and
D2 unlinks the `.fwdata` A has open; A then saves into a dir whose `WritingSystemStore`
was `rmtree`d underneath it. No real project lost, but both workers' results are
silently invalid -- a fidelity sweep reporting PASS on corrupted state is worse than a
crash. Stopped: no; `restore.py`'s `PermissionError` branch fires non-deterministically
per handle held.

**A5 Target name assembled by concatenation (P0).** Trigger:
`"Target" + str(worker_id)` with id `None`/`""`/a float (`Target1.0`)/a path fragment;
or `join(root, name)` with a leading separator or `..`. Radius: empty id collapses N
workers onto one dir (= A4); `"Target/../Ejagham Mini"` passes any substring check and
D1-D5 hit a real project. Stopped today: no -- `restore_target` does not even reject a
separator in `project_name`.

**A6 Env/config redirect (P0, non-obvious).** Trigger: `GRAMTRANS_PROJECTS_ROOT`
set to a sandbox "to make the sweep safe", or `GT_TARGET`/`GT_TARGET_PATH` exported into
a worker. Radius: that variable is read by `restore.py:108` but
**never by `api.py`** (`_DEFAULT_PROJECTS_ROOT` is a literal at `api.py:66`, and
D11 resolves by name through the registry) -- so the restore lands in the sandbox and
the transfer **writes into the real project of the same name**. The safety measure
creates the accident, and the run looks clean because the restore succeeded. Separately,
`GT_TARGET` and `GT_TARGET_PATH` are independent variables both feeding
`TargetCandidate(project_name=..., project_path=...)` (`run_fullsweep_verify.py:296`,
`full_run.py:160`): D8 uses the path, D11 the name, so one stale variable rewrites X's
`.plsx` while transferring into Y. Stopped today: no -- nothing checks that path and
name agree.

**A7 Backup content does not match the destination (P0).** Trigger: any call
omitting `backup_path`, taking `newest_backup()`. The sweep's own prudent step -- back
up all 82 sources first -- silently repoints that default to a *real project's* archive
if the files land in repo `backups/`. `_dest_for_member:134-135` then renames the
archive's root `.fwdata` to `<Target>.fwdata` and reports success. Radius: hours of
transfers into a target that is secretly a clone of a real project; every fidelity delta
meaningless, and GUID-preserving writes now exist twice under one identity. Stopped
today: no
-- no check that the archive stem matches the destination, and no hash pin.

**A8 Crashed worker leaves a partial target treated as valid (P0).** Trigger:
kill mid-D4 or mid-`execute_move`, after D2/D3 deleted. The next restore mostly
self-heals -- **verified**: D1 unlinks locks first, before D2/D3/D4, so a stale lock
*file* is cleared. Three holes: (i) that only helps if the next step *is* a restore -- a
resumed sweep skipping restore because "the target exists" runs on rubble; (ii)
`restore.py` leaves unrelated files alone, so `LinkedFiles`, `Temp`, `BackupSettings`
and orphaned evidence files accumulate -- assets from project K leak into K+1's baseline
(S-65); (iii) a lock held by a *live* process is not healed at all -- D1 unlinks the
file while the owner keeps its handle, and the restore proceeds against a project
another process believes it owns.

**A9 Config-view and picture writes escape the target (P1).** D9 writes
wherever the handle points, inheriting every mis-targeting above; D10 writes wherever
the restored fwdata says `LinkedFilesDir` is, and a backup restored under a new name can
carry an absolute path to the project it came from. Radius: assets and `.fwdictconfig`
files *added* into a real project -- additive, so an fwdata-only fingerprint never sees
it. UNMEASURED.

## 3. REQUIRED ASSERTIONS

Placement first. **The lead is right that a restore-boundary-only assertion is
insufficient, and understates it.** Three reasons: (a) D8/D11 are reachable with no
restore -- `bind_target` is public and `run_full_move()` is a separate function from
`main()`; (b) A2 bypasses the name entirely, so the restore guard passes while the write
lands elsewhere; (c) the irreversible act is the write-open, seconds later, under a name
that arrived via a *different* variable. Guard both, as two independent checks -- not
one flag read twice.

1. **Anchored name check:** `re.fullmatch(r"Target(?:[0-9]+)?", name)` --
   `fullmatch`, never `match`; no `startswith`; no glob. Tests must include the
   near-misses on disk (`Target.pre025bak`, `Target.pre029bak`) plus `Target `,
   ` Target`, `target`, `TARGET`, `Target/x`, `Target..`, `Target1.0`, `""`.
2. **Placement: at D1 (in `restore_target`, before `mkdir`) AND at the write-open
   (in `bind_target`, before `_disable_project_sharing`)** -- never in the sweep
   driver alone, the layer most likely to be rewritten under pressure.
3. **Do not hard-wire the pattern into `restore_target`** (it would red five
   integration tests and be reverted): add `assert_disposable(name, allowed:
   tuple[re.Pattern, ...])`, default allowlist of two *fullmatch* patterns
   (`Target(?:[0-9]+)?`, `Ejagham Full GT\-Test`), with the sweep driver passing
   a **narrowed** one. Deny by default; an empty allowlist raises.
4. **Path containment, independent of the name:**
   `dest.resolve().is_relative_to(proj_dir.resolve())` for every zip member
   (kills A2); `proj_dir.resolve() == root.resolve() / name` and reject any name
   containing `/`, `\`, `:`, or a `.`/`..` component (kills A5).
5. **Name/path agreement at the write boundary:** in `bind_target`, assert
   `normcase(choice.project_path) == normcase(join(registry FWProjectsDir,
   choice.project_name))`. Only this stops A6's split-brain, and it must use the
   *registry* root (`fwglobals.py:183`) -- that is what LCM opens.
6. **`worker.target != worker.source`, by name and by realpath**, before the
   restore -- and **repair the dead check**: stop passing
   `source_project_path=""` so `api.py:561` goes live. A guard skipped because
   an argument is falsy is worse than none; reviewers count it as present.
7. **`worker.target` absent from the whole 82-name source manifest**, not just
   this worker's current source (catches A3's retry-closure variant).
8. **No shared target, enforced by an OS resource:** an `O_CREAT|O_EXCL` claim
   file per target, outside the projects root, held for the whole iteration,
   aborting if creation fails. Ids alone are insufficient (A4 is id reuse).
   Assert the pool is a set of N distinct anchored names.
9. **Backup/destination correlation, before D3 deletes anything:** exactly one
   root-level `*.fwdata` member, its stem equal to the destination or a declared
   `expected_archive_stem`, no absolute/`..` members. **Never call
   `newest_backup()` from the sweep**; pin the path and its sha256 (A7).
10. **Post-restore sentinel** `.gt-restore-ok` holding backup sha256,
    destination name and pid. The next iteration must require it or restore
    unconditionally; "the directory exists so it is fine" is forbidden (A8-i).
11. **Residue assertion:** post-restore file set == archive member set plus the
    sentinel. If residue is tolerated, record the delta in the per-project
    artifact rather than ignore it (A8-ii, S-65).
12. **Assert `GetLinkedFilesDir()` resolves inside the target's own directory**
    before any picture action runs (A9 / D10).
13. **Freeze the 82 source names** into a hashed manifest captured once and
    re-verified per worker -- never re-enumerate live, or a dir created mid-sweep
    (D5, A1) silently joins the source set.

**On violation: hard-abort the entire sweep. Confirmed, and I would go
further.** Every assertion fires only when the sweep's model of the machine is wrong --
mis-assigned target, shared target, redirected root, mismatched archive
-- never a project-specific data quirk. Continuing bets the bug is scoped to the
project that tripped it, and A3/A4/A6 are exactly the bugs that are not: worker 3's bad
pairing means worker 4's is bad too, and the pool keeps destroying at machine speed
while the operator reads the first traceback. So: abort the pool, signal siblings via a
shared abort file polled between projects, leave the aborting worker's target untouched.
One carve-out -- a per-project *transfer* failure (LCM throw, timeout, migration) is a
RESULT: record and continue. Distinguish "guard tripped" from "project failed" by
exception type, never by message text.

## 4. SOURCE-INTEGRITY GUARD

Per source, captured immediately before the read-only open and again after the close.
Whole-directory hashing is rejected: read-only opens touch `.lock`, a
`WritingSystemStore` log, `Temp` and `SharedSettings`, so a tree hash false-alarms every
run and the guard gets switched off within an hour.

Fingerprint = exactly four fields: (1) `<name>.fwdata` size; (2) its mtime_ns; (3)
sha256 of `<name>.fwdata` -- compute it, since size+mtime is defeated by an in-place
same-length rewrite and ~5 MB is trivial next to a full transfer; (4) sha256 of
`SharedSettings/LexiconSettings.plsx` if present, kept as its own field -- the one
non-fwdata file a GramTrans path is *known* to rewrite (D8). Recorded as touched yes/no
but never compared: `*.lock`, `Temp/**`, `WritingSystemStore/*.log`,
`BackupSettings/**`. Also record each source's `projectSharing` flag without changing
it: with sharing on, even a read-only open uses the SharedXML commit-log peer backend
and may write. Never "fix" that -- flipping it is D8 aimed at a source; quarantine such
sources pending measurement.

On a delta:
- **fwdata sha256 + size + mtime all changed, file still parses**: almost
  certainly a legitimate data-model migration on open. **RECORD as a finding** --
  name, both hashes, sizes, mtimes, and the model-version header before/after. Do
  not suppress, retry, or restore the source from backup. Continue only if the
  sweep contract accepts migrations; the finding is a first-class artifact.
- **sha256 changed with size and mtime identical**: not a migration. Abort the
  whole sweep -- a write reached a source (A3/A6) or the filesystem is lying.
- **`.plsx` sha256 changed**: abort. Exactly one path does this (`api.py:526`)
  and only against a bind *target* -- proof a source was bound as a target.
- **fwdata missing after the run**: abort, page the human, no auto-recovery.

Capture pre-fingerprints for all 82 sources **once, up front, before any worker
starts**, into one hashed manifest -- a per-worker just-in-time pre-fingerprint would
baseline damage another worker already did.

## 5. WORKER MODEL RISKS (breaks at N>1, not at N=1)

- **Runtime init is per-process and unmeasured under concurrency.**
  `_ensure_flex_initialized` (`full_run.py:67-82`) is correct per process, and a
  CLI with a work queue is the right shape (a shared plugin host with a fixed
  timeout lets one slow project starve the pool). But `FLExInitialize` reads
  registry `CompanyKey`/`FWProjectsDir`; N simultaneous first-opens against one
  hive and one FieldWorks service is untested.
- **A FieldWorks service process is running and it is UNMEASURED whether it
  serializes concurrent opens.** Treat N as gated on measurement, not a tuning
  knob. The trial must measure, at N=2 then N=3: (a) wall time per project vs the
  N=1 baseline -- linear scaling with N means opens are serialized and extra
  workers buy nothing; (b) whether any open fails or blocks >60 s while a sibling
  is mid-open; (c) whether a sibling's open perturbs an unrelated project's lock
  file or `Temp`; (d) peak RSS per worker x N vs physical RAM (each holds a full
  LCM cache); (e) whether `CloseProject` latency degrades with N, since
  `_close_project_watchdog`'s 90 s deadline (`GRAMTRANS_SCHEMA_CLOSE_TIMEOUT`,
  `api.py:92`) only *logs* -- a watchdog that cannot abort is not a timeout.
  Publish numbers before choosing N; default N=1, and N=2 is the only defensible
  first step.
- **Shared mutable singletons that are fine at N=1:** repo `backups/`
  (`newest_backup()` racing a worker writing an archive), the `DEBUG_ENV` log path
  (per-worker logs are mandatory -- two processes appending to one log interleave
  and destroy its forensic value), and any fixed-path result file. Artifacts must
  be per-worker *and* per-project, never one CSV appended by N writers.
- **Environment inheritance is the N>1 amplifier.** `GT_TARGET`,
  `GT_TARGET_PATH`, `GRAMTRANS_PROJECTS_ROOT`, `GRAMTRANS_DEBUG` are read at
  import time in 13+ debug modules; if the launcher exports any, *every* worker
  inherits it and all N converge on one target (A4 and A6 at once). Pass target
  and source as **argv**; scrub `GT_*` and `GRAMTRANS_PROJECTS_ROOT` from the
  child environment.
- **Crash recovery:** the "restore unlinks locks first, so a re-run self-heals a
  stale target lock" reasoning is correct as far as it goes -- verified against
  `restore.py:193-194` preceding D2/D3/D4 -- but insufficient for a lock held by a
  live sibling (unlinking the file does not release the handle) and for a resumed
  sweep that skips the restore; assertions 8 and 10 cover both. Recovery must be
  idempotent per project: always restore first, never resume mid-transfer.
- **Cross-worker asset bleed:** D10 writes into `GetLinkedFilesDir()`, which
  `restore.py` never clears. If two restored targets resolve `LinkedFiles` to the
  same absolute path (possible from a shared archive), workers race on the same
  images and dedup-rename yields nondeterministic names -- results unreproducible
  with nothing looking wrong. Assertion 12, per worker.

## 6. TOP 5 P0 ITEMS (ranked)

1. Unanchored name match wipes `Target.pre0*bak` (`restore.py:198-201` `rmtree`s
   three unrecoverable dirs, then the wreck joins the live project list).
2. No zip-member path containment (`restore.py:118-136`, `:210-218`): arbitrary
   overwrite outside the target, bypassing any name guard.
3. `GRAMTRANS_PROJECTS_ROOT` redirects the restore but not the LCM write
   (`restore.py:108` vs `api.py:66` + registry): the "sandbox" writes into the real
   project of the same name.
4. No guard at the write-open, and the same-project path check is dead
   (`api.py:555-565` with `source_project_path=""`), so
   `_disable_project_sharing` (`api.py:526`) rewrites a real project's `.plsx`.
5. No exclusive target claim (A4) and no sha256-pinned baseline
   (`newest_backup()`, `restore.py:54-71`, A7).
