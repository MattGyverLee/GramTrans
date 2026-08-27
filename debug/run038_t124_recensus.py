"""Feature 038 T124 -- re-census the sanctioned pairs against the Wave 2 code.

WHY THIS IS NOT `run038_before_after_pairs.py --tag t124`.

That driver writes into `GT038 Ejagham After` / `GT038 Ngoreme After`, which
are the DESTINATION HALF of the T078 comparand. Two independent things then
break:

  * `TestT078ThePost037Baseline.T078_FWDATA_STATUS_TODAY` asserts a per-project
    digest status table (`match` / `drifted`) and a `drifted` -> `match` flip is
    as red as the reverse. Re-transferring into a T078 destination moves its
    digest and there is no backup of any of the three AS THEY NOW STAND, so the
    flip is not reversible.
  * `_EVIDENCE_TARGETS` in the before/after driver guards exactly two of the
    three (`GT038 Ejagham After`, `GT038 Phase6 Target`) and guards them only
    on `--no-census`. `GT038 Ngoreme After` -- measured 2026-08-27 to be the
    ONLY destination still byte-identical to its T078 pin, and therefore the
    single most load-bearing comparand in the feature -- is guarded by nothing.

So T124 runs into THREE FRESH throwaways and leaves all three T078
destinations untouched. The T078 figures become historical by being kept, not
by being overwritten.

WHAT THE COMPARAND IS, SETTLED BY MEASUREMENT (2026-08-27).

T081 said "the sources have moved off their pinned digests". Measured against
`$.projects.{source,destination}.fwdata_sha256_after` in the three committed
T078 artifacts, that is FALSE:

    Ejagham W Mini            5ad15c10...c2c5c3ea   MATCH
    Ngoreme FLEx              838b7635...b23b607f   MATCH
    Mbugwe LizzieHC practice  fb6aadab...226c3161   MATCH

    GT038 Ejagham After       f3f99837... -> 56283578...   DRIFTED
    GT038 Ngoreme After       979fbdf6...e5b61bb7          MATCH
    GT038 Phase6 Target       28c89140... -> 276dca27...   DRIFTED

Every SOURCE is on its pin. The drift is entirely destination-side, on two of
three, and `T078_FWDATA_STATUS_TODAY` already records and asserts precisely
that (20 passed). So no source needs re-pinning and no fresh source pair needs
naming: the sanctioned pairs are intact and are re-run here as they stand.

THE BASELINE, AND THE ONE PLACE COMPARABILITY IS LOST.

All three throwaways are restored from the same
`Target 2026-07-06 0218.fwbackup`, so all three are censused against the shared
starter baseline `contracts/starter-baseline.json` -- the same document T078s
ejagham and ngoreme artifacts used, which keeps their NET columns comparable.

T078s MBUGWE artifact did NOT use that document: it used
`scratchpad/038_census/phase6-starter.json` as captured 2026-08-22T08:38:06,
and that file has since been re-captured in place (now 2026-08-25T14:35:56).
The 08-22 capture is not committed anywhere. The mbugwe NET column is
therefore NOT comparable to T078s mbugwe NET column, and this driver says so
in its output rather than letting the diff imply otherwise.

WHAT THIS DRIVER MEASURES THAT THE CENSUS CANNOT.

T119-T123 each have an acceptance stated per OWNING FIELD, per OWNING LIST, or
per MAPPING TYPE. `Lib/census.py` has no such dimension (zero hits for
`owning_field` / `possibility_list` / `PossibilitiesOS`) and the artifact
schema is `additionalProperties: false`. Rather than bump the census schema,
this driver reuses the Wave 1 instrument --
`debug/run038_phase10_owner_probe.py`, whose `$.classes.<C>.owners` is ALREADY
keyed `OwningClass.Field (flid=N)` -- against each fresh destination, and adds
two supplements the Wave 1 probe does not carry:

  * `lex_references`: every `LexReference` bucketed by its owning
    `LexRefType`s Name AND `MappingType`, which is what T124s third
    obligation is stated in terms of (3 TREE / 1 COLLECTION / 1 SEQUENCE).
  * `possibility_nesting`: `LexEntryInflType` / `LexEntryType` split into
    NESTED (`*.SubPossibilities`) vs TOP-LEVEL (`*.PossibilitiesOS`), which is
    T124s fourth obligation and a shape the census is structurally blind to
    (its count goes 7 -> 7 either way).

The Wave 1 probe is imported, not edited: editing it would change the
instrument that produced the six committed `owner-probe-*.json` artifacts.

Usage:

    python debug/run038_t124_recensus.py ejagham
    python debug/run038_t124_recensus.py ngoreme
    python debug/run038_t124_recensus.py mbugwe
    python debug/run038_t124_recensus.py all

    --probe-only   re-probe an already-transferred T124 destination and
                   re-read P5 off the committed artifact; no restore, no
                   transfer, no census.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO / "src"))
sys.path.insert(0, str(_REPO / "tests" / "integration"))

BACKUP = _REPO / "backups" / "Target 2026-07-06 0218.fwbackup"
PROJECTS_ROOT = Path("C:/ProgramData/SIL/FieldWorks/Projects")
_SNAPS = _REPO / "tests" / "integration" / "_snapshots"
_MAIN = _REPO.parent / "GramTrans" / "specs" / "038-transfer-fidelity-gaps"
_BASELINE = _MAIN / "contracts" / "starter-baseline.json"
_PROBE_OUT = _MAIN / "probes" / "t124"
_WAVE1_PROBES = _MAIN / "probes"

_PAIRS = {
    "ejagham": {
        "source": "Ejagham W Mini",
        "target": "GT038 T124 Ejagham",
        "t078": "census-038-t078-ejagham.json",
        "wave1_source_probe": "owner-probe-Ejagham-W-Mini.json",
        "baseline_comparable_to_t078": True,
    },
    "ngoreme": {
        "source": "Ngoreme FLEx",
        "target": "GT038 T124 Ngoreme",
        "t078": "census-038-t078-ngoreme.json",
        "wave1_source_probe": "owner-probe-Ngoreme-FLEx.json",
        "baseline_comparable_to_t078": True,
    },
    "mbugwe": {
        "source": "Mbugwe LizzieHC practice",
        "target": "GT038 T124 Mbugwe",
        "t078": "census-038-t078-mbugwe.json",
        "wave1_source_probe": "owner-probe-Mbugwe-LizzieHC-practice.json",
        # T078s mbugwe artifact used phase6-starter.json as it stood on
        # 2026-08-22; that capture no longer exists on disk.
        "baseline_comparable_to_t078": False,
    },
}

#: Never write to these, whatever else changes. The first three are the
#: standing project-safety rules; the last three are the T078 comparand and
#: are refused HERE rather than only in the before/after driver, because that
#: driver misses `GT038 Ngoreme After` and fires only on --no-census.
_FORBIDDEN_TARGETS = {
    "Ngoreme Target", "Ejagham W Target", "Esperanto",
    "GT038 Ejagham After", "GT038 Ngoreme After", "GT038 Phase6 Target",
}

#: The nine owning fields T114 measured for `FsFeatStruc`, in the descending
#: volume order T119s scope was fixed in, plus `PhNCFeatures.Features` which
#: T114 measured beside them. Reported per pair AND per field: a counts-only
#: acceptance would pass while changing nothing.
_T119_OWNER_FIELDS = (
    "MoStemMsa.MsFeatures (flid=5001001)",
    "FsComplexValue.Value (flid=53001)",
    "PartOfSpeech.ReferenceForms (flid=5049010)",
    "PhPhoneme.Features (flid=5092002)",
    "PhNCFeatures.Features (flid=5094001)",
    "MoInflAffMsa.InflFeats (flid=5038001)",
    "CmAnnotation.Features (flid=34008)",
    "MoDerivAffMsa.FromMsFeatures (flid=5031001)",
    "MoDerivAffMsa.ToMsFeatures (flid=5031002)",
    "MoAffixAllomorph.MsEnvFeatures (flid=5027001)",
)


class _Report:
    """The methods `run038_phase10_owner_probe.Main` calls."""

    def Info(self, msg):
        print("       [probe] %s" % msg)

    def Warning(self, msg):
        print("       [probe][WARN] %s" % msg)

    def Error(self, msg):
        print("       [probe][ERROR] %s" % msg)


def _best(multi):
    try:
        return multi.BestAnalysisAlternative.Text
    except Exception:
        return None


def _owner_field_counts(probe: dict, cls: str) -> dict:
    return ((probe.get("classes") or {}).get(cls) or {}).get("owners") or {}


def _norm(label: str) -> str:
    """Drop the `[runtime=...]` suffix so a label compares by owning field."""
    return label.split(" [runtime=")[0].strip()


def _by_field(owners: dict) -> dict:
    out = {}
    for label, count in owners.items():
        key = _norm(label)
        out[key] = out.get(key, 0) + int(count)
    return out


def _lex_reference_supplement(proj) -> dict:
    """Every `LexReference` bucketed by owning type NAME and `MappingType`.

    T123 proved the enumerator was blinded by a base-typed proxy and that a
    cast recovers 5 of 5 on `Ngoreme FLEx`. Whether those 5 SURVIVE into a
    destination is a per-`MappingType` question -- the TREE ones survive only
    if `TargetsRS[0]` was copied -- so the mapping type has to be in the
    artifact, and the Wave 1 probe does not record it.
    """
    import SIL.LCModel as lcm
    from SIL.LCModel import ICmObject

    ILexRefType = getattr(lcm, "ILexRefType", None)
    repo = getattr(lcm, "ILexReferenceRepository", None)
    if repo is None:
        return {"error": "SIL.LCModel exposes no ILexReferenceRepository"}
    try:
        refs = list(proj.ObjectsIn(repo))
    except Exception as exc:
        return {"error": "ObjectsIn(ILexReferenceRepository) raised: %r" % (exc,)}

    by_type, uncastable = {}, 0
    for ref in refs:
        owner = None
        try:
            owner = ICmObject(ref).Owner
        except Exception:
            pass
        name, mapping = "(no owner)", None
        if owner is not None:
            name = getattr(owner, "ClassName", "(unknown)")
            if ILexRefType is not None:
                try:
                    typed = ILexRefType(owner)
                    mapping = getattr(typed, "MappingType", None)
                    name = _best(getattr(typed, "Name", None)) or "(unnamed)"
                except Exception:
                    uncastable += 1
        try:
            targets = int(ref.TargetsRS.Count)
        except Exception:
            targets = None
        key = "%s | MappingType=%s" % (name, mapping)
        bucket = by_type.setdefault(
            key, {"references": 0, "targets_per_reference": []})
        bucket["references"] += 1
        bucket["targets_per_reference"].append(targets)
    return {
        "lex_references_total": len(refs),
        "owning_types_uncastable": uncastable,
        "by_owning_type": dict(sorted(by_type.items())),
    }


def _possibility_nesting_supplement(proj) -> dict:
    """`LexEntryInflType` / `LexEntryType` split NESTED vs TOP-LEVEL.

    T123s nesting fix claims ejagham should read 6 nested / 1 top-level rather
    than 2 / 5. The census cannot see it: the class count is 7 either way.
    """
    import SIL.LCModel as lcm
    from SIL.LCModel import ICmObject

    mdc = proj.Cache.MetaDataCacheAccessor
    out = {}
    for cls in ("LexEntryInflType", "LexEntryType", "CmPossibility"):
        repo = getattr(lcm, "I" + cls + "Repository", None)
        if repo is None:
            out[cls] = {"error": "SIL.LCModel exposes no I%sRepository" % cls}
            continue
        try:
            objs = [o for o in proj.ObjectsIn(repo)
                    if getattr(o, "ClassName", None) == cls]
        except Exception as exc:
            out[cls] = {"error": "ObjectsIn raised: %r" % (exc,)}
            continue
        nested = top = other = 0
        detail = {}
        for obj in objs:
            try:
                co = ICmObject(obj)
                flid = co.OwningFlid
                label = "%s.%s (flid=%s)" % (mdc.GetOwnClsName(flid),
                                             mdc.GetFieldName(flid), flid)
            except Exception as exc:
                label = "ERROR:%r" % (exc,)
            detail[label] = detail.get(label, 0) + 1
            # The top-level field is `CmPossibilityList.Possibilities`
            # (flid=8008). It is NOT spelled `PossibilitiesOS` in the MDC --
            # matching that name puts every top-level item in `other` and
            # reports 0 top-level on a project that is all top-level, which is
            # exactly the kind of silent zero this feature exists to remove.
            if ".SubPossibilities" in label:
                nested += 1
            elif ".Possibilities " in label or ".PossibilitiesOS" in label:
                top += 1
            else:
                other += 1
        out[cls] = {
            "exact_class": len(objs),
            "nested": nested,
            "top_level": top,
            "other": other,
            "by_owning_field": dict(
                sorted(detail.items(), key=lambda kv: -kv[1])),
        }
        # Per-GUID attribution, because the count buckets alone cannot answer
        # the question the ruling asks. The destination is restored from a
        # backup that already carries 3 `LexEntryInflType` of its own, so
        # "2 nested / 5 top-level" mixes pre-existing starter items with
        # transferred ones. Matching source GUID -> destination GUID separates
        # "the fix did not nest it" from "it was never this transfers object".
        if cls in ("LexEntryInflType", "LexEntryType"):
            out[cls]["by_guid"] = _nesting_by_guid(objs, mdc)
    return out


def _nesting_by_guid(objs, mdc) -> dict:
    """guid -> {name, nesting, owner_guid, owning_field} for each object."""
    from SIL.LCModel import ICmObject

    rows = {}
    for obj in objs:
        try:
            guid = str(obj.Guid)
        except Exception:
            continue
        owner_guid, label = None, "(?)"
        try:
            co = ICmObject(obj)
            flid = co.OwningFlid
            label = "%s.%s (flid=%s)" % (mdc.GetOwnClsName(flid),
                                         mdc.GetFieldName(flid), flid)
            owner = co.Owner
            if owner is not None:
                try:
                    owner_guid = str(ICmObject(owner).Guid)
                except Exception:
                    owner_guid = None
        except Exception:
            pass
        if ".SubPossibilities" in label:
            nesting = "nested"
        elif ".Possibilities " in label or ".PossibilitiesOS" in label:
            nesting = "top_level"
        else:
            nesting = "other"
        rows[guid] = {
            "name": _best(getattr(obj, "Name", None)),
            "nesting": nesting,
            "owning_field": label,
            "owner_guid": owner_guid,
        }
    return rows


def _probe_project(name: str, *, supplements: bool, run_wave1: bool = True) -> dict:
    """Open `name` READ-ONLY, run the Wave 1 probe plus the T124 supplements.

    `run_wave1=False` runs ONLY the supplements. Used for the sources: their
    Wave 1 `owner-probe-*.json` is already committed and their digests are
    measured to be on their T078 pins, so re-running the 26-class probe would
    reproduce a committed artifact at the cost of a full pass over a 73 MB
    project. The supplements are the part that does not exist yet.
    """
    from harness import full_run

    _PROBE_OUT.mkdir(parents=True, exist_ok=True)
    os.environ["GT038_PROBE_OUT"] = str(_PROBE_OUT)
    proj = full_run._open_source_readonly(name)
    try:
        if run_wave1:
            # Executed AFTER FLEx is initialized: the probe module does
            # `import SIL.LCModel` at top level.
            probe_src = (
                _REPO / "debug" / "run038_phase10_owner_probe.py"
            ).read_text(encoding="utf-8")
            namespace: dict = {"__name__": "run038_phase10_owner_probe"}
            exec(compile(probe_src, "run038_phase10_owner_probe.py", "exec"),
                 namespace)
            namespace["Main"](proj, _Report(), False)

        extra = {}
        if supplements:
            extra["lex_references"] = _lex_reference_supplement(proj)
            extra["possibility_nesting"] = _possibility_nesting_supplement(proj)
        return extra
    finally:
        try:
            proj.CloseProject()
        except Exception:
            pass


def _probe_path(project_name: str) -> Path:
    safe = "".join(c if (c.isalnum() or c in "-_") else "-"
                   for c in project_name)
    return _PROBE_OUT / ("owner-probe-%s.json" % safe)


def _starter_counts() -> dict:
    """class -> count, read off the shared starter baseline document.

    The document keys its rows under `entries` (a list of
    `{"class", "count", "names"}`), NOT under `classes` like a census
    artifact does. Reading the wrong key yields `None` for every class, which
    would silently make T121s "moved off the baseline" test unfalsifiable.
    """
    baseline = json.loads(_BASELINE.read_text(encoding="utf-8"))
    counts = {}
    for entry in (baseline.get("entries") or []):
        if isinstance(entry, dict) and entry.get("class"):
            counts[entry["class"]] = entry.get("count")
    return counts


def _run_pair(pair: str, argv) -> int:
    spec = _PAIRS[pair]
    source, target = spec["source"], spec["target"]
    if target in _FORBIDDEN_TARGETS:
        print("[FAIL] refusing to write to %r" % target)
        return 1
    if not _BASELINE.is_file():
        print("[FAIL] no starter baseline at %s" % _BASELINE)
        return 1
    t078_path = _SNAPS / spec["t078"]
    if not t078_path.is_file():
        print("[FAIL] no T078 comparand at %s" % t078_path)
        return 1

    from gramtrans import census_cli
    from gramtrans.Lib import census
    from harness import full_run
    from harness.restore import restore_target

    probe_only = "--probe-only" in argv
    census_path = _SNAPS / ("census-038-t124-%s.json" % pair)
    report_path = str(_REPO / "_run_reports" / ("038-t124-%s-report.json" % pair))
    target_path = str(PROJECTS_ROOT / target / (target + ".fwdata"))

    print()
    print("  ==== T124 RE-CENSUS: %s ====" % pair.upper())
    print("       %r -> %r (FRESH throwaway; no T078 destination touched)"
          % (source, target))
    if not spec["baseline_comparable_to_t078"]:
        print("       [WARN] T078s %s artifact used a starter baseline that no "
              "longer exists on disk;" % pair)
        print("              its NET column is NOT comparable to this run.")

    if not probe_only:
        Path(report_path).parent.mkdir(parents=True, exist_ok=True)
        print("[INFO] restoring %r from %s" % (target, BACKUP.name))
        restore_target(target, BACKUP)
        print("[INFO] full transfer on the Wave 2 branch (this takes a while)")
        full_run.run_full_transfer(
            source, target, target_path,
            exclude=frozenset(), ws_mapping_mode="full",
            report_path=report_path,
        )
        print("[INFO] census run")
        code = census_cli.main([
            "run",
            "--source", source,
            "--destination", target,
            "--baseline", str(_BASELINE),
            "--destination-freshly-created",
            "--run-report", report_path,
            "--out", str(census_path),
        ])
        print("[INFO] census run exit code = %s" % code)
    if not census_path.is_file():
        print("[FAIL] no census artifact at %s" % census_path)
        return 1

    artifact = json.loads(census_path.read_text(encoding="utf-8"))

    # ---- obligation 2: P5, read off the PREDICATE and not the exit code ----
    # `gate_artifact` returns exit_code_for(verdict), and DUPLICATE_IDENTITY
    # outranks anything a phase can say, so the process would exit 3 whether
    # or not P5 holds. The phase answer is only available in-process.
    p5 = census.evaluate_phase(artifact, 5)
    print()
    print("       P5 satisfied ...... %s" % p5.satisfied)
    print("       P5 failures ....... %d" % len(p5.failures))
    for line in p5.failures:
        print("         - %s" % line)
    print("       run verdict ....... %s (exit %s)"
          % (artifact.get("verdict"), artifact.get("exit_code")))

    # ---- the per-owning-field / per-list / per-mapping-type readings -------
    print()
    print("[INFO] probing the destination read-only (owner probe + supplements)")
    extra = _probe_project(target, supplements=True)
    dest_probe_path = _probe_path(target)
    dest_probe = json.loads(dest_probe_path.read_text(encoding="utf-8"))
    dest_probe.update(extra)
    dest_probe_path.write_text(json.dumps(dest_probe, indent=1) + "\n",
                               encoding="utf-8")
    print("[OK] wrote %s" % dest_probe_path)

    src_probe_path = _WAVE1_PROBES / spec["wave1_source_probe"]
    src_probe = (json.loads(src_probe_path.read_text(encoding="utf-8"))
                 if src_probe_path.is_file() else {})

    src_fields = _by_field(_owner_field_counts(src_probe, "FsFeatStruc"))
    dst_fields = _by_field(_owner_field_counts(dest_probe, "FsFeatStruc"))
    print()
    print("       ---- T119 FsFeatStruc, PER OWNING FIELD (source -> dest) ----")
    print("       %-46s %8s %8s %10s"
          % ("owning field", "source", "dest", "verdict"))
    t119_rows = {}
    for field in _T119_OWNER_FIELDS:
        s = int(src_fields.get(field, 0))
        d = int(dst_fields.get(field, 0))
        if s == 0 and d == 0:
            verdict = "NO_DATA"
        elif d >= s:
            verdict = "OK"
        elif d == 0:
            verdict = "TOTAL_LOSS"
        else:
            verdict = "SHORTFALL"
        t119_rows[field] = {"source": s, "dest": d, "verdict": verdict}
        print("       %-46s %8d %8d %10s" % (field, s, d, verdict))
    unlisted = sorted(set(dst_fields) - set(_T119_OWNER_FIELDS))
    for field in unlisted:
        print("       %-46s %8s %8d %10s"
              % (field, "-", dst_fields[field], "UNLISTED"))

    print()
    print("       ---- T122 CmPossibility, PER OWNING LIST ----")
    src_lists = ((src_probe.get("classes") or {}).get("CmPossibility")
                 or {}).get("possibility_lists") or {}
    dst_lists = ((dest_probe.get("classes") or {}).get("CmPossibility")
                 or {}).get("possibility_lists") or {}
    t122_rows = {}
    for key in sorted(set(src_lists) | set(dst_lists)):
        s, d = int(src_lists.get(key, 0)), int(dst_lists.get(key, 0))
        t122_rows[key] = {"source": s, "dest": d}
        print("       %-64s %6d %6d" % (key[:64], s, d))

    print()
    print("       ---- T121 PhCode / PhPhoneme vs the STARTER BASELINE ----")
    b_counts = _starter_counts()
    t121_rows = {}
    for cls in ("PhCode", "PhPhoneme"):
        starter = b_counts.get(cls)
        exact = ((dest_probe.get("classes") or {}).get(cls)
                 or {}).get("exact_class")
        # RAW labels here, deliberately not normalized: `PhCode` resolves its
        # owning field to `PhTerminalUnit.Codes` for BOTH halves, and the
        # `[runtime=...]` suffix is the only thing that separates the phoneme
        # codes from the BOUNDARY-MARKER codes. T121s acceptance is stated
        # separately for the two halves, so stripping the suffix -- which the
        # FsFeatStruc table does on purpose -- would collapse exactly the
        # distinction the acceptance is about.
        src_owners = {k: int(v) for k, v
                      in _owner_field_counts(src_probe, cls).items()}
        dst_owners = {k: int(v) for k, v
                      in _owner_field_counts(dest_probe, cls).items()}
        moved = (isinstance(starter, int) and isinstance(exact, int)
                 and exact > starter)
        t121_rows[cls] = {"starter_baseline_total": starter,
                          "destination_exact": exact,
                          "moved_off_baseline": moved,
                          "source_owners_raw": src_owners,
                          "destination_owners_raw": dst_owners}
        print("       %-12s starter=%-6s destination=%-6s  %s"
              % (cls, starter, exact,
                 "MOVED OFF THE BASELINE" if moved else "READS THE BASELINE"))
        for label in sorted(set(src_owners) | set(dst_owners)):
            print("         %-56s src=%-6s dest=%-6s"
                  % (label[:56], src_owners.get(label, 0),
                     dst_owners.get(label, 0)))

    print()
    print("       ---- T123 obligations 3 and 4 (SOURCE vs DESTINATION) ----")
    print("[INFO] probing the source read-only for the T124 supplements only")
    src_extra = _probe_project(source, supplements=True, run_wave1=False)
    src_supp_path = _PROBE_OUT / ("t124-supplements-%s.json" % (
        "".join(c if (c.isalnum() or c in "-_") else "-" for c in source)))
    src_supp_path.write_text(json.dumps(src_extra, indent=1) + "\n",
                             encoding="utf-8")
    print("[OK] wrote %s" % src_supp_path)

    src_lexrefs = src_extra.get("lex_references") or {}
    lexrefs = dest_probe.get("lex_references") or {}
    print("       LexReference total   source=%s  destination=%s"
          % (src_lexrefs.get("lex_references_total"),
             lexrefs.get("lex_references_total")))
    s_by = src_lexrefs.get("by_owning_type") or {}
    d_by = lexrefs.get("by_owning_type") or {}
    if not s_by and not d_by:
        print("         (no LexReference on either side -- this pair cannot "
              "corroborate obligation 3)")
    for key in sorted(set(s_by) | set(d_by)):
        s = (s_by.get(key) or {})
        d = (d_by.get(key) or {})
        print("         %-46s src refs=%-4s targets=%-14s | dest refs=%-4s targets=%s"
              % (key[:46], s.get("references", 0),
                 s.get("targets_per_reference", []),
                 d.get("references", 0), d.get("targets_per_reference", [])))

    src_nesting = src_extra.get("possibility_nesting") or {}
    nesting = dest_probe.get("possibility_nesting") or {}
    print("       %-18s %-26s %s" % ("", "SOURCE", "DESTINATION"))
    for cls in ("LexEntryInflType", "LexEntryType", "CmPossibility"):
        s = src_nesting.get(cls) or {}
        d = nesting.get(cls) or {}
        print("       %-18s exact=%-4s nest=%-4s top=%-5s exact=%-4s nest=%-4s top=%-4s other=%s"
              % (cls, s.get("exact_class"), s.get("nested"), s.get("top_level"),
                 d.get("exact_class"), d.get("nested"), d.get("top_level"),
                 d.get("other")))

    # The nesting verdict, per GUID. A source object whose GUID is present in
    # the destination is one THIS transfer is responsible for; if its nesting
    # differs, that is the defect the ruling names. A source GUID absent from
    # the destination is a different failure and is counted separately.
    nesting_verdict = {}
    for cls in ("LexEntryInflType", "LexEntryType"):
        s_by_guid = (src_nesting.get(cls) or {}).get("by_guid") or {}
        d_by_guid = (nesting.get(cls) or {}).get("by_guid") or {}
        same, changed, absent, dest_only = [], [], [], []
        for guid, srow in s_by_guid.items():
            drow = d_by_guid.get(guid)
            if drow is None:
                absent.append({"guid": guid, "name": srow.get("name"),
                               "source_nesting": srow.get("nesting")})
            elif drow.get("nesting") == srow.get("nesting"):
                same.append({"guid": guid, "name": srow.get("name"),
                             "nesting": srow.get("nesting")})
            else:
                changed.append({"guid": guid, "name": srow.get("name"),
                                "source_nesting": srow.get("nesting"),
                                "destination_nesting": drow.get("nesting")})
        for guid, drow in d_by_guid.items():
            if guid not in s_by_guid:
                dest_only.append({"guid": guid, "name": drow.get("name"),
                                  "nesting": drow.get("nesting")})
        nesting_verdict[cls] = {
            "matched_guid_same_nesting": same,
            "matched_guid_nesting_CHANGED": changed,
            "source_guid_absent_from_destination": absent,
            "destination_only_guids": dest_only,
        }
        print("       %s by GUID: same=%d CHANGED=%d absent=%d dest_only=%d"
              % (cls, len(same), len(changed), len(absent), len(dest_only)))
        for row in changed:
            print("         CHANGED %-30s %s -> %s"
                  % (str(row["name"])[:30], row["source_nesting"],
                     row["destination_nesting"]))
        for row in absent:
            print("         ABSENT  %-30s (source %s)"
                  % (str(row["name"])[:30], row["source_nesting"]))

    # ---- the T078 row diff, kept because T078 stays the comparand ----------
    t078 = json.loads(t078_path.read_text(encoding="utf-8"))
    t_rows = {r["class"]: r for r in (t078.get("classes") or [])}
    n_rows = {r["class"]: r for r in (artifact.get("classes") or [])}
    fixed, still, regressed = [], [], []
    for cls in sorted(set(t_rows) | set(n_rows)):
        bv = (t_rows.get(cls) or {}).get("verdict_class")
        av = (n_rows.get(cls) or {}).get("verdict_class")
        row = {"class": cls, "verdict_t078": bv, "verdict_t124": av,
               "source_t078": (t_rows.get(cls) or {}).get("source_count"),
               "source_t124": (n_rows.get(cls) or {}).get("source_count"),
               "net_t078": (t_rows.get(cls) or {}).get("destination_count_net"),
               "net_t124": (n_rows.get(cls) or {}).get("destination_count_net")}
        if av == "NOT_EVALUATED":
            continue
        if bv != "MATCHED" and av == "MATCHED":
            fixed.append(row)
        elif bv == "MATCHED" and av not in ("MATCHED", None):
            regressed.append(row)
        elif av not in ("MATCHED", None):
            still.append(row)
    print()
    print("       ---- vs T078 (historical) ----")
    print("       fixed=%d  still_short=%d  regressed=%d"
          % (len(fixed), len(still), len(regressed)))
    for label, rows in (("FIXED", fixed), ("REGRESSED", regressed)):
        if rows:
            print("       %s:" % label)
            for r in rows:
                print("         %-26s %s -> %s (net %s -> %s)"
                      % (r["class"], r["verdict_t078"], r["verdict_t124"],
                         r["net_t078"], r["net_t124"]))

    summary = {
        "pair": pair,
        "source": source,
        "destination": target,
        "backup": BACKUP.name,
        "starter_baseline": str(_BASELINE),
        "baseline_comparable_to_t078": spec["baseline_comparable_to_t078"],
        "t078_comparand": spec["t078"],
        "t078_status": "historical; destination not touched by this run",
        "census_artifact": census_path.name,
        "destination_probe": str(dest_probe_path),
        "source_probe": str(src_probe_path),
        "verdict": artifact.get("verdict"),
        "exit_code": artifact.get("exit_code"),
        "phase_5": {"satisfied": p5.satisfied, "failures": list(p5.failures)},
        "t119_per_owning_field": t119_rows,
        "t119_unlisted_destination_fields": {f: dst_fields[f] for f in unlisted},
        "t122_per_owning_list": t122_rows,
        "t121_starter_baseline_readings": t121_rows,
        "t123_lex_references": {"source": src_lexrefs, "destination": lexrefs},
        "t123_possibility_nesting": {"source": src_nesting,
                                     "destination": nesting},
        "t123_nesting_verdict_by_guid": nesting_verdict,
        "vs_t078": {"fixed": fixed, "still_short": still,
                    "regressed": regressed},
        "totals": artifact.get("totals"),
    }
    out = _SNAPS / ("recensus-038-t124-%s.json" % pair)
    out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    print("[OK] wrote %s" % out)
    return 0


def main(argv) -> int:
    which = (argv[1] if len(argv) > 1 else "").lower()
    if which == "all":
        pairs = ["ejagham", "ngoreme", "mbugwe"]
    elif which in _PAIRS:
        pairs = [which]
    else:
        print("[FAIL] usage: python debug/run038_t124_recensus.py "
              "{%s|all} [--probe-only]" % "|".join(sorted(_PAIRS)))
        return 2
    worst = 0
    for pair in pairs:
        try:
            code = _run_pair(pair, argv)
        except Exception as exc:  # noqa: BLE001 -- a live driver reports, never hides
            import traceback
            traceback.print_exc()
            print("[FAIL] %s raised: %r" % (pair, exc))
            code = 1
        worst = max(worst, code)
    return worst


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
