"""Unit tests for feature 027 (Complex Forms & Variants), US2/US3: three-way
entry-type / publication reference resolution (`VariantEntryTypesRS`,
`ComplexEntryTypesRS`, `ShowComplexFormsInRS`), contract C3.

Resolves GitHub #30; unblocks the LexEntryRef leg of #28. Reuses feature 024's
`references.decide_reference`/`apply_reference` three-way disposition
(absent -> create incl. ancestor chain; diverged custom -> update; diverged
shared/GOLD -> link + report; identical -> link). See:
- specs/027-complex-forms-variants/contracts/entryref-reproduction.md (C3)
- specs/027-complex-forms-variants/research.md (Decision 4)

This module is scaffolded in T002 (import-smoke only); T013-T014 add the
RED tests (three-way disposition, Principle-I GUID-remap) ahead of the T015
GREEN implementation.
"""
from __future__ import annotations

from gramtrans.Lib import categories  # noqa: F401
from gramtrans.Lib import references  # noqa: F401
