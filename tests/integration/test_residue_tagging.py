"""T062 / FR-010 / Q5: Import Residue tag readable + parseable in the target.

The original scaffold was a fictional-API ``if False`` body: it imported
``gramtrans.Lib.residue.read_residue_carrier`` (which does not exist) and
called ``ctx.target_project.get_object_by_guid`` on a context that
``run_full_transfer`` has already closed. Both are removed here rather than
left as misleading dead code.

The serialize/parse contract for ``ImportResidueTag`` is already covered at
the unit level by ``tests/unit/test_residue_format.py``. The INTEGRATION-only
part — that a tag is physically written to each added LIVE object and reads
back parseable — genuinely needs target object access AFTER the Move, which
requires two pieces the repo does not have yet:

  1. a harness helper that reopens the target read-only and returns an object
     by GUID (``full_run`` only exposes count-level ``reopen_and_count``);
  2. a public ``residue`` reader that pulls the carrier value (LiftResidue for
     Carrier-A classes, or the ``[GT-Tag]:`` Description line for Carrier B)
     back off a live object.

Until both land this module honestly skips (matching the style of
``test_gold_inviolable.py``) instead of asserting through a fake surface.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


@pytest.mark.skip(
    reason="Live residue read-back needs (1) a harness reopen-and-fetch-object "
    "helper and (2) a public residue carrier reader; neither exists yet. The "
    "tag serialize/parse contract is unit-covered in test_residue_format.py."
)
def test_every_added_object_has_parseable_residue_tag() -> None:  # pragma: no cover
    """FR-010/Q5: every object added by Move carries a residue tag that reads
    back and parses via ImportResidueTag.parse, with run_id / source name /
    timestamp populated. Blocked on the two helpers named in the module
    docstring."""
    ...
