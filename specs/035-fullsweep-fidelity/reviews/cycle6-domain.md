# Cycle 6 -- lex-domain review of T045d (plane-2 metadata census reader)

Reviewer: lex-domain role (run via FLExToolsMCP, all runs `write_enabled=False`).
Projects: `Ejagham Mini` (EM), `Mbugwe LizzieHC practice` (MB). No writes; Esperanto not opened.

Evidence ops: `op-134230666-004` (EM class metadata), `op-134254725-005` (EM type histogram, special types, custom fields),
`op-134312822-006` (MB class metadata and custom fields), `op-134425000-008` (base-proxy sda reads),
`op-134508457-009` (full EM census timing, Time/Binary samples, custom value vs flexicon),
`op-134535994-010` (all flids <200; owned classes outside the 69).

**Verdict: ACCEPT the ruling, with 6 amendments (end of file).** The sda+MDC reader works on base
`ICmObject` proxies with no casting. It read every stored field of all 6,880 in-scope EM objects in 1.4 s
with 0 errors. The prior-art `_SKIP` branch must go: it silently drops `StPara.StyleRules`, the paragraph
style.

---

## Q1. Does GetFields include virtuals? Is get_IsVirtual the right filter?

- **Yes, virtuals are included.** For Segment, `GetFields(6, True, All)` returns 18 flids. 4 are virtual:
  `Self` 20000001, `Owner` 20000002, `ShortNameTSS` 20000003 and `BaselineText` 20000024 (op-...004).
  Across the 69 classes the virtual fields are: RefAtom 155, String 102, RefSeq 38, RefColl 29, Boolean 17, Integer 12,
  MultiString 9, MultiUnicode 9, Unicode 3, OwnColl 1. These are per-class counts.
- **`get_IsVirtual(flid)` is the right and sufficient filter.** The `flid<200` filter never catches a virtual field.
  All four fields below 200 are stored (Q2).
- `CellarPropertyTypeFilter.All` and `0x7FFFFFFF` return identical sets for all 69 classes (op-...004).
- **Segment:** `BaselineText` is **virtual** (20000024, String). `EndOffset` and `IsLabel` are **absent from the
  model**: `GetFieldId2` raises `LcmInvalidFieldException`, so they are C#-only computed members. Stored Segment
  fields are BeginOffset, FreeTranslation, LiteralTranslation, Notes, Analyses, Reference, MediaURI,
  BeginTimeOffset, EndTimeOffset and Speaker. Model names carry no RA/OS suffix: `AnalysesRS` is invalid and `Analyses` is correct.
- All 69 classes resolve by `mdc.GetClassId(name)` without instances. Per-class counts were **identical in EM and MB**,
  apart from custom fields (see table).

**Stored-type histogram (unique stored flids >=200, EM, 399 flids incl. 2 custom):**
MultiString(14) 54, ReferenceAtom(24) 55, MultiUnicode(16) 48, ReferenceCollection(26) 37, OwningAtom(23) 31,
ReferenceSequence(28) 31, Unicode(15) 27, OwningSequence(27) 26, OwningCollection(25) 25, Integer(2) 24,
Boolean(1) 18, String(13) 15, Time(5) 7, Binary(9) 1.
**Absent from all 69 classes:** Numeric(3), Float(4), Image(7) and GenDate(8). Guid(6) appears only as base flid 101.
Note that `str(CellarPropertyType(1))` prints `"Min"` (an enum alias), not `"Boolean"`. Key off the int.

## Q2. CmObject base fields

In the whole EM MDC, `GetFieldIds()` has exactly four flids below 200, all **stored** Integer/Guid fields on CmObject:
`Guid` 101 (t6), `ClassID` 102 (t2), `OwningFlid` 104 (t2) and `OwnOrd` 105 (t2) (op-...010). There is no stored `Owner` (no flid 103).
The owner is available only as the virtual `Owner` 20000002.
`DateCreated`/`DateModified` are **not** base fields. They are ordinary stored Time fields on CmMajorObject (5002/5003),
CmPossibility (7010/7011), LexEntry (5002005/5002006) and StText.DateModified (14004).
Unowned objects read `OwningFlid=0, OwnOrd=-1` (WfiWordform, op-...008).

Recommended census exclusions:
- **Guid (101)** is the identity key, not a compared value.
- **ClassID (102)** is redundant with the class bucket.
- **OwningFlid/OwnOrd (104/105)** are structural. Order is already captured by the owner's owning-sequence GUID vector.
  If owner placement is to be checked, compare "owner GUID + owning field name". Never compare raw flid ints
  across projects.
- **Time fields (7 flids)**: exclude them or report them in a separate non-fidelity tier. A transfer legitimately stamps
  new dates unless it preserves them on purpose.
- *Candidates, NOT verified as volatile:* `WfiWordform.Checksum`, `StTxtPara.ParseIsCurrent`,
  `WfiWordform.SpellingStatus`. These are parser/UI bookkeeping and need a domain decision.

## Q3. Custom fields

- They surface in `GetFields(..., True, All)` as stored fields with `IsCustom(flid)=True`.
  `GetFieldName` returns the **user label, spaces included** (e.g. `"Target Equivalent"`).
- Custom fields inherit. EM's `MoForm."Allomorph Comment"` appears on both MoAffixAllomorph and MoStemAllomorph.
- **Flids differ across projects.** They are allocated per owner class as `clid*1000+500+n`
  (observed pattern, not a documented contract). Examples: EM `LexSense.Target Equivalent` = 5016500;
  MB `LexEntry.Diminutive PL` = 5002500. **Match by (owner class, field name), never by flid.**
  The same flid number can name different fields in two projects.
- **EM:** `LexSense."Target Equivalent"` (5016500, String, ws -1) and `MoForm."Allomorph Comment"` (5035500, MultiUnicode, ws -3).
- **MB:** `LexEntry`: `Diminutive PL` 5002500, `Diminutive SG` 5002501 and `Plural2` 5002502 (MultiUnicode, ws -4);
  `ProtoBantu` 5002503 (String, ws -2); `Speaker` 5002504 (String, ws -1). No list roots.
  *The meanings of magic ws -1..-4 (anal/vern/anals/verns) are from memory, NOT verified live.*
- **GramTrans src (triaged real hits):**
  - **Definitions are transferred.** `Lib/api.py:671 _ensure_custom_fields` calls `AddCustomField` for owner classes
    `LexEntry, LexSense, LexExampleSentence, MoForm` (`Lib/categories.py:947`).
  - **Values are NOT transferred on the path this review traced.** `categories.custom_fields_execute_action`
    (`categories.py:1289`) is a documented **no-op** that defers to "transfer.execute internals".
    `transfer._dedupe_custom_fields` (`transfer.py:963`) expects `Custom*` keys from flexicon `GetSyncableProperties`.
    Live check (op-...009): a sense with `Target Equivalent` populated gets 18 keys from
    `LexSenseOperations.GetSyncableProperties`, and **none is custom** (cast and base proxy alike).
  - `merge_preview._read_custom_fields` reads values for preview display only.
  - *Not exhaustively traced:* other write paths, and the LexEntry/Example/MoForm operations.
  - **Implication for the census:** the metadata reader *will* see custom values. Expect them to surface as
    genuine losses, which is correct behaviour for a fidelity census.

## Q4. Canonical reads per CellarPropertyType (all verified in op-...008/009 unless marked)

| Type | Read | Canonical form |
|---|---|---|
| Boolean 1 | `get_BooleanProp` | bool |
| Integer 2 | `get_IntProp` | int |
| Time 5 | `get_TimeProp` -> Int64 | raw int. EM LexEntry 13419019756953 matches typed `DateCreated` 3/26/2026 5:29:16 PM, consistent with ms since 1601. *Epoch and UTC-vs-local are inferred, NOT verified.* |
| Guid 6 | `get_GuidProp` | str (base 101 only) |
| Binary 9 (`StPara.StyleRules` 15002) | **`get_UnknownProp`** -> `ITsTextProps` (210/210 OK; sample had 0 int / 1 str props) | sorted (tpt,var,val)/(tpt,str) tuples, same as run props. Do not use `BinaryPropRgb` (ArrayPtr). |
| String 13 | `get_StringProp` | run tuples (below); Length==0 -> None |
| MultiString 14 | `get_MultiStringProp` -> `ms.GetStringFromIndex(i)` -> `(tss, ws)` | `{ws_tag: runs}` |
| Unicode 15 | `get_UnicodeProp` | str/None |
| MultiUnicode 16 | as 14 | `{ws_tag: text}` |
| OwnAtom/RefAtom 23/24 | `get_ObjectProp`; **0 = null** -> None | GUID str via `ICmObjectRepository.GetObject(hvo).Guid` |
| Colls 25/26 | `get_VecSize`/`get_VecItem` | GUID list. Compare as a **set** (order carries no meaning in LCM collections). |
| Seqs 27/28 | same | GUID list, **order-significant** |
| Numeric 3, Float 4, Image 7, GenDate 8 | not present | **raise** on any unhandled type; never `_SKIP` |

- **WS resolution:** `sda.WritingSystemFactory.GetStrFromWs(ws)`. EM handles 999000001..7 map to en, es, etu,
  etu-fonipa, etu-x-Eastern, fr, zh-CN. Handles are per-session, so always emit tags. Only non-empty alternatives
  were kept. *Whether `StringCount` includes zero-length alternatives was NOT checked.*
- **References into other lists** (PhPhoneme.Codes -> PhCode, CmAgent.Approves -> CmAgentEvaluation, Segment.Analyses
  -> WfiGloss/Wordform) all resolved to GUIDs. There were no dangling-hvo errors in 126,064 reads.
- **ITsString, demonstrated (run-by-run):** for each run i, take `tss.get_RunText(i)`, then
  `tp = ITsTextProps(tss.get_Properties(i))`. `tp.GetIntProp(k)` returns `(val, tpt, var)` under pythonnet, and
  `tp.GetStrProp(k)` returns `(val, tpt)`. Map `tpt==1` (ws) val through GetStrFromWs. Emit
  `(text, sorted(int_props), sorted(str_props))`. The live EM `Target Equivalent` value came out as:
  `('linked to entry: ...', ((1,0,'en'),), ((6,'\x04silfw://localhost/link?database=Ejagham+E+Mini+Kathie...guid=08e0...'),(133,'Hyperlink')))`.
  **Warning:** str-prop 6 (object data / hyperlink) embeds the **source project name and GUIDs**. A strict comparison will
  flag any link that a target legitimately rewrites. It is also where ORC-embedded object GUIDs live.
  *The tpt 6 and 133 names are from memory. The payload confirms 133 is a style name. `TsStringSerializer` XML
  was NOT tried.*

## Q5. Casting trap

Yes, the hvo+flid path avoids it. All five sampled objects were `ICmObject` proxies straight from
`ICmObjectRepository.AllInstances()` (op-...008). Values read without casting:
- **PhPhoneme:** Name `{etu:'ə'}`, Description en, Codes=[1 GUID]
- **WfiWordform:** Form `{etu:'k'}`, Analyses=[]
- **Segment:** BeginOffset 52, Analyses=8 GUIDs
- **CmAgent:** Name `M3Parser`, Version `Normal`, Human False, Notes/Approves/Disapproves GUIDs
- **StTxtPara:** Contents run with ws etu

The sda never resolves members against the static wrapper type, so the trap cannot arise.
Side note: LexSense `GetSyncableProperties` on a base proxy returned the same 18 keys as on a cast object.
The `{}` failure is class-specific.

## Q6. Timing (EM, op-...009)

- **Workload:** 6,880 objects across 42 populated classes; **126,064 field reads**, of which 51,061 were non-empty.
- **Errors: 0.**
- **Time:** enumeration (filtering `AllInstances()`) took 0.607 s; the reads took **1.424 s** (~88.5k reads/s).
  The hvo->GUID memo cache held 13,883 entries.
- Project-open time is excluded.
- *MB was NOT timed.*

## Additional finding: owned children outside the 69

Owning fields of the 69 classes hold concrete classes that are **not** in scope (op-...010). The census records their
GUIDs but never their fields. Domain-relevant cases:
- **PhCode** (PhPhoneme.Codes, i.e. graphemes)
- **CmTranslation** (LexExampleSentence/StTxtPara.Translations, i.e. example translations)
- **CmDomainQ**
- FsComplexValue/FsNegatedValue/FsOpenValue/FsDisjunctiveValue/FsSharedValue (FsFeatStruc.FeatureSpecs)
- FsFeatStrucDisj
- PhIterationContext
- MoAffixProcess and MoDerivStepMsa (LexEntry forms/MSAs)
- MoReferralRule
- Note (Segment.Notes)
- CmMedia
- CmAgentEvaluation

`StTxtPara.AnalyzedTextObjects` is typed CmObject and can be ignored. The coverage floor should cover these deliberately,
either by adding them or by recording an explicit exclusion.

## Per-class counts (by class id, no instances needed)

Columns: total `GetFields(clid,True,All)`, stored (incl. the 4 CmObject base fields and custom), virtual, custom.
EM and MB are identical except where marked MB.

| Class | clid | total | stored | virtual | custom |
|---|---|---|---|---|---|
| CmAgent | 23 | 14 | 11 | 3 | 0 |
| CmAnthroItem | 26 | 26 | 23 | 3 | 0 |
| CmFile | 47 | 12 | 9 | 3 | 0 |
| CmFolder | 2 | 11 | 8 | 3 | 0 |
| CmPicture | 48 | 22 | 13 | 9 | 0 |
| CmPossibility | 7 | 26 | 23 | 3 | 0 |
| CmSemanticDomain | 66 | 32 | 28 | 4 | 0 |
| FsClosedFeature | 50 | 18 | 14 | 4 | 0 |
| FsClosedValue | 51 | 11 | 8 | 3 | 0 |
| FsComplexFeature | 4 | 17 | 14 | 3 | 0 |
| FsFeatStruc | 57 | 14 | 7 | 7 | 0 |
| FsFeatStrucType | 59 | 12 | 9 | 3 | 0 |
| FsSymFeatVal | 65 | 14 | 11 | 3 | 0 |
| LexAppendix | 5046 | 8 | 5 | 3 | 0 |
| LexEntry | 5002 | 57 (MB 62) | 27 (MB 32) | 30 | 0 (MB 5) |
| LexEntryInflType | 5133 | 32 | 29 | 3 | 0 |
| LexEntryRef | 5127 | 24 | 13 | 11 | 0 |
| LexEntryType | 5118 | 28 | 25 | 3 | 0 |
| LexEtymology | 5113 | 17 | 13 | 4 | 0 |
| LexExampleSentence | 5004 | 14 | 9 | 5 | 0 |
| LexExtendedNote | 5134 | 11 | 7 | 4 | 0 |
| LexPronunciation | 5014 | 16 | 11 | 5 | 0 |
| LexRefType | 5119 | 30 | 27 | 3 | 0 |
| LexReference | 5120 | 14 | 8 | 6 | 0 |
| LexSense | 5016 | 62 (MB 61) | 38 (MB 37) | 24 | 1 (MB 0) |
| MoAdhocProhibGr | 5110 | 12 | 9 | 3 | 0 |
| MoAffixAllomorph | 5027 | 19 (MB 18) | 14 (MB 13) | 5 | 1 (MB 0) |
| MoAlloAdhocProhib | 5101 | 12 | 9 | 3 | 0 |
| MoDerivAffMsa | 5031 | 33 | 19 | 14 | 0 |
| MoEndoCompound | 5033 | 17 | 14 | 3 | 0 |
| MoExoCompound | 5034 | 16 | 13 | 3 | 0 |
| MoInflAffMsa | 5038 | 29 | 13 | 16 | 0 |
| MoInflAffixSlot | 5036 | 11 | 7 | 4 | 0 |
| MoInflAffixTemplate | 5037 | 18 | 15 | 3 | 0 |
| MoInflClass | 5039 | 14 | 11 | 3 | 0 |
| MoMorphAdhocProhib | 5102 | 12 | 9 | 3 | 0 |
| MoMorphType | 5042 | 29 | 26 | 3 | 0 |
| MoStemAllomorph | 5045 | 16 (MB 15) | 11 (MB 10) | 5 | 1 (MB 0) |
| MoStemMsa | 5001 | 29 | 15 | 14 | 0 |
| MoStemName | 5047 | 13 | 10 | 3 | 0 |
| MoStratum | 5048 | 11 | 8 | 3 | 0 |
| MoUnclassifiedAffixMsa | 5117 | 23 | 9 | 14 | 0 |
| PartOfSpeech | 5049 | 39 | 36 | 3 | 0 |
| PhBdryMarker | 5091 | 10 | 7 | 3 | 0 |
| PhEnvironment | 5097 | 13 | 10 | 3 | 0 |
| PhFeatureConstraint | 5096 | 8 | 5 | 3 | 0 |
| PhMetathesisRule | 5130 | 16 | 12 | 4 | 0 |
| PhNCFeatures | 5094 | 11 | 8 | 3 | 0 |
| PhNCSegments | 5095 | 11 | 8 | 3 | 0 |
| PhPhoneme | 5092 | 12 | 9 | 3 | 0 |
| PhRegularRule | 5129 | 17 | 12 | 5 | 0 |
| PhSegRuleRHS | 5131 | 14 | 10 | 4 | 0 |
| PhSegmentRule | 5128 | 15 | 11 | 4 | 0 |
| PhSequenceContext | 5083 | 10 | 7 | 3 | 0 |
| PhSimpleContextBdry | 5085 | 10 | 7 | 3 | 0 |
| PhSimpleContextNC | 5086 | 12 | 9 | 3 | 0 |
| PhSimpleContextSeg | 5087 | 10 | 7 | 3 | 0 |
| PunctuationForm | 5011 | 8 | 5 | 3 | 0 |
| ReversalIndex | 5052 | 17 | 13 | 4 | 0 |
| ReversalIndexEntry | 5053 | 12 | 8 | 4 | 0 |
| Segment | 6 | 18 | 14 | 4 | 0 |
| StText | 14 | 17 | 8 | 9 | 0 |
| StTxtPara | 16 | 16 | 12 | 4 | 0 |
| Text | 5054 | 20 | 16 | 4 | 0 |
| TextTag | 22 | 12 | 9 | 3 | 0 |
| WfiAnalysis | 5059 | 24 | 13 | 11 | 0 |
| WfiGloss | 5060 | 10 | 5 | 5 | 0 |
| WfiMorphBundle | 5112 | 14 | 9 | 5 | 0 |
| WfiWordform | 5062 | 23 | 8 | 15 | 0 |

## Amendments to the ruling

1. Filter on `get_IsVirtual` only. Drop flids 101/102/104/105 by name, as structural. Drop the `flid<200` heuristic.
2. Replace `_SKIP` with a raise. Add Binary via `get_UnknownProp` -> ITsTextProps. Treat Numeric/Float/Image/GenDate
   as a hard error, since they are absent from the 69 today.
3. Canonicalize ws handles to tags everywhere, including run props. Emit GUIDs (0 -> None) for every object field.
   Compare collections as sets and sequences as ordered lists.
4. Key custom fields by (class, name). Expect the census to expose the untransferred custom values (Q3).
5. Put Time fields in a separate non-fidelity tier. Rule on Checksum, ParseIsCurrent and SpellingStatus.
6. Decide on coverage for the out-of-scope owned classes. PhCode and CmTranslation matter most.
