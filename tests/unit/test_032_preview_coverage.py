"""Feature 032 — Preview coverage completion (US1 blank, US2 thin, US3 regression guard).

Offline, Qt-free, LCM-free. Uses duck-typed fakes and plain-dict multistrings
(``_ms_to_dict`` accepts a plain dict directly). Live behaviour was separately
proven read-only via FLExToolsMCP against ``Ejagham Mini`` (texts / writing
systems / complex form types) and ``Mbugwe LizzieHC practice`` (ad hoc rules,
slots, phonological features, phonological rules); see
specs/032-preview-coverage-completion/research.md (T004) and
contracts/adhoc-loss-probe.md is out of P1 scope.

Covers:
- T005  bounded excerpt / bounded list helpers (FR-018)
- T007  US1 props-shape for Text / Writing System / Complex Form Type / Ad hoc
- T008  US1 non-blank result for a populated fixture
- T009  US1 create-case (source-only) + graceful degradation (read failure)
- T010  dispatch registration (four categories resolve to a non-None reader)
- T016  US2 enrichment: Phon Feature {Type, Values}, Phon Rule {Structure}, Slot {Affixes}
- T017  US2 bounded Slot affix list (FR-018; note wording per spec-036 FR-037 --
        the cap is disclosed WITH the true total, not as a bare "truncated")
- T022  US3 Natural Class Members/Features delivery is load-bearing (absent
        without the enrich step, present with it — on identical fixture data)
"""
from __future__ import annotations

import pytest

from gramtrans.Lib import merge_preview as mp
from gramtrans.Lib.merge_preview import (
    _CATEGORY_VALUE_TO_KEY,
    _DEDICATED_READERS,
    _bounded_excerpt,
    _bounded_list,
    _enrich_natural_class,
    _enrich_phon_feature,
    _enrich_phon_rule,
    _enrich_slot,
    _resolve_category_key,
    props_for,
)
from gramtrans.Lib.models import GrammarCategory
from gramtrans.Lib.selection import (
    _nonempty_seq,
    _phon_is_empty,
    _phon_strucrep_text,
)


# ===========================================================================
# Duck-typed fakes
# ===========================================================================


class FakeGuidObj:
    """Object whose GUID is read via the `.guid` fallback in `_obj_guid`."""

    def __init__(self, guid, **attrs):
        self.guid = guid
        for k, v in attrs.items():
            setattr(self, k, v)


class FakeTextOps:
    def __init__(self, texts, name_by_guid, paras_by_guid):
        self._texts = texts
        self._names = name_by_guid
        self._paras = paras_by_guid

    def GetAll(self):
        return self._texts

    def GetName(self, text):
        return self._names.get(text.guid, "")

    def GetParagraphs(self, text):
        return self._paras.get(text.guid, [])


class FakeSegOps:
    def __init__(self, segs_by_para, baseline_by_seg):
        self._segs = segs_by_para
        self._baselines = baseline_by_seg

    def GetAll(self, para):
        return self._segs.get(para.guid, [])

    def GetBaselineText(self, seg):
        return self._baselines.get(seg.guid, "")


class FakeTextHandle:
    def __init__(self, text_ops, seg_ops=None):
        self.Texts = text_ops
        if seg_ops is not None:
            self.Segments = seg_ops


class FakeWs:
    def __init__(self, ws_id, name):
        self.Id = ws_id
        self.DisplayLabel = name


class FakeWsOps:
    def __init__(self, all_ws, vern_ws):
        self._all = all_ws
        self._vern = vern_ws

    def GetAll(self):
        return self._all

    def GetVernacular(self):
        return self._vern


class FakeWsHandle:
    def __init__(self, ws_ops):
        self.WritingSystems = ws_ops


# ===========================================================================
# T005 — bounded excerpt / list helpers (FR-018)
# ===========================================================================


class TestBounding:
    def test_short_string_not_truncated(self):
        excerpt, truncated = _bounded_excerpt("short baseline")
        assert excerpt == "short baseline"
        assert truncated is False

    def test_long_string_truncated_with_flag(self):
        long = "x" * 500
        excerpt, truncated = _bounded_excerpt(long)
        assert truncated is True
        assert len(excerpt) <= mp._EXCERPT_CHAR_LIMIT + 1  # + ellipsis
        assert excerpt.endswith("…")

    def test_empty_string(self):
        assert _bounded_excerpt("") == ("", False)
        assert _bounded_excerpt(None) == ("", False)

    def test_short_list_not_truncated(self):
        lst, truncated = _bounded_list(["a", "b", "c"])
        assert lst == ["a", "b", "c"]
        assert truncated is False

    def test_long_list_truncated(self):
        items = [str(i) for i in range(100)]
        lst, truncated = _bounded_list(items)
        assert truncated is True
        assert len(lst) == mp._LIST_ITEM_LIMIT


# ===========================================================================
# T010 — dispatch registration (four blank categories now resolve)
# ===========================================================================


class TestDispatchRegistration:
    @pytest.mark.parametrize(
        "category",
        ["texts", "writing_systems_check", "complex_form_types", "adhoc_compound_rules"],
    )
    def test_category_resolves_to_reader(self, category):
        key = _resolve_category_key(category)
        assert key is not None, f"{category} should no longer map to None"
        assert key in _DEDICATED_READERS, f"{category} should have a dedicated reader"

    def test_map_no_longer_blanks_the_four(self):
        for cat in ("texts", "writing_systems_check", "complex_form_types",
                    "adhoc_compound_rules"):
            assert _CATEGORY_VALUE_TO_KEY.get(cat) is not None


# ===========================================================================
# US1 — Text reader (T007/T008/T009)
# ===========================================================================


class TestTextReader:
    def _handle(self, baseline="1 nnat nnyone 2 anat mbane"):
        text = FakeGuidObj("text-1")
        para = FakeGuidObj("para-1")
        seg = FakeGuidObj("seg-1")
        text_ops = FakeTextOps([text], {"text-1": "W Noun Interrogatives"},
                               {"text-1": [para]})
        seg_ops = FakeSegOps({"para-1": [seg]}, {"seg-1": baseline})
        return FakeTextHandle(text_ops, seg_ops)

    def test_text_populated_non_blank(self):
        props = props_for(self._handle(), "texts", "text-1")
        assert props  # non-empty (SC-001)
        assert props["Title"] == "W Noun Interrogatives"
        assert "nnat" in props["Baseline"]
        assert "Truncated" not in props  # short baseline

    def test_text_baseline_truncated(self):
        props = props_for(self._handle(baseline="w " * 400), "texts", "text-1")
        assert props["Truncated"] == "baseline excerpt truncated"
        assert props["Baseline"].endswith("…")

    def test_text_title_only_when_no_baseline(self):
        """Create-case / empty-baseline: show what exists, assert nothing absent."""
        text = FakeGuidObj("text-2")
        text_ops = FakeTextOps([text], {"text-2": "Empty Text"}, {"text-2": []})
        props = props_for(FakeTextHandle(text_ops), "texts", "text-2")
        assert props == {"Title": "Empty Text"}

    def test_text_missing_returns_none(self):
        text_ops = FakeTextOps([], {}, {})
        assert props_for(FakeTextHandle(text_ops), "texts", "nope") is None

    def test_text_read_failure_degrades_to_none_not_raise(self):
        class Exploding:
            @property
            def Texts(self):
                raise RuntimeError("boom")

        # props_for wraps the dedicated reader — never raises.
        assert props_for(Exploding(), "texts", "x") is None


# ===========================================================================
# US1 — Writing System reader (T007/T008)
# ===========================================================================


class TestWritingSystemReader:
    def _handle(self):
        en = FakeWs("en", "English")
        etu = FakeWs("etu", "Etung")
        etu_ipa = FakeWs("etu-fonipa", "Etung (IPA)")
        return FakeWsHandle(FakeWsOps([en, etu, etu_ipa], [etu, etu_ipa]))

    def test_ws_analysis_primary(self):
        props = props_for(self._handle(), "writing_systems_check", "en")
        assert props["Name"] == "English"
        assert props["Code"] == "en"
        assert props["Kind"] == "analysis"
        assert props["Rank"] == "primary"
        assert props["MapsTo"] == "unresolved"

    def test_ws_vernacular_primary(self):
        props = props_for(self._handle(), "writing_systems_check", "etu")
        assert props["Kind"] == "vernacular"
        assert props["Rank"] == "primary"

    def test_ws_sub_variant_rank(self):
        props = props_for(self._handle(), "writing_systems_check", "etu-fonipa")
        assert props["Kind"] == "vernacular"
        assert props["Rank"] == "sub"

    def test_ws_unknown_id_returns_none(self):
        assert props_for(self._handle(), "writing_systems_check", "zz") is None


# ===========================================================================
# US1 — Complex Form Type reader (T007) — finder monkeypatched
# ===========================================================================


class TestComplexFormTypeReader:
    def test_cft_name_abbrev_reverse(self, monkeypatch):
        node = FakeGuidObj(
            "cft-1",
            Name={"en": "Compound"},
            Abbreviation={"en": "cmp"},
            Description={"en": "A compound complex form."},
            ReverseName={"en": "component of"},
            ReverseAbbr={"en": "comp. of"},
        )
        monkeypatch.setattr(mp, "_find_complex_form_type_by_guid",
                            lambda handle, guid: node if guid == "cft-1" else None)
        props = props_for(object(), "complex_form_types", "cft-1")
        assert props["Name"] == {"en": "Compound"}
        assert props["Abbreviation"] == {"en": "cmp"}
        assert props["ReverseName"] == {"en": "component of"}
        assert props["ReverseAbbr"] == {"en": "comp. of"}

    def test_cft_missing_returns_none(self, monkeypatch):
        monkeypatch.setattr(mp, "_find_complex_form_type_by_guid",
                            lambda handle, guid: None)
        assert props_for(object(), "complex_form_types", "x") is None


# ===========================================================================
# US1 — Ad hoc / Compound rule reader (T007) — finder monkeypatched
# ===========================================================================


class TestAdhocReader:
    def test_adhoc_referenced_elements(self, monkeypatch):
        rule = FakeGuidObj(
            "rule-1",
            ClassName="MoMorphAdhocProhib",
            MorphemesRS=[FakeGuidObj("m1", LongName="Noun"),
                         FakeGuidObj("m2", LongName="Affix in np slot")],
        )
        monkeypatch.setattr(mp, "_find_adhoc_rule_by_guid",
                            lambda handle, guid: rule if guid == "rule-1" else None)
        props = props_for(object(), "adhoc_compound_rules", "rule-1")
        assert props["ReferencedElements"] == ["Noun", "Affix in np slot"]

    def test_adhoc_identity_fallback_never_blank(self, monkeypatch):
        """A rule with no name and no readable refs still yields its class type
        so the pane is never blank (FR-011)."""
        rule = FakeGuidObj("rule-2", ClassName="MoEndoCompound")
        monkeypatch.setattr(mp, "_find_adhoc_rule_by_guid",
                            lambda handle, guid: rule)
        props = props_for(object(), "adhoc_compound_rules", "rule-2")
        assert props == {"Type": "MoEndoCompound"}

    def test_adhoc_bounded_reference_list(self, monkeypatch):
        """The cap holds, and spec-036 FR-037: the note discloses the true total.

        Same reasoning as `test_affix_list_bounded`. A bare "truncated" says a
        cut happened and not how much is behind it, so the operator cannot tell
        26 referenced elements from 260 -- and cannot decide whether it matters.
        Both of this module's capped lists are held to the same disclosure.
        """
        total = 60
        rule = FakeGuidObj(
            "rule-3", ClassName="MoMorphAdhocProhib",
            MorphemesRS=[FakeGuidObj(f"m{i}", LongName=f"morph{i}")
                         for i in range(total)],
        )
        monkeypatch.setattr(mp, "_find_adhoc_rule_by_guid", lambda h, g: rule)
        props = props_for(object(), "adhoc_compound_rules", "rule-3")
        assert len(props["ReferencedElements"]) == mp._LIST_ITEM_LIMIT
        assert props["Truncated"] == (
            f"showing {mp._LIST_ITEM_LIMIT} of {total} referenced elements"
        )
        # The real total, not the cap echoed twice ("showing 25 of 25").
        assert str(total) in props["Truncated"]


# ===========================================================================
# US2 — thin-category enrichers (T016/T017)
# ===========================================================================


class TestPhonFeatureEnrich:
    def test_type_and_values(self):
        obj = FakeGuidObj(
            "pf-1",
            ValuesOC=[FakeGuidObj("v1", Abbreviation={"en": "+"}),
                      FakeGuidObj("v2", Abbreviation={"en": "-"})],
        )
        raw = {"Name": {"en": "back"}}
        _enrich_phon_feature(obj, raw)
        assert raw["Values"] == ["+", "-"]
        assert raw["Type"] == "closed"

    def test_no_values_leaves_label_level(self):
        obj = FakeGuidObj("pf-2", ValuesOC=[])
        raw = {"Name": {"en": "novalues"}}
        _enrich_phon_feature(obj, raw)
        assert "Values" not in raw
        assert raw == {"Name": {"en": "novalues"}}


class _FakeSeq(list):
    """List that also answers the LCM sequence protocol (.Count / .ToArray())."""
    @property
    def Count(self):
        return len(self)

    def ToArray(self):
        return list(self)


def _seg_ctx(symbol):
    """A fake PhSimpleContextSeg whose terminal unit's code renders `symbol`."""
    tu = FakeGuidObj("tu-" + symbol,
                     CodesOS=_FakeSeq([FakeGuidObj("code", Representation={"en": symbol})]))
    return FakeGuidObj("ctx-" + symbol,
                       ClassName="PhSimpleContextSeg", FeatureStructureRA=tu)


class TestPhonRuleEnrich:
    def test_renders_readable_rule_string(self):
        # k -> g (segment input, segment output), no environment.
        rhs = FakeGuidObj("rhs", ClassName="PhSegRuleRHS",
                          StrucChangeOS=[_seg_ctx("g")],
                          LeftContextOA=None, RightContextOA=None)
        obj = FakeGuidObj(
            "pr-1",
            StrucDescOS=[_seg_ctx("k")],
            RightHandSidesOS=[rhs],
            Direction=0, OrderNumber=3,
        )
        raw = {"Name": {"en": "palatalisation"}}
        _enrich_phon_rule(obj, raw)
        # The pane now shows the actual transformation, not just counts.
        assert raw["Rule"] == "k → g"
        # Metadata (direction/order) accompanies the readable rule.
        assert "direction=0" in raw["Structure"]
        assert "order=3" in raw["Structure"]

    def test_deletion_renders_empty_output(self):
        rhs = FakeGuidObj("rhs", ClassName="PhSegRuleRHS",
                          StrucChangeOS=[],  # deletion: no output
                          LeftContextOA=None, RightContextOA=None)
        obj = FakeGuidObj("pr-del", StrucDescOS=[_seg_ctx("a")],
                          RightHandSidesOS=[rhs], Direction=0, OrderNumber=1)
        raw = {}
        _enrich_phon_rule(obj, raw)
        assert raw["Rule"] == "a → ∅"  # a -> null

    def test_renders_alpha_variable_features(self):
        # Assimilation: output copies the 'back' feature as an α-variable from
        # the environment; the SAME constraint object gets the SAME letter.
        fc = FakeGuidObj("fc-back", FeatureRA=FakeGuidObj("f", Abbreviation={"en": "back"}))
        out_nc = FakeGuidObj("nc-out", ClassName="PhNCFeatures", FeaturesOA=None)
        out_ctx = FakeGuidObj("ctx-out", ClassName="PhSimpleContextNC",
                              FeatureStructureRA=out_nc, PlusConstrRS=[fc], MinusConstrRS=[])
        env_nc = FakeGuidObj("nc-env", ClassName="PhNCFeatures", FeaturesOA=None)
        env_ctx = FakeGuidObj("ctx-env", ClassName="PhSimpleContextNC",
                              FeatureStructureRA=env_nc, PlusConstrRS=[fc], MinusConstrRS=[])
        rhs = FakeGuidObj("rhs", StrucChangeOS=[out_ctx],
                          LeftContextOA=None, RightContextOA=env_ctx)
        obj = FakeGuidObj("pr-asm", StrucDescOS=[_seg_ctx("N")],
                          RightHandSidesOS=[rhs], Direction=0, OrderNumber=1)
        raw = {}
        _enrich_phon_rule(obj, raw)
        # Feature name appears WITH its variable, same letter in change + env.
        assert "αback" in raw["Rule"]
        assert raw["Rule"].count("αback") == 2  # matched agreement

    def test_two_rules_same_name_distinguishable(self):
        r1 = FakeGuidObj("a", StrucDescOS=[_seg_ctx("k")],
                         RightHandSidesOS=[FakeGuidObj("r", StrucChangeOS=[_seg_ctx("g")])],
                         Direction=0, OrderNumber=1)
        r2 = FakeGuidObj("b", StrucDescOS=[_seg_ctx("p")],
                         RightHandSidesOS=[FakeGuidObj("r", StrucChangeOS=[_seg_ctx("b")])],
                         Direction=0, OrderNumber=2)
        raw1, raw2 = {}, {}
        _enrich_phon_rule(r1, raw1)
        _enrich_phon_rule(r2, raw2)
        assert raw1["Rule"] != raw2["Rule"]  # FR-006: distinguishable by content


class TestSlotEnrich:
    def test_affixes_surface(self):
        obj = FakeGuidObj("slot-1",
                          Affixes=[FakeGuidObj("a1", LongName="Affix in (aug) slot")])
        raw = {"Name": {"en": "aug"}, "Optional": True}
        _enrich_slot(obj, raw)
        assert raw["Affixes"] == ["Affix in (aug) slot"]

    def test_affix_list_bounded(self):
        """The cap still holds, and spec-036 FR-037 requires the note to disclose
        BOTH the cap and the true total -- a bare "affix list truncated" tells the
        operator a cut happened but not how much is missing, so 26 affixes reads
        the same as 260.  Asserting the exact "showing N of M affixes" wording
        (with M computed from the fixture) fails a regression to the bare note."""
        total = 60
        obj = FakeGuidObj(
            "slot-2",
            Affixes=[FakeGuidObj(f"a{i}", LongName=f"affix{i}") for i in range(total)],
        )
        raw = {"Name": {"en": "big"}}
        _enrich_slot(obj, raw)
        assert len(raw["Affixes"]) == mp._LIST_ITEM_LIMIT
        assert raw["Truncated"] == f"showing {mp._LIST_ITEM_LIMIT} of {total} affixes"
        # Belt-and-braces: the disclosed total must be the REAL total, not the cap
        # echoed twice, so a note that says "showing 25 of 25" cannot pass.
        assert str(total) in raw["Truncated"]


# ===========================================================================
# US3 — Natural Class Members/Features delivery is load-bearing (T022, SC-003)
# ===========================================================================


class FakePhoneme:
    """Duck-typed phoneme: `_phoneme_label` reads Name (dict) first."""

    def __init__(self, grapheme):
        self.Name = {"en": grapheme}


class FakeSegmentNC:
    """Segment-based NC: `_natural_class_members` casts to IPhNCSegments (no-op
    headless) then reads SegmentsRC."""

    def __init__(self, graphemes):
        self.SegmentsRC = [FakePhoneme(g) for g in graphemes]


class TestNaturalClassRegressionGuard:
    def test_members_absent_before_and_present_after_enrich(self):
        """On identical fixture data: the resolved dict has NO Members until the
        delivery step (`_enrich_natural_class`) runs, and HAS them after. This
        pins the regression fix as load-bearing (SC-003, FR-008).

        NOTE (T023 live-pin): the segment-based Natural Class preview already
        delivers Members on `main` for the Ejagham Mini pair — the described
        regression does not reproduce on the covered path. This guard therefore
        pins the delivery contract so any future change that drops Members from
        render fails here.
        """
        nc = FakeSegmentNC(["bh", "ch", "r", "g", "l"])
        raw = {"Name": {"en": "Consonants"}, "Abbreviation": {"en": "C"}}
        # BEFORE the delivery step: members are resolvable but not in the dict.
        assert "Members" not in raw
        # AFTER: the enrich step delivers them onto the render dict.
        _enrich_natural_class(nc, raw)
        assert raw["Members"] == ["bh", "ch", "r", "g", "l"]

    def test_members_survive_prop_filter(self):
        """A non-empty Members list is not dropped by `_filter_props` (the
        candidate downstream drop point, R1)."""
        nc = FakeSegmentNC(["m", "n"])
        raw = {"Name": {"en": "Nasals"}}
        _enrich_natural_class(nc, raw)
        filtered = mp._filter_props(raw)
        assert filtered.get("Members") == ["m", "n"]


# ===========================================================================
# Content-aware phonology item-drop predicate (_phon_is_empty, DESIGN A)
#
# Principle: "Empty items should only be items with no syncable fields AND
# no child/linked objects." A name-only emptiness test wrongly dropped
# well-formed but unnamed phonemes/environments/natural classes/features that
# carry real content in other fields; conversely a truly-empty item (no name,
# no linked/child content) must still be dropped — this is the load-bearing
# dangling-BasicIPAInfo-catalog case (32 unreferenced empties, Ejagham Full
# GT-Test).
# ===========================================================================


def _analysis_name(text):
    """Fake `.Name` exposing only `.BestAnalysisAlternative.Text` (non-phoneme
    categories name themselves in the analysis WS; see `_phon_name_text`)."""
    return FakeGuidObj("name", BestAnalysisAlternative=FakeGuidObj("alt", Text=text))


def _vernacular_name(text):
    """Fake phoneme `.Name` exposing `.BestVernacularAlternative.Text` (the
    grapheme WS phonemes are read from first; see `_phon_name_text`)."""
    return FakeGuidObj("name", BestVernacularAlternative=FakeGuidObj("alt", Text=text))


class TestPhonIsEmptyContentAware:
    # --- phonemes ---------------------------------------------------------

    def test_phoneme_codes_only_retained(self):
        obj = FakeGuidObj("ph-1", CodesOS=[FakeGuidObj("code")])
        assert _phon_is_empty(obj, phoneme=True,
                               category=GrammarCategory.PHONEMES) is False

    def test_phoneme_features_only_retained(self):
        obj = FakeGuidObj("ph-2", FeaturesOA=FakeGuidObj("fs"))
        assert _phon_is_empty(obj, phoneme=True,
                               category=GrammarCategory.PHONEMES) is False

    def test_phoneme_truly_empty_dropped(self):
        """Dangling BasicIPAInfo catalog phoneme: no grapheme, IPA,
        description, codes, or features — the load-bearing regression guard.
        """
        obj = FakeGuidObj("ph-3")
        assert _phon_is_empty(obj, phoneme=True,
                               category=GrammarCategory.PHONEMES) is True

    def test_phoneme_named_retained(self):
        obj = FakeGuidObj("ph-4", Name=_vernacular_name("r"))
        assert _phon_is_empty(obj, phoneme=True,
                               category=GrammarCategory.PHONEMES) is False

    # --- environments -------------------------------------------------------

    def test_environment_strucrep_only_retained(self):
        obj = FakeGuidObj("env-1", StringRepresentation=FakeGuidObj("s", Text="/_[V]"))
        assert _phon_is_empty(obj, phoneme=False,
                               category=GrammarCategory.PH_ENVIRONMENT) is False

    def test_environment_nameless_no_strucrep_dropped(self):
        obj = FakeGuidObj("env-2")
        assert _phon_is_empty(obj, phoneme=False,
                               category=GrammarCategory.PH_ENVIRONMENT) is True

    def test_environment_named_retained(self):
        obj = FakeGuidObj("env-3", Name=_analysis_name("word-final"))
        assert _phon_is_empty(obj, phoneme=False,
                               category=GrammarCategory.PH_ENVIRONMENT) is False

    # --- natural classes ------------------------------------------------

    def test_natural_class_segments_only_retained(self):
        obj = FakeGuidObj("nc-1", SegmentsRC=[FakeGuidObj("s1")])
        assert _phon_is_empty(obj, phoneme=False,
                               category=GrammarCategory.NATURAL_CLASSES) is False

    def test_natural_class_features_only_retained(self):
        obj = FakeGuidObj("nc-2", FeaturesOA=FakeGuidObj("fs"))
        assert _phon_is_empty(obj, phoneme=False,
                               category=GrammarCategory.NATURAL_CLASSES) is False

    def test_natural_class_empty_dropped(self):
        obj = FakeGuidObj("nc-3")
        assert _phon_is_empty(obj, phoneme=False,
                               category=GrammarCategory.NATURAL_CLASSES) is True

    def test_natural_class_named_retained(self):
        obj = FakeGuidObj("nc-4", Name=_analysis_name("Vowels"))
        assert _phon_is_empty(obj, phoneme=False,
                               category=GrammarCategory.NATURAL_CLASSES) is False

    # --- phonological features -----------------------------------------

    def test_phon_feature_values_only_retained(self):
        obj = FakeGuidObj("pf-1", ValuesOC=[FakeGuidObj("v1")])
        assert _phon_is_empty(obj, phoneme=False,
                               category=GrammarCategory.PHONOLOGICAL_FEATURES) is False

    def test_phon_feature_empty_dropped(self):
        obj = FakeGuidObj("pf-2")
        assert _phon_is_empty(obj, phoneme=False,
                               category=GrammarCategory.PHONOLOGICAL_FEATURES) is True

    def test_phon_feature_named_retained(self):
        obj = FakeGuidObj("pf-3", Name=_analysis_name("back"))
        assert _phon_is_empty(obj, phoneme=False,
                               category=GrammarCategory.PHONOLOGICAL_FEATURES) is False

    def test_phoneme_description_only_retained(self):
        """Phoneme with only a Description ('refer to as') — no grapheme/IPA/
        codes/features — is still content, so retained."""
        obj = FakeGuidObj("ph-5", Description=FakeGuidObj(
            "d", BestAnalysisAlternative=FakeGuidObj("alt", Text="a mid vowel")))
        assert _phon_is_empty(obj, phoneme=True,
                               category=GrammarCategory.PHONEMES) is False

    # --- unknown / None category: legacy Name-only fallback --------------

    def test_unknown_category_named_retained(self):
        obj = FakeGuidObj("x-1", Name=_analysis_name("thing"))
        assert _phon_is_empty(obj, phoneme=False, category=None) is False

    def test_unknown_category_nameless_dropped(self):
        obj = FakeGuidObj("x-2")
        assert _phon_is_empty(obj, phoneme=False, category=None) is True

    # --- rules always retained -------------------------------------------

    def test_rule_always_retained_even_when_nameless(self):
        obj = FakeGuidObj("rule-1")
        assert _phon_is_empty(obj, phoneme=False,
                               category=GrammarCategory.PHONOLOGICAL_RULES) is False


class _CountSeq:
    """Sequence exposing `.Count` but NOT `len()` — mimics an LCM
    ref/owning collection (the branch a plain list never exercises)."""

    def __init__(self, n):
        self._n = n

    @property
    def Count(self):
        return self._n


class _IterOnly:
    """Iterable with neither `len()` nor `.Count` (generator-like)."""

    def __init__(self, items):
        self._items = list(items)

    def __iter__(self):
        return iter(self._items)


class TestNonemptySeq:
    """Direct coverage of `_nonempty_seq`'s three measurement branches."""

    def test_none_is_empty(self):
        assert _nonempty_seq(None) is False

    def test_len_branch(self):
        assert _nonempty_seq([]) is False
        assert _nonempty_seq(["a"]) is True

    def test_count_branch(self):
        assert _nonempty_seq(_CountSeq(0)) is False
        assert _nonempty_seq(_CountSeq(3)) is True

    def test_iterator_branch(self):
        assert _nonempty_seq(_IterOnly([])) is False
        assert _nonempty_seq(_IterOnly([1])) is True


class TestPhonStrucrepText:
    """Direct coverage of `_phon_strucrep_text`, incl. the sentinel fallback."""

    def test_direct_text(self):
        obj = FakeGuidObj("e", StringRepresentation=FakeGuidObj("s", Text="/_[V]"))
        assert _phon_strucrep_text(obj) == "/_[V]"

    def test_sentinel_text_falls_back_to_best_analysis(self):
        rep = FakeGuidObj("s", Text="***",
                          BestAnalysisAlternative=FakeGuidObj("alt", Text="/_#"))
        obj = FakeGuidObj("e", StringRepresentation=rep)
        assert _phon_strucrep_text(obj) == "/_#"

    def test_no_strucrep_is_empty(self):
        assert _phon_strucrep_text(FakeGuidObj("e")) == ""

    def test_sentinel_and_no_fallback_is_empty(self):
        rep = FakeGuidObj("s", Text="***")
        obj = FakeGuidObj("e", StringRepresentation=rep)
        assert _phon_strucrep_text(obj) == ""
