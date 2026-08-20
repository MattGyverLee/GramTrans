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
    "MoAffixProcess",
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
    """What a spied factory hands back: an object that knows its own class."""

    def __init__(self, guid: str, class_name: str) -> None:
        self.guid = guid
        self.ClassName = class_name


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


def _ctx_and_target(spy=None):
    def _get_factory(iface):
        if spy is not None:
            spy.factories_requested.append(getattr(iface, "name", repr(iface)))
        return iface

    target = SimpleNamespace(
        Cache=SimpleNamespace(DefaultAnalWs=1),
        GetFactory=_get_factory,
    )
    ctx = SimpleNamespace(
        target_handle=target,
        source_handle=SimpleNamespace(),
        _ws_map=None,
    )
    return ctx, target


def _walk(entry, spy):
    """Run the Move-mode walk over `entry`, returning its dropped records."""
    new_entry = SimpleNamespace(LexemeFormOA=None, AlternateFormsOS=_Seq())
    ctx, _target = _ctx_and_target(spy)
    dropped: list = []
    categories._walk_entry_allomorphs(
        entry, new_entry, ctx, tag=None, identity_remap={}, dropped=dropped
    )
    return new_entry, dropped


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

    new_entry, dropped = _walk(entry, failing_create)

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

    new_entry, dropped = _walk(entry, failing_create)

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

    new_entry, dropped = _walk(entry, spy)

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

    _new_entry, move_dropped = _walk(entry, spy)

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

    new_entry, dropped = _walk(entry, failing_create)

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

    The whitelist is read at RUN TIME, so this covers `MoAffixProcess` the
    moment T057 adds it to `known`. Adding it while
    `_walk_entry_allomorphs._mk` still routes every non-stem subclass to
    `IMoAffixAllomorphFactory` reinstates the exact historic defect: this test
    then fails on the created class, which is why T057 and T058 must land in
    one change.
    """
    form = _Form("11111111-0000-0000-0000-00000000000b", class_name)
    entry = _Entry("aaaaaaaa-0000-0000-0000-00000000000c", lexeme_form=form)

    new_entry, dropped = _walk(entry, spy)

    dispatched = categories._dispatch_allomorph_subclass(class_name)
    if dispatched is None:
        # Refused: nothing created, and the refusal is reported.
        assert spy.classes_created == []
        assert new_entry.LexemeFormOA is None
        assert len(dropped) == 1
        return

    # Accepted: whatever was created is of the SOURCE's class, and the factory
    # asked for is the one that builds that class.
    assert spy.classes_created == [class_name], (
        f"source {class_name} was created as {spy.classes_created} -- an "
        "object may never be created as a different kind (FR-025, SC-010)"
    )
    assert spy.factories_requested == [f"I{class_name}Factory"]
    assert new_entry.LexemeFormOA is not None
    assert new_entry.LexemeFormOA.ClassName == class_name
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
