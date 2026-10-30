"""Issue #16 live gate -- Phonemes and PH_ENVIRONMENT are promoted from
selector-only (Tier C) to full field-diff UPDATE (Tier A).

flexicon 4.1.2 (commit 1f9f747b) fixed the ``ITsString.get_String`` crash in
``PhonemeOperations`` / ``EnvironmentOperations.GetSyncableProperties`` (the
scalar ``BasicIPASymbol`` / ``StringRepresentation`` read) AND shipped the
shape-tolerant write half (``PhonemeOperations.__ApplyBasicIPASymbol``;
``BaseOperations``' ITsString ``MakeString`` fallback for a plain-str value).
``conflict._FLEXICON_ITSTRING_FIX_VERSION`` now names that release, so on any
install at the 4.8.0 floor the UPDATE path runs for these two categories.

WRITE PATH: writes ONLY the sandbox named by ``GT_LIVE_SANDBOX`` (default
``Target``, the repo's throwaway project), restored headlessly from a known
backup first.  The source ``Mbugwe LizzieHC practice`` (exact spelling) is
opened READ-ONLY.  ``Esperanto`` is never touched.

Run:
    set FLEXLIBS_REQUIRE_LIVE=1 && set GT_LIVE_SANDBOX=GT-Sandbox-16 && \
        python -m pytest tests/integration/test_issue16_phoneme_env_update_live.py -v -s

Scenario:
  1. ADD the phonology categories (Phase 0) into the restored sandbox.
  2. Diverge ONE phoneme's scalar ``BasicIPASymbol`` and ONE environment's
     scalar ``StringRepresentation`` on the sandbox copy (pre-values read back).
  3. Preview with ``enable_overwrite=True``: both items plan as
     ``PlannedOverwrite`` and the merge-preview pane shows a field-level diff on
     exactly the diverged scalar.
  4. Execute: the UPDATE path runs for both, and a fresh read-back shows the
     source values restored.
  5. Re-run: nothing diverges any more, so no phoneme/environment field is
     written again (idempotency -- no perpetual UPDATE churn).
"""
from __future__ import annotations

import dataclasses
import os
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

if os.environ.get("FLEXLIBS_REQUIRE_LIVE") != "1":
    pytest.skip("FLEXLIBS_REQUIRE_LIVE != 1; live write-path gate not requested.",
                allow_module_level=True)

SOURCE_NAME = os.environ.get("GT_LIVE_SOURCE", "Mbugwe LizzieHC practice")  # READ-ONLY
SANDBOX = os.environ.get("GT_LIVE_SANDBOX", "Target")
_PROJECTS_ROOT = os.environ.get(
    "GRAMTRANS_PROJECTS_ROOT", r"C:\ProgramData\SIL\FieldWorks\Projects")
SANDBOX_PATH = str(Path(_PROJECTS_ROOT) / SANDBOX / f"{SANDBOX}.fwdata")
BACKUP_NAME = "Target 2026-07-06 0218.fwbackup"

_REPO = Path(__file__).resolve().parents[2]
_BACKUP_DIRS = (_REPO / "backups", Path("D:/Github/_Projects/_LEX/GramTrans/backups"))
sys.path.insert(0, str(Path(__file__).parent))

DIVERGED_IPA = "QQ16"
DIVERGED_ENV = "/_QQ16"

if SANDBOX in ("Esperanto",):
    pytest.fail("[FAIL] refusing to write a read-only reference project")


def _restore():
    from harness.restore import restore_target
    for d in _BACKUP_DIRS:
        if (d / BACKUP_NAME).is_file():
            restore_target(SANDBOX, backup_path=d / BACKUP_NAME)
            return
    pytest.fail(f"[FAIL] backup {BACKUP_NAME!r} not found")


def _open(name, write=False):
    from gramtrans.Lib.flexinit import ensure_flex_initialized
    ensure_flex_initialized()
    from flexicon import FLExProject
    proj = FLExProject()
    proj.OpenProject(projectName=name, writeEnabled=write)
    return proj


def _phonology_only(enable_overwrite):
    from gramtrans.Lib.models import GrammarCategory as G
    keep = {G.PHONOLOGICAL_FEATURES, G.PHON_FEAT_TYPES, G.PHONEMES,
            G.PH_ENVIRONMENT}

    def _xf(sel):
        return dataclasses.replace(
            sel, categories={c: (c in keep) for c in G},
            enable_overwrite=enable_overwrite)
    return _xf


def _find(proj, ph_guid, env_guid):
    ph = env = None
    for p in proj.Phonemes.GetAll():
        if str(p.Guid).lower() == ph_guid:
            ph = p
    for e in proj.Environments.GetAll():
        if str(e.Guid).lower() == env_guid:
            env = e
    assert ph is not None and env is not None, "[FAIL] probe objects not found"
    return ph, env


def _scalar_reads(proj, ph_guid, env_guid):
    """Read the two scalars straight off LCM (not via GetSyncableProperties)."""
    from SIL.LCModel.Core.KernelInterfaces import ITsString
    ph, env = _find(proj, ph_guid, env_guid)
    return (ITsString(ph.BasicIPASymbol).Text,
            ITsString(env.StringRepresentation).Text)


class _UpdateRecorder:
    """Wrap transfer._execute_update_semantic / apply_update_semantic to record
    which (category, guid) reached the UPDATE path and which keys were written."""

    def __init__(self, monkeypatch):
        import gramtrans.Lib.transfer as t
        from gramtrans.Lib.conflict import compute_merge_fillable
        self.reached = []   # (category value, guid)
        self.written = {}   # guid -> sorted fillable keys
        self._cur = None
        orig_exec = t._execute_update_semantic
        orig_apply = t.apply_update_semantic

        def _exec(ow, *a, **kw):
            self._cur = ow.source_guid.lower()
            self.reached.append((ow.category.value, self._cur))
            return orig_exec(ow, *a, **kw)

        def _apply(src_props, tgt_props, ops, tgt_obj, ws_map=None):
            keys = sorted(compute_merge_fillable(src_props, tgt_props))
            self.written[self._cur] = keys
            return orig_apply(src_props, tgt_props, ops, tgt_obj, ws_map=ws_map)

        monkeypatch.setattr(t, "_execute_update_semantic", _exec)
        monkeypatch.setattr(t, "apply_update_semantic", _apply)


def test_phoneme_env_update_end_to_end(monkeypatch):
    from harness.full_run import run_full_transfer

    from gramtrans.Lib.conflict import _phoneme_env_field_diff_enabled
    from gramtrans.Lib.merge_preview import MERGE_KEEP, MergePreviewService

    assert _phoneme_env_field_diff_enabled() is True, (
        "[FAIL] gate closed on this install -- pyflexicon below the fix release?")

    _restore()

    # -- candidate probes from the READ-ONLY source ---------------------------
    src = _open(SOURCE_NAME)
    try:
        ph_cands = [str(p.Guid).lower() for p in src.Phonemes.GetAll()
                    if src.Phonemes.GetSyncableProperties(p).get("BasicIPASymbol")]
        env_cands = [str(e.Guid).lower() for e in src.Environments.GetAll()
                     if src.Environments.GetSyncableProperties(e).get(
                         "StringRepresentation")]
    finally:
        src.CloseProject()
    assert ph_cands and env_cands, "[FAIL] source has no probe phoneme/env"

    # -- 1. ADD (Phase 0) ------------------------------------------------------
    run_full_transfer(SOURCE_NAME, SANDBOX, SANDBOX_PATH,
                      selection_transform=_phonology_only(False))
    # Probe objects the sandbox holds under the SOURCE GUID (created
    # GUID-preserved, or already present by GUID), so one GUID addresses both
    # sides. A natural-key match lives under another GUID and is skipped here.
    tgt = _open(SANDBOX)
    try:
        tgt_ph = {str(p.Guid).lower() for p in tgt.Phonemes.GetAll()}
        tgt_env = {str(e.Guid).lower() for e in tgt.Environments.GetAll()}
        ph_guid = next((g for g in ph_cands if g in tgt_ph), None)
        env_guid = next((g for g in env_cands if g in tgt_env), None)
        assert ph_guid and env_guid, "[FAIL] no probe present by GUID after ADD"
        post_add = _scalar_reads(tgt, ph_guid, env_guid)
    finally:
        tgt.CloseProject()
    src = _open(SOURCE_NAME)
    try:
        src_ipa, src_env = _scalar_reads(src, ph_guid, env_guid)
    finally:
        src.CloseProject()
    print(f"[INFO] probe phoneme {ph_guid} IPA={src_ipa!r}; "
          f"env {env_guid} StringRepresentation={src_env!r}")
    print(f"[INFO] after ADD: {post_add!r}")
    assert post_add == (src_ipa, src_env), "[FAIL] ADD did not copy the scalars"

    # -- 2. diverge on the sandbox --------------------------------------------
    tgt = _open(SANDBOX, write=True)
    try:
        ph, env = _find(tgt, ph_guid, env_guid)
        tgt.Phonemes.SetBasicIPASymbol(ph, DIVERGED_IPA)
        tgt.Environments.SetStringRepresentation(env, DIVERGED_ENV)
    finally:
        tgt.CloseProject()
    tgt = _open(SANDBOX)
    try:
        pre_update = _scalar_reads(tgt, ph_guid, env_guid)
    finally:
        tgt.CloseProject()
    print(f"[INFO] pre-UPDATE (diverged): {pre_update!r}")
    assert pre_update == (DIVERGED_IPA, DIVERGED_ENV)

    # -- 3. preview ------------------------------------------------------------
    plan, _ = run_full_transfer(SOURCE_NAME, SANDBOX, SANDBOX_PATH,
                                selection_transform=_phonology_only(True),
                                preview_only=True)
    ow_guids = {o.source_guid.lower() for o in plan.overwrites}
    assert ph_guid in ow_guids and env_guid in ow_guids, (
        "[FAIL] diverged phoneme/env not planned as PlannedOverwrite")
    src = _open(SOURCE_NAME)
    tgt = _open(SANDBOX)
    try:
        svc = MergePreviewService(src, tgt)
        diffs = {}
        # MERGE_KEEP: what the pane renders for a write_mode="merge" overwrite.
        for cat, guid, fld, src_val, tgt_val in (
                ("phoneme", ph_guid, "BasicIPASymbol", src_ipa, DIVERGED_IPA),
                ("environment", env_guid, "StringRepresentation", src_env,
                 DIVERGED_ENV)):
            pv = svc.preview_for(cat, guid, guid, "present", MERGE_KEEP)
            fd = [f for f in pv.fields if f.field_name == fld]
            assert fd, f"[FAIL] no {fld} row in the {cat} preview"
            kinds = [s.kind.value for s in fd[0].segments]
            texts = " | ".join(s.text for s in fd[0].segments)
            diffs[cat] = (kinds, texts)
            print(f"[INFO] preview {cat}.{fld}: kinds={kinds} text={texts!r}")
            assert set(kinds) != {"unchanged"}, (
                f"[FAIL] preview shows no field-level diff on {cat}.{fld}")
            assert src_val in texts and tgt_val in texts, (
                f"[FAIL] preview of {cat}.{fld} does not show both values")
    finally:
        tgt.CloseProject()
        src.CloseProject()

    # -- 4. execute UPDATE -----------------------------------------------------
    rec = _UpdateRecorder(monkeypatch)
    run_full_transfer(SOURCE_NAME, SANDBOX, SANDBOX_PATH,
                      selection_transform=_phonology_only(True))
    reached = {g for _c, g in rec.reached}
    assert ph_guid in reached and env_guid in reached, (
        "[FAIL] UPDATE path not reached for the probe objects "
        "(gate still closing it?)")
    print(f"[INFO] run-2 UPDATE keys: phoneme={rec.written.get(ph_guid)} "
          f"env={rec.written.get(env_guid)}")
    assert "BasicIPASymbol" in rec.written.get(ph_guid, [])
    assert "StringRepresentation" in rec.written.get(env_guid, [])
    tgt = _open(SANDBOX)
    try:
        post_update = _scalar_reads(tgt, ph_guid, env_guid)
    finally:
        tgt.CloseProject()
    print(f"[INFO] post-UPDATE read-back: {post_update!r}")
    assert post_update == (src_ipa, src_env), (
        "[FAIL] UPDATE did not restore the source scalars")

    # -- 5. re-run: idempotent -------------------------------------------------
    rec2 = _UpdateRecorder(monkeypatch)
    run_full_transfer(SOURCE_NAME, SANDBOX, SANDBOX_PATH,
                      selection_transform=_phonology_only(True))
    churn = {g: k for g, k in rec2.written.items()
             if any(c in ("phonemes", "ph_environment") for c, gg in rec2.reached
                    if gg == g) and k}
    print(f"[INFO] run-3 phoneme/env items still writing: {len(churn)} {churn}")
    assert ph_guid not in churn and env_guid not in churn, (
        "[FAIL] probe items re-written on an unchanged re-run")
    assert not churn, "[FAIL] perpetual UPDATE churn on phonemes/environments"
