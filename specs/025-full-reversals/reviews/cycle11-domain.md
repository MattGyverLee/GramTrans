# Cycle 11 — Domain Expert adjudication: Finding 1(a) stringify-fallback collision risk

**Tool caveat:** FLExToolsMCP was not available to this reviewer session (no Write
tool either). Findings reuse already-recorded live evidence from cycle ~024's own
verification (`tests/unit/test_reference_ws_keying.py` header, confirmed live on
Ejagham Mini: WS handles are large project-cache ints, e.g. `999000001`; WS Ids are
IETF/ICU locale tags, e.g. `'en'/'es'/'fr'/'zh-CN'`), plus FieldWorks/ICU LocaleId
grammar (primary language subtag must be alphabetic). A follow-up session with live
FLExToolsMCP access should re-confirm point 1 directly against Ejagham Full GT-Test /
Mbugwe Lizzie HCPractice custom WS lists.

## 1. Collision risk

`str(wh)` for an unresolved raw handle is always a plain non-negative **decimal-digit
string** (Python `int.__str__`). A colliding resolved WS Id would have to be a WS whose
portable `Id` is *also* a bare digit string. Every FieldWorks/LCM WS Id is an ICU
LocaleId / IETF BCP-47-shaped tag; the primary subtag MUST start with a letter (ISO 639
code, `qaa`-`qtz` private-use, or `x-...`). A tag that is nothing but digits cannot pass
FieldWorks' WS-creation validation and is not a legal IETF language tag — a bare
digit-string WS Id is not achievable through normal WS creation/edit or through
`WritingSystems.GetAll()`'s own Id-generation path. Hand-corrupted LCM XML is the only
way to force such a value, which is not realistic for a normally-authored project
(including the GT-Test corpus this Move targets). Real handles observed live are large
(9+ digit) cache-instance ints, while the `wh` values feeding this fallback in the actual
failure (~164 stems) are ordinary small ints — a true collision would additionally need
a second orphaned handle numerically equal to a digit-string Id, compounding an already
non-existent precondition. Verdict: structurally near-impossible, not observed, not
realistic for this corpus.

## 2. Fingerprint contract

- **Cross-WS swap detection:** unaffected — swapped content between two normally-resolving
  WS Ids never touches the stringify-fallback branch (both keys resolve via
  `handle_to_id.get(wh)`); `sorted(...)` tuples differ as before. The fallback fires
  per-key, not per-field.
- **True-identical entries:** still compare equal — content that resolves cleanly on both
  sides produces identical Id-keyed snapshots regardless of the fallback. The fallback
  only changes behavior when an actual orphaned handle is present, which is asymmetric in
  practice (the anomaly lives on the source side); the fix, if anything, correctly flags
  an extra source alt as a real divergence rather than masking one. A false-EQUAL outcome
  requires the doubly-compounded collision from Q1, already ruled implausible.

## 3. Verdict: SAFE-WITH-FOLLOWUP

Ship the Finding 1(a) fix for the T037 Move — it strictly improves on the pre-fix
TypeError crash, and the collision precondition is not realistic for this corpus.
Recommend, as low-cost hardening (NOT a blocker), adopting the programmer's own suggested
sentinel prefix (`f"~unresolved~{wh}"`) in a follow-up so the fallback key-space is
provably disjoint from any legal WS Id, removing the residual theoretical risk at
near-zero regression cost (changes only the never-normally-hit branch's string shape).
Not blocking T037.

---
**Reviewed By:** lex-domain (cycle 11)
**Tooling caveat:** FLExToolsMCP unavailable this session; recommend a live-tool follow-up confirmation per above.
