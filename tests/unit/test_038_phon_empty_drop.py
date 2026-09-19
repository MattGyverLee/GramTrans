"""T024f -- the inventory-level blank drop is recorded, never silent.

`_phon_is_empty` is applied twice in `selection.py`, both a bare `continue`
guarded by nothing, and `Selection` carries no field that switches it -- so
even force-all drops these. That is not what this task changes: the predicate
still decides exactly what it decided before. What changes is that the two
skips now emit a `DroppedItemRecord` apiece, so a filtered blank stops being
indistinguishable from a real loss in a `source - after` comparison.

The two sites are NOT the same event and carry DIFFERENT reason tokens:

  * source side  -- removes the item from the inventory, so it is never
    previewed and never transferred. This is the one a count-based census
    would misread as a loss.
  * target side  -- removes the item only from the pool a source row may
    MATCH against. It changes a row's `status`, and transfers nothing away.

Hermetic: fakes only, no live project.
"""
from __future__ import annotations

from _fakes_phonology import (
    FakeEnv, FakeFeature, FakeNC, FakePhoneme, FakePhonSource, FakeRule,
)

from gramtrans.Lib.models import DroppedItemRecord, GrammarCategory as GC
from gramtrans.Lib.selection import (
    PHON_EMPTY_SOURCE_DROP_REASON, PHON_EMPTY_TARGET_CANDIDATE_REASON,
    build_phonology_inventory,
)


# ---------------------------------------------------------------------------
# Blank fakes. `_PhonObj` defaults `Name` to `guid[:8]`, so "empty" has to be
# constructed deliberately -- which is the point: an item only reaches the
# predicate when FLEx really did leave every field clear.
# ---------------------------------------------------------------------------

def _blank(obj):
    """Strip every name-bearing attribute `_phon_name_text` reads."""
    obj.Name = None
    obj.name = ""
    return obj


def _blank_phoneme(guid="dead-phoneme"):
    ph = _blank(FakePhoneme(guid))
    ph.BasicIPASymbol = None
    ph.Description = None
    ph.FeaturesOA = None
    ph.CodesOS = []
    return ph


def _blank_nc(guid="dead-nc"):
    nc = _blank(FakeNC(guid, segments=()))
    nc.FeaturesOA = None
    return nc


def _blank_env(guid="dead-env"):
    env = _blank(FakeEnv(guid))
    env.StringRepresentation = None
    return env


def _blank_feature(guid="dead-feat"):
    feat = _blank(FakeFeature(guid))
    feat.ValuesOC = []
    return feat


def _live_phoneme(guid="ph-live", name="p"):
    return FakePhoneme(guid, name)


# ---------------------------------------------------------------------------


class TestTheSourceDropIsRecorded:
    """The skip that actually removes something from the transfer."""

    def test_a_blank_phoneme_is_dropped_and_says_so(self):
        source = FakePhonSource(phonemes=[_live_phoneme(), _blank_phoneme()])
        inv = build_phonology_inventory(source)

        rows = inv.group_for(GC.PHONEMES).rows
        assert [r.guid for r in rows] == ["ph-live"], (
            "the predicate's behaviour must be unchanged -- T024f records the "
            "drop, it does not stop it"
        )
        assert len(inv.dropped_items) == 1
        record = inv.dropped_items[0]
        assert isinstance(record, DroppedItemRecord)
        assert record.item_guid == "dead-phoneme"
        assert record.owner_kind == "PhonologySource"
        assert record.field_name == "Phonemes"
        assert record.owner_label == "Phonemes"
        assert record.reason == PHON_EMPTY_SOURCE_DROP_REASON

    def test_every_category_that_can_drop_does_record(self):
        """All four droppable categories, one blank each. Rules are exempt by
        design (`_phon_is_empty` returns False for PHONOLOGICAL_RULES: a
        rule's content is its structural description, not its Name), so a
        nameless rule must still be present and must NOT be recorded."""
        nameless_rule = _blank(FakeRule("rule-unnamed"))
        source = FakePhonSource(
            features=[_blank_feature()],
            phonemes=[_blank_phoneme()],
            ncs=[_blank_nc()],
            envs=[_blank_env()],
            rules=[nameless_rule],
        )
        inv = build_phonology_inventory(source)

        dropped = {r.item_guid: r for r in inv.dropped_items}
        assert set(dropped) == {
            "dead-feat", "dead-phoneme", "dead-nc", "dead-env"}
        assert {r.field_name for r in inv.dropped_items} == {
            "PhonFeatures", "Phonemes", "NaturalClasses", "Environments"}
        assert all(r.reason == PHON_EMPTY_SOURCE_DROP_REASON
                   for r in inv.dropped_items)

        rule_rows = inv.group_for(GC.PHONOLOGICAL_RULES).rows
        assert [r.guid for r in rule_rows] == ["rule-unnamed"], (
            "f4e1b83's regression: a Name-only test wrongly dropped every "
            "unnamed rule, making it un-previewable AND silently excluding it "
            "from transfer"
        )

    def test_nothing_dropped_means_an_empty_tuple_not_a_missing_field(self):
        """The additive-with-empty-default contract: a build that skips
        nothing is indistinguishable from one made before the field existed."""
        inv = build_phonology_inventory(
            FakePhonSource(phonemes=[_live_phoneme()]))
        assert inv.dropped_items == ()

    def test_the_record_survives_a_nameless_item(self):
        """An item that reached this predicate has, by construction, almost
        nothing to name it by. `item_name` is "" -- the honest answer -- and
        `DroppedItemRecord` still validates, because only owner_kind /
        field_name / reason are required non-empty."""
        inv = build_phonology_inventory(
            FakePhonSource(phonemes=[_blank_phoneme()]))
        record = inv.dropped_items[0]
        assert record.item_name == ""
        assert record.owner_guid == ""
        assert record.owner_kind and record.field_name and record.reason


class TestTheTargetDropIsRecordedSeparately:
    """The skip that only removes a MATCH CANDIDATE."""

    def test_a_blank_target_item_is_recorded_with_its_own_reason(self):
        source = FakePhonSource(phonemes=[_live_phoneme()])
        target = FakePhonSource(phonemes=[_blank_phoneme("dead-target-ph")])
        inv = build_phonology_inventory(source, target)

        assert len(inv.dropped_items) == 1
        record = inv.dropped_items[0]
        assert record.item_guid == "dead-target-ph"
        assert record.owner_kind == "PhonologyTarget"
        assert record.reason == PHON_EMPTY_TARGET_CANDIDATE_REASON

    def test_the_two_reasons_are_distinct_tokens(self):
        """If they collapsed, a reader could not tell a transfer loss from a
        match-pool trim -- which is the whole point of recording them."""
        assert (PHON_EMPTY_SOURCE_DROP_REASON
                != PHON_EMPTY_TARGET_CANDIDATE_REASON)

        source = FakePhonSource(phonemes=[_live_phoneme(), _blank_phoneme()])
        target = FakePhonSource(phonemes=[_blank_phoneme("dead-target-ph")])
        inv = build_phonology_inventory(source, target)

        by_side = {r.owner_kind: r for r in inv.dropped_items}
        assert set(by_side) == {"PhonologySource", "PhonologyTarget"}
        assert (by_side["PhonologySource"].reason
                == PHON_EMPTY_SOURCE_DROP_REASON)
        assert (by_side["PhonologyTarget"].reason
                == PHON_EMPTY_TARGET_CANDIDATE_REASON)

    def test_a_dropped_target_item_cannot_match_a_source_row(self):
        """The consequence the target-side record exists to explain: the
        source row reads `new`, not `in_target`, even though an object with
        that GUID IS present in the target."""
        shared = "shared-guid"
        source = FakePhonSource(phonemes=[_live_phoneme(shared, "p")])
        target = FakePhonSource(phonemes=[_blank_phoneme(shared)])
        inv = build_phonology_inventory(source, target)

        row = inv.group_for(GC.PHONEMES).rows[0]
        assert row.guid == shared
        assert row.status == "new"
        assert [r.owner_kind for r in inv.dropped_items] == ["PhonologyTarget"]
