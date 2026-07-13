"""Unit tests for feature 027 (Complex Forms & Variants) cross-cutting
concerns: the never-silent drop-policy flip (contract C4), Preview/Move
parity (C5), and the empty-source regression (C7).

Resolves GitHub #30; unblocks the LexEntryRef leg of #28. See:
- specs/027-complex-forms-variants/contracts/entryref-reproduction.md (C4, C5, C7)
- specs/027-complex-forms-variants/research.md (Decision 5)

This module is scaffolded in T002 (import-smoke only); T019 adds the RED
C4 policy-flip test (in-closure reproduced -> 0 drops; out-of-closure ->
1 drop) ahead of the T020 GREEN implementation.
"""
from __future__ import annotations

from gramtrans.Lib import categories  # noqa: F401
