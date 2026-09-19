"""Feature 038 T081 (6th re-gate): `PhPhoneme.FeaturesOA` never reached the
phonemes this run MATCHED to the destination's starter inventory.

THE MEASUREMENT, from the committed `census-038-t134-*` artifacts'
`t119_per_owning_field` tables. `PhPhoneme.Features` reads:

    ejagham  41 -> 20        ngoreme  41 -> 21        mbugwe  46 -> 27

and each destination figure is exactly the number of phonemes that pair
CREATED (41-21, 41-20, 46-19). The loss is the matched half and nothing else.
It is the WHOLE of ejagham's `FsFeatStruc` -21, and part of ngoreme's -90 and
mbugwe's -415 beside the T045 `ReferenceForms` shells and `FsComplexValue`.

THE MECHANISM WAS ALREADY WRITTEN DOWN, ONE FIELD OVER. `phonemes_execute_
action` calls `ApplySyncableProperties` -- which carries `Features` -- on the
CREATE path only, and T121's `_wire_phoneme_codes` docstring states the
consequence in as many words: "a matched phoneme never reaches this function
at all (it plans as a natural-key PlannedOverwrite). A create-path-only fix
would leave the enrichment half standing." T121 fixed `CodesOS` that way and
left `FeaturesOA` behind. PHONEMES is MULTI_INSTANCE, not GOLD_RESERVED
(`_GOLD_RESERVED_PHONOLOGY_CATEGORIES` holds PHONOLOGICAL_FEATURES alone), so
there is no edit-copy route either.

WHY IT IS A DEFECT AND NOT COSMETIC METADATA. A phoneme with a correct name
and a null `FeaturesOA` cannot satisfy any feature-based natural-class
membership test, silently disabling phonological-rule matching for exactly
those phonemes -- the failure mode feature 037 exists to prevent for
`IPhNCFeatures`, arriving one level down.

ADD-ONLY BY CONSTRUCTION. The props dict is NARROWED to `Features` before it
is handed over, so the pass cannot reach a matched starter phoneme's `Name`,
`Description` or `BasicIPASymbol` even if `fill_gaps` were ignored. That is
asserted here on the CALL, not just on the outcome, because an outcome test
passes just as well against a props dict that happens to be harmless on the
fixture and is not harmless on a real starter project.

Host-free: duck fakes only.
"""
from __future__ import annotations

import inspect
import types

from gramtrans.Lib import categories
from gramtrans.Lib.models import GrammarCategory


class _SrcPhoneme:
    def __init__(self, guid):
        self.guid = guid


class _TgtPhoneme:
    def __init__(self, guid, features=None):
        self.guid = guid
        self.FeaturesOA = features


class _WS:
    def __init__(self, handle, ws_id):
        self.Handle = handle
        self.Id = ws_id


class _PhonemeOps:
    """Duck `project.Phonemes`, recording every sync call verbatim so the
    NARROWING and `fill_gaps` claims are checkable on the call itself."""

    def __init__(self, phonemes=(), props=None, get_raises=None,
                 apply_raises=None):
        self._phonemes = list(phonemes)
        self._props = props or {}
        self._get_raises = get_raises
        self._apply_raises = apply_raises
        self.applied = []          # [(target, props, ws_map, fill_gaps)]

    def GetAll(self):  # noqa: N802 -- mirrors the flexicon API
        return list(self._phonemes)

    def GetSyncableProperties(self, item):  # noqa: N802
        if self._get_raises is not None:
            raise self._get_raises
        return self._props.get(getattr(item, "guid", None), {})

    def ApplySyncableProperties(self, item, props, ws_map=None,  # noqa: N802
                                fill_gaps=False):
        if self._apply_raises is not None:
            raise self._apply_raises
        self.applied.append((item, props, ws_map, fill_gaps))
        if props.get("Features") and getattr(item, "FeaturesOA", None) is None:
            item.FeaturesOA = object()      # flexicon creates it when missing


class _Handle:
    def __init__(self, ops, registry=None, ws=(("1", "en"),)):
        self.Phonemes = ops
        self.WritingSystems = types.SimpleNamespace(
            GetAll=lambda: [_WS(int(h), i) for h, i in ws])
        self._registry = registry or {}

    def get_object_by_guid(self, guid):
        return self._registry.get(guid)


def _context(source, target, plan=None):
    return types.SimpleNamespace(source_handle=source, target_handle=target,
                                 _run_plan=plan)


def _plan(overwrites=(), remap=None):
    return types.SimpleNamespace(
        overwrites=tuple(overwrites), identity_remap=remap or {},
        ws_mapping=None, actions=())


class _Overwrite:
    def __init__(self, source_guid, target_guid,
                 category=GrammarCategory.PHONEMES):
        self.category = category
        self.source_guid = source_guid
        self.target_guid = target_guid


_SPECS = [{"FeatureGuid": "f1", "ValueGuid": "v1"},
          {"FeatureGuid": "f2", "ValueGuid": "v2"}]


# --------------------------------------------------------------------------
# The enrichment half -- the measured defect
# --------------------------------------------------------------------------

def test_features_reach_a_starter_matched_phoneme():
    """THE ROW THAT MOVES. A phoneme matched to a starter carries the
    STARTER's GUID, so a source-GUID lookup cannot find it -- only the run's
    PlannedOverwrite can. Its FeaturesOA is null before the pass."""
    src_ops = _PhonemeOps([_SrcPhoneme("src-a")],
                          props={"src-a": {"Name": {"en": "a"},
                                           "Features": _SPECS}})
    src = _Handle(src_ops)
    starter = _TgtPhoneme("starter-a", features=None)
    tgt_ops = _PhonemeOps()
    tgt = _Handle(tgt_ops, registry={"starter-a": starter})
    ctx = _context(src, tgt, _plan(overwrites=[_Overwrite("src-a",
                                                          "starter-a")]))

    skips = categories._wire_phoneme_features(ctx, tgt, None)

    assert skips == []
    assert len(tgt_ops.applied) == 1
    applied_to, props, _ws, fill_gaps = tgt_ops.applied[0]
    assert applied_to is starter
    assert props["Features"] == _SPECS
    assert fill_gaps is True
    assert starter.FeaturesOA is not None


def test_the_props_dict_is_narrowed_to_features_only():
    """ADD-ONLY BY CONSTRUCTION, asserted on the CALL. A matched starter
    phoneme already has a correct Name; handing the whole props dict over
    would put that Name in reach of the sync path, and `fill_gaps` would be
    the only thing standing between this pass and overwriting destination
    data. The narrowing means it cannot happen even if the flag is ignored."""
    src_ops = _PhonemeOps(
        [_SrcPhoneme("src-a")],
        props={"src-a": {"Name": {"en": "source name"},
                         "Description": {"en": "source description"},
                         "BasicIPASymbol": {"en": "a"},
                         "FeaturesGuid": "struct-guid",
                         "Features": _SPECS}})
    src = _Handle(src_ops)
    starter = _TgtPhoneme("starter-a")
    tgt_ops = _PhonemeOps()
    tgt = _Handle(tgt_ops, registry={"starter-a": starter})
    ctx = _context(src, tgt, _plan(overwrites=[_Overwrite("src-a",
                                                          "starter-a")]))

    categories._wire_phoneme_features(ctx, tgt, None)

    _to, props, _ws, _fg = tgt_ops.applied[0]
    assert set(props) == {"Features"}, (
        "props must be narrowed to Features alone; got " + repr(sorted(props)))


# --------------------------------------------------------------------------
# The create half -- already correct, and must stay a no-op claim
# --------------------------------------------------------------------------

def test_a_created_phoneme_is_reapplied_but_not_counted_as_filled(caplog):
    """The pass walks EVERY source phoneme rather than only the matched set,
    because flexicon's `_ApplyFeatureStruc` matches specs by
    `(FeatureGuid, ValueGuid)` and is idempotent -- one code path beats two
    populations kept in step. The LOG must still not claim it repaired one."""
    src_ops = _PhonemeOps([_SrcPhoneme("p1")],
                          props={"p1": {"Features": _SPECS}})
    src = _Handle(src_ops)
    created = _TgtPhoneme("p1", features=object())      # already carries one
    tgt_ops = _PhonemeOps()
    tgt = _Handle(tgt_ops, registry={"p1": created})

    with caplog.at_level("INFO", logger="gramtrans.Lib.categories"):
        categories._wire_phoneme_features(_context(src, tgt), tgt, None)

    assert len(tgt_ops.applied) == 1                    # idempotent re-apply
    text = caplog.text
    assert "filled FeaturesOA on 0" in text
    assert "1 already carried one" in text


def test_identity_remap_is_honoured():
    src_ops = _PhonemeOps([_SrcPhoneme("p1")],
                          props={"p1": {"Features": _SPECS}})
    src = _Handle(src_ops)
    minted = _TgtPhoneme("minted")
    tgt_ops = _PhonemeOps()
    tgt = _Handle(tgt_ops, registry={"minted": minted})
    ctx = _context(src, tgt, _plan(remap={"p1": "minted"}))

    categories._wire_phoneme_features(ctx, tgt, None)

    assert tgt_ops.applied and tgt_ops.applied[0][0] is minted


# --------------------------------------------------------------------------
# What is NOT a loss, and what degrades rather than aborting
# --------------------------------------------------------------------------

def test_a_source_phoneme_with_no_feature_structure_is_not_a_loss():
    src_ops = _PhonemeOps([_SrcPhoneme("p1")], props={"p1": {"Name": {}}})
    src = _Handle(src_ops)
    tgt_ops = _PhonemeOps()
    tgt = _Handle(tgt_ops, registry={"p1": _TgtPhoneme("p1")})

    skips = categories._wire_phoneme_features(_context(src, tgt), tgt, None)

    assert skips == []
    assert tgt_ops.applied == []


def test_a_source_phoneme_with_no_destination_counterpart_is_skipped():
    """T074's scoping, as in T121: a phoneme this run never transferred is not
    a lost feature structure."""
    src_ops = _PhonemeOps([_SrcPhoneme("ghost")],
                          props={"ghost": {"Features": _SPECS}})
    src = _Handle(src_ops)
    tgt_ops = _PhonemeOps()
    tgt = _Handle(tgt_ops, registry={})

    skips = categories._wire_phoneme_features(_context(src, tgt), tgt, None)

    assert skips == []
    assert tgt_ops.applied == []


def test_unreadable_source_properties_degrade_to_a_skip_not_an_abort():
    """Mirrors the create path's Ruling Y guard. The SECOND phoneme must still
    be processed -- a per-phoneme failure may not cost the inventory."""
    src_ops = _PhonemeOps([_SrcPhoneme("bad"), _SrcPhoneme("good")],
                          props={"good": {"Features": _SPECS}})

    def _get(item):
        if getattr(item, "guid", None) == "bad":
            raise RuntimeError("ITsString.get_String")
        return {"Features": _SPECS}

    src_ops.GetSyncableProperties = _get
    src = _Handle(src_ops)
    good = _TgtPhoneme("good")
    tgt_ops = _PhonemeOps()
    tgt = _Handle(tgt_ops, registry={"bad": _TgtPhoneme("bad"), "good": good})

    skips = categories._wire_phoneme_features(_context(src, tgt), tgt, None)

    assert len(skips) == 1
    assert skips[0].source_guid == "bad"
    assert skips[0].category is GrammarCategory.PHONEMES
    assert len(tgt_ops.applied) == 1 and tgt_ops.applied[0][0] is good


def test_an_apply_failure_degrades_to_a_skip():
    src_ops = _PhonemeOps([_SrcPhoneme("p1")],
                          props={"p1": {"Features": _SPECS}})
    src = _Handle(src_ops)
    tgt_ops = _PhonemeOps(apply_raises=RuntimeError("feature system absent"))
    tgt = _Handle(tgt_ops, registry={"p1": _TgtPhoneme("p1")})

    skips = categories._wire_phoneme_features(_context(src, tgt), tgt, None)

    assert len(skips) == 1 and skips[0].source_guid == "p1"
    assert "FeaturesOA could not be applied" in skips[0].detail


def test_no_source_phonemes_is_a_clean_no_op():
    src = _Handle(_PhonemeOps([]))
    tgt = _Handle(_PhonemeOps())
    assert categories._wire_phoneme_features(_context(src, tgt), tgt, None) == []


# --------------------------------------------------------------------------
# Wiring -- the pass is worthless if nothing calls it
# --------------------------------------------------------------------------

def test_the_tail_pass_is_registered_under_its_own_flag():
    """Registered beside T121's codes pass, on the SAME `_run_tail_once`
    anchor (the last PHONEMES action) but under its OWN idempotency flag --
    sharing `_did_phoneme_codes` would make whichever ran second a silent
    no-op."""
    body = inspect.getsource(categories.phonemes_execute_action)
    assert "_wire_phoneme_features" in body
    assert '"_did_phoneme_features"' in body
    assert '"_did_phoneme_codes"' in body


def test_the_pass_walks_phonemes_not_a_feature_structure_repository():
    """Same by-construction guarantee T121 relies on: reading
    `source.Phonemes.GetAll()` makes a `PhNCFeatures` or `CmAnnotation`
    feature structure -- the other owners in the same `FsFeatStruc` class row
    -- unreachable from here. An `IFsFeatStrucRepository` loop would pass every
    behavioural test above and still be one edit away from touching them."""
    body = inspect.getsource(categories._wire_phoneme_features)
    assert "source.Phonemes.GetAll()" in body
    assert "IFsFeatStrucRepository" not in body
    code = body.split('"""')[2]
    assert "PhNCFeatures" not in code      # not in the CODE
    assert "IPhNCFeatures" in body         # but IS discussed in the docstring
