"""Issue #172 live gate -- a POS created by dependency closure gets its
InflectableFeatsRC links through the single link pass.

WRITE PATH: writes ONLY the throwaway project ``Target`` (restored headlessly
from a known backup before every test and again at the end). The source
``Mbugwe LizzieHC practice`` is opened READ-ONLY. ``Esperanto`` and every other
project are never touched.

Skips unless FLEXLIBS_REQUIRE_LIVE=1. When it is set, an unavailable LCM
FAILS rather than skips.

Run:
    set FLEXLIBS_REQUIRE_LIVE=1 && python -m pytest \
        tests/integration/test_issue172_closure_pos_inflfeats_live.py -v -s

Two proofs:

1. ``test_execute_time_closure_create_links_features`` drives the exact
   function the issue is about, `categories.resolve_or_create_target_pos`
   (the execute-time creator closure paths use, e.g. an allomorph's
   MsEnvPartOfSpeechRA), against the live LCM inside a real Move. No natural
   source project here carries a MsEnvPartOfSpeechRA, so the call is injected
   just before the link pass; everything else (factory create, GUID preserved,
   stash, link pass, read-back) is the production code on live objects.
2. ``test_planned_pull_in_closure_still_links`` is the regression guard for
   the plan-time pull-in (INFLECTION_CLASSES pulls in its owner POS).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

_LIVE = os.environ.get("FLEXLIBS_REQUIRE_LIVE") == "1"
if not _LIVE:
    pytest.skip("FLEXLIBS_REQUIRE_LIVE != 1; live write-path gate not requested.",
                allow_module_level=True)

SOURCE_NAME = "Mbugwe LizzieHC practice"        # READ-ONLY
TARGET_NAME = "Target"                          # the ONLY project this module writes
TARGET_PATH = "C:/ProgramData/SIL/FieldWorks/Projects/Target/Target.fwdata"
BACKUP_NAME = "Target 2026-07-06 0218.fwbackup"

if str(Path(__file__).parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent))

_REPO = Path(__file__).resolve().parents[2]
_BACKUP_DIRS = (
    _REPO / "backups",
    Path("D:/Github/_Projects/_LEX/GramTrans/backups"),
)


def _backup_path() -> Path:
    for d in _BACKUP_DIRS:
        p = d / BACKUP_NAME
        if p.is_file():
            return p
    pytest.fail("[FAIL] backup %r not found under %s" % (BACKUP_NAME, _BACKUP_DIRS))


def _restore() -> None:
    assert TARGET_NAME == "Target"
    from harness.restore import restore_target
    restore_target(TARGET_NAME, backup_path=_backup_path())


@pytest.fixture(autouse=True)
def _restore_around():
    import flexicon
    import gramtrans
    print("[LIVE] gramtrans=%s flexicon=%s" % (gramtrans.__file__, flexicon.__file__))
    _restore()
    yield
    _restore()


def _sel(*cats):
    from gramtrans.Lib.models import GrammarCategory, Selection

    def _transform(_full):
        return Selection(categories={getattr(GrammarCategory, c): True for c in cats})
    return _transform


def _open_ro(name: str):
    from gramtrans.Lib.flexinit import ensure_flex_initialized
    ensure_flex_initialized()
    from flexicon import FLExProject
    proj = FLExProject()
    proj.OpenProject(projectName=name, writeEnabled=False)
    return proj


def _pos_index(name: str) -> dict:
    """{pos guid: (pos name, frozenset(feature guids))} via a read-only open."""
    from SIL.LCModel import ICmObject, IPartOfSpeech
    proj = _open_ro(name)
    try:
        out = {}
        for pos in proj.POS.GetAll(recursive=True):
            c = IPartOfSpeech(pos.concrete if hasattr(pos, "concrete") else pos)
            out[str(ICmObject(c).Guid).lower()] = (
                c.Name.BestAnalysisAlternative.Text,
                frozenset(str(ICmObject(f).Guid).lower()
                          for f in c.InflectableFeatsRC))
        return out
    finally:
        proj.CloseProject()


def _feature_guids(name: str) -> set:
    proj = _open_ro(name)
    try:
        return {str(f.Guid).lower() if hasattr(f, "Guid") else str(f).lower()
                for f in proj.InflectionFeatures.FeatureGetAll()}
    finally:
        proj.CloseProject()


def _infl_drops(report) -> list:
    return [d for d in report.dropped_items if d.field_name == "InflectableFeatsRC"]


def test_execute_time_closure_create_links_features(monkeypatch):
    from harness import full_run
    from gramtrans.Lib import categories

    src_index = _pos_index(SOURCE_NAME)
    tgt_index = _pos_index(TARGET_NAME)
    tgt_names = {n.lower() for n, _ in tgt_index.values()}
    # a feature-bearing source POS the Target has neither by GUID nor by name,
    # so resolve_or_create_target_pos CREATES it (identity and natural key miss)
    candidates = sorted(
        g for g, (n, feats) in src_index.items()
        if feats and g not in tgt_index and n.lower() not in tgt_names)
    assert candidates, "[SETUP] every feature-bearing source POS already in Target"
    victim = candidates[0]
    victim_name, victim_feats = src_index[victim]
    print("[LIVE] victim POS %s (%s) with %d inflectable features"
          % (victim[:8], victim_name, len(victim_feats)))

    # Features must already exist in the target when the POS is closure-created
    # (the cycle-2 boundary: this fix links to existing features, it never
    # creates one). Run 1 seeds ONLY the features.
    full_run.run_full_transfer(SOURCE_NAME, TARGET_NAME, TARGET_PATH,
                               selection_transform=_sel("INFLECTION_FEATURES"))
    feats_before = _feature_guids(TARGET_NAME)
    assert victim_feats <= feats_before, "[SETUP] seed run did not land the features"
    assert victim not in _pos_index(TARGET_NAME)

    created = []
    real_pass = categories._run_infl_feature_link_pass

    def _inject_then_pass(context, target, tag=None):
        if not created:
            src_pos = next(p for p in context.source_handle.POS.GetAll(recursive=True)
                           if categories._guid_str_from(p) == victim)
            new_pos = categories.resolve_or_create_target_pos(
                context, src_pos, getattr(context, "_ws_map", None), tag)
            created.append(new_pos)
            plan = context._run_plan
            print("[LIVE] injected closure create -> %s ; link map entry=%s"
                  % (new_pos is not None,
                     plan.feature_category_links.get(victim)))
        return real_pass(context, target, tag)

    monkeypatch.setattr(categories, "_run_infl_feature_link_pass", _inject_then_pass)
    try:
        # INFLECTION_CLASSES: a real, small category so the run has actions and
        # the post-loop link pass runs; it does NOT select INFLECTION_FEATURES
        # or GRAM_CATEGORIES (the victim is created by closure only).
        plan, report = full_run.run_full_transfer(
            SOURCE_NAME, TARGET_NAME, TARGET_PATH,
            selection_transform=_sel("INFLECTION_CLASSES"))
    finally:
        monkeypatch.setattr(categories, "_run_infl_feature_link_pass", real_pass)

    assert created and created[0] is not None, "[FAIL] closure create did not happen"
    after = _pos_index(TARGET_NAME)
    feats_after = _feature_guids(TARGET_NAME)
    drops = [d for d in _infl_drops(report) if d.owner_guid.lower() == victim]
    print("[LIVE] after: victim features=%d (source %d) drops=%d features %d->%d"
          % (len(after.get(victim, ("", ()))[1]), len(victim_feats), len(drops),
             len(feats_before), len(feats_after)))
    assert victim in after, "[FAIL] victim POS absent after run"
    assert after[victim][1] == victim_feats, "[FAIL] features not linked"
    assert drops == [], "[FAIL] pairs still reported as drops: %r" % drops
    assert feats_after == feats_before, "[FAIL] a feature definition was created/edited"


def test_planned_pull_in_closure_still_links():
    """Regression guard: INFLECTION_CLASSES alone pulls in its owner POS at
    plan time; its pairs must link and none may be reported as drops."""
    from harness import full_run

    src_index = _pos_index(SOURCE_NAME)
    full_run.run_full_transfer(SOURCE_NAME, TARGET_NAME, TARGET_PATH,
                               selection_transform=_sel("INFLECTION_FEATURES"))
    feats_before = _feature_guids(TARGET_NAME)
    before = _pos_index(TARGET_NAME)

    plan, report = full_run.run_full_transfer(
        SOURCE_NAME, TARGET_NAME, TARGET_PATH,
        selection_transform=_sel("INFLECTION_CLASSES"))
    after = _pos_index(TARGET_NAME)
    pulled = [a for a in plan.actions if getattr(a, "pulled_in_by", ())]
    new_pos = {g for g in after if g not in before}
    print("[LIVE] pulled-in actions=%d new POS=%d drops=%d"
          % (len(pulled), len(new_pos), len(_infl_drops(report))))
    for g in new_pos:
        assert after[g][1] == src_index.get(g, ("", frozenset()))[1], (
            "[FAIL] closure-created POS %s lacks its inflectable features" % g[:8])
    assert _infl_drops(report) == [], "[FAIL] unexpected InflectableFeatsRC drops"
    assert _feature_guids(TARGET_NAME) == feats_before
