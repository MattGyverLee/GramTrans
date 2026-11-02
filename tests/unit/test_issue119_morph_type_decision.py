"""Issue #119: a morph type absent from the target is a REPORTED DROP, never a
CREATE; every other possibility list still decides CREATE for a missing item.
(The live proof is tests/integration/test_issue119_anthro_morphtype_create_live.py.)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import pytest  # noqa: E402

from gramtrans.Lib import references  # noqa: E402
from gramtrans.Lib.models import (  # noqa: E402
    ReferenceAction, ReferenceCardinality, ReferenceFieldSpec,
)


class _Name:
    BestAnalysisAlternative = type("T", (), {"Text": "mt"})()


class _Item:
    Guid = "99999999-9999-9999-9999-999999999999"
    OwningPossibility = None
    Owner = None
    Name = _Name()
    ClassName = "MoMorphType"


class _List:
    def __init__(self, clsid):
        self.ItemClsid = clsid
        self.PossibilitiesOS = []


def _spec(lst):
    return ReferenceFieldSpec(
        owner_class="X", field_name="F", cardinality=ReferenceCardinality.ATOMIC,
        target_list_path=lambda _t: lst, hierarchical=False)


def test_missing_morph_type_is_reported_drop():
    lst = _List(5042)
    d = references.decide_reference(_Item(), object(), _spec(lst), {})
    assert d.action == ReferenceAction.REPORT_DROPPED
    assert d.dropped is not None and "not created" in d.dropped.reason
    assert d.dropped.item_guid == _Item.Guid


@pytest.mark.parametrize("clsid", (7, 26, 66, 5118))
def test_missing_item_in_other_lists_still_creates(clsid):
    d = references.decide_reference(_Item(), object(), _spec(_List(clsid)), {})
    assert d.action == ReferenceAction.CREATE
