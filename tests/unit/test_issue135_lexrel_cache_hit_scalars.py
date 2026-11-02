"""Issue #135: LexReference Name/Comment must copy on lexrel cache-hit too."""
from __future__ import annotations

from unittest.mock import MagicMock

from gramtrans.Lib import categories


def test_lexrel_cache_hit_copies_name_and_comment(monkeypatch):
    calls = []

    def _spy(owner_class, src, new, ctx, ws_map, dropped, owner_guid):
        calls.append((owner_class, owner_guid))

    monkeypatch.setattr(categories, "_copy_supplemental_scalars", _spy)
    monkeypatch.setattr(
        categories, "_rebuild_targets_rs_in_source_order", lambda *a, **k: None)
    monkeypatch.setattr(
        categories, "_evaluate_lexical_relation",
        lambda *a, **k: ("rel-guid", MagicMock(), [MagicMock()]))

    existing = MagicMock()
    cache = {categories._LEXREL_REPRODUCED_KEY: {"rel-guid": existing}}
    src_rel = MagicMock()
    ctx = MagicMock()
    ctx._ws_map = {}

    out = categories.reproduce_lexical_relation(
        src_rel, ctx, "tag", cache, [])
    assert out is existing
    assert calls == [("LexReference", "rel-guid")]
