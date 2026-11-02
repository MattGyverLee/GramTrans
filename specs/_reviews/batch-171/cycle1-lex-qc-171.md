# cycle1 lex-qc -- issue #171 (fix-171-infl-midpass)

**Score: 90/100. Verdict: APPROVE. No P0/P1.**

## Scope check

Fix matches issue #171 acceptance: confirmed link count and skips emitted before a
mid-pass raise are preserved. Reconciliation behaviour (#133) unchanged.

## Code review

- `try`/`finally` flush is minimal and mirrors the existing end-of-pass accumulation.
- Stash is read only on the exception path in `_ensure_infl_feature_links`; success
  path still uses the returned skip list (no double-extend).
- `sys.exc_info()[0]` in `finally` is the standard pattern for exceptional flush.

## Tests

- Mid-pass write count assertion added to existing #133 test.
- New test covers skip retention across POS iteration order before feature resolve raise.

## Residual (P3, not blocking)

- Live gate with SHA in evidence still open per issue body; cloud agent has no flexicon.
