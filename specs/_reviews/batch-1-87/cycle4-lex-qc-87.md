# QC cycle4 -- issue #87 delta (commit 44e09d9 on 3a86bb0) -- static review only

**Score: 93/100 -- APPROVE.** No P0/P1; P2 nits only.

(Saved by the main session: lex-qc has Read/Grep/Glob only and ran no tests.)

## 1. residue.py strip helper (332-365)

- Hand-traced `strip_residue_text` on "", "Foo", "Foo\n", "Foo\r\n", "Foo\n\n", "  ", "\n", "A\n\nB": each stamped by apply_carrier_b ("\n\n", or "\n" when empty) strips back to x exactly.
- Two-tag histories ("x\n\n[t1]\n\n[t2]") strip to "x"; `trim_at` resets correctly when a tag follows non-blank content.
- Separator handling matches apply_carrier_b (288-291). Legacy targets still strip (the "\n\n" format and the empty-source "\n" lead-in are asserted in tests).
- `strip_residue_props` drops residue-only alternatives and returns the same object when nothing changed.
- Parametrised test (tests/unit/test_issue87_residue_idempotent.py:244-265) covers empty, whitespace-only, LF, CRLF, multiple blank lines, multi-paragraph; checks stamp, update-with-history, props round-trip.
- **P2 (test_issue87_residue_idempotent.py:271):** `strip(...) != "different"` is trivially true. Assert a changed source's stripped text differs from the target source, or that compute_disposition returns UPDATE.
- **P2 (residue.py:340-343):** overlong, slightly garbled docstring line; three blank lines at 298-300.

## 2. Live test (tests/integration/test_issue87_residue_idempotent_live.py)

- Whole-class `changed` excludes are gone. EXCLUDED_NEW_CLASSES covers only NEW MoInflAffixSlot / MoInflAffixTemplate / FsFeatStruc objects. MoInflAffMsa not excluded. FsFeatStruc exclusion cites the draft issue via ISSUE_REF (evidence not re-checked).
- `_normalise` (123-140) removes only `<objsur>` entries for dropped guids, only inside the three wrapper blocks, only for PartOfSpeech, and drops a wrapper only when left empty. Docstring (26-36) matches code.
- **P2 (line 140):** `replace(m.group(2), inner, 1)` works but is fragile if the inner text repeats; build from group spans.
- Live evidence gate: outside this static delta.

## 3. Commit message

- `closes #87` present; exactly one `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` trailer (main session confirmed with `git log -1`).
- **P2:** body does not mention the cycle-4 trailing-whitespace inverse fix -- describes the cycle-3 state.
