# Defect report — writing systems: SLDR never initialized, and store-vs-active conflation

**Date**: 2026-08-19
**Component**: `pyflexicon` (flexicon) `code/FLExInit.py`, `code/System/WritingSystemOperations.py`,
`code/BaseOperations.py`; GramTrans `Lib/api.py`, `Lib/ui/ws_wizard.py`, `Lib/debuglog.py`
**Trigger**: user report of "a failure warning about adding a writing system (English) that was already there"
**Status**: investigation complete; **NO CODE CHANGED BY THIS REPORT**
**Filed**: flexicon [#249](https://github.com/MattGyverLee/flexicon/issues/249),
[#250](https://github.com/MattGyverLee/flexicon/issues/250);
GramTrans [#43](https://github.com/MattGyverLee/GramTrans/issues/43),
[#44](https://github.com/MattGyverLee/GramTrans/issues/44) — see
[Filed issues](#filed-issues)

Three *distinct* defects were found while tracing that one report. They are separated
deliberately: only **(A)** is live and firing, **(B)** is already fixed, and **(C)** has
never yet fired but is a silent-drop breach waiting for the right project pair.

**No transfer was run during this investigation.** `Ejagham Mini`, `Esperanto` and
`Mbugwe LizzieHC practice` are **read-only test projects** and were not written to.
The evidence below is read-only inspection of an existing `WritingSystemStore`,
existing GramTrans logs, and source.

---

## (A) LIVE, ACTIVE — SLDR is never initialized, so liblcm quarantines and re-synthesizes English on every open

### Root cause

`flexicon/code/FLExInit.py:66-73`:

```python
    logger.debug("Calling Sldr.Initialize()")
    try:
        Sldr.Initialize(True)
    except Exception as e:
        # SLDR may already be initialized in some test/startup scenarios
        logger.warning(f"Sldr.Initialize failed (already initialized?): {e}")
```

The `except Exception` swallows **any** failure on the assumption that the only failure
mode is "already initialized". When `Sldr.Initialize(True)` genuinely fails, the SLDR
stays down. Every subsequent LDML read inside
`CoreLdmlInFolderWritingSystemRepository` throws `The SLDR has not been initialized`,
liblcm treats the file as malformed, **renames it to `.ldml.bad`**, logs the event to
`badldml.log`, and must synthesize the writing system from defaults again.

### Why nobody sees the warning

GramTrans configures logging for a fixed list of logger names —
`src/gramtrans/Lib/debuglog.py:46`:

```python
LOGGER_NAMES = (
    "gramtrans",
    "transfer",
    "api",
    "preview",
    "selection_wizard",
)
```

...with `propagate = False`. flexicon logs to `flexicon.code.FLExInit`, which is not in
that tuple and not a child of anything in it. **The warning is emitted and discarded.**

### Live evidence

`C:\ProgramData\SIL\FieldWorks\Projects\Ejagham Full GT-Test\WritingSystemStore\`
contains **no valid `.ldml` file at all**:

```
badldml.log      3968  2026-08-19 08:08
en.ldml.bad       453  2026-08-19 08:07
etu.ldml.bad      573  2026-08-19 08:07
idchangelog.xml  2170  2026-08-19 08:07
```

`badldml.log` records **16** quarantine events (8 per-open pairs of `en` + `etu`),
recurring on **every** open — 02:32:27, 02:39:10, 02:49:19, 03:01:31, 03:11:45,
03:23:52, 05:01:28, 05:08:00 (all UTC; local = UTC+3, so the last pair matches the
08:07/08:08 local file mtimes). Verbatim, one entry:

```
(8/19/2026 5:08:00 AM UTC)
Encountered a bad LDML file in a writing system repository.
Exception: The SLDR has not been initialized.
Moved C:\ProgramData\SIL\FieldWorks\Projects\Ejagham Full GT-Test\WritingSystemStore\en.ldml to en.ldml.bad
```

The `.fwdata` still declares the writing systems as active
(`Ejagham Full GT-Test.fwdata:112209-112217`):

```xml
<CurAnalysisWss>
<Uni>en</Uni>
</CurAnalysisWss>
...
<CurVernWss>
<Uni>etu</Uni>
</CurVernWss>
```

### Data loss is negligible — state this plainly

Do **not** overstate this defect. Both quarantined files carry only default content:

- `en.ldml.bad` — LTR `characterOrder` plus a `<sil:font name="Charis SIL" />`
  reference. Nothing else.
- `etu.ldml.bad` — the same, plus a `<collations>` block that declares
  `<defaultCollation>standard</defaultCollation>` and an **empty**
  `<collation type="standard" />` (no tailoring rules).

No custom collation tailoring. No keyboard. No custom fonts beyond the FLEx default.

The decisive observation is the timing. `en.ldml.bad` carries:

```xml
<generation date="2026-08-19T05:07:51Z" />
```

against a quarantine at `05:08:00Z` — **nine seconds**. FLEx writes the file and then
cannot read back what it just wrote. This is a **self-perpetuating cycle regenerating
defaults**, not erosion of hand-tuned settings. The cost is the cycle repeating on
every single open (and the WS store being permanently in a "no valid LDML" state),
not lost linguistic configuration.

### Open question

Does `Sldr.Initialize(True)` fail for a real reason (DLL / offline-cache / permissions),
or because a `Sldr.Cleanup()` from a prior `HostSession.release()` left the SLDR down
for a later open in the same process? The teardown path is
`src/gramtrans/standalone/app.py:416-422` -> `flexicon.FLExCleanup()` ->
`flexicon/code/FLExInit.py:82` `Sldr.Cleanup()`.

This is **settled by adding `"flexicon"` to `debuglog.py:46 LOGGER_NAMES` and re-running
with `GRAMTRANS_DEBUG=1`** — the swallowed warning then names the real exception.

Note that flexicon issue
[#179](https://github.com/MattGyverLee/flexicon/issues/179) (CLOSED) is the **same
symptom** from a different cause: unit tests calling `FLExCleanup()` in teardown. Its
fix was test-isolation only. The recurrence documented here is on the **production GUI
path**, so #179's fix does not cover it.

---

## (B) FIXED — `WS mapping not 1:1` `ValueError` escaping a Qt slot

Recorded for completeness. **Already fixed; no action required.**

`closest_ws_defaults` (`src/gramtrans/Lib/ws_mapping.py:426`) proposed `swh -> en`
while `en` already mapped to itself. `WSMapping.__post_init__`
(`src/gramtrans/Lib/models.py:549-559`) rejects a non-1:1 mapping:

```python
    def __post_init__(self) -> None:
        # 1:1: no two entries share target_ws_id unless they share source_ws_id
        by_target: dict = {}
        for e in self.entries:
            prev = by_target.get(e.target_ws_id)
            if prev is not None and prev != e.source_ws_id:
                raise ValueError(
                    f"WS mapping not 1:1: {prev!r} and {e.source_ws_id!r} "
                    f"both map to {e.target_ws_id!r}"
                )
```

The `ValueError` escaped a Qt slot and killed the app. Crash log
`C:\Users\thoua\AppData\Local\GramTrans\logs\gramtrans-GT-20260819-023439.log`
(mtime 02:44, source project `Ngoreme FLEx`, MOVE-enabled):

```
[ERROR] [GramTrans] Unhandled ValueError: WS mapping not 1:1: 'en' and 'swh' both map to 'en'
[ERROR]   File "gramtrans\Lib\ui\selection_wizard.py", line 5622, in _on_dry_run
[ERROR]   File "gramtrans\Lib\ui\selection_wizard.py", line 5405, in _compute_wizard_plan
[ERROR]   File "gramtrans\Lib\ui\selection_wizard.py", line 1444, in ws_mapping
[ERROR]   File "gramtrans\Lib\models.py", line 555, in __post_init__
[ERROR] ValueError: WS mapping not 1:1: 'en' and 'swh' both map to 'en'
```

Fixed by commit **`3dcc6a6`** — *"fix(ws): make the default WS mapping 1:1, and stop a
raising slot going silent"*, 2026-08-19 02:49:16 — **verified an ancestor of `HEAD`**
(`git merge-base --is-ancestor 3dcc6a6 HEAD` -> exit 0). Post-fix the slot returns
`(None, None)` after showing a dialog, at
`src/gramtrans/Lib/ui/selection_wizard.py:5485-5492`.

Note the fix landed at 02:49:16 and `badldml.log` records a quarantine pair at
02:49:19 — i.e. defect (A) continued unaffected. (A) and (B) are independent.

---

## (C) LATENT / NEVER-FIRED — store-vs-active conflation causes a SILENT DROP

This has **not** fired in any observed run. It needs a target project that has a
writing system **in its LDML store but not in `CurVernWss`/`CurAnalysisWss`**. When
that happens, source content in that writing system is dropped with no record.

### Three collections disagree along one path

1. **GramTrans decides "missing" from active-only.**
   `WritingSystems.GetAll()` filters `AllWritingSystems` down to
   `CurVernWss | CurAnalysisWss` — `flexicon/code/System/WritingSystemOperations.py:109-115`:

   ```python
        vern_ws_set = self._GetAllVernacularWSTags()
        anal_ws_set = self._GetAllAnalysisWSTags()
        active_tags = vern_ws_set | anal_ws_set

        for ws in self.project.project.ServiceLocator.WritingSystems.AllWritingSystems:
            if ws.Id in active_tags:
                yield ws
   ```

2. **It guards the create with a whole-store scan.** `Exists` (`:826`) delegates at
   `:858` to `_GetWSByTag` (`:949-964`), which walks **`AllWritingSystems`** — the
   entire store, active or not — and compares case-normalized.

3. **flexicon then writes content through active-only, exact-case keys.**
   `flexicon/code/BaseOperations.py:1306-1308`:

   ```python
        target_ws_by_id = {
            ws.Id: ws.Handle for ws in self.project.WritingSystems.GetAll()
        }
   ```

### The resulting sequence

A writing system present in the store but absent from the current lists is:

- **proposed for creation** (invisible to `GetAll()`), then
- **refused as already existing** — `WritingSystemOperations.py:240-241`:

  ```python
        if self.Exists(language_tag):
            raise FP_ParameterError(f"Writing system '{language_tag}' already exists")
  ```

- therefore **never activated** — nothing adds it to `Cur*Wss`, and
- its content is **silently dropped** — `BaseOperations.py:360-364`:

  ```python
                tgt_handle = target_ws_by_id.get(tgt_ws_id)
                if tgt_handle is None:
                    # Target lacks this WS; skip silently. Callers wanting
                    # strict mapping should pre-validate ws_map.
                    continue
  ```

### GramTrans downgrades this to a warning and continues

`src/gramtrans/Lib/api.py:874-884`:

```python
        try:
            tgt_ops.Create(tag, name, is_vernacular=is_vern)
            created.append(tag)
            ...
        except Exception as exc:  # noqa: BLE001 -- one bad tag must not abort the Move
            _log.warning(
                "_ensure_writing_systems: could not create WS %r: %s: %s",
                tag, type(exc).__name__, exc,
            )
```

The loop then continues and `execute_move` proceeds unchanged
(`src/gramtrans/Lib/api.py:963-968`). **No `DroppedItemRecord`. No `SkipReason`.**

That is precisely the never-silent breach that `_ensure_writing_systems`' own docstring
(`src/gramtrans/Lib/api.py:802-812`) was written to close:

> *"Without this, a source WS the target lacks (audio `*-Zxxx-x-audio`, IPA `*-fonipa`,
> a related-language variant, ...) is mapped by `to_ws_map_dict` to a target Id that does
> not exist, so every `ApplySyncableProperties` call SILENTLY DROPS that WS's content
> and the field lands empty (never-silent breach)."*

The pre-pass closes that hole for a tag genuinely absent from the store. It does **not**
close it for a tag present-but-inactive, because the guard it relies on cannot tell the
two apart.

### `Create` and "activate an existing WS" are conflated

flexicon has **no public method** to activate a store-present writing system.
`AddToCurrentVernacularWritingSystems` / `AddToCurrentAnalysisWritingSystems` are
reachable only from *inside* `Create`
(`WritingSystemOperations.py:265` / `:267`) — which refuses to run when `Exists` is
true. There is no `Add`, no `Activate`, no `Ensure`. Full public method list of
`WritingSystemOperations`: `GetAll`, `GetVernacular`, `GetAnalysis`, `Create`, `Delete`,
`Get/SetFontName`, `Get/SetFontSize`, `Get/SetRightToLeft`, `SetDefaultVernacular`,
`SetDefaultAnalysis`, `GetDefaultVernacular`, `GetDefaultAnalysis`, `GetDisplayName`,
`GetLanguageTag`, `Exists`, `GetBestString`, `Duplicate`, `GetSyncableProperties`,
`CompareTo`.

### Why it shipped: the unit fake makes the divergence unrepresentable

`tests/unit/test_ensure_writing_systems.py:50-54`:

```python
    def GetAll(self):  # noqa: N802
        return [_FakeWS(i) for i in self.proj["existing"]]

    def Exists(self, tag):  # noqa: N802
        return tag in self.proj["existing"]
```

`GetAll()` and `Exists()` read the **same** `existing` list, so "in the store but not
active" cannot be expressed by the fixture. The test suite is structurally incapable of
seeing this bug.

This is the **same trap** as the flexicon 4.5.0 `FeaturesOA` defect documented in
`CLAUDE.md`: all 1467 flexicon tests passed while the feature was 100% dead live,
because the tests built factory-fresh concrete-typed objects that never reproduced the
live base-interface view.

### Nothing in `specs/` owns this

- `specs/035-fullsweep-fidelity/object-inventory.md:178` and `:223` document
  `_ensure_writing_systems` **descriptively only** — *"Skips a tag already present. A
  failure is logged, not raised."* — with no fix task.
- Feature 038's only writing-system mentions (`tasks.md` T027, T029) concern
  natural-key **scoping** (which WS a comparison key is read from), which is unrelated.

---

## Two further findings

### F1 — `ws_wizard.py:146` calls a method that does not exist: FR-212's CREATE side-effect is 100% dead

`src/gramtrans/Lib/ui/ws_wizard.py:143-150`:

```python
            elif choice == WSChoice.CREATE:
                # Apply the CREATE side-effect (FR-212) if target was supplied.
                if self._target is not None:
                    try:
                        self._target.WritingSystems.Add(m.source_ws_id)
                    except (AttributeError, TypeError, Exception):
                        # Best-effort; the new WS may already exist from a
                        # prior wizard run on the same session.
                        pass
```

**`WritingSystemOperations` has no `Add` method**, and neither does its base
`BaseOperations` (`grep -n "def Add"` on `WritingSystemOperations.py` returns 0 matches;
on `BaseOperations.py` it matches only a docstring example at `:2264`). Every call
raises `AttributeError` straight into the `except`, disguised by a comment that blames a
benign cause. **FR-212's CREATE side-effect never executes** on the live
`src/gramtrans/gramtrans.py:559-568` (`_build_default_ws_resolver` -> `WSWizard`)
FlexTools path.

Severity note: this is the higher-severity of the two further findings, and it is
independently verified — the grep result is unambiguous.

### F2 — the PyInstaller build venv is below the declared dependency floor

```
build/.venv-build/Lib/site-packages/pyflexicon-4.4.1.dist-info
```

**4.4.1**, against `pyproject.toml`'s declared `pyflexicon>=4.5.2`. Any packaged `.exe`
built from that venv:

- **silently regenerates GUIDs** — the `guid=` kwarg raises `TypeError` on 4.4.x, which
  the engine's `_safe` / `except Exception` wrappers swallow into a generic
  "create failed" drop (feature 033);
- **transfers natural-class features as empty shells** — 4.4.x
  `NaturalClassOperations.GetSyncableProperties` never touches `FeaturesOA` at all
  (feature 037). See `CLAUDE.md` for why the floor is 4.5.2 and not 4.5.0/4.5.1.

The **source checkout is correct**: `import flexicon` resolves to
`D:\Github\_Projects\_LEX\flexicon\flexicon\__init__.py` (the working tree, not
site-packages) at version **4.5.2**.

---

## Proposed fix — NOT IMPLEMENTED

**Nothing below has been done.** No source file was modified by this investigation.
Most of the work belongs in **flexicon**.

### flexicon

1. **`WritingSystemOperations.Exists` (`:826`, body `:858`) must honour its own
   documented contract.** Its docstring says *"exists and is active"* (`:828`, `:834`)
   and *"Only checks active (vernacular or analysis) writing systems"* (`:849`); the
   MCP index says the same. The body scans the whole store. Fix: intersect
   `_GetWSByTag` against `_GetAllVernacularWSTags() | _GetAllAnalysisWSTags()`, exactly
   as `GetAll` already does at `:109-111`.

2. **`Create` (`:240-241`) must stop treating store-presence as "already exists".**
   For a tag present in the store but absent from `Cur*Wss`, skip
   `ws_manager.Create` / `ws_manager.Set` and call only
   `AddToCurrentVernacularWritingSystems` / `AddToCurrentAnalysisWritingSystems`.
   Cleanest shape is a new idempotent method:

   ```python
   WritingSystemOperations.Ensure(language_tag, name, is_vernacular) -> (ws, created: bool)
   ```

3. **Compare on the normalized language tag on both sides.** `Exists` normalizes via
   `_NormalizeLangTag` (`:937-947`, lowercase + `_` -> `-`) while
   `BaseOperations.py:1307` keys `target_ws_by_id` on **exact-case** `ws.Id`. That is a
   **second, independent live divergence**: `en-US` vs `en-us` passes `Exists` and
   misses the write map. Normalize the `target_ws_by_id` keys too.

4. **`FLExInit.py:66-73` must distinguish "already initialized" from a real SLDR
   failure** — inspect the exception, and re-raise (or at minimum log at ERROR) when it
   is not the benign case.

### GramTrans

5. Add `"flexicon"` to `src/gramtrans/Lib/debuglog.py:46 LOGGER_NAMES` so flexicon's
   warnings are no longer discarded.
6. `_ensure_writing_systems` (`src/gramtrans/Lib/api.py:802`) must emit a
   `DroppedItemRecord` / `SkipReason` instead of a bare `_log.warning` at `:881-884`,
   so a failed WS creation is reported to the user rather than swallowed.
7. Fix or remove the dead `WritingSystems.Add` call at
   `src/gramtrans/Lib/ui/ws_wizard.py:146`, and narrow its `except` clause — the
   `(AttributeError, TypeError, Exception)` tuple is a bare catch-all wearing a
   disguise.
8. Rebuild `build/.venv-build` against `pyflexicon>=4.5.2`, and add a build-time floor
   assertion so an under-floor venv fails the build instead of shipping a silently
   lossy `.exe`.

---

## Open questions

1. **Which message did the user actually see?** The report was "a failure warning about
   adding a writing system (English) that was already there". Three candidates produce
   English-plus-already-exists text: the (C) warning
   `_ensure_writing_systems: could not create WS 'en': FP_ParameterError: Writing system 'en' already exists`
   (never observed firing), the (B) `WS mapping not 1:1: 'en' and 'swh' both map to 'en'`
   crash dialog (observed, and fixed), and liblcm's own
   *"Unable to create writing system: en"* modal (the #179 symptom, produced by (A)).
   Not yet resolved.
2. **Why does `Sldr.Initialize(True)` fail?** A genuine DLL / offline-cache /
   permissions failure, or a prior `Sldr.Cleanup()` from `HostSession.release()` leaving
   the SLDR down for a later open in the same process? Settled by item (5) above — add
   `"flexicon"` to `LOGGER_NAMES` and re-run with `GRAMTRANS_DEBUG=1`.
3. **Did the user run a source checkout or a built `.exe`?** This determines whether
   they were on 4.5.2 (correct) or on the 4.4.1 build venv (F2), which changes the
   expected symptoms substantially.

---

## Verification performed for this report

| Claim | Result | Evidence |
|---|---|---|
| `WritingSystems.Add` does not exist on flexicon | **CONFIRMED** | `grep -n "def Add"` on `WritingSystemOperations.py` -> 0 matches; on `BaseOperations.py` -> only a docstring example at `:2264` |
| `Exists` docstring says "active", body scans whole store | **CONFIRMED** | docstring `:828`/`:834`/`:849`; body `:858` -> `_GetWSByTag` `:949-964` walks `AllWritingSystems` |
| Unit fake backs `GetAll()` and `Exists()` with one list | **CONFIRMED** | `tests/unit/test_ensure_writing_systems.py:50-54`, both read `self.proj["existing"]` |
| `build/.venv-build` on 4.4.1, active env on 4.5.2 | **CONFIRMED** | `pyflexicon-4.4.1.dist-info` in the build venv; `importlib.metadata.version("pyflexicon")` -> `4.5.2`, `flexicon.__file__` -> working tree |
| `3dcc6a6` is an ancestor of `HEAD` | **CONFIRMED** | `git merge-base --is-ancestor 3dcc6a6 HEAD` -> exit `0` |

## Filed issues

Both repositories have GitHub issue trackers enabled
(`MattGyverLee/GramTrans`, `MattGyverLee/flexicon`).

| Defect | Repo | Issue |
|---|---|---|
| (A) `Sldr.Initialize` swallowed failure | flexicon | [#249](https://github.com/MattGyverLee/flexicon/issues/249) |
| (C) `Exists` store-vs-active + `Create` conflation + missing `Ensure` + case divergence | flexicon | [#250](https://github.com/MattGyverLee/flexicon/issues/250) |
| (F1) dead `WritingSystems.Add`, FR-212 CREATE 100% dead | GramTrans | [#43](https://github.com/MattGyverLee/GramTrans/issues/43) |
| (C) silent drop + (5) logger gap + (F2) 4.4.1 build venv | GramTrans | [#44](https://github.com/MattGyverLee/GramTrans/issues/44) |
| (B) 1:1 WS mapping `ValueError` | — | already fixed by `3dcc6a6`; no issue filed |

Not a duplicate, but cross-referenced: a comment was added to flexicon
[#179](https://github.com/MattGyverLee/flexicon/issues/179#issuecomment-5338099124)
(CLOSED) noting that its `badldml.log` symptom recurred on the production GUI path from a
different cause, and that both of its own root causes are genuinely fixed and not
implicated. No reopen was requested.

No duplicates were found for any of the four issues. Search terms checked against both
trackers (`--state all`): `SLDR`, `writing system`, `Exists`, `LDML`, `badldml`,
`Sldr.Initialize`, `ws_wizard`, `FR-212`, `debuglog`, `pyflexicon`.

---

# Follow-up sweep — six candidate "deciding read vs guarding check vs writing read" sites, verified 2026-08-19

Everything above this line is the original report and is unchanged. This section records a
follow-up verification sweep that took the bug *shape* identified in section (C) — a
decision made against one collection, guarded against a second, and written against a
third — and hunted for siblings. Six candidate sites were examined. Each was pushed to a
verdict: does the divergence exist, and can it actually fire?

## Verdicts

| # | file:line | verdict | severity | can fire? |
|---|---|---|---|---|
| 1 | `Lib/ui/ws_wizard.py:146` | CONFIRMED mechanism, consequence overstated | dead code, latent | No — orphaned entry point |
| 2 | `Lib/ui/selection_wizard.py:1298` + `Lib/api.py:866` | CONFIRMED | silent data loss | Yes — firing today |
| 3 | `Lib/transfer.py:755` | PARTIAL | silent misread, end-state unproven | Yes on live path; no false-negative constructible |
| 4 | `Lib/texts.py:812` (key `:799`) | CONFIRMED (executed) | silent data loss | Yes — 328 texts / 25 projects |
| 5 | `Lib/ws_mapping.py:592` | KILLED | none | No — invariant + unreachable |
| 6 | `Lib/reversals.py:519` | PARTIAL, mechanism wrong | visible mid-write abort | Yes |

## #1 — `ws_wizard.py:146` — mechanism confirmed, severity overstated

Section F1 above says FR-212's CREATE side-effect is "100% dead". The **mechanism** is
confirmed three ways: `flexicon/code/System/WritingSystemOperations.py` has no `def Add`
(the creator is `Create(language_tag, name, is_vernacular=True)` at `:188`); the MCP index
lists 23 methods with no `Add`, `Activate` or `Ensure`; and live on `Ejagham Mini`
`hasattr(project.WritingSystems, 'Add')` is `False`. The
`except (AttributeError, TypeError, Exception)` at `:147` swallows it unconditionally.

The **consequence claim is wrong**. The call site is unreachable. `ws_wizard` is imported
only at `gramtrans.py:563` inside `_build_default_ws_resolver` (`:559`), called only from
`phase2_interactive_move` (`:397`) — which has **zero callers anywhere in the repo**. The
only references are prose: `specs/005-phonology-block/spec.md:127`,
`specs/006-inflection-prep-block/spec.md:133`, `STATUS.md:2754`, `STATUS.md:2807`. The
live path is `MainFunction` -> `_run_gui` -> `selection_wizard` -> `gt_api.execute_move`,
where FR-212's CREATE **is** implemented at `Lib/api.py:963` (`_ensure_writing_systems`).

**User-visible consequence today: none.** Re-read F1's severity as dead code carrying
latent risk, not active data loss. The risk is real if `phase2_interactive_move` is
revived: it calls `execute()` directly at `gramtrans.py:546`, bypassing
`_ensure_writing_systems`, at which point CREATE choices really would silently never
create. Correction posted to GramTrans
[#43](https://github.com/MattGyverLee/GramTrans/issues/43#issuecomment-5338263276); title
amended to drop "100% dead"; issue deliberately left OPEN.

## #2 — store-vs-active — confirmed FIRING, with a named reproduction

Section (C) filed this as LATENT / never-fired. It is not latent.

Three-way divergence, precisely: the **deciding read** is
`_target_ws_ids = _enumerate_active_ws_ids(target)` (`selection_wizard.py:1225`, def
`:6420`, `WritingSystems.GetAll()` at `:6431`), tested exact-case at `:1298`;
`closest_ws_defaults`' `tgt_ids` is likewise active-only (`ws_mapping.py:459` via
`_enumerate_ws`). The **guarding check** is `tgt_ops.Exists(tag)` at `api.py:866`. The
**writing reads** are `id_to_handle` (`texts.py:245`) and
`references._project_handle_to_id` (`:464`), both `GetAll()`.

flexicon side: `GetAll()` filters to `CurVernWss | CurAnalysisWss`
(`WritingSystemOperations.py:110-116`); `Exists()` -> `_GetWSByTag` (`:949-964`) scans the
unfiltered `AllWritingSystems` and normalizes case plus `-`/`_`.

**Named reproduction.** Source `Ejagham Full` (active vern `etu`, `etu-fonipa`; anal `en`,
`fr`) -> target `Ejagham Mini` (active vern `etu`; anal `en`; store ALSO holds inactive
LDMLs `es`, `etu-fonipa`, `etu-x-Eastern`, `fr`, `zh-CN`). Row `etu-fonipa`: absent from
`['etu','en']` -> `closest_ws_defaults` pass-3 rebase yields `("create","etu-fonipa")` ->
`WSMappingEntry(target_ws_id='etu-fonipa', create_in_target=True)` ->
`Exists('etu-fonipa')` is **True** via the inactive store copy -> `continue`, no create,
`_log.debug` only -> never activated -> `id_to_handle` lacks the key -> every
`etu-fonipa`-tagged string silently dropped. Same for `fr`.

**The triggering state is the norm.** A scan of all 88 local projects found store ⊋ active
in `Ejagham Full`, `Ejagham W Mini`, `Ejagham025Src`, `Ejagham029Src`, `EjaghamCfgSrc`,
`Korean-GIAL`, `Quenya`, `Egyptian Arabic Template`, `Lex Training Sample Project 1`,
`Iceve-Maci Test-Iceve`, `Iceve-Maci Test-Ici`, `German-FLExTrans-Sample`,
`Mbugwe LizzieHC practice`.

The case route is live-confirmed independently: `Exists('EN')` is `True` while
`'EN' in active_list` is `False`.

Structural note worth keeping: `WritingSystemOperations.Exists` at `api.py:866` is the
**only** whole-store tag-normalized WS lookup in GramTrans apart from `reversals.py:519`'s
`WSHandle`. Everything else is active-only exact-case `GetAll()` — `texts.py:125`,
`texts.py:245`, `references.py:464`, `reversals.py:139`, `categories.py:600`, `:604`,
`:2223`, `:7419`, `config_views.py:174`. One outlier guard in a uniformly active-only
codebase is exactly the shape that yields a false negative.

Evidence posted to flexicon
[#250](https://github.com/MattGyverLee/flexicon/issues/250#issuecomment-5338277832) and
GramTrans
[#44](https://github.com/MattGyverLee/GramTrans/issues/44#issuecomment-5338278157).

## #3 — `transfer.py:755` — PARTIAL; blocked on a contradiction in the docs

Scope is exactly `existing = target.Object(src_guid)` (`:754`) wrapped in
`except Exception: existing = None` (`:755-756`). `None` -> `return (False, None)`
(`:758-759`) = proceed with `Create`, with **no `DroppedItemRecord` and no `SkipReason`**.
Six live call sites, all on the production Move path, all feeding raw LCM factories
(`:833`): `:823` (PartOfSpeech), `:849` (MoInflAffixTemplate), `:876` (MoInflAffixSlot),
`:1378` (PhEnvironment), `:1406` (LexEntry), `:1433` (LexSense).

Live probe: `Object(<absent guid>)` raises `KeyNotFoundException` and
`Object("not-a-guid")` raises `FP_ParameterError`. So the bare `except` **is** the absence
signal — it cannot simply be narrowed without first distinguishing those two, and a
genuine false negative could not be constructed from the probes available.

**Unresolved contradiction — flag this prominently.** The two authorities disagree about
what LCM does on a duplicate GUID:

- `Lib/transfer.py:742-744`: *"LCM `factory.Create(existingGuid, owner)` does NOT throw --
  it silently creates a duplicate object permanently written to `.fwdata` on
  `CloseProject`."*
- flexicon `BaseOperations.py:1915-1918`: *"If the GUID is already present in the project,
  LCM raises and this falls back to a fresh identity, logging a warning that names the
  GUID."*

**One of the two is wrong**, and which one decides whether #3 is **data corruption**
(duplicate objects in `.fwdata`) or **identity loss** (a fresh GUID silently minted). The
severity of #3 cannot be set until this is settled.

Settling it needs exactly one write: against a **throwaway** project, create an object
with a GUID already present, then check `ObjectCountFor` and whether the returned object's
GUID matches the requested one. **Not** against `Ejagham Mini`, `Esperanto`,
`Mbugwe LizzieHC practice` or any other read-only test project.

## #4 — `texts.py:812` — CONFIRMED BY EXECUTION; largest measured loss

Deciding read `_text_disposition` (`texts.py:367-411`) = GUID scan -> `Find(title)` ->
structural fingerprint. Guarding check `Exists(name)` where
`name = plan.title or "(untitled)"` (`:799`), guard `:809-814` with
`except -> already_exists = False`. Writing read `Find(name)` (`:820`).

The three keys differ in flexicon: `GetName` reads the **source's** `DefaultAnalWs`
(`TextOperations.py:565-570`); `Exists` reads `BestAnalysisAlternative` over the
**target's** texts via `ObjectsIn(ITextRepository)` (`:457-467`); `Find` reads the
**target's** `DefaultAnalWs` over `GetAll()` (`:507-517`).

Executed against the repo's own fakes, empty target:

```
plan1 guid=src-A -> target guid='src-A' name='(untitled)'
plan2 guid=src-B -> target guid='src-A' name='(untitled)'   <- same object
texts in target: 1;  DroppedItemRecords: 0
```

Two distinct untitled source texts collapse into one; the second's GUID is never created;
its paragraphs are appended into the first's `StText`; `_added` is incremented for **both**
(`texts.py:759`).

**Scale, measured:** 328 of 1207 texts are untitled in their default analysis WS across 25
of 88 local projects — `Tlachichilco Tepehua-NT Noparse` 39/50, `Tlachichilco Tepehua`
36/46, `Mbugwe Lizzie` 34/44, `Isenye Nora` 30/42, `blx-flex` 29/107, `Ngoreme` 15/64,
`Vanaw` 10/26. Transferring `Tlachichilco Tepehua` into a clean target silently loses 38 of
39 untitled texts. `texts.py:371-373` itself calls empty titles "the common shape for
glossed/interlinear practice texts".

**Secondary, visible route:** a target text named only in a non-default analysis WS gives
`Exists` True / `Find` None, falling through to `Create`, whose own `Exists` check
(`TextOperations.py:150-156`) raises `FP_ParameterError` -> `DroppedItemRecord "text create
failed"`. So the `:809` mitigation **does not mitigate the case it was added for**.

Filed as GramTrans [#45](https://github.com/MattGyverLee/GramTrans/issues/45).

## #5 — `ws_mapping.py:592` — KILLED, twice over

The suspicion was that `fold_choices_into_ws_mapping` discards a rebased target on a
CREATE choice by writing `target_ws_id=c.source_ws_id` (`:592`) instead of
`c.target_ws_id`. It discards nothing, for two independent reasons:

1. **Invariant.** `WSMappingChoice.__post_init__` (`models.py:952-960`) raises
   `ValueError(f"target_ws_id must be empty for choice={self.choice.value}")` whenever
   `target_ws_id` is non-empty for a non-MAP choice. A CREATE choice carrying a rebased
   target is therefore **unconstructible** — `c.target_ws_id` is provably `""` at `:592`,
   so nothing is lost.
2. **Unreachable.** `fold_choices_into_ws_mapping` is called only from the orphaned
   `phase2_interactive_move` (`gramtrans.py:468`, `:488`) and from tests.

The rebased tag from `closest_ws_defaults` pass 3 (`ws_mapping.py:540-547`, e.g.
`mgz-fonipa-x-emic` -> `etu-fonipa-x-emic`) reaches the plan by a **different** route:
`selection_wizard.py:1414-1450` (`ws_mapping()`), which **does** honour it —
`target_ws_id=create_target` at `:1437`. No defect.

## #6 — `reversals.py:519` — PARTIAL, and the presumed mechanism was wrong

The gate `_target_ws_ids = target.WritingSystems.GetAll()` (`reversals.py:139`) is applied
at `:461` to **the reversal index's own WS only**. Alt WSs are **never gated**:
`_reversal_form_alts` passes an unmapped source id straight through
(`:236`, `ws_map.get(src_id, src_id)`). The write read `target.WSHandle(ws_id)` (`:519`)
scans `AllWritingSystems` normalizing case and `-`/`_`
(`FLExProject.py:2814-2834`, `__NormaliseLangTag` at `:3292`) and returns `None` on a miss
— live-verified: `WSHandle('zz-absent')` is `None`.

**The escape, live-verified.** Python evaluates `TsStringUtils.MakeString(text, None)`
*before* `set_String`, and it raises `System.ArgumentNullException`, whose MRO is
`ArgumentNullException -> ArgumentException -> SystemException -> Exception`. So
`isinstance(e, TypeError)` is **False** and it **escapes** the
`except (AttributeError, TypeError)` at `:521`. This is why the verdict is "mechanism
wrong": the failure is not a swallowed silent drop, it is an uncaught throw one call
earlier than the handler anticipated.

**Nothing catches it upstream.** The alt-write loop (`:919-922`) has no `try`;
`_apply_one_entry` and `apply_reversals` (`:950-959`) both *claim* "Never raises" in their
docstrings and do not; the calls at `transfer.py:521` and `categories.py:5471` are bare.

**Consequence:** the Move aborts **mid-write** — after all lexical and text writes, before
the config-view copy and the summary. A visible crash on a partially-written target, not a
reported drop.

**Scenario:** a source with an active `mgz-fonipa-x-etic` reversal alt whose index WS is
`en` (so the gate passes on `en`), transferred into a target lacking `mgz-fonipa-x-etic`.

Filed as GramTrans [#46](https://github.com/MattGyverLee/GramTrans/issues/46).

## Cross-cutting cause: self-consistent test fakes

Every confirmed bug in this sweep shares one enabling condition. The unit fake collapses
the divergent collections into a single source of truth, making the bug **structurally
unrepresentable** — so no test could have caught it, however thorough:

- `tests/unit/test_ensure_writing_systems.py:50-54` — `GetAll()` and `Exists()` are two
  reads of one `proj["existing"]` list. Store-vs-active cannot be expressed.
- `tests/unit/_fakes_texts.py:236-262` — `GetName`, `Find` and `Exists` are three reads of
  one `t.name` scalar. The source-DefaultAnalWs / BestAnalysisAlternative /
  target-DefaultAnalWs split cannot be expressed.
- `tests/unit/test_p0_idempotency_ws.py:51-64` — `fake_object` raises a generic
  `Exception` for absence only, so "lookup failed" is indistinguishable from "absent" and
  the `transfer.py:755` conflation cannot be expressed.

This is the same shape as the flexicon 4.5.0 `FeaturesOA` trap documented in `CLAUDE.md`:
1467 tests green over factory-fresh CONCRETE-typed objects while the live path, which
yields base-typed proxies, was 100% dead. **A fake that is more self-consistent than the
API it doubles converts a real defect into an untestable one.** Any fix in this area should
begin by making the fakes diverge the way the real API diverges.

## Fix first — three, in order

1. **#4, `texts.py:799`/`:812`** — the largest measured silent loss (328 texts, 25
   projects), proven by execution, and it hits a *first* Move into a clean target, which is
   the normal case. An untitled text has no name-based identity; the placeholder string
   must stop being used as a lookup key. Create unconditionally under the source GUID
   (`texts.py:830` already passes `guid=plan.source_guid`).
2. **#2, `api.py:866`** — firing today on ordinary projects, and silent. GramTrans can
   mitigate ahead of flexicon #250 by testing the tag against the **same** active-only set
   the decider and writer use, and treating "`Exists` true but not active" as a distinct
   *reported* outcome instead of a `_log.debug` skip.
3. **#6, `reversals.py:519` + the two docstrings** — the only candidate that leaves a
   partially-written target. Gate the alts at decision time and record a
   `DroppedItemRecord`; widening the `except` alone would only trade a crash for a silent
   drop. Fix or delete the two "Never raises" docstrings — they are actively misleading
   maintenance.

**#3 is not on this list on purpose.** It needs the throwaway-project probe below before
its severity can even be assigned; fixing it blind risks narrowing the one `except` that
currently carries the absence signal.

## Undetermined — two questions this sweep could not close

1. **Does LCM throw on a duplicate GUID?** `transfer.py:742-744` and flexicon
   `BaseOperations.py:1915-1918` state opposite behaviours (see #3). This decides whether
   #3 is data corruption or identity loss. Resolution: one write against a **throwaway**
   project — create an object with a GUID already present, check `ObjectCountFor` and
   whether the returned object's GUID matches the requested one. Never against a read-only
   test project.
2. **Does the fingerprint fallback rescue any of the 328 untitled texts on a *non-empty*
   target?** The #4 proof used an empty target, where `_text_disposition`'s structural
   fingerprint (`texts.py:402-411`) has nothing to match against. On a populated target it
   may return `UPDATE` with a real `target_guid` and short-circuit at `:791` before the
   placeholder is synthesized. Residual loss is unquantified. Resolution: a live
   repeat-Move against a populated target, comparing target text count and GUID set
   before/after.

## Two incidentals recorded in passing

- **`WritingSystemOperations.py:906` `GetBestString` is dead on liblcm 11.0.0.** Its body
  does `from SIL.LCModel.Core.KernelInterfaces import IMultiUnicode, IMultiString`, which
  raises `ImportError` on liblcm 11.0.0 — live-verified. Harmless here only because
  GramTrans never calls it; worth an upstream note.
- **`"(untitled text)"` vs `"(untitled)"`.** `Lib/selection.py:3795` labels untitled texts
  `"(untitled text)"` in the selection inventory while `Lib/texts.py:799` creates them as
  `"(untitled)"`. The UI shows one string and the target receives another. Note that making
  them agree is **not** a fix for #4 — any shared constant is still a colliding key.

## Issues filed or amended by this sweep

| Item | Repo | Issue | Action |
|---|---|---|---|
| #1 severity correction | GramTrans | [#43](https://github.com/MattGyverLee/GramTrans/issues/43) | correcting comment + title amended; left OPEN |
| #2 firing-today evidence | flexicon | [#250](https://github.com/MattGyverLee/flexicon/issues/250) | evidence comment |
| #2 firing-today evidence | GramTrans | [#44](https://github.com/MattGyverLee/GramTrans/issues/44) | evidence comment |
| #4 untitled-text collision | GramTrans | [#45](https://github.com/MattGyverLee/GramTrans/issues/45) | NEW |
| #6 reversal mid-write abort | GramTrans | [#46](https://github.com/MattGyverLee/GramTrans/issues/46) | NEW |
| #3 duplicate-GUID contradiction | — | not filed | blocked on the throwaway-project probe |
| #5 `ws_mapping.py:592` | — | not filed | KILLED — no defect |
