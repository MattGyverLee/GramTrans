# QC Report

> Authored by lex-qc (cycle 3). This subagent had only Read/Grep/Glob tools (no
> Write/Bash), so the orchestrator persisted this report verbatim at this path.

**Date:** 2026-07-20
**Quality Score:** 78/100
**Status:** ISSUES

## Pattern-Audit Gate
- Sweep present in artifact: UNVERIFIED (no Bash access to `git log`/`gh pr view` this session — orchestrator must confirm commit body has a "Pattern audit" section before merge).
- Independent re-audit (a) — no-GUID-Create + name-only-dedup shape: found an UNCOVERED sibling in `Lib/reversals.py`: `_create_top_level_entry` (line 604, `target.ReversalEntries.Create(index, form, sense)`) and `_create_sub_entry` (line 660, raw `IReversalIndexEntryFactory.Create()`) have **no dedup at all** (not even name/fingerprint) before create — every re-Move will duplicate `ReversalIndexEntry` objects. Worse than the Text case this PR fixed. `wordforms.py` was already checked by the programmer per the task; this reversals.py site was not.
- Independent re-audit (b) — OWNED_OBJECT_MAP duplicate-sync-surface shape: no other row duplicates a parent `*Operations.GetSyncableProperties` surface (verified `LexEntry`/`Senses` sync calls in categories.py:5899/5975 only cover scalar/multistring fields, never create owned children). `LexSense.ExtendedNoteOS` confirmed genuinely different (no sync-ops surface at all) — correctly out of scope.
- Gate status: **BLOCK** pending (1) confirmation the commit body actually has the sweep section, and (2) a decision on filing the reversals.py finding (P1, new issue or same-PR fix).

## Code Quality: 20/25
Clear docstrings, consistent naming. `_text_disposition`/`_text_fingerprint` are appropriately small; `owned.py`'s docstring explaining the removed TranslationsOC row is excellent regression documentation.

## Standards Compliance: 22/25
Consistent with codebase conventions (`_safe`, lazy imports, `DroppedItemRecord`). No issues found.

## Error Handling: 20/25
`texts.py:1004-1010` distinct "paragraph has no mappable baseline text" reason is correct and never swallows the underlying exception — `_create_paragraph`->`_raw_create_blank_paragraph` failures still route through `_safe`, logged at debug (`texts.py:1101`). Minor: no test asserts the debug log fires.

## Best Practices: 16/25
**P2 coupling risk** — `_raw_create_blank_paragraph` (`texts.py:919-939`) hard-codes flexicon internals via a line-number citation (`ParagraphOperations.py:169`, `:182-190`) with no pinned version guard; a flexicon bump could silently drift. Recommend a smoke test (or MCP-driven live check) tied to the `pyflexicon` floor version already declared in `pyproject.toml`.
**P1** — `reversals.py` ReversalIndexEntry create sites lack any re-run dedup (see gate above).

## Final Assessment
**Overall Score:** 78/100
**Recommendation:** FIX ISSUES — confirm/add pattern-audit section; triage reversals.py finding.

---
**Reviewed By:** QC Agent

Files reviewed:
- `src/gramtrans/Lib/texts.py`
- `src/gramtrans/Lib/owned.py`
- `src/gramtrans/Lib/reversals.py` (lines 400-680, pattern-audit sibling finding)
- `tests/unit/test_texts_fullcopy_defects.py`
