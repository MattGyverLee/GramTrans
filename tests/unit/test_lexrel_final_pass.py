"""Tests (feature 024, US3, FR-008) driving lexical-relation reproduction
through the FINAL-PASS entrypoints ONLY --
`categories.reproduce_all_lexical_relations` (Move) /
`categories.plan_all_lexical_relations` (Preview) -- the same functions
`Lib/transfer.py.execute`/`Lib/preview.py.build_run_plan` call once, after
the run's ENTIRE `ctx._copy_set` has been assembled. This file no longer
calls the per-member incremental trigger functions
(`categories._reproduce_lex_relations_for_member`/
`categories._plan_lex_relations_for_member`, `owned._reproduce_lex_relations_
for_recursed_child`/`owned._plan_lex_relations_for_recursed_child`) directly
-- those are slated for removal once the single-final-pass redesign lands
(the "next task"), so no test here may pin them as a standalone API. Where
a scenario needs a member to already be sitting in `ctx._copy_set` "as if"
an earlier point of the closure had copied it, the test drives that through
`owned.walk_owned_children`/`owned.plan_owned_object_decisions` (a surviving
closure entrypoint) or by mutating `ctx._copy_set` directly and re-invoking
the final-pass entrypoint -- never by calling the doomed per-member trigger.

Tests 1-5 retarget the ORIGINAL write-first defects this file locked
(partial-cache-then-stale-drop for COLLECTION/PAIR members copied at
different times) onto the final-pass entrypoints: each "member copied at
time T" step is now `ctx._copy_set[guid] = value` followed by a call to
`reproduce_all_lexical_relations`/`plan_all_lexical_relations` -- these
calls hit EXACTLY the same `reproduce_lexical_relation`/
`plan_lexical_relation_decision` caching core the old per-member trigger
called, so the same completeness/no-false-drop guarantees apply, now
proven through the surviving API.

Tests 6-8 (NEW, this cycle) are the FIRST tests in this suite to prove the
HYBRID's remaining defect: TargetsRS on a MULTI-member relation whose
members are copied (added to `ctx._copy_set`) in an order DIFFERENT from
the SOURCE relation's own `TargetsRS` order comes out in CLOSURE-DISCOVERY
order, not SOURCE order, because `reproduce_lexical_relation`'s cache-hit
branch only ever APPENDS newly-available members onto whatever partial
`TargetsRS` an earlier, less-complete final-pass call already created --
it never re-sorts. `_evaluate_lexical_relation` itself always recomputes
`copied_members` in correct source order from scratch every call (proven by
using it as a read-only probe of the CORRECT order below); the divergence
lives entirely in the stateful `existing.TargetsRS.Add()` accumulation in
`reproduce_lexical_relation`'s cache-hit branch. These three tests (test 6
COLLECTION, test 7 SEQUENCE, test 8 TREE) MUST FAIL (RED) against current
code on their ORDER assertion, and MUST PASS once the single-final-pass
redesign makes TargetsRS always reflect the CURRENT, fully-settled copy_set
recomputed in source order (regardless of how many times, or in what copy
order, the final pass happens to run). PAIR/ASYMMETRIC-PAIR relations are
NOT similarly affected (a below-minimum evaluation is never cached, so the
first CREATE only ever happens once >=2 members are already present, at
which point `copied_members` is already correct source order) -- no
dedicated PAIR ordering test is added for that reason.

Test 9 (NEW, this cycle) proves a relation whose sole trigger-eligible
member is an ALLOMORPH (`IMoForm`) is discovered and reproduced by the
final pass even though NO per-member incremental trigger exists for
allomorphs at all (`categories._plan_entry_reference_decisions`'s allomorph
loop registers `copy_set[a_guid] = True` but never calls
`_plan_lex_relations_for_member` for it -- confirmed by reading
categories.py's allomorph loop, ~3456-3481). This case is already GREEN
today: the final pass's own enumeration (`_iter_relations_touching_copy_
set`) does not care what kind of object a `TargetsRS` member is, so it is
found and reproduced on its first (and only) evaluation regardless.
"""
from __future__ import annotations

from gramtrans.Lib import categories, owned


WS_EN = 100
_TAG = "tag-lexrel-final-pass"
_MAPPING_TYPE_COLLECTION = 10  # kmtEntryOrSenseCollection -- open-ended
_MAPPING_TYPE_PAIR = 11        # kmtEntryOrSensePair -- exactly 2 required


# ============================================================================
# Shared fakes (same shapes as test_lexical_relations.py / test_subsense_
# copy_set.py -- kept local per this codebase's per-file fixture convention).
# ============================================================================

class _FakeGuidObj:
    def __init__(self, guid):
        self.Guid = guid
        self.guid = guid


class _FakeMember(_FakeGuidObj):
    """Fake `ILexEntry`/`ILexSense` `TargetsRS` member -- only GUID matters
    for the resolver's copy-set membership check, so this stands in for a
    whole separately-copied entry without needing the full LCM-bound
    `ILexEntryFactory` closure machinery `_walk_lex_entry_closure` uses."""


class _FakeOwningCollection:
    def __init__(self, items=()):
        self._items = list(items)

    def __iter__(self):
        return iter(self._items)

    def __len__(self):
        return len(self._items)

    def __getitem__(self, idx):
        return self._items[idx]

    def Add(self, item):
        self._items.append(item)


class _FakeLexRefType(_FakeGuidObj):
    def __init__(self, guid, mapping_type, members=()):
        super().__init__(guid)
        self.MappingType = mapping_type
        self.MembersOC = _FakeOwningCollection(members)


class _FakeNewLexReference(_FakeGuidObj):
    def __init__(self, guid):
        super().__init__(guid)
        self.TargetsRS = _FakeOwningCollection()


class _FakeLexReferenceFactory:
    def __init__(self):
        self.create_calls = []

    def Create(self, guid, owner):
        if not hasattr(owner, "MembersOC"):
            raise TypeError(
                "ILexReferenceFactory.Create(guid, owner) expects an "
                f"ILexRefType (MembersOC); got {owner!r}"
            )
        self.create_calls.append((guid, owner))
        new_rel = _FakeNewLexReference(guid)
        owner.MembersOC.Add(new_rel)
        return new_rel


class _FakeSourceLexReference(_FakeGuidObj):
    def __init__(self, guid, owner_type, targets=()):
        super().__init__(guid)
        self.Owner = owner_type
        self.TargetsRS = list(targets)


class _FakeTargetList:
    def __init__(self, items=()):
        self.PossibilitiesOS = list(items)


class _FakeLexDb:
    def __init__(self, references_oa):
        self.ReferencesOA = references_oa
        self.SenseTypesOA = _FakeTargetList()
        self.TranslationTagsOA = _FakeTargetList()
        self.LanguagesOA = _FakeTargetList()
        self.PublicationTypesOA = _FakeTargetList()


class _FakeLangProject:
    def __init__(self, references_oa):
        self.LexDbOA = _FakeLexDb(references_oa)


class _FakeCache:
    def __init__(self, lang_project):
        self.LangProject = lang_project
        self.DefaultAnalWs = WS_EN


class _FakeSyncOps:
    def GetSyncableProperties(self, obj):
        return {"_marker": getattr(obj, "Guid", None)}

    def ApplySyncableProperties(self, obj, props, ws_map=None):
        pass


class _FakeProject:
    """Fake FLExProject-shaped handle -- `Cache.LangProject...` for the
    relation-type list, plus the per-class sync-ops namespaces + sense
    factory `owned.walk_owned_children`/`plan_owned_object_decisions`
    need for the sub-sense leg (test 2 only; harmless no-ops elsewhere)."""

    def __init__(self, ref_types=(), factories=None):
        self.Cache = _FakeCache(_FakeLangProject(_FakeTargetList(ref_types)))
        self.Examples = _FakeSyncOps()
        self.Translations = _FakeSyncOps()
        self.Pronunciations = _FakeSyncOps()
        self.Etymology = _FakeSyncOps()
        self.Senses = _FakeSyncOps()
        self._factories = dict(factories or {})
        self._factories.setdefault("ILexSenseFactory", _FakeSenseFactory())
        self.requested_services = []

    def GetService(self, name):
        self.requested_services.append(name)
        return self._factories[name]


class _FakeContext:
    def __init__(self, source_handle, target_handle, copy_set=None):
        self.source_handle = source_handle
        self.target_handle = target_handle
        self._ws_map = {}
        self._copy_set = copy_set if copy_set is not None else {}


# ---- sense / sub-sense fakes (test 2 only) --------------------------------

class _FakeMultiString:
    def __init__(self, data=None):
        self._data = dict(data or {})

    def get_String(self, ws_handle):
        class _Ts:
            def __init__(self, text):
                self.Text = text
        return _Ts(self._data.get(ws_handle))


class _FakeSourceSense:
    def __init__(self, guid, gloss="", examples=(), sub_senses=()):
        self.Guid = guid
        self.guid = guid
        self.Gloss = _FakeMultiString({WS_EN: gloss} if gloss else {})
        self.ExamplesOS = list(examples)
        self.SensesOS = list(sub_senses)
        self.SenseTypeRA = None


class _NewSense:
    def __init__(self, guid):
        self.Guid = guid
        self.guid = guid
        self.ExamplesOS = _FakeOwningCollection()
        self.SensesOS = _FakeOwningCollection()
        self.SenseTypeRA = None


class _FakeSenseFactory:
    def __init__(self):
        self.create_calls = []

    def Create(self, guid, owner):
        if not hasattr(owner, "SensesOS"):
            raise TypeError(
                "ILexSenseFactory.Create(guid, owner) expects an ILexSense "
                f"(SensesOS); got {owner!r}"
            )
        self.create_calls.append((guid, owner))
        new_s = _NewSense(guid)
        owner.SensesOS.Add(new_s)
        return new_s


def _new_ctx_pair(ref_types_src, ref_types_move_tgt, ref_types_preview_tgt,
                   rel_factory):
    """Build a (move_ctx, preview_ctx) pair sharing one SOURCE project (same
    `src_relation`/`TargetsRS` objects) but each with its OWN target project
    + `_copy_set` + `dropped` list + `resolver_cache` -- mirrors Preview and
    Move each getting their own `resolver_cache` per run
    (`preview.build_run_plan`/`transfer.execute`)."""
    source = _FakeProject(ref_types=ref_types_src)
    move_target = _FakeProject(
        ref_types=ref_types_move_tgt,
        factories={"ILexReferenceFactory": rel_factory})
    preview_target = _FakeProject(ref_types=ref_types_preview_tgt)
    move_ctx = _FakeContext(source, move_target, copy_set={})
    preview_ctx = _FakeContext(source, preview_target, copy_set={})
    return move_ctx, preview_ctx


# ============================================================================
# Test 1 -- CROSS-ENTRY collection relation, members copied at different
# times (simulating two separately-copied `LexEntry`s in the same closure).
# ============================================================================

def test_cross_entry_collection_relation_reproduces_complete_preview_and_move():
    """Two entries copied at DIFFERENT points in the closure both being
    members of one open-ended COLLECTION relation must reproduce COMPLETE
    (both members present, no false drop) in BOTH Move and Preview, and the
    two must not diverge. Driven ENTIRELY through the final-pass entrypoints
    (`reproduce_all_lexical_relations`/`plan_all_lexical_relations`), called
    once per simulated copy point -- never through the per-member incremental
    trigger.

    Already GREEN (T031 hybrid fix, commit 4142899): the first final-pass
    call, with only entry 1 in `_copy_set`, creates+caches a relation with
    ONLY entry 1 and drops entry 2 as "not in copy set"; the SECOND
    final-pass call (entry 2 now copied) re-evaluates against the grown
    copy_set, unions in entry 2, and retracts the stale drop. Since entry 1
    is source-first here, the union-append lands in correct source order
    too (see tests 6-8 for the case where it does not).
    """
    type_guid, rel_guid = "type-cross", "rel-cross"
    e1_src, e2_src = _FakeMember("entry-1"), _FakeMember("entry-2")
    e1_move, e2_move = _FakeMember("entry-1"), _FakeMember("entry-2")

    src_type = _FakeLexRefType(type_guid, _MAPPING_TYPE_COLLECTION)
    src_rel = _FakeSourceLexReference(rel_guid, src_type, targets=[e1_src, e2_src])
    src_type.MembersOC.Add(src_rel)

    move_factory = _FakeLexReferenceFactory()
    move_ctx, preview_ctx = _new_ctx_pair(
        ref_types_src=[src_type],
        ref_types_move_tgt=[_FakeLexRefType(type_guid, _MAPPING_TYPE_COLLECTION)],
        ref_types_preview_tgt=[_FakeLexRefType(type_guid, _MAPPING_TYPE_COLLECTION)],
        rel_factory=move_factory)
    move_dropped, preview_dropped = [], []
    move_cache, preview_cache = {}, {}

    # --- entry 1 copied first: final pass runs against the copy_set as it
    # stands at this point in the (simulated) closure ---
    move_ctx._copy_set["entry-1"] = e1_move
    categories.reproduce_all_lexical_relations(move_ctx, _TAG, move_cache, move_dropped)
    preview_ctx._copy_set["entry-1"] = True
    categories.plan_all_lexical_relations(preview_ctx, preview_cache, preview_dropped)

    # --- entry 2 copied LATER (separate point in the closure); the final
    # pass runs again against the now-grown copy_set ---
    move_ctx._copy_set["entry-2"] = e2_move
    categories.reproduce_all_lexical_relations(move_ctx, _TAG, move_cache, move_dropped)
    preview_ctx._copy_set["entry-2"] = True
    categories.plan_all_lexical_relations(preview_ctx, preview_cache, preview_dropped)

    move_rels = list(move_ctx.target_handle.Cache.LangProject.LexDbOA
                      .ReferencesOA.PossibilitiesOS[0].MembersOC)
    assert len(move_rels) == 1
    assert list(move_rels[0].TargetsRS) == [e1_move, e2_move]
    assert not any("not in copy set" in getattr(r, "reason", "") for r in move_dropped)
    assert not any("not in copy set" in getattr(r, "reason", "") for r in preview_dropped)

    # Preview decision == Move outcome: neither run should still be
    # reporting a missing member once both entries have been copied.
    move_complete = list(move_rels[0].TargetsRS) == [e1_move, e2_move]
    preview_complete = not any(
        r.item_guid in ("entry-1", "entry-2") for r in preview_dropped)
    assert move_complete == preview_complete == True


# ============================================================================
# Test 2 -- SENSE + SUB-SENSE collection relation across two entries.
# ============================================================================

def test_sense_and_subsense_collection_relation_reproduces_complete_no_false_drop():
    """A relation whose members are a top-level sense (copied first) and a
    DIFFERENT entry's sub-sense (copied later, via the recursive `SensesOS`
    leg) must reproduce with BOTH members and no false drop, in both Move
    and Preview. Sense A's copy point is driven through the final-pass
    entrypoint directly (no per-member trigger call); sense B's sub-sense is
    driven through the real closure entrypoint (`owned.walk_owned_children`/
    `owned.plan_owned_object_decisions`) -- ordering of `_copy_set` is
    exactly as the real closure produces it. (`walk_owned_children` still
    fires its OWN internal recursed-child trigger for the sub-sense --
    that is plumbing inside a surviving entrypoint, not something this test
    calls directly.)

    Already GREEN: sense A happens to be source-first here, so the
    final pass's first call (sense A only) creates a correctly-ordered
    partial relation, and the sub-sense's later registration unions onto
    the END in the same relative order -- no divergence for this 2-member,
    source-order-matches-copy-order case. See tests 6-8 for the ordering
    defect this masks.
    """
    type_guid, rel_guid = "type-sense-sub", "rel-sense-sub"

    sense_a_src = _FakeSourceSense("sense-a")
    sub_b_src = _FakeSourceSense("sub-b")
    sense_b_src = _FakeSourceSense("sense-b", sub_senses=(sub_b_src,))

    src_type = _FakeLexRefType(type_guid, _MAPPING_TYPE_COLLECTION)
    src_rel = _FakeSourceLexReference(
        rel_guid, src_type, targets=[sense_a_src, sub_b_src])
    src_type.MembersOC.Add(src_rel)

    move_factory = _FakeLexReferenceFactory()
    move_ctx, preview_ctx = _new_ctx_pair(
        ref_types_src=[src_type],
        ref_types_move_tgt=[_FakeLexRefType(type_guid, _MAPPING_TYPE_COLLECTION)],
        ref_types_preview_tgt=[_FakeLexRefType(type_guid, _MAPPING_TYPE_COLLECTION)],
        rel_factory=move_factory)
    move_dropped, preview_dropped = [], []
    move_cache, preview_cache = {}, {}

    # --- sense A copied+registered+discovered FIRST (mirrors
    # categories.py's own top-level-sense registration order) ---
    sense_a_move = _NewSense("sense-a-new")
    move_ctx._copy_set["sense-a"] = sense_a_move
    categories.reproduce_all_lexical_relations(move_ctx, _TAG, move_cache, move_dropped)
    preview_ctx._copy_set["sense-a"] = True
    categories.plan_all_lexical_relations(preview_ctx, preview_cache, preview_dropped)

    # --- sense B's sub-sense copied LATER, via the real recursive walk
    # (registers + fires its own discovery trigger internally -- owned.py
    # ~747-749/1033-1035) ---
    sense_b_move = _NewSense("sense-b-new")
    owned.walk_owned_children(
        sense_b_src, sense_b_move, move_ctx, _TAG, move_cache, move_dropped)
    owned.plan_owned_object_decisions(
        sense_b_src, preview_ctx, preview_cache, preview_dropped)
    sub_b_move = sense_b_move.SensesOS[0]

    move_rels = list(move_ctx.target_handle.Cache.LangProject.LexDbOA
                      .ReferencesOA.PossibilitiesOS[0].MembersOC)
    assert len(move_rels) == 1
    assert list(move_rels[0].TargetsRS) == [sense_a_move, sub_b_move]
    assert not any(
        r.item_guid == "sub-b" and "not in copy set" in r.reason for r in move_dropped)
    assert not any(
        r.item_guid == "sub-b" and "not in copy set" in r.reason
        for r in preview_dropped)


# ============================================================================
# Test 3 -- PAIR relation, 2 members copied at different times: reproduced
# EXACTLY ONCE, no stale "reduced below minimum" record left behind.
# ============================================================================

def test_pair_relation_members_copied_at_different_times_reproduces_once_no_stale_drop():
    """A PAIR relation whose 2 members are copied at different times must
    end up reproduced exactly once, with both members, and NO leftover
    "reduced below minimum" `DroppedItemRecord` once the second member
    arrives and completes it. Driven entirely through
    `reproduce_all_lexical_relations`/`plan_all_lexical_relations`, called
    once per simulated copy point.

    Already GREEN (T031 hybrid fix): member 1 alone triggers the pair's
    structural-minimum check (< 2 copied) -- drops the WHOLE relation
    ("reduced below minimum") and is deliberately NOT cached so a later,
    fuller call can still succeed. Member 2's later call DOES succeed and
    creates the relation, and `_evaluate_lexical_relation`'s own retraction
    removes the earlier "below minimum" drop record for this same relation
    GUID.
    """
    type_guid, rel_guid = "type-pair", "rel-pair"
    m1_src, m2_src = _FakeMember("pair-m1"), _FakeMember("pair-m2")
    m1_move, m2_move = _FakeMember("pair-m1"), _FakeMember("pair-m2")

    src_type = _FakeLexRefType(type_guid, _MAPPING_TYPE_PAIR)
    src_rel = _FakeSourceLexReference(rel_guid, src_type, targets=[m1_src, m2_src])
    src_type.MembersOC.Add(src_rel)

    move_factory = _FakeLexReferenceFactory()
    move_ctx, preview_ctx = _new_ctx_pair(
        ref_types_src=[src_type],
        ref_types_move_tgt=[_FakeLexRefType(type_guid, _MAPPING_TYPE_PAIR)],
        ref_types_preview_tgt=[_FakeLexRefType(type_guid, _MAPPING_TYPE_PAIR)],
        rel_factory=move_factory)
    move_dropped, preview_dropped = [], []
    move_cache, preview_cache = {}, {}

    # --- member 1 copied first: pair below minimum, whole relation dropped ---
    move_ctx._copy_set["pair-m1"] = m1_move
    categories.reproduce_all_lexical_relations(move_ctx, _TAG, move_cache, move_dropped)
    preview_ctx._copy_set["pair-m1"] = True
    categories.plan_all_lexical_relations(preview_ctx, preview_cache, preview_dropped)

    # --- member 2 copied later: pair now complete ---
    move_ctx._copy_set["pair-m2"] = m2_move
    categories.reproduce_all_lexical_relations(move_ctx, _TAG, move_cache, move_dropped)
    preview_ctx._copy_set["pair-m2"] = True
    categories.plan_all_lexical_relations(preview_ctx, preview_cache, preview_dropped)

    assert len(move_factory.create_calls) == 1
    move_rels = list(move_ctx.target_handle.Cache.LangProject.LexDbOA
                      .ReferencesOA.PossibilitiesOS[0].MembersOC)
    assert len(move_rels) == 1
    assert list(move_rels[0].TargetsRS) == [m1_move, m2_move]
    assert not any("below minimum" in getattr(r, "reason", "") for r in move_dropped)
    assert not any("below minimum" in getattr(r, "reason", "") for r in preview_dropped)


# ============================================================================
# Test 4 -- genuinely-absent member reported EXACTLY ONCE, no double-count,
# alongside a completeness fix for the other two members.
# ============================================================================

def test_genuinely_absent_member_reported_exactly_once_not_duplicated():
    """A 3-member COLLECTION relation where member 3 is NEVER copied must
    end up with exactly ONE `DroppedItemRecord` total once members 1 and 2
    (copied at different times) both land -- member 3's genuine absence
    reported once, no stale/duplicate record for members 1 or 2. Driven
    through `reproduce_all_lexical_relations`, called once per copy point.

    Already GREEN: the first final-pass call (member 1 only) reports BOTH
    member 2 and member 3 as missing; the second call (member 2 now copied)
    retracts member 2's drop and leaves only member 3's genuine one.
    """
    type_guid, rel_guid = "type-triple", "rel-triple"
    m1_src, m2_src, m3_src = (
        _FakeMember("tri-m1"), _FakeMember("tri-m2"), _FakeMember("tri-m3"))
    m1_move, m2_move = _FakeMember("tri-m1"), _FakeMember("tri-m2")

    src_type = _FakeLexRefType(type_guid, _MAPPING_TYPE_COLLECTION)
    src_rel = _FakeSourceLexReference(
        rel_guid, src_type, targets=[m1_src, m2_src, m3_src])
    src_type.MembersOC.Add(src_rel)

    move_factory = _FakeLexReferenceFactory()
    move_ctx, _preview_ctx = _new_ctx_pair(
        ref_types_src=[src_type],
        ref_types_move_tgt=[_FakeLexRefType(type_guid, _MAPPING_TYPE_COLLECTION)],
        ref_types_preview_tgt=[_FakeLexRefType(type_guid, _MAPPING_TYPE_COLLECTION)],
        rel_factory=move_factory)
    move_dropped = []
    move_cache = {}

    move_ctx._copy_set["tri-m1"] = m1_move
    categories.reproduce_all_lexical_relations(move_ctx, _TAG, move_cache, move_dropped)

    move_ctx._copy_set["tri-m2"] = m2_move
    categories.reproduce_all_lexical_relations(move_ctx, _TAG, move_cache, move_dropped)

    assert len(move_dropped) == 1
    assert move_dropped[0].item_guid == "tri-m3"
    assert "not in copy set" in move_dropped[0].reason
    move_rels = list(move_ctx.target_handle.Cache.LangProject.LexDbOA
                      .ReferencesOA.PossibilitiesOS[0].MembersOC)
    assert list(move_rels[0].TargetsRS) == [m1_move, m2_move]


# ============================================================================
# Test 5 -- each relation evaluated EXACTLY ONCE (no duplicate relation, no
# duplicate member) no matter how many of its members independently trigger
# discovery, including a redundant re-trigger after full completion.
# ============================================================================

def test_relation_evaluated_exactly_once_regardless_of_trigger_count():
    """A 2-member COLLECTION relation's discovery/reproduction is driven
    THREE times via `reproduce_all_lexical_relations` (once per member's own
    copy point, plus one redundant call for the SAME, already-complete
    copy_set) -- must still create exactly ONE `ILexReference`, with each
    member appearing exactly ONCE in `TargetsRS` (never re-added).

    Already GREEN: the first call (member 1 only) caches a PARTIAL relation.
    The second call (member 2 now copied) unions member 2 in. The third,
    redundant call (copy_set unchanged) hits the cache and adds nothing new
    -- `resolver_cache`'s GUID-keyed dedup makes this safe regardless of how
    many times the final pass happens to run.
    """
    type_guid, rel_guid = "type-retrigger", "rel-retrigger"
    m1_src, m2_src = _FakeMember("re-m1"), _FakeMember("re-m2")
    m1_move, m2_move = _FakeMember("re-m1"), _FakeMember("re-m2")

    src_type = _FakeLexRefType(type_guid, _MAPPING_TYPE_COLLECTION)
    src_rel = _FakeSourceLexReference(rel_guid, src_type, targets=[m1_src, m2_src])
    src_type.MembersOC.Add(src_rel)

    move_factory = _FakeLexReferenceFactory()
    move_ctx, _preview_ctx = _new_ctx_pair(
        ref_types_src=[src_type],
        ref_types_move_tgt=[_FakeLexRefType(type_guid, _MAPPING_TYPE_COLLECTION)],
        ref_types_preview_tgt=[_FakeLexRefType(type_guid, _MAPPING_TYPE_COLLECTION)],
        rel_factory=move_factory)
    move_dropped = []
    move_cache = {}

    move_ctx._copy_set["re-m1"] = m1_move
    categories.reproduce_all_lexical_relations(move_ctx, _TAG, move_cache, move_dropped)

    move_ctx._copy_set["re-m2"] = m2_move
    categories.reproduce_all_lexical_relations(move_ctx, _TAG, move_cache, move_dropped)

    # Redundant re-run of the final pass, after the relation is (or should
    # be) already complete -- copy_set is unchanged from the previous call.
    categories.reproduce_all_lexical_relations(move_ctx, _TAG, move_cache, move_dropped)

    assert len(move_factory.create_calls) == 1
    move_rels = list(move_ctx.target_handle.Cache.LangProject.LexDbOA
                      .ReferencesOA.PossibilitiesOS[0].MembersOC)
    assert len(move_rels) == 1
    assert list(move_rels[0].TargetsRS) == [m1_move, m2_move]
    assert not any("not in copy set" in getattr(r, "reason", "") for r in move_dropped)


# ============================================================================
# Tests 6-8 (NEW, this cycle) -- SOURCE-ORDER TargetsRS regardless of
# copy/discovery order. RED against the current hybrid for all three: the
# cache-hit union-append in `reproduce_lexical_relation` lands new members
# at the END of whatever partial `TargetsRS` an earlier, less-complete
# final-pass call already created, not at their correct source position.
# ============================================================================

_MAPPING_TYPE_SEQUENCE = 14  # kmtEntryOrSenseSequence -- ordered, open-ended
_MAPPING_TYPE_TREE = 13      # kmtEntryOrSenseTree -- ordered, root = TargetsRS[0]


def test_collection_relation_targetsrs_in_source_order_regardless_of_copy_order():
    """Source relation members [A, B, C] (COLLECTION) must reproduce as
    target TargetsRS [A, B, C] even though the closure copies them in the
    order A, C, B (final pass invoked once per copy point, mirroring how
    the SAME `reproduce_lexical_relation` cache is exercised whether the
    caller is a per-member trigger or repeated final-pass calls).

    RED today: stage 1 (A only) creates TargetsRS=[A]. Stage 2 (+C) unions
    C onto the end -> [A, C]. Stage 3 (+B) unions B onto the end -> [A, C,
    B] -- WRONG source order (B belongs between A and C).
    """
    type_guid, rel_guid = "type-coll-order", "rel-coll-order"
    a_src, b_src, c_src = _FakeMember("ord-a"), _FakeMember("ord-b"), _FakeMember("ord-c")
    a_mv, b_mv, c_mv = _FakeMember("ord-a"), _FakeMember("ord-b"), _FakeMember("ord-c")

    src_type = _FakeLexRefType(type_guid, _MAPPING_TYPE_COLLECTION)
    src_rel = _FakeSourceLexReference(rel_guid, src_type, targets=[a_src, b_src, c_src])
    src_type.MembersOC.Add(src_rel)

    move_factory = _FakeLexReferenceFactory()
    move_ctx, preview_ctx = _new_ctx_pair(
        ref_types_src=[src_type],
        ref_types_move_tgt=[_FakeLexRefType(type_guid, _MAPPING_TYPE_COLLECTION)],
        ref_types_preview_tgt=[_FakeLexRefType(type_guid, _MAPPING_TYPE_COLLECTION)],
        rel_factory=move_factory)
    move_dropped, preview_dropped = [], []
    move_cache, preview_cache = {}, {}

    # Copy order: A, then C, then B -- deliberately NOT source order.
    for guid, mv in (("ord-a", a_mv), ("ord-c", c_mv), ("ord-b", b_mv)):
        move_ctx._copy_set[guid] = mv
        categories.reproduce_all_lexical_relations(move_ctx, _TAG, move_cache, move_dropped)
        preview_ctx._copy_set[guid] = True
        categories.plan_all_lexical_relations(preview_ctx, preview_cache, preview_dropped)

    move_rels = list(move_ctx.target_handle.Cache.LangProject.LexDbOA
                      .ReferencesOA.PossibilitiesOS[0].MembersOC)
    assert len(move_rels) == 1
    # Completeness (already correct today): all three present, no false drop.
    assert {m.Guid for m in move_rels[0].TargetsRS} == {"ord-a", "ord-b", "ord-c"}
    assert not any("not in copy set" in getattr(r, "reason", "") for r in move_dropped)
    assert not any("not in copy set" in getattr(r, "reason", "") for r in preview_dropped)
    # SOURCE-ORDER assertion -- RED today (comes out [A, C, B]).
    assert list(move_rels[0].TargetsRS) == [a_mv, b_mv, c_mv]


def test_sequence_relation_targetsrs_in_source_order_regardless_of_copy_order():
    """Same defect as the COLLECTION test above, for a SEQUENCE-kind
    relation (MappingType 14, `kmtEntryOrSenseSequence`) -- semantically
    ORDER-defined by definition, so a misordered TargetsRS is a correctness
    bug, not just cosmetic. Also asserts Preview/Move convergence: Preview's
    own read-only probe of the CURRENT, fully-settled copy_set (via the
    shared `_evaluate_lexical_relation` core -- never used here to DRIVE
    reproduction, only to inspect what order SHOULD result) always computes
    correct source order, proving the divergence lives in Move's stateful
    `TargetsRS.Add()` accumulation, not in the shared decision core.
    """
    type_guid, rel_guid = "type-seq-order", "rel-seq-order"
    a_src, b_src, c_src = _FakeMember("seq-a"), _FakeMember("seq-b"), _FakeMember("seq-c")
    a_mv, b_mv, c_mv = _FakeMember("seq-a"), _FakeMember("seq-b"), _FakeMember("seq-c")

    src_type = _FakeLexRefType(type_guid, _MAPPING_TYPE_SEQUENCE)
    src_rel = _FakeSourceLexReference(rel_guid, src_type, targets=[a_src, b_src, c_src])
    src_type.MembersOC.Add(src_rel)

    move_factory = _FakeLexReferenceFactory()
    move_ctx, preview_ctx = _new_ctx_pair(
        ref_types_src=[src_type],
        ref_types_move_tgt=[_FakeLexRefType(type_guid, _MAPPING_TYPE_SEQUENCE)],
        ref_types_preview_tgt=[_FakeLexRefType(type_guid, _MAPPING_TYPE_SEQUENCE)],
        rel_factory=move_factory)
    move_dropped, preview_dropped = [], []
    move_cache, preview_cache = {}, {}

    for guid, mv in (("seq-a", a_mv), ("seq-c", c_mv), ("seq-b", b_mv)):
        move_ctx._copy_set[guid] = mv
        categories.reproduce_all_lexical_relations(move_ctx, _TAG, move_cache, move_dropped)
        # Preview's copy_set stores the GUID itself (not a bare `True`
        # placeholder) so the read-only probe below can show actual member
        # identity, not just membership count.
        preview_ctx._copy_set[guid] = guid
        categories.plan_all_lexical_relations(preview_ctx, preview_cache, preview_dropped)

    # Preview convergence probe: the shared core, evaluated fresh against
    # the NOW fully-settled copy_set, always recomputes correct source
    # order -- this is a read-only assertion helper, not a reproduction
    # driver (its own drop-list side effects are discarded via a scratch list).
    probe_dropped: list = []
    evaluated = categories._evaluate_lexical_relation(src_rel, preview_ctx, probe_dropped)
    assert evaluated is not None
    _rel_guid, _target_type, correct_order = evaluated
    assert correct_order == ["seq-a", "seq-b", "seq-c"]

    move_rels = list(move_ctx.target_handle.Cache.LangProject.LexDbOA
                      .ReferencesOA.PossibilitiesOS[0].MembersOC)
    assert len(move_rels) == 1
    assert not any("not in copy set" in getattr(r, "reason", "") for r in move_dropped)
    assert not any("not in copy set" in getattr(r, "reason", "") for r in preview_dropped)
    # SOURCE-ORDER assertion -- RED today: Move's real TargetsRS diverges
    # from the correct order the shared core always computes.
    assert list(move_rels[0].TargetsRS) == [a_mv, b_mv, c_mv]


def test_tree_relation_targetsrs_in_source_order_regardless_of_copy_order():
    """Same defect for a TREE-kind relation (MappingType 13,
    `kmtEntryOrSenseTree`): root/parent (TargetsRS[0], the ROOT source
    member) copied FIRST (required -- a tree without its root is
    incoherent and never reproduced at all), then the two children copied
    OUT of source order (Y before X, though source order is [ROOT, X, Y]).
    """
    type_guid, rel_guid = "type-tree-order", "rel-tree-order"
    root_src, x_src, y_src = (
        _FakeMember("tree-root"), _FakeMember("tree-x"), _FakeMember("tree-y"))
    root_mv, x_mv, y_mv = (
        _FakeMember("tree-root"), _FakeMember("tree-x"), _FakeMember("tree-y"))

    src_type = _FakeLexRefType(type_guid, _MAPPING_TYPE_TREE)
    src_rel = _FakeSourceLexReference(
        rel_guid, src_type, targets=[root_src, x_src, y_src])
    src_type.MembersOC.Add(src_rel)

    move_factory = _FakeLexReferenceFactory()
    move_ctx, preview_ctx = _new_ctx_pair(
        ref_types_src=[src_type],
        ref_types_move_tgt=[_FakeLexRefType(type_guid, _MAPPING_TYPE_TREE)],
        ref_types_preview_tgt=[_FakeLexRefType(type_guid, _MAPPING_TYPE_TREE)],
        rel_factory=move_factory)
    move_dropped, preview_dropped = [], []
    move_cache, preview_cache = {}, {}

    # Copy order: ROOT (required first), then Y, then X -- NOT source order.
    for guid, mv in (("tree-root", root_mv), ("tree-y", y_mv), ("tree-x", x_mv)):
        move_ctx._copy_set[guid] = mv
        categories.reproduce_all_lexical_relations(move_ctx, _TAG, move_cache, move_dropped)
        preview_ctx._copy_set[guid] = True
        categories.plan_all_lexical_relations(preview_ctx, preview_cache, preview_dropped)

    move_rels = list(move_ctx.target_handle.Cache.LangProject.LexDbOA
                      .ReferencesOA.PossibilitiesOS[0].MembersOC)
    assert len(move_rels) == 1
    assert not any("root member not copied" in getattr(r, "reason", "") for r in move_dropped)
    assert not any("not in copy set" in getattr(r, "reason", "") for r in move_dropped)
    assert not any("not in copy set" in getattr(r, "reason", "") for r in preview_dropped)
    # SOURCE-ORDER assertion -- RED today (comes out [ROOT, Y, X]).
    assert list(move_rels[0].TargetsRS) == [root_mv, x_mv, y_mv]


# ============================================================================
# Test 9 (NEW, this cycle) -- relation trigger-eligible member is an
# ALLOMORPH: no per-member incremental trigger exists for allomorphs at all
# (categories.py's allomorph loop registers `copy_set[a_guid] = True` but
# never calls a per-member lexrel discovery function for it) -- the final
# pass must still discover and reproduce it. Already GREEN.
# ============================================================================

def test_relation_with_allomorph_member_discovered_by_final_pass_only():
    """A relation whose sole `TargetsRS` member is an allomorph (`IMoForm`)
    is registered into `ctx._copy_set` exactly the way
    `categories._plan_entry_reference_decisions`'s allomorph loop does
    (`copy_set[a_guid] = True`, no discovery call alongside it) -- proving
    the final pass is the ONLY path that ever finds this relation."""
    type_guid, rel_guid = "type-allo", "rel-allo"
    allo_src = _FakeMember("allo-1")
    allo_mv = _FakeMember("allo-1")

    src_type = _FakeLexRefType(type_guid, _MAPPING_TYPE_COLLECTION)
    src_rel = _FakeSourceLexReference(rel_guid, src_type, targets=[allo_src])
    src_type.MembersOC.Add(src_rel)

    move_factory = _FakeLexReferenceFactory()
    move_ctx, preview_ctx = _new_ctx_pair(
        ref_types_src=[src_type],
        ref_types_move_tgt=[_FakeLexRefType(type_guid, _MAPPING_TYPE_COLLECTION)],
        ref_types_preview_tgt=[_FakeLexRefType(type_guid, _MAPPING_TYPE_COLLECTION)],
        rel_factory=move_factory)
    move_dropped, preview_dropped = [], []
    move_cache, preview_cache = {}, {}

    # Mirrors categories.py's allomorph loop: register into copy_set, no
    # per-member discovery call alongside it (none exists for allomorphs).
    move_ctx._copy_set["allo-1"] = allo_mv
    preview_ctx._copy_set["allo-1"] = True

    # ONLY the final pass ever runs for this member.
    categories.reproduce_all_lexical_relations(move_ctx, _TAG, move_cache, move_dropped)
    categories.plan_all_lexical_relations(preview_ctx, preview_cache, preview_dropped)

    move_rels = list(move_ctx.target_handle.Cache.LangProject.LexDbOA
                      .ReferencesOA.PossibilitiesOS[0].MembersOC)
    assert len(move_rels) == 1
    assert list(move_rels[0].TargetsRS) == [allo_mv]
    assert not any("not in copy set" in getattr(r, "reason", "") for r in move_dropped)
    assert not any("not in copy set" in getattr(r, "reason", "") for r in preview_dropped)


# ============================================================================
# Note for the final-pass implementer (per task instructions -- not a test):
#
# `tests/unit/test_subsense_copy_set.py`'s Test 2
# (`test_relation_with_sense_and_subsense_members_reproduces_without_false_
# drop`) pre-registers the top-level sense into `ctx._copy_set` BEFORE
# calling `owned.walk_owned_children` (its own comment: "matches
# production's own convention... entry/each top-level sense into
# `ctx._copy_set` BEFORE discovering/reproducing"). That is true for a
# SINGLE sense's own processing order, but it masks the CROSS-sense/
# cross-entry ordering this file's Test 2 exercises instead (a sub-sense
# under a DIFFERENT, LATER-processed sense). Once the single-final-pass
# redesign lands, `test_subsense_copy_set.py`'s pre-registration is no
# longer load-bearing (a final pass evaluates after `ctx._copy_set` has
# fully settled regardless of registration order) and MAY be left as-is
# (it still documents the single-sense case correctly) or simplified to
# register via the real call order like this file's tests do -- either is
# acceptable; it should NOT be used as a template for new ordering-
# sensitive fixtures going forward.
# ============================================================================
