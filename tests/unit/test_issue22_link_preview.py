"""Issue #22 Part 3 slice -- Preview must not promise a Merge under LINK.

Move writes nothing to an existing item under ConflictMode.LINK, so the
planner's GUID-matched ``merge`` overwrite is converted to an honest skip.
Pure fakes; no LCM host.
"""
from __future__ import annotations

import pytest

from gramtrans.Lib.models import (
    ConflictMode,
    GrammarCategory,
    PlannedOverwrite,
    Selection,
    Skip,
    SkipReason,
)
from gramtrans.Lib.preview import _link_mode_skip

CAT = GrammarCategory.GRAM_CATEGORIES


def _ow(**kw):
    base = dict(category=CAT, source_guid="abcdef12-0000", target_guid="abcdef12-0000",
                summary="Merge GUID abcdef12... [gram_categories]: update diverged",
                write_mode="merge", match_via="guid")
    base.update(kw)
    return PlannedOverwrite(**base)


def _sel(mode):
    return Selection(categories={CAT: True}, category_conflict_modes={CAT: mode})


def test_link_turns_guid_merge_into_skip():
    res = _link_mode_skip(_ow(), _sel(ConflictMode.LINK))
    assert isinstance(res, Skip)
    assert res.reason is SkipReason.ALREADY_PRESENT_BY_GUID
    assert "NOT applied" in res.detail and "update diverged" in res.detail


@pytest.mark.parametrize("mode", [ConflictMode.UPDATE, ConflictMode.OVERWRITE,
                                  ConflictMode.ADD_NEW])
def test_other_modes_keep_the_merge(mode):
    assert _link_mode_skip(_ow(), _sel(mode)) is None


def test_legacy_link_string_is_normalised_and_applies():
    assert isinstance(_link_mode_skip(_ow(), _sel("link")), Skip)


def test_natural_key_and_non_merge_overwrites_are_kept_under_link():
    assert _link_mode_skip(_ow(match_via="natural_key"), _sel(ConflictMode.LINK)) is None
    assert _link_mode_skip(_ow(write_mode="overwrite"), _sel(ConflictMode.LINK)) is None
