"""Feature 038, US5 -- an affix process rule is reproduced or reported, never
downgraded into a plain allomorph.

The historic defect (`GT-20260819-030049`, 13/13 `MoAffixProcess` destroyed on
Ejagham and 1/1 on the second pair): `_dispatch_allomorph_subclass` correctly
returned `None` for `MoAffixProcess`, and `_walk_entry_allomorphs._mk` ignored
the `None` and fell through the factory ternary's `else` to
`IMoAffixAllomorphFactory` anyway. The result kept the source GUID and `Form`,
silently discarded `InputOS`/`OutputOS` -- the entire process-rule chain -- and
was then stamped with GT residue, so the run reported a clean transfer.

These are the two host-free layers of the three-layer proof in
`specs/038-transfer-fidelity-gaps/contracts/process-morphology-create-path.md`
section 5. Layer (c), the census gate against `Mbugwe LizzieHC practice`, is
`tests/integration/test_038_process_rules.py` (T063/T064).

- **T049, layer (a) -- class-identity assertion.** Feed the walk a fake whose
  `ClassName == "MoAffixProcess"` while the create path is stubbed to fail, and
  assert *neither* allomorph factory was so much as ASKED FOR. The pre-existing
  coverage in `test_038_affix_fidelity.py` asserts the weaker "nothing landed on
  the entry", which a create-then-discard would still satisfy; this asserts the
  factory was never reached.
- **T050, layer (b) -- the negative-whitelist invariant.** The same guarantee
  for *every* `ClassName` the dispatch refuses, not just the one class that was
  observed failing. This is what makes the downgrade unable to recur for an
  `IMoForm` subclass nobody has thought of yet.
- **T051 -- no planned action may name a target class differing from its source
  class** (`data-model.md` section 8's hard invariant, FR-025/SC-010). Two
  halves: the dispatch never RENAMES a class, and the object actually created
  for a dispatchable class is of that same class. The second half is the trap
  T057 is filed to avoid -- adding `MoAffixProcess` to the `known` set while the
  factory ternary still routes everything non-stem to
  `IMoAffixAllomorphFactory` reinstates the downgrade exactly, and the test
  reads the whitelist at run time so it covers that class the moment T057 lands.
"""
from __future__ import annotations

import sys
import types
from types import SimpleNamespace

import pytest

from gramtrans.Lib import categories
import gramtrans.Lib.categories as _cat_mod
import gramtrans.Lib.owned as _owned_mod
import gramtrans.Lib.residue as _residue_mod
from gramtrans.Lib.models import DroppedItemRecord


# ============================================================================
# The class corpus under test
# ============================================================================

#: Every concrete `IMoForm` subclass LCM defines. `MoAffixProcess` is the one
#: this engine cannot (yet) reproduce; the other two are the reproducible pair.
IMOFORM_SUBCLASSES = ("MoAffixAllomorph", "MoStemAllomorph", "MoAffixProcess")

#: Names the dispatch must refuse. Real LCM neighbours that are NOT IMoForm
#: subclasses, a plausible-looking future subclass, and degenerate inputs -- a
#: whitelist that leaks would send any of these to an allomorph factory.
REFUSED_CLASS_NAMES = (
    # NOT "MoAffixProcess" -- T057 admitted it to the whitelist in the same
    # change as its real executor, so it is dispatchable now and its own
    # coverage is the T049 section below. Leaving it here would have made this
    # corpus assert the opposite of the shipped contract.
    "MoSomethingNew",
    "MoInflAffixSlot",
    "MoInflAffixTemplate",
    "MoDerivAffMsa",
    "PhSequenceContext",
    "LexEntry",
    "moaffixallomorph",  # case matters: the whitelist is exact
    "MoAffixAllomorph ",  # so does whitespace
    "",
    None,
)


# ============================================================================
# Fakes
# ============================================================================

class _FactoryIface:
    """Stands in for an LCM factory interface object, e.g.
    `IMoAffixAllomorphFactory`.

    Callable because the engine uses the pythonnet cast idiom
    ``factory_iface(target.GetFactory(factory_iface))``. `creates_class` is
    derived from the interface NAME rather than hard-coded, so when T053 adds
    `IMoAffixProcessFactory` to the walk's import list this harness recognises
    it with no edit -- the invariant then covers the new class automatically
    instead of quietly ignoring it.
    """

    def __init__(self, name: str) -> None:
        self.name = name
        assert name.startswith("I") and name.endswith("Factory"), name
        self.creates_class = name[1:-len("Factory")]

    def __call__(self, obj):
        return obj

    def __repr__(self) -> str:  # pragma: no cover -- assertion messages only
        return f"<{self.name}>"


class _LcmStub(types.ModuleType):
    """`SIL.LCModel` stand-in that manufactures any `I<Class>Factory` on demand.

    Manufacturing rather than enumerating is deliberate: a future import of a
    factory this file has never heard of must not fail the suite with an
    ImportError that hides which factory the engine reached.
    """

    def __getattr__(self, name):
        if name.startswith("I") and name.endswith("Factory"):
            iface = _FactoryIface(name)
            setattr(self, name, iface)
            return iface
        raise AttributeError(name)


class _Form:
    """Duck-typed `IMoForm`: lowercase `.guid` plus a `ClassName`."""

    def __init__(self, guid: str, class_name) -> None:
        self.guid = guid
        self.ClassName = class_name


class _Seq(list):
    """LCM owning-sequence surface."""

    def Add(self, item):
        self.append(item)


class _Entry:
    def __init__(self, guid, lexeme_form=None, alternates=()) -> None:
        self.guid = guid
        self.LexemeFormOA = lexeme_form
        self.AlternateFormsOS = list(alternates)
        self.MorphoSyntaxAnalysesOC = []


class _Created:
    """What a spied factory hands back: an object that knows its own class.

    Carries the owning/reference sequences the process-rule create path writes
    through, so a graph really is assembled rather than merely counted.
    """

    def __init__(self, guid: str, class_name: str) -> None:
        self.guid = guid
        self.ClassName = class_name
        self.InputOS = _Seq()
        self.OutputOS = _Seq()
        self.MembersRS = _Seq()
        self.ContentRS = _Seq()
        self.FeatureStructureRA = None
        self.ContentRA = None


class _Member:
    """A rule-graph member: a class name, a GUID, and whatever references its
    class declares. Anything not passed simply is not there, which is what a
    `PhVariable` (no own properties) looks like."""

    def __init__(self, class_name: str, guid: str, **refs) -> None:
        self.ClassName = class_name
        self.guid = guid
        for name, value in refs.items():
            setattr(self, name, value)


class _Rule(_Member):
    """A source `MoAffixProcess` with its two owned sequences."""

    def __init__(self, guid: str, inputs=(), outputs=()) -> None:
        super().__init__("MoAffixProcess", guid)
        self.InputOS = list(inputs)
        self.OutputOS = list(outputs)


class _TargetObj:
    """A destination object reachable by GUID -- a phoneme, a natural class, a
    shared project-level context."""

    def __init__(self, guid: str, class_name: str) -> None:
        self.guid = guid
        self.ClassName = class_name


class _FlexiconRefusal(Exception):
    """Stands in for flexicon's `FP_ParameterError`, which
    `AllomorphOperations` raises for any ClassName outside the two allomorph
    factories it manages."""


class _AllomorphOps:
    """flexicon's `AllomorphOperations` surface, as the engine uses it.

    On a live host `source_handle.Allomorphs` always EXISTS -- so the
    field-level drop the engine reports here fires only when flexicon actually
    refuses the class, which is the case worth reporting. A fake without this
    attribute would have made the drop fire on a harness gap instead.
    """

    def __init__(self, refuses: bool = False) -> None:
        self.refuses = refuses
        self.applied = []

    def GetSyncableProperties(self, obj):
        if self.refuses:
            raise _FlexiconRefusal(
                "AllomorphOperations does not manage " + str(obj.ClassName))
        return {"Form": {"vernacular": "src-form"}}

    def ApplySyncableProperties(self, obj, props, ws_map=None):
        if self.refuses:
            raise _FlexiconRefusal(
                "AllomorphOperations does not manage " + str(obj.ClassName))
        self.applied.append((obj, props))
        obj.Form = props.get("Form")


class _Spy:
    """Records every factory the engine asks for and every object it creates."""

    def __init__(self) -> None:
        self.factories_requested: list[str] = []
        self.classes_created: list[str] = []

    @property
    def reached_an_allomorph_factory(self) -> bool:
        return any(
            n in ("IMoAffixAllomorphFactory", "IMoStemAllomorphFactory")
            for n in self.factories_requested
        )


# ============================================================================
# Harness
# ============================================================================

@pytest.fixture
def _stub_lcm():
    fake = _LcmStub("SIL.LCModel")
    fake.ILexEntry = lambda obj: obj
    fake.ICmObject = lambda obj: SimpleNamespace(
        Guid=getattr(obj, "guid", ""),
        ClassName=getattr(obj, "ClassName", None),
    )
    sys.modules.setdefault("SIL", types.ModuleType("SIL"))
    original = sys.modules.get("SIL.LCModel")
    sys.modules["SIL.LCModel"] = fake
    yield fake
    if original is None:
        sys.modules.pop("SIL.LCModel", None)
    else:
        sys.modules["SIL.LCModel"] = original


@pytest.fixture(autouse=True)
def _patch_guid(monkeypatch):
    monkeypatch.setattr(
        _cat_mod,
        "_guid_str_from",
        lambda obj: str(getattr(obj, "guid", "")).lower(),
    )


@pytest.fixture
def spy(monkeypatch):
    """Spy the two observable creation steps: which factory is asked for, and
    what `create_with_guid` is then asked to build.

    Everything downstream of the create (reference fields, allomorph-hung data,
    residue) is stubbed out -- this file's subject is which CLASS gets created,
    and a fake object cannot carry a real resolver's inputs.
    """
    s = _Spy()

    def _fake_create_with_guid(factory, src_guid, kind):
        s.classes_created.append(getattr(factory, "creates_class", kind))
        return _Created(src_guid, getattr(factory, "creates_class", kind))

    monkeypatch.setattr(_cat_mod, "create_with_guid", _fake_create_with_guid)
    monkeypatch.setattr(
        _cat_mod, "_apply_reference_fields", lambda *a, **k: None)
    monkeypatch.setattr(
        _owned_mod, "reproduce_allomorph_hung_data", lambda *a, **k: None)
    monkeypatch.setattr(_residue_mod, "apply_residue", lambda *a, **k: None)
    return s


@pytest.fixture
def failing_create(monkeypatch, spy):
    """The create path stubbed to FAIL, per the contract's layer (a): a create
    that returns nothing must not be retried against a simpler class."""

    def _fails(factory, src_guid, kind):
        spy.classes_created.append(getattr(factory, "creates_class", kind))
        return None

    monkeypatch.setattr(_cat_mod, "create_with_guid", _fails)
    return spy


def _ctx_and_target(spy=None, destination=(), allomorph_ops_refuses=False,
                    contexts_os=None):
    """A run context whose destination holds `destination` addressably by GUID.

    `get_object_by_guid` is the offline half of `_resolve_target_by_guid` --
    the live path goes through the LCM object repository -- so a destination
    populated here is what FR-024's "resolve to the matched item" resolves to.

    `contexts_os` (T076) is the destination's `PhPhonData.ContextsOS`. It
    DEFAULTS TO ABSENT on purpose: a target with no phonological data is the
    shape every pre-T076 test in this file was written against, and the
    co-create path must report a reason on it rather than raise. Pass a
    `_Seq()` to exercise the co-create.
    """
    def _get_factory(iface):
        if spy is not None:
            spy.factories_requested.append(getattr(iface, "name", repr(iface)))
        return iface

    by_guid = {o.guid: o for o in destination}
    cache = SimpleNamespace(DefaultAnalWs=1)
    if contexts_os is not None:
        cache.LangProject = SimpleNamespace(
            PhonologicalDataOA=SimpleNamespace(ContextsOS=contexts_os))
    target = SimpleNamespace(
        Cache=cache,
        GetFactory=_get_factory,
        get_object_by_guid=by_guid.get,
        Allomorphs=_AllomorphOps(allomorph_ops_refuses),
    )
    ctx = SimpleNamespace(
        target_handle=target,
        source_handle=SimpleNamespace(
            Allomorphs=_AllomorphOps(allomorph_ops_refuses)),
        _ws_map=None,
    )
    return ctx, target


def _walk(entry, spy, destination=(), allomorph_ops_refuses=False,
          contexts_os=None):
    """Run the Move-mode walk over `entry`, returning its dropped records."""
    new_entry = SimpleNamespace(LexemeFormOA=None, AlternateFormsOS=_Seq())
    ctx, _target = _ctx_and_target(spy, destination, allomorph_ops_refuses,
                                   contexts_os)
    dropped: list = []
    categories._walk_entry_allomorphs(
        entry, new_entry, ctx, tag=None, identity_remap={}, dropped=dropped
    )
    return new_entry, dropped, ctx


# ============================================================================
# The live corpus's rule shape, as a fixture
# ============================================================================

#: Destination phoneme and natural class, addressable by the SOURCE GUID --
#: which is what "resolve to the destination item matched under FR-001/FR-002"
#: means once Phase 1's creates preserve GUIDs.
DEST_PHONEME = "7325210f-0000-0000-0000-00000000aaaa"
DEST_NC = "8f5b331b-0000-0000-0000-00000000bbbb"
SHARED_CTX = "cccccccc-0000-0000-0000-0000000000cc"


def _reproducible_rule():
    """The representative live rule from the create-path contract section 4
    (`Mbugwe LizzieHC practice`, entry `re-2`), and its destination.

    Input  = [PhSimpleContextNC -> NC, PhVariable]
    Output = [MoInsertPhones -> phoneme, MoCopyFromInput -> that NC context,
              MoCopyFromInput -> the same NC context]

    The doubled `MoCopyFromInput` is the point: one input member referenced by
    two output steps is what makes the intra-rule GUID map many-to-one
    tolerant rather than a bijection, and it is measured, not invented.
    """
    ctx_nc = _Member("PhSimpleContextNC", "ctx-nc-0001",
                     FeatureStructureRA=_TargetObj(DEST_NC, "PhNCSegments"),
                     PlusConstrRS=[], MinusConstrRS=[])
    ctx_var = _Member("PhVariable", "ctx-var-0002")
    rule = _Rule(
        "19bab2cf-6580-45db-b600-58857c4a6e65",
        inputs=[ctx_nc, ctx_var],
        outputs=[
            _Member("MoInsertPhones", "out-ins-0003",
                    ContentRS=[_TargetObj(DEST_PHONEME, "PhPhoneme")]),
            _Member("MoCopyFromInput", "out-cpy-0004", ContentRA=ctx_nc),
            _Member("MoCopyFromInput", "out-cpy-0005", ContentRA=ctx_nc),
        ],
    )
    destination = (
        _TargetObj(DEST_PHONEME, "PhPhoneme"),
        _TargetObj(DEST_NC, "PhNCSegments"),
    )
    return rule, destination


def _rule_records(ctx):
    return list(getattr(ctx, "_process_rules", ()) or ())


# ============================================================================
# T049 -- layer (a): class-identity assertion on MoAffixProcess
# ============================================================================

def test_affix_process_never_reaches_an_allomorph_factory(
    _stub_lcm, failing_create
):
    """The core lock. Neither allomorph factory is so much as REQUESTED.

    `test_038_affix_fidelity.py` already proves nothing lands on the entry;
    this proves nothing was created and thrown away either, which is the
    difference between "the guard fired" and "the damage was tidied up".
    """
    proc = _Form("19bab2cf-6580-45db-b600-58857c4a6e65", "MoAffixProcess")
    entry = _Entry("aaaaaaaa-0000-0000-0000-000000000001", lexeme_form=proc)

    new_entry, dropped, _ctx = _walk(entry, failing_create)

    assert failing_create.factories_requested == []
    assert failing_create.classes_created == []
    assert new_entry.LexemeFormOA is None
    assert list(new_entry.AlternateFormsOS) == []

    assert len(dropped) == 1
    rec = dropped[0]
    assert isinstance(rec, DroppedItemRecord)
    assert rec.item_name == "MoAffixProcess"
    assert rec.item_guid == "19bab2cf-6580-45db-b600-58857c4a6e65"
    assert rec.owner_kind == "LexEntry"
    assert rec.owner_guid == "aaaaaaaa-0000-0000-0000-000000000001"
    assert rec.field_name == "LexemeFormOA"
    assert rec.reason.strip()


def test_affix_process_in_alternate_forms_is_reported_against_that_field(
    _stub_lcm, failing_create
):
    proc = _Form("bbbbbbbb-0000-0000-0000-000000000002", "MoAffixProcess")
    entry = _Entry("aaaaaaaa-0000-0000-0000-000000000003", alternates=[proc])

    new_entry, dropped, _ctx = _walk(entry, failing_create)

    assert failing_create.factories_requested == []
    assert list(new_entry.AlternateFormsOS) == []
    assert [r.field_name for r in dropped] == ["AlternateFormsOS"]
    assert [r.item_name for r in dropped] == ["MoAffixProcess"]


def test_one_rule_yields_exactly_one_record_even_beside_good_allomorphs(
    _stub_lcm, spy
):
    """A rule dropped from an entry that also carries reproducible allomorphs:
    the good ones still transfer, the rule contributes EXACTLY one record.

    An entry losing its remaining allomorphs to one unreproducible member would
    be a second silent loss hiding behind the first.
    """
    proc = _Form("cccccccc-0000-0000-0000-000000000004", "MoAffixProcess")
    good = _Form("dddddddd-0000-0000-0000-000000000005", "MoAffixAllomorph")
    entry = _Entry(
        "aaaaaaaa-0000-0000-0000-000000000006",
        lexeme_form=proc,
        alternates=[good],
    )

    new_entry, dropped, _ctx = _walk(entry, spy)

    assert spy.classes_created == ["MoAffixAllomorph"]
    assert [o.ClassName for o in new_entry.AlternateFormsOS] == [
        "MoAffixAllomorph"]
    assert len(dropped) == 1
    assert dropped[0].item_guid == "cccccccc-0000-0000-0000-000000000004"


def test_preview_reports_the_same_rule_move_refuses(_stub_lcm, spy):
    """Principle III: Preview must SHOW the skip, not discover it at Move time.

    The Preview twin lives in `_plan_entry_reference_decisions`; a rule it
    silently omitted would make Preview and Move disagree about what a run does.
    """
    proc = _Form("eeeeeeee-0000-0000-0000-000000000007", "MoAffixProcess")
    entry = _Entry("aaaaaaaa-0000-0000-0000-000000000008", lexeme_form=proc)

    _new_entry, move_dropped, _mctx = _walk(entry, spy)

    preview_dropped: list = []
    ctx, _target = _ctx_and_target(spy)
    ctx._dropped = preview_dropped
    categories._plan_entry_reference_decisions(entry, ctx, target=object())

    def _key(records):
        return sorted(
            (r.owner_guid, r.field_name, r.item_guid, r.item_name)
            for r in records
        )

    assert _key(preview_dropped) == _key(move_dropped)
    assert len(preview_dropped) == 1
    assert spy.factories_requested == []


# ============================================================================
# T050 -- layer (b): the negative-whitelist invariant
# ============================================================================

@pytest.mark.parametrize("class_name", REFUSED_CLASS_NAMES)
def test_a_refused_class_never_reaches_a_factory(
    _stub_lcm, failing_create, class_name
):
    """FR-025's SHAPE, not one instance: for every `ClassName` the dispatch
    refuses, the walk returns without asking for any factory at all.

    This is what makes the downgrade unable to recur for a subclass nobody has
    thought of. Each case also proves the refusal is REPORTED -- a silent
    refusal is the same loss with a different mechanism (Principle I).
    """
    assert categories._dispatch_allomorph_subclass(class_name) is None

    form = _Form("ffffffff-0000-0000-0000-000000000009", class_name)
    entry = _Entry("aaaaaaaa-0000-0000-0000-00000000000a", lexeme_form=form)

    new_entry, dropped, _ctx = _walk(entry, failing_create)

    assert failing_create.factories_requested == []
    assert failing_create.classes_created == []
    assert new_entry.LexemeFormOA is None
    assert list(new_entry.AlternateFormsOS) == []
    assert len(dropped) == 1
    assert dropped[0].item_guid == "ffffffff-0000-0000-0000-000000000009"
    assert dropped[0].reason.strip()


def test_the_refusal_set_is_exactly_the_complement_of_the_whitelist(_stub_lcm):
    """Guards the invariant's own premise: the parametrised corpus above is
    only meaningful while these names really are outside the whitelist. If a
    later change admits one of them, this fails rather than letting the
    parametrised test silently start asserting the wrong thing."""
    for name in REFUSED_CLASS_NAMES:
        assert categories._dispatch_allomorph_subclass(name) is None
    for name in IMOFORM_SUBCLASSES:
        dispatched = categories._dispatch_allomorph_subclass(name)
        assert dispatched is None or dispatched == name


# ============================================================================
# T051 -- no planned action may name a target class differing from its source
# ============================================================================

def test_the_dispatch_never_renames_a_class(_stub_lcm):
    """Half one of `data-model.md` section 8's hard invariant, at the only site
    that chooses a class: the dispatch either accepts a class under its own
    name, or refuses it. It may never answer with a DIFFERENT name -- that
    answer is precisely the `MoAffixProcess -> MoAffixAllomorph` downgrade."""
    corpus = tuple(IMOFORM_SUBCLASSES) + tuple(
        n for n in REFUSED_CLASS_NAMES if n
    )
    for name in corpus:
        dispatched = categories._dispatch_allomorph_subclass(name)
        assert dispatched is None or dispatched == name, (
            f"dispatch renamed {name!r} to {dispatched!r} -- an object would "
            "be created as a different, simpler kind (FR-025)"
        )


@pytest.mark.parametrize("class_name", IMOFORM_SUBCLASSES)
def test_created_class_equals_source_class(_stub_lcm, spy, class_name):
    """Half two, and the trap T057 exists to avoid.

    The whitelist is read at RUN TIME and the harness derives each factory's
    class from its interface NAME, so `MoAffixProcess` entered this invariant
    automatically when T057 admitted it -- no edit here, and no way to admit a
    class silently. Admitting it while `_walk_entry_allomorphs._mk` still
    routed every non-stem subclass to `IMoAffixAllomorphFactory` reinstates
    the historic defect, and this test then fails naming both classes. That is
    why T057 and T058 landed in one change.

    Each `IMoForm` subclass is fed the smallest source object that its own
    create path accepts, because "nothing was created" and "the wrong thing
    was created" are different answers and only the second is a defect.
    """
    if class_name == "MoAffixProcess":
        form, destination = _reproducible_rule()
    else:
        form, destination = _Form(
            "11111111-0000-0000-0000-00000000000b", class_name), ()
    entry = _Entry("aaaaaaaa-0000-0000-0000-00000000000c", lexeme_form=form)

    new_entry, dropped, _ctx = _walk(entry, spy, destination)

    dispatched = categories._dispatch_allomorph_subclass(class_name)
    if dispatched is None:
        # Refused: nothing created, and the refusal is reported.
        assert spy.classes_created == []
        assert new_entry.LexemeFormOA is None
        assert len(dropped) == 1
        return

    # Accepted. The object attached to the entry is of the SOURCE's class,
    # the rule's OWN factory was the first one asked for, and no allomorph
    # factory was reached for a class that is not an allomorph.
    assert new_entry.LexemeFormOA is not None
    assert new_entry.LexemeFormOA.ClassName == class_name, (
        f"source {class_name} arrived as "
        f"{new_entry.LexemeFormOA.ClassName} -- an object may never be "
        "created as a different kind (FR-025, SC-010)"
    )
    assert spy.classes_created[0] == class_name, (
        f"source {class_name} was created as {spy.classes_created[0]} -- an "
        "object may never be created as a different kind (FR-025, SC-010)"
    )
    assert spy.factories_requested[0] == f"I{class_name}Factory"
    if class_name != "MoAffixAllomorph":
        assert "IMoAffixAllomorphFactory" not in spy.factories_requested
    if class_name != "MoStemAllomorph":
        assert "IMoStemAllomorphFactory" not in spy.factories_requested
    assert dropped == []


def test_preview_plans_nothing_for_a_class_move_will_not_create(
    _stub_lcm, spy
):
    """The invariant's plan-side half. Preview must not emit reference
    decisions for a rule Move refuses -- decisions naming an object that will
    never exist are how a plan comes to name a class the run cannot deliver."""
    proc = _Form("22222222-0000-0000-0000-00000000000d", "MoAffixProcess")
    entry = _Entry("aaaaaaaa-0000-0000-0000-00000000000e", lexeme_form=proc)

    ctx, _target = _ctx_and_target(spy)
    dropped: list = []
    ctx._dropped = dropped

    records = categories._plan_entry_reference_decisions(
        entry, ctx, target=object())

    rule_guid = "22222222-0000-0000-0000-00000000000d"
    assert not [
        r for r in records
        if rule_guid in (getattr(r, "owner_guid", ""), getattr(r, "guid", ""))
    ]
    assert [r.item_guid for r in dropped] == [rule_guid]
    assert spy.factories_requested == []


# ============================================================================
# T053-T058 -- the create path itself
# ============================================================================

def test_a_wholly_owned_rule_is_rebuilt_with_its_input_and_output(
    _stub_lcm, spy
):
    """SC-006: "with their input and output content". A rule that arrives as a
    correctly-classed shell with an empty `OutputOS` is the same loss as the
    downgrade wearing a better class name, so the assertions are on CONTENT."""
    rule, destination = _reproducible_rule()
    entry = _Entry("aaaaaaaa-0000-0000-0000-00000000000f", lexeme_form=rule)

    new_entry, dropped, ctx = _walk(entry, spy, destination)

    new_rule = new_entry.LexemeFormOA
    assert new_rule.ClassName == "MoAffixProcess"
    assert new_rule.guid == "19bab2cf-6580-45db-b600-58857c4a6e65"
    assert dropped == []

    # Input first, in source order.
    assert [m.ClassName for m in new_rule.InputOS] == [
        "PhSimpleContextNC", "PhVariable"]
    assert new_rule.InputOS[0].FeatureStructureRA.guid == DEST_NC

    # Output in source order -- order is significant.
    assert [m.ClassName for m in new_rule.OutputOS] == [
        "MoInsertPhones", "MoCopyFromInput", "MoCopyFromInput"]
    assert [t.guid for t in new_rule.OutputOS[0].ContentRS] == [DEST_PHONEME]

    # The intra-rule back-reference points at the NEW input member, not at the
    # source object and not at a second copy of it.
    assert new_rule.OutputOS[1].ContentRA is new_rule.InputOS[0]
    assert new_rule.OutputOS[2].ContentRA is new_rule.InputOS[0]


def test_the_intra_rule_map_is_many_to_one(_stub_lcm, spy):
    """Two output steps naming ONE input member is the live shape (rule
    `re-2`). A map that assumed a bijection would either raise or silently
    create a second input member for the second reference."""
    rule, destination = _reproducible_rule()
    entry = _Entry("aaaaaaaa-0000-0000-0000-000000000010", lexeme_form=rule)

    new_entry, _dropped, _ctx = _walk(entry, spy, destination)

    new_rule = new_entry.LexemeFormOA
    assert len(new_rule.InputOS) == 2  # not 3
    assert new_rule.OutputOS[1].ContentRA is new_rule.OutputOS[2].ContentRA


def test_every_member_is_created_with_its_source_guid(_stub_lcm, spy):
    """Criterion 2: all creates go through `create_with_guid`, never a bare
    `Create()`. A regenerated identity would make a re-run duplicate the whole
    graph instead of recognising it (SC-008)."""
    rule, destination = _reproducible_rule()
    entry = _Entry("aaaaaaaa-0000-0000-0000-000000000011", lexeme_form=rule)

    new_entry, _dropped, _ctx = _walk(entry, spy, destination)

    new_rule = new_entry.LexemeFormOA
    assert [m.guid for m in new_rule.InputOS] == ["ctx-nc-0001", "ctx-var-0002"]
    assert [m.guid for m in new_rule.OutputOS] == [
        "out-ins-0003", "out-cpy-0004", "out-cpy-0005"]


def test_a_reproduced_rule_is_recorded_with_what_arrived(_stub_lcm, spy):
    """SC-010 needs the run to be able to say which rules it REBUILT, not only
    which it could not."""
    rule, destination = _reproducible_rule()
    entry = _Entry("aaaaaaaa-0000-0000-0000-000000000012", lexeme_form=rule)

    _new_entry, _dropped, ctx = _walk(entry, spy, destination)

    records = _rule_records(ctx)
    assert len(records) == 1
    rec = records[0]
    assert rec.reproduced is True
    assert rec.source_guid == "19bab2cf-6580-45db-b600-58857c4a6e65"
    assert [c.context_class for c in rec.input_contexts] == [
        "PhSimpleContextNC", "PhVariable"]
    assert [o.step_class for o in rec.output_steps] == [
        "MoInsertPhones", "MoCopyFromInput", "MoCopyFromInput"]
    assert [o.index for o in rec.output_steps] == [0, 1, 2]


# --- T055: the R5 condition-4 detector and the unexercised classes ---------

def test_a_sequence_context_naming_a_shared_context_skips_the_rule(
    _stub_lcm, spy
):
    """Condition 4, the finding that split Phase 4. A `PhSequenceContext` is
    owned by the rule but its `MembersRS` name shared, project-level
    `PhPhonData.ContextsOS` contexts -- 6 of the 18 live rules. Creating the
    rule with an empty or partly-filled `MembersRS` is the silent content loss
    FR-023 forbids, so the whole rule skips and the reason names the member.

    RE-POINTED BY T076, not left to pass by accident. T076 gave this engine a
    co-create path for a shared context, so "absent from the destination" is
    no longer sufficient on its own to skip -- the rule now skips only when
    the context ALSO fails the co-create test. This fake fails it in the
    plainest way available (`shared` has no `Owner`, so it is not a
    `PhPhonData.ContextsOS` member as far as this engine can tell), and the
    assertion below pins WHICH branch refused it. Without that pin this test
    would keep passing while testing something it was never about.
    """
    shared = _TargetObj(SHARED_CTX, "PhSimpleContextSeg")
    seq = _Member("PhSequenceContext", "ctx-seq-0006", MembersRS=[shared])
    rule = _Rule("rule-seq-0001", inputs=[seq],
                 outputs=[_Member("MoCopyFromInput", "out-0007",
                                  ContentRA=seq)])
    entry = _Entry("aaaaaaaa-0000-0000-0000-000000000013", lexeme_form=rule)

    new_entry, dropped, ctx = _walk(entry, spy, destination=())

    assert new_entry.LexemeFormOA is None
    assert not spy.reached_an_allomorph_factory
    assert len(dropped) == 1
    assert dropped[0].item_name == "MoAffixProcess"
    assert SHARED_CTX in dropped[0].reason
    assert "PhPhonData.ContextsOS" in dropped[0].reason
    # T076: WHICH refusal. This is the "neither present nor co-createable"
    # branch, not the co-create's own "the referent did not resolve".
    assert "nor a PhPhonData.ContextsOS context this engine can co-create" \
        in " ".join(dropped[0].reason.split())
    records = _rule_records(ctx)
    assert len(records) == 1 and records[0].reproduced is False
    assert records[0].not_reproducible_reason


def test_the_same_rule_transfers_once_the_shared_context_is_present(
    _stub_lcm, spy
):
    """The detector is written against RESOLVABILITY, not against a hard-coded
    list of six rules -- so Phase 7's closure switches these rules on with no
    edit to the create path. This is that claim, executed."""
    shared = _TargetObj(SHARED_CTX, "PhSimpleContextSeg")
    seq = _Member("PhSequenceContext", "ctx-seq-0006", MembersRS=[shared])
    rule = _Rule("rule-seq-0001", inputs=[seq],
                 outputs=[_Member("MoCopyFromInput", "out-0007",
                                  ContentRA=seq)])
    entry = _Entry("aaaaaaaa-0000-0000-0000-000000000014", lexeme_form=rule)

    new_entry, dropped, _ctx = _walk(entry, spy, destination=(shared,))

    assert dropped == []
    new_rule = new_entry.LexemeFormOA
    assert new_rule.ClassName == "MoAffixProcess"
    assert [m.guid for m in new_rule.InputOS[0].MembersRS] == [SHARED_CTX]


def test_a_sequence_context_member_owned_by_the_rule_is_wired_to_the_new_one(
    _stub_lcm, spy
):
    """A member that IS a sibling input must resolve to the newly created
    sibling, not to a destination lookup that would find the SOURCE object."""
    ctx_seg = _Member("PhSimpleContextSeg", "ctx-seg-0008",
                      FeatureStructureRA=_TargetObj(DEST_PHONEME, "PhPhoneme"))
    seq = _Member("PhSequenceContext", "ctx-seq-0009", MembersRS=[ctx_seg])
    rule = _Rule("rule-seq-0002", inputs=[ctx_seg, seq],
                 outputs=[_Member("MoCopyFromInput", "out-0010",
                                  ContentRA=seq)])
    entry = _Entry("aaaaaaaa-0000-0000-0000-000000000015", lexeme_form=rule)

    new_entry, dropped, _ctx = _walk(
        entry, spy, destination=(_TargetObj(DEST_PHONEME, "PhPhoneme"),))

    assert dropped == []
    new_rule = new_entry.LexemeFormOA
    assert new_rule.InputOS[1].MembersRS[0] is new_rule.InputOS[0]


# ===========================================================================
# T076 -- the shared PhPhonData.ContextsOS context is CO-CREATED
# ===========================================================================
#
# WHY CO-CREATE AND NOT CLOSURE, which is what T076's task line asked for.
# Measured read-only on both corpora
# (`debug/audit038_t076_process_contexts.py`, artifact
# `tests/integration/_snapshots/t076-process-context-audit.json`): all 6 far
# endpoints on `Mbugwe LizzieHC practice` are owned by
# `PhPhonData.ContextsOS`, and **0 of 6 are reachable from
# `PhPhonData.PhonRulesOS`** -- the only path in this engine that ever creates
# a `PhSimpleContext*` into a destination's `ContextsOS`. No `GrammarCategory`
# enumerates a member of `ContextsOS` either, so an edge naming one is the
# unplannable far endpoint T089 refused to register. What IS registered is the
# referent one hop out (`PROCESS_RULE_TO_PHONEME` /
# `PROCESS_RULE_TO_NATURAL_CLASS`), measured 6 of 6 enumerable.


def _phon_data_owned(guid, class_name, referent=None, plus=(), minus=()):
    """A shared context as the SOURCE holds it: owned by `PhPhonData`.

    The `Owner` is what distinguishes a co-createable shared context from any
    other unowned member, so it is set explicitly here rather than defaulted
    -- a fake that carried it by accident would make the narrowing untestable.
    """
    kwargs = {"Owner": _TargetObj("owner-phondata", "PhPhonData")}
    if referent is not None:
        kwargs["FeatureStructureRA"] = referent
    if class_name == "PhSimpleContextNC":
        kwargs["PlusConstrRS"] = list(plus)
        kwargs["MinusConstrRS"] = list(minus)
    return _Member(class_name, guid, **kwargs)


def _shared_ctx_rule(shared, rule_guid="rule-shared-0001",
                     entry_guid="aaaaaaaa-0000-0000-0000-0000000000c4"):
    seq = _Member("PhSequenceContext", "ctx-seq-c4", MembersRS=[shared])
    rule = _Rule(rule_guid, inputs=[seq],
                 outputs=[_Member("MoCopyFromInput", "out-c4",
                                  ContentRA=seq)])
    return _Entry(entry_guid, lexeme_form=rule)


def test_a_shared_phon_data_context_is_co_created_and_wired(_stub_lcm, spy):
    """The headline: the rule that used to skip now transfers, and the
    context it needed was BUILT rather than found.

    Three things are asserted together because any one alone would pass on a
    wrong fix: the rule arrives, the context lands in the destination's
    `ContextsOS` carrying its SOURCE GUID (so a re-run recognises it), and the
    sequence's `MembersRS` points at that very object. A rule that arrived
    with an empty `MembersRS` would satisfy the first assertion alone, and
    that is exactly the silent content loss FR-023 forbids.
    """
    referent = _TargetObj(DEST_PHONEME, "PhPhoneme")
    shared = _phon_data_owned(SHARED_CTX, "PhSimpleContextSeg", referent)
    contexts_os = _Seq()

    new_entry, dropped, ctx = _walk(
        _shared_ctx_rule(shared), spy, destination=(referent,),
        contexts_os=contexts_os)

    assert dropped == []
    new_rule = new_entry.LexemeFormOA
    assert new_rule.ClassName == "MoAffixProcess"
    assert [c.ClassName for c in contexts_os] == ["PhSimpleContextSeg"]
    assert [c.guid for c in contexts_os] == [SHARED_CTX]
    assert contexts_os[0].FeatureStructureRA is referent
    assert new_rule.InputOS[0].MembersRS[0] is contexts_os[0]
    records = _rule_records(ctx)
    assert len(records) == 1 and records[0].reproduced is True


def test_the_co_created_context_is_reported_on_the_input_spec(_stub_lcm, spy):
    """SC-010 admits no unreported outcome, and a write into a SHARED,
    project-level collection made as a side effect of transferring a lexical
    entry is the write a reader is least able to see coming. So the source
    GUID of every co-created context is recorded on the input spec.

    The negative half is the one that makes the field mean something: a rule
    that co-creates nothing must record an EMPTY tuple, or "this run created
    a shared context" would be indistinguishable from "this field exists".
    """
    referent = _TargetObj(DEST_NC, "PhNCFeatures")
    shared = _phon_data_owned(SHARED_CTX, "PhSimpleContextNC", referent)

    _entry, dropped, ctx = _walk(
        _shared_ctx_rule(shared), spy, destination=(referent,),
        contexts_os=_Seq())
    assert dropped == []
    specs = _rule_records(ctx)[0].input_contexts
    assert [s.co_created_shared for s in specs] == [(SHARED_CTX,)]

    # ...and the ordinary rule, which co-creates nothing.
    rule, destination = _reproducible_rule()
    _entry2, dropped2, ctx2 = _walk(
        _Entry("aaaaaaaa-0000-0000-0000-0000000000c5", lexeme_form=rule),
        spy, destination=destination, contexts_os=_Seq())
    assert dropped2 == []
    assert all(s.co_created_shared == ()
               for s in _rule_records(ctx2)[0].input_contexts)


def test_a_shared_context_already_present_is_not_co_created_twice(
    _stub_lcm, spy
):
    """SC-008 idempotence, and the reason identity is still tried FIRST.

    On run 2 the context created by run 1 is in the destination under its
    source GUID, so `_resolve_process_referent` finds it and the co-create
    never runs. If the co-create ran anyway the destination would grow a
    second context per run -- the duplication this feature exists to remove,
    reintroduced by its own fix.
    """
    referent = _TargetObj(DEST_PHONEME, "PhPhoneme")
    shared = _phon_data_owned(SHARED_CTX, "PhSimpleContextSeg", referent)
    already_there = _TargetObj(SHARED_CTX, "PhSimpleContextSeg")
    contexts_os = _Seq()

    new_entry, dropped, _ctx = _walk(
        _shared_ctx_rule(shared), spy,
        destination=(referent, already_there), contexts_os=contexts_os)

    assert dropped == []
    assert list(contexts_os) == []          # nothing was built
    assert new_entry.LexemeFormOA.InputOS[0].MembersRS[0] is already_there


def test_a_context_owned_by_anything_but_phon_data_is_not_co_created(
    _stub_lcm, spy
):
    """The narrowing, and it needed its OWN test rather than riding on the
    unowned case.

    Mutation M2 found this gap: flipping the owner comparison to `return True`
    left every test green, because the one fake that reached the check had no
    `Owner` at all and was refused one line earlier. So the half of the
    predicate that says WHICH owner counts was untested, and a context owned
    by some other object would have quietly acquired a create path this task
    measured nothing about.

    The measurement this test protects: all 6 live far endpoints are owned by
    `PhPhonData` (flid 5099004). Anything else is unmeasured, and an
    unmeasured owner must keep the FR-025 skip rather than inherit one.
    """
    referent = _TargetObj(DEST_PHONEME, "PhPhoneme")
    elsewhere = _Member(
        "PhSimpleContextSeg", SHARED_CTX,
        Owner=_TargetObj("owner-other", "PhRegularRule"),
        FeatureStructureRA=referent)
    contexts_os = _Seq()

    new_entry, dropped, _ctx = _walk(
        _shared_ctx_rule(elsewhere), spy, destination=(referent,),
        contexts_os=contexts_os)

    assert new_entry.LexemeFormOA is None
    assert list(contexts_os) == []
    assert len(dropped) == 1
    assert "nor a PhPhonData.ContextsOS context this engine can co-create" \
        in " ".join(dropped[0].reason.split())


def test_a_shared_context_whose_referent_is_absent_still_skips(_stub_lcm, spy):
    """The co-create is not a licence to build a context that matches nothing.

    This engine can manufacture the two-field context object; it cannot
    manufacture the phoneme or natural class it points AT. When that referent
    does not resolve, co-creating would produce a context matching nothing --
    a rule that silently stops firing while the run reports success, which is
    the FR-024 failure the whole skip exists for. So the rule still skips and
    the reason names the referent, not the context.
    """
    referent = _TargetObj(DEST_PHONEME, "PhPhoneme")
    shared = _phon_data_owned(SHARED_CTX, "PhSimpleContextSeg", referent)

    new_entry, dropped, ctx = _walk(
        _shared_ctx_rule(shared), spy, destination=(), contexts_os=_Seq())

    assert new_entry.LexemeFormOA is None
    assert len(dropped) == 1
    reason = " ".join(dropped[0].reason.split())
    assert DEST_PHONEME in reason
    assert "co-creating the context would produce one that matches nothing" \
        in reason
    assert _rule_records(ctx)[0].reproduced is False


def test_a_shared_context_naming_no_referent_at_all_skips(_stub_lcm, spy):
    """A `FeatureStructureRA` of None in the SOURCE. Reproducing it faithfully
    would mean creating a context that matches nothing by construction, which
    FR-023 refuses for the same reason the rule's own members refuse it."""
    shared = _phon_data_owned(SHARED_CTX, "PhSimpleContextNC", None)

    _entry, dropped, _ctx = _walk(
        _shared_ctx_rule(shared), spy, destination=(), contexts_os=_Seq())

    assert len(dropped) == 1
    assert "names no natural class at all" in " ".join(
        dropped[0].reason.split()) or "names no" in dropped[0].reason


def test_a_shared_context_carrying_feature_constraints_skips(_stub_lcm, spy):
    """`PhFeatureConstraint` has zero live instances and ties into the feature
    system. The rule's OWN `PhSimpleContextNC` members already ship behind
    that skip (create-path contract section 4); a shared one gets the same
    treatment, because widening the create path to a class no corpus
    exercises is the guess that contract refuses."""
    referent = _TargetObj(DEST_NC, "PhNCFeatures")
    shared = _phon_data_owned(SHARED_CTX, "PhSimpleContextNC", referent,
                              plus=[_TargetObj("constr-1",
                                               "PhFeatureConstraint")])

    _entry, dropped, _ctx = _walk(
        _shared_ctx_rule(shared), spy, destination=(referent,),
        contexts_os=_Seq())

    assert len(dropped) == 1
    assert "PlusConstrRS" in dropped[0].reason


@pytest.mark.parametrize("unexercised_class", ["PhIterationContext"])
def test_an_unexercised_shared_context_class_is_not_co_created(
    _stub_lcm, spy, unexercised_class
):
    """`Mbugwe LizzieHC practice` really does hold 11 `PhIterationContext` in
    `ContextsOS` and NOT ONE is referenced by any of its 18 affix process
    rules -- measured, not assumed. It stays behind the FR-025 skip, and the
    destination's `ContextsOS` is left untouched.

    **T107 (2026-08-25) removed `PhSimpleContextBdry` from this parametrize,
    and the parametrize is kept for one class on purpose**: it is the shape of
    the claim that matters, and the next class proposed for the co-create path
    should land here first. T076 excluded the boundary context on two grounds
    -- "the path is unwritten" and "no corpus can check it" -- and `Ejagham W
    Mini` falsified the second: 5 of its 13 rules reach a boundary context
    through exactly this shared-`ContextsOS` route. `PhIterationContext` keeps
    both grounds intact. Evidence:
    `tests/integration/_snapshots/process-rules-038-t078-corpus.json`.
    """
    shared = _phon_data_owned(SHARED_CTX, unexercised_class,
                              _TargetObj(DEST_PHONEME, "PhPhoneme"))
    contexts_os = _Seq()

    _entry, dropped, _ctx = _walk(
        _shared_ctx_rule(shared), spy,
        destination=(_TargetObj(DEST_PHONEME, "PhPhoneme"),),
        contexts_os=contexts_os)

    assert len(dropped) == 1
    assert list(contexts_os) == []


# ===========================================================================
# T107 -- PhSimpleContextBdry, on both routes `Ejagham W Mini` uses
# ===========================================================================
#
# T076 held this class behind `_PROCESS_UNEXERCISED_CLASSES` on a measurement
# taken on `Mbugwe LizzieHC practice` alone: 22 boundary contexts in
# `ContextsOS`, not one referenced by any of its 18 rules. Correct, and it
# still reproduces. T078 measured the same question on `Ejagham W Mini` and
# got the opposite answer -- 13 of 13 rules blocked, on this class alone.
#
# TWO ROUTES, AND THE SPLIT IS EXACT. Verified read-only against the source's
# own object graph: 8 of the 10 `PhSimpleContextBdry` in `Ejagham W Mini` are
# owned directly by a `MoAffixProcess` (the direct `InputOS` route), 1 by a
# `PhSegRuleRHS` (a PHONOLOGICAL rule -- not this feature's), and exactly 1 by
# `PhPhonData`. Five distinct rules reach that single shared one through a
# rule-owned `PhSequenceContext`. 8 + 5 = the 13 blocked rules, with no rule
# counted twice. So both routes are load-bearing and each gets its own test.
#
# WHAT MAKES THE REFERENT RESOLVABLE, and why no closure edge is owed:
# `PhBdryMarker` is fixed FLEx content. All three sanctioned sources AND both
# live destinations hold the same two GUIDs -- 3bde17ce-...cb56 and
# 7db635e0-...89aaa -- and every one of Ejagham's 10 boundary contexts points
# at one of them. The census reads `PhBdryMarker` 2 -> 2 MATCHED on all three
# pairs, so the identity leg resolves and nothing needs creating one hop out.

#: A boundary marker as FLEx ships it: `kguidPhRuleWordBdry`, byte-identical
#: in every sanctioned source and in both live destinations. Spelled out
#: rather than invented because the whole reason this class needs no closure
#: edge is that this GUID is the SAME on both sides.
WORD_BDRY = "3bde17ce-e39a-4bae-8a5c-a8d96fd4cb56"


def _bdry_input_rule(bdry, rule_guid="rule-bdry-0001",
                     entry_guid="aaaaaaaa-0000-0000-0000-0000000000d1"):
    """The 8-rule route: the boundary context is the rule's OWN input member.

    Paired with a `MoCopyFromInput` pointing back at it, because an output
    step that copies nothing is a different skip and would mask this one.
    """
    rule = _Rule(rule_guid, inputs=[bdry],
                 outputs=[_Member("MoCopyFromInput", "out-d1",
                                  ContentRA=bdry)])
    return _Entry(entry_guid, lexeme_form=rule)


def test_a_boundary_context_as_a_direct_input_member_is_created_and_wired(
    _stub_lcm, spy
):
    """THE 8-RULE ROUTE, and the headline of T107: a rule that used to be
    dropped with a reason now arrives.

    The three assertions are inseparable. The rule arrives; the input member
    is a `PhSimpleContextBdry` carrying its SOURCE guid (so a re-run finds it
    rather than building a second); and its `FeatureStructureRA` is the
    DESTINATION boundary marker. A context created with a null referent would
    satisfy the first two and match nothing at all -- which is precisely the
    silent failure the FR-025 skip existed to prevent, so admitting the class
    without this third assertion would trade a reported loss for an
    unreported one.
    """
    marker = _TargetObj(WORD_BDRY, "PhBdryMarker")
    bdry = _Member("PhSimpleContextBdry", "ctx-bdry-d1",
                   FeatureStructureRA=marker)

    new_entry, dropped, ctx = _walk(
        _bdry_input_rule(bdry), spy, destination=(marker,))

    assert dropped == []
    new_rule = new_entry.LexemeFormOA
    assert new_rule.ClassName == "MoAffixProcess"
    assert [m.ClassName for m in new_rule.InputOS] == ["PhSimpleContextBdry"]
    assert new_rule.InputOS[0].guid == "ctx-bdry-d1"
    assert new_rule.InputOS[0].FeatureStructureRA is marker
    assert "IPhSimpleContextBdryFactory" in spy.factories_requested
    records = _rule_records(ctx)
    assert len(records) == 1 and records[0].reproduced is True


def test_a_direct_boundary_context_with_an_unresolved_marker_still_skips(
    _stub_lcm, spy
):
    """Admitting the class is not a licence to build one that matches nothing.

    The resolvability test T076 landed for phonemes and natural classes is
    UNCONDITIONAL -- it does not consult `_PROCESS_REFERENT_CATEGORY`, so the
    argument "boundary markers always resolve" is not what makes this safe;
    the check is. A destination that somehow lacks the marker keeps the
    FR-025 skip, and the reason names the MARKER rather than the context,
    because the marker is the thing this engine cannot manufacture.
    """
    marker = _TargetObj(WORD_BDRY, "PhBdryMarker")
    bdry = _Member("PhSimpleContextBdry", "ctx-bdry-d2",
                   FeatureStructureRA=marker)

    new_entry, dropped, ctx = _walk(
        _bdry_input_rule(bdry), spy, destination=())   # no marker there

    assert new_entry.LexemeFormOA is None
    assert len(dropped) == 1
    reason = " ".join(dropped[0].reason.split())
    assert "boundary marker" in reason
    assert WORD_BDRY in reason
    assert _rule_records(ctx)[0].reproduced is False


def test_a_direct_boundary_context_naming_no_marker_at_all_skips(
    _stub_lcm, spy
):
    """`FeatureStructureRA` None in the SOURCE. The derived
    `_PROCESS_SIMPLE_CONTEXT_CLASSES` set is what makes this fire: before
    T107 the referent check was an inline two-class tuple, so a third class
    with a factory would have been created with a null referent and reported
    as a success."""
    bdry = _Member("PhSimpleContextBdry", "ctx-bdry-d3",
                   FeatureStructureRA=None)

    new_entry, dropped, _ctx = _walk(
        _bdry_input_rule(bdry), spy, destination=())

    assert new_entry.LexemeFormOA is None
    assert len(dropped) == 1
    assert "names no boundary marker at all" in " ".join(
        dropped[0].reason.split())


def test_a_shared_boundary_context_is_co_created_and_wired(_stub_lcm, spy):
    """THE 5-RULE ROUTE -- the one T076 built and then excluded this class
    from. `Ejagham W Mini` holds exactly ONE `PhPhonData`-owned boundary
    context and five distinct rules reach it through a rule-owned
    `PhSequenceContext`, so this is the route that carries the majority of the
    contexts even though it is the minority of the rules.

    The owner is the whole difference from the test above: the object lands in
    the destination's project-level `ContextsOS`, not under the rule, because
    that is where the source keeps it.
    """
    marker = _TargetObj(WORD_BDRY, "PhBdryMarker")
    shared = _phon_data_owned(SHARED_CTX, "PhSimpleContextBdry", marker)
    contexts_os = _Seq()

    new_entry, dropped, ctx = _walk(
        _shared_ctx_rule(shared), spy, destination=(marker,),
        contexts_os=contexts_os)

    assert dropped == []
    assert [c.ClassName for c in contexts_os] == ["PhSimpleContextBdry"]
    assert [c.guid for c in contexts_os] == [SHARED_CTX]
    assert contexts_os[0].FeatureStructureRA is marker
    assert new_entry.LexemeFormOA.InputOS[0].MembersRS[0] is contexts_os[0]
    specs = _rule_records(ctx)[0].input_contexts
    assert [s.co_created_shared for s in specs] == [(SHARED_CTX,)]


def test_a_shared_boundary_context_with_an_unresolved_marker_still_skips(
    _stub_lcm, spy
):
    """The same refusal on the shared route, asserted separately because the
    two routes reach the resolvability test through different functions
    (`_resolve_process_graph` vs `_resolve_shared_process_context`) and a fix
    to one has twice in this feature's history left the other behind."""
    marker = _TargetObj(WORD_BDRY, "PhBdryMarker")
    shared = _phon_data_owned(SHARED_CTX, "PhSimpleContextBdry", marker)
    contexts_os = _Seq()

    new_entry, dropped, _ctx = _walk(
        _shared_ctx_rule(shared), spy, destination=(),
        contexts_os=contexts_os)

    assert new_entry.LexemeFormOA is None
    assert list(contexts_os) == []
    assert len(dropped) == 1
    reason = " ".join(dropped[0].reason.split())
    assert "boundary marker" in reason
    assert "co-creating the context would produce one that matches nothing" \
        in reason


def test_a_shared_boundary_context_already_present_is_not_co_created_twice(
    _stub_lcm, spy
):
    """SC-008, on the class T107 admitted. Identity is tried first, so run 2
    finds what run 1 built and `ContextsOS` does not grow once per run -- the
    duplication this feature exists to remove, which its own fix must not
    reintroduce through a new class."""
    marker = _TargetObj(WORD_BDRY, "PhBdryMarker")
    shared = _phon_data_owned(SHARED_CTX, "PhSimpleContextBdry", marker)
    already_there = _TargetObj(SHARED_CTX, "PhSimpleContextBdry")
    contexts_os = _Seq()

    new_entry, dropped, _ctx = _walk(
        _shared_ctx_rule(shared), spy,
        destination=(marker, already_there), contexts_os=contexts_os)

    assert dropped == []
    assert list(contexts_os) == []
    assert new_entry.LexemeFormOA.InputOS[0].MembersRS[0] is already_there


def test_a_boundary_context_owned_by_a_phonological_rule_is_not_co_created(
    _stub_lcm, spy
):
    """The one of Ejagham's ten this task does NOT claim.

    Of the 10 `PhSimpleContextBdry` in that source, 8 are owned by a
    `MoAffixProcess` and 1 by `PhPhonData` -- both routes above -- and 1 is
    owned by a `PhSegRuleRHS`, i.e. by a PHONOLOGICAL rule. That is 037's
    successor's territory, not US5's, and the narrowing in
    `_process_shared_context_owner_is_phon_data` is what keeps it there.
    Asserted so the census delta after this task can be accounted for
    exactly rather than approximately.
    """
    marker = _TargetObj(WORD_BDRY, "PhBdryMarker")
    elsewhere = _Member(
        "PhSimpleContextBdry", SHARED_CTX,
        Owner=_TargetObj("owner-rhs", "PhSegRuleRHS"),
        FeatureStructureRA=marker)
    contexts_os = _Seq()

    new_entry, dropped, _ctx = _walk(
        _shared_ctx_rule(elsewhere), spy, destination=(marker,),
        contexts_os=contexts_os)

    assert new_entry.LexemeFormOA is None
    assert list(contexts_os) == []
    assert len(dropped) == 1
    assert "nor a PhPhonData.ContextsOS context this engine can co-create" \
        in " ".join(dropped[0].reason.split())


def test_the_co_created_context_reaches_the_run_report_json(_stub_lcm, spy):
    """T107 -- THE SC-010 GAP T076 LEFT, and T107 found the hard way.

    T076 put `co_created_shared` on `ProcessContextSpec` so that "a write into
    a shared, project-level collection made as a side effect of transferring a
    lexical entry" would not be a silent write, and asserted it on the
    IN-MEMORY record only (`test_the_co_created_context_is_reported_on_the_
    input_spec` above). `report._process_rule_json` never emitted the field,
    so the claim was true of the object and false of the artifact anyone
    reads.

    It cost T107 its own evidence: the live Ejagham run cannot say whether the
    shared boundary context was co-created there or brought across by the
    phonological-rule path, because BOTH write `PhPhonData.ContextsOS` and the
    only field that distinguishes them was dropped on the way out.

    Asserted through the real serializer, both ways -- a co-creating rule
    lists the GUID, a rule that co-creates nothing emits an empty list rather
    than omitting the key, because "created nothing" is the reading that makes
    a non-empty list mean anything.
    """
    from gramtrans.Lib.models import ProcessContextSpec, ProcessRuleTransferRecord
    from gramtrans.Lib.report import _process_rule_json

    payload = _process_rule_json(ProcessRuleTransferRecord(
        source_guid="rule-1", reproduced=True, target_guid="rule-1",
        input_contexts=(
            ProcessContextSpec(
                context_class="PhSequenceContext", index=0,
                co_created_shared=(SHARED_CTX,)),
            ProcessContextSpec(context_class="PhVariable", index=1),
        ),
    ))
    assert [c["co_created_shared"] for c in payload["input_contexts"]] == [
        [SHARED_CTX], []]


def test_the_referent_check_is_derived_from_the_referent_kind_map(_stub_lcm):
    """The structural guard T107 added, and the bug it forecloses.

    `_PROCESS_SIMPLE_CONTEXT_CLASSES` is DERIVED from
    `_PROCESS_CONTEXT_REFERENT_KIND` rather than spelled a second time, so a
    class cannot be given a factory without also being given the
    resolvability check. Before T107 the check was an inline
    `("PhSimpleContextSeg", "PhSimpleContextNC")` tuple; admitting a third
    class to `_PROCESS_INPUT_FACTORIES` and forgetting that tuple would have
    created contexts with null referents and called it a successful transfer.
    """
    assert (categories._PROCESS_SIMPLE_CONTEXT_CLASSES
            == frozenset(categories._PROCESS_CONTEXT_REFERENT_KIND))
    # Every context class with a referent kind has a factory, and vice versa:
    # a kind with no factory can never be built, and a factory with no kind
    # would skip the check.
    for name in categories._PROCESS_SIMPLE_CONTEXT_CLASSES:
        assert name in categories._PROCESS_INPUT_FACTORIES, name
        assert name not in categories._PROCESS_UNEXERCISED_CLASSES, name


def test_a_destination_with_no_contexts_os_reports_rather_than_raises(
    _stub_lcm, spy
):
    """Fail-soft, and it is not politeness. A crash here would replace a
    REPORTED loss with an unreported one -- the run would die mid-entry
    instead of skipping one rule with a reason -- which is strictly worse
    under Principle I."""
    referent = _TargetObj(DEST_PHONEME, "PhPhoneme")
    shared = _phon_data_owned(SHARED_CTX, "PhSimpleContextSeg", referent)

    new_entry, dropped, _ctx = _walk(
        _shared_ctx_rule(shared), spy, destination=(referent,),
        contexts_os=None)          # no PhPhonData on the destination at all

    assert new_entry.LexemeFormOA is None
    assert len(dropped) == 1
    assert "ContextsOS" in dropped[0].reason


# --- T076: the two registered closure producers ----------------------------

def test_the_process_rule_producers_are_narrow_and_see_shared_contexts(
    _stub_lcm
):
    """The producers registered under `PROCESS_RULE_TO_PHONEME` and
    `PROCESS_RULE_TO_NATURAL_CLASS`.

    NARROW is asserted in both directions -- each returns only its own far
    category -- because a producer that leaked the other's edges would make
    one row's `verified_by` cover two relationships, the substitution FR-018
    exists to prevent and the reason T067 split the composite at all.

    The SHARED context is in this fixture on purpose: the closure question is
    what must exist for the rule to be rebuildable, and that does not depend
    on whether the context holding the pointer is owned by the rule or by
    `PhPhonData`. A producer that walked only `InputOS` would miss the
    referent of every condition-4 rule -- the 6 this task is about.
    """
    from gramtrans.Lib.models import GrammarCategory

    own_nc = _Member("PhSimpleContextNC", "ctx-nc-own",
                     FeatureStructureRA=_TargetObj(DEST_NC, "PhNCSegments"),
                     PlusConstrRS=[], MinusConstrRS=[])
    shared_seg = _phon_data_owned(
        SHARED_CTX, "PhSimpleContextSeg",
        _TargetObj(DEST_PHONEME, "PhPhoneme"))
    seq = _Member("PhSequenceContext", "ctx-seq-prod",
                  MembersRS=[own_nc, shared_seg])
    inserted = "9999210f-0000-0000-0000-00000000dddd"
    rule = _Rule("rule-prod-0001", inputs=[own_nc, seq],
                 outputs=[_Member("MoInsertPhones", "out-prod",
                                  ContentRS=[_TargetObj(inserted,
                                                        "PhPhoneme")])])
    entry = _Entry("aaaaaaaa-0000-0000-0000-0000000000c6", lexeme_form=rule)

    phonemes = categories.affixes_process_rule_phoneme_dependencies(entry)
    classes = categories.affixes_process_rule_natural_class_dependencies(entry)

    assert set(phonemes) == {
        (GrammarCategory.PHONEMES, DEST_PHONEME),   # via the SHARED context
        (GrammarCategory.PHONEMES, inserted),       # via MoInsertPhones
    }
    assert set(classes) == {(GrammarCategory.NATURAL_CLASSES, DEST_NC)}
    assert all(ref[0] is GrammarCategory.PHONEMES for ref in phonemes)
    assert all(ref[0] is GrammarCategory.NATURAL_CLASSES for ref in classes)


def test_the_process_rule_producers_are_silent_on_an_entry_with_no_rules(
    _stub_lcm
):
    """`Ejagham Mini` holds zero `MoAffixProcess` rules and the audit reports
    NO_DATA there rather than CONFIRMED. An entry with an ordinary allomorph
    must contribute no edges at all -- otherwise the closure would pull in
    phonemes for a rule that does not exist, and every AFFIXES piece in a
    corpus like that would acquire dependencies it has no use for."""
    entry = _Entry("aaaaaaaa-0000-0000-0000-0000000000c7",
                   lexeme_form=_Form("plain-allo", "MoAffixAllomorph"))

    assert categories.affixes_process_rule_phoneme_dependencies(entry) == ()
    assert categories.affixes_process_rule_natural_class_dependencies(
        entry) == ()


@pytest.mark.parametrize("unexercised", [
    "MoModifyFromInput", "MoInsertNC", "PhIterationContext",
])
def test_an_unexercised_class_skips_rather_than_guesses(
    _stub_lcm, spy, unexercised
):
    """No corpus exercises these inside a rule, so none can tell a correct
    implementation from a plausible one -- they ship behind the skip, and the
    reason says WHICH class, not "unknown class".

    **T107 (2026-08-25) FIXED THE REASON STRING and shrank this parametrize
    from four classes to three.** `PhSimpleContextBdry` left
    `_PROCESS_UNEXERCISED_CLASSES` for a create path, so it is asserted
    elsewhere now. The string it left behind said "a class with zero instances
    in any sanctioned corpus", which T078 pinned as false of the boundary
    context (10 / 13 / 24 in source) and which is **also false of
    `PhIterationContext`**: Mbugwe holds 11 in `ContextsOS` and a live run
    created 9 more under transferred phonological rules. So the fix was not
    "delete the one false case" -- it was correcting the CLAIM to the one every
    remaining member satisfies, which is per-RULE, not per-project: no
    `MoAffixProcess` in any sanctioned corpus uses any of these three."""
    member = _Member(unexercised, "member-unexercised-0001")
    is_input = unexercised == "PhIterationContext"
    rule = _Rule(
        "rule-unexercised-0001",
        inputs=[member] if is_input else [_Member("PhVariable", "v-1")],
        outputs=[] if is_input else [member],
    )
    entry = _Entry("aaaaaaaa-0000-0000-0000-000000000016", lexeme_form=rule)

    new_entry, dropped, _ctx = _walk(entry, spy, destination=())

    assert new_entry.LexemeFormOA is None
    assert not spy.reached_an_allomorph_factory
    assert len(dropped) == 1
    assert unexercised in dropped[0].reason
    # The corrected claim, asserted as a string because it is what the user
    # reads. "zero instances" was the old wording and is refused: it is false
    # of PhIterationContext at the project level, and a reason that overstates
    # its own evidence is the defect T078 pinned.
    assert "no affix process rule in any sanctioned corpus uses" in \
        dropped[0].reason
    assert "zero instances" not in dropped[0].reason


def test_a_feature_constraint_skips_the_rule(_stub_lcm, spy):
    """`PhFeatureConstraint` has zero live refs and ties into the feature
    system; a non-empty PlusConstrRS/MinusConstrRS is not silently ignored."""
    ctx_nc = _Member("PhSimpleContextNC", "ctx-nc-0011",
                     FeatureStructureRA=_TargetObj(DEST_NC, "PhNCSegments"),
                     PlusConstrRS=[_TargetObj("fc-1", "PhFeatureConstraint")],
                     MinusConstrRS=[])
    rule = _Rule("rule-fc-0001", inputs=[ctx_nc],
                 outputs=[_Member("MoCopyFromInput", "out-0012",
                                  ContentRA=ctx_nc)])
    entry = _Entry("aaaaaaaa-0000-0000-0000-000000000017", lexeme_form=rule)

    new_entry, dropped, _ctx = _walk(
        entry, spy, destination=(_TargetObj(DEST_NC, "PhNCSegments"),))

    assert new_entry.LexemeFormOA is None
    assert len(dropped) == 1
    assert "PlusConstrRS" in dropped[0].reason


# --- T054/FR-024: references resolve to the destination, never to duplicates

def test_an_unresolvable_phoneme_skips_the_rule(_stub_lcm, spy):
    """FR-024. A rule whose inserted phoneme is absent from the destination
    cannot be rebuilt faithfully -- and inserting nothing in its place is
    exactly the empty-content shell SC-006 fails."""
    rule, _destination = _reproducible_rule()
    entry = _Entry("aaaaaaaa-0000-0000-0000-000000000018", lexeme_form=rule)

    new_entry, dropped, _ctx = _walk(
        entry, spy, destination=(_TargetObj(DEST_NC, "PhNCSegments"),))

    assert new_entry.LexemeFormOA is None
    assert len(dropped) == 1
    assert DEST_PHONEME in dropped[0].reason
    assert "MoInsertPhones" in dropped[0].reason


def test_a_context_naming_no_referent_at_all_skips_the_rule(_stub_lcm, spy):
    ctx_seg = _Member("PhSimpleContextSeg", "ctx-seg-0013",
                      FeatureStructureRA=None)
    rule = _Rule("rule-noref-0001", inputs=[ctx_seg],
                 outputs=[_Member("MoCopyFromInput", "out-0014",
                                  ContentRA=ctx_seg)])
    entry = _Entry("aaaaaaaa-0000-0000-0000-000000000019", lexeme_form=rule)

    new_entry, dropped, _ctx = _walk(entry, spy, destination=())

    assert new_entry.LexemeFormOA is None
    assert "names no phoneme" in dropped[0].reason


def test_a_copy_step_naming_a_foreign_input_skips_the_rule(_stub_lcm, spy):
    """`MoCopyFromInput.ContentRA` must name an input member of the SAME rule.
    A copy of something this rule does not own would copy nothing."""
    foreign = _Member("PhVariable", "foreign-0015")
    rule = _Rule("rule-foreign-0001",
                 inputs=[_Member("PhVariable", "v-2")],
                 outputs=[_Member("MoCopyFromInput", "out-0016",
                                  ContentRA=foreign)])
    entry = _Entry("aaaaaaaa-0000-0000-0000-00000000001a", lexeme_form=rule)

    new_entry, dropped, _ctx = _walk(entry, spy, destination=())

    assert new_entry.LexemeFormOA is None
    assert "foreign-0015" in dropped[0].reason


# --- T056: the skip contract ----------------------------------------------

def test_a_skipped_rule_creates_nothing_at_all(_stub_lcm, spy):
    """FR-025's first clause. Not an allomorph, not a partially populated
    MoAffixProcess, not a shell: nothing."""
    rule, _destination = _reproducible_rule()
    entry = _Entry("aaaaaaaa-0000-0000-0000-00000000001b", lexeme_form=rule)

    new_entry, dropped, _ctx = _walk(entry, spy, destination=())

    assert new_entry.LexemeFormOA is None
    assert list(new_entry.AlternateFormsOS) == []
    assert spy.classes_created == []
    assert not spy.reached_an_allomorph_factory
    assert len(dropped) == 1


def test_the_skip_record_carries_the_contract_fields(_stub_lcm, spy):
    """The create-path contract section 5 fixes every field, because the
    report line has to be actionable by a person who was not in the run."""
    rule, _destination = _reproducible_rule()
    entry = _Entry("aaaaaaaa-0000-0000-0000-00000000001c", alternates=[rule])

    _new_entry, dropped, _ctx = _walk(entry, spy, destination=())

    rec = dropped[0]
    assert rec.owner_kind == "LexEntry"
    assert rec.owner_guid == "aaaaaaaa-0000-0000-0000-00000000001c"
    assert rec.field_name == "AlternateFormsOS"
    assert rec.item_name == "MoAffixProcess"
    assert rec.item_guid == "19bab2cf-6580-45db-b600-58857c4a6e65"
    assert rec.reason.strip()


def test_a_skipped_rule_leaves_the_entry_partial(_stub_lcm, spy):
    """T056 asks for `FidelityStatus.PARTIAL` on the owning entry. It is
    DERIVED from the record's `owner_guid` rather than set by hand, so this
    proves the derivation actually reaches the entry -- a second, hand-set
    marking would be a parallel source of truth that could disagree."""
    from gramtrans.Lib.models import FidelityStatus

    rule, _destination = _reproducible_rule()
    entry = _Entry("aaaaaaaa-0000-0000-0000-00000000001d", lexeme_form=rule)

    _new_entry, dropped, _ctx = _walk(entry, spy, destination=())

    fidelity = categories.compute_fidelity_by_guid(dropped)
    assert fidelity["aaaaaaaa-0000-0000-0000-00000000001d"] is (
        FidelityStatus.PARTIAL)


def test_one_skipped_rule_yields_one_record_however_often_it_is_walked(
    _stub_lcm, spy
):
    """Dedup key is `(owner_guid, field_name, item_guid)`, so the reason is
    diagnostic rather than identity."""
    rule, _destination = _reproducible_rule()
    entry = _Entry("aaaaaaaa-0000-0000-0000-00000000001e", lexeme_form=rule)
    new_entry = SimpleNamespace(LexemeFormOA=None, AlternateFormsOS=_Seq())
    ctx, _target = _ctx_and_target(spy, ())
    dropped: list = []
    for _ in range(3):
        categories._walk_entry_allomorphs(
            entry, new_entry, ctx, tag=None, identity_remap={},
            dropped=dropped)
    assert len(dropped) == 1


# --- Principle III: Preview reaches the same verdict, without writing ------

def test_preview_and_move_agree_on_a_blocked_rule(_stub_lcm, spy):
    """Preview runs the SAME resolution pass -- `_resolve_process_graph`
    writes nothing -- so it cannot disagree with Move about which rules a run
    will skip or about why."""
    rule, _destination = _reproducible_rule()
    entry = _Entry("aaaaaaaa-0000-0000-0000-00000000001f", lexeme_form=rule)

    _new_entry, move_dropped, _mctx = _walk(entry, spy, destination=())

    preview_dropped: list = []
    ctx, _target = _ctx_and_target(spy, ())
    ctx._dropped = preview_dropped
    categories._plan_entry_reference_decisions(entry, ctx, target=object())

    assert [(r.owner_guid, r.field_name, r.item_guid, r.item_name, r.reason)
            for r in preview_dropped] == [
        (r.owner_guid, r.field_name, r.item_guid, r.item_name, r.reason)
        for r in move_dropped]


def test_preview_writes_nothing_for_a_reproducible_rule(_stub_lcm, spy):
    """Preview must not create the rule it is only planning."""
    rule, destination = _reproducible_rule()
    entry = _Entry("aaaaaaaa-0000-0000-0000-000000000020", lexeme_form=rule)

    ctx, _target = _ctx_and_target(spy, destination)
    dropped: list = []
    ctx._dropped = dropped
    categories._plan_entry_reference_decisions(entry, ctx, target=object())

    assert spy.classes_created == []
    assert dropped == []


def test_a_create_that_fails_after_pass_one_leaves_nothing_behind(
    _stub_lcm, spy, monkeypatch
):
    """The residual path pass 1 is designed to make unreachable.

    Pass 1 resolves the whole graph before the first write, so a rule can
    normally only be skipped BEFORE anything exists. This forces the other
    case -- a factory that fails after pass 1 approved the rule -- and proves
    the shell is detached and nothing is left on the entry. The reason says
    "rolled back", so a reader can tell this apart from a rule that was never
    started.

    It is reachable in practice: disabling pass 1's condition-4 check makes
    pass 2's own guard fire on the live-shaped fixture, which is how this path
    was first exercised.
    """
    real_create = _cat_mod.create_with_guid
    calls = {"n": 0}

    def _fails_on_the_second_create(factory, src_guid, kind):
        calls["n"] += 1
        if calls["n"] == 2:
            return None
        return real_create(factory, src_guid, kind)

    monkeypatch.setattr(
        _cat_mod, "create_with_guid", _fails_on_the_second_create)

    rule, destination = _reproducible_rule()
    entry = _Entry("aaaaaaaa-0000-0000-0000-000000000021", lexeme_form=rule)

    new_entry, dropped, ctx = _walk(entry, spy, destination)

    assert new_entry.LexemeFormOA is None
    assert list(new_entry.AlternateFormsOS) == []
    assert len(dropped) == 1
    assert "rolled back" in dropped[0].reason
    assert dropped[0].item_name == "MoAffixProcess"
    records = _rule_records(ctx)
    assert len(records) == 1 and records[0].reproduced is False


# ============================================================================
# T061 -- residue and the inherited IMoForm half
# ============================================================================

def test_a_reproduced_rule_is_residue_tagged(_stub_lcm, spy, monkeypatch):
    """`MoAffixProcess` was ALREADY in `residue.CARRIER_A_CLASSES` (:43), so
    T061's confirmation stands: no new carrier. What was missing was the
    CALL -- a reproduced rule carrying no GT tag would be invisible to every
    residue-based audit while the allomorph beside it was tagged."""
    tagged = []
    monkeypatch.setattr(
        _residue_mod, "apply_residue",
        lambda obj, ws, tag, class_name=None: tagged.append(obj))

    rule, destination = _reproducible_rule()
    entry = _Entry("aaaaaaaa-0000-0000-0000-000000000022", lexeme_form=rule)

    new_entry, _dropped, _ctx = _walk(entry, spy, destination)

    assert tagged == [new_entry.LexemeFormOA]


def test_the_carrier_table_already_covers_the_class(_stub_lcm):
    """The confirmation itself, executable rather than asserted in prose."""
    from gramtrans.Lib import residue

    assert "MoAffixProcess" in residue.CARRIER_A_CLASSES
    assert residue.class_uses_carrier_a("MoAffixProcess")


def test_the_inherited_form_fields_are_copied(_stub_lcm, spy):
    """A rule keeps the IMoForm half it shares with an allomorph."""
    rule, destination = _reproducible_rule()
    entry = _Entry("aaaaaaaa-0000-0000-0000-000000000023", lexeme_form=rule)

    new_entry, dropped, ctx = _walk(entry, spy, destination)

    assert dropped == []
    assert ctx.target_handle.Allomorphs.applied
    assert new_entry.LexemeFormOA.Form == {"vernacular": "src-form"}


def test_a_refused_property_copy_is_reported_not_swallowed(_stub_lcm, spy):
    """flexicon's AllomorphOperations manages only the two allomorph factories
    and raises on any other ClassName, so this leg may legitimately be
    unavailable for a rule.

    That is a FIELD-level loss and is reported as one. It is deliberately NOT
    escalated into a rule-level skip: the Input/Output content -- what makes
    the object a rule at all -- has already transferred, and discarding it to
    punish a missing Form would destroy more than it protects.
    """
    rule, destination = _reproducible_rule()
    entry = _Entry("aaaaaaaa-0000-0000-0000-000000000024", lexeme_form=rule)

    new_entry, dropped, ctx = _walk(
        entry, spy, destination, allomorph_ops_refuses=True)

    # The rule still arrived, with its content.
    new_rule = new_entry.LexemeFormOA
    assert new_rule.ClassName == "MoAffixProcess"
    assert len(new_rule.InputOS) == 2 and len(new_rule.OutputOS) == 3
    assert _rule_records(ctx)[0].reproduced is True

    # ...and the loss reached the report rather than a log line.
    assert len(dropped) == 1
    assert dropped[0].owner_kind == "MoAffixProcess"
    assert dropped[0].field_name == "Form"
    assert "AllomorphOperations" in dropped[0].reason


# ============================================================================
# Preview resolves against what the run WILL create, not only what is there
# ============================================================================
#
# Found by the live Mbugwe run, not by inspection: Preview looks before
# anything is written, so a phoneme this transfer is about to create is absent
# when Preview asks. Resolving against the destination alone made Preview
# predict 15 lost rules where Move then lost 6 and rebuilt 9. A Preview that
# overstates the loss is not a safe error -- it is why a person declines a
# transfer that would have worked.

from gramtrans.Lib.models import GrammarCategory


def _selection(**flags):
    return SimpleNamespace(categories={
        GrammarCategory.PHONEMES: flags.get("phonemes", True),
        GrammarCategory.NATURAL_CLASSES: flags.get("natural_classes", True),
    })


def test_preview_does_not_predict_a_loss_the_run_will_not_have(
    _stub_lcm, spy
):
    """The destination is EMPTY -- as it is at plan time -- and the run is
    transferring phonemes and natural classes. Preview must not report the
    rule as lost."""
    rule, _destination = _reproducible_rule()
    entry = _Entry("aaaaaaaa-0000-0000-0000-000000000030", lexeme_form=rule)

    ctx, _target = _ctx_and_target(spy, destination=())
    dropped: list = []
    ctx._dropped = dropped
    ctx._selection = _selection()

    categories._plan_entry_reference_decisions(entry, ctx, target=object())

    assert dropped == []
    assert not _rule_records(ctx)


def test_a_deselected_category_is_still_predicted_as_a_loss(_stub_lcm, spy):
    """The predicate is the SELECTION, not mere presence in the source.

    Under-reporting is the failure this must not commit: a rule whose phoneme
    is in a category the user deselected really will be lost, and Preview is
    where that has to be visible.
    """
    rule, _destination = _reproducible_rule()
    entry = _Entry("aaaaaaaa-0000-0000-0000-000000000031", lexeme_form=rule)

    ctx, _target = _ctx_and_target(spy, destination=())
    dropped: list = []
    ctx._dropped = dropped
    ctx._selection = _selection(phonemes=False, natural_classes=False)

    categories._plan_entry_reference_decisions(entry, ctx, target=object())

    assert len(dropped) == 1
    assert "absent from the destination" in dropped[0].reason


def test_a_shared_context_is_predicted_as_a_loss_whatever_is_selected(
    _stub_lcm, spy
):
    """Condition 4 is not softened by the plan-time leg. No category creates a
    `PhSimpleContext*` owned by `PhPhonData.ContextsOS`, so nothing this run
    does will bring it across -- which is exactly why Phase 7's closure is a
    separate phase."""
    shared = _TargetObj(SHARED_CTX, "PhSimpleContextSeg")
    seq = _Member("PhSequenceContext", "ctx-seq-0030", MembersRS=[shared])
    rule = _Rule("rule-seq-0030", inputs=[seq],
                 outputs=[_Member("MoCopyFromInput", "out-0030",
                                  ContentRA=seq)])
    entry = _Entry("aaaaaaaa-0000-0000-0000-000000000032", lexeme_form=rule)

    ctx, _target = _ctx_and_target(spy, destination=())
    dropped: list = []
    ctx._dropped = dropped
    ctx._selection = _selection()

    categories._plan_entry_reference_decisions(entry, ctx, target=object())

    assert len(dropped) == 1
    assert "PhPhonData.ContextsOS" in dropped[0].reason


def test_move_never_takes_the_plan_time_leg(_stub_lcm, spy):
    """Move's verdict stays decided entirely by what is really there. If the
    plan-time leg leaked into Move, a rule would be created referencing a
    phoneme that does not exist."""
    rule, _destination = _reproducible_rule()
    entry = _Entry("aaaaaaaa-0000-0000-0000-000000000033", lexeme_form=rule)

    new_entry = SimpleNamespace(LexemeFormOA=None, AlternateFormsOS=_Seq())
    ctx, _target = _ctx_and_target(spy, destination=())
    ctx._selection = _selection()
    dropped: list = []
    categories._walk_entry_allomorphs(
        entry, new_entry, ctx, tag=None, identity_remap={}, dropped=dropped)

    assert new_entry.LexemeFormOA is None
    assert len(dropped) == 1
    assert "absent from the destination" in dropped[0].reason


# ============================================================================
# One record per rule: the run's outcome beats the plan's prediction
# ============================================================================

def test_the_run_record_replaces_the_plan_prediction():
    """Also found live: plan and run records are NOT disjoint, and
    concatenating them said the same loss happened twice.

    The run wins because it is the outcome and the plan is a prediction -- not
    a tie-break, the only direction that can be right. Measured on Mbugwe, the
    plan named 15 rules unreproducible where the run rebuilt 9 of them; the
    other direction would report those 9 as lost while the destination held
    them.
    """
    from gramtrans.Lib.report import _merge_process_rules
    from gramtrans.Lib.models import ProcessRuleTransferRecord

    predicted = ProcessRuleTransferRecord(
        source_guid="rule-1", reproduced=False,
        not_reproducible_reason="phoneme absent from the destination")
    actual = ProcessRuleTransferRecord(
        source_guid="rule-1", reproduced=True, target_guid="rule-1")

    merged = _merge_process_rules((predicted,), (actual,))

    assert len(merged) == 1
    assert merged[0].reproduced is True


def test_a_rule_the_run_never_reached_keeps_its_plan_record():
    """A Preview-only report, or a run that aborted, must not lose what the
    plan already knew."""
    from gramtrans.Lib.report import _merge_process_rules
    from gramtrans.Lib.models import ProcessRuleTransferRecord

    only_planned = ProcessRuleTransferRecord(
        source_guid="rule-2", reproduced=False,
        not_reproducible_reason="shared context absent")

    merged = _merge_process_rules((only_planned,), ())

    assert [r.source_guid for r in merged] == ["rule-2"]


def test_merging_preserves_order_and_does_not_lose_unkeyed_records():
    from gramtrans.Lib.report import _merge_process_rules
    from gramtrans.Lib.models import ProcessRuleTransferRecord

    a = ProcessRuleTransferRecord(
        source_guid="a", reproduced=False, not_reproducible_reason="x")
    b = ProcessRuleTransferRecord(
        source_guid="b", reproduced=False, not_reproducible_reason="y")
    c = ProcessRuleTransferRecord(
        source_guid="c", reproduced=True, target_guid="c")

    merged = _merge_process_rules((a, b), (c,))

    assert [r.source_guid for r in merged] == ["a", "b", "c"]
