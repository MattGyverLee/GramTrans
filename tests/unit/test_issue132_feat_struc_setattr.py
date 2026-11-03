"""Issue #132: `_get_or_create_feat_struc` must not leave a created structure
orphaned when assigning it to the owner fails (never-silent audit, impl-111)."""
from __future__ import annotations

import types

from gramtrans.Lib import categories


class _RejectSetattr:
    """MSA whose InflFeatsOA setter raises (LCM binding failure)."""

    def __init__(self):
        self._infl = None

    @property
    def InflFeatsOA(self):
        return self._infl

    @InflFeatsOA.setter
    def InflFeatsOA(self, value):
        raise TypeError("InflFeatsOA assignment rejected")


class _DuckFactory:
    def Create(self, guid=None):
        return types.SimpleNamespace(
            Guid=str(guid) if guid else "new-guid",
            TypeRA=None,
        )


def test_setattr_failure_returns_none_not_orphan(monkeypatch):
    monkeypatch.setattr(categories, "_lcm_factory", lambda *_a, **_k: _DuckFactory())
    monkeypatch.setattr(categories, "_parse_guid", lambda g: g or None)
    msa = _RejectSetattr()
    out = categories._get_or_create_feat_struc(
        object(), msa, "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "")
    assert out is None
    assert msa.InflFeatsOA is None


def test_type_ra_assignment_failure_logs_warning(monkeypatch, caplog):
    import logging

    class _Struc:
        TypeRA = None

    class _Factory:
        def Create(self, guid=None):
            return _Struc()

    monkeypatch.setattr(categories, "_lcm_factory", lambda *_a, **_k: _Factory())
    monkeypatch.setattr(categories, "_parse_guid", lambda g: g or None)
    monkeypatch.setattr(categories, "_resolve_target_by_guid", lambda *_a, **_k: object())
    monkeypatch.setattr(
        categories, "_cast_lcm",
        lambda obj, _iface: (_ for _ in ()).throw(TypeError("cast failed")),
    )
    msa = types.SimpleNamespace(InflFeatsOA=None)
    with caplog.at_level(logging.WARNING, logger="gramtrans.Lib.categories"):
        out = categories._get_or_create_feat_struc(
            object(), msa, "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
    assert out is not None
    assert msa.InflFeatsOA is out
    assert any("TypeRA wiring failed" in r.message for r in caplog.records)
