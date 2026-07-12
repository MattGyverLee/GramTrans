"""Write-first tests (feature 024, US3, FR-008) locking the DEFECT that the
incremental, per-copied-member/GUID-cached lexical-relation discovery in
`Lib/categories.py` (`_evaluate_lexical_relation`, `reproduce_lexical_
relation`, `plan_lexical_relation_decision`, `_reproduce_lex_relations_for_
member`/`_plan_lex_relations_for_member`) produces WRONG, PERMANENT results
for a multi-member relation whose members are copied at DIFFERENT times:

  * COLLECTION/SEQUENCE/TREE kinds: the FIRST discovery (fired the moment
    the FIRST member is copied) creates-and-CACHES a PARTIAL `ILexReference`
    (missing every member not yet copied) keyed by relation GUID
    (`_LEXREL_REPRODUCED_KEY`/`_LEXREL_PLANNED_KEY`). Every LATER discovery
    trigger (fired when a later member is copied) hits that cache and
    returns immediately -- the relation is never completed, and the
    `DroppedItemRecord` ("lexical-relation member not in copy set")
    recorded for the not-yet-copied member is NEVER retracted, becoming a
    permanent FALSE report for a member that WAS, in fact, copied.
  * PAIR/ASYMMETRIC-PAIR kinds: a FIRST discovery with < 2 members copied
    drops the WHOLE relation ("reduced below minimum") and is deliberately
    NOT cached (so a later, fuller discovery CAN still succeed) -- but the
    earlier "reduced below minimum" `DroppedItemRecord` is never retracted
    either, so a relation that ultimately reproduces successfully still
    carries a stale, phantom, contradictory drop record.

`categories.py` ~3522-3637 (`_evaluate_lexical_relation`, the shared
Preview/Move core), ~3640-3723 (`reproduce_lexical_relation`, Move, GUID
cache ~3669/3721), ~3726-3760 (`plan_lexical_relation_decision`, Preview,
own `_LEXREL_PLANNED_KEY` cache in the SAME `resolver_cache`), ~3798-3826
(`_reproduce_lex_relations_for_member`/`_plan_lex_relations_for_member`,
the per-member trigger). `Lib/owned.py` ~441-459 (`_register_copy_set`),
~463-519 (`_reproduce_lex_relations_for_recursed_child`/`_plan_lex_
relations_for_recursed_child` -- QC P1: a recursively-copied sub-sense is
now registered into `ctx._copy_set` AND given its own discovery trigger the
moment it is created, so the sub-sense-registration gap `test_subsense_
copy_set.py` was written against is already fixed; the tests below build on
that fix rather than re-testing it).

None of these tests pre-register a member into `ctx._copy_set` before the
timeline that copies it (unlike `test_subsense_copy_set.py`'s Test 2, which
pre-registers the top-level sense before calling `walk_owned_children` --
masking the real ordering where a top-level sense's OWN registration
(categories.py ~4022) happens AFTER its recursive sub-sense leg has already
run (~4004-4005) and after the sub-sense's own discovery trigger has
already fired (owned.py ~748-749). See the module-end note re: whether
that masking should be removed once the final-pass implementer lands.

This is a diagnostic/regression-locking file for the upcoming SINGLE
FINAL PASS redesign (replacing per-member incremental discovery). ALL
tests below MUST FAIL against current code and MUST PASS once discovery
runs as one pass over the fully-settled `ctx._copy_set` at the end of the
run. Do NOT implement the fix here.
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
    two must not diverge.

    FAILS TODAY (partial-cache bug): entry 1's discovery trigger fires
    while entry 2 is not yet copied -- creates+caches a relation with ONLY
    entry 1, permanently drops entry 2 as "not in copy set". Entry 2's OWN
    later discovery trigger hits the GUID cache and returns immediately,
    never adding entry 2 and never retracting its false drop.
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

    # --- entry 1 copied first ---
    move_ctx._copy_set["entry-1"] = e1_move
    categories._reproduce_lex_relations_for_member(
        e1_src, move_ctx, _TAG, move_cache, move_dropped)
    preview_ctx._copy_set["entry-1"] = True
    preview_rec_1 = categories._plan_lex_relations_for_member(
        e1_src, preview_ctx, preview_cache, preview_dropped)

    # --- entry 2 copied LATER (separate point in the closure) ---
    move_ctx._copy_set["entry-2"] = e2_move
    categories._reproduce_lex_relations_for_member(
        e2_src, move_ctx, _TAG, move_cache, move_dropped)
    preview_ctx._copy_set["entry-2"] = True
    preview_rec_2 = categories._plan_lex_relations_for_member(
        e2_src, preview_ctx, preview_cache, preview_dropped)

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
    and Preview. No member is pre-registered into `ctx._copy_set` outside
    the actual copy mechanism (`owned.walk_owned_children`/
    `plan_owned_object_decisions`) -- ordering is exactly as the real
    closure produces it.

    FAILS TODAY: sense A's discovery trigger fires before sense B's
    sub-sense exists at all -- partial-caches the relation with only sense
    A, permanently drops the sub-sense as "not in copy set" even after
    `walk_owned_children` copies and registers it (owned.py QC P1 fix) and
    fires its OWN discovery trigger, which hits the stale cache.
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
    categories._reproduce_lex_relations_for_member(
        sense_a_src, move_ctx, _TAG, move_cache, move_dropped)
    preview_ctx._copy_set["sense-a"] = True
    categories._plan_lex_relations_for_member(
        sense_a_src, preview_ctx, preview_cache, preview_dropped)

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
    arrives and completes it.

    FAILS TODAY (stale-drop bug): member 1 alone triggers the pair's
    structural-minimum check (< 2 copied) -- drops the WHOLE relation
    ("reduced below minimum"), deliberately NOT cached so a later, fuller
    attempt can still succeed. Member 2's later trigger DOES succeed and
    creates the relation -- but the earlier drop record is never retracted,
    so the successful relation coexists with a phantom "not reproduced"
    report about itself.
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
    categories._reproduce_lex_relations_for_member(
        m1_src, move_ctx, _TAG, move_cache, move_dropped)
    preview_ctx._copy_set["pair-m1"] = True
    categories._plan_lex_relations_for_member(
        m1_src, preview_ctx, preview_cache, preview_dropped)

    # --- member 2 copied later: pair now complete ---
    move_ctx._copy_set["pair-m2"] = m2_move
    categories._reproduce_lex_relations_for_member(
        m2_src, move_ctx, _TAG, move_cache, move_dropped)
    preview_ctx._copy_set["pair-m2"] = True
    categories._plan_lex_relations_for_member(
        m2_src, preview_ctx, preview_cache, preview_dropped)

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
    reported once, no stale/duplicate record for members 1 or 2.

    FAILS TODAY: member 1's trigger partial-caches the relation (only
    member 1 present) and reports BOTH member 2 and member 3 as missing.
    Member 2's later trigger hits the cache and never corrects anything --
    its "not in copy set" report survives forever alongside member 3's
    genuine one, so `dropped` ends up with 2 records instead of 1.
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
    categories._reproduce_lex_relations_for_member(
        m1_src, move_ctx, _TAG, move_cache, move_dropped)

    move_ctx._copy_set["tri-m2"] = m2_move
    categories._reproduce_lex_relations_for_member(
        m2_src, move_ctx, _TAG, move_cache, move_dropped)

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
    """A 2-member COLLECTION relation triggers discovery THREE times (once
    per member's own copy point, plus one redundant re-trigger for member 1
    after the relation is already complete) -- must still create exactly
    ONE `ILexReference`, with each member appearing exactly ONCE in
    `TargetsRS` (never re-added).

    FAILS TODAY: member 1's trigger caches a PARTIAL relation (member 1
    only). Member 2's trigger hits the cache and never adds member 2 --
    `TargetsRS` never reaches length 2. (The redundant third trigger
    already behaves safely today via the GUID cache -- this test locks
    that non-duplication guarantee wrong-side-up: this file's whole point
    is that today's cache-driven "safety" against duplication is bought at
    the cost of never allowing legitimate completion.)
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
    categories._reproduce_lex_relations_for_member(
        m1_src, move_ctx, _TAG, move_cache, move_dropped)

    move_ctx._copy_set["re-m2"] = m2_move
    categories._reproduce_lex_relations_for_member(
        m2_src, move_ctx, _TAG, move_cache, move_dropped)

    # Redundant re-trigger for member 1, after the relation is (or should
    # be) already complete.
    categories._reproduce_lex_relations_for_member(
        m1_src, move_ctx, _TAG, move_cache, move_dropped)

    assert len(move_factory.create_calls) == 1
    move_rels = list(move_ctx.target_handle.Cache.LangProject.LexDbOA
                      .ReferencesOA.PossibilitiesOS[0].MembersOC)
    assert len(move_rels) == 1
    assert list(move_rels[0].TargetsRS) == [m1_move, m2_move]
    assert not any("not in copy set" in getattr(r, "reason", "") for r in move_dropped)


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
