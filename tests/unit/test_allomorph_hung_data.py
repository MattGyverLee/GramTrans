"""Write-first unit tests for `owned.reproduce_allomorph_hung_data` (feature
024 US3, T029) plus one BEHAVIORAL guard test for the ALREADY-implemented
`walk_owned_children` entry-level dispatch (closes QC's cycle-10 nit -- see
the clearly-marked GREEN section at the bottom of this file).

Contract: `specs/024-lexicon-reference-fidelity/contracts/owned-object-walk.md`
`reproduce_allomorph_hung_data`; research.md R6.

CONFIRMED-LIVE surfaces (MCP, 2026-07-11/12, against Ejagham Mini -- 0 real
APRs / factory-default phonological environments in that project, so every
fixture below is FAKES-ONLY; there is no live positive-count probe to run
this cycle):

- `IMoStemAllomorph.PhoneEnvRC` (coll of IPhEnvironment) resolves against
  `lp.PhonologicalDataOA.EnvironmentsOS` -- an OWNED SEQUENCE, NOT an
  ICmPossibilityList (no `PossibilitiesOS`/`SubPossibilitiesOS` nesting, no
  ancestor-chain creation) -- by GUID: link if present, REPORT_DROPPED if
  absent, NEVER create an environment from scratch (contract non-goal). The
  fakes below deliberately give the environment-list fake NO
  `PossibilitiesOS` attribute at all, so a wrongly-implemented version that
  routes this field through `references._find_in_possibility_list` (which
  falls back to an empty list via `getattr(..., "PossibilitiesOS", None)`)
  would ALWAYS see "absent" even when the environment genuinely IS present
  in the flat target list -- test (a) below would then fail, catching that
  exact mistake.
- `IMoStemAllomorph.StemNameRA` resolves against the OWNING POS's OWN
  `StemNamesOC` (`IPartOfSpeech.StemNamesOC`) -- POS-scoped, not a single
  global list -- found by matching the source stem name's owning POS GUID
  against `target.POS.GetAll(recursive=True)` (mirrors the proven
  `categories.stem_names_execute_action` owner-POS-lookup idiom), then
  searching that target POS's own `StemNamesOC` by the stem name's GUID.
- `IMoAlloAdhocProhibFactory.Create(Guid)` -- UNOWNED (only a bare-Guid
  overload; no `(guid, owner)` overload -- confirmed live). The caller must
  separately `.Add()` the new APR to
  `LangProject.MorphologicalDataOA.AdhocCoProhibitionsOC`.
  `IMoAlloAdhocProhib.FirstAllomorphRA` (atomic), `.RestOfAllosRS` (seq),
  `.AllomorphsRS` (seq) are set to the COPIED counterparts of the source's
  own members -- reproduced ONLY when every member GUID is present in the
  run's copy set (mirrors FR-008's lexical-relation partial-member rule,
  research R6's "open sub-point"); otherwise exactly one `DroppedItemRecord`
  (reason "member not in copy set" -- data-model.md's own worked example
  for this exact phrase) and the APR is NOT created at all.

Copy-set convention (this cycle's fixture design -- not yet an existing
`RunContext` field): `ctx._copy_set` models the run's copy set as a
`dict[str_guid, already_copied_target_object]` -- a superset of "GUID set"
(membership checked via plain `in`) that ALSO gives a future implementation
the already-copied allomorph OBJECT it needs in order to point
`FirstAllomorphRA`/`RestOfAllosRS`/`AllomorphsRS` at real target objects,
not just prove membership. Populated by the fixture as though every
allomorph referenced by an APR under test had already been walked earlier
in the same run (matches `_walk_entry_allomorphs`' sequential
LexemeFormOA-then-AlternateFormsOS order) -- this file does not assert
anything about call ORDER/dedup across multiple `reproduce_allomorph_hung_data`
calls for the same APR (out of scope this cycle).
"""
from __future__ import annotations

from gramtrans.Lib import owned


# ============================================================================
# Small guid-only fakes
# ============================================================================

class _FakeGuidObj:
    def __init__(self, guid):
        self.Guid = guid
        self.guid = guid


class _FakeOwningCollection:
    """Iterable + `.Add()`-able -- used for every owned/reference collection
    on a freshly-created target-side object (`PhoneEnvRC`, `RestOfAllosRS`,
    `AllomorphsRS`, `AdhocCoProhibitionsOC`)."""

    def __init__(self, items=()) -> None:
        self._items = list(items)

    def __iter__(self):
        return iter(self._items)

    def __len__(self):
        return len(self._items)

    def __getitem__(self, idx):
        return self._items[idx]

    def Add(self, item):
        self._items.append(item)


# ============================================================================
# Phonological environment fakes -- flat, NOT a possibility list.
# ============================================================================

class _FakeEnvironment(_FakeGuidObj):
    """Fake IPhEnvironment -- a flat member of
    `PhonologicalDataOA.EnvironmentsOS`. Deliberately carries NO
    `PossibilitiesOS`/`SubPossibilitiesOS` (unlike `_FakePossibility` in
    `test_reference_resolver.py`/`test_owned_object_walk.py`) -- this field
    is NOT routed through the generic possibility resolver (contract)."""


# ============================================================================
# POS + stem-name fakes -- POS-scoped StemNamesOC.
# ============================================================================

class _FakeStemName(_FakeGuidObj):
    """Fake IMoStemName. `.Owner` (set by the test, not the constructor) is
    the owning `_FakePOS` -- mirrors the real `StemNamesOC` owned-collection
    shape."""


class _FakePOS(_FakeGuidObj):
    def __init__(self, guid, stem_names=()):
        super().__init__(guid)
        self.StemNamesOC = list(stem_names)


class _FakePOSNamespace:
    """Fake `project.POS` accessor -- `.GetAll(recursive=True)` mirrors
    `categories._iter_pos`'s real accessor path."""

    def __init__(self, pos_list=()):
        self._pos_list = list(pos_list)

    def GetAll(self, recursive=False):
        return list(self._pos_list)


# ============================================================================
# Allomorph fakes (source + freshly-created target).
# ============================================================================

class _FakeSourceAllomorph(_FakeGuidObj):
    def __init__(self, guid, phone_env_rc=(), stem_name_ra=None):
        super().__init__(guid)
        self.PhoneEnvRC = list(phone_env_rc)
        self.StemNameRA = stem_name_ra


class _FakeNewAllomorph(_FakeGuidObj):
    def __init__(self, guid):
        super().__init__(guid)
        self.PhoneEnvRC = _FakeOwningCollection()
        self.StemNameRA = None


# ============================================================================
# APR fakes -- IMoAlloAdhocProhib (source) / freshly-created target + its
# UNOWNED factory.
# ============================================================================

class _FakeSourceAPR(_FakeGuidObj):
    def __init__(self, guid, first_allomorph=None, rest_of_allos=(), allomorphs=()):
        super().__init__(guid)
        self.FirstAllomorphRA = first_allomorph
        self.RestOfAllosRS = list(rest_of_allos)
        self.AllomorphsRS = list(allomorphs)


class _FakeNewAPR(_FakeGuidObj):
    def __init__(self, guid):
        super().__init__(guid)
        self.FirstAllomorphRA = None
        self.RestOfAllosRS = _FakeOwningCollection()
        self.AllomorphsRS = _FakeOwningCollection()


class _FakeAPRFactory:
    """UNOWNED: `IMoAlloAdhocProhibFactory.Create(Guid)` -- no owner
    parameter at all (confirmed live via MCP). The caller must separately
    `.Add()` the new APR onto `MorphologicalDataOA.AdhocCoProhibitionsOC`."""

    def __init__(self):
        self.create_calls = []

    def Create(self, guid):
        self.create_calls.append(guid)
        return _FakeNewAPR(guid)


# ============================================================================
# LangProject / Cache / project (source + target) fakes.
# ============================================================================

class _FakePhonologicalData:
    def __init__(self, environments=()):
        self.EnvironmentsOS = list(environments)


class _FakeMorphologicalData:
    def __init__(self, aprs=()):
        # `_FakeOwningCollection` for BOTH roles: source only ever iterates
        # it (discovery), target also `.Add()`s a newly-reproduced APR.
        self.AdhocCoProhibitionsOC = _FakeOwningCollection(aprs)


class _FakeLangProject:
    def __init__(self, environments=(), aprs=()):
        self.PhonologicalDataOA = _FakePhonologicalData(environments)
        self.MorphologicalDataOA = _FakeMorphologicalData(aprs)


class _FakeCache:
    def __init__(self, lang_project):
        self.LangProject = lang_project


class _FakeProject:
    """Fake FLExProject-shaped handle: `Cache.LangProject.PhonologicalDataOA
    .EnvironmentsOS`, `Cache.LangProject.MorphologicalDataOA
    .AdhocCoProhibitionsOC`, `POS.GetAll(recursive=True)`, and the
    `GetService`-keyed owned-child factories."""

    def __init__(self, environments=(), aprs=(), pos_list=(), factories=None):
        self.Cache = _FakeCache(_FakeLangProject(environments, aprs))
        self.POS = _FakePOSNamespace(pos_list)
        self._factories = factories or {}
        self.requested_services = []

    def GetService(self, name):
        self.requested_services.append(name)
        return self._factories[name]


class _FakeContext:
    """Mirrors the real `RunContext`-shaped `ctx` -- `source_handle`,
    `target_handle`, `_ws_map` -- plus this file's `_copy_set` fixture
    convention (see module docstring)."""

    def __init__(self, source_handle, target_handle, ws_map=None, copy_set=None):
        self.source_handle = source_handle
        self.target_handle = target_handle
        self._ws_map = ws_map or {}
        self._copy_set = copy_set if copy_set is not None else {}


_TAG = "tag-allomorph-hung-data"


# ============================================================================
# (a) PhoneEnvRC resolves/links to a target environment present by GUID.
# ============================================================================

def test_phone_env_rc_resolves_to_target_environment_by_guid():
    env_guid = "env-guid-1"
    src_env = _FakeEnvironment(env_guid)
    target_env = _FakeEnvironment(env_guid)  # same GUID, distinct instance

    src_allo = _FakeSourceAllomorph("allo-guid-1", phone_env_rc=[src_env])
    new_allo = _FakeNewAllomorph("allo-guid-1")

    source = _FakeProject(environments=[src_env])
    target = _FakeProject(environments=[target_env],
                           factories={"IMoAlloAdhocProhibFactory": _FakeAPRFactory()})
    ctx = _FakeContext(source, target)
    dropped: list = []
    resolver_cache: dict = {}

    owned.reproduce_allomorph_hung_data(
        src_allo, new_allo, ctx, _TAG, resolver_cache, dropped)

    assert list(new_allo.PhoneEnvRC) == [target_env]
    assert dropped == []


# ============================================================================
# (b) PhoneEnvRC where the environment is ABSENT in target -> DroppedItemRecord,
# no environment created.
# ============================================================================

def test_phone_env_rc_absent_in_target_reports_dropped_and_creates_nothing():
    env_guid = "env-guid-missing"
    src_env = _FakeEnvironment(env_guid)

    src_allo = _FakeSourceAllomorph("allo-guid-2", phone_env_rc=[src_env])
    new_allo = _FakeNewAllomorph("allo-guid-2")

    source = _FakeProject(environments=[src_env])
    target = _FakeProject(environments=[],  # absent
                           factories={"IMoAlloAdhocProhibFactory": _FakeAPRFactory()})
    ctx = _FakeContext(source, target)
    dropped: list = []
    resolver_cache: dict = {}

    owned.reproduce_allomorph_hung_data(
        src_allo, new_allo, ctx, _TAG, resolver_cache, dropped)

    assert list(new_allo.PhoneEnvRC) == []
    assert len(dropped) == 1
    rec = dropped[0]
    assert rec.field_name == "PhoneEnvRC"
    assert rec.item_guid == env_guid
    # Exact wording is the future implementation's to choose; this pins down
    # only the never-silent + never-create guarantees the contract demands.
    assert "not" in rec.reason.lower()


# ============================================================================
# (c) APR whose ALL members are in the copy set is reproduced with
# FirstAllomorphRA/RestOfAllosRS/AllomorphsRS pointing at the COPIED
# allomorphs, GUID preserved.
# ============================================================================

def test_apr_all_members_in_copy_set_is_reproduced_with_copied_members_guid_preserved():
    apr_guid = "apr-guid-1"
    allo_a_src = _FakeSourceAllomorph("allo-a-guid")
    allo_b_src = _FakeSourceAllomorph("allo-b-guid")
    allo_a_new = _FakeNewAllomorph("allo-a-guid")
    allo_b_new = _FakeNewAllomorph("allo-b-guid")

    src_apr = _FakeSourceAPR(
        apr_guid,
        first_allomorph=allo_a_src,
        rest_of_allos=[allo_b_src],
        allomorphs=[allo_a_src, allo_b_src],
    )

    source = _FakeProject(aprs=[src_apr])
    apr_factory = _FakeAPRFactory()
    target = _FakeProject(factories={"IMoAlloAdhocProhibFactory": apr_factory})
    ctx = _FakeContext(source, target, copy_set={
        "allo-a-guid": allo_a_new,
        "allo-b-guid": allo_b_new,
    })
    dropped: list = []
    resolver_cache: dict = {}

    owned.reproduce_allomorph_hung_data(
        allo_a_src, allo_a_new, ctx, _TAG, resolver_cache, dropped)

    target_aprs = list(target.Cache.LangProject.MorphologicalDataOA.AdhocCoProhibitionsOC)
    assert len(target_aprs) == 1
    new_apr = target_aprs[0]
    assert new_apr.Guid == apr_guid
    assert new_apr.FirstAllomorphRA is allo_a_new
    assert list(new_apr.RestOfAllosRS) == [allo_b_new]
    assert list(new_apr.AllomorphsRS) == [allo_a_new, allo_b_new]
    assert dropped == []


# ============================================================================
# (d) An APR with a member NOT in the copy set -> exactly one
# DroppedItemRecord "member not in copy set", APR NOT created.
# ============================================================================

def test_apr_member_not_in_copy_set_reports_dropped_and_apr_not_created():
    apr_guid = "apr-guid-2"
    allo_a_src = _FakeSourceAllomorph("allo-a-guid")
    allo_c_src = _FakeSourceAllomorph("allo-c-guid")  # never copied
    allo_a_new = _FakeNewAllomorph("allo-a-guid")

    src_apr = _FakeSourceAPR(
        apr_guid,
        first_allomorph=allo_a_src,
        rest_of_allos=[allo_c_src],
        allomorphs=[allo_a_src, allo_c_src],
    )

    source = _FakeProject(aprs=[src_apr])
    apr_factory = _FakeAPRFactory()
    target = _FakeProject(factories={"IMoAlloAdhocProhibFactory": apr_factory})
    ctx = _FakeContext(source, target, copy_set={"allo-a-guid": allo_a_new})
    dropped: list = []
    resolver_cache: dict = {}

    owned.reproduce_allomorph_hung_data(
        allo_a_src, allo_a_new, ctx, _TAG, resolver_cache, dropped)

    assert list(target.Cache.LangProject.MorphologicalDataOA.AdhocCoProhibitionsOC) == []
    assert apr_factory.create_calls == []
    assert len(dropped) == 1
    rec = dropped[0]
    assert rec.reason == "member not in copy set"
    assert rec.item_guid == "allo-c-guid"


# ============================================================================
# (e) StemNameRA resolves against the target POS's StemNamesOC, or REPORTs.
# ============================================================================

def test_stem_name_ra_resolves_against_target_pos_stem_names_oc():
    pos_guid = "pos-guid-1"
    sn_guid = "sn-guid-1"

    src_pos = _FakePOS(pos_guid)
    src_stem_name = _FakeStemName(sn_guid)
    src_stem_name.Owner = src_pos

    src_allo = _FakeSourceAllomorph("allo-guid-3", stem_name_ra=src_stem_name)
    new_allo = _FakeNewAllomorph("allo-guid-3")

    target_stem_name = _FakeStemName(sn_guid)
    target_pos = _FakePOS(pos_guid, stem_names=[target_stem_name])

    source = _FakeProject()
    target = _FakeProject(pos_list=[target_pos],
                           factories={"IMoAlloAdhocProhibFactory": _FakeAPRFactory()})
    ctx = _FakeContext(source, target)
    dropped: list = []
    resolver_cache: dict = {}

    owned.reproduce_allomorph_hung_data(
        src_allo, new_allo, ctx, _TAG, resolver_cache, dropped)

    assert new_allo.StemNameRA is target_stem_name
    assert dropped == []


def test_stem_name_ra_absent_in_target_pos_reports_dropped():
    pos_guid = "pos-guid-2"
    sn_guid = "sn-guid-missing"

    src_pos = _FakePOS(pos_guid)
    src_stem_name = _FakeStemName(sn_guid)
    src_stem_name.Owner = src_pos

    src_allo = _FakeSourceAllomorph("allo-guid-4", stem_name_ra=src_stem_name)
    new_allo = _FakeNewAllomorph("allo-guid-4")

    # Owning POS IS present in target (GUID matches) but its StemNamesOC has
    # no member matching `sn_guid`.
    target_pos = _FakePOS(pos_guid, stem_names=[])

    source = _FakeProject()
    target = _FakeProject(pos_list=[target_pos],
                           factories={"IMoAlloAdhocProhibFactory": _FakeAPRFactory()})
    ctx = _FakeContext(source, target)
    dropped: list = []
    resolver_cache: dict = {}

    owned.reproduce_allomorph_hung_data(
        src_allo, new_allo, ctx, _TAG, resolver_cache, dropped)

    assert new_allo.StemNameRA is None
    assert len(dropped) == 1
    rec = dropped[0]
    assert rec.field_name == "StemNameRA"
    assert rec.item_guid == sn_guid


# ============================================================================
# GREEN guard test (closes QC's cycle-10 nit) -- NOT part of the write-first
# RED set above. Exercises ALREADY-implemented `owned.walk_owned_children`
# behavior and is expected to PASS today.
# ============================================================================

class _FakeEntryOwner:
    """Duck-types a `SensesOS` attribute too (a real `ILexEntry`'s own
    top-level senses collection) -- the exact collision
    `owned._matches_owner_class` (QC P1a) must disambiguate by real
    `ClassName`, not by `hasattr` alone."""

    def __init__(self, guid):
        self.Guid = guid
        self.guid = guid
        self.ClassName = "LexEntry"
        self.SensesOS = [_FakeGuidObj("phantom-sub-sense-guid")]
        self.PronunciationsOS = []
        self.EtymologyOS = []


class _NewEntryOwnerStub:
    def __init__(self, guid="new-entry-guid-1"):
        self.Guid = guid
        self.guid = guid
        self.PronunciationsOS = _FakeOwningCollection()
        self.EtymologyOS = _FakeOwningCollection()


def test_entry_level_dispatch_skips_lex_sense_senses_os_row():
    """GREEN (existing behavior): `owned.walk_owned_children`, called
    UNFILTERED (no `owning_fields` kwarg) on a `ClassName == "LexEntry"`
    owner, must NOT match the `OWNED_OBJECT_MAP` `LexSense.SensesOS` row
    (recurse=True) even though `entry_owner` duck-types `SensesOS` too --
    proven by asserting the sub-sense factory (`ILexSenseFactory`) is NEVER
    invoked. Calling this UNFILTERED (unlike the real T030 entry-level call,
    which also passes `owning_fields={"PronunciationsOS", "EtymologyOS"}`)
    isolates the ClassName check itself as what prevents the phantom
    sub-sense creation, independent of the `owning_fields` filter."""
    entry_owner = _FakeEntryOwner("entry-guid-1")
    new_entry = _NewEntryOwnerStub()

    class _FakeSenseFactory:
        def __init__(self):
            self.create_calls = []

        def Create(self, guid, owner):
            self.create_calls.append((guid, owner))
            return _FakeGuidObj(guid)

    sense_factory = _FakeSenseFactory()
    source = _FakeProject()
    target = _FakeProject(factories={"ILexSenseFactory": sense_factory})
    ctx = _FakeContext(source, target)
    dropped: list = []
    resolver_cache: dict = {}

    owned.walk_owned_children(entry_owner, new_entry, ctx, _TAG, resolver_cache, dropped)

    assert sense_factory.create_calls == []
    assert dropped == []
