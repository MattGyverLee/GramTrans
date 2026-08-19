"""T024f (live half) -- nothing leaves the phonology inventory unrecorded.

The unit suite pins the two `_phon_is_empty` sites against fakes. This pins the
ACCOUNTING IDENTITY against real projects, which is the claim that actually
matters downstream:

    for every category:  enumerated == rows + source-side drops recorded

If that holds, a `source - after` comparison can subtract the recorded drops
and be left with real losses only. If it fails, something left the inventory by
a path nobody is reporting, and a count-based census cannot tell that from a
transfer defect.

The identity is corpus-independent, so this test does not pin a drop COUNT.
The measured figures are recorded here as evidence, not as assertions --
tasks.md T024f asked for the size of the set to be established empirically
rather than assumed:

    2026-08-19, read-only, this machine, 8 free projects / 921 enumerated
    phonology items:

        Ejagham Mini              41 enumerated   0 dropped
        Ejagham W Mini            83 enumerated   0 dropped
        Ejagham W Target         108 enumerated   0 dropped
        Ejagham Full              38 enumerated   0 dropped
        Ngoreme                  153 enumerated   0 dropped
        Ngoreme Johnny           122 enumerated   0 dropped
        Ngoreme Target           162 enumerated   1 dropped
        Mbugwe LizzieHC practice 214 enumerated   0 dropped

    The single drop is a NaturalClass in `Ngoreme Target`
    (ad5738e0-2a61-4e42-8f95-8db24e7b9881) with no Name, no SegmentsRC and no
    FeaturesOA. So `_phon_is_empty`'s docstring is very nearly right that the
    motivating case is "no longer reproducible in current live data" -- but it
    is NOT empty, which is exactly why T024f asked for a measurement instead
    of an assumption. One unrecorded drop is one unattributable row in the
    T024c comparison.

`Ngoreme FLEx` is deliberately absent from the roster below: it was locked by
FieldWorks when this was measured, and a locked project is a refusal, not a
number.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from gramtrans.Lib.selection import (
    PHON_EMPTY_SOURCE_DROP_REASON, PHON_EMPTY_TARGET_CANDIDATE_REASON,
    _PHON_CATEGORY_ACCESSORS, build_phonology_inventory,
)

pytestmark = pytest.mark.integration

PROJECTS_ROOT = Path("C:/ProgramData/SIL/FieldWorks/Projects")

#: Free (unlocked) projects with phonology worth walking. Every one of these is
#: opened READ-ONLY. `Esperanto` is excluded on purpose -- it is read-only in
#: the strong sense and nothing here needs it.
LIVE_PROJECTS = (
    "Ejagham Mini",
    "Ejagham W Mini",
    "Ejagham W Target",
    "Ngoreme",
    "Ngoreme Target",
    "Mbugwe LizzieHC practice",
)


def _open_or_skip(name: str):
    fwdata = PROJECTS_ROOT / name / (name + ".fwdata")
    if not fwdata.is_file():
        pytest.skip("live project not on this machine: " + str(fwdata))
    if (PROJECTS_ROOT / name / (name + ".fwdata.lock")).exists():
        pytest.skip(
            "live project " + repr(name) + " is locked by FieldWorks; a "
            "locked project is a refusal, not a measurement"
        )
    try:
        from gramtrans.Lib.flexinit import ensure_flex_initialized
        from flexicon import FLExProject
    except Exception as exc:  # noqa: BLE001
        pytest.skip("flexicon unavailable: %s" % (exc,))

    ensure_flex_initialized()
    project = FLExProject()
    try:
        project.OpenProject(projectName=name, writeEnabled=False)
    except Exception as exc:  # noqa: BLE001
        pytest.skip("could not open %r read-only: %s" % (name, exc))
    return project


def _enumerated_guids(project, accessor: str) -> list:
    from gramtrans.Lib.selection import _phon_guid

    coll = getattr(project, accessor, None)
    if coll is None:
        return []
    try:
        return [_phon_guid(o) for o in coll.GetAll()]
    except Exception:  # noqa: BLE001
        return []


@pytest.mark.parametrize("name", LIVE_PROJECTS)
def test_every_enumerated_item_is_either_a_row_or_a_recorded_drop(name):
    """THE identity. Read-only, one project per case."""
    project = _open_or_skip(name)
    try:
        inventory = build_phonology_inventory(project)
        source_drops = [r for r in inventory.dropped_items
                        if r.reason == PHON_EMPTY_SOURCE_DROP_REASON]

        for category, accessor, _label in _PHON_CATEGORY_ACCESSORS:
            enumerated = _enumerated_guids(project, accessor)
            group = inventory.group_for(category)
            rows = [] if group is None else list(group.rows)
            recorded = [r for r in source_drops if r.field_name == accessor]

            assert len(enumerated) == len(rows) + len(recorded), (
                "%s / %s: %d enumerated but %d rows + %d recorded drops -- "
                "something left the inventory by an unreported path"
                % (name, accessor, len(enumerated), len(rows), len(recorded))
            )
            assert (set(r.guid for r in rows) | set(r.item_guid for r in recorded)
                    == set(enumerated)), (
                "%s / %s: the row GUIDs and the recorded drop GUIDs do not "
                "partition what was enumerated" % (name, accessor)
            )
    finally:
        try:
            project.CloseProject()
        except Exception:  # noqa: BLE001
            pass


@pytest.mark.parametrize("name", LIVE_PROJECTS)
def test_a_recorded_drop_names_a_side_and_a_real_field(name):
    """Whatever the corpus holds, each record has to be readable: a known
    reason token, a known accessor, and a GUID."""
    project = _open_or_skip(name)
    try:
        inventory = build_phonology_inventory(project)
        accessors = {a for _c, a, _l in _PHON_CATEGORY_ACCESSORS}
        for record in inventory.dropped_items:
            assert record.reason in (PHON_EMPTY_SOURCE_DROP_REASON,
                                     PHON_EMPTY_TARGET_CANDIDATE_REASON)
            assert record.owner_kind in ("PhonologySource", "PhonologyTarget")
            assert record.field_name in accessors
            assert record.item_guid
    finally:
        try:
            project.CloseProject()
        except Exception:  # noqa: BLE001
            pass
