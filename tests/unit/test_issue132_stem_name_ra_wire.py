"""Issue #132 -- never-silent StemNameRA assignment helper."""
from __future__ import annotations

from types import SimpleNamespace

from gramtrans.Lib import categories


class _Stem:
    def __init__(self, guid):
        self.guid = guid


def test_try_wire_stem_name_ra_records_drop_on_setattr_failure():
    stem = _Stem("sn1")
    allo = SimpleNamespace(StemNameRA=None)

    @property
    def _reject_set(_self):
        return None

    class _Reject(SimpleNamespace):
        @property
        def StemNameRA(self):
            return None

        @StemNameRA.setter
        def StemNameRA(self, _value):
            raise TypeError("binding rejected")

    tgt = _Reject()
    dropped = []
    ok = categories._try_wire_allomorph_stem_name_ra(
        tgt, stem, "sn1", owner_guid="al1",
        src_allo=SimpleNamespace(StemNameRA=stem), dropped=dropped)
    assert ok is False
    assert len(dropped) == 1
    assert dropped[0].field_name == "StemNameRA"
    assert "WRITE_FAILED" in dropped[0].reason
