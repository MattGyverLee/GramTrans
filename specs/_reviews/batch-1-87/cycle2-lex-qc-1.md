# QC cycle2 -- issue #1 (commit 8793ba8) -- static review only

**Score: 88/100 -- APPROVE with P2 notes.** No P0/P1.

(Saved by the main session: lex-qc has Read/Grep/Glob only, so it could neither write this file nor run unit tests.)

## Gates

- Pattern audit: programmer's report not re-checked; commit-body "Pattern audit" section not verified.
- Live-LCM evidence: change is read-only on LCM objects (display label) -- treated as N/A; confirm.
- Unit tests: NOT run by QC (no shell). Programmer reported 5074 passed (+7 new) with PYTHONPATH=GramTrans-fix-1/src.

## Findings

1. **Lazy import (fingerprints.py:174-185).**
   - No circular-import risk: categories.py never imports fingerprints (docstring mention only, categories.py:14919).
   - Per-call cost after the first import is a sys.modules lookup -- negligible across 15k senses.
   - **P2:** `except Exception` also swallows ImportError and cast errors with no log. If the import breaks, labels silently revert to "" and the original bug returns with no signal. `_cast_to_concrete` is already fail-soft (categories.py:309-325), so the outer catch only needs ImportError -- narrow it, or log once at debug.
2. **Display-only.**
   - Sole caller of msa_label_from_obj is `_msa_label_for_gather` (merge_preview.py:3294), used only at merge_preview.py:3430-3432 for the "Grammatical Info" display row. No match key, dedup key, hash or conflict comparison; the preview fingerprint is the separate `preview._msa_fingerprint`.
   - **P2 (visible side effect):** senses previously skipped for an empty label now get a row. Preview-only, not a match change.
   - Not checked: whether the preview diff engine compares "Grammatical Info" source vs target. Worth one grep.
3. **"From>To" format (fingerprints.py:224-231).**
   - One-side-null gives ">v" or "Root>"; both null gives "". Sensible and matches tests. selection.py:875-880 handles each side independently with None guards -- consistent in spirit (GUIDs there, abbreviations here).
   - **P2:** ":" joins parts, so a deriv label with slots reads "Root>v:slot" -- ambiguous but harmless.
   - **P2:** docstring still says "Mirrors preview._msa_fingerprint"; it no longer mirrors it for From>To.
4. **Tests (tests/unit/test_issue1_deriv_msa_pos_base_typed.py).**
   - `_BaseProxy` hides POS attrs (AttributeError) until the patched `_cast_lcm` returns the concrete object -- models the base-typed situation; `test_uncast_proxy_hides_pos` proves the hiding.
   - **P2:** `_cast_lcm` is mocked, so the real pythonnet cast is untested here (live evidence: existing T088 measurements).
   - **P2:** no test for import failure falling back to the uncast object.
   - **P2:** no test pinning the fail-soft path for a non-deriv MSA (stem MSA with slot).
5. **Style.** Docstrings/comments match repo conventions; complexity acceptable. **P2:** nested `_abbr_text` and bare `except Exception: pass` blocks are pre-existing style.
