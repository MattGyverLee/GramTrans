"""Feature 035 -- T045d: the generic field reader's dispatch table and
model_fields enumeration.

NO FLEx project and NO LCM in this file. ``field_dispatch.build_field_source``
is the LIVE half (it lazily imports ``SIL.LCModel``, which requires
``flexicon.FLExInitialize()`` to have already run); it is exercised instead by
``debug/probe_field_dispatch_t045d.py`` against a real, read-only project
(``Ejagham Mini``), the same split ``debug/probe_field_census_api.py`` and
``census.py`` already use elsewhere in this feature. Everything testable
offline -- the dispatch tables' structural integrity and
``model_fields_for_class``'s pure-python MDC-shape logic -- is tested here
with fakes.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from debug.fullsweep import census, field_dispatch as fd  # noqa: E402


# ===========================================================================
# A fake MDC, standing in for IFwMetaDataCacheManaged
# ===========================================================================

class _FakeMdc:
    """Minimal stand-in for ``IFwMetaDataCacheManaged``.

    ``fields`` maps class name -> list of (flid, field_name, cellar_type,
    is_virtual) tuples, exactly the shape ``model_fields_for_class`` reads.
    """

    def __init__(self, fields):
        self._fields = fields

    def GetClassId(self, class_name):
        if class_name not in self._fields:
            raise KeyError("no such class: %r" % (class_name,))
        return hash(class_name) or 1  # any truthy value

    def GetFields(self, clid, include_base, cpt_filter):
        for class_name, rows in self._fields.items():
            if (hash(class_name) or 1) == clid:
                return [flid for (flid, _name, _ctype, _virt) in rows]
        return []

    def get_IsVirtual(self, flid):
        for rows in self._fields.values():
            for (fi, _name, _ctype, virt) in rows:
                if fi == flid:
                    return virt
        return False

    def GetFieldName(self, flid):
        for rows in self._fields.values():
            for (fi, name, _ctype, _virt) in rows:
                if fi == flid:
                    return name
        raise KeyError(flid)

    def GetFieldType(self, flid):
        for rows in self._fields.values():
            for (fi, _name, ctype, _virt) in rows:
                if fi == flid:
                    return ctype
        raise KeyError(flid)


_CPT_ALL = 0  # the fake never inspects the filter value


# ===========================================================================
# model_fields_for_class
# ===========================================================================

class TestModelFieldsForClass:

    def test_bare_scalar_field_included_once(self):
        mdc = _FakeMdc({"C": [(5001, "Name", 13, False)]})  # 13 = String
        model = fd.model_fields_for_class(mdc, _CPT_ALL, "C")
        assert "Name" in model

    def test_owning_atomic_gets_bare_suffix_and_guid_alias(self):
        """FR-051 shape: a GetSyncableProperties override may spell an OA
        field bare ("DefaultFeatures"), suffixed ("DefaultFeaturesOA", the
        C# accessor name), or as a synthesized "...Guid" convenience key
        (POS's DefaultFeaturesGuid) -- all three are the same field."""
        mdc = _FakeMdc({"C": [(5001, "DefaultFeatures", 23, False)]})  # 23 = OA
        model = fd.model_fields_for_class(mdc, _CPT_ALL, "C")
        assert {"DefaultFeatures", "DefaultFeaturesOA", "DefaultFeaturesGuid"} <= model

    def test_reference_atomic_gets_ra_suffix(self):
        mdc = _FakeMdc({"C": [(5001, "MorphoSyntaxAnalysis", 24, False)]})  # 24 = RA
        model = fd.model_fields_for_class(mdc, _CPT_ALL, "C")
        assert {"MorphoSyntaxAnalysis", "MorphoSyntaxAnalysisRA"} <= model

    def test_reference_collection_gets_rc_suffix(self):
        mdc = _FakeMdc({"C": [(5001, "DoNotPublishIn", 26, False)]})  # 26 = RC
        model = fd.model_fields_for_class(mdc, _CPT_ALL, "C")
        assert {"DoNotPublishIn", "DoNotPublishInRC"} <= model

    def test_owning_sequence_gets_os_suffix(self):
        mdc = _FakeMdc({"C": [(5001, "AffixTemplates", 27, False)]})  # 27 = OS
        model = fd.model_fields_for_class(mdc, _CPT_ALL, "C")
        assert {"AffixTemplates", "AffixTemplatesOS"} <= model

    def test_reference_sequence_gets_rs_suffix(self):
        mdc = _FakeMdc({"C": [(5001, "Foo", 28, False)]})  # 28 = RS
        model = fd.model_fields_for_class(mdc, _CPT_ALL, "C")
        assert {"Foo", "FooRS"} <= model

    def test_guid_is_always_present(self):
        """Every CmObject has a Guid; several GetSyncableProperties overrides
        emit it (verified live: PossibilityItemOperations always does), and
        it is not itself an MDC field."""
        mdc = _FakeMdc({"C": [(5001, "Name", 13, False)]})
        model = fd.model_fields_for_class(mdc, _CPT_ALL, "C")
        assert "Guid" in model

    def test_structural_field_excluded(self):
        mdc = _FakeMdc({"C": [(150, "Owner", 24, False), (5001, "Name", 13, False)]})
        model = fd.model_fields_for_class(mdc, _CPT_ALL, "C")
        assert "Owner" not in model
        assert "Name" in model

    def test_virtual_field_excluded(self):
        mdc = _FakeMdc({"C": [(5001, "ComputedThing", 13, True),
                               (5002, "Name", 13, False)]})
        model = fd.model_fields_for_class(mdc, _CPT_ALL, "C")
        assert "ComputedThing" not in model
        assert "Name" in model

    def test_unknown_class_raises_contract_error(self):
        mdc = _FakeMdc({"C": [(5001, "Name", 13, False)]})
        with pytest.raises(census.CensusContractError, match="no class"):
            fd.model_fields_for_class(mdc, _CPT_ALL, "Ghost")

    def test_class_with_only_structural_or_virtual_fields_raises(self):
        """FR-051: an unenumerable class is not an empty one."""
        mdc = _FakeMdc({"C": [(150, "Owner", 24, False),
                               (5001, "Virt", 13, True)]})
        with pytest.raises(census.CensusContractError, match="no model fields"):
            fd.model_fields_for_class(mdc, _CPT_ALL, "C")


# ===========================================================================
# The dispatch tables: structural integrity
# ===========================================================================

class TestDispatchTableIntegrity:

    def test_mandatory_and_discovered_unreachable_do_not_overlap(self):
        mandatory = set(fd.MANDATORY_UNREACHABLE_CLASSES)
        discovered = set(fd.DISCOVERED_UNREACHABLE_CLASSES)
        assert not (mandatory & discovered)

    def test_unreachable_classes_is_exactly_the_union(self):
        assert set(fd.UNREACHABLE_CLASSES) == (
            set(fd.MANDATORY_UNREACHABLE_CLASSES)
            | set(fd.DISCOVERED_UNREACHABLE_CLASSES)
        )

    def test_mandatory_three_are_present(self):
        """The exact hole T045d's task text names -- must not be skipped."""
        assert {"MoAdhocProhibGr", "MoAlloAdhocProhib", "MoMorphAdhocProhib"} \
            <= set(fd.MANDATORY_UNREACHABLE_CLASSES)

    def test_no_class_is_both_dispatchable_and_unreachable(self):
        dispatchable = set(fd.CLASS_TO_ACCESSOR) | set(fd.POSSIBILITY_GENERIC_CLASSES)
        assert not (dispatchable & set(fd.UNREACHABLE_CLASSES))

    def test_class_to_accessor_and_possibility_generic_are_disjoint(self):
        assert not (set(fd.CLASS_TO_ACCESSOR) & fd.POSSIBILITY_GENERIC_CLASSES)

    def test_every_reason_is_a_non_empty_string(self):
        for cls, reason in fd.UNREACHABLE_CLASSES.items():
            assert isinstance(reason, str) and reason.strip(), cls


# ===========================================================================
# is_dispatchable / partition_dispatchable
# ===========================================================================

class TestPartitionDispatchable:

    def test_mapped_class_is_dispatchable(self):
        assert fd.is_dispatchable("PartOfSpeech") is True

    def test_generic_possibility_class_is_dispatchable(self):
        assert fd.is_dispatchable("MoMorphType") is True

    def test_mandatory_unreachable_is_not_dispatchable(self):
        assert fd.is_dispatchable("MoAdhocProhibGr") is False

    def test_discovered_unreachable_is_not_dispatchable(self):
        assert fd.is_dispatchable("TextTag") is False

    def test_genuinely_unmapped_class_is_not_dispatchable(self):
        assert fd.is_dispatchable("CmPicture") is False

    def test_partition_splits_all_three_buckets_correctly(self):
        classes = ["PartOfSpeech", "MoMorphType", "MoAdhocProhibGr",
                   "TextTag", "CmPicture"]
        dispatchable, unreachable = fd.partition_dispatchable(classes)
        assert dispatchable == ["PartOfSpeech", "MoMorphType"]
        assert set(unreachable) == {"MoAdhocProhibGr", "TextTag", "CmPicture"}
        # the mandatory hole's reason is the one on record, not a generic one
        assert unreachable["MoAdhocProhibGr"] == fd.UNREACHABLE_CLASSES["MoAdhocProhibGr"]
        # a genuinely-unmapped class gets its OWN distinguishable reason,
        # never confused with a recognized hole
        assert "not one of the recognized unreachable holes" in unreachable["CmPicture"]

    def test_partition_never_calls_anything_live(self):
        """Pure data lookup -- must work with no flexicon/LCM importable at
        all, which this whole test file already proves by never importing
        SIL.LCModel, but is asserted explicitly here as the load-bearing
        guarantee callers rely on before ever opening a project."""
        dispatchable, unreachable = fd.partition_dispatchable(
            list(fd.CLASS_TO_ACCESSOR) + list(fd.UNREACHABLE_CLASSES))
        assert set(dispatchable) == set(fd.CLASS_TO_ACCESSOR)
        assert set(unreachable) == set(fd.UNREACHABLE_CLASSES)


# ===========================================================================
# UnreachableClassError
# ===========================================================================

class TestUnreachableClassError:

    def test_is_a_census_contract_error(self):
        """So a caller that only catches CensusContractError (the
        established idiom throughout census.py) still catches this."""
        assert issubclass(fd.UnreachableClassError, census.CensusContractError)

    def test_message_names_the_class_and_reason(self):
        exc = fd.UnreachableClassError("MoAdhocProhibGr", "some reason")
        assert "MoAdhocProhibGr" in str(exc)
        assert "some reason" in str(exc)
        assert exc.cls == "MoAdhocProhibGr"
        assert exc.reason == "some reason"


# ===========================================================================
# coverage-floor.json cross-check: the 66-present-class roster this module
# was built against, so a future edit to either side is caught here rather
# than only discovered live.
# ===========================================================================

class TestAgainstCoverageFloor:

    @pytest.fixture
    def present_classes(self):
        import json
        p = (_ROOT / "specs" / "035-fullsweep-fidelity" / "contracts"
             / "coverage-floor.json")
        d = json.loads(p.read_text(encoding="utf-8"))
        absent = {e["class"] for e in d["known_absent_corpus_wide"]}
        return [c for c in d["in_scope_classes"] if c not in absent]

    def test_mandatory_three_are_in_scope(self, present_classes):
        assert {"MoAdhocProhibGr", "MoAlloAdhocProhib", "MoMorphAdhocProhib"} \
            <= set(present_classes)

    def test_majority_of_present_classes_are_dispatchable(self, present_classes):
        """A regression guard, not a completeness claim: if this number
        drops, something that used to be reachable stopped being mapped."""
        dispatchable, _unreachable = fd.partition_dispatchable(present_classes)
        assert len(dispatchable) >= 45
