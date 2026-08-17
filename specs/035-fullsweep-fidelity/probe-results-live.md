# Probe results: LIVE EXECUTION (feature 035 fullsweep-fidelity)

Route used: standalone Python process. No FLExToolsMCP tool was present in
this session's tool list (checked before starting); this is the documented
fallback in the task brief. All calls below ran for real via pythonnet
against a live, read-only-opened FLEx project -- nothing here is read out
of C# source. Script: `debug/probe_field_census_api.py` (tracked, ASCII,
refuses `^Target([0-9]+)?$` project names by construction).

Read-only guarantee: every `OpenProject` call used `writeEnabled=False`.
No Save/Commit/Undo/Redo/mutating class was imported. No project named
Target or Target* was opened (the guard was smoke-tested and correctly
raised `SystemExit` for `--project "Target"`).

## Part 1 -- claim-by-claim results

### C1. Managed metadata cache cast -- CONFIRMED-LIVE
`proj.Cache.MetaDataCacheAccessor` resolves, at the pythonnet layer, to the
BASE interface `IFwMetaDataCache` (confirmed: calling `.GetFields(...)`
uncast raises, live, `TypeError: No method matches given arguments for
IFwMetaDataCache.GetFields: (int, bool, int)` -- not `AttributeError` as
the source-only probe guessed, but the underlying claim, cast required,
is confirmed exactly). `IFwMetaDataCacheManaged(mdca)` succeeds; `GetFields`,
`get_IsVirtual`, `IsCustom`, `GetFieldWs`, `GetFieldListRoot` all resolve
and return live values (e.g. `get_IsVirtual(f0)=True`, `IsCustom(f0)=False`,
`GetFieldListRoot(f0)` returns a `System.Guid`).

### C2. `.All` sentinel bypasses the bitmask check -- CONFIRMED-LIVE
On LexEntry (clid 5002, 252 live instances in Ejagham Mini):
`GetFields(clid, True, int(CellarPropertyTypeFilter.All))` and
`GetFields(clid, True, 0x7FFFFFFF)` return **identical** sets: 57 fields
each, field types `{1,2,5,6,13,14,15,16,23,24,25,26,27,28}` -- i.e. Boolean,
Integer, Time, Guid, String, MultiString, Unicode, MultiUnicode fields ARE
present. `CellarPropertyTypeFilter.All == 528482304` is literally
`AllOwning|AllReference` (bits for types 23-28 only); if the implementation
used it as a literal bitmask, only types 23-28 could ever match. Their
live presence proves the sentinel bypass. Contrast case run in the same
session: a genuine non-`.All` mask (`MultiString|MultiUnicode`, int 81920,
not equal to `.All`) DOES restrict correctly -- 9 fields, types
`{14,16}` only -- proving masking works normally and `.All` is a real,
deliberate special case, not a broken filter.

### C3. Populated WS-alternative enumeration -- CONFIRMED-LIVE
`ms.GetStringFromIndex(i)` resolves through pythonnet to a plain 2-tuple
(the C# `out` parameter becomes a second Python return value, no explicit
out-arg needed). Live on `LexSense.Gloss` (flid 5016008), a sense with
`StringCount=2`:

```python
ms = sda.get_MultiStringProp(hvo, flid)      # ITsMultiString
for i in range(ms.StringCount):
    tss, ws = ms.GetStringFromIndex(i)        # tuple(ITsString, int)
```

Observed: `i=0 ws=999000001 text='two:CLS5,9; pair'`,
`i=1 ws=999000005 text='deux'`.

### C4. Native `ITsString` equality -- CONFIRMED-LIVE
`ITsString(s1).Equals(s2)` resolves and works as designed; an **uncast**
`s1.Equals(s2)` resolves to the same result too (pythonnet picks the
correct overload without an explicit `ITsString()` wrapper in this build).
Built two same-text strings via `TsStringUtils.MakeString(text, ws)` /
`MakeString(text, ws, styleName)` (both project-agnostic factory calls,
no pre-existing style needed):

```python
from SIL.LCModel.Core.KernelInterfaces import ITsString
from SIL.LCModel.Core.Text import TsStringUtils
s1 = TsStringUtils.MakeString("probe-word", vern_ws)
s2 = TsStringUtils.MakeString("probe-word", anal_ws)          # different WS
s3 = TsStringUtils.MakeString("probe-word", vern_ws, "Emphasis")  # diff style
ITsString(s1).Equals(s1b)      # -> True  (identical)
ITsString(s1).Equals(s2)       # -> False (WS differs, .Text WOULD be equal)
ITsString(s1).Equals(s3)       # -> False (char style differs)
```
Confirmed live: `s1.Text == s2.Text` is `True` even though `.Equals` is
`False` -- proves a naive `.Text ==` compare (as in `check_text_fidelity.py`)
would miss a silent WS change that native `.Equals` catches.

### C5. Virtual/structural exclusion -- CONFIRMED-LIVE
On LexEntry (57 total fields via the `.All` sentinel): `flid < 200`
(structural) removes 4 fields; `get_IsVirtual` removes 30 fields; overlap
between the two predicates is 0 (as the design doc predicted -- they are
independent, both-necessary exclusions). 23 fields remain after both are
applied.

### Item 4 (decorator spot-check) -- CONFIRMED-LIVE
`MetaDataCacheAccessor.GetType().FullName` (both before AND after the
`IFwMetaDataCacheManaged` cast) is
`SIL.LCModel.Infrastructure.Impl.LcmMetaDataCache` -- the direct
implementation, not `MetaDataCacheDecoratorBase` or any subclass. No
decorator wrapping observed on this project's open path.

### Bonus finding: undoable/unit-of-work default vs. version string
Installed `pyflexicon` reports version **4.3.1** (`pip show pyflexicon`),
yet the SAME checked-out source's `OpenProject` signature (confirmed via
`inspect.signature`, no write access needed) already is
`(self, projectName, writeEnabled=False, undoable=True, ui=None)`, and its
own docstring says this `undoable=True` default has been in effect
"since 4.4.0". **The breaking default already shipped under the 4.3.1
version label** -- the version string was not bumped when the default
changed. At runtime, for a READ-ONLY open (`writeEnabled=False`), the
effective `proj._undoable` attribute is observed to be `False` regardless
of the `undoable` argument, because flexicon computes
`_undoable = undoable and writeEnabled` -- `undoable` is only load-bearing
when `writeEnabled=True`, which this read-only-only task cannot exercise
live. Recommend: bump the version string, or add a runtime-visible
attribute/log line stating the effective undoable mode at every
`OpenProject` call regardless of write-enablement, so silent-default
drift like this cannot recur unnoticed.

### Stale-lock finding (Ejagham Mini)
The Ejagham Mini `.fwdata.lock` file recorded PID 13364
(`ProcessName: GramTrans-portable`), confirmed DEAD (`Get-Process -Id
13364` returned nothing). `XMLBackendProvider.LockProject()` is called
unconditionally on EVERY open (read or write) via `SimpleFileLock`. Live
result: the read-only open of Ejagham Mini **succeeded** in every run
(open times 2.30-2.52s) -- the stale lock did NOT block a read-only open.
Per task instructions the lock file was left untouched.

## Part 2 -- measured numbers

| Metric | Value |
|---|---|
| Ejagham Mini open (read-only), run 1 | 2.348 s |
| Ejagham Mini open (read-only), run 2 | 2.303 s |
| Ejagham Mini open (read-only), run 3 (hold-mode child) | 2.318-2.522 s |
| Full per-field census, most populous class found (`IWfiAnalysisRepository`, 279 objects, 1 clid) | 2511 field reads, 0 skipped, 0 errors, **0.102 s** (~24,700 reads/s) |

Peak process working-set memory, ONE project per SEPARATE subprocess,
strictly sequential (never two open at once), sampled via
`psutil.Process(pid).memory_info().peak_wset` while the child held the
project open:

| Project | fwdata size | wall time to HELD | peak working set |
|---|---|---|---|
| Ejagham Mini | 11,730,543 B (11.2 MB) | 3.43 s | 193,781,760 B (184.8 MB) |
| Mbugwe LizzieHC practice | 11,112,552 B (10.6 MB) | 3.60 s | 196,247,552 B (187.2 MB) |
| Esperanto | 188,263,966 B (179.5 MB) | 5.82 s | 523,567,104 B (499.3 MB) |

Esperanto opened in under 6 seconds -- far short of the 10-minute
abandon threshold; no timeout was needed.

**Slope observed:** ~185-190 MB is a roughly FIXED per-process floor (CLR
host + LCM/FLEx assembly load) essentially independent of the two ~11 MB
projects. Esperanto adds ~310-335 MB of RAM over that floor for ~168 MB
of extra fwdata -- approximately **1.9 MB RAM per 1 MB of fwdata** above
the fixed floor. Scheduling rule of thumb for ~4.4 GB free RAM: floor(4400
/ 190) is approx. 23 sequential/parallel small-project workers by RAM
alone (not a concurrency-safety claim -- concurrency itself was
explicitly out of scope this session); for Esperanto-sized (~180 MB)
projects, floor(4400 / 500) is approx. 8 workers.

## Not exercised (read-only constraint)

- Live `undoable=True` write-mode behavior itself -- correctly out of
  scope (write disabled by task instructions); the version-string finding
  above is based on source/introspection, not a write-mode live run.
- Binary/Image/Numeric/Float `CellarPropertyType` field reads in the
  census dispatch table -- rare/unused in the model (Numeric/Float are
  documented unused as of 2013); skipped by design, not a gap in the
  claims tested.

## Tally
CONFIRMED-LIVE: C1, C2, C3, C4, C5, item-4 decorator spot-check (6/6).
REFUTED-LIVE: none.
NOT-TESTABLE: none of C1-C5; write-mode `undoable=True` behavior is
NOT-TESTABLE this session by design (read-only constraint).
