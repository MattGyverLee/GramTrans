# cycle1-lex-qc-116 (PR #123, HEAD 68db9b1)

> Saved by the main session: lex-qc has no Write/Bash tool and returned this text verbatim (it read worktree files directly instead of `git diff`).

Verdict: APPROVE, 88/100. No P0 or blocking P1. Gates: the pattern-audit and live-evidence gates look satisfied per impl-116 (live run, 8 passed and 1 xfailed). I did not re-run anything.

1. **Move behaviour: unchanged in effect.** Call sites at categories.py:8910-8913 discard the return values. Drops, `new_sense` writes and `resolver_cache` use are the same as before.
   - Move now also builds records and calls `_thesaurus_new_ancestors` before `apply_reference`. These are read-only.
   - **P2, categories.py:8510:** `_find_in_possibility_list` and `_item_label` are not inside the try block, although the docstring says "never raises". An unexpected exception there would now escape in Move, where before it could not. Wrap the loop in try/except returning `()`.
2. **`_thesaurus_new_ancestors` mirrors the CREATE loop.** `apply_reference` (references.py:1103-1108) reuses an ancestor if `cache.get(guid)` or `_find_in_possibility_list(target_list, guid)` finds it. The helper skips on the same two tests (categories.py:8508-8511). `[:-1]` correctly drops the leaf.
   - Known limit: Preview never primes the cache, so two new items under one new ancestor both list it (documented in impl-116).
3. **xfail confirmed.** The test is `@pytest.mark.xfail(strict=True)` at test_issue42_appendix_thesaurus_live.py:548. The swallowed error exists on main c088d16: `create_props[...] = ... _best_text(field_ms)` (references.py:1195-1203), then `ApplySyncableProperties(...)` inside `except (AttributeError, TypeError): pass` (references.py:1209-1211). It is pre-existing and does not block this PR.
   - I did not independently confirm that the setattr raises TypeError for Description. That rests on the implementer's live probe.
   - **Rating: P1.** It is a silent swallow on the write path. A plain-string Description is dropped, and the next run decides UPDATE on items the previous run created. It should be filed as its own issue and go through the full crew cycle.
4. **Renderer** (preview.py:1978-2021). It dedupes correctly: the key is (field, action, item_guid) and senses are counted by owner set.
   - **P2, preview.py:1991-2020:** it is bounded per distinct item, not per sense, and there is no row cap. A thesaurus using many semantic-domain items would produce hundreds of pane rows, and every LINK is listed. Add a cap with a "+N more" line, or collapse LINK rows to a count.
   - **P2:** rows with an empty `owner_guid` collapse into one count.
5. **Live capture is not vacuous.** The wrapper (test file :360-386) collects only when `args[1]` is set. Move passes `new_sense` positionally, so it is captured. The Preview rows are asserted non-empty (:489). The Move row list is compared in order to Preview's (:512), and the s3 equality (:541). Empty capture would therefore fail.
   - **P2:** items 2 and 3 of that test compare the same resolver run in both modes, so they are partly circular. The ground-truth check at :523-528 is the real guard, and it reads post-state.
