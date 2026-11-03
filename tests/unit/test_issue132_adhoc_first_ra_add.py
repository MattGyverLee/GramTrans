"""Issue #132: never-silent FirstAllomorphRA / FirstMorphemeRA on adhoc rules."""
from __future__ import annotations

from gramtrans.Lib import categories
from gramtrans.Lib.models import DroppedItemRecord


class _FakeMember:
    def __init__(self, guid: str) -> None:
        self.Guid = guid
        self.guid = guid


class _RejectFirstRa:
    def __init__(self) -> None:
        self._first = None

    @property
    def FirstAllomorphRA(self):
        return self._first

    @FirstAllomorphRA.setter
    def FirstAllomorphRA(self, value):
        raise TypeError("RA binding failed")


class _RejectFirstMorphemeRa:
    def __init__(self) -> None:
        self._first = None

    @property
    def FirstMorphemeRA(self):
        return self._first

    @FirstMorphemeRA.setter
    def FirstMorphemeRA(self, value):
        raise TypeError("RA binding failed")


def test_first_allomorph_ra_assignment_failure_records_drop():
    rule = _RejectFirstRa()
    member = _FakeMember("allo-1")
    dropped: list = []
    ok = categories._try_wire_adhoc_first_ra(
        rule, "FirstAllomorphRA", member, "rule-1", dropped,
        owner_kind="MoAlloAdhocProhib",
    )
    assert ok is False
    assert len(dropped) == 1
    rec = dropped[0]
    assert isinstance(rec, DroppedItemRecord)
    assert rec.field_name == "FirstAllomorphRA"
    assert rec.owner_guid == "rule-1"
    assert "assignment failed" in rec.reason


def test_first_morpheme_ra_assignment_failure_records_drop():
    rule = _RejectFirstMorphemeRa()
    member = _FakeMember("msa-1")
    dropped: list = []
    ok = categories._try_wire_adhoc_first_ra(
        rule, "FirstMorphemeRA", member, "rule-2", dropped,
        owner_kind="MoMorphAdhocProhib",
    )
    assert ok is False
    assert len(dropped) == 1
    assert dropped[0].field_name == "FirstMorphemeRA"
    assert "assignment failed" in dropped[0].reason
