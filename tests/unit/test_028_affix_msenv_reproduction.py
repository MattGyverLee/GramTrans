"""Unit tests for feature 028 (Affix-Allomorph Morphosyntax Fidelity):
reproduction of three of the four `MoAffixAllomorph`/`MoAffixForm`
morphosyntactic-environment field families —

- `MsEnvPartOfSpeechRA` (US1, POS reference),
- `InflectionClassesRC` (US2, inflection-class references, read from the
  `IMoAffixForm` parent),
- `PositionRS` (US4, ordered infix-position environment references).

(`MsEnvFeaturesOA` — US3, owned feature structure — lives in
`test_028_msenv_feature_struct.py`.)

See:
- specs/028-affix-allomorph-morphosyntax/spec.md (US1/US2/US4/US5)
- specs/028-affix-allomorph-morphosyntax/contracts/affix-msenv-reproduction.md
- specs/028-affix-allomorph-morphosyntax/data-model.md

T002 SCAFFOLD (Phase 1): import-smoke only — assert the module under test and
its 028 dispatch seam import cleanly. The RED-before-GREEN tests are authored
per user story in Phase 3 (US1, T006), Phase 4 (US2, T008), Phase 6 (US4, T012),
and Phase 7 (US5, T014).
"""

from gramtrans.Lib import owned
from gramtrans.Lib.models import ReferenceAction


def test_028_dispatch_seam_present():
    """T005 adds the reproduce leg (`reproduce_moaffix_msenv_data`) and its
    read-only Preview twin (`_plan_moaffix_msenv_decisions`). Import-smoke: the
    module and both dispatch entry points exist and are callable."""
    assert callable(owned.reproduce_moaffix_msenv_data)
    assert callable(owned._plan_moaffix_msenv_decisions)


# ============================================================================
# Shared duck-typed fakes for the POS-ref (US1) and inflection-class (US2) legs.
#
# These model the minimal live surface the reproduce legs touch:
#   - a target project exposing `POS.GetAll(recursive=True)` over a MUTABLE
#     registry (so a POS created mid-run becomes resolvable to a later
#     reference -- the dedup path), `Cache.LangProject.PartsOfSpeechOA`, and a
#     `GetFactory(...)`-served POS factory whose `Create(guid, owner)` registers
#     the new POS (mirroring the real 2-arg overload that auto-owns);
#   - source/target parts of speech carrying `ClassName == "PartOfSpeech"` so
#     the host-free sub-POS detection (owner-is-a-POS) works without a live cast.
# The affix allomorph carries `ClassName == "MoAffixAllomorph"` so
# `owned._is_moaffix_allomorph` gates it in.
# ============================================================================


class _FakeGuid:
    def __init__(self, guid):
        self.Guid = guid
        self.guid = guid


class _FakeAddList(list):
    """List that also exposes the LCM-direct `.Add()` used to populate
    read-only-through-wrapper collections (InflectionClassesRC/OC, PositionRS,
    SubPossibilitiesOS)."""

    def Add(self, item):
        self.append(item)


class _FakePOS(_FakeGuid):
    ClassName = "PartOfSpeech"

    def __init__(self, guid, owner=None, inflection_classes=()):
        super().__init__(guid)
        self.Owner = owner
        self.SubPossibilitiesOS = _FakeAddList()
        self.InflectionClassesOC = _FakeAddList(inflection_classes)


class _FakeInflClass(_FakeGuid):
    ClassName = "MoInflClass"

    def __init__(self, guid, owner=None):
        super().__init__(guid)
        self.Owner = owner
        self.SubclassesOC = _FakeAddList()


class _FakePOSNamespace:
    """`project.POS.GetAll(recursive=True)` over a shared mutable registry."""

    def __init__(self, registry):
        self._registry = registry

    def GetAll(self, recursive=False):
        return list(self._registry)


class _FakePOSFactory:
    """`IPartOfSpeechFactory` double. The real 2-arg `Create(Guid, owner)`
    overload auto-owns the new POS into its parent/list; this fake mirrors that
    by registering the new POS into the target's recursive POS registry (and
    under the parent's `SubPossibilitiesOS` when the owner is a POS)."""

    def __init__(self, registry):
        self._registry = registry
        self.create_calls = []

    def Create(self, guid, owner=None):
        self.create_calls.append((str(guid), owner))
        parent = owner if isinstance(owner, _FakePOS) else None
        new = _FakePOS(str(guid), owner=parent)
        self._registry.append(new)
        if parent is not None:
            parent.SubPossibilitiesOS.Add(new)
        return new


class _FakeInflClassFactory:
    """`IMoInflClassFactory` double -- the 1-arg `Create(Guid)` overload
    (caller `.Add()`s it under the owning POS's InflectionClassesOC / parent
    class's SubclassesOC)."""

    def __init__(self):
        self.create_calls = []

    def Create(self, guid):
        self.create_calls.append(str(guid))
        return _FakeInflClass(str(guid))


class _FakePossibilityList:
    def __init__(self):
        self.PossibilitiesOS = []


class _FakeLangProject:
    def __init__(self):
        self.PartsOfSpeechOA = _FakePossibilityList()


class _FakeCache:
    def __init__(self):
        self.LangProject = _FakeLangProject()
        self.DefaultAnalWs = 0


class _FakeTarget:
    def __init__(self, pos=(), factories=None):
        self._registry = list(pos)
        self.Cache = _FakeCache()
        self.POS = _FakePOSNamespace(self._registry)
        self._factories = dict(factories or {})

    def GetFactory(self, key):
        name = key if isinstance(key, str) else getattr(key, "__name__", str(key))
        if name in self._factories:
            return self._factories[name]
        raise KeyError(name)


class _FakeSource:
    """Source handle -- these legs never read the source project directly
    (they read off the source allomorph object), so this is a bare stand-in."""


class _FakeAffixAllomorph(_FakeGuid):
    ClassName = "MoAffixAllomorph"

    def __init__(self, guid, msenv_pos=None, inflection_classes=None,
                 positions=None):
        super().__init__(guid)
        self.MsEnvPartOfSpeechRA = msenv_pos
        self.InflectionClassesRC = list(inflection_classes or [])
        # PositionRS source shape (US4): a plain ordered list of env refs.
        self.PositionRS = list(positions or [])


class _FakeNewAffixAllomorph(_FakeGuid):
    ClassName = "MoAffixAllomorph"

    def __init__(self, guid, msenv_pos=None, inflection_classes=(),
                 positions=()):
        super().__init__(guid)
        self.MsEnvPartOfSpeechRA = msenv_pos
        self.InflectionClassesRC = _FakeAddList(inflection_classes)
        # PositionRS target shape (US4): read-only-through-wrapper RS populated
        # via LCM-direct `.Add()`.
        self.PositionRS = _FakeAddList(positions)


class _FakeCtx:
    def __init__(self, target, source=None):
        self.source_handle = source or _FakeSource()
        self.target_handle = target


_TAG = "tag-028-msenv"


def _make_target(pos=(), with_factory=True, infl_class_factory=False):
    """Build a fake target. `with_factory` adds an `IPartOfSpeechFactory`
    (bound to the target's live POS registry so a created POS resolves
    afterwards); `infl_class_factory` adds an `IMoInflClassFactory`. Returns
    `(target, pos_factory)`; the inflection-class factory (when requested) is
    reachable as `target._factories["IMoInflClassFactory"]`."""
    target = _FakeTarget(pos=pos)
    pos_factory = None
    if with_factory:
        pos_factory = _FakePOSFactory(target._registry)
        target._factories["IPartOfSpeechFactory"] = pos_factory
    if infl_class_factory:
        target._factories["IMoInflClassFactory"] = _FakeInflClassFactory()
    return target, pos_factory


# ============================================================================
# T006 (US1) -- MsEnvPartOfSpeechRA reproduction (POS reference).
# ============================================================================


def test_msenv_pos_ra_link_when_present():
    """POS already present in target (by GUID) -> the new allomorph references
    it; no POS is created; nothing dropped (G2/LINK)."""
    src_pos = _FakePOS("pos-guid-1")
    tgt_pos = _FakePOS("pos-guid-1")
    target, factory = _make_target(pos=[tgt_pos])
    src_allo = _FakeAffixAllomorph("allo-1", msenv_pos=src_pos)
    new_allo = _FakeNewAffixAllomorph("allo-1")
    ctx = _FakeCtx(target)
    dropped: list = []

    owned.reproduce_moaffix_msenv_data(
        src_allo, new_allo, ctx, _TAG, {}, dropped)

    assert new_allo.MsEnvPartOfSpeechRA is tgt_pos
    assert factory.create_calls == []
    assert dropped == []


def test_msenv_pos_ra_create_when_absent_guid_preserved():
    """POS absent from target, create infra present -> a POS is created with
    the source GUID preserved and the allomorph references it (CREATE/G3)."""
    src_pos = _FakePOS("pos-guid-new")
    target, factory = _make_target(pos=[])
    src_allo = _FakeAffixAllomorph("allo-2", msenv_pos=src_pos)
    new_allo = _FakeNewAffixAllomorph("allo-2")
    ctx = _FakeCtx(target)
    dropped: list = []

    owned.reproduce_moaffix_msenv_data(
        src_allo, new_allo, ctx, _TAG, {}, dropped)

    assert len(factory.create_calls) == 1
    assert new_allo.MsEnvPartOfSpeechRA is not None
    assert new_allo.MsEnvPartOfSpeechRA.guid == "pos-guid-new"
    assert dropped == []


def test_msenv_pos_ra_create_with_ancestor_chain():
    """A nested source POS whose parent is absent -> both the parent POS and
    the child POS are created (ancestor chain), and the allomorph references
    the child (US1 scenario 1)."""
    parent = _FakePOS("pos-parent")
    child = _FakePOS("pos-child", owner=parent)
    target, factory = _make_target(pos=[])
    src_allo = _FakeAffixAllomorph("allo-3", msenv_pos=child)
    new_allo = _FakeNewAffixAllomorph("allo-3")
    ctx = _FakeCtx(target)
    dropped: list = []

    owned.reproduce_moaffix_msenv_data(
        src_allo, new_allo, ctx, _TAG, {}, dropped)

    created = {g for g, _ in factory.create_calls}
    assert created == {"pos-parent", "pos-child"}
    assert new_allo.MsEnvPartOfSpeechRA.guid == "pos-child"
    assert dropped == []


def test_msenv_pos_ra_report_when_uncreatable():
    """POS absent and no create infra (no POS factory) -> REPORT_DROPPED with
    field_name/owner identity; the allomorph field is left unset (G1)."""
    src_pos = _FakePOS("pos-guid-missing")
    target, _ = _make_target(pos=[], with_factory=False)
    src_allo = _FakeAffixAllomorph("allo-4", msenv_pos=src_pos)
    new_allo = _FakeNewAffixAllomorph("allo-4")
    ctx = _FakeCtx(target)
    dropped: list = []

    owned.reproduce_moaffix_msenv_data(
        src_allo, new_allo, ctx, _TAG, {}, dropped)

    assert new_allo.MsEnvPartOfSpeechRA is None
    assert len(dropped) == 1
    rec = dropped[0]
    assert rec.field_name == "MsEnvPartOfSpeechRA"
    assert rec.owner_kind == "MoAffixAllomorph"
    assert rec.owner_guid == "allo-4"
    assert rec.item_guid == "pos-guid-missing"


def test_msenv_pos_ra_empty_source_does_not_blank_target():
    """Unset source MsEnvPartOfSpeechRA -> no write, and a populated target
    field is not blanked (FR-005/G2)."""
    existing = _FakePOS("pos-existing")
    target, factory = _make_target(pos=[existing])
    src_allo = _FakeAffixAllomorph("allo-5", msenv_pos=None)
    new_allo = _FakeNewAffixAllomorph("allo-5", msenv_pos=existing)
    ctx = _FakeCtx(target)
    dropped: list = []

    owned.reproduce_moaffix_msenv_data(
        src_allo, new_allo, ctx, _TAG, {}, dropped)

    assert new_allo.MsEnvPartOfSpeechRA is existing
    assert factory.create_calls == []
    assert dropped == []


def test_msenv_pos_ra_dedup_shared_pos_created_once():
    """Two allomorphs referencing the same absent POS -> the POS is created
    once (resolver_cache dedup) and both reference the same object (G4/SC-005)."""
    src_pos_a = _FakePOS("pos-shared")
    src_pos_b = _FakePOS("pos-shared")
    target, factory = _make_target(pos=[])
    resolver_cache: dict = {}
    ctx = _FakeCtx(target)
    dropped: list = []

    new_a = _FakeNewAffixAllomorph("allo-a")
    owned.reproduce_moaffix_msenv_data(
        _FakeAffixAllomorph("allo-a", msenv_pos=src_pos_a),
        new_a, ctx, _TAG, resolver_cache, dropped)
    new_b = _FakeNewAffixAllomorph("allo-b")
    owned.reproduce_moaffix_msenv_data(
        _FakeAffixAllomorph("allo-b", msenv_pos=src_pos_b),
        new_b, ctx, _TAG, resolver_cache, dropped)

    assert len(factory.create_calls) == 1
    assert new_a.MsEnvPartOfSpeechRA is new_b.MsEnvPartOfSpeechRA
    assert dropped == []


def test_msenv_pos_ra_preview_move_parity():
    """Preview twin's decision matches the Move outcome for the same input
    (G6): LINK when present, CREATE when absent-but-creatable, REPORT when
    uncreatable."""
    # LINK
    tgt_pos = _FakePOS("pos-link")
    target, _ = _make_target(pos=[tgt_pos])
    recs = owned._plan_moaffix_msenv_decisions(
        _FakeAffixAllomorph("a", msenv_pos=_FakePOS("pos-link")),
        _FakeCtx(target), {}, [])
    pos_recs = [r for r in recs if r.field_name == "MsEnvPartOfSpeechRA"]
    assert len(pos_recs) == 1
    assert pos_recs[0].action == ReferenceAction.LINK

    # CREATE
    target2, _ = _make_target(pos=[])
    recs2 = owned._plan_moaffix_msenv_decisions(
        _FakeAffixAllomorph("b", msenv_pos=_FakePOS("pos-abs")),
        _FakeCtx(target2), {}, [])
    pos_recs2 = [r for r in recs2 if r.field_name == "MsEnvPartOfSpeechRA"]
    assert len(pos_recs2) == 1
    assert pos_recs2[0].action == ReferenceAction.CREATE

    # REPORT (no create infra)
    target3, _ = _make_target(pos=[], with_factory=False)
    dropped3: list = []
    recs3 = owned._plan_moaffix_msenv_decisions(
        _FakeAffixAllomorph("c", msenv_pos=_FakePOS("pos-gone")),
        _FakeCtx(target3), {}, dropped3)
    assert not [r for r in recs3 if r.field_name == "MsEnvPartOfSpeechRA"]
    assert any(r.field_name == "MsEnvPartOfSpeechRA" for r in dropped3)


# ============================================================================
# T008 (US2) -- InflectionClassesRC reproduction (inflection-class references,
# read from the IMoAffixForm parent; each class owned by a POS).
# ============================================================================


def test_infl_class_link_when_present():
    """Inflection class already present in the target (under its owning POS's
    InflectionClassesOC, by GUID) -> the new allomorph references it; no class
    is created; nothing dropped (G2/LINK)."""
    src_pos = _FakePOS("pos-ic-1")
    src_class = _FakeInflClass("ic-1", owner=src_pos)
    tgt_class = _FakeInflClass("ic-1")
    tgt_pos = _FakePOS("pos-ic-1", inflection_classes=[tgt_class])
    target, _ = _make_target(pos=[tgt_pos], with_factory=False,
                             infl_class_factory=True)
    factory = target._factories["IMoInflClassFactory"]
    src_allo = _FakeAffixAllomorph("allo-ic-1", inflection_classes=[src_class])
    new_allo = _FakeNewAffixAllomorph("allo-ic-1")

    owned.reproduce_moaffix_msenv_data(
        src_allo, new_allo, _FakeCtx(target), _TAG, {}, [])

    assert list(new_allo.InflectionClassesRC) == [tgt_class]
    assert factory.create_calls == []


def test_infl_class_create_under_owning_pos_guid_preserved():
    """Class absent, owning POS present in target, create infra present -> the
    class is created under that POS's InflectionClassesOC (GUID preserved) and
    the allomorph references it (CREATE/G3/US2 scenario 1)."""
    src_pos = _FakePOS("pos-ic-2")
    src_class = _FakeInflClass("ic-new", owner=src_pos)
    tgt_pos = _FakePOS("pos-ic-2")  # owning POS in-closure, class absent
    target, _ = _make_target(pos=[tgt_pos], with_factory=False,
                             infl_class_factory=True)
    factory = target._factories["IMoInflClassFactory"]
    src_allo = _FakeAffixAllomorph("allo-ic-2", inflection_classes=[src_class])
    new_allo = _FakeNewAffixAllomorph("allo-ic-2")
    dropped: list = []

    owned.reproduce_moaffix_msenv_data(
        src_allo, new_allo, _FakeCtx(target), _TAG, {}, dropped)

    assert factory.create_calls == ["ic-new"]
    assert [c.guid for c in tgt_pos.InflectionClassesOC] == ["ic-new"]
    assert [c.guid for c in new_allo.InflectionClassesRC] == ["ic-new"]
    assert dropped == []


def test_infl_class_report_when_owning_pos_out_of_closure():
    """Owning POS neither present in the target nor in the copied closure ->
    the class reference is REPORT_DROPPED (owner/field/item identity) and the
    owning POS is NOT invented (G8/Principle V)."""
    src_pos = _FakePOS("pos-absent")
    src_class = _FakeInflClass("ic-orphan", owner=src_pos)
    target, _ = _make_target(pos=[], with_factory=False,
                             infl_class_factory=True)
    factory = target._factories["IMoInflClassFactory"]
    src_allo = _FakeAffixAllomorph("allo-ic-3", inflection_classes=[src_class])
    new_allo = _FakeNewAffixAllomorph("allo-ic-3")
    dropped: list = []

    owned.reproduce_moaffix_msenv_data(
        src_allo, new_allo, _FakeCtx(target), _TAG, {}, dropped)

    assert factory.create_calls == []
    assert list(new_allo.InflectionClassesRC) == []
    assert len(dropped) == 1
    rec = dropped[0]
    assert rec.field_name == "InflectionClassesRC"
    assert rec.owner_kind == "MoAffixAllomorph"
    assert rec.owner_guid == "allo-ic-3"
    assert rec.item_guid == "ic-orphan"


def test_infl_class_dedup_shared_class_created_once():
    """Two allomorphs referencing the same absent class (owning POS present)
    -> created once (resolver_cache), both reference the same object (G4)."""
    src_pos = _FakePOS("pos-ic-shared")
    tgt_pos = _FakePOS("pos-ic-shared")
    target, _ = _make_target(pos=[tgt_pos], with_factory=False,
                             infl_class_factory=True)
    factory = target._factories["IMoInflClassFactory"]
    resolver_cache: dict = {}
    ctx = _FakeCtx(target)

    new_a = _FakeNewAffixAllomorph("allo-a")
    owned.reproduce_moaffix_msenv_data(
        _FakeAffixAllomorph(
            "allo-a", inflection_classes=[_FakeInflClass("ic-shared", owner=src_pos)]),
        new_a, ctx, _TAG, resolver_cache, [])
    new_b = _FakeNewAffixAllomorph("allo-b")
    owned.reproduce_moaffix_msenv_data(
        _FakeAffixAllomorph(
            "allo-b", inflection_classes=[_FakeInflClass("ic-shared", owner=src_pos)]),
        new_b, ctx, _TAG, resolver_cache, [])

    assert factory.create_calls == ["ic-shared"]
    assert list(new_a.InflectionClassesRC) == list(new_b.InflectionClassesRC)
    assert len(new_a.InflectionClassesRC) == 1


def test_infl_class_empty_source_does_not_blank_target():
    """Empty source InflectionClassesRC -> no write; a populated target
    collection is not blanked (FR-005/G2)."""
    existing = _FakeInflClass("ic-keep")
    target, _ = _make_target(pos=[], with_factory=False, infl_class_factory=True)
    factory = target._factories["IMoInflClassFactory"]
    src_allo = _FakeAffixAllomorph("allo-ic-5", inflection_classes=[])
    new_allo = _FakeNewAffixAllomorph("allo-ic-5", inflection_classes=[existing])
    dropped: list = []

    owned.reproduce_moaffix_msenv_data(
        src_allo, new_allo, _FakeCtx(target), _TAG, {}, dropped)

    assert list(new_allo.InflectionClassesRC) == [existing]
    assert factory.create_calls == []
    assert dropped == []


def test_infl_class_preview_move_parity():
    """Preview twin's decision matches the Move outcome (G6): LINK present,
    CREATE absent-but-owning-POS-present, REPORT owning-POS-absent."""
    # LINK
    src_pos = _FakePOS("pos-p-link")
    tgt_class = _FakeInflClass("ic-p-link")
    tgt_pos = _FakePOS("pos-p-link", inflection_classes=[tgt_class])
    target, _ = _make_target(pos=[tgt_pos], with_factory=False,
                             infl_class_factory=True)
    recs = owned._plan_moaffix_msenv_decisions(
        _FakeAffixAllomorph(
            "a", inflection_classes=[_FakeInflClass("ic-p-link", owner=src_pos)]),
        _FakeCtx(target), {}, [])
    ic_recs = [r for r in recs if r.field_name == "InflectionClassesRC"]
    assert len(ic_recs) == 1 and ic_recs[0].action == ReferenceAction.LINK

    # CREATE
    tgt_pos2 = _FakePOS("pos-p-create")
    target2, _ = _make_target(pos=[tgt_pos2], with_factory=False,
                              infl_class_factory=True)
    recs2 = owned._plan_moaffix_msenv_decisions(
        _FakeAffixAllomorph(
            "b", inflection_classes=[
                _FakeInflClass("ic-p-new", owner=_FakePOS("pos-p-create"))]),
        _FakeCtx(target2), {}, [])
    ic_recs2 = [r for r in recs2 if r.field_name == "InflectionClassesRC"]
    assert len(ic_recs2) == 1 and ic_recs2[0].action == ReferenceAction.CREATE

    # REPORT (owning POS absent)
    target3, _ = _make_target(pos=[], with_factory=False, infl_class_factory=True)
    dropped3: list = []
    recs3 = owned._plan_moaffix_msenv_decisions(
        _FakeAffixAllomorph(
            "c", inflection_classes=[
                _FakeInflClass("ic-p-gone", owner=_FakePOS("pos-gone"))]),
        _FakeCtx(target3), {}, dropped3)
    assert not [r for r in recs3 if r.field_name == "InflectionClassesRC"]
    assert any(r.field_name == "InflectionClassesRC" for r in dropped3)


# ============================================================================
# T012 (US4) -- PositionRS reproduction (ordered infix-position environment
# references). Same target env list as PhoneEnvRC: link-or-report by GUID,
# in source order, NEVER create an environment.
# ============================================================================


class _FakeEnv(_FakeGuid):
    """A phonological environment (`IPhEnvironment`) in the target's flat
    `EnvironmentsOS` sequence -- identified by GUID (PositionRS resolves by
    GUID, the same way PhoneEnvRC does)."""

    ClassName = "PhEnvironment"


class _FakePhonData:
    """`lp.PhonologicalDataOA` exposing the flat owned `EnvironmentsOS`
    sequence PositionRS resolves against (the SAME list PhoneEnvRC uses)."""

    def __init__(self, envs=()):
        self.EnvironmentsOS = _FakeAddList(envs)


def _make_position_target(envs=()):
    """Fake target whose `Cache.LangProject.PhonologicalDataOA.EnvironmentsOS`
    holds `envs` (the resolvable target environments). No POS/class factory is
    wired -- PositionRS is link-or-report and never creates anything."""
    target, _ = _make_target(pos=[], with_factory=False)
    target.Cache.LangProject.PhonologicalDataOA = _FakePhonData(envs)
    return target


def test_position_rs_link_when_present():
    """Each source position resolves to a target env by GUID -> appended to the
    new allomorph's PositionRS; no env created; nothing dropped (G2/LINK)."""
    envs = [_FakeEnv("env-1"), _FakeEnv("env-2")]
    target = _make_position_target(envs)
    src_allo = _FakeAffixAllomorph("allo-pos-1", positions=[_FakeEnv("env-1")])
    new_allo = _FakeNewAffixAllomorph("allo-pos-1")
    dropped: list = []

    owned.reproduce_moaffix_msenv_data(
        src_allo, new_allo, _FakeCtx(target), _TAG, {}, dropped)

    # Linked to the actual target-project env object (by identity), not a copy.
    assert list(new_allo.PositionRS) == [envs[0]]
    assert list(target.Cache.LangProject.PhonologicalDataOA.EnvironmentsOS) == envs
    assert dropped == []


def test_position_rs_order_preserved():
    """Three resolvable positions -> the new PositionRS holds them in the SAME
    order as the source (INV-5/G5)."""
    envs = [_FakeEnv("env-a"), _FakeEnv("env-b"), _FakeEnv("env-c")]
    target = _make_position_target(envs)
    src_allo = _FakeAffixAllomorph(
        "allo-pos-2",
        positions=[_FakeEnv("env-b"), _FakeEnv("env-a"), _FakeEnv("env-c")])
    new_allo = _FakeNewAffixAllomorph("allo-pos-2")
    dropped: list = []

    owned.reproduce_moaffix_msenv_data(
        src_allo, new_allo, _FakeCtx(target), _TAG, {}, dropped)

    assert [e.guid for e in new_allo.PositionRS] == ["env-b", "env-a", "env-c"]
    assert dropped == []


def test_position_rs_middle_unresolvable_reported_without_reordering():
    """Positions [A, B, C] where B is absent from target -> new PositionRS ==
    [A, C] in order, and exactly one DroppedItemRecord for B (never-silent, G1;
    a middle drop does NOT reorder or drop the survivors)."""
    envs = [_FakeEnv("env-a"), _FakeEnv("env-c")]  # env-b absent
    target = _make_position_target(envs)
    src_allo = _FakeAffixAllomorph(
        "allo-pos-3",
        positions=[_FakeEnv("env-a"), _FakeEnv("env-b"), _FakeEnv("env-c")])
    new_allo = _FakeNewAffixAllomorph("allo-pos-3")
    dropped: list = []

    owned.reproduce_moaffix_msenv_data(
        src_allo, new_allo, _FakeCtx(target), _TAG, {}, dropped)

    assert [e.guid for e in new_allo.PositionRS] == ["env-a", "env-c"]
    assert len(dropped) == 1
    rec = dropped[0]
    assert rec.field_name == "PositionRS"
    assert rec.owner_kind == "MoAffixAllomorph"
    assert rec.owner_guid == "allo-pos-3"
    assert rec.item_guid == "env-b"


def test_position_rs_never_creates_environment():
    """An absent env is REPORT_DROPPED and NO environment is added to the
    target's EnvironmentsOS (G7 -- never create an environment)."""
    envs = [_FakeEnv("present")]
    target = _make_position_target(envs)
    env_list = target.Cache.LangProject.PhonologicalDataOA.EnvironmentsOS
    before = list(env_list)
    src_allo = _FakeAffixAllomorph("allo-pos-4", positions=[_FakeEnv("absent")])
    new_allo = _FakeNewAffixAllomorph("allo-pos-4")
    dropped: list = []

    owned.reproduce_moaffix_msenv_data(
        src_allo, new_allo, _FakeCtx(target), _TAG, {}, dropped)

    assert list(env_list) == before  # target env list unchanged (never created)
    assert list(new_allo.PositionRS) == []
    assert len(dropped) == 1
    assert dropped[0].field_name == "PositionRS"
    assert dropped[0].item_guid == "absent"


def test_position_rs_empty_source_does_not_blank_target():
    """Empty source PositionRS -> no write; a populated target PositionRS is
    not blanked (FR-005/G2)."""
    keep = _FakeEnv("keep")
    target = _make_position_target([keep])
    src_allo = _FakeAffixAllomorph("allo-pos-5", positions=[])
    new_allo = _FakeNewAffixAllomorph("allo-pos-5", positions=[keep])
    dropped: list = []

    owned.reproduce_moaffix_msenv_data(
        src_allo, new_allo, _FakeCtx(target), _TAG, {}, dropped)

    assert list(new_allo.PositionRS) == [keep]
    assert dropped == []


def test_position_rs_preview_move_parity():
    """Preview twin emits LINK decisions in source order for resolvable
    positions and a drop record for the unresolvable one, matching the Move
    outcome (G6)."""
    envs = [_FakeEnv("env-a"), _FakeEnv("env-c")]  # env-b absent
    target = _make_position_target(envs)
    src_allo = _FakeAffixAllomorph(
        "allo-pos-6",
        positions=[_FakeEnv("env-a"), _FakeEnv("env-b"), _FakeEnv("env-c")])
    dropped: list = []

    recs = owned._plan_moaffix_msenv_decisions(
        src_allo, _FakeCtx(target), {}, dropped)

    pos_recs = [r for r in recs if r.field_name == "PositionRS"]
    assert [r.action for r in pos_recs] == [
        ReferenceAction.LINK, ReferenceAction.LINK]
    assert [r.item_guid for r in pos_recs] == ["env-a", "env-c"]  # source order
    pos_drops = [r for r in dropped if r.field_name == "PositionRS"]
    assert len(pos_drops) == 1
    assert pos_drops[0].item_guid == "env-b"
