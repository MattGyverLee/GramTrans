# PR #73 cycle 1 -- lex-domain (reviewer could not write; transcribed by main session)

Basis: worktree source read; FLEx behaviour claims from domain knowledge, unverified via MCP.

## (1) Stored-but-inactive WS reported, not activated -- PASS (P1)
Activating silently changes project settings; reporting matches never-silent. FLEx LIFT import adds missing WS tags without prompting (unverified) so activation is defensible only as explicit previewed opt-in.
P1: surface the inactive-WS drop at Preview, not only post-run. The `Exists()` fallback when `active is None` should also yield a report entry, not only a log line.

## (2) Reversal alts dropped at plan time -- PASS on severity, FAIL on index-WS case
Per-alt drop + Move completes is right. When the index's OWN WS is absent, the whole index is skipped with one record whose reason "writing system not mapped" is wrong (may be mapped but absent).
P1: higher severity / Preview warning for index-level drop; reason text -> "writing system absent in target".

## (3) .fwdictconfig rewrite -- FAIL (insufficient)
Root writingSystem= + Option id= correct for common case; magic tokens correctly untouched.
P1: scope rewrite to `<WritingSystemOptions>` options; simultaneous (single-pass) rename; collision handling when renamed id already listed (duplicate `<Option id>` -- dedupe keeping first enabled flag); `ReversalIndex/<ws>.fwdictconfig` filename must follow a renamed root WS.
P2: handle single-quoted attributes / attribute order.

## P0
None.
