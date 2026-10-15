# PR #73 cycle 1 -- lex-qc (PARTIAL: reviewer had no shell/write; transcribed by main session)

Score ~68/100. P0: none.

## P1
- config_views.py:300-317 `_rewritten_bytes` is regex-based. (a) `<Option id=>` rewritten anywhere, not scoped to `<WritingSystemOptions>` like the scanner (:390-398); (b) sequential renames corrupt swaps/chains (a->b, b->a) -- do a single simultaneous pass; (c) double-quoted only, `[^>]*?` breaks on `>` inside a value; a single-quoted/reformatted file is silently not rewritten while the plan says it is.
- api.py:951-956, 879-887, 892-916: broad `except Exception` handlers log without `exc_info`; ones that become drops (:951, :879) treat AttributeError/TypeError programming errors as drops with only `Type: msg`. Bare handlers at :892, :903, :915, :926 swallow with no log line.

## P2
- config_views.py:395 `$ws=`/magic ids skipped correctly; multi-ws comma lists unverified; mapping direction correct (:348).
- gramtrans.py:586 lazy flat `from api import ...` consistent with flat imports at :60-76; other lazy imports have a `gramtrans.Lib.` fallback, this one has none.
- api.py:813-818 WritingSystem drop uses owner_guid="", item_guid=tag; ConfigView producers use item_guid="" -- inconsistent. `_attach_dropped_items` does no dedup.
- config_views.py:287-294 plan-time identical detection correct if regex matches symmetrically.
- Q5 (untested changed lines) not checked.

Test result: not run by reviewer. Main session run on 55b3fd0: `pytest tests/unit tests/verification -p no:randomly` -> 5069 passed, 81 skipped, 14 xfailed, 0 failed.
