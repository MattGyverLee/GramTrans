# Cycle 1 - live verification of the MERGED tree (#153/#157/#159/#160/#155)

**Verdict: [PASS]** | FLEXLIBS_REQUIRE_LIVE=1 | live: yes | 2026-10-31

## Trees tested
- Base B (primary): `integ-141-147-stack` @ **fb25f0f**, worktree GramTrans-integ-141-147-stack
- Base A (bonus): `integ-141-147` @ **a986e6a**
- Both built; no PR branch touched; nothing pushed; no stash.

## Env print (both, with PYTHONPATH=<worktree>/src)
`gramtrans=D:\Github\_Projects\_LEX\GramTrans-integ-141-147-stack\src\gramtrans\__init__.py`
`flexicon=D:\Github\_Projects\_LEX\flexicon\flexicon\__init__.py`
(A: same, with `GramTrans-integ-141-147\src`.) Note: root `conftest.py` also inserts its own worktree `src` at sys.path[0], so a PYTHONPATH to a different tree is overridden inside pytest. This invalidated my first RED attempt, which I redid on a full tree copy.

## Per-module (sandbox pairs GT-Src-NNN / GT-Sandbox-NNN, sequential)
| Module | Expected | B | A |
|---|---|---|---|
| #141 | 5 passed | 5 passed | 5 passed |
| #144 | 6 passed | 6 passed | 6 passed |
| #145 | 4 passed | 4 passed | 4 passed |
| #146 | 5 passed + 2 xfailed | 5 passed + 2 xfailed (genre, GetGenre AttributeError, #161) | same |
| #147 | 2 passed | 2 passed | 2 passed |

## Step 2 - #146 segment-tag rebind, LIVE (GT-Src-146 -> GT-Sandbox-146)
New module (uncommitted, in B worktree): `tests/integration/test_integ_146_segment_tag_rebind_live.py` (4 tests). Authoring worked live via raw `ITextTagFactory` plus `IStText.TagsOC`; no fallback needed.
- Target forked from restored source BEFORE authoring. Fixture: texts 1 and 2 share new tag T `16896aeb-5af2-481e-a3b6-1ea00250e85d`; text 3 has control tag U `f035e3e5-8088-4c7c-a044-2a3683ed9986`. Source ITextTags: 1e8e19db..., b34c2519..., f32f1077....
- Pre: target TextMarkupTagsOA holds 4 stock tags, none of T or U; the 3 texts are absent.
- Preview: one T text planned CREATE, the other LINK, U CREATE. Which text is first varies between runs, so the test asserts the set; the first draft assumed order and flaked once. The target fwdata bytes are unchanged after Preview.
- Move: the list gained exactly T and U, with the source GUIDs. Text1 tag -> T, text2 tag -> T (rebound LINK), text3 tag -> U.
- Re-run: idempotent (post2 == post).
- GREEN: 4 passed on B, 4 passed on A, 3 consecutive B runs after the order fix.
- **RED control** (full copy of the tree in scratchpad `redwt`, `rebind_planned_link` made to `return decision`): Preview unchanged; Move created T and U but **the LINK text's TagsOC came back `[]`, so its tag was silently lost**. `test_move_both_texts_reference_same_created_tag` FAILED (1 failed, 3 passed). The worktree `references.py` was never edited: sha256 c8f3a0ad...2945e before and after, `git status` clean apart from the new test.
- Conclusion: the Move-side rebind is load-bearing live and is now proven.

## Step 3 - read-only project hashes (.fwdata sha256, before == after: SAME)
| Project | sha256 |
|---|---|
| Esperanto | e9effa15...6683189 |
| Ejagham Mini | d5bb4d32...ed9e4 |
| Mbugwe LizzieHC practice | 3fb29a29...5436d |
| Target | 13c5a96f...74c7f |

## Notes
- All writes were confined to GT-Src-146 / GT-Sandbox-146 and the other per-PR sandbox pairs; both #146 projects were restored in fixture teardown.
- `tests/live_status.json` does not exist in the integration worktrees (these modules do not use the conftest live fixtures), so Step 5 `run_mode` was unavailable. Liveness is evidenced by the real project GUIDs read back from the LCM.
- Each pytest run printed a faulthandler stack at exit; no test failure was associated with it.
- The new test is left uncommitted in the B worktree for the lead to commit.
