"""T106 -- the seven target-POS finders whose callers mix source GUIDs with
destination ones.

T095 swept four open-coded target-POS scans in `categories.py` and widened
T094's pin into `test_038_t095_target_pos_scan_sweep.py`, which enumerates every
`target.POS.GetAll(...)` in production by AST. Re-deriving the count the way
T094 re-derived its own found seven more finders OUTSIDE `categories.py` -- in
`transfer.py`, `preview.py`, `merge_preview.py` and `conflict.py` -- and filed
them here rather than sweeping them blind.

**WHY A SEPARATE TASK: THE FIX IS NOT UNIFORM.** A caller that already holds the
plan's `target_guid` is CORRECT as it stands, and routing it through the natural
key would re-derive a decision Preview already made and recorded -- Principle
III, and worse, it could override a T091 reuse with a fresh name match. A caller
holding a SOURCE GUID has T095's defect exactly. Separating them is the task; a
blanket sweep would have been a regression dressed as a fix.

**THE COUNT, RE-DERIVED ONCE MORE.** The filing said "thirteen call sites"; the
tree holds SIXTEEN references across the seven finders. The classification:

  CORRECT_AS_IS (5) -- the GUID is already destination-side
    transfer.py       `_execute_overwrite` POS branch      `overwrite.target_guid`
    transfer.py       `_execute_overwrite` SLOTS fallback  walks POS for a SLOT guid
    merge_preview.py  `_PROPS_TABLE["pos"]`                one side per call
    merge_preview.py  `_PROPS_TABLE["gram_cat"]`           one side per call
    conflict.py       `collect_overwrite_conflicts`        `ow.target_guid`

  DEFECTIVE, SWEPT (8) -- the GUID is source-side
    transfer.py  `_execute_verb_vertical`        `_first_pos_guid(plan)`
    transfer.py  `_execute_layer3`               `src_verb_guid`
    transfer.py  `_execute_overwrite` TEMPLATE   `owner_guid` (source owner)
    transfer.py  `_execute_overwrite` SLOTS      `owner_guid` (source owner)
    transfer.py  `_execute_overwrite` MSA        `src_ia.PartOfSpeechRA`
    preview.py   `_plan_verb_vertical_inner`     `src_verb_guid`
    preview.py   `_check_msa_pos_excluded_lossy` source MSA's POS
    preview.py   `_emit_template` / slot probe   source owner GUID

  NOT SWEPT, DOCUMENTED (3)
    merge_preview.py  `_find_gap_object`               no source handle exists at
                                                       the call site; the miss is
                                                       absorbed by a fallback
    merge_preview.py  `_find_target_template_by_guid`  unreachable (`is_gap=True`)
    preview.py        `_find_pos_by_guid`              identity-pure by design

**ONE OF THE EIGHT WAS LIVE AND SILENT, AND IT IS THE POINT.** The MSA branch of
`_execute_overwrite` re-syncs `SlotsRC` by first resolving the owning category
from `src_ia.PartOfSpeechRA` -- a SOURCE object. On a miss the whole re-sync sat
behind `if tgt_pos is not None:` with **no else**: no Warning, no Skip, no
`DroppedItemRecord`. The MSA silently kept its old slot membership. And because
`SlotsRC` is a REFERENCE COLLECTION rather than a counted object class, no census
row moves and `total_shortfall` reads clean either way -- T087's blind spot at a
third site, and Principle I's exact shape. T106 routes it through the natural key
AND gives the residual miss a Warning, guarded on a non-empty source `SlotsRC` so
an MSA with nothing to sync cannot manufacture a phantom loss (the flexicon 4.5.1
shape CLAUDE.md records).

**THE OTHER SEVEN WERE LATENT, AND THE REASON MATTERS.** Six sit behind
`_VERB_VERTICAL_ENABLED = False` in both `transfer.py` and `preview.py` -- dead
in production today, live the moment anybody flips the flag to A/B the legacy
path. That is exactly the state in which a defect is cheapest to fix and most
likely to be forgotten, so they are swept now rather than allowlisted forward.

COVERAGE HONESTY. These run against duck-typed fakes, as T094's and T095's do,
so what is pinned is the RESOLUTION RULE plus the per-site classification as a
fact about the tree. `_execute_overwrite` needs live LCM factories and cannot be
reached by a host-free fake; it gets the treatment T094 gave
`_create_msa_for_closure` and T095 gave `stem_names_execute_action` -- a
source-reading assertion that the source object is CARRIED to the resolver rather
than discarded one line before the call.
"""
from __future__ import annotations

import ast
import json
import pathlib
import sys
import types
from types import SimpleNamespace

import pytest

from gramtrans.Lib import matcher as matcher_mod
from gramtrans.Lib import merge_preview as mp_mod
from gramtrans.Lib import preview as prev_mod
from gramtrans.Lib import transfer as xfer_mod

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

SRC_ANAL, TGT_ANAL = 502, 602
SRC_VERN, TGT_VERN = 501, 601

#: The post-T091 condition this whole task exists for: the SAME category,
#: present on both sides, under DIFFERENT GUIDs.
SRC_POS_G = "c46c8242-5555-4555-8555-cccccccccccc"
DST_POS_G = "d1ffe4e4-6666-4666-8666-dddddddddddd"
TPL_G = "7e307a71-7777-4777-8777-eeeeeeeeeeee"
SLOT_G = "510700aa-8888-4888-8888-aaaaaaaaaaaa"


# ---------------------------------------------------------------------------
# Fakes -- the shapes T095's sweep file uses, kept local so this file's coverage
# stays identifiable and it does not import another test module.
# ---------------------------------------------------------------------------

class _Ts:
    def __init__(self, text):
        self.Text = text


class _MultiString:
    def __init__(self, by_handle):
        self._by_handle = dict(by_handle)

    def get_String(self, ws_handle):
        return _Ts(self._by_handle.get(ws_handle))


class _Tpl:
    def __init__(self, guid):
        self.guid = guid
        self.Guid = guid
        self.ClassName = "MoInflAffixTemplate"


class _Slot:
    def __init__(self, guid):
        self.guid = guid
        self.Guid = guid
        self.ClassName = "MoInflAffixSlot"


class _Pos:
    def __init__(self, guid, name=None, ws_handle=None, templates=(), slots=()):
        self.guid = guid
        self.Guid = guid
        self.ClassName = "PartOfSpeech"
        self.Name = _MultiString({ws_handle: name} if ws_handle else {})
        self.Owner = None
        self.AffixTemplatesOS = list(templates)
        self.AffixSlotsOC = list(slots)


class _PosAccessor:
    def __init__(self, poses):
        self._poses = list(poses)

    def GetAll(self, recursive=False):
        return list(self._poses)

    def GetAffixSlots(self, pos):
        return list(getattr(pos, "AffixSlotsOC", ()))


class _MorphRules:
    @staticmethod
    def GetAllAffixTemplatesForPOS(pos):
        return list(getattr(pos, "AffixTemplatesOS", ()))


class _Handle:
    def __init__(self, poses, vern, anal):
        self.POS = _PosAccessor(poses)
        self.MorphRules = _MorphRules()
        self.Cache = SimpleNamespace(DefaultAnalWs=anal)
        self._vern = vern
        self._anal = anal

    def GetDefaultVernacularWSHandle(self):
        return self._vern

    def GetDefaultAnalysisWSHandle(self):
        return self._anal


def _appended_roster(tmp_path):
    base = json.loads(ROSTER_035.read_text(encoding="utf-8"))
    ext = json.loads(EXTENSION_038.read_text(encoding="utf-8"))
    base["entries"] = list(base["entries"]) + list(ext["proposed_entries"])
    path = tmp_path / "natural-key-identity-roster.json"
    path.write_text(json.dumps(base), encoding="utf-8")
    return str(path)


@pytest.fixture(autouse=True)
def offline_lcm():
    """`preview._guid_str` / `transfer._guid_str` lazy-import `ICmObject` and
    cast through it, unlike `categories._guid_str_from`, which grew a
    duck-typed branch. Rather than widen a production helper to suit a fake,
    stand up the offline `SIL.LCModel` stub these tests need -- the convention
    `test_031_infl_feature_linking.py` and `test_038_executor_match_basis.py`
    already use. `ICmObject(x)` returns `x`, so `.Guid` reads off the fake.
    """
    fake_lcm = types.ModuleType("SIL.LCModel")
    fake_lcm.ICmObject = lambda obj: obj
    fake_lcm.IPartOfSpeech = lambda obj: obj
    sys.modules.setdefault("SIL", types.ModuleType("SIL"))
    original = sys.modules.get("SIL.LCModel")
    sys.modules["SIL.LCModel"] = fake_lcm
    yield
    if original is None:
        sys.modules.pop("SIL.LCModel", None)
    else:
        sys.modules["SIL.LCModel"] = original


@pytest.fixture
def admitted(tmp_path):
    matcher_mod.reset_natural_key_roster_cache(_appended_roster(tmp_path))
    yield
    matcher_mod.reset_natural_key_roster_cache(None)


@pytest.fixture
def pair():
    """The post-T091 condition: `Verb` on both sides, different GUIDs."""
    src_pos = _Pos(SRC_POS_G, "Verb", SRC_ANAL)
    dst_pos = _Pos(DST_POS_G, "Verb", TGT_ANAL,
                   templates=[_Tpl(TPL_G)], slots=[_Slot(SLOT_G)])
    source = _Handle([src_pos], SRC_VERN, SRC_ANAL)
    target = _Handle([dst_pos], TGT_VERN, TGT_ANAL)
    return SimpleNamespace(source=source, target=target,
                           src_pos=src_pos, dst_pos=dst_pos)


# ===========================================================================
# 1. The resolution rule, both modules that gained a resolver
# ===========================================================================

def test_identity_alone_cannot_find_the_reused_category(pair):
    """THE DEFECT, stated as the premise every swept site relied on. This is
    not a bug in `_find_target_pos_by_guid` -- it answers its own question
    correctly. It is a bug in ASKING it with a source GUID."""
    assert xfer_mod._find_target_pos_by_guid(pair.target, SRC_POS_G) is None
    assert prev_mod._find_pos_by_guid(pair.target, SRC_POS_G) is None


def test_the_transfer_resolver_finds_it_by_natural_key(admitted, pair):
    """THE FIX. Identity fails, the roster-admitted key succeeds, and what it
    returns is the DESTINATION object under its own GUID."""
    got = xfer_mod._target_pos_for_source_guid(
        pair.target, SRC_POS_G, src_pos=pair.src_pos,
        source_handle=pair.source)
    assert got is not None
    assert str(got.Guid).lower() == DST_POS_G


def test_the_preview_resolver_finds_it_by_natural_key(admitted, pair):
    got = prev_mod._target_pos_for_source_guid(
        pair.target, SRC_POS_G, src_pos=pair.src_pos,
        source_handle=pair.source)
    assert got is not None
    assert str(got.Guid).lower() == DST_POS_G


@pytest.mark.parametrize("mod", [xfer_mod, prev_mod])
def test_the_resolver_is_additive_without_the_keywords(admitted, pair, mod):
    """The opt-in shape `_resolve_target_pos` and
    `owned._resolve_target_pos_by_guid` already use. A caller -- or a fake --
    that supplies neither keyword gets exactly the pre-038 identity answer, so
    landing this could not change behaviour anywhere it was not routed."""
    assert mod._target_pos_for_source_guid(pair.target, SRC_POS_G) is None


@pytest.mark.parametrize("mod", [xfer_mod, prev_mod])
def test_half_the_keywords_buy_nothing_and_say_so(admitted, pair, mod):
    """BOTH are required: the key is the category's `Name` (a GUID string
    cannot supply it) AND it is scoped to the source writing systems (only the
    source handle can supply those). A site that can reach one of them is not
    half-fixed, it is unfixed -- which is why `merge_preview._find_gap_object`
    is documented rather than given a `src_pos` that would merely look right."""
    assert mod._target_pos_for_source_guid(
        pair.target, SRC_POS_G, src_pos=pair.src_pos) is None
    assert mod._target_pos_for_source_guid(
        pair.target, SRC_POS_G, source_handle=pair.source) is None


def test_the_resolver_still_prefers_identity(admitted, pair):
    """Identity FIRST, key second. A destination GUID must never be re-decided
    by a name match -- that is the failure mode that makes the correct-as-is
    sites correct."""
    got = xfer_mod._target_pos_for_source_guid(
        pair.target, DST_POS_G, src_pos=pair.src_pos,
        source_handle=pair.source)
    assert got is not None and str(got.Guid).lower() == DST_POS_G


# ===========================================================================
# 2. The preview probes -- "is this CATEGORY present", answered correctly
# ===========================================================================
#
# Both callers of `_target_has_pos_guid` mean *is this category present*, not
# *is this exact object present*. One branches straight into "create a new
# category" (a duplicate) and the other tells the user "Entry X will have no
# Part of Speech" (a loss that will not happen). T093 drew this distinction for
# a different report; this is the same distinction at a planner.

def test_the_presence_probe_says_absent_without_the_keywords(pair):
    """PINNED AS THE OLD ANSWER, so the change below is deliberate rather than
    silent drift."""
    assert prev_mod._target_has_pos_guid(pair.target, SRC_POS_G) is False


def test_the_presence_probe_says_present_when_it_can_ask_properly(admitted, pair):
    assert prev_mod._target_has_pos_guid(
        pair.target, SRC_POS_G, src_pos=pair.src_pos,
        source_handle=pair.source) is True


def test_the_template_probe_no_longer_plans_a_duplicate(admitted, pair):
    """The destination already holds this template, under a category whose GUID
    is not the source's. Before T106 the probe said False and the planner
    emitted an ADD -- a DUPLICATE, the opposite direction from T095's lost item
    and the same root cause."""
    assert prev_mod._target_has_template_guid(
        pair.target, SRC_POS_G, TPL_G) is False
    assert prev_mod._target_has_template_guid(
        pair.target, SRC_POS_G, TPL_G,
        src_owner_pos=pair.src_pos, source_handle=pair.source) is True


def test_the_slot_probe_no_longer_plans_a_duplicate(admitted, pair):
    assert prev_mod._target_has_slot_guid(
        pair.target, SRC_POS_G, SLOT_G) is False
    assert prev_mod._target_has_slot_guid(
        pair.target, SRC_POS_G, SLOT_G,
        src_owner_pos=pair.src_pos, source_handle=pair.source) is True


def test_a_genuinely_absent_template_is_still_absent(admitted, pair):
    """The other direction, and the one that matters for a probe: resolving the
    OWNER by natural key must not make the probe say yes to a template the
    destination does not have. A probe that answers True too readily is how a
    real item stops being transferred."""
    assert prev_mod._target_has_template_guid(
        pair.target, SRC_POS_G, "00000000-0000-4000-8000-000000000000",
        src_owner_pos=pair.src_pos, source_handle=pair.source) is False


# ===========================================================================
# 3. The classification, as a fact about the tree
# ===========================================================================
#
# The task's deliverable is the SEPARATION, so the separation is what is
# pinned. A later sweep that "tidies" a correct-as-is site into the resolver
# fails here, and so does one that quietly reverts a swept site.

def _fn_source(module_name: str, fn_name: str) -> str:
    text = (SRC_DIR / module_name).read_text(encoding="utf-8")
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == fn_name:
            return ast.get_source_segment(text, node) or ""
    raise AssertionError("no function %s in %s" % (fn_name, module_name))


#: (module, function, how many times it must route through the source-aware
#: resolver). Addressed by enclosing FUNCTION rather than line number: T095's
#: own filing named line numbers that had already drifted ~90 lines.
_SWEPT_SITES = [
    ("transfer.py", "_execute_verb_vertical", 1),
    ("transfer.py", "_execute_layer3", 1),
    ("transfer.py", "_execute_overwrite", 3),
    ("preview.py", "_plan_verb_vertical_inner", 0),
]


@pytest.mark.parametrize("module_name,fn_name,count", _SWEPT_SITES)
def test_the_swept_sites_route_through_the_resolver(module_name, fn_name, count):
    body = _fn_source(module_name, fn_name)
    assert body.count("_target_pos_for_source_guid(") == count, fn_name


def test_the_msa_branch_carries_the_source_object_to_the_resolver():
    """T095's `stem_names_execute_action` assertion at a fourth site. The MSA
    branch HAS `pos_obj` -- the source category object -- and the defect class
    T094 named `_pos_guid_of` is keeping only its GUID. Assert it is carried."""
    body = _fn_source("transfer.py", "_execute_overwrite")
    assert "src_pos=pos_obj" in body
    assert "source_handle=source" in body


def test_the_msa_miss_is_reported_rather_than_silent():
    """Principle I. The pre-T106 code had `if tgt_pos is not None:` with NO
    else, so a resolution failure left `SlotsRC` stale and said nothing. A
    reference collection moves no census row, so nothing else would have caught
    it either."""
    body = _fn_source("transfer.py", "_execute_overwrite")
    assert "slot re-sync skipped" in body
    assert "elif len(list(src_ia.SlotsRC)) > 0:" in body, (
        "the warning must be guarded on the source actually HAVING slots to "
        "sync -- an unguarded warning manufactures a phantom loss, the "
        "flexicon 4.5.1 shape")


def test_the_destination_side_sites_stay_identity_only():
    """THE OTHER HALF OF THE TASK, and the half a blanket sweep would have got
    wrong. Each of these holds a GUID Preview already resolved on the
    destination side; re-deriving it from the name could OVERRIDE a recorded
    T091 reuse."""
    ow = _fn_source("transfer.py", "_execute_overwrite")
    assert "_find_target_pos_by_guid(target, tgt_guid)" in ow

    coc = _fn_source("conflict.py", "collect_overwrite_conflicts")
    assert "finder(target, ow.target_guid)" in coc
    assert "_target_pos_for_source_guid" not in coc

    mp = (SRC_DIR / "merge_preview.py").read_text(encoding="utf-8")
    assert '"pos": ("POS", _find_target_pos_by_guid, False, False),' in mp
    assert ('"gram_cat": ("GramCat", _find_target_gram_cat_by_guid, False, '
            'False),') in mp


def test_every_correct_as_is_site_says_why_in_the_code():
    """A classification that lives only in a task file is one refactor away
    from being lost. Each site that deliberately did NOT change carries the
    reason at the call site."""
    for module_name, fn_name in (("transfer.py", "_execute_overwrite"),
                                 ("conflict.py",
                                  "collect_overwrite_conflicts")):
        body = _fn_source(module_name, fn_name)
        assert "T106" in body, (module_name, fn_name)


# ===========================================================================
# 4. merge_preview -- the two sites that were NOT swept, and why that holds
# ===========================================================================

def test_the_gap_template_fallback_absorbs_the_owner_miss():
    """WHY `_find_gap_object` IS NOT SWEPT. `owner_guid` is a SOURCE category
    GUID and the owner lookup does miss post-T091 -- but the fallback scans
    every category for the template BY ITS OWN GUID, and a template lives under
    exactly one category, so the object is still found. The cost is a wider
    scan, not a wrong answer, and there is no source handle at this call site
    to give the natural key anyway.

    THE FALLBACK IS LOAD-BEARING. This test exists so that deleting it as
    "dead code" fails loudly instead of turning a slow path into a blank pane.
    """
    dst_pos = _Pos(DST_POS_G, "Verb", TGT_ANAL, templates=[_Tpl(TPL_G)])
    handle = _Handle([dst_pos], TGT_VERN, TGT_ANAL)
    found = mp_mod._find_gap_object(handle, "template", TPL_G, SRC_POS_G)
    assert found is not None
    assert str(found.Guid).lower() == TPL_G


def test_the_dead_template_finder_is_still_unreachable():
    """`_find_target_template_by_guid` holds a source-side owner lookup that
    CANNOT run: its table entry carries `is_gap=True` and `props_for` returns
    from the gap branch before dispatching to any `finder_fn`. Pinned so that
    if somebody flips it reachable, this task's classification is revisited
    rather than silently inherited."""
    entry = mp_mod._PROPS_TABLE["template"]
    _ops_attr, finder_fn, needs_owner, is_gap = entry
    assert finder_fn is mp_mod._find_target_template_by_guid
    assert needs_owner is True
    assert is_gap is True, (
        "template is no longer a gap category -- `_find_target_template_by_guid` "
        "is now reachable and its source-side owner lookup needs T106's "
        "classification applied")


# ===========================================================================
# 5. The gate that makes six of the eight latent
# ===========================================================================

def test_the_verb_vertical_gate_is_still_off_in_both_modules():
    """SIX of the eight swept sites are unreachable today because both modules
    hard-code `_VERB_VERTICAL_ENABLED = False`. That is WHY T095's live pair
    showed no loss from them and why this task needed its own instrument rather
    than a re-run -- the same reasoning that kept T092 out of T091.

    Pinned in both directions: the flag's value, and the fact that the two
    modules agree. `transfer.py` says to keep them in lockstep, and a pair that
    silently diverged would plan one way and execute another."""
    for module_name in ("transfer.py", "preview.py"):
        text = (SRC_DIR / module_name).read_text(encoding="utf-8")
        assert "_VERB_VERTICAL_ENABLED = False" in text, module_name
        assert "_VERB_VERTICAL_ENABLED = True" not in text, module_name
