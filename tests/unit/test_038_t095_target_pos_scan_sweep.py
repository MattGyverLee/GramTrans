"""T095 -- the four target-POS lookups that were not `_resolve_target_pos`.

T094 swept every call site of `_resolve_target_pos` and pinned the sweep
structurally (`test_no_production_call_site_is_two_positional`). The pin greps
for the RESOLVER. Four sites never called it: they scanned
`target.POS.GetAll(recursive=True)` open-coded, compared GUIDs, and returned
None on a miss -- so the pin could not see them, and neither could the audit
that produced it.

**One of them stated the premise out loud.** `_stash_feature_category_links`
documented its key as *"`{target_pos_guid: [feature_guid, ...]}` -- GUIDs are
preserved on transfer so target_pos_guid == source pos guid"*. That sentence
was true until T091 taught the planner to REUSE a destination category matched
by natural key rather than duplicate it, and it is the whole of this defect.

MEASURED on `Ngoreme FLEx` (T094's own run, artifacts
`_snapshots/census-038-t094-ngoreme.json` /
`_run_reports/038-after-ngoreme-report.json`): two `Skip(DEPENDENCY_UNRESOLVED)`
on `GRAM_CATEGORIES` -- `pos_guid=c46c8242-... not in target after
categories+features transfer` and the same for `ff5c5e07-...` -- both of them
categories the run had deliberately reused. Each loses its `InflectableFeatsRC`
wiring, and it costs **0 shortfall**: a reference collection is not a counted
object class, so no census row moves and `total_shortfall` reads clean. A
predicate scoped to counted classes cannot see this, which is T087's blind spot
one layer out and why this needed a filing rather than a census row.

WHY THE OTHER THREE ARE LATENT ON THIS PAIR AND NOT LATENT IN GENERAL:
Ngoreme's `MoStemName` row is 0 -> 0 so the stem-name site has nothing to lose
today, and no census row is bound to `ExceptionFeaturesOC`. A corpus with stem
names under a starter-named category would lose them silently-except-for-a-Skip.

COVERAGE HONESTY. These run against duck-typed fakes, as T094's do, so what is
pinned is the RESOLUTION rule. `stem_names_execute_action` needs live LCM
factories and is covered by the structural pin plus a source-reading assertion
rather than by a fake that could not reach it -- the same treatment T094 gave
`_create_msa_for_closure`.
"""
from __future__ import annotations

import ast
import json
import pathlib
from types import SimpleNamespace

import pytest

from gramtrans.Lib import categories as cat_mod
from gramtrans.Lib import matcher as matcher_mod
from gramtrans.Lib.models import (
    GrammarCategory,
    RunContext,
    Skip,
    SkipReason,
    WSMapping,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src" / "gramtrans" / "Lib"
ROSTER_035 = (
    REPO_ROOT / "specs" / "035-fullsweep-fidelity" / "contracts"
    / "natural-key-identity-roster.json"
)
EXTENSION_038 = (
    REPO_ROOT / "specs" / "038-transfer-fidelity-gaps" / "contracts"
    / "natural-key-roster-extension.json"
)

SRC_ANAL, TGT_ANAL = 302, 402
SRC_VERN, TGT_VERN = 301, 401

SRC_POS_G = "c46c8242-1111-4111-8111-cccccccccccc"
DST_POS_G = "d1ffe4e4-2222-4222-8222-dddddddddddd"
FEAT_G = "fea70001-3333-4333-8333-ffffffffffff"
VAL_G = "va100002-4444-4444-8444-aaaaaaaaaaaa"


# ---------------------------------------------------------------------------
# Fakes -- the same shapes T094's sweep file uses, kept local so this file's
# coverage stays identifiable and does not import another test module.
# ---------------------------------------------------------------------------

class _Ts:
    def __init__(self, text):
        self.Text = text


class _MultiString:
    def __init__(self, by_handle):
        self._by_handle = dict(by_handle)

    def get_String(self, ws_handle):
        return _Ts(self._by_handle.get(ws_handle))


class _Coll(list):
    def Add(self, item):
        self.append(item)


class _Pos:
    def __init__(self, guid, name=None, ws_handle=None):
        self.guid = guid
        self.Guid = guid
        self.ClassName = "PartOfSpeech"
        self.Name = _MultiString({ws_handle: name} if ws_handle else {})
        self.Owner = None
        self.InflectableFeatsRC = _Coll()
        self.ExceptionFeaturesOC = _Coll()
        self.StemNamesOC = _Coll()
        self.InflectionClassesOC = _Coll()


class _Feat:
    def __init__(self, guid):
        self.guid = guid
        self.Guid = guid
        self.ClassName = "FsFeatDefn"


class _PosAccessor:
    def __init__(self, poses):
        self._poses = list(poses)

    def GetAll(self, recursive=False):
        return list(self._poses)


class _Handle:
    """A project handle. `objects` feeds `get_object_by_guid`, which is the
    offline stand-in for the LCM object repository -- deliberately NOT holding
    the destination category, because the whole case under test is a category
    the source GUID cannot find."""

    def __init__(self, poses, vern, anal, objects=()):
        self.POS = _PosAccessor(poses)
        self.Cache = SimpleNamespace(DefaultAnalWs=anal)
        self._vern = vern
        self._anal = anal
        self._objects = {str(g).lower(): o for g, o in objects}

    def get_object_by_guid(self, guid):
        return self._objects.get(str(guid).lower())

    def GetDefaultVernacularWSHandle(self):
        return self._vern

    def GetDefaultAnalysisWSHandle(self):
        return self._anal


def _ctx(source, target):
    ctx = RunContext(
        source_handle=source,
        source_project_name="Src",
        source_project_path=r"C:\p\Src",
        target_handle=target,
        target_project_name="Tgt",
        target_project_path=r"C:\p\Tgt",
        run_id="GT-20260824-000000",
        started_at="2026-08-24T00:00:00",
    )
    object.__setattr__(ctx, "_exec_skips", [])
    object.__setattr__(ctx, "_ws_map", None)
    return ctx


def _appended_roster(tmp_path):
    base = json.loads(ROSTER_035.read_text(encoding="utf-8"))
    ext = json.loads(EXTENSION_038.read_text(encoding="utf-8"))
    base["entries"] = list(base["entries"]) + list(ext["proposed_entries"])
    path = tmp_path / "natural-key-identity-roster.json"
    path.write_text(json.dumps(base), encoding="utf-8")
    return str(path)


@pytest.fixture
def admitted(tmp_path):
    matcher_mod.reset_natural_key_roster_cache(_appended_roster(tmp_path))
    yield
    matcher_mod.reset_natural_key_roster_cache(None)


@pytest.fixture
def guids_are_lowercase_attrs(monkeypatch):
    monkeypatch.setattr(
        cat_mod, "_guid_str_from",
        lambda obj: str(getattr(obj, "guid", "") or "").lower())


def _reused_pair(objects=()):
    """THE INPUT THE TREE COULD NOT PRODUCE BEFORE T091: a source `Noun` and a
    destination `Noun` sharing a NAME and not a GUID."""
    src = _Pos(SRC_POS_G, "Noun", SRC_ANAL)
    dst = _Pos(DST_POS_G, "Noun", TGT_ANAL)
    source = _Handle([src], SRC_VERN, SRC_ANAL)
    target = _Handle([dst], TGT_VERN, TGT_ANAL, objects=objects)
    return src, dst, source, target


# ===========================================================================
# The helper itself
# ===========================================================================

def test_the_helper_finds_a_reused_category_the_guid_cannot(
    admitted, guids_are_lowercase_attrs,
):
    """Identity finds nothing (the destination GUID is not the source's) and
    the natural key finds the category the planner reused."""
    src, dst, source, target = _reused_pair()
    got = cat_mod._target_pos_for_source_guid(
        _ctx(source, target), target, SRC_POS_G)
    assert got is dst


def test_the_helper_prefers_identity(admitted, guids_are_lowercase_attrs):
    """IDENTITY FIRST, ALWAYS (FR-001). A destination category carrying the
    source GUID wins even when a differently-GUIDed same-name one exists --
    inverting the two would let a name collision overwrite a category a GUID
    had already correctly identified."""
    src = _Pos(SRC_POS_G, "Noun", SRC_ANAL)
    same_guid = _Pos(SRC_POS_G, "Noun", TGT_ANAL)
    other = _Pos(DST_POS_G, "Noun", TGT_ANAL)
    source = _Handle([src], SRC_VERN, SRC_ANAL)
    target = _Handle([other, same_guid], TGT_VERN, TGT_ANAL)
    got = cat_mod._target_pos_for_source_guid(
        _ctx(source, target), target, SRC_POS_G)
    assert got is same_guid


def test_the_helper_scans_the_source_when_the_object_is_not_passed(
    admitted, guids_are_lowercase_attrs,
):
    """The key is the category's NAME, and a GUID string cannot supply it.
    Three of the four swept sites hold only the GUID, so "identity failed" is
    not an answer worth giving without fetching the object and trying."""
    src, dst, source, target = _reused_pair()
    assert cat_mod._target_pos_for_source_guid(
        _ctx(source, target), target, SRC_POS_G, src_pos=None) is dst


def test_the_helper_still_answers_none_for_a_category_that_is_absent(
    admitted, guids_are_lowercase_attrs,
):
    """A sweep that turned real dependency failures into silent successes
    would pass every "it resolves now" test and be worse than the defect. A
    differently-NAMED destination is not this category."""
    src = _Pos(SRC_POS_G, "Noun", SRC_ANAL)
    dst = _Pos(DST_POS_G, "Verb", TGT_ANAL)
    source = _Handle([src], SRC_VERN, SRC_ANAL)
    target = _Handle([dst], TGT_VERN, TGT_ANAL)
    assert cat_mod._target_pos_for_source_guid(
        _ctx(source, target), target, SRC_POS_G) is None


def test_the_helper_answers_none_for_an_empty_guid(admitted):
    """No GUID means no identity AND no natural key -- the same contract
    `_resolve_target_pos` states for itself."""
    _, _, source, target = _reused_pair()
    assert cat_mod._target_pos_for_source_guid(
        _ctx(source, target), target, "") is None


# ===========================================================================
# Site 1 -- `_run_infl_feature_link_pass`, the measured loss
# ===========================================================================

def _link_ctx(source, target, links):
    ctx = _ctx(source, target)
    object.__setattr__(ctx, "_feature_category_links", dict(links))
    return ctx


def test_the_link_pass_wires_a_reused_category(
    admitted, guids_are_lowercase_attrs,
):
    """THE TWO NGOREME SKIPS. `InflectableFeatsRC` membership is what was
    lost: the binding names the SOURCE category, the destination holds it
    under another GUID, and a GUID-only lookup called that absent."""
    feat = _Feat(FEAT_G)
    src, dst, source, target = _reused_pair(objects=((FEAT_G, feat),))
    ctx = _link_ctx(source, target, {SRC_POS_G: [FEAT_G]})
    skips = cat_mod._run_infl_feature_link_pass(ctx, target)
    assert skips == []
    assert list(dst.InflectableFeatsRC) == [feat]


def test_the_link_pass_prefers_the_object_repository(
    admitted, guids_are_lowercase_attrs,
):
    """The pre-T095 path is untouched when it works: a GUID-preserved category
    resolves through `get_object_by_guid` and the fallback never runs. That is
    what makes this change additive for every run where T091 reused nothing."""
    feat = _Feat(FEAT_G)
    kept = _Pos(SRC_POS_G, "Noun", TGT_ANAL)
    source = _Handle([_Pos(SRC_POS_G, "Noun", SRC_ANAL)], SRC_VERN, SRC_ANAL)
    target = _Handle([], TGT_VERN, TGT_ANAL,
                     objects=((FEAT_G, feat), (SRC_POS_G, kept)))
    ctx = _link_ctx(source, target, {SRC_POS_G: [FEAT_G]})
    assert cat_mod._run_infl_feature_link_pass(ctx, target) == []
    assert list(kept.InflectableFeatsRC) == [feat]


def test_the_link_pass_still_skips_a_category_that_really_is_absent(
    admitted, guids_are_lowercase_attrs,
):
    """VR-4: deferred, never a dangling write. The Skip is the report, and
    removing it would be the phantom-success direction."""
    feat = _Feat(FEAT_G)
    source = _Handle([_Pos(SRC_POS_G, "Noun", SRC_ANAL)], SRC_VERN, SRC_ANAL)
    target = _Handle([_Pos(DST_POS_G, "Verb", TGT_ANAL)], TGT_VERN, TGT_ANAL,
                     objects=((FEAT_G, feat),))
    ctx = _link_ctx(source, target, {SRC_POS_G: [FEAT_G]})
    skips = cat_mod._run_infl_feature_link_pass(ctx, target)
    assert [s.reason for s in skips] == [SkipReason.DEPENDENCY_UNRESOLVED]
    assert skips[0].category is GrammarCategory.GRAM_CATEGORIES


def test_the_link_pass_is_still_idempotent_on_a_reused_category(
    admitted, guids_are_lowercase_attrs,
):
    """VR-3. The membership guard has to survive the new resolution path, or
    a second run doubles every wiring it repaired."""
    feat = _Feat(FEAT_G)
    src, dst, source, target = _reused_pair(objects=((FEAT_G, feat),))
    ctx = _link_ctx(source, target, {SRC_POS_G: [FEAT_G]})
    cat_mod._run_infl_feature_link_pass(ctx, target)
    cat_mod._run_infl_feature_link_pass(ctx, target)
    assert list(dst.InflectableFeatsRC) == [feat]


def test_the_stash_records_the_source_guid(guids_are_lowercase_attrs):
    """The key this pass reads. It was DOCUMENTED as a target GUID on the
    premise that the two are equal; it has always been read off the source
    object, and after T091 the two are not equal."""
    src = _Pos(SRC_POS_G, "Noun", SRC_ANAL)
    src.InflectableFeatsRC = _Coll([_Feat(FEAT_G)])
    ctx = _ctx(_Handle([src], SRC_VERN, SRC_ANAL),
               _Handle([], TGT_VERN, TGT_ANAL))
    object.__setattr__(ctx, "_feature_category_links", {})
    object.__setattr__(ctx, "_selection", SimpleNamespace(
        is_on=lambda cat: True, leaf_picks_for=lambda cat: None))
    cat_mod._stash_feature_category_links(src, ctx)
    assert ctx._feature_category_links == {SRC_POS_G: [FEAT_G]}


# ===========================================================================
# Sites 2 and 3 -- the exception-feature twins (G6: plan and execute agree)
# ===========================================================================

def _exception_ctx(source, target):
    return _ctx(source, target)


def test_the_exception_feature_planner_sees_a_value_already_wired_on_a_reused_category(
    admitted, guids_are_lowercase_attrs,
):
    """THE PREVIEW HALF. A GUID-only lookup answers "no such POS", the
    already-present check never runs, and the plan promises an ADD the
    executor then finds already wired -- a preview that overstates its own
    run, which is the G6 shape T094 met at `can_create_inflection_class`."""
    val = _Feat(VAL_G)
    src, dst, source, target = _reused_pair()
    dst.ExceptionFeaturesOC.append(val)
    out = cat_mod.exception_features_plan_action(
        (SRC_POS_G, val), _exception_ctx(source, target), WSMapping())
    assert isinstance(out, Skip)
    assert out.reason is SkipReason.ALREADY_PRESENT_BY_GUID


def test_the_exception_feature_planner_still_plans_a_value_that_is_not_wired(
    admitted, guids_are_lowercase_attrs,
):
    """The default path, on the same reused category: the POS resolves, the
    value is not on it, and the action stands."""
    val = _Feat(VAL_G)
    src, dst, source, target = _reused_pair()
    out = cat_mod.exception_features_plan_action(
        (SRC_POS_G, val), _exception_ctx(source, target), WSMapping())
    assert not isinstance(out, Skip)
    assert out.source_guid == f"{SRC_POS_G}::{VAL_G}"


# ===========================================================================
# The structural pin -- what T094's could not see
# ===========================================================================
#
# T094's pin greps for `_resolve_target_pos`. An OPEN-CODED
# `target.POS.GetAll(recursive=True)` scan is invisible to it, which is
# exactly how these four sites survived a sweep that was otherwise complete.
# This pin enumerates the open-coded scans instead, and requires every one to
# be named with a reason -- so a new one fails the suite until somebody
# classifies it rather than joining the class silently.

#: `module: {function: why this target-POS scan is not a resolution}`.
#: NOT a suppression list: every entry states why a GUID scan is the right
#: question at that site, or names the task that will answer it.
_ALLOWED_TARGET_POS_SCANS = {
    "categories.py": {
        "_target_iter":
            "the candidate SCOPE handed to `_plan_natural_key_match` -- this "
            "is the enumeration the key matches against, not a lookup",
        "gram_categories_execute_action":
            "the verb-vertical collision guard: 'did THIS RUN already create "
            "this GUID', which is a question about identity by construction",
        "stem_names_plan_action":
            "scans every category's StemNamesOC for a STEM NAME guid; the "
            "category is walked, not resolved",
    },
    "conflict.py": {
        "_find_target_pos_by_guid":
            "callers pass a plan item's own `target_guid`, which is already "
            "the destination's GUID -- see T106",
    },
    "merge_preview.py": {
        "_find_target_pos_by_guid":
            "merge-preview finder; owner GUIDs reach it from the plan -- T106",
        "_find_target_gram_cat_by_guid":
            "merge-preview finder over the same accessor -- T106",
    },
    "preview.py": {
        "_target_has_pos_guid":
            "a presence probe on a GUID; T106 measures whether its callers "
            "mean 'is this category present' instead",
        "_find_pos_by_guid":
            "owner lookup behind `_target_has_template_guid` / "
            "`_target_has_slot_guid` -- T106",
    },
    "transfer.py": {
        "_find_target_pos_by_guid":
            "six callers, some passing a destination GUID and some a source "
            "one; separating them is T106",
        "_execute_overwrite":
            "the SLOTS fallback scans every category's affix slots for a SLOT "
            "guid; the category is walked, not resolved",
    },
}


def _target_pos_scans():
    """Every `target.POS.GetAll(...)` in production, by module and function.

    AST rather than regex: the receiver name is what separates a target scan
    from a source one, and the enclosing function is a stabler address than a
    line number -- T095's own filing named line numbers that had already
    drifted by ~90 lines when it was picked up.
    """
    found = {}
    for path in sorted(SRC_DIR.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        stack = []

        class _V(ast.NodeVisitor):
            def visit_FunctionDef(self, node):
                stack.append(node.name)
                self.generic_visit(node)
                stack.pop()

            def visit_AsyncFunctionDef(self, node):  # pragma: no cover
                self.visit_FunctionDef(node)

            def visit_Call(self, node):
                fn = node.func
                if (isinstance(fn, ast.Attribute) and fn.attr == "GetAll"
                        and isinstance(fn.value, ast.Attribute)
                        and fn.value.attr == "POS"
                        and isinstance(fn.value.value, ast.Name)
                        and fn.value.value.id == "target"):
                    found.setdefault(path.name, set()).add(
                        stack[-1] if stack else "<module>")
                self.generic_visit(node)

        _V().visit(tree)
    return found


def test_no_unclassified_open_coded_target_pos_scan_exists():
    """T095's claim, as a fact about the tree.

    The four sites this task swept are gone from this set. Everything left is
    named with a reason, and a NEW open-coded scan -- the way this defect
    comes back, and it comes back silently -- fails here until it is either
    routed through `_target_pos_for_source_guid` or explained.
    """
    found = _target_pos_scans()
    unclassified = sorted(
        (module, fn)
        for module, fns in found.items()
        for fn in fns
        if fn not in _ALLOWED_TARGET_POS_SCANS.get(module, {})
    )
    assert unclassified == [], (
        "these open-coded `target.POS.GetAll(...)` scans resolve a category "
        "without consulting the natural key, and nothing says why: %r"
        % (unclassified,))


def test_the_four_swept_sites_no_longer_scan_the_target():
    """The other direction, named site by site, so a revert is loud."""
    found = _target_pos_scans().get("categories.py", set())
    for swept in ("stem_names_execute_action",
                  "exception_features_plan_action",
                  "exception_features_execute_action",
                  "_run_infl_feature_link_pass"):
        assert swept not in found, swept


def test_the_pin_can_see_the_scans_that_remain():
    """Guard against the pin passing because it found nothing -- the failure
    mode a source-reading test actually has (T094 added the same guard to its
    own pin for the same reason)."""
    found = _target_pos_scans()
    assert sum(len(v) for v in found.values()) >= 10, found
    assert set(found) == set(_ALLOWED_TARGET_POS_SCANS), (
        sorted(found), sorted(_ALLOWED_TARGET_POS_SCANS))


def test_the_swept_sites_pass_the_source_object_where_they_have_one():
    """`stem_names_execute_action` cannot be reached by a host-free fake (it
    needs `IMoStemNameFactory`), so what is asserted is what T094 asserted for
    `_create_msa_for_closure`: the source object is CARRIED to the resolver
    rather than discarded one line before the call."""
    text = (SRC_DIR / "categories.py").read_text(encoding="utf-8")
    start = text.index("def stem_names_execute_action(")
    body = text[start:text.index("\ndef ", start + 10)]
    assert "src_owner_pos = pos_obj" in body
    assert "_target_pos_for_source_guid(" in body
    assert "src_pos=src_owner_pos" in body
