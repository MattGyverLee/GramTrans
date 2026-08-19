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
