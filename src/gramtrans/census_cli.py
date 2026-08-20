"""Feature 038 -- the per-object-class census CLI (T021).

    python -m gramtrans.census_cli capture-baseline --project ... --out ...
    python -m gramtrans.census_cli run   --source ... --destination ... --out ...
    python -m gramtrans.census_cli gate  --artifact ... [--phase N]
    python -m gramtrans.census_cli diff  --before ... --after ...

THIS IS THE INSTRUMENT, AND IT IS NOT A DEBUG SCRIPT (SC-009). Research R2 is
binding: the census lives in `Lib/census.py` (the engine) plus this file (the
command surface), and explicitly NOT in `debug/audit_object_census.py`, because
"a release gate cannot live in unsupported scratch". Every artifact this module
writes therefore stamps `instrument.name` as `INSTRUMENT_NAME` below -- never a
`debug/` path -- and `quickstart.md`'s `debug/audit_object_census.py`
invocations are stale (T025 sweeps them).

`--destination`, NEVER `--target`. R2's own sketch said `--target`; the schema,
`fidelity-census.md` and every artifact field say *destination*, and one word
for one concept is worth more than fidelity to a sketch. `--target` is not
merely unused here: `tests/integration/test_object_census.py` asserts the
parser does not define it.

THERE IS NO ESCAPE HATCH, BY CONSTRUCTION
-----------------------------------------
`fidelity-census.md` 5.3: "Staleness and absence are verdicts, not warnings.
There is no path on which a missing baseline yields exit 0." This module has no
`--force`, no `--allow-missing-baseline`, no `--warn-only`, no `--exit-zero` and
no `--non-strict`, and it must never grow one:
`test_no_flag_combination_yields_exit_zero_without_a_baseline` probes 17
candidate hatch names against `build_parser()`'s real option strings and
exercises every one that exists over a baseline-less artifact, asserting all are
non-zero. A hatch added here would be found, exercised, and would have to fail
anyway -- so the only shape a hatch could take is a lie.

The gate's answer is not this module's to compute either. Verdicts, the section
9 exit table, the published severity ordering and the phase predicates all come
from `Lib/census.py` (`gate_artifact`, `exit_code_for`, `most_severe_verdict`).
A second copy of the exit table living next to a CLI is precisely the drift this
feature exists to end, so nothing here re-declares one; `USAGE_EXIT_CODE` and
`PHASE_UNSATISFIED_EXIT_CODE` are the two documented non-verdict codes and the
second of them is *read out of* the table rather than written down again.

NO LIVE-FLEx IMPORT AT MODULE SCOPE. `tests/integration/test_object_census.py`
imports this module at collection time and must stay runnable with no
FieldWorks host and no project. Every `flexicon` / `SIL.LCModel` /
`FLExGlobals` touch below is inside a function, exactly as `Lib/census.py` does
it and for the reason its docstring records
(`test_034_standalone_preview_live.py` demonstrates what an unconditional
`FLExInitialize()` at import time does to a test session on this machine).

READ-ONLY, WITHOUT EXCEPTION. `capture-baseline` and `run` are the only
subcommands that open a project, both do it `writeEnabled=False`, and both go
through `census.read_project`, which digests the `.fwdata` before the open and
again after the CLOSE and raises `CENSUS_ERROR` if it moved. There is no flag
that disables that comparison.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import __version__ as GRAMTRANS_VERSION
from .Lib import census, models

# ---------------------------------------------------------------------------
# The surface
# ---------------------------------------------------------------------------

#: The four subcommands, in the order the quickstart uses them: capture a
#: baseline, run a census, gate an artifact, diff two artifacts. Pinned as a
#: tuple by `tests/integration/test_object_census.py`.
SUBCOMMANDS: tuple = ("capture-baseline", "run", "gate", "diff")

#: How the instrument is invoked, and how it names itself in the artifact.
#: `instrument.name` must not contain "debug/" (SC-009).
PROG = "python -m gramtrans.census_cli"
INSTRUMENT_NAME = "gramtrans.census_cli"

#: A MALFORMED INVOCATION IS NOT A CENSUS VERDICT. argparse already exits 2 for
#: an unknown flag or a missing required one, so the no-subcommand case uses the
#: same code rather than inventing a second convention. No artifact is written
#: on this path, so there is no verdict for it to be confused with.
USAGE_EXIT_CODE = 2

#: The gate exit code for "the census itself passes, but the named PHASE
#: predicate does not". Section 9's verdict table has no token for it -- a phase
#: predicate is a claim about coverage of the classes the phase names, so the
#: code is READ OUT of the table's COVERAGE_INCOMPLETE entry rather than picked
#: independently. It is deliberately not 0: 9.1 says a phase "is done when the
#: census run for its predicate exits 0 WITH the predicate satisfied".
PHASE_UNSATISFIED_EXIT_CODE = census.exit_code_for("COVERAGE_INCOMPLETE")

#: T024b -- "the census passes, but only because 5.2's gross-basis cap turned a
#: measured shortfall into accounting". NOT a pass and NOT a hard failure.
#:
#: Measured before this existed: both live sanity pairs reported
#: `CENSUS_ACCOUNTED` / exit 0 / `passed=True` while carrying 44-47 failing rows
#: and 74,157 units of unexplained shortfall. That is the cap behaving exactly as
#: specified, and it is still an unsafe default for a release gate -- the headline
#: said success on a catastrophically incomplete transfer, and the failing
#: evidence surfaced only when the caller happened to pass `--phase`. Section 9's
#: own comment says there is deliberately no verdict meaning "loss reported,
#: review advisable, exit success"; a bare exit 0 here was one anyway.
#:
#: 8, not 3: codes 0-7 are all spoken for by the verdict table (3 is
#: DUPLICATE_IDENTITY), and a non-verdict outcome must never borrow a verdict's
#: code -- that is the drift `USAGE_EXIT_CODE`'s comment warns about. The verdict
#: TOKEN is unchanged (`CENSUS_ACCOUNTED`): the artifact schema is
#: `additionalProperties: false` and inventing a tenth token is forbidden, so this
#: is a property of the process outcome, not of the document.
CAPPED_PASS_EXIT_CODE = 8

#: The two baseline kinds this CLI can capture. `NONE` is not capturable: an
#: absent baseline is `StarterBaseline.missing()`, produced by finding no
#: `--baseline`, never written to a file and claimed as a measurement.
CAPTURABLE_BASELINE_KINDS: tuple = (
    models.StarterBaselineKind.STARTER_CAPTURE.value,
    models.StarterBaselineKind.PRE_TRANSFER_CENSUS.value,
)

#: Rows whose `class` is reported without being measured carry these counts.
#: `$defs.classRow` says a count is `null` "only on a NOT_EVALUATED row where
#: the class could not be counted at all", but `models.ClassCensusRow` requires
#: an int, so an `excluded_not_measurable` row is emitted as 0/0 plus the note
#: below. OPEN ITEM, flagged rather than papered over: the schema's honest value
#: here is null and the in-memory model cannot express it.
_NOT_MEASURED_NOTE = (
    "not measured: in_class_list_via 'excluded_not_measurable' (an abstract "
    "LCM base with no factory). The 0 counts are placeholders -- the schema's "
    "honest value is null, which models.ClassCensusRow cannot carry."
)

_A1_BASELINE_NOTE = (
    "Amendment A1: this row is one half of a class split by owning feature "
    "system, and the baseline document is not split, so no starter "
    "subtraction is applied to it (starter_baseline_source "
    "'absent_from_baseline')."
)


# ---------------------------------------------------------------------------
# Console
# ---------------------------------------------------------------------------

def _say(line: str = "") -> None:
    print(line)


def _info(line: str) -> None:
    print("[INFO] " + line)


def _ok(line: str) -> None:
    print("[OK] " + line)


def _warn(line: str) -> None:
    print("[WARN] " + line)


def _fail(line: str) -> None:
    print("[FAIL] " + line)


# ---------------------------------------------------------------------------
# Reading files the operator named
#
# Every failure here is a MESSAGE plus a non-zero exit, never a traceback: a
# gate whose failure output is a stack trace is a gate a release engineer
# learns to ignore.
# ---------------------------------------------------------------------------

def _load_json(path: Path, what: str) -> dict:
    """One JSON object from `path`, or `CensusError` naming what was wanted."""
    if not path.is_file():
        raise census.CensusError(
            "no " + what + " at " + str(path)
            + " -- the census gates on a document it can read; a path that "
            "does not resolve is a failure, never an empty pass"
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise census.CensusError(
            "could not read the " + what + " at " + str(path) + ": "
            + type(exc).__name__ + ": " + str(exc)
        ) from exc
    except ValueError as exc:
        raise census.CensusError(
            "the " + what + " at " + str(path) + " is not valid JSON: "
            + str(exc)
        ) from exc
    if not isinstance(data, dict):
        raise census.CensusError(
            "the " + what + " at " + str(path) + " is a "
            + type(data).__name__ + ", not a JSON object"
        )
    return data


def load_artifact(path: Path) -> dict:
    """One census artifact, shape-checked enough to fail legibly.

    The full check is `census.validate_artifact`; this only refuses documents
    that are not censuses at all, so `gate` says "that is not a census
    artifact" instead of reporting a confident verdict over a stranger's JSON.
    """
    artifact = _load_json(path, "census artifact")
    version = artifact.get("schema_version")
    if not isinstance(version, int):
        raise census.CensusError(
            str(path) + " has no integer schema_version, so it is not a "
            "census artifact (contracts/census-artifact.schema.json requires "
            "one, and readers select their validator by it)"
        )
    if version > census.CENSUS_SCHEMA_VERSION:
        raise census.CensusError(
            str(path) + " declares schema_version " + str(version)
            + " but this instrument implements "
            + str(census.CENSUS_SCHEMA_VERSION)
            + " -- an artifact from a newer census must be gated by the newer "
            "instrument, not silently by this one"
        )
    if not isinstance(artifact.get("classes"), list):
        raise census.CensusError(
            str(path) + " carries no `classes` array, so there is nothing to "
            "gate (FR-012 requires one row per class, and an absent row is a "
            "coverage defect rather than a clean class)"
        )
    return artifact


# ---------------------------------------------------------------------------
# The instrument block
# ---------------------------------------------------------------------------

def _git_head(root: Path) -> tuple:
    """`(short_sha, dirty)` for `root`, or `("unknown", False)`.

    Recorded rather than inferred (`$defs.instrument.gramtrans_dirty`): a dirty
    tree does not invalidate the counts, it makes the artifact
    non-reproducible, and that is worth saying out loud.
    """
    import subprocess  # noqa: PLC0415 -- not needed to import this module

    def _git(*args):
        return subprocess.run(  # noqa: S603 -- fixed argv, no shell
            ("git", "-C", str(root)) + args,
            capture_output=True, text=True, timeout=30, check=False,
        )

    try:
        head = _git("rev-parse", "--short", "HEAD")
        status = _git("status", "--porcelain")
    except (OSError, ValueError):
        return "unknown", False
    if head.returncode != 0:
        return "unknown", False
    return head.stdout.strip() or "unknown", bool(status.stdout.strip())


def _flexicon_provenance() -> tuple:
    """`(version, path)` of the installed flexicon, or `("", "")`.

    A `site-packages` path here means the editable install did not take effect
    and the whole run measures the wrong code -- which is why it is recorded in
    the artifact rather than checked once by a human.
    """
    try:
        import flexicon  # noqa: PLC0415 -- see the module docstring
    except Exception:  # noqa: BLE001 -- flexicon raises bare Exception
        return "", ""
    path = str(getattr(flexicon, "__file__", "") or "")
    version = str(getattr(flexicon, "__version__", "") or "")
    if not version:
        try:
            import importlib.metadata as metadata  # noqa: PLC0415

            version = metadata.version("pyflexicon")
        except Exception:  # noqa: BLE001
            version = ""
    return version, path


def running_flex_version() -> str:
    """The running FieldWorks version, or "" when it cannot be read.

    Read through `standalone/fwglobals.py`, which
    `tests/unit/test_034_fwglobals_only.py` makes the SOLE permitted reader of
    the FieldWorks globals -- so this module never names one. `fwglobals`
    refuses to read before `FLExInitialize()` has completed, so the latch is
    set from `census`'s own initialiser rather than guessed at.
    """
    from .standalone import fwglobals  # noqa: PLC0415 -- see module docstring

    try:
        census._ensure_flex_initialized()  # noqa: SLF001 -- the one latch
        fwglobals.mark_initialized()
        return fwglobals.short_version()
    except Exception:  # noqa: BLE001 -- absence is reported, never fatal here
        return ""


def instrument_block(*, root: Path, flex_version: str = "") -> dict:
    """-> artifact `instrument`. `name` is never a `debug/` path (SC-009)."""
    sha, dirty = _git_head(root)
    flexicon_version, flexicon_path = _flexicon_provenance()
    block = {
        "name": INSTRUMENT_NAME,
        "version": GRAMTRANS_VERSION,
        "gramtrans_sha": sha,
        "gramtrans_dirty": dirty,
        "python_version": sys.version.split()[0],
    }
    if flexicon_version:
        block["flexicon_version"] = flexicon_version
    if flexicon_path:
        block["flexicon_path"] = flexicon_path
    if flex_version:
        block["flex_version"] = flex_version
    return block


# ---------------------------------------------------------------------------
# The baseline DOCUMENT (the file `--baseline` names)
#
# `$defs.starterBaseline` is the provenance block EMBEDDED in an artifact and
# carries no entries; the subtraction needs the entries, so the file on disk is
# this richer document and `census.starter_baseline_artifact` narrows it to the
# schema's shape on the way into an artifact. `class_count` and
# `carries_natural_keys` are written for the quickstart's one-liner check and
# are RECOMPUTED from `entries` on load -- a document cannot talk its way into
# a stronger claim than its own content supports.
# ---------------------------------------------------------------------------

def baseline_content_hash(entries) -> str:
    """A stable digest of a baseline's inventory.

    `data-model.md`:90 declares `content_hash` the staleness detector while the
    schema detects staleness from `flex_version` / `data_model_version` and has
    no such property (T015's disagreement 2). It is kept because cheap equality
    between two captures is genuinely useful, and it is document-only: the
    models translation table maps it to None, so it never reaches an artifact.
    """
    payload = json.dumps(
        [[e.object_class, e.count, list(e.names)]
         for e in sorted(entries, key=lambda e: e.object_class)],
        ensure_ascii=False, sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def baseline_document(
    baseline, *, fwdata_sha256: str = "", instrument: Optional[dict] = None,
) -> dict:
    """-> the JSON document `capture-baseline` writes and `--baseline` reads."""
    document = {
        "schema_version": baseline.schema_version,
        "kind": baseline.kind.value,
        "project_name": baseline.captured_from,
        "captured_at": baseline.captured_at,
        "flex_version": baseline.flex_version,
        "data_model_version": baseline.data_model_version,
        "content_hash": baseline.content_hash,
        # Derived, written for the reader; recomputed on load.
        "class_count": baseline.class_count,
        "carries_natural_keys": baseline.carries_natural_keys,
        "entries": [
            {"class": e.object_class, "count": e.count, "names": list(e.names)}
            for e in baseline.entries
        ],
    }
    if fwdata_sha256:
        document["fwdata_sha256"] = fwdata_sha256
    if instrument:
        document["instrument"] = dict(instrument)
    return document


def load_baseline_document(path: Path) -> models.StarterBaseline:
    """One baseline document -> a `StarterBaseline`, or a legible failure.

    Never returns `None` and never returns a NONE-kind baseline: a path the
    operator named and the census could not read is an error, not an absence.
    Absence is what happens when no `--baseline` is given at all.
    """
    document = _load_json(path, "baseline document")
    kind = document.get("kind")
    if kind not in CAPTURABLE_BASELINE_KINDS:
        raise census.CensusError(
            "the baseline at " + str(path) + " declares kind " + repr(kind)
            + ", not one of " + repr(CAPTURABLE_BASELINE_KINDS)
            + " -- kind 'none' is never written to a file: an absent baseline "
            "is the ABSENCE of --baseline, and it is a verdict "
            "(BASELINE_MISSING, exit 4), not a document"
        )
    raw_entries = document.get("entries")
    if not isinstance(raw_entries, list) or not raw_entries:
        raise census.CensusError(
            "the baseline at " + str(path) + " carries no entries -- a "
            "baseline with no per-class counts is indistinguishable from no "
            "baseline at all and must not be passed off as a measurement"
        )
    entries = []
    for index, raw in enumerate(raw_entries):
        if not isinstance(raw, dict):
            raise census.CensusError(
                "the baseline at " + str(path) + " entry " + str(index)
                + " is a " + type(raw).__name__ + ", not an object"
            )
        names = raw.get("names") or ()
        if not isinstance(names, (list, tuple)):
            raise census.CensusError(
                "the baseline at " + str(path) + " entry " + str(index)
                + " has a non-list `names`"
            )
        try:
            entries.append(models.StarterBaselineEntry(
                object_class=str(raw.get("class") or ""),
                count=int(raw.get("count")),
                names=tuple(str(n) for n in names),
            ))
        except (TypeError, ValueError) as exc:
            raise census.CensusError(
                "the baseline at " + str(path) + " entry " + str(index)
                + " (" + repr(raw.get("class")) + ") is not usable: "
                + str(exc)
            ) from exc
    try:
        return models.StarterBaseline(
            kind=models.StarterBaselineKind(kind),
            flex_version=str(document.get("flex_version") or ""),
            captured_at=str(document.get("captured_at") or ""),
            captured_from=str(document.get("project_name") or ""),
            entries=tuple(entries),
            content_hash=str(document.get("content_hash") or ""),
            path=str(path),
            source_census_id=str(document.get("source_census_id") or ""),
            data_model_version=document.get("data_model_version"),
        )
    except ValueError as exc:
        raise census.CensusError(
            "the baseline at " + str(path) + " is not a usable baseline: "
            + str(exc)
        ) from exc


# ---------------------------------------------------------------------------
# Opening a project, and the two extra read-only passes
# ---------------------------------------------------------------------------

def _read_only_handle(project_name: str):
    """Open one project with `writeEnabled=False`, and nothing else.

    Passed to `census.read_project` as its `open_project` seam so this module
    has ONE place that opens a project: the natural-key pass (baseline capture)
    and the duplicate pass (`run`) both need the handle while it is open, and
    `read_project` closes it in a `finally` before it returns.
    """
    from flexicon import FLExProject  # noqa: PLC0415 -- see module docstring

    census._ensure_flex_initialized()  # noqa: SLF001 -- the one latch
    handle = FLExProject()
    handle.OpenProject(projectName=project_name, writeEnabled=False)
    return handle


def natural_keys_for(handle, class_names) -> dict:
    """`{class: (key, ...)}` for every class the 035 roster gives a key.

    The writing-system resolution is `census._ws_handle_for` on purpose: a
    second implementation of "which writing system does this key live in" is
    exactly the drift the roster's measured `Yi Sichuan` counterexample
    punishes (matching a secondary vernacular fabricated 16 matches).
    """
    ws_handles: dict = {}
    out: dict = {}
    for name in dict.fromkeys(class_names):
        spec = census.NATURAL_KEY_DEFINITIONS.get(name)
        if spec is None:
            continue
        if spec.ws_scope not in ws_handles:
            ws_handles[spec.ws_scope] = census._ws_handle_for(  # noqa: SLF001
                handle, spec.ws_scope)
        keys = []
        for obj in census.objects_in_class(handle, name):
            key = census.natural_key_of(obj, spec, ws_handles[spec.ws_scope])
            if key is not None:
                keys.append(key)
        out[name] = tuple(keys)
    return out


# ---------------------------------------------------------------------------
# capture-baseline  (and `run --pre-transfer`, which is the same capture)
# ---------------------------------------------------------------------------

def _measurable_classes(class_list) -> tuple:
    """The classes the counting pass asks for.

    `excluded_not_measurable` entries are left out BY NAME: they are abstract
    LCM bases with no factory, so asking for a repository count would turn
    their expected absence into an `unresolved_accessors` entry and drive the
    whole run to CENSUS_ERROR. They are still emitted as rows (CP-2), just
    never counted.
    """
    return tuple(dict.fromkeys(
        e.object_class for e in class_list.entries
        if e.in_class_list_via != "excluded_not_measurable"
    ))


def _report_unmeasurable(reading) -> None:
    """Print every unresolved accessor, one line per class, and raise.

    An unresolved accessor is a REPORTED OUTCOME, never a skip
    (`Lib/census.py` T017 header). The run stops here rather than emitting
    rows: `models.ClassCensusRow` cannot carry a null count, so there is no
    honest row to write for a class nobody could count.
    """
    for entry in census.unmeasurable_errors(reading):
        _fail(json.dumps(entry, ensure_ascii=False))
    raise census.CensusError(
        str(len(reading.counts.unmeasurable)) + " class(es) could not be "
        "counted in " + repr(reading.name) + ": "
        + ", ".join(reading.counts.unmeasurable)
        + " -- the census may fail to measure a class; it may not fail QUIETLY"
    )


def capture_baseline(
    project: str,
    out: Path,
    *,
    kind: str = models.StarterBaselineKind.STARTER_CAPTURE.value,
    projects_root: Optional[str] = None,
    root: Optional[Path] = None,
    open_project=None,
) -> int:
    """Capture one project's per-class inventory as a baseline document.

    `open_project` is the same injection seam `census.read_project` exposes; it
    is a FUNCTION argument and deliberately not a CLI flag -- it exists so this
    path is exercisable without a FieldWorks host, not so an operator can
    substitute the project being measured.
    """
    base = census.repo_root() if root is None else Path(root)
    class_list = census.derive_class_list(base)
    wanted = _measurable_classes(class_list)
    opener = open_project or _read_only_handle
    captured_keys: dict = {}

    def _open_and_read_keys(name: str):
        handle = opener(name)
        # Taken while the handle is open, because `read_project` closes it
        # before returning and a baseline of counts alone cannot support the
        # matched subtraction of fidelity-census.md 5.2.
        captured_keys.update(natural_keys_for(handle, wanted))
        return handle

    _info("capturing a " + kind + " baseline from " + repr(project)
          + " (read-only, " + str(len(wanted)) + " classes)")
    reading = census.read_project(
        project, wanted,
        projects_root=projects_root,
        open_project=_open_and_read_keys,
    )
    if reading.counts.unmeasurable:
        _report_unmeasurable(reading)

    entries = []
    for name in wanted:
        count = reading.counts.counts[name]
        names = tuple(captured_keys.get(name, ()))
        try:
            entries.append(models.StarterBaselineEntry(
                object_class=name, count=count, names=names))
        except ValueError as exc:
            # Most often: the repository count and the enumeration disagree,
            # which is a defect in the measurement itself and must be named as
            # one rather than surfacing as a bare ValueError from a model.
            raise census.CensusError(
                "the capture of " + repr(name) + " from " + repr(project)
                + " is not usable (count " + str(count) + ", "
                + str(len(names)) + " natural key(s)): " + str(exc)
            ) from exc
    entries = tuple(entries)
    flex_version = running_flex_version()
    if not flex_version:
        raise census.CensusError(
            "the running FieldWorks version could not be read, so this "
            "baseline's staleness could never be judged -- and a baseline "
            "whose staleness cannot be judged cannot be trusted "
            "(fidelity-census.md 5.3). Nothing was written."
        )
    try:
        baseline = models.StarterBaseline(
            kind=models.StarterBaselineKind(kind),
            flex_version=flex_version,
            captured_at=reading.counted_at,
            captured_from=project,
            entries=entries,
            content_hash=baseline_content_hash(entries),
            path=str(out),
            data_model_version=reading.data_model_version,
        )
    except ValueError as exc:
        raise census.CensusError(
            "the capture from " + repr(project) + " is not a usable "
            "baseline: " + str(exc)
        ) from exc

    document = baseline_document(
        baseline,
        fwdata_sha256=reading.fwdata_sha256_after,
        instrument=instrument_block(root=base, flex_version=flex_version),
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")

    _info("digest " + reading.fwdata_sha256_before[:12] + "... unchanged "
          "before and after (the census wrote nothing)")
    _info("classes " + str(baseline.class_count)
          + "  objects " + str(sum(e.count for e in entries))
          + "  flex_version " + flex_version
          + "  data_model_version " + str(reading.data_model_version))
    if not baseline.carries_natural_keys:
        keyless = [e.object_class for e in entries
                   if e.count > 0 and len(e.names) != e.count]
        _warn("carries_natural_keys is FALSE: " + str(len(keyless))
              + " class(es) hold objects this capture could not name, e.g. "
              + ", ".join(sorted(keyless)[:8])
              + ". Every census row against this baseline is therefore forced "
              "onto the weaker `baseline_gross` subtraction basis "
              "(fidelity-census.md 5.2).")
    else:
        _info("carries_natural_keys True -- the matched subtraction of 5.2 is "
              "available")
    _ok("wrote " + str(out))
    return 0


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _CensusIdentity:
    """The four fields `census.build_artifact` reads off its census argument.

    NOT a second `FidelityCensus`, and not a shortcut: `models.FidelityCensus`
    rejects two rows for one class, which Amendment A1's `FsFeatStrucType`
    split deliberately produces (one row per owning feature system, same
    `object_class`). So the emitted row set cannot be held by a real
    `FidelityCensus` at all. FLAGGED for A1's resolution rather than worked
    around by dropping half the split or by handing `FidelityCensus` a row set
    that is not the one emitted.
    """

    run_id: str
    taken_at: str
    baseline: object
    schema_version: int = census.CENSUS_SCHEMA_VERSION


def _census_id(taken_at: str) -> str:
    """`CENSUS-YYYYMMDD-HHMMSS` from an ISO timestamp.

    The prefix is deliberately not `GT-`: a census id and a transfer run id
    must never be confusable in a log or a filename (invariant 10).
    """
    digits = "".join(ch for ch in taken_at if ch.isdigit())
    return "CENSUS-" + digits[:8] + "-" + digits[8:14]


def transfer_run_block(path: Path) -> dict:
    """-> artifact `transfer_run`, read from a GramTrans run-report snapshot."""
    data = _load_json(path, "run report")
    context = data.get("context") or {}
    run_id = data.get("run_id") or context.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise census.CensusError(
            "the run report at " + str(path) + " carries no context.run_id, "
            "so nothing in it could be cited as evidence (invariant 10 wants "
            "a GT-YYYYMMDD-HHMMSS id)"
        )
    block = {"run_id": run_id, "report_path": str(path)}
    mode = data.get("mode")
    if isinstance(mode, str) and mode:
        block["mode"] = mode
    started = context.get("started_at")
    if isinstance(started, str) and started:
        block["started_at"] = started
    categories = data.get("per_category")
    if isinstance(categories, dict) and categories:
        block["selected_categories"] = list(categories)
    return block


def matched_by_class_from_report(path: Path) -> tuple:
    """`(per_class, complete)` read from a run report's `matched_to_source`.

    T024d-b. `per_class` maps LCM class name -> count of destination objects that
    already existed and were matched to a source object; `complete` is False when
    the run left any match unattributed, in which case NO class's tally may be
    trusted (an unattributed match cannot be proven to belong elsewhere, so every
    tally is potentially understated -- see `RunReport.matched_class_is_complete`).

    A report with no `matched_to_source` key yields `({}, False)`. That is the
    correct reading, not a degenerate one: 038's snapshot surface OMITS the block
    when nothing matched, and an absent tally is NO EVIDENCE the matcher ran --
    never a zero. Every row then stays on `baseline_gross`, which is exactly what
    a pre-T024d report, or a build whose matcher has not landed, deserves.
    """
    data = _load_json(path, "run report")
    block = data.get("matched_to_source")
    if not isinstance(block, dict):
        return {}, False
    raw = block.get("by_object_class")
    per_class = {}
    if isinstance(raw, dict):
        for name, count in raw.items():
            if isinstance(name, str) and isinstance(count, int) and count >= 0:
                per_class[name] = count
    # `complete` is authoritative when the producer states it; fall back to the
    # unattributed split so an older/hand-built block cannot claim completeness
    # by omission.
    complete = block.get("complete")
    if not isinstance(complete, bool):
        complete = not block.get("unattributed_by_category")
    return per_class, bool(complete) and bool(per_class)


#: `^GT-YYYYMMDD-HHMMSS$` -- `reportRef.run_id`'s schema pattern
#: (`census-artifact.schema.json` `$defs.reportRef.run_id`). A run id that does
#: not match is OMITTED rather than written through: `run_id` is optional on a
#: `reportRef`, so omitting it costs a convenience while writing a malformed one
#: costs schema validity of the whole artifact.
_RUN_ID_PATTERN = re.compile(r"^GT-[0-9]{8}-[0-9]{6}$")


def enriched_by_class_from_report(path: Path) -> tuple:
    """`(per_class, measured)` read from a run report's `enrichments[]`.

    `per_class` maps LCM class name -> count of destination objects that already
    existed and GAINED content (`match_basis.enriched`, fidelity-census.md 8);
    `measured` is False when the report carries no `enrichments` key at all.

    THE CLASS KEY IS `enrichments[].object_class`, AND NOTHING ELSE. The report
    also carries `enriched_counts` (`Lib/report.py`'s `_counter_block`), which is
    keyed by `GrammarCategory` -- and a category is NOT 1:1 with an LCM class for
    the affix and MSA categories, so crediting a category total to a class row
    would attribute an enrichment to a class the run may never have touched. That
    is the same mis-attribution `matched_by_class_from_report` refuses to make,
    for the same reason.

    An enrichment record is counted only when it is not `is_empty`. `is_empty`
    means, in `models.EnrichmentRecord`'s own words, "nothing was actually gained
    AND nothing was lost" -- the ONE case data-model.md section 7 permits to
    degrade to a `Skip`. Counting one would let a whole-object skip satisfy the
    phase-3 predicate, which exists precisely to catch a skip masquerading as a
    match (defect G3).

    `measured` False is NOT a per-class zero. A report predating feature 038, or
    one from a build whose enrichment recorder has not landed, omits the key
    entirely; reading that as "0 enriched" would be the absent-read-as-zero error
    `census.unmatched_starter` refuses to make. When the key IS present the list
    is the complete record (`Lib/report.py`: "NONE of these lists is capped"), so
    a class absent from a present list is a PROVEN zero.
    """
    data = _load_json(path, "run report")
    records = data.get("enrichments")
    if not isinstance(records, list):
        return {}, False
    per_class: dict = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        name = record.get("object_class")
        if not isinstance(name, str) or not name:
            continue
        if record.get("is_empty") is True:
            continue
        per_class[name] = per_class.get(name, 0) + 1
    return per_class, True


# ---------------------------------------------------------------------------
# Reading a REPORTED drop as accounting (T024c sub-point 3)
#
# `census.class_row_artifact` has accepted `accounted_for` since T019 and
# nothing ever populated it, so a loss the engine REPORTED still read as
# `unexplained_shortfall` -- the exact mis-attribution SC-005 is about. Measured
# on run GT-20260820-002806: MoStemMsa 164 -> 162, `difference -2`,
# `unexplained_shortfall: 2`, beside two `DroppedItemRecord`s naming those two
# objects by GUID.
#
# ------------------------- THE VOCABULARY GAP ------------------------------
# `fidelity-census.md` 7.1 is a CLOSED 16-token enum and it has NO token for
# "the source referent is legitimately absent, and the engine required it".
# The nearest member is
#
#     DEPENDENCY_UNRESOLVED | shortfall | A required referent is absent in the
#                                         destination (FR-017).
#
# and "absent in the destination" is NOT this case: an MSA whose
# `PartOfSpeechRA` is empty ON THE SOURCE was never resolvable anywhere, and
# nothing about the destination would fix it. `NO_CREATE_PATH` is wrong too --
# there IS a create path for `MoStemMsa` and this very run exercised it 162
# times -- and so is `UNSUPPORTED_SUBTYPE`, which is about a subtype the engine
# cannot reproduce.
#
# Contracts are spec artifacts and are not this module's to edit, and the enum
# forbids inventing a 17th token here. So the token is a NAMED, OVERRIDABLE
# CONSTANT rather than a literal buried in a mapping: the mechanism ships, the
# mis-attribution is visible in one place and stated in every emitted line's
# `detail`, and closing the gap is a one-line change once the contract grows
# the token it needs.
# ---------------------------------------------------------------------------

#: PROVISIONAL. The token stamped on a drop whose referent was absent on the
#: SOURCE. Least-wrong member of the closed enum, and still wrong: see the
#: block comment above. TODO(contract): replace with the token
#: `fidelity-census.md` 7.1 adds for "required source referent absent".
SOURCE_REFERENT_ABSENT_TOKEN: str = "DEPENDENCY_UNRESOLVED"

#: Said in every line that token produces, so the substitution is auditable in
#: the artifact and not only in this source file.
SOURCE_REFERENT_ABSENT_DETAIL: str = (
    "PROVISIONAL TOKEN: the referent was absent ON THE SOURCE, which the "
    "closed FR-013 vocabulary has no member for; DEPENDENCY_UNRESOLVED is the "
    "least-wrong existing token and means 'absent in the destination' "
    "(fidelity-census.md 7.1)"
)

#: `(substring of DroppedItemRecord.reason, FR-013 token)`, most specific first.
#: `reason` is free text by construction (`models.DroppedItemRecord`: "reason :
#: e.g. 'shared-default diverged', ..."), so classification is by distinctive
#: substring -- and a reason matching NOTHING here yields NO LINE AT ALL rather
#: than a fallback token. That asymmetry is the point: an unclassifiable drop
#: leaves the shortfall unexplained, which is the honest answer, whereas a
#: catch-all token would launder it into accounting. There is no `OTHER`.
DROP_REASON_TOKENS: tuple = (
    ("is not reproducible by this engine", "UNSUPPORTED_SUBTYPE"),
    ("not resolvable in target", "DEPENDENCY_UNRESOLVED"),
    ("is empty on source", SOURCE_REFERENT_ABSENT_TOKEN),
)


def drop_reason_token(reason):
    """-> the FR-013 token for one free-text drop reason, or None.

    None means "the census cannot classify this drop", and per FR-013 that is
    an ABSENT accounting line, never a 17th token.
    """
    if not isinstance(reason, str):
        return None
    for needle, token in DROP_REASON_TOKENS:
        if needle in reason:
            return token
    return None


def dropped_by_class_from_report(path: Path, classes=()) -> dict:
    """`{object_class: ((token, census.ReportRef), ...)}` from `dropped_items`.

    THE CLASS OF A DROPPED OBJECT IS `item_name`, NOT `owner_kind`.
    `models.DroppedItemRecord.owner_kind` names the class of the OWNER, so the
    two MSA drops measured on GT-20260820-002806 are recorded as
    `owner_kind="LexEntry", field_name="MorphoSyntaxAnalysesOC",
    item_name="MoStemMsa"` -- crediting them to `LexEntry` would pay down a
    shortfall on a class that lost nothing.

    A drop is admitted as accounting ONLY when `item_name` is one of `classes`,
    the classes this census measures. That filter is doing real work, not
    defensive noise: the same run reported 169 drops of
    `MoForm.MorphTypeRA -> item_name "stem"`. Those are dropped REFERENCES --
    the `MoMorphType` named "stem" is still in the destination, and the object
    count of no class moved -- so crediting them anywhere would explain away a
    loss that did not happen and trip R-2 (`CENSUS_ERROR`). Under-accounting
    leaves an honest `unexplained_shortfall`; over-accounting is a verdict
    failure. Only one of those two errors is recoverable.

    The returned `ReportRef` states `count_in_report` (how many records the
    report ACTUALLY names) and every non-empty `item_guid` as `record_ids`. The
    CLAIMING count is the caller's, because only the caller knows the row's
    difference and R-2 caps a claim at it.
    """
    data = _load_json(path, "run report")
    records = data.get("dropped_items")
    if not isinstance(records, list):
        return {}
    admitted = frozenset(classes)
    context = data.get("context") or {}
    run_id = data.get("run_id") or context.get("run_id") or ""
    if not (isinstance(run_id, str) and _RUN_ID_PATTERN.match(run_id)):
        run_id = ""

    grouped: dict = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        object_class = record.get("item_name")
        if not isinstance(object_class, str) or object_class not in admitted:
            continue
        token = drop_reason_token(record.get("reason"))
        if token is None:
            continue
        guid = record.get("item_guid")
        grouped.setdefault(object_class, {}).setdefault(token, []).append(
            guid if isinstance(guid, str) else "")

    out: dict = {}
    for object_class, by_token in grouped.items():
        out[object_class] = tuple(
            (token, census.ReportRef(
                kind="dropped_item",
                count_in_report=len(guids),
                run_id=run_id,
                report_path=str(path),
                record_ids=tuple(g for g in guids if g),
            ))
            for token, guids in sorted(by_token.items())
        )
    return out


@dataclass(frozen=True)
class ReportEvidence:
    """What one run report proves about a class, beyond its matched tally.

    Grouped into one object rather than added as four more positional
    parameters on `_row_for_entry`, whose existing six are pinned positionally
    by `tests/unit/test_038_matched_by_class.py`.

    `present` is the fact that a report was supplied AT ALL, and it is what
    licenses `match_basis.basis_source == "run_report"`. Without it the row
    carries no `match_basis` block at all -- 5.2's `basis_source: "unavailable"`
    is emitted by the row builder only when it was asked for a basis it cannot
    source, and a row nobody offered a report to is not that case.
    """

    present: bool = False
    enriched_by_class: dict = field(default_factory=dict)
    enriched_measured: bool = False
    dropped_by_class: dict = field(default_factory=dict)

    def enriched_for(self, object_class: str):
        """-> the `enriched` tally for one class, or None when unmeasured.

        A PROVEN zero when the report carried an `enrichments` list and this
        class is absent from it; None when it carried no list at all. The two
        must not collapse: the first says the enrichment pass ran and this class
        gained nothing, the second says nothing is known.
        """
        if not self.enriched_measured:
            return None
        return int(self.enriched_by_class.get(object_class, 0))

    def drops_for(self, object_class: str) -> tuple:
        return tuple(self.dropped_by_class.get(object_class) or ())


def read_report_evidence(path: Optional[Path], classes=()) -> ReportEvidence:
    """`ReportEvidence` for a run report, or the empty one for no report."""
    if path is None:
        return ReportEvidence()
    enriched, measured = enriched_by_class_from_report(path)
    return ReportEvidence(
        present=True,
        enriched_by_class=enriched,
        enriched_measured=measured,
        dropped_by_class=dropped_by_class_from_report(path, classes),
    )


def accounted_for_drops(difference, drops, notes=None) -> tuple:
    """-> `tuple[census.AccountedLine, ...]` for one row's reported drops.

    R-2 IS ENFORCED HERE, BY CAPPING. A row may hold more reported drops than
    its difference has room for -- the destination may have gained objects
    elsewhere in the same class -- and a claim exceeding `max(0, -difference)`
    is `CENSUS_ERROR`, so the claim is capped at the room and the cap is stated
    in `notes`. The `report_ref` still names the FULL count the report carries,
    which is what R-1 compares against, so capping never invents evidence.

    Nothing is emitted for a zero or positive difference: a dropped object
    cannot pay down a SURPLUS, and a MATCHED row that also reports a drop is a
    real finding (something was lost and something else over-created) that an
    accounting line would hide.
    """
    if difference is None or difference >= 0:
        return ()
    room = -difference
    lines = []
    for token, ref in drops:
        if room <= 0:
            break
        count = min(ref.count_in_report, room)
        detail = (
            SOURCE_REFERENT_ABSENT_DETAIL
            if token == SOURCE_REFERENT_ABSENT_TOKEN else
            "reported as a DroppedItemRecord on run "
            + (ref.run_id or "(unstamped)")
        )
        if count < ref.count_in_report:
            capped = (
                "the run report names " + str(ref.count_in_report)
                + " dropped " + token + " item(s) but the row's shortfall is "
                + str(-difference) + ", so the accounting line claims only "
                + str(count) + " (R-2: the census must not explain away more "
                "than actually happened)"
            )
            if notes is not None:
                notes.append(capped)
            detail = detail + " -- CLAIM CAPPED, see notes"
        lines.append(census.AccountedLine(
            reason=token, count=count, direction="shortfall",
            report_ref=ref, detail=detail))
        room -= count
    return tuple(lines)


def _row_for_entry(
    entry, source_counts, destination_counts, baseline,
    matched_by_class=None, matched_complete=False,
    *, evidence: Optional[ReportEvidence] = None,
):
    """One `(ClassCensusRow, emitter kwargs)` pair for one class-list entry.

    THE SUBTRACTION BASIS IS PER ROW, and `baseline_matched` is EARNED, not
    assumed. 5.2 ties the matched count to the run report ("baseline_gross ...
    used when no run report is available"), so a row reaches the stronger basis
    only when all three hold:

    1. there is a baseline count for this row, and
    2. the run report carries a matched tally for THIS object class, and
    3. the report attributed every match it made (`matched_complete`).

    Anything else stays on `baseline_gross`. That is deliberately conservative:
    understating `starter_matched_to_source` overstates `unmatched_starter`, which
    subtracts too much and manufactures a shortfall on a lossless run -- the very
    mis-report 5.2 exists to name. Being wrong in the capped, advisory direction
    is recoverable; silently claiming a trustworthy answer is not.

    On the matched basis `starter_excluded` becomes `unmatched_starter`
    (baseline - matched) rather than the gross baseline, which is the whole point:
    a starter object the transfer matched to a source object is NOT surplus and
    must not be subtracted from the destination.
    """
    matched_by_class = matched_by_class or {}
    evidence = evidence or ReportEvidence()
    measured = entry.in_class_list_via != "excluded_not_measurable"
    notes = []
    if measured:
        source_count = source_counts[entry.object_class]
        destination_count = destination_counts[entry.object_class]
    else:
        source_count = 0
        destination_count = 0
        notes.append(_NOT_MEASURED_NOTE)

    # Looked up by `row_key`, not by class: an A1 split row's key is not in the
    # baseline, so both halves land on `absent_from_baseline` and the class's
    # single baseline count cannot be subtracted twice.
    baseline_count = (
        None if baseline.is_missing else baseline.count_for(entry.row_key)
    )
    if baseline.is_missing:
        basis = "no_baseline"
        source_of_baseline = "assumed_zero_not_permitted"
        starter_excluded = 0
    elif baseline_count is None:
        basis = "baseline_gross"
        source_of_baseline = "absent_from_baseline"
        starter_excluded = 0
        if entry.owning_feature_system is not None:
            notes.append(_A1_BASELINE_NOTE)
    else:
        source_of_baseline = "baseline_document"
        # T024d-b: the one path that can earn `baseline_matched`. `row_key` is
        # deliberately NOT used for the tally lookup -- a run report tallies by
        # LCM class, and an A1 split row's key is not a class -- so a split row
        # never reaches the matched basis. Correct: the report cannot say which
        # feature system a matched FsFeatStrucType belonged to.
        matched = matched_by_class.get(entry.object_class)
        if (
            matched_complete
            and matched is not None
            and entry.owning_feature_system is None
        ):
            basis = "baseline_matched"
            starter_excluded = census.unmatched_starter(baseline_count, matched)
            notes.append(
                "starter_matched_to_source=" + str(matched)
                + " read from the run report; subtracting "
                + str(starter_excluded) + " unmatched starter object(s) rather "
                "than the gross baseline of " + str(baseline_count)
            )
        else:
            basis = "baseline_gross"
            starter_excluded = baseline_count

    reasons = ()
    out_of_scope = False
    if entry.not_evaluated_reason is not None:
        reasons = (entry.not_evaluated_reason,)
        out_of_scope = True

    row = models.ClassCensusRow(
        object_class=entry.object_class,
        source_count=source_count,
        destination_count=destination_count,
        starter_excluded=starter_excluded,
        difference=destination_count - starter_excluded - source_count,
        explained=False,
        engine_can_create=entry.engine_can_create,
        out_of_scope=out_of_scope,
        reasons=reasons,
    )
    kwargs = {
        "starter_subtraction_basis": basis,
        "starter_baseline_source": source_of_baseline,
    }
    if baseline_count is not None:
        kwargs["starter_baseline_count"] = baseline_count
    if basis == "baseline_matched":
        # Emitted ONLY on the matched basis. On the gross basis the count is
        # unknown, and writing a 0 there would be the "absent read as zero"
        # error `census.unmatched_starter` refuses to make.
        kwargs["starter_matched_to_source"] = matched_by_class[entry.object_class]

    # ---- T024c sub-point 3: a REPORTED drop is accounting -----------------
    # An A1 split row is excluded for the same reason it cannot reach the
    # matched basis: a `dropped_items` record names an LCM CLASS, not a feature
    # system, so crediting one to a split half would pay down a shortfall the
    # report cannot attribute -- and crediting it to BOTH halves would double it.
    drops = (
        evidence.drops_for(entry.object_class)
        if entry.owning_feature_system is None else ()
    )
    lines = accounted_for_drops(row.difference, drops, notes)
    if lines:
        kwargs["accounted_for"] = lines

    # ---- match_basis: P3's only input --------------------------------------
    # Emitted whenever a run report was supplied, because `basis_source:
    # "run_report"` is itself the load-bearing fact -- `census._phase_3` reads
    # `match_basis.enriched` off this block and there is nowhere else for it to
    # come from. Every SUMMAND stays null: `identity`/`natural_key` need a
    # PER-CLASS basis split the report does not carry (`matched_to_source`
    # publishes `by_natural_key` as a run-wide scalar), and `created_new` /
    # `unmatched_reported` have no per-class surface at all. Null is not a
    # shortcut here -- `census.MatchBasis.summed` returns None unless all four
    # are known, so invariant 11 is correctly SKIPPED rather than checked
    # against a number nothing supports. `enriched` is deliberately NOT added
    # to any sum: `census.MATCH_BASIS_SUMMANDS` excludes it because it is a
    # SUBSET of identity + natural_key, and including it would double-count
    # every enriched object.
    if evidence.present:
        enriched = (
            evidence.enriched_for(entry.object_class)
            if entry.owning_feature_system is None else None
        )
        kwargs["match_basis"] = census.MatchBasis(
            basis_source="run_report", enriched=enriched)
        if enriched is None and entry.owning_feature_system is None:
            notes.append(
                "match_basis.enriched is null: the run report carries no "
                "`enrichments` list, and an absent list is no evidence the "
                "enrichment pass ran -- never a measured zero"
            )

    kwargs["notes"] = tuple(notes)
    return row, kwargs


def census_run(
    source: str,
    destination: str,
    out: Path,
    *,
    baseline_path: Optional[Path] = None,
    run_report: Optional[Path] = None,
    destination_freshly_created: bool = False,
    projects_root: Optional[str] = None,
    root: Optional[Path] = None,
    open_project=None,
) -> int:
    """Census one source -> destination pair, write the artifact, gate it.

    The artifact is written even when the verdict fails -- 5.3's "no baseline;
    the counts are still written, the run cannot pass". The exit code is the
    gate's, taken from `census.gate_artifact`.
    """
    base = census.repo_root() if root is None else Path(root)
    class_list = census.split_feature_system_entries(
        census.derive_class_list(base))
    wanted = _measurable_classes(class_list)
    opener = open_project or _read_only_handle

    baseline = (
        models.StarterBaseline.missing() if baseline_path is None
        else load_baseline_document(baseline_path)
    )
    if baseline.is_missing:
        _warn("no --baseline: the counts will be written but the run CANNOT "
              "pass (BASELINE_MISSING, exit "
              + str(census.exit_code_for("BASELINE_MISSING")) + ") -- absence "
              "is a verdict, not a warning (fidelity-census.md 5.3)")

    _info("source      " + repr(source))
    _info("destination " + repr(destination))
    _info("classes     " + str(len(class_list.entries)) + " rows over "
          + str(len(wanted)) + " measurable classes")

    # A1: `FsFeatStrucType` is counted through EACH owning feature system, on
    # both sides. The repository total is exactly the ambiguous summed figure
    # A1 forbids, so the per-system counts are taken while each handle is open
    # rather than reconstructed from it afterwards.
    split_classes = tuple(sorted(census.FEATURE_SYSTEM_SPLIT_CLASSES))
    source_split: dict = {}
    destination_split: dict = {}
    duplicates: dict = {}
    admitted = census.roster_admitted_classes(base)

    def _count_split(handle, into: dict) -> None:
        for split_class in split_classes:
            into[split_class] = census.count_by_feature_system(
                handle, split_class)

    def _open_source(name: str):
        handle = opener(name)
        _count_split(handle, source_split)
        return handle

    def _open_destination(name: str):
        handle = opener(name)
        # Both extra passes run while the handle is open, because
        # `read_project` closes it in a `finally` before it returns.
        duplicates.update(census.duplicate_reports_for(
            handle, wanted, admitted=admitted))
        _count_split(handle, destination_split)
        return handle

    source_reading = census.read_project(
        source, wanted, projects_root=projects_root,
        open_project=_open_source)
    if source_reading.counts.unmeasurable:
        _report_unmeasurable(source_reading)

    destination_reading = census.read_project(
        destination, wanted,
        projects_root=projects_root,
        declared_freshly_created=destination_freshly_created or None,
        open_project=_open_destination,
    )
    if destination_reading.counts.unmeasurable:
        _report_unmeasurable(destination_reading)

    source_counts = dict(source_reading.counts.counts)
    destination_counts = dict(destination_reading.counts.counts)

    # T024d-b: per-class matched tallies, when the run report carries them.
    matched_by_class, matched_complete = (
        matched_by_class_from_report(run_report)
        if run_report is not None else ({}, False)
    )
    # T024c sub-point 3 + the P3 seam: the enrichment tally `match_basis`
    # needs and the reported drops `accounted_for` needs, both read from the
    # SAME report and both keyed by LCM class. `wanted` is passed so a drop can
    # only ever be credited to a class this census actually measures.
    evidence = read_report_evidence(run_report, wanted)

    rows = []
    for entry in class_list.entries:
        owner = entry.owning_feature_system
        if owner is None:
            row, kwargs = _row_for_entry(
                entry, source_counts, destination_counts, baseline,
                matched_by_class, matched_complete, evidence=evidence)
            duplicate_report = duplicates.get(entry.object_class)
        else:
            row, kwargs = _row_for_entry(
                entry,
                {entry.object_class:
                    source_split.get(entry.object_class, {}).get(owner, 0)},
                {entry.object_class:
                    destination_split.get(entry.object_class, {}).get(owner, 0)},
                baseline,
                matched_by_class, matched_complete, evidence=evidence,
            )
            # No natural-key definition covers a split class, and a whole-class
            # duplicate report attached to one half would double-count it.
            duplicate_report = None
        rows.append(census.class_row_artifact(
            row, entry, duplicates=duplicate_report, **kwargs))

    if not baseline.is_missing and run_report is not None and not matched_complete:
        # T024d-b: the run report was supplied but cannot lift the cap. Said out
        # loud, because before this task the cap's remediation advice ("supply the
        # run report") was unfollowable and the operator had no way to tell.
        _warn("--run-report carries no usable per-class matched tally"
              + (" (every match it made went unattributed, so no class's tally "
                 "can be trusted)" if matched_by_class else
                 " (no `matched_to_source` block -- the report predates it, or "
                 "the run matched nothing)")
              + ": every row stays on the `baseline_gross` basis and its "
                "shortfalls remain advisory (fidelity-census.md 5.2).")

    if not baseline.is_missing and run_report is None:
        # 5.2 again, said out loud: with no run report the matched count is
        # unknown, so the GROSS baseline is subtracted and a correct run can
        # read as a shortfall (the contract's own worked example: 43 - 23 = 20
        # reports -21 on a run that lost nothing). The verdict is still the
        # gate's, and this line is a warning about the BASIS, not a downgrade
        # of the verdict -- nothing here may soften what the gate concluded.
        _warn("no --run-report: every row is on the `baseline_gross` "
              "subtraction basis, which over-subtracts by exactly the number "
              "of starter objects the transfer matched. Shortfalls reported "
              "on this basis are advisory (fidelity-census.md 5.2); supply "
              "the run report for the `baseline_matched` basis.")

    taken_at = destination_reading.counted_at
    identity = _CensusIdentity(
        run_id=_census_id(taken_at), taken_at=taken_at, baseline=baseline)
    artifact = census.build_artifact(
        identity, class_list, rows,
        projects=census.projects_artifact(source_reading, destination_reading),
        instrument=instrument_block(
            root=base, flex_version=running_flex_version()),
        transfer_run=(transfer_run_block(run_report)
                      if run_report is not None else None),
    )
    census.stamp_verdict(artifact)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")

    _print_class_table(artifact)
    outcome = census.gate_artifact(artifact)
    code = _print_gate(artifact, outcome, census.validate_artifact(artifact))
    _info("wrote " + str(out))
    return code


# ---------------------------------------------------------------------------
# Console rendering
#
# The FULL per-class table is `Lib/report.py`'s, attached to the run report by
# T022. What follows is deliberately the smaller thing a command line needs,
# and where it shortens a list it says how many rows it left out -- invariant 2
# permits truncation in a console summary only on that condition.
# ---------------------------------------------------------------------------

_CONSOLE_MAX_ROWS = 40


def _signed(value) -> str:
    """A difference with its sign always visible: the sign is load-bearing."""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return "?"
    return "0" if number == 0 else format(number, "+d")


def _row_label(row: dict) -> str:
    """One row's console label, with Amendment A1's owner shown exactly once.

    Under the settled `row_property` encoding the owner is a separate property
    and is appended here; under the retained `class_string` fallback it is
    already inside `class` and there is no property to append. So this renders
    the owner once under either encoding without knowing which is in force.
    """
    owner = str(row.get("owning_feature_system") or "")
    label = str(row.get("class", "?"))
    return label + ("(" + owner + ")" if owner else "")


def _row_line(row: dict) -> str:
    dup = row.get("duplicates") or {}
    return (
        "  " + _row_label(row).ljust(34)
        + str(row.get("source_count")).rjust(7) + " ->"
        + str(row.get("destination_count_total")).rjust(7)
        + "  net " + str(row.get("destination_count_net")).rjust(7)
        + "  diff " + _signed(row.get("difference")).rjust(7)
        + "  " + str(row.get("verdict_class", "?")).ljust(14)
        + "  unexp -" + str(row.get("unexplained_shortfall", 0))
        + "/+" + str(row.get("unexplained_surplus", 0))
        + ("  dup " + str(dup.get("extra_objects", 0))
           if dup.get("extra_objects") else "")
    )


def _print_class_table(artifact: dict) -> None:
    """Every row, in emission order. Not truncated."""
    rows = artifact.get("classes") or []
    _say("")
    _say("  " + "class".ljust(34) + "source".rjust(7) + "   "
         + "dest".rjust(7) + "      net" + "     diff" + "  verdict")
    for row in rows:
        _say(_row_line(row))
    _say("")


def _artifact_notes(artifact: dict) -> tuple:
    """T023c -- every note the artifact carries, for DISPLAY only.

    Its own `notes` array first, in stored order, then any of 5.2's gross-basis
    cap notes not already present. The second source matters on the `gate` path:
    `gate` reads a file somebody else wrote and `census.gate_artifact`
    RECOMPUTES the verdict, so an artifact that was never `stamp_verdict`-ed can
    still be gated to a capped `CENSUS_ACCOUNTED` while holding no note
    explaining it. `census.gross_basis_cap_notes` supplies exactly the sentences
    stamping would have written, so the console is never more silent than the
    verdict it prints.

    The accessor is CALLED, not reimplemented: "is this row capped" has one
    derivation (`census.is_gross_basis_row`), and a second read-only copy here
    would be free to drift from it.

    NOT LOAD-BEARING (invariant 9). No exit code, no verdict and no invariant
    check reads any of this back; a hand-written note cannot buy a cap, and
    deleting every note changes nothing but what the operator is told.
    """
    notes = [str(note) for note in (artifact.get("notes") or ())
             if str(note).strip()]
    for note in census.gross_basis_cap_notes(artifact):
        if note not in notes:
            notes.append(note)
    return tuple(notes)


def _print_notes(artifact: dict, outcome) -> None:
    """Print the artifact's notes above the verdict headline.

    ABOVE the headline on purpose: 5.2's cap can turn a 21-object shortfall
    into `CENSUS_ACCOUNTED` / exit 0, and on a release gate the sentence that
    says so has to be the thing the operator reads immediately before the
    exit code, not something scrolled off the top.

    Truncation obeys invariant 2 -- a console summary may shorten a list only
    while stating how many it left out. The artifact is never truncated.
    """
    notes = _artifact_notes(artifact)
    if not notes:
        return
    _warn(str(len(notes)) + " census note(s) -- the census's own reportage; "
          "the verdict below is computed from counts, bases and accounting "
          "lines, NEVER from a note:")
    for note in notes[:_CONSOLE_MAX_ROWS]:
        _say("  " + note)
    if len(notes) > _CONSOLE_MAX_ROWS:
        _info(str(len(notes) - _CONSOLE_MAX_ROWS) + " further note(s) omitted "
              "from this console summary; the artifact carries all of them")
    # A cap note is written whenever the gross basis suppressed a tally, which
    # can happen on a run a MORE severe verdict then decides. Say so, or the
    # note reads as "capped at CENSUS_ACCOUNTED" beside a [FAIL] exit 4.
    ceiling = census.GROSS_BASIS_VERDICT_CAP
    if census.most_severe_verdict((outcome.verdict, ceiling)) != ceiling:
        _info("the cap those notes describe did NOT decide this run: "
              + outcome.verdict + " is more severe than the " + ceiling
              + " ceiling, so it stands")


def _print_gate(artifact: dict, outcome, invariant_failures) -> int:
    """Print the gate's answer and return the process exit code."""
    totals = artifact.get("totals") or {}
    baseline = artifact.get("starter_baseline") or {}
    projects = artifact.get("projects") or {}
    code = 0 if outcome.passed else outcome.exit_code
    if not outcome.passed and code == 0:
        # The verdict passes but something else refused. An invariant failure
        # is a CENSUS_ERROR; an unsatisfied phase predicate is neither an
        # error nor a pass, and 9.1 forbids it exiting 0.
        code = (census.exit_code_for("CENSUS_ERROR") if invariant_failures
                else PHASE_UNSATISFIED_EXIT_CODE)

    # T024b: a pass that only holds because the gross-basis cap suppressed a
    # measured shortfall must not exit 0. Keyed off the SUPPRESSIONS, not off the
    # basis: a gross-basis run that suppressed nothing hid nothing, and flipping
    # it to non-zero would cry wolf on every honest run. Same accessor the cap
    # and its notes use, so the three cannot disagree about which rows are capped.
    capped = census.gross_basis_suppressions(artifact) if code == 0 else ()
    if capped:
        code = CAPPED_PASS_EXIT_CODE

    _info("census " + str(artifact.get("census_id", "?"))
          + " generated " + str(artifact.get("generated_at", "?")))
    _info("projects " + repr((projects.get("source") or {}).get("name", "?"))
          + " -> " + repr((projects.get("destination") or {}).get("name", "?")))
    _info("baseline kind " + str(baseline.get("kind", "?"))
          + "  class_count " + str(baseline.get("class_count", "-"))
          + "  carries_natural_keys "
          + str(baseline.get("carries_natural_keys", "-")))
    _info("classes " + str(totals.get("classes_reported", "?"))
          + "  matched " + str(totals.get("classes_matched", "?"))
          + "  shortfall " + str(totals.get("classes_shortfall", "?"))
          + "  surplus " + str(totals.get("classes_surplus", "?"))
          + "  not evaluated " + str(totals.get("classes_not_evaluated", "?")))
    _info("shortfall " + str(totals.get("total_shortfall", "?"))
          + " (unexplained " + str(totals.get("unexplained_shortfall", "?"))
          + ")  surplus " + str(totals.get("total_surplus", "?"))
          + " (unexplained " + str(totals.get("unexplained_surplus", "?"))
          + ")  duplicate extras "
          + str(totals.get("duplicate_extra_objects", "?")))

    failing = [row for row in (artifact.get("classes") or [])
               if not census.row_passes(row)]
    if failing:
        _fail(str(len(failing)) + " class(es) do not pass section 6:")
        for row in failing[:_CONSOLE_MAX_ROWS]:
            _fail(_row_line(row))
        if len(failing) > _CONSOLE_MAX_ROWS:
            _info(str(len(failing) - _CONSOLE_MAX_ROWS) + " further failing "
                  "row(s) omitted from this console summary; the artifact "
                  "carries all of them")

    phase = outcome.phase
    if phase is not None:
        if phase.satisfied:
            _ok("phase " + str(phase.phase) + " predicate satisfied")
        else:
            _fail("phase " + str(phase.phase) + " predicate NOT satisfied:")
            for line in phase.failures:
                _fail("  - " + line)

    other = [line for line in outcome.failures
             if phase is None or line not in tuple(phase.failures)]
    if other:
        _fail(str(len(other)) + " gate failure(s):")
        for line in other[:_CONSOLE_MAX_ROWS]:
            _fail("  - " + line)
        if len(other) > _CONSOLE_MAX_ROWS:
            _info(str(len(other) - _CONSOLE_MAX_ROWS) + " further failure(s) "
                  "omitted from this console summary")

    # T023c: the notes, immediately above the headline. Without them a capped
    # `CENSUS_ACCOUNTED` / exit 0 was indistinguishable on this surface from a
    # run that lost nothing -- which is the exact silence 5.2's warning text
    # exists to break.
    _print_notes(artifact, outcome)

    headline = (
        "verdict " + outcome.verdict + " (" + outcome.human_label
        + ")  exit " + str(code)
    )
    if capped:
        # T024b: never [OK]. The gate's own conclusion is unchanged and is still
        # printed verbatim -- what changes is that the operator and the exit code
        # both learn the pass is CAPPED. `_warn`, not `_fail`: this is not a
        # refusal, it is a refusal to call it success.
        total = sum(count for _, _, count in capped)
        _warn(str(len(capped)) + " capped row(s) totalling " + str(total)
              + " unexplained object(s) were turned into accounting by the "
                "gross-basis cap -- this is NOT a clean result. Supply a run "
                "report carrying per-class matched tallies for a trustworthy "
                "answer (fidelity-census.md 5.2).")
        _warn(headline + "  [CAPPED -- advisory, not a pass]")
    elif outcome.passed:
        _ok(headline)
    else:
        _fail(headline)
    return code


# ---------------------------------------------------------------------------
# gate
# ---------------------------------------------------------------------------

def gate(artifact_path: Path, phase: Optional[int] = None) -> int:
    """Gate one artifact. The verdict is RECOMPUTED, never read.

    So an artifact that writes `CENSUS_CLEAN` / `exit_code: 0` into itself over
    `starter_baseline.kind == "none"` is still refused with exit 4. That is
    5.3's "there is no path on which a missing baseline yields exit 0", and it
    is a property of `census.gate_artifact`, not of this wrapper.
    """
    artifact = load_artifact(artifact_path)
    _info("artifact " + str(artifact_path))
    outcome = census.gate_artifact(artifact, phase)
    return _print_gate(artifact, outcome, census.validate_artifact(artifact))


# ---------------------------------------------------------------------------
# diff  (SC-008, idempotency)
# ---------------------------------------------------------------------------

def diff(before_path: Path, after_path: Path) -> int:
    """Compare two censuses of the same destination. Non-zero on a regression.

    `quickstart.md` section 5: "Every class's `destination_count_total` must be
    unchanged. Any increase is a duplicate-creation defect REGARDLESS of what
    either census's own verdict says." So this reads the counts, not the
    verdicts, and maps what it finds onto section 9's tokens through
    `most_severe_verdict` / `exit_code_for` -- there is no third exit table
    here.
    """
    before = load_artifact(before_path)
    after = load_artifact(after_path)

    def _by_class(artifact):
        # Keyed on the LABEL, not on `class`: Amendment A1 emits both halves of
        # a split class under the same plain class name with the owner in a
        # separate property, so keying on `class` alone would silently drop one
        # half of the comparison -- exactly the masking A1 exists to prevent.
        return {_row_label(row): row
                for row in (artifact.get("classes") or [])}

    rows_before = _by_class(before)
    rows_after = _by_class(after)

    _info("before " + str(before_path) + "  ("
          + str(before.get("census_id", "?")) + ")")
    _info("after  " + str(after_path) + "  ("
          + str(after.get("census_id", "?")) + ")")

    only_before = sorted(set(rows_before) - set(rows_after))
    only_after = sorted(set(rows_after) - set(rows_before))
    increases = []
    decreases = []
    incomparable = []
    for label in sorted(set(rows_before) & set(rows_after)):
        old = rows_before[label].get("destination_count_total")
        new = rows_after[label].get("destination_count_total")
        if not isinstance(old, int) or not isinstance(new, int):
            incomparable.append(label)
        elif new > old:
            increases.append((label, old, new))
        elif new < old:
            decreases.append((label, old, new))

    verdicts = []
    if only_before or only_after:
        verdicts.append("COVERAGE_INCOMPLETE")
        _fail("the two censuses do not report the same classes -- only in "
              "before: " + (", ".join(only_before) or "(none)")
              + "; only in after: " + (", ".join(only_after) or "(none)"))
    if increases:
        verdicts.append("DUPLICATE_IDENTITY")
        _fail(str(len(increases)) + " class(es) GAINED objects between the two "
              "censuses -- a second transfer into the same destination must "
              "add nothing (SC-008):")
        for label, old, new in increases[:_CONSOLE_MAX_ROWS]:
            _fail("  " + label.ljust(34) + str(old).rjust(7) + " ->"
                  + str(new).rjust(7) + "  " + _signed(new - old))
        if len(increases) > _CONSOLE_MAX_ROWS:
            _info(str(len(increases) - _CONSOLE_MAX_ROWS) + " further "
                  "increase(s) omitted from this console summary")
    if decreases:
        verdicts.append("UNEXPLAINED_SHORTFALL")
        _fail(str(len(decreases)) + " class(es) LOST objects between the two "
              "censuses:")
        for label, old, new in decreases[:_CONSOLE_MAX_ROWS]:
            _fail("  " + label.ljust(34) + str(old).rjust(7) + " ->"
                  + str(new).rjust(7) + "  " + _signed(new - old))
        if len(decreases) > _CONSOLE_MAX_ROWS:
            _info(str(len(decreases) - _CONSOLE_MAX_ROWS) + " further "
                  "decrease(s) omitted from this console summary")
    if incomparable:
        _info(str(len(incomparable)) + " class(es) not compared (a null "
              "destination_count_total on one side): "
              + ", ".join(incomparable[:_CONSOLE_MAX_ROWS]))

    if not verdicts:
        _ok("every class's destination_count_total is unchanged across "
            + str(len(rows_after)) + " rows -- idempotent (SC-008)")
        return 0
    verdict = census.most_severe_verdict(verdicts)
    code = census.exit_code_for(verdict)
    _fail("diff verdict " + verdict + " (" + census.VERDICT_HUMAN_LABELS[verdict]
          + ")  exit " + str(code))
    return code


# ---------------------------------------------------------------------------
# The parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """The whole flag surface, and deliberately no more of it.

    Two things are load-bearing about what is ABSENT: there is no `--target`
    (the vocabulary is `--destination` everywhere), and there is no flag of any
    kind that can turn a missing or stale baseline into a pass.
    """
    parser = argparse.ArgumentParser(
        prog=PROG,
        description=(
            "The per-object-class fidelity census (feature 038). Reads live "
            "FLEx projects READ-ONLY, writes a census artifact, and gates it "
            "against contracts/fidelity-census.md."
        ),
        epilog=(
            "Exit codes are fidelity-census.md section 9's: 0 CENSUS_CLEAN / "
            "CENSUS_ACCOUNTED, 1 UNEXPLAINED_SHORTFALL, 2 UNEXPLAINED_SURPLUS, "
            "3 DUPLICATE_IDENTITY, 4 BASELINE_MISSING, 5 BASELINE_STALE, "
            "6 COVERAGE_INCOMPLETE, 7 CENSUS_ERROR. Only 0 is success, and "
            "there is no flag that produces it over a missing baseline."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", metavar="SUBCOMMAND")

    capture = subparsers.add_parser(
        "capture-baseline",
        help="capture a starter baseline from a brand-new, empty FLEx project",
        description=(
            "Capture one project's per-class inventory, with natural keys "
            "where the 035 roster gives the class one, as a baseline document. "
            "Run it against a genuinely blank project: an edited starter "
            "inventory is no longer a baseline. Re-capture when FieldWorks is "
            "upgraded -- the document records flex_version and "
            "data_model_version, and a census against a newer destination "
            "exits BASELINE_STALE rather than mis-subtracting."
        ),
    )
    capture.add_argument("--project", required=True, metavar="NAME",
                         help="the FLEx project to capture")
    capture.add_argument("--out", required=True, type=Path, metavar="PATH",
                         help="where to write the baseline document")
    capture.add_argument("--projects-root", metavar="PATH", default=None,
                         help="override where FLEx projects live on disk")

    run = subparsers.add_parser(
        "run",
        help="census a source -> destination pair and gate the result",
        description=(
            "Open both projects READ-ONLY, count every class in the census "
            "class list once, group the destination's key-bearing classes by "
            "natural key, write the artifact, and exit with the gate's code. "
            "The artifact is written even when the verdict fails: with no "
            "baseline the counts are still recorded, the run simply cannot "
            "pass."
        ),
    )
    run.add_argument("--source", metavar="NAME", default=None,
                     help="the source project (required unless --pre-transfer)")
    run.add_argument("--destination", required=True, metavar="NAME",
                     help="the destination project -- never spelled --target")
    run.add_argument("--out", required=True, type=Path, metavar="PATH",
                     help="where to write the census artifact")
    run.add_argument("--baseline", type=Path, metavar="PATH", default=None,
                     help=("the baseline document to subtract; omitting it is "
                           "BASELINE_MISSING (exit 4), never an assumed zero"))
    run.add_argument("--run-report", type=Path, metavar="PATH", default=None,
                     help="the GramTrans run report this census judges")
    run.add_argument(
        "--pre-transfer", action="store_true",
        help=("census the DESTINATION only, before the transfer, and write it "
              "as a pre_transfer_census baseline for the post-transfer run to "
              "consume"))
    run.add_argument(
        "--destination-freshly-created", action="store_true",
        help=("declare the destination a brand-new project; required by a "
              "starter_capture baseline and CENSUS_ERROR without it"))
    run.add_argument("--projects-root", metavar="PATH", default=None,
                     help="override where FLEx projects live on disk")

    gate_parser = subparsers.add_parser(
        "gate",
        help="gate an existing census artifact, optionally against a phase",
        description=(
            "Recompute the verdict from the artifact's own evidence and exit "
            "with section 9's code. The stored verdict and exit_code are never "
            "trusted, so a document claiming CENSUS_CLEAN over an absent "
            "baseline is still refused."
        ),
    )
    gate_parser.add_argument("--artifact", required=True, type=Path,
                             metavar="PATH",
                             help="the census artifact to gate")
    gate_parser.add_argument(
        "--phase", type=int, choices=sorted(census.PHASE_PREDICATES),
        default=None, metavar="N",
        help=("also require the phase N acceptance predicate of "
              "fidelity-census.md 9.1"))

    diff_parser = subparsers.add_parser(
        "diff",
        help="compare two censuses of the same destination (SC-008)",
        description=(
            "Idempotency check: every class's destination_count_total must be "
            "unchanged between the two artifacts. An increase is a "
            "duplicate-creation defect regardless of either census's own "
            "verdict."
        ),
    )
    diff_parser.add_argument("--before", required=True, type=Path,
                             metavar="PATH",
                             help="the earlier census artifact")
    diff_parser.add_argument("--after", required=True, type=Path,
                             metavar="PATH",
                             help="the later census artifact")
    return parser


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def _dispatch(args, parser: argparse.ArgumentParser) -> int:
    if args.command == "capture-baseline":
        return capture_baseline(
            args.project, args.out, projects_root=args.projects_root)
    if args.command == "run":
        if args.pre_transfer:
            if args.baseline is not None:
                _warn("--pre-transfer captures the destination's own starting "
                      "point, so --baseline is not used on this path")
            return capture_baseline(
                args.destination, args.out,
                kind=models.StarterBaselineKind.PRE_TRANSFER_CENSUS.value,
                projects_root=args.projects_root)
        if not args.source:
            parser.error("run requires --source unless --pre-transfer is given")
        return census_run(
            args.source, args.destination, args.out,
            baseline_path=args.baseline,
            run_report=args.run_report,
            destination_freshly_created=args.destination_freshly_created,
            projects_root=args.projects_root)
    if args.command == "gate":
        return gate(args.artifact, args.phase)
    if args.command == "diff":
        return diff(args.before, args.after)
    parser.print_help(sys.stderr)
    _fail("no subcommand: expected one of " + ", ".join(SUBCOMMANDS))
    return USAGE_EXIT_CODE


def main(argv=None) -> int:
    """Run one subcommand and return its exit code.

    Returns rather than raises, so a caller (and the gate test) can read the
    code without catching `SystemExit`. Every failure below is a message plus a
    non-zero code: a bad path, a malformed artifact or an unknown verdict must
    never surface as a traceback, and must never surface as 0.
    """
    parser = build_parser()
    args = parser.parse_args(list(sys.argv[1:] if argv is None else argv))
    try:
        return _dispatch(args, parser)
    except census.CoverageIncomplete as exc:
        _fail(str(exc))
        return census.exit_code_for("COVERAGE_INCOMPLETE")
    except census.CensusFailure as exc:
        _fail(str(exc))
        return census.exit_code_for("CENSUS_ERROR")
    except Exception as exc:  # noqa: BLE001 -- a traceback is not a verdict
        _fail(type(exc).__name__ + ": " + str(exc))
        _fail("the census could not complete, so it reports CENSUS_ERROR "
              "(exit " + str(census.exit_code_for("CENSUS_ERROR"))
              + ") rather than a pass")
        return census.exit_code_for("CENSUS_ERROR")


if __name__ == "__main__":
    raise SystemExit(main())
