"""Compare the full rule CELL tree source vs target, by GUID.

check_phon_fidelity.py only inspects PhSimpleContextNC cells, so it is blind to
a whole context subtype going missing -- exactly the PhIterationContext defect
(7 silent skips/run). This walks every ordered cell collection on every rule and
compares class-name sequences, so a dropped or reordered cell shows up.

Walks:
  rule.StrucDesc[*]                       (input pattern)
  rule.RightHandSides[*].StrucChange[*]   (output)
  rule.RightHandSides[*].LeftContext      (OA slot)
  rule.RightHandSides[*].RightContext     (OA slot)
  PhSequenceContext.Members[*]            (nested, recursive)
  PhIterationContext.Member               (nested, recursive)

Usage: python check_rule_cells.py "Ngoreme FLEx" "Target"
Exit 0 = identical cell trees, 1 = drift.
"""

import collections
import os
import sys
import xml.etree.ElementTree as ET

ROOT = r"C:\ProgramData\SIL\FieldWorks\Projects"
RULE_CLASSES = ("PhRegularRule", "PhMetathesisRule")


def _refs(elem, tag):
    holder = elem.find(tag)
    if holder is None:
        return []
    return [o.get("guid").lower() for o in holder.findall("objsur") if o.get("guid")]


def _first_ref(elem, tag):
    r = _refs(elem, tag)
    return r[0] if r else None


def parse(project):
    path = os.path.join(ROOT, project, project + ".fwdata")
    if not os.path.isfile(path):
        raise SystemExit("[ERROR] no .fwdata for %r" % project)
    objs = {}
    for _, elem in ET.iterparse(path, events=("end",)):
        if elem.tag != "rt":
            continue
        guid = (elem.get("guid") or "").lower()
        cls = elem.get("class") or "?"
        rec = {"cls": cls}
        if cls in RULE_CLASSES:
            rec["struc_desc"] = _refs(elem, "StrucDesc")
            rec["rhss"] = _refs(elem, "RightHandSides")
            nm = elem.find("Name")
            txt = None
            if nm is not None:
                a = nm.find("AUni")
                if a is not None:
                    txt = (a.text or "").strip()
            rec["name"] = txt or "(unnamed)"
        elif cls == "PhSegRuleRHS":
            rec["struc_change"] = _refs(elem, "StrucChange")
            rec["left"] = _first_ref(elem, "LeftContext")
            rec["right"] = _first_ref(elem, "RightContext")
        elif cls == "PhSequenceContext":
            rec["members"] = _refs(elem, "Members")
        elif cls == "PhIterationContext":
            rec["member"] = _first_ref(elem, "Member")
            mn = elem.find("Minimum")
            mx = elem.find("Maximum")
            rec["min"] = mn.get("val") if mn is not None else None
            rec["max"] = mx.get("val") if mx is not None else None
        objs[guid] = rec
        elem.clear()
    return objs


def render_cell(guid, objs, depth=0):
    """Render one cell (recursively) as a compact structural signature."""
    if guid is None:
        return "<null>"
    o = objs.get(guid)
    if o is None:
        return "<MISSING:%s>" % guid[:8]
    cls = o["cls"]
    if cls == "PhSequenceContext":
        inner = ",".join(render_cell(m, objs, depth + 1) for m in o.get("members", []))
        return "Seq[%s]" % inner
    if cls == "PhIterationContext":
        return "Iter(min=%s,max=%s){%s}" % (
            o.get("min"), o.get("max"), render_cell(o.get("member"), objs, depth + 1))
    return cls


def rule_signature(guid, objs):
    r = objs[guid]
    sig = {"input": [render_cell(c, objs) for c in r.get("struc_desc", [])],
           "rhss": []}
    for rhs_guid in r.get("rhss", []):
        rhs = objs.get(rhs_guid)
        if rhs is None:
            sig["rhss"].append({"MISSING": rhs_guid[:8]})
            continue
        sig["rhss"].append({
            "out": [render_cell(c, objs) for c in rhs.get("struc_change", [])],
            "left": render_cell(rhs.get("left"), objs),
            "right": render_cell(rhs.get("right"), objs),
        })
    return sig


def cell_class_tally(objs):
    """Count every context object in the project by class."""
    interesting = ("PhSimpleContextNC", "PhSimpleContextSeg", "PhSimpleContextBdry",
                   "PhSequenceContext", "PhIterationContext")
    t = collections.Counter(o["cls"] for o in objs.values() if o["cls"] in interesting)
    return t


def main(argv):
    if len(argv) != 3:
        print(__doc__)
        return 2
    src_name, tgt_name = argv[1], argv[2]
    s, t = parse(src_name), parse(tgt_name)

    print("=" * 78)
    print("RULE CELL TREES:  %s  ->  %s" % (src_name, tgt_name))
    print("=" * 78)

    st, tt = cell_class_tally(s), cell_class_tally(t)
    print("\n  context objects by class (whole project):")
    print("    %-22s %8s %8s" % ("", "SOURCE", "TARGET"))
    problems = []
    for cls in sorted(set(st) | set(tt)):
        a, b = st.get(cls, 0), tt.get(cls, 0)
        flag = ""
        if b < a:
            flag = "   <<< TARGET HAS FEWER"
        print("    %-22s %8d %8d%s" % (cls, a, b, flag))
    print()

    src_rules = {g: o for g, o in s.items() if o["cls"] in RULE_CLASSES}
    tgt_rules = {g: o for g, o in t.items() if o["cls"] in RULE_CLASSES}
    shared = sorted(set(src_rules) & set(tgt_rules),
                    key=lambda g: src_rules[g]["name"])
    print("  rules: source=%d target=%d matched=%d"
          % (len(src_rules), len(tgt_rules), len(shared)))

    drift = 0
    for g in shared:
        a, b = rule_signature(g, s), rule_signature(g, t)
        if a == b:
            continue
        drift += 1
        name = src_rules[g]["name"]
        print("\n  [ERROR] %s  (guid=%s)" % (name[:52], g[:8]))
        if a["input"] != b["input"]:
            print("      input  source: %s" % (a["input"],))
            print("      input  target: %s" % (b["input"],))
        if len(a["rhss"]) != len(b["rhss"]):
            print("      RHS count %d -> %d" % (len(a["rhss"]), len(b["rhss"])))
        for i, (ra, rb) in enumerate(zip(a["rhss"], b["rhss"])):
            if ra != rb:
                print("      rhs[%d] source: %s" % (i, ra))
                print("      rhs[%d] target: %s" % (i, rb))
    if drift:
        problems.append("%d of %d matched rules have a different cell tree"
                        % (drift, len(shared)))

    # A cell class present in source rules but absent from target rules is the
    # PhIterationContext failure mode, and is worth calling out on its own.
    for cls in ("PhIterationContext", "PhSequenceContext"):
        a, b = st.get(cls, 0), tt.get(cls, 0)
        if a > 0 and b == 0:
            problems.append("%s: %d in source, ZERO in target -- subtype dropped "
                            "entirely" % (cls, a))

    print()
    if problems:
        for p in problems:
            print("  [ERROR] %s" % p)
    else:
        print("  [OK] every matched rule's cell tree is structurally identical")
    print()
    print("=" * 78)
    print("RESULT: %d problem(s)" % len(problems))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
