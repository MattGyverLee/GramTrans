"""T128 acceptance, CORRECTED QUERY -- ownership read from the CHILD side.

T128's stated acceptance was a "destination-side `MembersOC` GUID diff". Read
from the OWNER side that query returns empty for every group on both projects,
because `.fwdata` serialises owned-collection membership on the CHILD
(`ownerguid`), not as `<objsur t="o">` entries under the parent's field. The
owner-side read is a FALSE NEGATIVE: it reports "no members lost" at the exact
moment every group lost its only child.

This is the same reading done from the child side, on both projects, plus the
destination pin check T129 now requires of any comparison.

READ-ONLY. No project opened, nothing written.
"""
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(r"C:\ProgramData\SIL\FieldWorks\Projects")
SOURCE = "Mbugwe LizzieHC practice"
DEST = "GT038 T124 Mbugwe"
OUT = Path(__file__).with_name("t128-child-side-result.json")

ADHOC_CHILD = "MoMorphAdhocProhib"
GROUP = "MoAdhocProhibGr"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def scan(project):
    path = ROOT / project / (project + ".fwdata")
    cls_of, owner_of = {}, {}
    empty_rule = {}
    for _e, elem in ET.iterparse(str(path), events=("end",)):
        if elem.tag == "rt":
            guid = (elem.get("guid") or "").lower()
            cls_of[guid] = elem.get("class")
            owner_of[guid] = (elem.get("ownerguid") or "").lower()
            if elem.get("class") == ADHOC_CHILD:
                filled = []
                for field in elem:
                    if field.tag in ("FirstMorpheme", "RestOfMorphs"):
                        if len(list(field)):
                            filled.append(field.tag)
                empty_rule[guid] = not filled
        elem.clear()
    return {"sha256": sha256(path), "cls_of": cls_of, "owner_of": owner_of,
            "empty_rule": empty_rule}


def owned_by_group(scan_result):
    """group guid -> [child guid], read from the CHILD's ownerguid."""
    out = {}
    for guid, cls in scan_result["cls_of"].items():
        if cls != ADHOC_CHILD:
            continue
        owner = scan_result["owner_of"].get(guid, "")
        if scan_result["cls_of"].get(owner) == GROUP:
            out.setdefault(owner, []).append(guid)
    return {g: sorted(v) for g, v in out.items()}


def owner_class_histogram(scan_result):
    hist = {}
    for guid, cls in scan_result["cls_of"].items():
        if cls != ADHOC_CHILD:
            continue
        owner = scan_result["owner_of"].get(guid, "")
        oc = scan_result["cls_of"].get(owner) or "(no owner)"
        hist[oc] = hist.get(oc, 0) + 1
    return dict(sorted(hist.items(), key=lambda kv: -kv[1]))


src, dst = scan(SOURCE), scan(DEST)
s_groups, d_groups = owned_by_group(src), owned_by_group(dst)

s_children = {g for g, c in src["cls_of"].items() if c == ADHOC_CHILD}
d_children = {g for g, c in dst["cls_of"].items() if c == ADHOC_CHILD}
missing = sorted(s_children - d_children)

result = {
    "method": "child-side ownerguid read; the owner-side MembersOC read that "
              "T128 specified is a false negative on .fwdata",
    "source": {"project": SOURCE, "sha256": src["sha256"]},
    "destination": {"project": DEST, "sha256": dst["sha256"]},
    "counts": {
        "source_children": len(s_children),
        "destination_children": len(d_children),
        "difference": len(d_children) - len(s_children),
        "guid_identical_overlap": len(s_children & d_children),
        "destination_only": sorted(d_children - s_children),
    },
    "owner_class_histogram": {
        "source": owner_class_histogram(src),
        "destination": owner_class_histogram(dst),
    },
    "group_membership_child_side": {
        "source": {g: s_groups.get(g, []) for g in sorted(
            set(s_groups) | set(d_groups))},
        "destination": {g: d_groups.get(g, []) for g in sorted(
            set(s_groups) | set(d_groups))},
    },
    "groups_present": {
        "source": sorted(g for g, c in src["cls_of"].items() if c == GROUP),
        "destination": sorted(g for g, c in dst["cls_of"].items()
                              if c == GROUP),
    },
    "missing_children": missing,
    "missing_are_group_owned": sorted(
        g for g in missing
        if src["cls_of"].get(src["owner_of"].get(g, "")) == GROUP),
    "missing_rule_is_empty_in_source": {
        g: src["empty_rule"].get(g) for g in missing},
}

OUT.write_text(json.dumps(result, indent=1), encoding="utf-8")
print(json.dumps({k: v for k, v in result.items()
                  if k != "group_membership_child_side"}, indent=1))
print()
print("group membership (child-side):")
print(json.dumps(result["group_membership_child_side"], indent=1))
print()
print("[OK] wrote %s" % OUT)
