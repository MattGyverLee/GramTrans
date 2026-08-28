"""Feature 038 T119: the `Fs*` cascade -- one class, nine owners.

WHAT WAS WRONG, AND WHY COUNTING COULD NOT SEE IT.

T114's live owner-attribution probe (`probes/owner-probe-*.json`, three
sanctioned pairs) took the census's `FsFeatStruc` / `FsClosedValue` residue
apart and found it was not two losses but one, with nine owning fields:

    owner (flid)                            ejagham   ngoreme   mbugwe
    MoStemMsa.MsFeatures (5001001)          117 -> 0  782 -> 0  104 -> 0
    FsComplexValue.Value (53001)               --     825 -> 0     --
    MoInflAffMsa.InflFeats (5038001)         86 -> 86  38 -> 18  78 -> 78
    MoDerivAffMsa.FromMsFeatures (5031001)     --        --      17 -> 0
    MoDerivAffMsa.ToMsFeatures (5031002)       --        --      17 -> 0
    MoAffixAllomorph.MsEnvFeatures (5027001)   --        --       1 -> 0

`MoStemMsa` is itself count-MATCHED (153/153, 139/139) while every destination
reports `MsFeaturesOA` as `{(none): 153}` / `{(none): 1953}` / `{(none): 139}`.
The MSAs arrive; they arrive HOLLOW. That is invisible to a gate that counts
MSAs, which is why these tests assert on CONTENT and per OWNING FIELD, never on
a class total.

The cause is in the code rather than in the data: `_create_msa_for_closure`'s
`MoStemMsa` branch writes exactly `{GUID, PartOfSpeechRA, StratumRA}`, and
before T119 the string `MsFeaturesOA` never appeared on the left of an
assignment anywhere in `Lib/`.

THE SECOND FINDING, WHICH IS THE ANSWER TO T119'S OPEN QUESTION.

The task asks why `MoInflAffMsa.InflFeats` is 86/86 and 78/78 but 38 -> 18 on
Ngoreme. It is not the owner: it is `_wire_msa_infl_feats` deferring a
structure WHOLE when any spec is not an `IFsClosedValue`. Ngoreme is the only
sanctioned project that holds `FsComplexValue` at all -- 825 of them, against
zero on the other two (`owner-probe-*.json`), corroborated by a different
instrument in `tests/integration/_snapshots/two-mode-038-ngoreme.json`, which
records `FsComplexValue` source 825 / arrived 0 / missing 825 beside
`FsComplexFeature` arrived 2 of 2. The complex DEFINITIONS transferred and the
complex VALUES did not, so every structure containing one deferred whole and
took its closed siblings down with it.

Host-free: duck-typed fakes only, in the fixture style of
`test_033_affix_msa_guid_inflfeats.py`, whose `_FakeTarget` (no `Cache`, so
`_lcm_factory` returns None) exercises the duck creation path.
"""
from __future__ import annotations

import types

import pytest

from gramtrans.Lib import categories, preview
from gramtrans.Lib.models import SkipReason


# --------------------------------------------------------------------------
# Fakes
# --------------------------------------------------------------------------

class _Obj:
    def __init__(self, guid):
        self.guid = guid


class _Closed:
    """Source IFsClosedValue: has ValueRA, no ValueOA."""

    def __init__(self, guid, feature, value):
        self.guid = guid
        self.FeatureRA = _Obj(feature) if feature else None
        self.ValueRA = _Obj(value) if value else None


class _Complex:
    """Source IFsComplexValue: has ValueOA (a nested structure), no ValueRA."""

    def __init__(self, guid, feature, nested):
        self.guid = guid
        self.FeatureRA = _Obj(feature) if feature else None
        self.ValueOA = nested


class _Struc:
    def __init__(self, guid, specs, type_guid=None):
        self.guid = guid
        self.FeatureSpecsOC = list(specs)
        self.TypeRA = _Obj(type_guid) if type_guid else None


class _SrcMSA:
    """A source MSA. Which attribute is set decides which owner it stands for
    -- exactly as the live cast does, where `MsFeaturesOA` exists on
    `IMoStemMsa` and not on `IMoInflAffMsa`."""

    def __init__(self, guid, **strucs):
        self.guid = guid
        for attr in ("InflFeatsOA", "MsFeaturesOA",
                     "FromMsFeaturesOA", "ToMsFeaturesOA"):
            setattr(self, attr, strucs.get(attr))


class _SrcAllomorph:
    def __init__(self, guid, struc=None):
        self.guid = guid
        self.MsEnvFeaturesOA = struc


class _SrcEntry:
    def __init__(self, msas=(), alternates=(), lexeme=None):
        self.MorphoSyntaxAnalysesOC = list(msas)
        self.AlternateFormsOS = list(alternates)
        self.LexemeFormOA = lexeme


class _SrcHandle:
    def __init__(self, entries):
        self.LangProject = types.SimpleNamespace(
            LexDbOA=types.SimpleNamespace(Entries=list(entries)))


class _TgtOwner:
    """A target owner with every feature-structure slot empty."""

    def __init__(self, guid):
        self.guid = guid
        for attr in ("InflFeatsOA", "MsFeaturesOA", "FromMsFeaturesOA",
                     "ToMsFeaturesOA", "MsEnvFeaturesOA"):
            setattr(self, attr, None)


class _FakeTarget:
    def __init__(self, registry):
        self._registry = registry

    def get_object_by_guid(self, guid):
        return self._registry.get(guid)


def _plan(bindings, remap=None, owner_entries=None):
    return types.SimpleNamespace(
        msa_feat_struc_bindings=bindings,
        msa_infl_feat_bindings={},
        msa_slot_bindings={},
        identity_remap=remap or {},
        # T074's owner->entry map. Empty by default, which is the
        # "cannot be scoped" case: an unresolved owner stays silent because
        # there is no evidence either way.
        msa_owner_entry=owner_entries or {},
    )


def _read(struc):
    """`{(feature_guid, value_guid_or_nested_marker)}` off a duck structure."""
    if struc is None:
        return set()
    out = set()
    for spec in struc.FeatureSpecsOC:
        feat = spec.FeatureRA.guid if spec.FeatureRA else None
        nested = getattr(spec, "ValueOA", None)
        if nested is not None:
            out.add((feat, f"complex:{nested.guid}"))
        else:
            val = getattr(spec, "ValueRA", None)
            out.add((feat, val.guid if val else None))
    return out


# --------------------------------------------------------------------------
# Producer -- reading the owners feature 033 never read
# --------------------------------------------------------------------------

def test_producer_reads_stem_msa_ms_features():
    """`MoStemMsa.MsFeatures` is 1,003 objects and zero of them arrive today.
    The producer must see it at all before anything can write it."""
    struc = _Struc("s1", [_Closed("cv1", "feat1", "val1")], type_guid="ty1")
    src = _SrcHandle([_SrcEntry(msas=[_SrcMSA("msa1", MsFeaturesOA=struc)])])

    bindings: dict = {}
    preview._populate_msa_feat_struc_bindings(src, bindings)

    key = preview.feat_struc_binding_key("msa1", "MsFeaturesOA")
    assert key in bindings
    assert bindings[key]["struc_guid"] == "s1"
    assert bindings[key]["type_guid"] == "ty1"
    assert bindings[key]["attr"] == "MsFeaturesOA"
    assert bindings[key]["owner_guid"] == "msa1"
    assert bindings[key]["specs"] == [
        {"spec_guid": "cv1", "kind": "closed",
         "feature": "feat1", "value": "val1"}]


def test_producer_keys_both_derivational_structures_separately():
    """`IMoDerivAffMsa` carries TWO structures (17 and 17 on Mbugwe). Keying by
    owner GUID alone would carry one and report success -- a silent
    half-transfer. This is the test that pins the key shape."""
    src = _SrcHandle([_SrcEntry(msas=[_SrcMSA(
        "msa1",
        FromMsFeaturesOA=_Struc("sf", [_Closed("a", "f1", "v1")]),
        ToMsFeaturesOA=_Struc("st", [_Closed("b", "f2", "v2")]),
    )])])

    bindings: dict = {}
    preview._populate_msa_feat_struc_bindings(src, bindings)

    from_key = preview.feat_struc_binding_key("msa1", "FromMsFeaturesOA")
    to_key = preview.feat_struc_binding_key("msa1", "ToMsFeaturesOA")
    assert from_key in bindings and to_key in bindings
    assert bindings[from_key]["struc_guid"] == "sf"
    assert bindings[to_key]["struc_guid"] == "st"


def test_producer_reads_allomorph_ms_env_features():
    """`MoAffixAllomorph.MsEnvFeatures` hangs off the entry's FORMS, not its
    MSAs, so it needs its own walk. Both alternates and the lexeme form."""
    src = _SrcHandle([_SrcEntry(
        alternates=[_SrcAllomorph("al1", _Struc("s1", [_Closed("c", "f", "v")]))],
        lexeme=_SrcAllomorph("lf1", _Struc("s2", [_Closed("d", "f", "v")])),
    )])

    bindings: dict = {}
    preview._populate_msa_feat_struc_bindings(src, bindings)

    assert preview.feat_struc_binding_key("al1", "MsEnvFeaturesOA") in bindings
    assert preview.feat_struc_binding_key("lf1", "MsEnvFeaturesOA") in bindings


def test_producer_does_not_claim_infl_feats():
    """`MoInflAffMsa.InflFeats` keeps its own producer -- it is the one owner
    measured working (86/86, 78/78), and T119's instruction is to copy that
    path, not to absorb it. A regression here must not be able to take it
    down."""
    src = _SrcHandle([_SrcEntry(msas=[_SrcMSA(
        "msa1", InflFeatsOA=_Struc("s1", [_Closed("cv", "f", "v")]))])])

    bindings: dict = {}
    preview._populate_msa_feat_struc_bindings(src, bindings)

    assert bindings == {}
    assert "InflFeatsOA" not in preview._MSA_EXTRA_FEAT_STRUC_ATTRS


def test_producer_skips_an_empty_structure():
    """A structure with no specs is not a loss and must not become a binding
    that reports one."""
    src = _SrcHandle([_SrcEntry(msas=[_SrcMSA(
        "msa1", MsFeaturesOA=_Struc("s1", []))])])

    bindings: dict = {}
    preview._populate_msa_feat_struc_bindings(src, bindings)
    assert bindings == {}


# --------------------------------------------------------------------------
# Producer -- the complex-value reading (T119's open question)
# --------------------------------------------------------------------------

def test_producer_follows_a_complex_value_into_its_nested_structure():
    """`FsComplexValue.Value` is 825 objects on Ngoreme, `arrived: 0`. Feature
    033's reader could only record a complex spec as an empty `"value"`, which
    the consumer then treated as unresolvable."""
    nested = _Struc("nested1", [_Closed("ncv", "nfeat", "nval")])
    struc = _Struc("s1", [_Complex("cx1", "cfeat", nested)])
    src = _SrcHandle([_SrcEntry(msas=[_SrcMSA("msa1", MsFeaturesOA=struc)])])

    bindings: dict = {}
    preview._populate_msa_feat_struc_bindings(src, bindings)

    row = bindings[preview.feat_struc_binding_key("msa1", "MsFeaturesOA")]
    assert len(row["specs"]) == 1
    spec = row["specs"][0]
    assert spec["kind"] == "complex"
    assert spec["feature"] == "cfeat"
    assert spec["nested"]["struc_guid"] == "nested1"
    assert spec["nested"]["specs"] == [
        {"spec_guid": "ncv", "kind": "closed",
         "feature": "nfeat", "value": "nval"}]


def test_infl_feats_producer_now_reads_complex_values_too():
    """The SAME fix reaches the working owner, which is the whole explanation
    for Ngoreme's 38 -> 18: that pair is the only one holding complex values."""
    nested = _Struc("n1", [_Closed("ncv", "nf", "nv")])
    src = _SrcHandle([_SrcEntry(msas=[_SrcMSA("msa1", InflFeatsOA=_Struc(
        "s1", [_Closed("cv", "f", "v"), _Complex("cx", "cf", nested)]))])])

    bindings: dict = {}
    preview._populate_msa_infl_feat_bindings(src, bindings)

    kinds = [s.get("kind") for s in bindings["msa1"]["specs"]]
    assert kinds == ["closed", "complex"]


def test_reader_caps_the_nesting_recursion():
    """LCM does not structurally forbid a cycle. Under-reporting beats
    hanging, and the cap must match the dependency side's."""
    assert preview._FEAT_STRUC_MAX_DEPTH == categories._FEAT_STRUC_MAX_DEPTH

    deepest = _Struc("leaf", [_Closed("lcv", "f", "v")])
    for i in range(preview._FEAT_STRUC_MAX_DEPTH + 3):
        deepest = _Struc(f"lvl{i}", [_Complex(f"cx{i}", "cf", deepest)])
    src = _SrcHandle([_SrcEntry(msas=[_SrcMSA("msa1", MsFeaturesOA=deepest)])])

    bindings: dict = {}
    preview._populate_msa_feat_struc_bindings(src, bindings)  # must terminate

    depth = 0
    node = bindings[preview.feat_struc_binding_key("msa1", "MsFeaturesOA")]
    while node["specs"] and node["specs"][0].get("kind") == "complex":
        node = node["specs"][0]["nested"]
        depth += 1
    assert depth <= preview._FEAT_STRUC_MAX_DEPTH + 1


# --------------------------------------------------------------------------
# Consumer -- writing them
# --------------------------------------------------------------------------

def _wire(bindings, registry, remap=None, owner_entries=None):
    target = _FakeTarget(registry)
    return categories._wire_owner_feat_strucs(
        None, target, _plan(bindings, remap, owner_entries)), target


def test_wire_fills_a_hollow_stem_msa():
    """The headline: a MATCHED `MoStemMsa` that arrived with no feature
    structure gets one. Asserted on CONTENT, because the count was already
    right when the object was hollow."""
    src = _SrcHandle([_SrcEntry(msas=[_SrcMSA("msa1", MsFeaturesOA=_Struc(
        "s1", [_Closed("cv1", "feat1", "val1")], type_guid="ty1"))])])
    bindings: dict = {}
    preview._populate_msa_feat_struc_bindings(src, bindings)

    tgt = _TgtOwner("msa1")
    assert tgt.MsFeaturesOA is None            # hollow, exactly as measured

    skips, _ = _wire(bindings, {"msa1": tgt, "feat1": _Obj("feat1"),
                                "val1": _Obj("val1"), "ty1": _Obj("ty1")})

    assert skips == []
    assert tgt.MsFeaturesOA is not None
    assert tgt.MsFeaturesOA.guid == "s1"       # GUID-preserved
    assert _read(tgt.MsFeaturesOA) == {("feat1", "val1")}
    # and it did NOT land on a neighbouring slot
    assert tgt.InflFeatsOA is None and tgt.ToMsFeaturesOA is None


def test_wire_writes_both_derivational_slots():
    src = _SrcHandle([_SrcEntry(msas=[_SrcMSA(
        "msa1",
        FromMsFeaturesOA=_Struc("sf", [_Closed("a", "f1", "v1")]),
        ToMsFeaturesOA=_Struc("st", [_Closed("b", "f2", "v2")]),
    )])])
    bindings: dict = {}
    preview._populate_msa_feat_struc_bindings(src, bindings)

    tgt = _TgtOwner("msa1")
    skips, _ = _wire(bindings, {
        "msa1": tgt, "f1": _Obj("f1"), "v1": _Obj("v1"),
        "f2": _Obj("f2"), "v2": _Obj("v2")})

    assert skips == []
    assert _read(tgt.FromMsFeaturesOA) == {("f1", "v1")}
    assert _read(tgt.ToMsFeaturesOA) == {("f2", "v2")}
    assert tgt.FromMsFeaturesOA.guid == "sf"
    assert tgt.ToMsFeaturesOA.guid == "st"


def test_wire_creates_the_nested_complex_structure():
    """`FsClosedValue` gets no code of its own -- it is 100%
    `FsFeatStruc.FeatureSpecs`, so it rides the cascade. This asserts the
    cascade actually cascades."""
    nested = _Struc("n1", [_Closed("ncv", "nf", "nv")])
    src = _SrcHandle([_SrcEntry(msas=[_SrcMSA("msa1", MsFeaturesOA=_Struc(
        "s1", [_Complex("cx1", "cf", nested)]))])])
    bindings: dict = {}
    preview._populate_msa_feat_struc_bindings(src, bindings)

    tgt = _TgtOwner("msa1")
    skips, _ = _wire(bindings, {"msa1": tgt, "cf": _Obj("cf"),
                                "nf": _Obj("nf"), "nv": _Obj("nv")})

    assert skips == []
    outer = tgt.MsFeaturesOA
    assert outer.guid == "s1"
    assert len(outer.FeatureSpecsOC) == 1
    complex_spec = outer.FeatureSpecsOC[0]
    assert complex_spec.guid == "cx1"                 # GUID-preserved
    assert complex_spec.ValueOA is not None
    assert complex_spec.ValueOA.guid == "n1"          # nested, GUID-preserved
    assert _read(complex_spec.ValueOA) == {("nf", "nv")}


def test_wire_is_idempotent():
    src = _SrcHandle([_SrcEntry(msas=[_SrcMSA("msa1", MsFeaturesOA=_Struc(
        "s1", [_Closed("cv1", "feat1", "val1")]))])])
    bindings: dict = {}
    preview._populate_msa_feat_struc_bindings(src, bindings)
    registry = {"msa1": _TgtOwner("msa1"), "feat1": _Obj("feat1"),
                "val1": _Obj("val1")}

    categories._wire_owner_feat_strucs(None, _FakeTarget(registry),
                                       _plan(bindings))
    first = len(registry["msa1"].MsFeaturesOA.FeatureSpecsOC)
    categories._wire_owner_feat_strucs(None, _FakeTarget(registry),
                                       _plan(bindings))
    assert len(registry["msa1"].MsFeaturesOA.FeatureSpecsOC) == first == 1


def test_wire_defers_the_whole_structure_when_an_endpoint_is_missing():
    """Feature 033's all-or-nothing rule, kept. A partially resolvable
    structure must not land half-written; a later run completes it."""
    src = _SrcHandle([_SrcEntry(msas=[_SrcMSA("msa1", MsFeaturesOA=_Struc(
        "s1", [_Closed("cv1", "feat1", "val1"),
               _Closed("cv2", "feat2", "MISSING")]))])])
    bindings: dict = {}
    preview._populate_msa_feat_struc_bindings(src, bindings)

    tgt = _TgtOwner("msa1")
    skips, _ = _wire(bindings, {"msa1": tgt, "feat1": _Obj("feat1"),
                                "val1": _Obj("val1"), "feat2": _Obj("feat2")})

    assert tgt.MsFeaturesOA is None            # nothing written at all
    assert len(skips) == 1
    assert skips[0].reason is SkipReason.DEPENDENCY_UNRESOLVED
    assert "MISSING" in skips[0].detail


def test_wire_defers_when_a_nested_endpoint_is_missing():
    """The deferral has to survive the recursion, or a complex value becomes a
    way to land a half-written structure."""
    nested = _Struc("n1", [_Closed("ncv", "nf", "MISSING")])
    src = _SrcHandle([_SrcEntry(msas=[_SrcMSA("msa1", MsFeaturesOA=_Struc(
        "s1", [_Complex("cx1", "cf", nested)]))])])
    bindings: dict = {}
    preview._populate_msa_feat_struc_bindings(src, bindings)

    tgt = _TgtOwner("msa1")
    skips, _ = _wire(bindings, {"msa1": tgt, "cf": _Obj("cf"),
                                "nf": _Obj("nf")})

    assert tgt.MsFeaturesOA is None
    assert len(skips) == 1
    assert skips[0].reason is SkipReason.DEPENDENCY_UNRESOLVED


def test_wire_skips_an_owner_absent_from_the_destination_silently():
    """T074's scoping. This producer walks the WHOLE source lexicon regardless
    of the selection, so an owner not in the destination is an entry this run
    never selected -- not a loss. Reporting it produced 203 phantom failures
    and 0 real ones when the inflectional pass got this wrong."""
    src = _SrcHandle([_SrcEntry(msas=[_SrcMSA("msa1", MsFeaturesOA=_Struc(
        "s1", [_Closed("cv1", "feat1", "val1")]))])])
    bindings: dict = {}
    preview._populate_msa_feat_struc_bindings(src, bindings)

    skips, _ = _wire(bindings, {"feat1": _Obj("feat1"), "val1": _Obj("val1")})
    assert skips == []


def test_wire_reports_an_absent_owner_whose_ENTRY_is_present():
    """THE OTHER HALF OF T074'S SCOPING, MISSING UNTIL 2026-08-28.

    The test above is right that an owner absent along with its entry is an
    unselected entry, not a loss. But the code had ONLY that branch: an
    unconditional `continue`, with no predicate to decide which case it was
    looking at. That converts every ORDERING or reachability bug in this pass
    into silence -- and it did. The pass ran at AFFIX_TEMPLATES, one category
    before STEMS created the `MoStemMsa` owners, so all 1,003 bindings hit
    this `continue`: no write, and no failure record either. Three census runs
    and a green suite said nothing.

    If the ENTRY is in the destination, this run selected it and its MSA
    should exist. That is a real dependency failure and must be reported.
    """
    src = _SrcHandle([_SrcEntry(msas=[_SrcMSA("msa1", MsFeaturesOA=_Struc(
        "s1", [_Closed("cv1", "feat1", "val1")]))])])
    bindings: dict = {}
    preview._populate_msa_feat_struc_bindings(src, bindings)

    # The entry IS in the destination; its MSA is NOT.
    skips, _ = _wire(
        bindings,
        {"entry1": _Obj("entry1"), "feat1": _Obj("feat1"),
         "val1": _Obj("val1")},
        owner_entries={"msa1": "entry1"},
    )

    assert len(skips) == 1, (
        "an owner absent while its entry is present is a dependency failure "
        "and must not be silent -- this silence hid 1,003 lost structures")
    assert skips[0].reason is SkipReason.DEPENDENCY_UNRESOLVED
    assert "entry1" in skips[0].detail


def test_wire_stays_silent_when_the_owner_cannot_be_scoped():
    """`msa_owner_entry` records MSAs, not allomorphs, so `MsEnvFeaturesOA`
    owners cannot be scoped. Degrade to silence rather than invent a failure
    on no evidence -- reporting on absence of evidence is the direction T074
    exists to remove."""
    src = _SrcHandle([_SrcEntry(msas=[_SrcMSA("msa1", MsFeaturesOA=_Struc(
        "s1", [_Closed("cv1", "feat1", "val1")]))])])
    bindings: dict = {}
    preview._populate_msa_feat_struc_bindings(src, bindings)

    skips, _ = _wire(bindings, {"feat1": _Obj("feat1"), "val1": _Obj("val1")},
                     owner_entries={})
    assert skips == []


def test_wire_reports_a_binding_it_cannot_attribute():
    """An unattributable binding is a producer defect, not a transfer
    decision. It must be reported rather than dropped (never-silent)."""
    skips, _ = _wire({"bogus": {"struc_guid": "s", "specs": []}}, {})
    assert len(skips) == 1
    assert skips[0].reason is SkipReason.DEPENDENCY_UNRESOLVED
    assert "owner_guid" in skips[0].detail


def test_wire_honours_the_identity_remap():
    """When the GUID-preserving create fell back to a minted identity, the
    owner is reachable only through the remap."""
    src = _SrcHandle([_SrcEntry(msas=[_SrcMSA("msa1", MsFeaturesOA=_Struc(
        "s1", [_Closed("cv1", "feat1", "val1")]))])])
    bindings: dict = {}
    preview._populate_msa_feat_struc_bindings(src, bindings)

    tgt = _TgtOwner("minted")
    skips, _ = _wire(bindings, {"minted": tgt, "feat1": _Obj("feat1"),
                                "val1": _Obj("val1")},
                     remap={"msa1": "minted"})
    assert skips == []
    assert _read(tgt.MsFeaturesOA) == {("feat1", "val1")}


# --------------------------------------------------------------------------
# Wiring: the pass has to actually be called
# --------------------------------------------------------------------------

def test_the_171_subpass_no_longer_runs_the_new_pass():
    """RETARGETED 2026-08-28, AND THE OLD VERSION OF THIS TEST IS THE BEST
    EVIDENCE FOR WHY SOURCE-TEXT ASSERTIONS ARE NOT ENOUGH.

    It read:

        body = inspect.getsource(categories._run_171_subpass)
        assert "_wire_owner_feat_strucs" in body

    and its docstring warned against "a pass nothing calls ... written,
    correct, and dead". It could not tell the difference between a pass that
    is CALLED and a pass that is merely MENTIONED -- so it stayed green while
    the pass ran one category too early and lost all 1,003
    `MoStemMsa.MsFeatures` structures, and it stayed green again after the
    call was removed, because the comment explaining the removal still
    contains the identifier.

    The 17.1 sub-pass is anchored to AFFIX_TEMPLATES, which executes BEFORE
    STEMS. `_wire_owner_feat_strucs` must therefore NOT be called from it.
    """
    import inspect
    body = inspect.getsource(categories._run_171_subpass)
    called = [ln for ln in body.splitlines()
              if "_wire_owner_feat_strucs" in ln
              and not ln.lstrip().startswith("#")]
    assert called == [], (
        "the feature-structure owner pass is called from the 17.1 sub-pass "
        "again; that sub-pass runs at AFFIX_TEMPLATES, one category before "
        "STEMS creates the MoStemMsa owners it needs: %r" % (called,))
    assert "_wire_msa_infl_feats" in body


def test_the_owner_pass_runs_after_the_whole_leaf_loop():
    """Where it moved TO, asserted on the caller rather than on a string.

    `transfer.execute` must invoke `_ensure_owner_feat_strucs` after the
    leaf-dispatch loop, so every owner class exists whatever the user selected
    and whatever order the categories ran in.
    """
    import inspect
    from gramtrans.Lib import transfer

    assert hasattr(transfer, "_ensure_owner_feat_strucs")
    body = inspect.getsource(transfer.execute)
    assert "_ensure_owner_feat_strucs(exec_ctx" in body


def test_the_owner_pass_has_its_own_latch_not_the_171_one():
    """THE SAFETY NET MUST NOT BE DISARMED BY THE THING IT GUARDS.

    While this pass lived inside `_run_171_subpass`, the post-loop
    `_ensure_171_subpass` that would have re-run it after STEMS was already a
    no-op: the AFFIX_TEMPLATES tail had set `_did_171_subpass`. A shared latch
    made the bug unreachable by its own remedy. Separate flags, permanently.

    Asserted BEHAVIOURALLY. The first draft of this test grepped the function
    source for `_did_171_subpass` and failed on the docstring that explains
    all of the above -- the same source-text trap this file's
    `test_the_171_subpass_no_longer_runs_the_new_pass` exists to document.
    Prose about a flag is not use of a flag.
    """
    from gramtrans.Lib import transfer

    ran = []

    class _Ctx:
        pass

    ctx = _Ctx()
    # Exactly the state the AFFIX_TEMPLATES tail leaves behind.
    object.__setattr__(ctx, "_did_171_subpass", True)
    object.__setattr__(ctx, "_run_plan", types.SimpleNamespace(
        msa_feat_struc_bindings={}, identity_remap={}, msa_owner_entry={}))

    original = categories._wire_owner_feat_strucs
    try:
        categories._wire_owner_feat_strucs = (
            lambda c, t, p: ran.append(True) or [])
        transfer._ensure_owner_feat_strucs(ctx, object(), None, [])
    finally:
        categories._wire_owner_feat_strucs = original

    assert ran == [True], (
        "the owner pass was skipped because the 17.1 latch was already set -- "
        "a shared latch is what made the original defect unreachable by its "
        "own safety net")
    assert getattr(ctx, "_did_owner_feat_strucs", False) is True


def test_the_owner_pass_is_a_noop_when_already_run():
    """Idempotent: the latch makes a second call cost nothing, so adding the
    post-loop call cannot double-write."""
    from gramtrans.Lib import transfer

    class _Ctx:
        pass

    ctx = _Ctx()
    object.__setattr__(ctx, "_did_owner_feat_strucs", True)
    object.__setattr__(ctx, "_run_plan", object())
    skips: list = []
    transfer._ensure_owner_feat_strucs(ctx, object(), None, skips)
    assert skips == []


def test_the_owner_pass_never_raises_without_a_plan():
    """No plan is not an error: a failure here must not lose the writes the
    run already made."""
    from gramtrans.Lib import transfer

    class _Ctx:
        pass

    skips: list = []
    transfer._ensure_owner_feat_strucs(_Ctx(), object(), None, skips)
    assert skips == []


def test_runplan_carries_the_new_bindings():
    from gramtrans.Lib.models import RunPlan
    field = RunPlan.__dataclass_fields__.get("msa_feat_struc_bindings")
    assert field is not None
    # A shared mutable default would leak bindings between runs.
    assert field.default_factory is dict


def test_owner_attr_table_matches_the_categories_table():
    """`preview` mirrors `categories._MSA_FEAT_STRUC_ATTRS` minus the
    inflectional slot. If someone adds a fifth MSA slot to one and not the
    other, this is what says so."""
    assert set(preview._MSA_EXTRA_FEAT_STRUC_ATTRS) | {"InflFeatsOA"} == set(
        categories._MSA_FEAT_STRUC_ATTRS)


@pytest.mark.parametrize("attr", [
    "MsFeaturesOA", "FromMsFeaturesOA", "ToMsFeaturesOA", "MsEnvFeaturesOA",
])
def test_every_written_attr_has_a_skip_category(attr):
    """A Skip filed under the wrong category is a report defect. Every
    attribute this pass can write must have an explicit row."""
    assert attr in categories._FEAT_STRUC_OWNER_CATEGORIES
