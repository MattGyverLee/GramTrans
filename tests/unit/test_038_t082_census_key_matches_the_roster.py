"""Feature 038 T082 / `038-NK-P3`: the census was keying wider than the roster.

THE FINDING. `PhNCFeatures`'s roster entry admits the class BY PREDICATE:

    "(default analysis writing system, exact Name string of the natural class,
     restricted to members of the PhPhonData natural-class list whose class is
     PhNCFeatures, AND ONLY WHERE THAT NAME IS NOT A FLEx AUTO-GENERATED RULE
     LABEL)"

with a `key_scoping_note` that is explicit: *"AUTO-GENERATED NAMES ARE NOT
ELIGIBLE KEYS ... Such a name identifies the RULE that owns the class, not the
class ... never matched, and not treated as an ambiguity either, since the
ineligibility is decided before candidate counting."*

`Lib/matcher.py` implements it (`KEY_INELIGIBLE_AUTO_GENERATED`,
`_AUTO_GENERATED_NAME_PREFIX`, `_AUTO_GENERATED_LABEL_CLASSES`).
`Lib/census.py` did not. Two sites implementing one contract differently, with
no reader to notice -- this feature's recurring shape.

WHAT THE DRIFT COST, MEASURED ON THREE LIVE PAIRS (T124).
FLEx names every natural class it auto-creates after the rule that owns it, so
one rule owning several context classes produces several identically-named
objects **in the source**. All 36 duplicate groups the census found across the
three pairs are that label (ejagham 1, ngoreme 12, mbugwe 23). They contribute
ALL of `duplicate_extra_objects` (3 / 21 / 66) and force `DUPLICATE_IDENTITY` /
exit 3 on every pair -- while the `PhNCFeatures` row itself is MATCHED
(15->15, 41->41, 113->113) against a starter baseline of ZERO, and mbugwe's
SOURCE is independently measured at the same 113 objects / 66 collisions.
The duplication is REPRODUCED, not manufactured.

WHY A KEY FIX AND NOT AN EXEMPTION. An exemption suppresses a true reading.
This was a FALSE reading produced by the wrong key, so the correct instrument
is the right key -- which also keeps the detector live for a real
`PhNCFeatures` duplicate on a linguist-chosen name, the case actually worth
catching. Recorded because the difference decides whether a future reader may
widen the key back.

NOT CLAIMED HERE: that this clears the gate on the live pairs. That is a
re-census measurement. These tests fix the KEY's behaviour; the artifact
figures are measured elsewhere.
"""
from __future__ import annotations

import pytest

from gramtrans.Lib import census, matcher


AUTO = 'Created automatically for rule "Dahl\'s Law"'
AUTO_STARRED = 'Created automatically for rule "***"'
CHOSEN = "Nasals"


class _Alt:
    def __init__(self, text):
        self.Text = text


class _MultiString:
    def __init__(self, text):
        self._text = text

    def get_String(self, ws_handle):
        return _Alt(self._text)


class _Obj:
    """An object with a Name in the scoped writing system."""

    def __init__(self, name, guid="g"):
        self.Name = _MultiString(name)
        self.Guid = guid


WS = object()


def _definition(object_class):
    return census.NATURAL_KEY_DEFINITIONS[object_class]


# ---------------------------------------------------------------------------
# The census key now matches the roster key
# ---------------------------------------------------------------------------

def test_an_auto_generated_label_is_not_an_eligible_duplicate_key():
    """THE REGRESSION TEST. Before the fix these grouped as duplicates."""
    assert census._key_is_eligible("PhNCFeatures", AUTO) is False
    assert census._key_is_eligible("PhNCFeatures", AUTO_STARRED) is False


def test_a_linguist_chosen_name_is_still_an_eligible_key():
    """The detector must stay LIVE. Narrowing the key must not blind the
    census to a genuine duplicate on a name a person chose."""
    assert census._key_is_eligible("PhNCFeatures", CHOSEN) is True


def test_natural_key_of_stays_a_pure_name_reader():
    """LOAD-BEARING SEPARATION. `matcher` builds its key functions on
    `natural_key_of` so the two can never hold different keys, then layers its
    OWN eligibility verdicts on top -- it must be able to tell
    `KEY_INELIGIBLE_AUTO_GENERATED` from `KEY_INELIGIBLE_NO_NAME_IN_SCOPED_WS`.
    Filtering here would collapse "has an ineligible name" into "has no name",
    a different and wrong statement about the object.

    This is not hypothetical: the filter was first placed in `natural_key_of`
    and turned `test_auto_generated_natural_class_names_are_ineligible` red by
    reporting the wrong reason. This test pins the placement so it cannot
    migrate back.
    """
    assert census.natural_key_of(
        _Obj(AUTO), _definition("PhNCFeatures"), WS) == AUTO
    assert matcher.natural_key_eligibility(
        "PhNCFeatures", _Obj(AUTO), WS
    ) == matcher.KEY_INELIGIBLE_AUTO_GENERATED


def test_auto_generated_objects_do_not_group_as_duplicates():
    """Behavioural, at the level the artifact is built from: three classes
    sharing one auto-generated label are three classes, not a duplicate group
    of three."""
    objs = [_Obj(AUTO, "a"), _Obj(AUTO, "b"), _Obj(AUTO, "c")]
    grouped = census.group_by_natural_key(
        objs, _definition("PhNCFeatures"), WS)
    assert grouped == {}


def test_chosen_names_still_group_as_duplicates():
    objs = [_Obj(CHOSEN, "a"), _Obj(CHOSEN, "b")]
    grouped = census.group_by_natural_key(
        objs, _definition("PhNCFeatures"), WS)
    assert list(grouped) == [CHOSEN]
    assert len(grouped[CHOSEN]) == 2


def test_a_mixed_population_counts_only_the_chosen_name():
    """The shape of every measured pair: a handful of real classes among many
    auto-generated ones. Only the real collision may reach the report."""
    objs = [
        _Obj(AUTO, "a"), _Obj(AUTO, "b"),
        _Obj(AUTO_STARRED, "c"), _Obj(AUTO_STARRED, "d"),
        _Obj(CHOSEN, "e"), _Obj(CHOSEN, "f"),
    ]
    report = census.duplicate_report(
        "PhNCFeatures", objs, ws_handle=WS, roster_admitted=True)
    assert report is not None
    assert report.groups == 1
    assert report.extra_objects == 1


# ---------------------------------------------------------------------------
# Scope: the exclusion belongs to PhNCFeatures ALONE
# ---------------------------------------------------------------------------

def test_phncsegments_is_deliberately_left_alone():
    """`matcher`'s own comment: `PhNCSegments`' roster entry states no such
    clause, and inventing one would narrow the basis beyond what the roster
    admits. If a future edit widens `_AUTO_GENERATED_LABEL_CLASSES`, the
    roster must be amended first -- this test is the tripwire."""
    assert matcher._AUTO_GENERATED_LABEL_CLASSES == frozenset({"PhNCFeatures"})
    assert census.natural_key_of(
        _Obj(AUTO), _definition("PhNCSegments"), WS) == AUTO


@pytest.mark.parametrize(
    "object_class", ["PhPhoneme", "PartOfSpeech", "PhNCSegments"])
def test_other_admitted_classes_are_untouched(object_class):
    """A phoneme or category literally named after a rule is not a FLEx
    artefact and must keep its key."""
    assert census._key_is_eligible(object_class, AUTO) is True
    assert census.natural_key_of(
        _Obj(AUTO), _definition(object_class), WS) == AUTO


# ---------------------------------------------------------------------------
# The two sites cannot drift again
# ---------------------------------------------------------------------------

def test_the_census_defers_to_the_matcher_rather_than_restating_the_rule():
    """The whole defect was two implementations of one contract. The census
    must read the matcher's constants, so a change to the roster rule can only
    be made in one place."""
    assert census._key_is_eligible("PhNCFeatures", CHOSEN) is True
    assert census._key_is_eligible("PhNCFeatures", AUTO) is False
    assert matcher._AUTO_GENERATED_NAME_PREFIX == "Created automatically for rule"
    assert AUTO.startswith(matcher._AUTO_GENERATED_NAME_PREFIX)


def test_the_two_implementations_agree_object_for_object():
    """Cross-check the census's predicate against the matcher's eligibility
    verdict on the same strings. These are the two readers that disagreed."""
    for text, eligible in ((CHOSEN, True), (AUTO, False), (AUTO_STARRED, False)):
        census_says = census._key_is_eligible("PhNCFeatures", text)
        matcher_says = not (
            text.startswith(matcher._AUTO_GENERATED_NAME_PREFIX)
            and "PhNCFeatures" in matcher._AUTO_GENERATED_LABEL_CLASSES)
        assert census_says == matcher_says == eligible, text


def test_the_key_definition_the_artifact_emits_states_the_clause():
    """`description` is written verbatim into the artifact as
    `duplicates.key_definition`, so a reader can tell WHICH key produced a
    group. It asserted a key the roster does not define; a reader auditing the
    artifact would have had no way to notice the drift."""
    text = _definition("PhNCFeatures").description
    assert "auto-generated" in text.lower()
    assert "PhNCFeatures" in text


def test_eligibility_fails_open_when_the_rule_is_unreadable(monkeypatch):
    """A census that cannot read the matcher's rule must not silently start
    ignoring objects: under-reporting duplicates is the worse failure, because
    a suppressed duplicate looks exactly like a clean transfer.

    SCOPE, STATED SO THE GREEN IS NOT OVER-READ: this exercises the
    `getattr(..., <default>)` half of the fail-open, by removing the constants
    from the matcher. The `try/except ImportError` half around the import
    itself is NOT covered here -- monkeypatching `__import__` does not reach it
    once the submodule is bound on the package -- and is asserted only by
    inspection.
    """
    monkeypatch.delattr(matcher, "_AUTO_GENERATED_NAME_PREFIX", raising=False)
    monkeypatch.delattr(matcher, "_AUTO_GENERATED_LABEL_CLASSES", raising=False)

    assert census._key_is_eligible("PhNCFeatures", AUTO) is True
    grouped = census.group_by_natural_key(
        [_Obj(AUTO, "a"), _Obj(AUTO, "b")], _definition("PhNCFeatures"), WS)
    assert list(grouped) == [AUTO], "fail-open must still group"
