"""Follow-ups to PR #73 / #79: issues #75, #76, #77, #78, #80.

* #75 -- `WSChoice` / `WSKind` from the flat `models` and from
  `gramtrans.Lib.models` are different enum classes; a choice built from one
  path was silently not folded by the other.
* #76 -- GUID-less drop records (WritingSystem, ConfigView) used inconsistent
  identity fields, and `_attach_dropped_items` did no de-duplication.
* #77 -- gramtrans.py's lazy `from api import ...` had no package fallback.
* #78 -- severity on `DroppedItemRecord`; Preview predicts WS creates that
  Move cannot perform, and flags whole-index reversal drops as warnings.
* #80 -- two source reversal configs mapping to one target filename collided.

All host-free: no SIL.LCModel / pythonnet, no FLEx project.
"""
from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

import pytest

from gramtrans.Lib import api as api_mod
from gramtrans.Lib import config_views
from gramtrans.Lib import ws_mapping as pkg_ws_mapping
from gramtrans.Lib import models as pkg_models
from gramtrans.Lib.models import (
    DroppedItemRecord,
    RunContext,
    RunMode,
    RunPlan,
    RunReport,
    Selection,
    WSKind,
    WSMapping,
    WSMappingEntry,
    dropped_identity,
)
from gramtrans.Lib.report import render_text_summary, to_snapshot_json

# The flat module path the FlexTools host uses: `site.addsitedir(Lib/)`.
_LIB = str(Path(pkg_models.__file__).resolve().parent)
if _LIB not in sys.path:
    sys.path.append(_LIB)  # appended, so package imports still win elsewhere
try:
    import models as flat_models
except ImportError:  # pragma: no cover
    flat_models = None

_GRAMTRANS_PY = Path(pkg_models.__file__).resolve().parent.parent / "gramtrans.py"


# ============================================================================
# #75 -- enum identity across the two import paths
# ============================================================================

needs_flat = pytest.mark.skipif(
    flat_models is None or flat_models is pkg_models,
    reason="flat `models` not importable as a separate module here",
)


@needs_flat
def test_flat_and_package_enums_really_differ():
    """Guard: the bug only exists while the two classes are distinct."""
    assert flat_models.WSChoice.CREATE != pkg_models.WSChoice.CREATE


@needs_flat
@pytest.mark.parametrize("choice_name", ["CREATE", "MAP"])
def test_package_fold_accepts_flat_choices(choice_name):
    target = "etu" if choice_name == "MAP" else ""
    c = flat_models.WSMappingChoice(
        source_ws_id="mgz-fonipa",
        source_ws_kind=flat_models.WSKind.VERNACULAR,
        choice=getattr(flat_models.WSChoice, choice_name),
        target_ws_id=target,
    )
    m = pkg_ws_mapping.fold_choices_into_ws_mapping((c,), None)
    assert len(m.entries) == 1
    e = m.entries[0]
    assert e.create_in_target is (choice_name == "CREATE")
    # The entry's kind is THIS module's enum, so `== WSKind.VERNACULAR` holds.
    assert e.source_ws_kind == pkg_models.WSKind.VERNACULAR


@needs_flat
def test_flat_fold_accepts_package_choices():
    import ws_mapping as flat_ws_mapping
    c = pkg_models.WSMappingChoice(
        source_ws_id="mgz-fonipa", source_ws_kind=pkg_models.WSKind.ANALYSIS,
        choice=pkg_models.WSChoice.CREATE,
    )
    m = flat_ws_mapping.fold_choices_into_ws_mapping((c,), None)
    assert [e.create_in_target for e in m.entries] == [True]


@needs_flat
def test_fold_dedupes_across_import_paths():
    """A base-mapping entry keyed by one path's WSKind still blocks a choice
    for the same WS keyed by the other path's WSKind."""
    base = WSMapping(entries=(WSMappingEntry(
        source_ws_id="mgz", source_ws_kind=pkg_models.WSKind.VERNACULAR,
        target_ws_id="mgz"),))
    c = flat_models.WSMappingChoice(
        source_ws_id="mgz", source_ws_kind=flat_models.WSKind.VERNACULAR,
        choice=flat_models.WSChoice.CREATE,
    )
    m = pkg_ws_mapping.fold_choices_into_ws_mapping((c,), base)
    assert len(m.entries) == 1 and m.entries[0].create_in_target is False


def test_mapping_choice_validates_raw_values():
    c = pkg_models.WSMappingChoice(
        source_ws_id="x", source_ws_kind="vernacular", choice="map", target_ws_id="y")
    assert c.choice is pkg_models.WSChoice.MAP
    assert c.source_ws_kind is WSKind.VERNACULAR
    with pytest.raises(ValueError):
        pkg_models.WSMappingChoice(source_ws_id="x", source_ws_kind=WSKind.VERNACULAR,
                                   choice="map")  # MAP without a target


@needs_flat
def test_ensure_writing_systems_honours_flat_vernacular_kind(monkeypatch):
    calls = []

    class _Ops:
        def __init__(self, proj):
            pass

        def GetAll(self):  # noqa: N802
            return []

        def Exists(self, tag):  # noqa: N802
            return False

        def Create(self, tag, name, is_vernacular=True):  # noqa: N802
            calls.append((tag, is_vernacular))

    monkeypatch.setattr("flexicon.WritingSystemOperations", _Ops, raising=False)
    monkeypatch.setattr(api_mod, "_persist_without_close", lambda proj, what: None)
    entry = flat_models.WSMappingEntry(
        source_ws_id="mgz-fonipa", source_ws_kind=flat_models.WSKind.VERNACULAR,
        target_ws_id="mgz-fonipa", create_in_target=True)
    plan = type("P", (), {"ws_mapping": flat_models.WSMapping(entries=(entry,))})()
    api_mod._ensure_writing_systems(object(), None, plan, [])
    assert calls == [("mgz-fonipa", True)]


# ============================================================================
# #76 -- consistent identity for GUID-less drops, and dedupe on attach
# ============================================================================

def _cv(file, item="zz", field="writingSystem"):
    return DroppedItemRecord(owner_kind="ConfigView", owner_guid="", owner_label=file,
                             field_name=field, item_name=item, item_guid="",
                             reason="absent")


def test_ws_create_failure_has_no_fake_guid():
    rec = pkg_ws_mapping.ws_create_failure("mgz-fonipa", "boom")
    assert rec.owner_guid == "" and rec.item_guid == ""
    assert rec.owner_label == rec.item_name == "mgz-fonipa"
    assert api_mod._ws_create_failure("mgz-fonipa", "boom") == rec


def test_guidless_records_from_different_files_are_distinct():
    assert dropped_identity(_cv("a.fwdictconfig")) != dropped_identity(_cv("b.fwdictconfig"))
    assert dropped_identity(_cv("a.fwdictconfig")) == dropped_identity(_cv("a.fwdictconfig"))


def test_guided_record_identity_is_the_published_triple():
    rec = DroppedItemRecord(owner_kind="LexSense", owner_guid="o1", owner_label="x",
                            field_name="f", item_name="n", item_guid="i1", reason="r")
    assert dropped_identity(rec) == ("o1", "f", "i1")


def _report(dropped=()):
    ctx = RunContext(
        source_handle=object(), source_project_name="S", source_project_path="",
        target_handle=object(), target_project_name="T", target_project_path="",
        run_id="GT-20261015-120000", started_at="2026-10-15T12:00:00",
    )
    plan = RunPlan(context=ctx, selection=Selection(), ws_mapping=WSMapping(), actions=())
    return RunReport.build_from_plan(plan, RunMode.MOVE, extra_dropped_items=dropped)


def test_attach_dropped_items_dedupes():
    ws = pkg_ws_mapping.ws_create_failure("pt", "boom")
    report = _report(dropped=(_cv("a.fwdictconfig"),))
    out = api_mod._attach_dropped_items(
        report, [ws, ws, _cv("a.fwdictconfig"), _cv("b.fwdictconfig")])
    assert [d.owner_label for d in out.dropped_items] == [
        "a.fwdictconfig", "pt", "b.fwdictconfig"]


# ============================================================================
# #77 -- lazy api import in gramtrans.py has a package fallback
# ============================================================================

def test_lazy_api_import_has_package_fallback():
    tree = ast.parse(_GRAMTRANS_PY.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        body_mods = {n.module for n in node.body if isinstance(n, ast.ImportFrom)}
        if "api" not in body_mods:
            continue
        handler_mods = {
            n.module for h in node.handlers
            if isinstance(h.type, ast.Name) and h.type.id == "ImportError"
            for n in h.body if isinstance(n, ast.ImportFrom)
        }
        assert "gramtrans.Lib.api" in handler_mods
        return
    pytest.fail("no try/except ImportError around the lazy `from api import`")


def test_no_bare_lazy_flat_api_import():
    """Every `from api import` in gramtrans.py sits inside a try block."""
    tree = ast.parse(_GRAMTRANS_PY.read_text(encoding="utf-8"))
    guarded = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            for n in node.body:
                if isinstance(n, ast.ImportFrom) and n.module == "api":
                    guarded.add(id(n))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "api":
            assert id(node) in guarded, f"unguarded `from api import` at line {node.lineno}"


# ============================================================================
# #78 -- severity, Preview preflight, rendering
# ============================================================================

def test_severity_defaults_to_info_and_is_validated():
    assert _cv("a").severity == "info"
    with pytest.raises(ValueError):
        DroppedItemRecord(owner_kind="X", owner_guid="", owner_label="", field_name="f",
                          item_name="", item_guid="", reason="r", severity="fatal")


class _FakeWS:
    def __init__(self, ws_id):
        self.Id = ws_id


class _PreflightOps:
    """Read-only surface only: Create must never be called from Preview."""

    def __init__(self, proj):
        self.proj = proj

    def GetAll(self):  # noqa: N802
        if self.proj.get("active") is None:
            raise RuntimeError("unreadable")
        return [_FakeWS(i) for i in self.proj["active"]]

    def Exists(self, tag):  # noqa: N802
        return tag in self.proj["store"]

    def Create(self, *a, **k):  # noqa: N802
        raise AssertionError("Preview must not create writing systems")


def _create_mapping(*tags):
    return WSMapping(entries=tuple(
        WSMappingEntry(source_ws_id=t, source_ws_kind=WSKind.VERNACULAR,
                       target_ws_id=t, create_in_target=True) for t in tags))


@pytest.fixture()
def preflight_ops(monkeypatch):
    monkeypatch.setattr("flexicon.WritingSystemOperations", _PreflightOps, raising=False)


def test_preflight_predicts_stored_but_inactive(preflight_ops):
    target = {"store": ["etu", "mgz-fonipa"], "active": ["etu"]}
    recs = pkg_ws_mapping.preflight_ws_creates(
        target, _create_mapping("etu", "mgz-fonipa", "pt"))
    assert [(r.item_name, r.severity) for r in recs] == [("mgz-fonipa", "warning")]
    assert "not active" in recs[0].reason


def test_preflight_unverifiable_active_list(preflight_ops):
    target = {"store": ["mgz-fonipa"], "active": None}
    recs = pkg_ws_mapping.preflight_ws_creates(target, _create_mapping("mgz-fonipa"))
    assert len(recs) == 1 and "not verifiably active" in recs[0].reason


def test_preflight_matches_move_failure(preflight_ops, monkeypatch):
    """Preview predicts exactly the record Move then emits."""
    monkeypatch.setattr(api_mod, "_persist_without_close", lambda proj, what: None)
    target = {"store": ["mgz-fonipa"], "active": []}
    mapping = _create_mapping("mgz-fonipa")
    predicted = pkg_ws_mapping.preflight_ws_creates(target, mapping)
    failures = []
    plan = type("P", (), {"ws_mapping": mapping})()
    api_mod._ensure_writing_systems(target, None, plan, failures)
    assert predicted == failures


def test_preflight_is_fail_soft(monkeypatch):
    class _Broken:
        def __init__(self, proj):
            raise RuntimeError("no host")

    monkeypatch.setattr("flexicon.WritingSystemOperations", _Broken, raising=False)
    assert pkg_ws_mapping.preflight_ws_creates(object(), _create_mapping("x")) == []
    assert pkg_ws_mapping.preflight_ws_creates(None, _create_mapping("x")) == []
    assert pkg_ws_mapping.preflight_ws_creates(object(), WSMapping()) == []


def test_build_run_plan_carries_preflight_warnings(monkeypatch):
    from gramtrans.Lib import preview
    sentinel = pkg_ws_mapping.ws_create_failure("mgz-fonipa", "stored but not active")
    seen = {}

    def _fake_preflight(target, ws_mapping):
        seen["args"] = (target, ws_mapping)
        return [sentinel]

    monkeypatch.setattr(pkg_ws_mapping, "preflight_ws_creates", _fake_preflight)
    ctx = RunContext(
        source_handle=object(), source_project_name="S", source_project_path="",
        target_handle=object(), target_project_name="T", target_project_path="",
        run_id="GT-20261015-120000", started_at="2026-10-15T12:00:00",
    )
    mapping = _create_mapping("mgz-fonipa")
    plan = preview.build_run_plan(ctx, Selection(), mapping, object(), "TGT")
    assert seen["args"] == ("TGT", mapping)
    assert sentinel in plan.dropped_items


def test_render_flags_warnings_first():
    warn = pkg_ws_mapping.ws_create_failure("pt", "boom")
    lines = list(render_text_summary(_report(dropped=(_cv("a.fwdictconfig"), warn))))
    i = next(i for i, l in enumerate(lines) if "Dropped references" in l)
    assert "2 total, 1 warning(s)" in lines[i]
    assert lines[i + 1].lstrip().startswith("- [WARN] pt")
    assert "[WARN]" not in lines[i + 2]


def test_snapshot_json_severity_is_additive():
    import json
    warn = pkg_ws_mapping.ws_create_failure("pt", "boom")
    data = json.loads(to_snapshot_json(_report(dropped=(_cv("a.fwdictconfig"), warn))))
    info_row, warn_row = data["dropped_items"]
    assert "severity" not in info_row
    assert warn_row["severity"] == "warning"


def test_reversal_index_level_drops_are_warnings():
    src = (Path(pkg_models.__file__).parent / "reversals.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    index_records = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "DroppedItemRecord"
        and any(k.arg == "owner_kind" and getattr(k.value, "value", None) == "ReversalIndex"
                for k in n.keywords)
    ]
    assert index_records, "no ReversalIndex drop sites found"
    for call in index_records:
        sev = [k for k in call.keywords if k.arg == "severity"]
        assert sev and sev[0].value.value == "warning", f"line {call.lineno}"


# ============================================================================
# #80 -- reversal config filename collision
# ============================================================================

class _CVWSCollection:
    def __init__(self, ids):
        self._ids = list(ids)

    def GetAll(self):  # noqa: N802
        return [_FakeWS(i) for i in self._ids]


class _CVProject:
    def __init__(self, project_dir, ws_ids):
        self.ProjectFolder = str(project_dir)
        self.WritingSystems = _CVWSCollection(ws_ids)


def _rev_file(project_dir, ws):
    d = os.path.join(project_dir, "ConfigurationSettings", "ReversalIndex")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, f"{ws}.fwdictconfig"), "w", encoding="utf-8") as fh:
        fh.write(f'<?xml version="1.0" encoding="utf-8"?>\n'
                 f'<DictionaryConfiguration name="{ws}" writingSystem="{ws}" '
                 f'version="26" />\n')


def test_two_reversal_configs_onto_one_target_keep_one_and_report(tmp_path):
    _rev_file(tmp_path / "Src", "en")
    _rev_file(tmp_path / "Src", "en-x-old")
    src = _CVProject(tmp_path / "Src", ["en", "en-x-old"])
    tgt = _CVProject(tmp_path / "Tgt", ["en"])

    records = config_views.plan_config_views(src, tgt, ws_map={"en-x-old": "en"})

    rev = [r for r in records if r.kind == "ReversalIndex"]
    assert [r.filename for r in rev] == ["en.fwdictconfig"], \
        "the file already named for the target WS is kept"
    collision = [d for d in rev[0].missing_refs if d.field_name == "filename"]
    assert len(collision) == 1
    c = collision[0]
    assert c.owner_label == "en-x-old.fwdictconfig"
    assert c.severity == "warning"
    assert "en.fwdictconfig" in c.reason

    dropped = []
    config_views.apply_config_views(records, dropped)
    landed = os.listdir(tmp_path / "Tgt" / "ConfigurationSettings" / "ReversalIndex")
    assert landed == ["en.fwdictconfig"]
    with open(tmp_path / "Tgt" / "ConfigurationSettings" / "ReversalIndex"
              / "en.fwdictconfig", encoding="utf-8") as fh:
        assert 'name="en"' in fh.read()
    assert c in dropped


def test_collision_without_a_name_match_keeps_first(tmp_path):
    _rev_file(tmp_path / "Src", "en-x-a")
    _rev_file(tmp_path / "Src", "en-x-b")
    src = _CVProject(tmp_path / "Src", ["en-x-a", "en-x-b"])
    tgt = _CVProject(tmp_path / "Tgt", ["fr"])

    with pytest.raises(ValueError):
        # A 1:1 WSMapping can never send both here; plan_config_views takes a
        # raw dict, so exercise it directly below.
        WSMapping(entries=(
            WSMappingEntry("en-x-a", WSKind.ANALYSIS, "fr"),
            WSMappingEntry("en-x-b", WSKind.ANALYSIS, "fr"),
        ))
    records = config_views.plan_config_views(
        src, tgt, ws_map={"en-x-a": "fr", "en-x-b": "fr"})
    rev = [r for r in records if r.kind == "ReversalIndex"]
    assert [r.filename for r in rev] == ["en-x-a.fwdictconfig"]
    assert os.path.basename(rev[0].tgt_path) == "fr.fwdictconfig"
    assert any(d.owner_label == "en-x-b.fwdictconfig" for d in rev[0].missing_refs)


def test_no_collision_leaves_plan_untouched(tmp_path):
    _rev_file(tmp_path / "Src", "en")
    _rev_file(tmp_path / "Src", "fr")
    src = _CVProject(tmp_path / "Src", ["en", "fr"])
    tgt = _CVProject(tmp_path / "Tgt", ["en", "fr"])
    records = config_views.plan_config_views(src, tgt)
    assert sorted(r.filename for r in records) == ["en.fwdictconfig", "fr.fwdictconfig"]
    assert all(not r.missing_refs for r in records)
