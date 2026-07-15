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


class _FakePOS(_FakeGuid):
    ClassName = "PartOfSpeech"

    def __init__(self, guid, owner=None):
        super().__init__(guid)
        self.Owner = owner
        self.SubPossibilitiesOS = []
        self.InflectionClassesOC = []


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
            parent.SubPossibilitiesOS.append(new)
        return new


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
    def __init__(self, pos=(), pos_factory=None):
        self._registry = list(pos)
        self.Cache = _FakeCache()
        self.POS = _FakePOSNamespace(self._registry)
        self._pos_factory = pos_factory

    def GetFactory(self, key):
        if self._pos_factory is None:
            raise KeyError(key)
        return self._pos_factory


class _FakeSource:
    """Source handle -- the POS legs never read the source project directly
    (they read off the source allomorph object), so this is a bare stand-in."""


class _FakeAffixAllomorph(_FakeGuid):
    ClassName = "MoAffixAllomorph"

    def __init__(self, guid, msenv_pos=None, inflection_classes=None):
        super().__init__(guid)
        self.MsEnvPartOfSpeechRA = msenv_pos
        self.InflectionClassesRC = list(inflection_classes or [])


class _FakeNewAffixAllomorph(_FakeGuid):
    ClassName = "MoAffixAllomorph"

    def __init__(self, guid, msenv_pos=None, inflection_classes=()):
        super().__init__(guid)
        self.MsEnvPartOfSpeechRA = msenv_pos
        self.InflectionClassesRC = list(inflection_classes)


class _FakeCtx:
    def __init__(self, target, source=None):
        self.source_handle = source or _FakeSource()
        self.target_handle = target


_TAG = "tag-028-msenv"


def _make_target(pos=(), with_factory=True):
    registry = list(pos)
    factory = _FakePOSFactory(registry) if with_factory else None
    target = _FakeTarget(pos=registry, pos_factory=factory)
    # `_FakeTarget.__init__` copied `pos` into its own registry; rebind the
    # factory to that same list so a created POS is resolvable afterwards.
    if factory is not None:
        factory._registry = target._registry
        target.POS = _FakePOSNamespace(target._registry)
    return target, factory


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
