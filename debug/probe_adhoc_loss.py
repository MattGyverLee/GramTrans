"""US5 read-only probe: characterize Ad hoc / Compound rule transfer loss.

Feature 032 (T030-T032), contracts/adhoc-loss-probe.md.

Investigation + characterization ONLY. This probe writes NOTHING to either
project (read-only DoD, SC-008); reproduction of ad hoc rules is out of scope
(FR-016). It enumerates the source ad hoc/compound rules and, against a target
that has already received all stems/affixes, characterizes per rule:

  1. whether the rule itself is present on the target (by GUID);
  2. which of its member-reference dependencies (morphemes / allomorphs /
     MSA-POS) resolve to real target objects vs are absent;
  3. the leading silent-loss hypothesis (research.md R5): whether the rule's
     Name multistring carries source writing systems that have NO target
     counterpart -- the WSs that ``to_ws_map_dict`` / ``ApplySyncableProperties``
     silently drop (ws_mapping.py ~66-85). This confirms or refutes that the
     drop mechanism applies to the ad-hoc transfer path.

Output is ASCII-only (Windows-terminal safe). An evidence JSON is written under
``specs/032-preview-coverage-completion/`` (the spec folder in the repo -- NOT
a FLEx project), so the read-only-against-projects guarantee is preserved.

Run (read-only):
    set GRAMTRANS_SOURCE=Ejagham Mini
    set GRAMTRANS_TARGET=Ejagham Full GT-Test
    python debug/probe_adhoc_loss.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "src" / "gramtrans" / "Lib"))

SOURCE = os.environ.get("GRAMTRANS_SOURCE", "Ejagham Mini")
TARGET = os.environ.get("GRAMTRANS_TARGET", "Ejagham Full GT-Test")
EVIDENCE = (_REPO / "specs" / "032-preview-coverage-completion"
            / "adhoc-loss-evidence.json")


def _class_name(obj) -> str:
    try:
        from SIL.LCModel import ICmObject
        return str(ICmObject(getattr(obj, "concrete", obj)).ClassName)
    except Exception:
        return str(getattr(obj, "ClassName", getattr(obj, "class_name", "")) or "")


def _name_ws_values(obj):
    """Return {ws_id: text} for the rule's Name multistring, best-effort."""
    out = {}
    nm = getattr(obj, "Name", None)
    if nm is None:
        return out
    # IMultiUnicode / IMultiAccessorBase: enumerate available alternatives.
    try:
        # flexicon exposes .StringCount / .get_String via the accessor; fall back
        # to probing the project WS ids from the caller.
        best = getattr(nm, "BestAnalysisVernacularAlternative", None)
        if best is not None and getattr(best, "Text", None):
            out["__best__"] = str(best.Text)
    except Exception:
        pass
    return out


def _target_ws_ids(target):
    try:
        return {str(w.Id) for w in target.WritingSystems.GetAll()}
    except Exception:
        return set()


def _source_name_ws_ids(obj, src_ws_descs):
    """Which source WS ids actually carry a Name value on this rule.

    ``src_ws_descs`` is a list of (ws_id, handle) pairs; LCM's ``get_String``
    keys on the integer WS *handle*, not the tag string, so we resolve by
    handle to avoid a vacuous (always-empty) result.
    """
    carried = []
    nm = getattr(obj, "Name", None)
    if nm is None or not hasattr(nm, "get_String"):
        return carried
    for ws_id, handle in src_ws_descs:
        if handle is None:
            continue
        try:
            val = nm.get_String(handle)
        except Exception:
            val = None
        if val is not None and getattr(val, "Text", None):
            carried.append(ws_id)
    return carried


def main() -> int:
    import flexicon
    flexicon.FLExInitialize()
    try:
        from SIL.WritingSystems import Sldr  # type: ignore
        if not Sldr.IsInitialized:
            Sldr.Initialize(True)
    except Exception:
        pass

    from flexicon import FLExProject
    from categories import (  # reused, Qt-free
        _rules_enumerate_all,
        adhoc_compound_rules_dependencies,
        _guid_str_from,
    )

    source = FLExProject()
    source.OpenProject(projectName=SOURCE, writeEnabled=False)
    target = FLExProject()
    target.OpenProject(projectName=TARGET, writeEnabled=False)
    print(f"[OK] opened SOURCE={SOURCE!r} and TARGET={TARGET!r} read-only")

    # Target GUID membership: rule GUIDs + a repository check for dependencies.
    tgt_rule_guids = set()
    for r in _rules_enumerate_all(target):
        g = _guid_str_from(r)
        if g:
            tgt_rule_guids.add(g)

    repo = None
    try:
        from SIL.LCModel import ICmObjectRepository
        from System import Guid  # type: ignore
        repo = target.ObjectRepository(ICmObjectRepository)
    except Exception as exc:
        print(f"[WARN] target object repository unavailable: {exc!r}")

    def _dep_present(guid_str) -> bool:
        if repo is None:
            return False
        try:
            from System import Guid  # type: ignore
            return bool(repo.IsValidObjectId(Guid(guid_str)))
        except Exception:
            return False

    src_ws_ids = []
    src_ws_descs = []
    try:
        for w in source.WritingSystems.GetAll():
            wid = str(w.Id)
            src_ws_ids.append(wid)
            src_ws_descs.append((wid, getattr(w, "Handle", None)))
    except Exception:
        pass
    tgt_ws_ids = _target_ws_ids(target)

    rows = []
    ws_drop_seen = False
    for rule in _rules_enumerate_all(source):
        cls = _class_name(rule)
        if cls == "MoAdhocProhibGr":
            continue  # grouping node, not a leaf rule
        guid = _guid_str_from(rule)
        deps = [d for d in (adhoc_compound_rules_dependencies(rule) or []) if d]
        deps_absent = [d for d in deps if not _dep_present(d)]
        name_ws = _source_name_ws_ids(rule, src_ws_descs)
        name_ws_dropped = [w for w in name_ws if w not in tgt_ws_ids]
        if name_ws_dropped:
            ws_drop_seen = True
        rows.append({
            "guid": guid,
            "class": cls,
            "present_in_target": guid in tgt_rule_guids,
            "dep_count": len(deps),
            "deps_absent": deps_absent,
            "name_ws_carried": name_ws,
            "name_ws_dropped": name_ws_dropped,
        })

    # ---- summary ------------------------------------------------------------
    total = len(rows)
    present = sum(1 for r in rows if r["present_in_target"])
    with_absent_deps = sum(1 for r in rows if r["deps_absent"])
    print("")
    print("=== Ad hoc / Compound rule transfer-loss characterization ===")
    print(f"source rules (leaf)         : {total}")
    print(f"present on target by GUID   : {present}")
    print(f"absent on target by GUID    : {total - present}")
    print(f"rules w/ unresolved deps    : {with_absent_deps}")
    print(f"WS-drop hypothesis (R5)     : "
          f"{'CONFIRMED (some Name WSs have no target counterpart)' if ws_drop_seen else 'REFUTED (every carried Name WS has a target counterpart)'}")
    for r in rows:
        flag = "PRESENT" if r["present_in_target"] else "ABSENT"
        extra = ""
        if r["deps_absent"]:
            extra += f" deps_absent={len(r['deps_absent'])}"
        if r["name_ws_dropped"]:
            extra += f" name_ws_dropped={r['name_ws_dropped']}"
        print(f"  [{flag}] {r['class']} {r['guid']}{extra}")

    EVIDENCE.write_text(json.dumps({
        "source": SOURCE,
        "target": TARGET,
        "source_ws_ids": src_ws_ids,
        "target_ws_ids": sorted(tgt_ws_ids),
        "totals": {
            "source_rules": total,
            "present_in_target": present,
            "absent_in_target": total - present,
            "rules_with_unresolved_deps": with_absent_deps,
            "ws_drop_hypothesis_confirmed": ws_drop_seen,
        },
        "rules": rows,
    }, indent=2), encoding="utf-8")
    print(f"\n[OK] evidence written: {EVIDENCE}")
    print("[OK] NO writes to either FLEx project (read-only probe).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
