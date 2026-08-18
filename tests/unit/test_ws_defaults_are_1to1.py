"""`closest_ws_defaults` must propose a mapping the wizard can actually build.

Regression tests for a live failure on `Ngoreme FLEx` -> `Ngoreme Target`:
clicking Dry run did nothing at all. The reason was a proposal that is not
injective --

    ValueError: WS mapping not 1:1: 'en' and 'swh' both map to 'en'

-- raised by `WSMapping.__post_init__` out of a Qt slot, where an exception is
either a dead button or an `abort()`.

The source had analysis writing systems `en` and `swh`; the target had `en`.
`en` was mapped to itself by the wizard's identity rule, while `swh` -- which is
a different LANGUAGE, not a variant of `en` -- reached Pass 3, had an empty
subtag suffix, and was "rebased" onto the bare target base `en`. Two languages,
one target field.

`closest_ws_defaults` had no unit tests before this file, which is how it
shipped.
"""

from __future__ import annotations

import pytest

from gramtrans.Lib.models import WSKind, WSMapping, WSMappingEntry
from gramtrans.Lib.ws_mapping import closest_ws_defaults


class FakeProject:
    """Duck-typed stand-in exposing only what `_enumerate_ws` reads."""

    def __init__(self, vernacular=(), analysis=()) -> None:
        self._v = list(vernacular)
        self._a = list(analysis)

    # `_enumerate_ws` goes through flexicon's WritingSystems.GetAll(); the
    # tests patch it instead, so this class only needs to be identifiable.


@pytest.fixture(autouse=True)
def fake_enumerate(monkeypatch):
    """Make `_enumerate_ws` read the FakeProject's declared lists."""
    from gramtrans.Lib import ws_mapping

    def _fake(project):
        out = []
        for wid in project._v:
            out.append({"id": wid, "kind": WSKind.VERNACULAR, "handle": 0})
        for wid in project._a:
            out.append({"id": wid, "kind": WSKind.ANALYSIS, "handle": 0})
        return out

    monkeypatch.setattr(ws_mapping, "_enumerate_ws", _fake)


def effective_mapping(source, target) -> dict:
    """What the WIZARD ends up with: identity rows plus the proposals.

    `closest_ws_defaults` omits identity rows, so its own output being 1:1 is
    not enough -- the collision that broke Dry run was between a proposal and an
    omitted identity row. This mirrors `_PageWritingSystems`' row defaults:
    a source Id present in the target MAPs to itself, else the proposal is used,
    else CREATE under the source tag.
    """
    from gramtrans.Lib import ws_mapping

    proposals = closest_ws_defaults(source, target)
    tgt_ids = {w["id"] for w in ws_mapping._enumerate_ws(target)}
    out = {}
    for w in ws_mapping._enumerate_ws(source):
        sid = w["id"]
        if sid in tgt_ids:
            out[sid] = sid
        elif sid in proposals:
            out[sid] = proposals[sid][1]
        else:
            out[sid] = sid
    return out


def assert_is_1to1(source, target) -> dict:
    """The proposal must survive the invariant the wizard enforces on it."""
    from gramtrans.Lib import ws_mapping

    mapping = effective_mapping(source, target)
    by_target: dict = {}
    for sid, tid in mapping.items():
        assert tid not in by_target, (
            f"not 1:1: {by_target.get(tid)!r} and {sid!r} both map to {tid!r}"
        )
        by_target[tid] = sid

    # And the real invariant, not just our restatement of it: build the thing
    # the wizard builds. This is what actually raised.
    kinds = {w["id"]: w["kind"] for w in ws_mapping._enumerate_ws(source)}
    WSMapping(entries=tuple(
        WSMappingEntry(source_ws_id=s, source_ws_kind=kinds[s], target_ws_id=t)
        for s, t in mapping.items()
    ))
    return mapping


# ---------------------------------------------------------------------------
# The live failure
# ---------------------------------------------------------------------------

def test_ngoreme_en_plus_swh_into_en_is_1to1():
    """The exact shape that made Dry run do nothing."""
    source = FakeProject(vernacular=["ngq"], analysis=["en", "swh"])
    target = FakeProject(vernacular=["ngq"], analysis=["en"])
    mapping = assert_is_1to1(source, target)
    # `en` keeps the identity row it already had...
    assert mapping["en"] == "en"
    # ...and Swahili must NOT be merged into the English field.
    assert mapping["swh"] != "en"


def test_a_distinct_language_is_created_under_its_own_tag_not_rebased():
    """Rebasing only makes sense for a VARIANT of the primary.

    `swh` does not extend `en`, so the rebase that produced `en` was wrong on
    the data quite apart from the collision: it proposed writing Swahili into
    English.
    """
    source = FakeProject(analysis=["en", "swh"])
    target = FakeProject(analysis=["en"])
    proposals = closest_ws_defaults(source, target)
    assert proposals["swh"] == ("create", "swh")


def test_the_collision_reproduces_on_the_old_behaviour():
    """Guard the guard: the invariant really does reject the old proposal.

    If this stops raising, `WSMapping` has been loosened and the tests above
    would pass for the wrong reason.
    """
    with pytest.raises(ValueError, match="not 1:1"):
        WSMapping(entries=(
            WSMappingEntry("en", WSKind.ANALYSIS, "en"),
            WSMappingEntry("swh", WSKind.ANALYSIS, "en"),
        ))


# ---------------------------------------------------------------------------
# The documented behaviour that must NOT regress (feature 032 US4)
# ---------------------------------------------------------------------------

def test_primary_still_bridges_differing_base_subtags():
    """`eja` -> `abc`: the whole point of the primary rule."""
    source = FakeProject(vernacular=["eja"], analysis=["en"])
    target = FakeProject(vernacular=["abc"], analysis=["en"])
    proposals = closest_ws_defaults(source, target)
    assert proposals["eja"] == ("map", "abc")


def test_variant_suffixes_still_match_one_to_one_and_rebase():
    """Exact-suffix match wins; a leftover variant is rebased onto the target."""
    source = FakeProject(vernacular=["eja", "eja-fonipa", "eja-x-emic"])
    target = FakeProject(vernacular=["abc", "abc-fonipa"])
    proposals = closest_ws_defaults(source, target)
    assert proposals["eja"] == ("map", "abc")
    assert proposals["eja-fonipa"] == ("map", "abc-fonipa")
    # No target variant left: rebased onto the TARGET base, not the source's.
    assert proposals["eja-x-emic"] == ("create", "abc-x-emic")
    assert_is_1to1(source, target)


def test_a_variant_is_never_given_a_target_an_identity_row_owns():
    """The identity row wins; the variant is created instead of merged."""
    source = FakeProject(vernacular=["eja", "abc-fonipa"])
    target = FakeProject(vernacular=["abc", "abc-fonipa"])
    mapping = assert_is_1to1(source, target)
    assert mapping["abc-fonipa"] == "abc-fonipa"   # identity
    assert mapping["eja"] == "abc"                 # primary bridge, uncontested


def test_primary_yields_when_its_target_is_already_an_identity_row():
    """Two source primaries cannot both take the target primary."""
    source = FakeProject(analysis=["abc", "def"])
    target = FakeProject(analysis=["abc"])
    mapping = assert_is_1to1(source, target)
    assert mapping["abc"] == "abc"
    assert mapping["def"] != "abc"


@pytest.mark.parametrize("src_analysis,tgt_analysis", [
    (["en", "swh"], ["en"]),
    (["en", "swh", "fr"], ["en"]),
    (["swh", "en"], ["en", "swh"]),
    (["en"], ["en", "swh"]),
    (["en", "en-x-lit"], ["en"]),
    (["eja", "eja-fonipa", "eja-x-emic"], ["abc"]),
    (["abc", "def", "ghi"], ["abc", "def"]),
])
def test_never_proposes_a_non_1to1_mapping(src_analysis, tgt_analysis):
    """Whatever the shape, the wizard must be able to build the result."""
    source = FakeProject(vernacular=["ngq"], analysis=src_analysis)
    target = FakeProject(vernacular=["ngq"], analysis=tgt_analysis)
    assert_is_1to1(source, target)


def test_every_source_ws_still_gets_an_answer():
    """1:1 must not be achieved by dropping rows on the floor."""
    source = FakeProject(vernacular=["ngq"], analysis=["en", "swh", "fr"])
    target = FakeProject(vernacular=["ngq"], analysis=["en"])
    mapping = effective_mapping(source, target)
    assert set(mapping) == {"ngq", "en", "swh", "fr"}
    assert all(mapping.values()), "a source WS was left with no target"
