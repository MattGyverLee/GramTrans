"""Phonology-transfer regression check -- real XML parser (no regex).

Supersedes check_phon_transfer.py, whose "<rt ...>(.*?)</rt>" regex silently
mis-parsed SELF-CLOSING <rt ... /> elements: it matched the empty tag and then
swallowed the FOLLOWING object's body, attributing that object's children to
the empty one. That produced phantom feature specs (and could equally produce
a phantom Features element, i.e. a false "not hollow" pass).

Checks:
  DEFECT 1  PhNCFeatures arriving with no FeaturesOA structure
  DEFECT 2  rule context cells pointing at a hollow natural class
  DEFECT 3  rule Disabled flag not carried across
  DEFECT 4  GUID-matched PhNCFeatures whose feature-spec count differs
            (either direction -- loss OR gain)

Exit 0 = clean, 1 = defects.
"""

import collections
import os
import sys
import xml.etree.ElementTree as ET

ROOT = r"C:\ProgramData\SIL\FieldWorks\Projects"
PAIRS = [("Ngoreme FLEx", "Ngoreme Target"), ("Ejagham W Mini", "Ejagham W Target")]
RULE_CLASSES = ("PhRegularRule", "PhMetathesisRule")


def _ascii(text):
    """Render IPA safely on a cp1252 console: U+014B -> <U+014B>."""
    return "".join(
        c if ord(c) < 128 else "<U+%04X>" % ord(c) for c in text)


def _objsur_guids(elem, child_tag):
    """GUIDs referenced by <child_tag><objsur guid=.../></child_tag>."""
    out = []
    holder = elem.find(child_tag)
    if holder is not None:
        for os_ in holder.findall("objsur"):
            g = os_.get("guid")
            if g:
                out.append(g.lower())
    return out


def _multistring(elem, tag):
    holder = elem.find(tag)
    if holder is None:
        return None
    for t in list(holder.findall("AUni")) + list(holder.findall("AStr")):
        txt = (t.text or "").strip()
        if not txt:
            txt = "".join(r.text or "" for r in t.findall("Run")).strip()
        if txt:
            return txt
    return None


def parse(project):
    path = os.path.join(ROOT, project, project + ".fwdata")
    if not os.path.isfile(path):
        raise SystemExit("[ERROR] no .fwdata for %r at %s" % (project, path))
    objs = {}
    for _, elem in ET.iterparse(path, events=("end",)):
        if elem.tag != "rt":
            continue
        guid = (elem.get("guid") or "").lower()
        cls = elem.get("class") or "?"
        rec = {"cls": cls, "owner": (elem.get("ownerguid") or "").lower() or None}
        if cls == "PhNCFeatures":
            fg = _objsur_guids(elem, "Features")
            rec["features_guid"] = fg[0] if fg else None
        elif cls == "PhNCSegments":
            rec["segments"] = _objsur_guids(elem, "Segments")
        elif cls == "FsFeatStruc":
            rec["specs"] = _objsur_guids(elem, "FeatureSpecs")
        elif cls == "PhSimpleContextNC":
            fs = _objsur_guids(elem, "FeatureStructure")
            rec["nc_ref"] = fs[0] if fs else None
        elif cls in RULE_CLASSES:
            d = elem.find("Disabled")
            rec["disabled"] = bool(
                d is not None and (d.get("val") or "").lower() == "true")
            rec["name"] = _multistring(elem, "Name") or "(unnamed)"
        elif cls == "PhPhoneme":
            rec["name"] = _multistring(elem, "Name") or "(unnamed)"
        objs[guid] = rec
        elem.clear()

    kids = collections.defaultdict(list)
    for g, o in objs.items():
        if o["owner"]:
            kids[o["owner"]].append(g)
    return objs, kids


def descendants(guid, kids):
    stack, seen = list(kids.get(guid, ())), set()
    while stack:
        g = stack.pop()
        if g in seen:
            continue
        seen.add(g)
        yield g
        stack.extend(kids.get(g, ()))


def audit(project):
    objs, kids = parse(project)
    ncf = {g: o for g, o in objs.items() if o["cls"] == "PhNCFeatures"}
    ncs = {g: o for g, o in objs.items() if o["cls"] == "PhNCSegments"}

    hollow = {g for g, o in ncf.items() if not o.get("features_guid")}
    spec_count = {}
    for g, o in ncf.items():
        fg = o.get("features_guid")
        fs = objs.get(fg) if fg else None
        spec_count[g] = None if fs is None else len(fs.get("specs") or ())

    rules = {}
    for g, o in objs.items():
        if o["cls"] not in RULE_CLASSES:
            continue
        bad = 0
        for k in descendants(g, kids):
            ko = objs[k]
            if ko["cls"] != "PhSimpleContextNC":
                continue
            ref = ko.get("nc_ref")
            if ref is None or ref in hollow:
                bad += 1
        rules[g] = {"name": o["name"], "disabled": o["disabled"],
                    "hollow_cells": bad}

    phon = [o["name"] for o in objs.values() if o["cls"] == "PhPhoneme"]
    return {
        "ncf": ncf, "hollow": hollow, "spec_count": spec_count,
        "ncs_total": len(ncs),
        "ncs_empty": sum(1 for o in ncs.values() if not o.get("segments")),
        "phonemes": phon,
        "featstruc": sum(1 for o in objs.values() if o["cls"] == "FsFeatStruc"),
        "rules": rules,
    }


def compare(src_name, tgt_name):
    s, t = audit(src_name), audit(tgt_name)
    problems = []
    print("=" * 78)
    print("%s  ->  %s" % (src_name, tgt_name))
    print("=" * 78)
    print("  %-36s %8s %8s" % ("", "SOURCE", "TARGET"))
    rows = [
        ("PhNCFeatures total", len(s["ncf"]), len(t["ncf"])),
        ("PhNCFeatures HOLLOW (no FeaturesOA)", len(s["hollow"]), len(t["hollow"])),
        ("PhNCSegments total", s["ncs_total"], t["ncs_total"]),
        ("PhNCSegments EMPTY", s["ncs_empty"], t["ncs_empty"]),
        ("PhPhoneme", len(s["phonemes"]), len(t["phonemes"])),
        ("FsFeatStruc (whole project)", s["featstruc"], t["featstruc"]),
    ]
    for label, a, b in rows:
        print("  %-36s %8d %8d" % (label, a, b))

    if len(t["hollow"]) > len(s["hollow"]):
        problems.append("DEFECT 1: %d of %d PhNCFeatures in target have NO feature "
                        "structure (source: %d of %d)"
                        % (len(t["hollow"]), len(t["ncf"]),
                           len(s["hollow"]), len(s["ncf"])))

    shared_nc = set(s["ncf"]) & set(t["ncf"])
    mism = [(g, s["spec_count"][g], t["spec_count"][g]) for g in shared_nc
            if s["spec_count"][g] != t["spec_count"][g]]
    print("\n  PhNCFeatures GUID-matched=%d  spec-count mismatches=%d"
          % (len(shared_nc), len(mism)))
    for g, a, b in sorted(mism)[:20]:
        print("    [ERROR] %s  source=%s target=%s" % (g, a, b))
    if mism:
        problems.append("DEFECT 4: %d GUID-matched PhNCFeatures have a different "
                        "feature-spec count in target" % len(mism))

    src_r, tgt_r = s["rules"], t["rules"]
    shared = set(src_r) & set(tgt_r)
    print("\n  rules: source=%d target=%d matched=%d source-only=%d target-only=%d"
          % (len(src_r), len(tgt_r), len(shared),
             len(set(src_r) - set(tgt_r)), len(set(tgt_r) - set(src_r))))
    broken, dis_lost = 0, []
    for g in sorted(shared, key=lambda x: tgt_r[x]["name"]):
        sr, tr = src_r[g], tgt_r[g]
        notes = []
        gained = tr["hollow_cells"] - sr["hollow_cells"]
        if gained > 0:
            broken += gained
            notes.append("%d cell(s) -> hollow NC" % gained)
        if sr["disabled"] and not tr["disabled"]:
            dis_lost.append(tr["name"])
            notes.append("Disabled flag LOST")
        if notes:
            print("    [ERROR] %-46s %s" % (_ascii(tr["name"])[:46], "; ".join(notes)))
    if broken:
        problems.append("DEFECT 2: %d rule context cell(s) point at a hollow "
                        "natural class" % broken)
    if dis_lost:
        problems.append("DEFECT 3: Disabled flag lost on %d rule(s): %s"
                        % (len(dis_lost), _ascii(", ".join(dis_lost))))
    for g in sorted(set(src_r) - set(tgt_r)):
        problems.append("MISSING: rule %r absent from target"
                        % _ascii(src_r[g]["name"]))

    dup = {k: v for k, v in collections.Counter(t["phonemes"]).items() if v > 1}
    if dup:
        print("\n  [NOTE] %d duplicate phoneme name(s) in target -- feature 038 "
              "scope, NOT counted as a 037 defect:" % len(dup))
        # Phoneme names are IPA; a cp1252 console cannot encode them and would
        # raise UnicodeEncodeError mid-report, losing the RESULT line.
        print("         %s" % _ascii(
            ", ".join("%s x%d" % (k, v) for k, v in sorted(dup.items()))))

    print()
    for p in problems:
        print("  [ERROR] %s" % p)
    if not problems:
        print("  [OK] no phonology-transfer defects detected")
    print()
    return problems


def main(argv):
    if len(argv) == 3:
        pairs = [(argv[1], argv[2])]
    elif len(argv) == 2 and argv[1] == "--all":
        pairs = PAIRS
    else:
        print(__doc__)
        return 2
    total = []
    for a, b in pairs:
        total.extend(compare(a, b))
    print("=" * 78)
    print("RESULT: %d defect(s) across %d pair(s)" % (len(total), len(pairs)))
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
