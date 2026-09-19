# t123b probe directory

This directory holds the 2026-08-28 16:58 post-T123-fix re-probe of the
throwaway `GT038 T124 Ngoreme` destination project, run via
`debug/run038_t124_recensus.py --tag t123b` (feature worktree
`GramTrans-038-transfer-fidelity-gaps`).

It was originally misfiled into `probes/t124/` and overwrote the pinned T124
owner-probe reading, because the driver's `--tag` guard reparametrizes only
the census/report filenames, not the hardcoded `_PROBE_OUT` probe path. That
overwrite has been reverted (`git checkout --` restored HEAD's pinned t124
reading byte-for-byte); this copy preserves the genuine t123b re-probe data
instead of discarding it.

The companion `t124-supplements-Ngoreme-FLEx.json` is **not** duplicated
here: that file was rewritten byte-identically by the same run (`git diff
--quiet` against HEAD exits 0), because it describes the SOURCE project
(`Ngoreme FLEx`), which did not change -- only the destination (`GT038 T124
Ngoreme`) did. The byte-identity is corroborating evidence that this run's
only real effect was on the destination-side owner-probe, consistent with a
post-fix re-probe rather than an unrelated or partial run.

See `reviews/cycle1-verification-probe.md` for the full provenance analysis.
