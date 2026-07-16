"""Unit tests for the Part B `.fwdictconfig` configuration-view file copy
(`Lib/config_views.py`).

User Story 3 (T028-T030, spec 025-full-reversals):
  T028 -- enumerate + plan Add/Overwrite/Skip across Dictionary/ReversalIndex.
  T029 -- absent-reference scan (writingSystem / custom field / style).
  T030 -- apply: copy ADD/OVERWRITE with a pre-overwrite .gtbak backup, no
          I/O for SKIP, no file written during the plan pass, every
          missing_ref folded into the run `dropped` collector.

`resolve_config_dirs` derives its two directories from an LCM cache project
path (contracts/config-view-copy.md) -- these tests exercise
`plan_config_views`/`apply_config_views` (the testable core) over explicit
temp directories via a minimal duck-typed `_FakeProject` double that exposes
`ProjectFolder` (mirroring `Lib/ui/main_window.py._safe_path`'s
`ProjectPath`/`ProjectFilename`/`ProjectFolder` convention), plus optional
`WritingSystems`/`CustomFields`/`Styles` surfaces for the R9 reference scan
-- no live LCM project is needed (mirrors `tests/unit/test_ws_mapping_detect
.py`'s `_FakeProject`/`_FakeWS` fake-project pattern for the same reason).
"""
from __future__ import annotations

import os

import pytest

from gramtrans.Lib.config_views import (
    apply_config_views,
    plan_config_views,
    resolve_config_dirs,
)
from gramtrans.Lib.models import ConfigViewAction, DroppedItemRecord


# ============================================================================
# Fake project surfaces (mirrors tests/unit/test_ws_mapping_detect.py)
# ============================================================================

class _FakeWS:
    def __init__(self, id_):
        self.Id = id_


class _FakeWSCollection:
    def __init__(self, ids):
        self._ids = list(ids)

    def GetAll(self):
        return [_FakeWS(i) for i in self._ids]


class _FakeCustomFields:
    """Mirrors the live `CustomFieldOperations`: `GetAllFields` REQUIRES an
    `owner_class` argument (a no-arg call raises `TypeError`, exactly as it does
    against real flexicon -- the divergence that silently dropped custom-field
    missing-ref reporting until it was caught by the config-view live proof).
    Fixture fields are modeled as entry-level; class assignment is irrelevant to
    the R9 name-based scan, which unions labels across all owner classes."""

    _OWNER_CLASSES = ("LexEntry", "LexSense", "LexExampleSentence", "MoForm")

    def __init__(self, names):
        self._names = list(names)

    def GetAllFields(self, owner_class):
        if owner_class not in self._OWNER_CLASSES:
            raise ValueError("unknown owner class: %r" % (owner_class,))
        return list(self._names) if owner_class == "LexEntry" else []


class _FakeProject:
    """Minimal duck-typed project double. `ProjectFolder` is the on-disk
    project directory (no `ConfigurationSettings` suffix -- `resolve_config_
    dirs` appends that) -- `config_views._project_dir` tries this attribute
    name directly since it carries no file extension."""

    def __init__(self, project_dir, ws_ids=(), custom_fields=(), styles=()):
        self.ProjectFolder = str(project_dir)
        self.WritingSystems = _FakeWSCollection(ws_ids)
        self.CustomFields = _FakeCustomFields(custom_fields)
        self.Styles = list(styles)


class _BareFakeProject:
    """A project double exposing ONLY the directory accessor -- no
    WritingSystems/CustomFields/Styles at all -- to verify the R9 scan's
    "unknown, don't report" posture on a duck-typing gap (never a false
    positive when the target can't answer the question)."""

    def __init__(self, project_dir):
        self.ProjectFolder = str(project_dir)


# ============================================================================
# Fixture .fwdictconfig bodies
# ============================================================================

_SIMPLE_CONFIG = """<?xml version="1.0" encoding="utf-8"?>
<DictionaryConfiguration name="English" writingSystem="en" version="26">
  <ConfigurationItem name="Reversal Entry" style="Reversal-Normal" field="ReversalIndexEntry">
    <ConfigurationItem name="Reversal Form" field="ReversalForm">
      <WritingSystemOptions writingSystemType="reversal">
        <Option id="reversal" isEnabled="true" />
      </WritingSystemOptions>
    </ConfigurationItem>
  </ConfigurationItem>
</DictionaryConfiguration>
"""

_CONFIG_WITH_MISSING_REFS = """<?xml version="1.0" encoding="utf-8"?>
<DictionaryConfiguration name="French" writingSystem="fr" version="26">
  <ConfigurationItem name="Reversal Entry" style="Missing-Style" field="ReversalIndexEntry">
    <ConfigurationItem name="Custom Note" isCustomField="true" field="MyCustomField">
      <WritingSystemOptions writingSystemType="analysis">
        <Option id="analysis" isEnabled="true" />
      </WritingSystemOptions>
    </ConfigurationItem>
    <ConfigurationItem name="Reversal Form" field="ReversalForm">
      <WritingSystemOptions writingSystemType="reversal">
        <Option id="de" isEnabled="true" />
      </WritingSystemOptions>
    </ConfigurationItem>
  </ConfigurationItem>
</DictionaryConfiguration>
"""


def _write(directory, filename, body):
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, filename)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    return path


def _dict_dir(project_dir):
    return os.path.join(project_dir, "ConfigurationSettings", "Dictionary")


def _rev_dir(project_dir):
    return os.path.join(project_dir, "ConfigurationSettings", "ReversalIndex")


# ============================================================================
# T028 -- enumerate + plan Add/Overwrite/Skip
# ============================================================================

def test_plan_add_when_absent_in_target(tmp_path):
    src_dir = tmp_path / "Source"
    tgt_dir = tmp_path / "Target"
    _write(_rev_dir(src_dir), "en.fwdictconfig", _SIMPLE_CONFIG)

    src = _FakeProject(src_dir, ws_ids=["en"])
    tgt = _FakeProject(tgt_dir, ws_ids=["en"])

    records = plan_config_views(src, tgt)
    assert len(records) == 1
    rec = records[0]
    assert rec.kind == "ReversalIndex"
    assert rec.filename == "en.fwdictconfig"
    assert rec.action is ConfigViewAction.ADD
    assert not os.path.exists(rec.tgt_path), "plan pass MUST NOT write any file"


def test_plan_skip_when_byte_identical(tmp_path):
    src_dir = tmp_path / "Source"
    tgt_dir = tmp_path / "Target"
    _write(_rev_dir(src_dir), "en.fwdictconfig", _SIMPLE_CONFIG)
    _write(_rev_dir(tgt_dir), "en.fwdictconfig", _SIMPLE_CONFIG)

    src = _FakeProject(src_dir, ws_ids=["en"])
    tgt = _FakeProject(tgt_dir, ws_ids=["en"])

    records = plan_config_views(src, tgt)
    assert len(records) == 1
    assert records[0].action is ConfigViewAction.SKIP


def test_plan_overwrite_when_differs(tmp_path):
    src_dir = tmp_path / "Source"
    tgt_dir = tmp_path / "Target"
    _write(_rev_dir(src_dir), "en.fwdictconfig", _SIMPLE_CONFIG)
    _write(_rev_dir(tgt_dir), "en.fwdictconfig", _SIMPLE_CONFIG.replace("English", "Old English"))

    src = _FakeProject(src_dir, ws_ids=["en"])
    tgt = _FakeProject(tgt_dir, ws_ids=["en"])

    records = plan_config_views(src, tgt)
    assert len(records) == 1
    assert records[0].action is ConfigViewAction.OVERWRITE


def test_plan_covers_both_dictionary_and_reversalindex_subdirs(tmp_path):
    src_dir = tmp_path / "Source"
    tgt_dir = tmp_path / "Target"
    _write(_dict_dir(src_dir), "Lexeme.fwdictconfig", _SIMPLE_CONFIG)
    _write(_rev_dir(src_dir), "en.fwdictconfig", _SIMPLE_CONFIG)

    src = _FakeProject(src_dir, ws_ids=["en"])
    tgt = _FakeProject(tgt_dir, ws_ids=["en"])

    records = plan_config_views(src, tgt)
    kinds = {(r.kind, r.filename) for r in records}
    assert kinds == {
        ("Dictionary", "Lexeme.fwdictconfig"),
        ("ReversalIndex", "en.fwdictconfig"),
    }
    assert all(r.action is ConfigViewAction.ADD for r in records)


# ============================================================================
# T029 -- absent-reference scan
# ============================================================================

def test_missing_ref_scan_reports_ws_field_and_style(tmp_path):
    src_dir = tmp_path / "Source"
    tgt_dir = tmp_path / "Target"
    _write(_rev_dir(src_dir), "fr.fwdictconfig", _CONFIG_WITH_MISSING_REFS)

    # Target lacks: WS 'fr' (root) and 'de' (Option id), custom field
    # 'MyCustomField', and style 'Missing-Style'. It DOES have WS 'analysis'
    # is a magic token so never checked regardless.
    src = _FakeProject(src_dir, ws_ids=["fr", "de"])
    tgt = _FakeProject(tgt_dir, ws_ids=["en"], custom_fields=[], styles=["Dictionary-Normal"])

    records = plan_config_views(src, tgt)
    assert len(records) == 1
    rec = records[0]
    # Still copied (ADD) despite the dangling references -- never blocked.
    assert rec.action is ConfigViewAction.ADD

    by_field = {(m.field_name, m.item_name) for m in rec.missing_refs}
    assert ("writingSystem", "fr") in by_field
    assert ("writingSystem", "de") in by_field
    assert ("field", "MyCustomField") in by_field
    assert ("style", "Missing-Style") in by_field
    for m in rec.missing_refs:
        assert isinstance(m, DroppedItemRecord)
        assert m.owner_kind == "ConfigView"
        assert m.owner_label == "fr.fwdictconfig"
        assert m.reason  # non-empty, per DroppedItemRecord.__post_init__


def test_missing_ref_scan_does_not_report_present_custom_field(tmp_path):
    """Positive path for the owner-class enumeration fix: a custom field the
    target DOES hold must NOT be reported. Guards against a regression where
    `_target_custom_field_names` returns None/empty unconditionally (which
    would make the absent-field test pass vacuously). The target's custom-field
    surface is only readable via `GetAllFields(owner_class)` per owner class --
    the exact live contract a no-arg call could never satisfy."""
    src_dir = tmp_path / "Source"
    tgt_dir = tmp_path / "Target"
    _write(_rev_dir(src_dir), "fr.fwdictconfig", _CONFIG_WITH_MISSING_REFS)

    # Target HAS 'MyCustomField' (+ the WS/style the config needs), so ONLY the
    # 'de' Option-id WS should remain missing -- the custom field must not.
    src = _FakeProject(src_dir, ws_ids=["fr", "de"])
    tgt = _FakeProject(
        tgt_dir, ws_ids=["fr"], custom_fields=["MyCustomField"],
        styles=["Missing-Style"],
    )

    records = plan_config_views(src, tgt)
    by_field = {(m.field_name, m.item_name) for m in records[0].missing_refs}
    assert ("field", "MyCustomField") not in by_field
    assert ("style", "Missing-Style") not in by_field
    assert ("writingSystem", "fr") not in by_field
    assert ("writingSystem", "de") in by_field  # this one really is absent


def test_missing_ref_scan_ignores_ws_magic_tokens(tmp_path):
    src_dir = tmp_path / "Source"
    tgt_dir = tmp_path / "Target"
    _write(_rev_dir(src_dir), "en.fwdictconfig", _SIMPLE_CONFIG)

    # Target's WS list doesn't even include "reversal" -- that's a magic
    # WritingSystemOptions token (default WS-group selector), never a real
    # WS id, and must never be reported as missing. Target styles/fields
    # cover _SIMPLE_CONFIG's own style="Reversal-Normal" so this test
    # isolates the WS-magic-token behavior specifically.
    src = _FakeProject(src_dir, ws_ids=["en"])
    tgt = _FakeProject(tgt_dir, ws_ids=["en"], styles=["Reversal-Normal"])

    records = plan_config_views(src, tgt)
    assert records[0].missing_refs == []


def test_missing_ref_scan_never_reports_when_target_cannot_answer(tmp_path):
    """R9 'unknown, don't report' posture: a target double with no
    WritingSystems/CustomFields/Styles surface at all must not produce
    false-positive missing_refs -- silence here means "can't tell", not
    "definitely absent"."""
    src_dir = tmp_path / "Source"
    tgt_dir = tmp_path / "Target"
    _write(_rev_dir(src_dir), "fr.fwdictconfig", _CONFIG_WITH_MISSING_REFS)

    src = _FakeProject(src_dir, ws_ids=["fr", "de"])
    tgt = _BareFakeProject(tgt_dir)

    records = plan_config_views(src, tgt)
    assert records[0].missing_refs == []


# ============================================================================
# T030 -- apply
# ============================================================================

def test_apply_copies_add_and_overwrite_and_skips_skip(tmp_path):
    src_dir = tmp_path / "Source"
    tgt_dir = tmp_path / "Target"
    _write(_dict_dir(src_dir), "Lexeme.fwdictconfig", _SIMPLE_CONFIG)  # -> ADD
    _write(_rev_dir(src_dir), "en.fwdictconfig", _SIMPLE_CONFIG)  # -> SKIP (identical)
    _write(_rev_dir(tgt_dir), "en.fwdictconfig", _SIMPLE_CONFIG)
    _write(_rev_dir(src_dir), "de.fwdictconfig", _SIMPLE_CONFIG.replace("English", "Deutsch"))  # -> OVERWRITE
    old_de_body = _SIMPLE_CONFIG.replace("English", "Old Deutsch")
    _write(_rev_dir(tgt_dir), "de.fwdictconfig", old_de_body)

    src = _FakeProject(src_dir, ws_ids=["en"])
    tgt = _FakeProject(tgt_dir, ws_ids=["en"])

    records = plan_config_views(src, tgt)
    actions = {(r.kind, r.filename): r.action for r in records}
    assert actions[("Dictionary", "Lexeme.fwdictconfig")] is ConfigViewAction.ADD
    assert actions[("ReversalIndex", "en.fwdictconfig")] is ConfigViewAction.SKIP
    assert actions[("ReversalIndex", "de.fwdictconfig")] is ConfigViewAction.OVERWRITE

    # Plan pass alone must not have written the ADD target yet.
    assert not os.path.exists(os.path.join(_dict_dir(tgt_dir), "Lexeme.fwdictconfig"))

    dropped: list = []
    apply_config_views(records, dropped)

    # ADD landed.
    added_path = os.path.join(_dict_dir(tgt_dir), "Lexeme.fwdictconfig")
    assert os.path.isfile(added_path)
    with open(added_path, encoding="utf-8") as fh:
        assert fh.read() == _SIMPLE_CONFIG

    # OVERWRITE replaced content AND backed up the prior target first.
    de_path = os.path.join(_rev_dir(tgt_dir), "de.fwdictconfig")
    with open(de_path, encoding="utf-8") as fh:
        assert "Deutsch" in fh.read() and "Old Deutsch" not in fh.read()
    backup_path = de_path + ".gtbak"
    assert os.path.isfile(backup_path)
    with open(backup_path, encoding="utf-8") as fh:
        assert "Old Deutsch" in fh.read()

    # SKIP performed no I/O -- target file unchanged (still exactly the
    # identical body it started as; mtime/content untouched).
    skip_path = os.path.join(_rev_dir(tgt_dir), "en.fwdictconfig")
    with open(skip_path, encoding="utf-8") as fh:
        assert fh.read() == _SIMPLE_CONFIG


def test_apply_folds_missing_refs_into_dropped_collector(tmp_path):
    src_dir = tmp_path / "Source"
    tgt_dir = tmp_path / "Target"
    _write(_rev_dir(src_dir), "fr.fwdictconfig", _CONFIG_WITH_MISSING_REFS)

    src = _FakeProject(src_dir, ws_ids=["fr", "de"])
    tgt = _FakeProject(tgt_dir, ws_ids=["en"], custom_fields=[], styles=[])

    records = plan_config_views(src, tgt)
    assert records[0].missing_refs  # sanity: this fixture does have gaps

    dropped: list = []
    apply_config_views(records, dropped)

    assert len(dropped) == len(records[0].missing_refs)
    assert all(isinstance(d, DroppedItemRecord) for d in dropped)
    assert all(d.owner_kind == "ConfigView" for d in dropped)
    # The file is STILL copied despite the dangling references (FLEx
    # degrades gracefully) -- never silently blocked.
    assert os.path.isfile(os.path.join(_rev_dir(tgt_dir), "fr.fwdictconfig"))


def test_apply_skip_action_performs_no_io():
    """SKIP must not even touch the filesystem -- covered structurally by
    passing a record whose src_path doesn't exist; if apply_config_views
    tried to copy it, this would raise."""
    from gramtrans.Lib.models import ConfigViewRecord

    rec = ConfigViewRecord(
        kind="ReversalIndex",
        filename="en.fwdictconfig",
        src_path="/nonexistent/src/en.fwdictconfig",
        tgt_path="/nonexistent/tgt/en.fwdictconfig",
        action=ConfigViewAction.SKIP,
        missing_refs=[],
    )
    dropped: list = []
    apply_config_views([rec], dropped)  # must not raise
    assert dropped == []


# ============================================================================
# resolve_config_dirs -- directory creation
# ============================================================================

def test_resolve_config_dirs_creates_target_subdirs(tmp_path):
    tgt_dir = tmp_path / "FreshTarget"
    tgt = _FakeProject(tgt_dir)
    dictionary_dir, reversal_dir = resolve_config_dirs(tgt)
    assert os.path.isdir(dictionary_dir)
    assert os.path.isdir(reversal_dir)
    assert dictionary_dir == os.path.abspath(_dict_dir(tgt_dir))
    assert reversal_dir == os.path.abspath(_rev_dir(tgt_dir))
