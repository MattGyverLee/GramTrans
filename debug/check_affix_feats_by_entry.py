"""Re-key the affix MSA / feature-assignment comparison by ENTRY, not MSA GUID.

The full-sweep run showed affix_msas and affix_msa_feats as source=88/target=88
with missing=88/extra=88 -- identical counts, fully disjoint GUID sets. That is
the signature of MSA GUIDs being REGENERATED in the target (the owning LexEntry
GUIDs are preserved -- `affixes` diffed clean), not of the feature assignments
being lost. Keying D4 by MSA GUID therefore cannot distinguish "features gone"
from "features intact under a new MSA identity".

This re-keys both sides by the STABLE owning-entry GUID and compares the MSA
payload (class, POS, slot memberships, and the (feature, value) pairs assigned)
as a canonical sorted bag. Feature/value/POS/slot GUIDs were all proven stable by
the same run, so this comparison is immune to MSA GUID churn.

Read-only: opens both projects writeEnabled=False. Run AFTER a sweep, against the
target in its post-Move state.
    python scratchpad/check_affix_feats_by_entry.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scratchpad"))

import run_fullsweep_verify as R  # noqa: E402 -- path bootstrap must precede

SOURCE = os.environ.get("GT_SOURCE", "Ejagham Mini")
TARGET = os.environ.get("GT_TARGET", "Target")


def by_entry(inv):
    """entry_guid -> canonical sorted bag of its MSA payloads (MSA GUID dropped)."""
    out = {}
    for msa_guid, rec in inv["affix_msas"].items():
        payload = {
            "class": rec["class"],
            "pos": rec["pos"],
            "slots": sorted(rec["slots"] or []),
            # feature assignments: sorted [feature_guid, value_guid] pairs
            "feats": sorted(inv["affix_msa_feats"].get(msa_guid, []),
                            key=lambda p: (p[0] or "", p[1] or "")),
        }
        out.setdefault(rec["entry"], []).append(json.dumps(payload, sort_keys=True))
    return {k: sorted(v) for k, v in out.items()}


def main():
    print("[INFO] read-only re-keyed comparison: %s -> %s" % (SOURCE, TARGET))
    src = by_entry(R.inventory(SOURCE))
    tgt = by_entry(R.inventory(TARGET))

    s, t = set(src), set(tgt)
    missing, extra = sorted(s - t), sorted(t - s)
    mismatched = [k for k in sorted(s & t) if src[k] != tgt[k]]

    n_src_feat = sum(len(json.loads(p)["feats"]) for v in src.values() for p in v)
    n_tgt_feat = sum(len(json.loads(p)["feats"]) for v in tgt.values() for p in v)

    print("  entries with affix MSAs   source=%d target=%d" % (len(src), len(tgt)))
    print("  (feature,value) pairs     source=%d target=%d" % (n_src_feat, n_tgt_feat))
    print("  entries missing in target %d" % len(missing))
    print("  entries extra in target   %d" % len(extra))
    print("  entries with differing MSA payload %d" % len(mismatched))

    for k in mismatched[:8]:
        print("\n  [MISMATCH] entry %s" % k)
        print("    source: %s" % json.dumps(src[k])[:600])
        print("    target: %s" % json.dumps(tgt[k])[:600])

    ok = not missing and not extra and not mismatched and n_src_feat == n_tgt_feat
    print("\n[%s] affix MSA payload + feature assignments preserved by entry"
          % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
