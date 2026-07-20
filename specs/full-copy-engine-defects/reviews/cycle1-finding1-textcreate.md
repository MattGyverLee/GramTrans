# Cycle 1 – Finding 1: Text/Paragraph Create FP_ParameterError — Root Cause

> Authored by lex-domain (cycle 1). NOTE: this subagent invocation had no Write
> tool and no FLExToolsMCP tools available; signatures were confirmed by reading
> the installed flexicon package source directly
> (`D:\Github\_Projects\_LEX\flexicon\flexicon\code\TextsWords\{TextOperations,ParagraphOperations}.py`),
> which is the actual live library GramTrans imports per pyproject.toml
> (`pyflexicon>=4.1.1`), not an offline fake. Report saved verbatim by the orchestrator.

**Confirmed live signatures** (flexicon `pyflexicon`, installed package):

```python
TextOperations.Create(self, name: str, genre: ICmPossibility|None = None) -> IText
ParagraphOperations.Create(self, text_or_hvo: IText, content: str, wsHandle: int|None = None) -> IStTxtPara
```

## Verdict: NOT a signature mismatch

Both call sites already match these signatures exactly:
- `texts.py:712`: `text_ops.Create(plan.title or "(untitled)", None)` -> `(name, genre)`. Correct.
- `texts.py:856`: `para_ops.Create(target_text, content or "", default_vern_handle)` ->
  `(text_or_hvo, content, wsHandle)`. Correct. `default_vern_handle` comes from
  `target.GetDefaultVernacularWSHandle()` (confirmed present on `FLExProject`,
  `FLExProject.py:2601`), so the arg type/arity is right.

## Real root cause — internal FP_ParameterError guards, per site

**Site 1 (`TextOperations.Create`, texts.py:712):** raises
`FP_ParameterError(f"A text with the name '{name}' already exists.")` when
`self.Exists(name)` is already true. `_resolve_or_create_text` only checks
GUID-match for `ReferenceAction.UPDATE`; for ADD it calls `Create` unconditionally.
Two source texts sharing a title (or two texts with no title, both falling back to
`"(untitled)"`) collide on the second `Create` call. Matches the x1 cardinality seen
in Ejagham Mini/Esperanto (one duplicate-name pair each).

**Site 2 (`ParagraphOperations.Create`, texts.py:856), the dominant bucket:** raises
`FP_ParameterError("Content cannot be empty")` when
`content.strip()` is empty. `content` comes from `_first_mapped(para_plan.baseline, ...)`,
falling back to a space-join of segment baselines; both paths return `None`/`""` when
the source paragraph is genuinely blank (spacer paragraphs) or its only writing systems
are absent from `ws_map`/target inventory. `content or ""` then hits the empty-content
guard. This is a **data/mapping gap, not an API bug** — but it fires the same way at
every call, so the observed 20/1207/33 count == count of blank-or-unmapped source
paragraphs per project (Esperanto's high count implies many spacer/blank paragraphs or
a WS not represented in `ws_map`). The knock-on `Segment/alignment token had no copied
target referent` (103/27844/1724) is the direct cascade: no paragraph -> no target
segments -> alignment can't resolve a referent.

## Corrected calls

No arg-shape change needed at either site. The **actual fix** is pre-validation before
calling `Create`, so a legitimately-empty/duplicate case is turned into a controlled skip
or a distinct DroppedItemRecord reason (not swallowed by the generic except):

- Site 1: before calling `text_ops.Create`, check `text_ops.Exists(name)`; if true,
  either disambiguate the name (e.g. append the source GUID/suffix) or treat as
  UPDATE-by-name and reuse the existing text, matching Move-mode's stated "never
  silent" contract with a clearer reason than `FP_ParameterError`.
- Site 2: before calling `para_ops.Create(target_text, content, default_vern_handle)`,
  if `content.strip()` is empty, either (a) create the paragraph via the raw
  `IStTxtParaFactory` + `ContentsOA.ParagraphsOS.Add` idiom directly (bypassing the
  wrapper's non-empty guard) to faithfully reproduce a blank source paragraph, or
  (b) explicitly report `DroppedItemRecord(reason="paragraph has no mappable baseline
  text")` instead of the misleading generic `FP_ParameterError` label — never call
  `Create` with blank content into the guarded wrapper.

## Sweep hint

`owned.py` and the rest of `texts.py` use **raw LCM factories** (`IMoAlloAdhocProhibFactory.Create(guid)`,
`ICmTranslationFactory.Create(owner, type, guid)`, `ITextTagFactory.Create()`, lines
626/640/651/1340/1872/1876/816), not the flexicon `*Operations.Create(name/content, ...)`
wrapper shape — a different call class, unaffected by this defect. The only two
"offline-fake-shape" `.Create(` calls with the wrapper's `(business_field, ...)`
signature in this file are the two already confirmed above; no other sites in
texts.py/owned.py share this pattern.
