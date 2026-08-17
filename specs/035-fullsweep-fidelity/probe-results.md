# Probe results: generic per-object field census (feature 035)

Design research only. No source file modified; no FLEx project opened
write-enabled.

## Method note (VERIFIED vs INFERRED)

FLExToolsMCP was not reachable as a callable tool in this session (no MCP
tool surfaced to this agent). Per the task's fallback instruction,
findings are grounded directly in the **liblcm C# source**
(`D:\Github\_Projects\_LEX\liblcm\src\`, the actual implementation
flexicon/LCM ships from) and this repo's own prior art
(`tests/verification/fidelity_census.py`, `specs/024-lexicon-reference-
fidelity/contracts/fidelity-census.md`, `src/gramtrans/Lib/categories.py`,
`debug/check_text_fidelity.py`).

- **VERIFIED (source)**: read directly from liblcm `.cs` source, or from
  flexicon/GramTrans Python that already calls it in this repo.
- **INFERRED**: reasoned from adjacent verified code, not read letter-for-
  letter at the exact call site.

Nothing below was confirmed by live MCP/execution this session; VERIFIED
(source) is strong (shipping implementation, not docs) but a live smoke
test against Ejagham Mini is still recommended before this becomes
production code.

Key files consulted: `SIL.LCModel.Core/Cellar/CellarPropertyType{,Filter}.cs`,
`SIL.LCModel/Infrastructure/{IFwMetaDataCacheManaged,Impl/
LcmMetaDataCache}.cs`, `SIL.LCModel/Application/Impl/DomainDataByFlid.cs`,
`SIL.LCModel/DomainServices/CopyObject.cs` (LCM's OWN generic per-object
field-walking deep-copy engine -- the most valuable find here),
`SIL.LCModel.Core/Text/{TsString,TsRun,TsTextProps}.cs`, `LcmCache.cs`,
flexicon's `FLExProject.py`, and this repo's `categories.py` /
`fidelity_census.py`.

---

## Q1. Reaching the managed metadata cache

**VERIFIED (source).** `LcmCache.MetaDataCacheAccessor`
(`LcmCache.cs:882`) is declared to return the **base** `IFwMetaDataCache`,
NOT `IFwMetaDataCacheManaged`. The members this census needs
(`GetFields` returning `int[]`, `get_IsVirtual`, `IsCustom`, `GetFieldWs`,
`GetFieldListRoot`) live only on `IFwMetaDataCacheManaged`, so the cast is
**required**, not stylistic -- every call site in flexicon and in this
repo's `categories.py` performs it:

```python
from SIL.LCModel.Infrastructure import IFwMetaDataCacheManaged
mdc = IFwMetaDataCacheManaged(proj.Cache.MetaDataCacheAccessor)
```

An alternative, `cache.ServiceLocator.GetInstance<IFwMetaDataCacheManaged>()`
(used internally by LCM's own `CopyObject<T>`), exists in C#, but
flexicon's own `GetFactory()` docstring documents pythonnet's generic
`GetInstance<T>()` as unreliable via `[T]` subscript across builds --
every Python call site in this codebase uses the direct cast above
instead. Use that.

---

## Q2. Enumerating fields of a class

**VERIFIED (source).** Signature (`IFwMetaDataCacheManaged.cs:46`,
impl `LcmMetaDataCache.cs:816`): `int[] GetFields(int clid, bool
includeSuperclasses, int fieldTypes)`. **clsid** from a live object:
`obj.ClassID` (plain int property; used the same way in flexicon's
`FLExProject.py:2892`).

**What "all" means -- the most surprising finding of this probe.**
`CellarPropertyTypeFilter.All` (`CellarPropertyTypeFilter.cs:37`) is
literally `AllOwning | AllReference` (528482304) -- a naive reading says
"only owning/reference, not String/Integer/Boolean". **That's wrong.**
`LcmMetaDataCache.IsMatchingFieldType` (`:846-857`) special-cases the
literal `.All` int as a sentinel: if `fieldTypes == (int)
CellarPropertyTypeFilter.All` exactly, the bitmask check is skipped
entirely and *every* field matches, of every type. This is why LCM's own
generic deep-copy engine passes exactly this value
(`CopyObject.cs:610-613`, `GetAllFieldsFromClassId`) to get literally
every field. A second, non-sentinel way also works: pass `0x7FFFFFFF`
(all real `CellarPropertyType` values are 0-28, so `1 << flidType` always
falls inside that mask) -- this is what `fidelity_census.py`'s own
docstring says it used for its live MCP snapshot.

**Recommendation:** mirror LCM's own blessed internal call:

```python
from SIL.LCModel.Core.Cellar import CellarPropertyTypeFilter
flids = mdc.GetFields(obj.ClassID, True, int(CellarPropertyTypeFilter.All))
```

**Marshaling:** this is the `[ComVisible(false)]` managed `int[]`
overload (`LcmMetaDataCache.cs:816`), not the 5-arg COM/`ArrayPtr`
overload. Flexicon iterates it directly, no preallocation
(`FLExProject.py:3696`): `for flid in mdc.GetFields(classID, False,
int(CellarPropertyTypeFilter.All)):`.

---

## Q3. Per-flid metadata

**VERIFIED (source),** all from `LcmMetaDataCache.cs`:

| Method | Line | Returns |
|---|---|---|
| `GetFieldName(flid)` | 352 | bare name, e.g. `"Senses"` |
| `GetFieldLabel(flid)` | 361 | user-facing label |
| `GetFieldType(flid)` | 418 | `int` cast of pure `CellarPropertyType` |
| `get_IsVirtual(flid)` | 763 | `bool`, true iff `FieldSource.kVirtual` |
| `IsCustom(flid)` | 995 | `bool`, true iff `FieldSource.kCustom` |
| `GetOwnClsId(flid)` | 334 | declaring clsid |
| `GetDstClsId(flid)` | 343 | destination clsid (object-valued fields) |
| `GetFieldWs(flid)` | 401 | WS selector (custom fields) |
| `GetFieldListRoot(flid)` | 392 | possibility-list root GUID (custom list fields) |

`MetaFieldRec.m_fieldType` is a pure `CellarPropertyType`
(`LcmMetaDataCache.cs:1436`); `Virtual` is a **separate** derived bool
(`m_fieldSource == FieldSource.kVirtual`, `:1450`) -- virtual-ness is not
bit-packed into the type int here. `GetFieldType` returns a clean 0-28
value (this repo's `categories.py:1073` masks with `& 0x1F` defensively;
harmless but not required against this implementation).

**CellarPropertyType values** (VERIFIED, `CellarPropertyType.cs`):
`Nil=0, Boolean=1(Min), Integer=2, Numeric=3(unused), Float=4(unused),
Time=5, Guid=6, Image=7, GenDate=8, Binary=9, String=13, MultiString=14,
Unicode=15, MultiUnicode=16, OwningAtom=23(MinObj)/OwningAtomic(alias),
ReferenceAtom=24/ReferenceAtomic(alias), OwningCollection=25,
ReferenceCollection=26, OwningSequence=27, ReferenceSequence=28, Lim=29`.

**FLAG -- conflicting mirror inside flexicon.**
`flexicon/code/Shared/lcm_constants.py` defines its OWN
`class CellarPropertyType` with **different, wrong-looking values**
(`Boolean=20, Integer=6, String=2, MultiString=13, MultiUnicode=14,
Guid=15, Time=4, GenDate=16, Binary=17, Object=23, ...`), imported by
`FLExLCM.py` under the same name (shadowing the real one in that one
module only). Everywhere else (`FLExProject.py`,
`System/CustomFieldOperations.py`, this repo's `categories.py`) the REAL
`SIL.LCModel.Core.Cellar.CellarPropertyType` .NET enum is used, matching
the table above. **Import `CellarPropertyType` directly from
`SIL.LCModel.Core.Cellar`** for this feature -- never from
`flexicon.code.Shared.lcm_constants` / `flexicon.code.FLExLCM`.

---

## Q4. Reading values generically (`ISilDataAccess`)

**Obtaining it (VERIFIED):** `proj.Cache.DomainDataByFlid`
(concrete impl `SIL.LCModel/Application/Impl/DomainDataByFlid.cs`).

**VERIFIED dispatch table**, taken letter-for-letter from LCM's own
generic field-copier `CopyObject.HandleBasicOrStringFlid` (`:468-525`):

| CellarPropertyType | Getter | Type |
|---|---|---|
| Binary | `((ISilDataAccessManaged)sda).get_Binary(hvo,tag,out rgb)` (.NET-friendly; not `get_BinaryProp`) | `byte[]` |
| Boolean | `get_BooleanProp(hvo,tag)` | `bool` |
| Guid | `get_GuidProp(hvo,tag)` | `Guid` |
| GenDate | `get_IntProp` (raw int; `get_GenDateProp` decodes) | `int`/`GenDate` |
| Integer | `get_IntProp(hvo,tag)` | `int` |
| Time | `get_TimeProp` (raw SilTime ticks; `get_DateTime` decodes) | `long` |
| String | `get_StringProp(hvo,tag)` | `ITsString` (never null) |
| Unicode | `get_UnicodeProp(hvo,tag)` | plain string |
| MultiString/MultiUnicode | `get_MultiStringProp` -> `ITsMultiString`, iterate `StringCount`+`GetStringFromIndex` | see Q5 |
| ReferenceAtom / OwningAtom | `get_ObjectProp(hvo,tag)` | `int` hvo (0=unset) |
| Ref/Own Collection/Sequence | `get_VecSize`+`get_VecItem` loop | `int` hvo per item |

**Exception behavior on unset properties (VERIFIED from the actual
`DomainDataByFlid.cs` bodies, not just doc comments):**
- `get_ObjectProp`/`get_GuidProp`/`get_IntProp` do **not** throw for a
  legitimately-unset value on a valid hvo/flid pair -- they return the
  type default (0 / `Guid.Empty`), per their own doc comments.
- `get_StringProp` **never** returns null -- empty `ITsString` in the
  field's default WS (`:542-562`). `get_MultiStringAlt` likewise never
  null (`:589-596`).
- `get_IntProp` catches `KeyNotFoundException` but only swallows it for
  the special `kflidClass` tag; re-throws otherwise (`:233-246`). A
  census reading only flids from `GetFields(obj.ClassID, ...)` for that
  object's own/base class should never hit this -- don't wrap the read
  loop in a blanket `except`; if it fires, the flid/class pairing is
  wrong and should surface, not be swallowed.
- `get_VecSize` on a never-populated collection legitimately returns 0.

---

## Q5. Enumerating populated WS alternatives

**VERIFIED (source)** -- cleanest finding here, straight from LCM's own
copier (`CopyObject.cs:512-521`):

```csharp
ITsMultiString sMulti = m_sda.get_MultiStringProp(hvoSrc, thisFlid);
for (int i = 0; i < sMulti.StringCount; i++) {
    int ws;
    ITsString tss = sMulti.GetStringFromIndex(i, out ws);
}
```

Python:

```python
ms = sda.get_MultiStringProp(hvo, flid)          # ITsMultiString
for i in range(ms.StringCount):
    tss, ws = ms.GetStringFromIndex(i)            # out-param -> 2nd return
```

Confirms the task's guess exactly. **Do not** probe every project WS (the
`CurrentAnalysisWritingSystems | CurrentVernacularWritingSystems` pattern
flexicon's `GetCustomFieldValue` uses, `FLExProject.py:3300-3329`) --
that's a UI "best single value" convenience for a different purpose and
would both miss WSs outside those lists and waste calls on WSs never
touched.

---

## Q6. `ITsString` equality -- catching distortion, not just `.Text ==`

**VERIFIED (source),** second load-bearing finding. `ITsString.Equals`
is real (`TextServ.idh:790-792`; managed impl `TsString.cs:158-162` ->
`:567`):

```csharp
public bool Equals(ITsString tss) { var o = tss as TsString; return o != null && Equals(o); }
public bool Equals(TsString other) { return other != null && m_text == other.m_text && m_runs.SequenceEqual(other.m_runs); }
```

Tracing `m_runs.SequenceEqual` (all VERIFIED):
- `TsRun.Equals` (`TsRun.cs:39-42`): `m_ichLim == other.m_ichLim &&
  m_textProps.Equals(...)` -- run **count** and every run's boundary
  must match (catches a run silently split/merged).
- `TsTextProps.Equals` (`TsTextProps.cs:74-97`): compares BOTH
  `IntProperties` and `StringProperties` as full ordered dicts
  (count + key + value at every entry). WS is the `ktptWs` int prop
  inside `IntProperties`, so a silently changed run WS is caught by this
  same comparison, along with italic/bold/superscript/font-size/named-
  style -- nothing normalized away.

**Net answer:** don't hand-roll a comparator; call native equality:

```python
from SIL.LCModel.Core.KernelInterfaces import ITsString
are_equal = ITsString(src_tss).Equals(tgt_tss)   # False on: text diff,
    # run-count diff, run-boundary diff, WS diff, or any style-prop diff
```

This directly names the gap in this repo's own `debug/
check_text_fidelity.py` (`_text_shape`/`main`), which compares only
`s_txt == t_txt` (plain `.Text`) and would NOT catch a silently-changed
run WS/style even with byte-identical characters -- a concrete example of
the exact bug class this feature must catch generically. (That script is
a debug tool, not this task's deliverable; flagged for context only.)

Caveat (INFERRED, not exercised live): pythonnet overload resolution
across `object.Equals`, `TsString.Equals(TsString)`, and
`TsString.Equals(ITsString)` was not exercised this session; all three
compute the same comparison, but a live smoke test is recommended.

---

## Q7. Identifying and excluding virtual/derived/back-reference fields

**VERIFIED (source).** Two independent, both-necessary exclusions from
LCM's own walker (`CopyObject.cs:181-188`, `:344-356`):

```csharp
if (thisFlid < 200 || m_cache.IsReferenceProperty(thisFlid) || m_mdc.get_IsVirtual(thisFlid))
    continue;
```

1. **`get_IsVirtual(flid)`** -- backed by `FieldSource`
   (`FwKernel.idh:1150-1155`: `kModel=0`/`kCustom=1`/`kVirtual=2`,
   mutually exclusive). True iff `FieldSource.kVirtual` ("added by
   program"). Matches `fidelity_census.py`'s own provenance note. Do
   NOT conflate with `IsCustom` (`kCustom` = genuine user field, must be
   INCLUDED). `LexEntry.MainEntriesOrSensesRS` (this repo's one
   `OUT_OF_SCOPE_EXCLUDED` field) is the poster child.
2. **`thisFlid < 200`** -- structural `CmObject` fields (Guid, owner,
   owning flid/ord, class id), already set at object-creation time, not
   discovered generically. A census should treat the object's own
   `Guid`/`Owner`/`OwningFlid`/`ClassID` (already surfaced by the 033
   GUID machinery) as out of the generic field loop.

Neither predicate alone suffices: `thisFlid < 200` catches non-virtual
structural fields; `get_IsVirtual` catches computed aggregates at
ordinary (>=200) flids. Use both.

---

## Q8. Cost for a full census over ~30k objects

**INFERRED** (no live timing taken; reasoned from the verified shapes
above plus this repo's own field-count precedent).

- **Cache `GetFields` per class, not per object.** The flid list depends
  only on `clid`. LCM has ~100-150 concrete classes, so memoize
  `clid -> flid[]` once; a 30k-object sweep becomes ~100-150 `GetFields`
  calls + 30k dict lookups, not 30k `GetFields` calls.
- **Confirmed trap (Q5): never probe every project WS per MultiString
  field per object.** `get_MultiStringProp` once + `StringCount`
  iterations (only populated WSs) is the LCM-native shape;
  `get_MultiStringAlt` looped over every configured project WS
  multiplies calls by WS count for nothing.
- **pythonnet call overhead, not per-property algorithm cost, is the
  real driver.** Each getter crosses the Python/.NET boundary once; for
  ~15-30 real fields/object (per `fidelity_census.py`'s
  `EXPECTED_MODEL_FIELDS`) a 30k-object sweep is several hundred
  thousand to low millions of calls -- plausible for an **offline batch/
  CI harness** (exactly how this repo already treats `fidelity_census.py`
  and `check_text_fidelity.py`, both explicitly "not invoked during a
  live transfer"): tens of seconds to a few minutes, not sub-second. Not
  acceptable per-click inside the interactive wizard.
- **Cheapest correct shape:** (1) memoize `clid -> (flid, name, type,
  is_virtual)[]` once per class from `GetFields(clid, True, int(
  CellarPropertyTypeFilter.All))`, dropping `flid<200` and
  `get_IsVirtual`; (2) per object, dispatch each cached flid through the
  Q4 table (one call per scalar/string field; `StringCount`-bounded loop
  per multi-field; `VecSize`-bounded loop per vector field, never a
  per-WS probe); (3) for GUID-keyed source/target comparison, read once
  per side and compare in Python, not via a second LCM round-trip.

---

## UNRESOLVED

1. **No live timing data** -- Q8 is reasoned, not measured.
2. **pythonnet overload resolution for `ITsString.Equals`** (Q6) not
   exercised live.
3. **FLExToolsMCP unavailable this session** -- all findings come from
   direct liblcm C# source instead. A follow-up session with MCP access
   should spot-check the VERIFIED claims above against a live Ejagham
   Mini `IFwMetaDataCacheManaged` to rule out a build-specific fork.
4. **`MetaDataCacheDecoratorBase`** exists in liblcm and was not
   inspected -- if some project path wraps the MDC in a decorator,
   `GetFieldType`/`get_IsVirtual` could theoretically differ from
   `LcmMetaDataCache`'s direct impl (not expected, decorators typically
   delegate, but unread this session).
5. **Raw `ISilDataAccess` COM interface declaration** was not located as
   a single file this session; its members were confirmed only via the
   concrete `DomainDataByFlid` class, not the interface source itself
   (likely IDL-generated like `ITsString`). Functionally sufficient here.
