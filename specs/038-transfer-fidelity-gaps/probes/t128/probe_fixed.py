"""Corrected read-only .fwdata probe for T127 and T128.

BUG BEING FIXED: the earlier probes called `elem.clear()` on EVERY element as
iterparse fired its `end` event. `end` fires for children before their parent,
so every `<Name>`, `<AUni>`, `<Members>` and `<objsur>` was emptied before the
owning `<rt>` was processed. Anything read from an `rt` ATTRIBUTE (class, guid,
ownerguid) was unaffected; anything read from a CHILD element came back empty.

Only the `rt` element is cleared here, and only after it is fully processed.
"""
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(r"C:\ProgramData\SIL\FieldWorks\Projects")
OUT = Path(__file__).with_name("probe-fixed-result.json")

SOURCE = "Mbugwe LizzieHC practice"
DEST = "GT038 T124 Mbugwe"

ENTRY_TYPES = {"LexEntryType", "LexEntryInflType"}
ADHOC = {"MoMorphAdhocProhib", "MoAlloAdhocProhib", "MoAdhocProhibGr"}
MULTI = ("Name", "Abbreviation", "ReverseName", "ReverseAbbr", "Description")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def multistring(field):
    out = {}
    for alt in field:
        ws = alt.get("ws")
        text = "".join(alt.itertext()).strip()
        if ws:
            out[ws] = text
    return out


def scan(project):
    path = ROOT / project / (project + ".fwdata")
    entry_types = {}
    adhoc_cls = {}
    adhoc_owner = {}
    members_field = {}
    for _e, elem in ET.iterparse(str(path), events=("end",)):
        if elem.tag != "rt":
            continue                      # <-- do NOT clear children
        cls = elem.get("class")
        guid = (elem.get("guid") or "").lower()
        owner = (elem.get("ownerguid") or "").lower()
        if cls in ENTRY_TYPES:
            rec = {"class": cls, "ownerguid": owner}
            for field in elem:
                if field.tag in MULTI:
                    rec[field.tag] = multistring(field)
            entry_types[guid] = rec
        if cls in ADHOC:
            adhoc_cls[guid] = cls
            adhoc_owner[guid] = owner
            if cls == "MoAdhocProhibGr":
                kids = []
                for field in elem:
                    if field.tag == "Members":
                        kids = [(o.get("guid") or "").lower() for o in field]
                members_field[guid] = kids
        elem.clear()
    return {"sha256": sha256(path), "entry_types": entry_types,
            "adhoc_cls": adhoc_cls, "adhoc_owner": adhoc_owner,
            "members_field": members_field}


src, dst = scan(SOURCE), scan(DEST)

# ---- T127 -----------------------------------------------------------------
TARGET = "99e0cab9-f284-45fb-84a5-4cb2516d0bf4"


def nameless(rows):
    return sorted(g for g, r in rows.items()
                  if not any((r.get("Name") or {}).values()))


t127 = {
    "target_guid": TARGET,
    "in_source": src["entry_types"].get(TARGET),
    "in_destination": dst["entry_types"].get(TARGET),
    "source_count": len(src["entry_types"]),
    "destination_count": len(dst["entry_types"]),
    "nameless_in_source": nameless(src["entry_types"]),
    "nameless_in_destination": nameless(dst["entry_types"]),
}
both = set(src["entry_types"]) & set(dst["entry_types"])
t127["name_lost_in_transfer"] = sorted(
    g for g in both
    if any((src["entry_types"][g].get("Name") or {}).values())
    and not any((dst["entry_types"][g].get("Name") or {}).values()))
t127["name_preserved"] = sorted(
    g for g in both
    if any((src["entry_types"][g].get("Name") or {}).values())
    and any((dst["entry_types"][g].get("Name") or {}).values()))

# ---- T128 -----------------------------------------------------------------
def owner_hist(scn):
    hist = {}
    for g, cls in scn["adhoc_cls"].items():
        if cls != "MoMorphAdhocProhib":
            continue
        oc = scn["adhoc_cls"].get(scn["adhoc_owner"].get(g, "")) or "(other)"
        hist[oc] = hist.get(oc, 0) + 1
    return dict(sorted(hist.items(), key=lambda kv: -kv[1]))


s_kids = {g for g, c in src["adhoc_cls"].items()
          if c == "MoMorphAdhocProhib"}
d_kids = {g for g, c in dst["adhoc_cls"].items()
          if c == "MoMorphAdhocProhib"}

t128 = {
    "owner_histogram_source": owner_hist(src),
    "owner_histogram_destination": owner_hist(dst),
    "members_field_source": src["members_field"],
    "members_field_destination": dst["members_field"],
    "missing_children": sorted(s_kids - d_kids),
    "counts": {"source": len(s_kids), "destination": len(d_kids)},
}

result = {
    "source": {"project": SOURCE, "sha256": src["sha256"]},
    "destination": {"project": DEST, "sha256": dst["sha256"]},
    "t127": t127, "t128": t128,
}
OUT.write_text(json.dumps(result, indent=1, ensure_ascii=False),
               encoding="utf-8")
print(json.dumps(result, indent=1, ensure_ascii=False))
