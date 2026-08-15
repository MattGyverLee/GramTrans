"""Feature 033 regression: the wordform/analysis GUID confusion.

Wiring wordform creation to `plan.source_guid` stamped the ANALYSIS's GUID onto
the WORDFORM. The GUID-first analysis dedup then looked up the analysis GUID,
found the wordform wearing it, concluded "already present", and skipped the
analysis -- silently. A live full transfer created 23 analyses instead of 143
(and 35 glosses instead of 231, 46 morph bundles instead of 283).

Two independent guards, either of which alone would have prevented it:
  1. the wordform is created from AnalysisPlan.wordform_guid, never source_guid
  2. `_resolve_by_guid` is class-checked, so a GUID worn by the wrong class of
     object is not accepted as a match
"""
from __future__ import annotations

import types

from gramtrans.Lib import wordforms
from gramtrans.Lib.models import AnalysisPlan


class _Obj:
    def __init__(self, guid, class_name):
        self.guid = guid
        self.Guid = guid
        self.ClassName = class_name


class _Target:
    def __init__(self, registry):
        self._registry = registry

    def get_object_by_guid(self, guid):
        return self._registry.get(guid)


def test_wordform_is_created_with_the_wordform_guid_not_the_analysis_guid():
    plan = AnalysisPlan(source_guid="analysis-guid",
                        wordform_guid="wordform-guid",
                        wordform_form={"en": "run"})
    seen = {}

    class _WfOps:
        def Find(self, form, handle):
            return None

        def Create(self, form, handle, guid=None):
            seen["guid"] = guid
            return _Obj(guid or "minted", "WfiWordform")

    out = wordforms._find_or_create_wordform(
        plan, _WfOps(), {"en": "en"}, {"en": 1}, [])

    assert out is not None
    assert seen["guid"] == "wordform-guid"
    assert seen["guid"] != plan.source_guid


def test_missing_wordform_guid_mints_rather_than_reusing_the_analysis_guid():
    """An older plan without wordform_guid must mint, NOT fall back to
    source_guid -- the fallback is what caused the collision."""
    plan = AnalysisPlan(source_guid="analysis-guid", wordform_form={"en": "run"})
    seen = {}

    class _WfOps:
        def Find(self, form, handle):
            return None

        def Create(self, form, handle, guid=None):
            seen["guid"] = guid
            return _Obj("minted", "WfiWordform")

    wordforms._find_or_create_wordform(plan, _WfOps(), {"en": "en"}, {"en": 1}, [])

    assert seen["guid"] is None


def test_guid_lookup_rejects_an_object_of_the_wrong_class():
    """The precise failure: a WfiWordform wearing the analysis's GUID must NOT
    satisfy a lookup for that analysis."""
    target = _Target({"analysis-guid": _Obj("analysis-guid", "WfiWordform")})

    assert wordforms._resolve_by_guid(
        target, "analysis-guid", expect_class="WfiAnalysis") is None


def test_guid_lookup_accepts_the_right_class():
    target = _Target({"analysis-guid": _Obj("analysis-guid", "WfiAnalysis")})

    found = wordforms._resolve_by_guid(
        target, "analysis-guid", expect_class="WfiAnalysis")

    assert found is not None
    assert found.ClassName == "WfiAnalysis"


def test_guid_lookup_tolerates_fakes_without_a_classname():
    """Duck fakes with no ClassName must still resolve (offline test shape)."""
    target = _Target({"g": types.SimpleNamespace(guid="g")})

    assert wordforms._resolve_by_guid(target, "g", expect_class="WfiAnalysis") is not None
