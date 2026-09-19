"""T077 -- READ-ONLY. Is every rule's `MembersRS` COMPLETE in the destination?

`run038_phase6_live.py` proves 18 of 18 rules arrive and that each one's
per-class member census matches its source. Neither claim reaches the thing
T076 actually changed: a `PhSequenceContext` counts as one input member
whether its `MembersRS` holds three references or none, so a rule could arrive
with the right shape and an EMPTY sequence -- which is precisely the
partly-filled `MembersRS` FR-023 calls silent content loss, and precisely what
the condition-4 skip existed to prevent.

So this compares, per rule and per sequence, the ORDERED list of member GUIDs
in the source against the destination. Both projects are opened read-only and
closed; nothing is written.
"""
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_ROOT, "src"))
sys.path.insert(0, os.path.join(_ROOT, "tests", "integration"))

from harness.full_run import source_readonly  # noqa: E402

SOURCE = os.environ.get("GT038_T077_SOURCE", "Mbugwe LizzieHC practice")
TARGET = os.environ.get("GT038_PHASE6_TARGET", "GT038 Phase6 Target")
OUT = os.path.join(_ROOT, "tests", "integration", "_snapshots",
                   "t077-membersrs-completeness.json")


def cn(o):
    try:
        return str(getattr(o, "ClassName", "") or "")
    except Exception:
        return ""


def guid(o):
    try:
        return str(getattr(o, "Guid", "") or "").lower()
    except Exception:
        return ""


def cast(o, iface):
    try:
        import SIL.LCModel as L
        return getattr(L, iface)(o)
    except Exception:
        return o


def rule_sequences(project_name):
    """`{rule_guid: {"sequences": [[member_guid, ...], ...],
                     "contexts_os": {guid: class}}}`."""
    out = {}
    contexts_os = {}
    with source_readonly(project_name) as proj:
        import SIL.LCModel as L
        lp = L.ILangProject(proj.project.LangProject)
        for ctx in lp.PhonologicalDataOA.ContextsOS:
            contexts_os[guid(ctx)] = cn(ctx)
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
                seqs = []
                for member in getattr(ap, "InputOS", []) or []:
                    if cn(member) != "PhSequenceContext":
                        continue
                    seq = cast(member, "IPhSequenceContext")
                    seqs.append({
                        "sequence_guid": guid(member),
                        "members": [
                            {"guid": guid(m), "class": cn(m)}
                            for m in (getattr(seq, "MembersRS", []) or [])
                        ],
                    })
                out[guid(form)] = {"sequences": seqs}
    return out, contexts_os


def main():
    print("[INFO] reading SOURCE %r" % SOURCE)
    src_rules, src_ctx = rule_sequences(SOURCE)
    print("[INFO] reading TARGET %r" % TARGET)
    tgt_rules, tgt_ctx = rule_sequences(TARGET)

    findings = []
    complete = 0
    empty_in_dest = 0
    for rule_guid, src in sorted(src_rules.items()):
        tgt = tgt_rules.get(rule_guid)
        if tgt is None:
            findings.append({"rule": rule_guid, "problem": "RULE_ABSENT"})
            continue
        src_seqs = {s["sequence_guid"]: s["members"] for s in src["sequences"]}
        tgt_seqs = {s["sequence_guid"]: s["members"] for s in tgt["sequences"]}
        for sg, src_members in sorted(src_seqs.items()):
            tgt_members = tgt_seqs.get(sg)
            if tgt_members is None:
                findings.append({"rule": rule_guid, "sequence": sg,
                                 "problem": "SEQUENCE_ABSENT"})
                continue
            if not tgt_members and src_members:
                empty_in_dest += 1
                findings.append({"rule": rule_guid, "sequence": sg,
                                 "problem": "MEMBERS_EMPTY",
                                 "source_count": len(src_members)})
                continue
            s_ids = [m["guid"] for m in src_members]
            t_ids = [m["guid"] for m in tgt_members]
            if s_ids != t_ids:
                findings.append({
                    "rule": rule_guid, "sequence": sg,
                    "problem": "MEMBERS_DIFFER",
                    "source": s_ids, "destination": t_ids,
                })
            else:
                complete += 1

    total_seqs = sum(len(r["sequences"]) for r in src_rules.values())
    # Which of the source's ContextsOS members the destination now holds,
    # restricted to the ones a rule sequence actually references.
    referenced = set()
    for r in src_rules.values():
        for s in r["sequences"]:
            for m in s["members"]:
                if m["guid"] in src_ctx:
                    referenced.add(m["guid"])
    co_created = sorted(g for g in referenced if g in tgt_ctx)
    missing = sorted(g for g in referenced if g not in tgt_ctx)

    payload = {
        "source": SOURCE,
        "destination": TARGET,
        "read_only": True,
        "source_rules": len(src_rules),
        "destination_rules": len(tgt_rules),
        "source_sequences": total_seqs,
        "sequences_identical": complete,
        "sequences_empty_in_destination": empty_in_dest,
        "shared_contexts_referenced_by_a_sequence": len(referenced),
        "shared_contexts_present_in_destination": len(co_created),
        "shared_contexts_missing_from_destination": missing,
        "source_contexts_os_total": len(src_ctx),
        "destination_contexts_os_total": len(tgt_ctx),
        "findings": findings,
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)

    print("[INFO] rules            : %s source / %s destination"
          % (len(src_rules), len(tgt_rules)))
    print("[INFO] sequences        : %s source, %s IDENTICAL in destination"
          % (total_seqs, complete))
    print("[INFO] empty in dest    : %s" % empty_in_dest)
    print("[INFO] shared contexts referenced by a sequence: %s"
          % len(referenced))
    print("[INFO]   ...present in the destination         : %s"
          % len(co_created))
    print("[INFO]   ...MISSING                            : %s" % len(missing))
    print("[INFO] ContextsOS totals: source %s / destination %s"
          % (len(src_ctx), len(tgt_ctx)))
    print("[OK] wrote %s" % OUT)
    if findings:
        print("[FAIL] %s finding(s):" % len(findings))
        for f in findings[:10]:
            print("       %s" % f)
        return 1
    print("[OK]   every sequence's MembersRS is identical in the destination")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
