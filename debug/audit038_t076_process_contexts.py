"""T076 audit -- READ-ONLY. What do the condition-4 rules actually reference?

Question 1: how many MoAffixProcess rules carry a PhSequenceContext in InputOS
whose MembersRS points at something the rule does NOT own?
Question 2: what OWNS those far endpoints?
Question 3 (the registration question, T089's shape): is that far GUID
reachable from any category that can ENUMERATE it -- specifically, is it also
reachable from PhPhonData.PhonRulesOS, the one path that already creates
PhSimpleContext* objects into the destination's ContextsOS?
"""
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_ROOT, "src"))
sys.path.insert(0, os.path.join(_ROOT, "tests", "integration"))

from harness.full_run import source_readonly  # noqa: E402

CORPORA = ["Mbugwe LizzieHC practice", "Ejagham Mini"]


def cn(o):
    try:
        return str(getattr(o, "ClassName", "") or "")
    except Exception:
        return ""


def guid(o):
    try:
        return str(getattr(o, "Guid", "") or "")
    except Exception:
        return ""


def cast(o, iface):
    try:
        import SIL.LCModel as L
        return getattr(L, iface)(o)
    except Exception:
        return o


def owner_chain(o, depth=4):
    out = []
    cur = o
    for _ in range(depth):
        try:
            owner = getattr(cur, "Owner", None)
        except Exception:
            owner = None
        if owner is None:
            break
        try:
            flid = getattr(cur, "OwningFlid", None)
        except Exception:
            flid = None
        out.append("%s(flid=%s)" % (cn(owner), flid))
        cur = owner
    return out


def collect_contexts_from_cell(cell, acc):
    """Every context GUID reachable from a phonological-rule cell."""
    if cell is None:
        return
    c = cn(cell)
    if not c:
        return
    acc.setdefault(c, set()).add(guid(cell))
    if c == "PhSequenceContext":
        try:
            for m in cast(cell, "IPhSequenceContext").MembersRS:
                collect_contexts_from_cell(m, acc)
        except Exception:
            pass
    elif c == "PhIterationContext":
        try:
            collect_contexts_from_cell(
                getattr(cast(cell, "IPhIterationContext"), "MemberRA", None), acc)
        except Exception:
            pass


def audit(project_name):
    result = {"project": project_name}
    with source_readonly(project_name) as proj:
        import SIL.LCModel as _L
        lp = _L.ILangProject(proj.project.LangProject)
        phon = lp.PhonologicalDataOA

        # --- every context OWNED by PhPhonData.ContextsOS -------------------
        contexts_os = {}
        for ctx in phon.ContextsOS:
            contexts_os[guid(ctx)] = cn(ctx)
        result["contexts_os_total"] = len(contexts_os)
        result["contexts_os_by_class"] = {}
        for g, c in contexts_os.items():
            result["contexts_os_by_class"][c] = \
                result["contexts_os_by_class"].get(c, 0) + 1

        # --- contexts reachable from PhonRulesOS ----------------------------
        from_rules = {}
        for tr in phon.PhonRulesOS:
            try:
                rr = cast(tr, "IPhRegularRule")
                for cell in getattr(rr, "StrucDescOS", []) or []:
                    collect_contexts_from_cell(cell, from_rules)
                for rhs in getattr(rr, "RightHandSidesOS", []) or []:
                    for cell in getattr(rhs, "StrucChangeOS", []) or []:
                        collect_contexts_from_cell(cell, from_rules)
                    for oa in ("LeftContextOA", "RightContextOA"):
                        collect_contexts_from_cell(getattr(rhs, oa, None), from_rules)
            except Exception as exc:
                result.setdefault("phon_rule_errors", []).append(str(exc))
        reachable_from_phon_rules = set()
        for s in from_rules.values():
            reachable_from_phon_rules |= s
        result["phon_rules_count"] = len(list(phon.PhonRulesOS))
        result["contexts_reachable_from_phon_rules"] = len(reachable_from_phon_rules)

        # --- what the enumerable categories can actually yield --------------
        # The registration question: a far endpoint no `enumerate_source`
        # yields cannot be planned, marked pulled-in or deselected (T089).
        enumerable = set()
        enumerable_by_class = {}
        for ps in phon.PhonemeSetsOS:
            for ph in ps.PhonemesOC:
                enumerable.add(guid(ph))
                enumerable_by_class["PhPhoneme"] = \
                    enumerable_by_class.get("PhPhoneme", 0) + 1
        for nc in phon.NaturalClassesOS:
            enumerable.add(guid(nc))
            enumerable_by_class[cn(nc)] = enumerable_by_class.get(cn(nc), 0) + 1
        result["enumerable_referents"] = len(enumerable)
        result["enumerable_by_class"] = enumerable_by_class

        # --- the affix process rules ---------------------------------------
        rules = []
        far_all = {}
        for entry in proj.LexiconAllEntries():
            e = entry._obj if hasattr(entry, "_obj") else entry
            forms = list(getattr(e, "AlternateFormsOS", []) or [])
            lexeme = getattr(e, "LexemeFormOA", None)
            if lexeme is not None:
                forms.append(lexeme)
            for form in forms:
                if cn(form) != "MoAffixProcess":
                    continue
                ap = cast(form, "IMoAffixProcess")
                rule_guid = guid(form)
                owned = set()
                members = []
                for m in getattr(ap, "InputOS", []) or []:
                    owned.add(guid(m))
                    members.append(m)
                far = []
                for idx, m in enumerate(members):
                    if cn(m) != "PhSequenceContext":
                        continue
                    seq = cast(m, "IPhSequenceContext")
                    for pos, ref in enumerate(getattr(seq, "MembersRS", []) or []):
                        rg = guid(ref)
                        if rg in owned:
                            continue
                        referent = None
                        rcls = cn(ref)
                        if rcls in ("PhSimpleContextSeg", "PhSimpleContextNC"):
                            referent = getattr(
                                cast(ref, "I" + rcls), "FeatureStructureRA", None)
                        rec = {
                            "input_index": idx,
                            "position": pos,
                            "class": rcls,
                            "guid": rg,
                            "owner_chain": owner_chain(ref),
                            "in_contexts_os": rg in contexts_os,
                            "reachable_from_phon_rules":
                                rg in reachable_from_phon_rules,
                            "referent_class": cn(referent) if referent is not None else "",
                            "referent_guid": guid(referent) if referent is not None else "",
                            "referent_enumerable": (
                                guid(referent) in enumerable
                                if referent is not None else False),
                        }
                        far.append(rec)
                        far_all[rg] = rec
                rules.append({
                    "rule_guid": rule_guid,
                    "input_count": len(members),
                    "far_refs": far,
                    "condition_4": bool(far),
                })
        result["affix_process_rules"] = len(rules)
        result["condition_4_rules"] = sum(1 for r in rules if r["condition_4"])
        result["distinct_far_endpoints"] = len(far_all)
        result["far_by_class"] = {}
        for r in far_all.values():
            result["far_by_class"][r["class"]] = \
                result["far_by_class"].get(r["class"], 0) + 1
        result["far_in_contexts_os"] = sum(
            1 for r in far_all.values() if r["in_contexts_os"])
        result["far_reachable_from_phon_rules"] = sum(
            1 for r in far_all.values() if r["reachable_from_phon_rules"])
        result["far_referents_enumerable"] = sum(
            1 for r in far_all.values() if r["referent_enumerable"])
        result["far_referent_by_class"] = {}
        for r in far_all.values():
            k = r["referent_class"] or "(none)"
            result["far_referent_by_class"][k] = \
                result["far_referent_by_class"].get(k, 0) + 1
        result["far_endpoints"] = list(far_all.values())
        result["rules"] = rules
    return result


def main():
    out = {}
    for name in CORPORA:
        print("[INFO] auditing %s" % name)
        try:
            out[name] = audit(name)
        except Exception as exc:  # noqa: BLE001 -- driver reports, never raises
            import traceback
            traceback.print_exc()
            out[name] = {"error": str(exc)}
        r = out[name]
        if "error" not in r:
            print("  affix process rules        : %s" % r["affix_process_rules"])
            print("  condition-4 rules          : %s" % r["condition_4_rules"])
            print("  distinct far endpoints     : %s" % r["distinct_far_endpoints"])
            print("  far by class               : %s" % r["far_by_class"])
            print("  ...owned by ContextsOS     : %s" % r["far_in_contexts_os"])
            print("  ...reachable from PhonRules: %s"
                  % r["far_reachable_from_phon_rules"])
            print("  far referents by class     : %s"
                  % r["far_referent_by_class"])
            print("  ...referent ENUMERABLE     : %s of %s"
                  % (r["far_referents_enumerable"], r["distinct_far_endpoints"]))
            print("  ContextsOS total           : %s (%s)"
                  % (r["contexts_os_total"], r["contexts_os_by_class"]))
    dest = os.path.abspath(os.path.join(
        _HERE, "..", "tests", "integration", "_snapshots",
        "t076-process-context-audit.json"))
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, sort_keys=True)
    print("[OK] wrote %s" % dest)


if __name__ == "__main__":
    main()
