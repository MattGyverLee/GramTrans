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

#: Rows whose `class` is reported without being measured carry NULL counts.
#: `$defs.classRow` says a count is `null` "only on a NOT_EVALUATED row where
#: the class could not be counted at all", and T099 widened
#: `models.ClassCensusRow` to that same type, so the row now says so.
#:
#: WHAT THIS NOTE USED TO SAY, and it is worth keeping the record. Until T099
#: these rows were emitted as 0/0 with a note calling the zeroes
#: "placeholders". A reader holding only the artifact therefore could not tell
#: `MoForm 0 -> 0` ("this project holds no MoForms") from `MoForm 0 -> 0`
#: ("nobody counted MoForms, and could not have"). The note was honest about
#: the zeroes being false; the DATA was not, and a phase gate reads the data.
_NOT_MEASURED_NOTE = (
    "not measured: in_class_list_via 'excluded_not_measurable' (an abstract "
    "LCM base with no factory). The counts are null, not 0: null says the "
    "class could not be counted at all, where 0 would claim the project holds "
    "none of them."
)

#: T099. The other half of the same defect, from the opposite direction. A
#: class this census ASKED for and could not count used to abort the whole run
#: (`_report_unmeasurable`), because "models.ClassCensusRow cannot carry a null
#: count, so there is no honest row to write". There is now, so the run writes
#: it -- and stays exactly as loud as it was: every unresolved accessor is
#: still printed as a [FAIL] line, still becomes an `errors[]` entry, and a
#: non-empty `errors[]` array is CENSUS_ERROR / exit 7 in
#: `census.recompute_verdict`. The change is that the failure now names itself
#: IN the artifact instead of leaving no artifact at all.
_UNRESOLVED_ACCESSOR_NOTE = (
    "not measured: this class's repository accessor could not be resolved in "
    "{project}, so its count is null rather than 0. The reason is in the "
    "artifact's `errors[]` array, which is CENSUS_ERROR on its own -- this row "
    "reports the gap, it does not excuse it."
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


def _refuse_uncorroborated_nulls(rows, errors) -> None:
    """T099: a null count on a GATE-REQUIRED row must be corroborated.

    THE HOLE THIS CLOSES, and it is the one a fix like T099 opens. A row whose
    `difference` is null reads `verdict_class: NOT_EVALUATED`, and
    `census.row_passes` returns True for NOT_EVALUATED -- so if a producer could
    null a required class's counts on its own initiative, nulling would be a way
    to make that class's shortfall disappear. Before T099 the model made that
    unreachable by refusing to hold a null at all; the model no longer does, so
    the prohibition has to be stated somewhere, and it is stated here rather
    than as a comment.

    TWO CORROBORATIONS ARE ACCEPTED, and they are the only two this CLI can
    produce. `gate_scope: advisory` -- every `excluded_not_measurable` entry is
    hardcoded advisory in `census.derive_class_list`, so an abstract LCM base
    cannot fail or excuse a gate either way. Or an `errors[]` entry naming the
    class, which is what an unresolved accessor produces and which is
    CENSUS_ERROR on its own.

    ALSO A VALIDATOR INVARIANT SINCE T101, and this guard is still not
    redundant. `census.uncorroborated_null_rows` (invariant 12) refuses the same
    shape in any artifact, from any producer, and drives it to CENSUS_ERROR;
    this raises BEFORE an artifact is written, so the operator gets the class
    name at the console instead of a document to validate. The two also differ
    deliberately in one direction: the invariant additionally accepts a
    `not_evaluated_reason` as corroboration, which this CLI cannot mint for a
    required row -- a tighter producer inside a looser format.
    """
    named = {
        entry.get("class") for entry in errors if isinstance(entry, dict)
    }
    offenders = []
    for row in rows:
        if row.get("gate_scope") != "required":
            continue
        nulled = tuple(
            key for key in ("source_count", "destination_count_total",
                            "difference")
            if row.get(key) is None
        )
        if nulled and row.get("class") not in named:
            offenders.append(str(row.get("class")) + " (" + ", ".join(nulled)
                             + ")")
    if offenders:
        raise census.CensusError(
            "these gate-required row(s) carry a null count with no `errors[]`"
            " entry naming the class: " + "; ".join(sorted(offenders))
            + " -- a null difference reads NOT_EVALUATED and NOT_EVALUATED "
            "passes `row_passes`, so an uncorroborated null is a way to retire "
            "a class's shortfall without measuring it"
        )


def _print_unmeasurable(reading) -> tuple:
    """Print every unresolved accessor, one line per class; return the entries.

    An unresolved accessor is a REPORTED OUTCOME, never a skip
    (`Lib/census.py` T017 header). Every one of them is printed as a [FAIL]
    line here and returned as an `errors[]` entry -- and `errors[]` non-empty
    is CENSUS_ERROR / exit 7 in `census.recompute_verdict`, so nothing about
    this is quiet.

    T099. This used to RAISE, on the stated grounds that
    "`models.ClassCensusRow` cannot carry a null count, so there is no honest
    row to write". The premise was true and is not any more, and the raise cost
    something real: the run produced NO artifact, so the one document that
    could have named which class went uncounted, in which project, and for what
    reason did not exist. The abort was loud in the console and silent in the
    record. What replaces it is louder in both -- same [FAIL] lines, same
    non-zero exit, plus a null-counted NOT_EVALUATED row and an `errors[]`
    entry that a reader can find six months later.

    NOT a downgrade to a warning. If a caller ignores the returned entries the
    verdict does not soften: `recompute_verdict` reads `errors[]` off the
    artifact, and `stamp_verdict` is the only thing that writes a verdict.
    """
    entries = tuple(census.unmeasurable_errors(reading))
    for entry in entries:
        _fail(json.dumps(entry, ensure_ascii=False))
    _fail(
        str(len(reading.counts.unmeasurable)) + " class(es) could not be "
        "counted in " + repr(reading.name) + ": "
        + ", ".join(reading.counts.unmeasurable)
        + " -- the census may fail to measure a class; it may not fail QUIETLY"
    )
    return entries


def _report_unmeasurable(reading) -> None:
    """Print every unresolved accessor and RAISE -- the no-rows callers.

    `capture_baseline` keeps the abort deliberately, and the reason is not
    inertia. A baseline document is a count MAP that a later run subtracts, and
    `census.unmatched_starter` refuses to read an absent count as zero; a null
    baseline count would be subtracted as 0 by exactly the arithmetic 5.2
    forbids. There is also no row to write here -- `capture-baseline` emits no
    `classes` array at all -- so T099's "the abort becomes a row" has nothing
    to become.
    """
    _print_unmeasurable(reading)
    raise census.CensusError(
        str(len(reading.counts.unmeasurable)) + " class(es) could not be "
        "counted in " + repr(reading.name) + ": "
        + ", ".join(reading.counts.unmeasurable)
        + " -- a baseline document is a count map a later run SUBTRACTS, and a "
        "null count there would be subtracted as 0"
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


# ---------------------------------------------------------------------------
# T048b: AN IDENTITY SKIP IS A STARTER MATCH
#
# Raised by the 2026-08-20 gate run (journal/T038-T048-live-gate-rerun.md),
# which proved against the raw `.fwdata` that `PartOfSpeech` transferred
# perfectly -- 20 source GUIDs, 20 destination GUIDs, none missing, no
# destination-only leftovers -- while the census still reported `difference:
# -2` and the gate exited 1.
#
# The arithmetic that produced the -2: the destination starter held 5 parts of
# speech and the run matched all five, but by TWO different mechanisms. Three
# were matched and then ENRICHED, so they reached
# `matched_to_source.by_object_class` through the plan item that carried the
# enrichment record. The other two were matched by GUID and then SKIPPED,
# landing in `skips[]` as `ALREADY_PRESENT_BY_GUID` -- and
# `report.build_from_plan` never calls `_count_matched` on the skips loop, so
# those two entered no tally at all. `starter_matched_to_source` read 3,
# `unmatched_starter` read 5 - 3 = 2, and two starter objects the run had
# positively identified were subtracted from the destination as though they
# were surplus.
#
# An `ALREADY_PRESENT_BY_GUID` skip is a match, and it is the STRONGEST kind --
# identity. Nothing was written because nothing needed to be; that is a
# statement about the disposition, not about whether the object was found.
# Counting it is the whole of this fix.
#
# THE SKIP'S `source_guid` IS ALSO ITS TARGET GUID. That is what matching by
# GUID means, and it is why deduping against the enrichment records is possible
# from the artifact alone: `Skip` carries no `target_guid` field (see
# `models.Skip` -- category, source_guid, reason, detail, and nothing else),
# but for this one reason the source GUID names the destination object too.
#
# ------------------------- WHY NOT FIX THE REPORT --------------------------
# Considered and rejected for this task. `report.build_from_plan` could count
# the skips itself, but `Skip` has no `object_class`, so the producer would
# have to grow one on ~12 emit sites in `Lib/categories.py` -- a claimed file,
# and a change that alters what the ENGINE records rather than what the
# instrument reads. The defect measured here is an accounting defect in the
# census (the journal's words: "The `-2` is arithmetic inside the census"), so
# it is fixed where the arithmetic lives. `Lib/categories.py` already carries
# the better long-term answer for the overwrite-enabled mode --
# `_plan_present_by_guid_outcome` emits a `PlannedOverwrite` with a real
# `MatchBasisRecord` when the class is known -- and that path is untouched
# here; this reads the skips that path still, correctly, leaves as skips.
# ---------------------------------------------------------------------------

#: The one `SkipReason` name that denotes a match. A skip for any other reason
#: is a genuine non-event and must never be counted.
IDENTITY_SKIP_REASON = "ALREADY_PRESENT_BY_GUID"

#: For a category the one-to-one table in `Lib/preview.py` deliberately OMITS,
#: the CLOSED set of LCM classes an identity skip in that category can name.
#:
#: This is NOT a second attribution table -- attribution goes through
#: `preview._LCM_CLASS_FOR_CATEGORY` and nothing else, so there is one
#: authority for "which class does this category name". This table answers a
#: different and weaker question: when that authority declines to answer, WHICH
#: ROWS ARE PUT AT RISK by the match we could not attribute. Bounding the
#: damage is the point. An unattributed match understates some class's tally,
#: and understating the tally over-subtracts and manufactures a shortfall --
#: but a match in category `VARIANT_TYPES` cannot possibly have been a
#: `PartOfSpeech`, so poisoning `PartOfSpeech` for it would withhold the
#: stronger basis from a row that was never in doubt.
#:
#: An entry is admitted here on ONE of exactly two grounds, and the comment
#: above it must say which:
#:
#: * the reason `preview._LCM_CLASS_FOR_CATEGORY` states for its own omission
#:   (quoted verbatim), or
#: * a set DERIVED FROM THE CATEGORY'S OWN WALK -- every `SkipReason
#:   .ALREADY_PRESENT_BY_GUID` emission site the category has, cited by
#:   file:line, and the classes the predicate at each of those sites can
#:   possibly have found. Nothing here is inferred from a category's NAME.
#:
#: A category in NEITHER table is treated as UNBOUNDED -- see
#: `IdentitySkipTally.unbounded`. Note that membership is decided by KEY
#: PRESENCE, never by truthiness: an empty candidate set is a real and
#: different answer from an absent one (see `_LINK_ONLY_IDENTITY_SKIP`), and
#: a reader who collapses the two turns a bounded category back into an
#: unbounded one.
#: The candidate set for a category whose identity skip found a LINK rather
#: than an object -- a reference already present in a reference collection,
#: where nothing was created and nothing could have been. An object census
#: has no row for a link, so such a skip understates no class's tally and
#: puts no class at risk. EMPTY IS THE ANSWER, not the absence of one:
#: leaving the category out of the table instead would declare the damage
#: unlocatable and withhold the strong basis from every row in the census.
_LINK_ONLY_IDENTITY_SKIP = frozenset()

_AMBIGUOUS_IDENTITY_SKIP_CLASSES = {
    # "ALLOMORPH covers both MoStemAllomorph and MoAffixAllomorph"
    "ALLOMORPH": frozenset({"MoStemAllomorph", "MoAffixAllomorph"}),
    # "MSA covers the four Mo*Msa subclasses"
    "MSA": frozenset({
        "MoStemMsa", "MoInflAffMsa", "MoDerivAffMsa", "MoUnclassifiedAffixMsa",
    }),
    # "NATURAL_CLASSES covers PhNCSegments and PhNCFeatures, which 038's own
    #  roster keeps strictly apart"
    "NATURAL_CLASSES": frozenset({"PhNCSegments", "PhNCFeatures"}),
    # "VARIANT_TYPES covers LexEntryType and LexEntryInflType, the same
    #  problem again"
    "VARIANT_TYPES": frozenset({"LexEntryType", "LexEntryInflType"}),
    # COMPLEX_FORM_TYPES is absent from the one-to-one table for the same
    # reason VARIANT_TYPES is: both name members of a LexDb possibility list
    # whose objects are ILexEntryType, and LexEntryInflType is a subclass the
    # census counts as its own row.
    "COMPLEX_FORM_TYPES": frozenset({"LexEntryType", "LexEntryInflType"}),
    # "INFLECTION_FEATURES covers FsClosedFeature and FsComplexFeature"
    "INFLECTION_FEATURES": frozenset({"FsClosedFeature", "FsComplexFeature"}),
    # ---- T048g: derived from the walk, not quoted from an omission -------
    # AFFIXES and STEMS are entry walks, and each has EXACTLY ONE
    # `ALREADY_PRESENT_BY_GUID` emission site: `affixes_plan_action`
    # (`Lib/categories.py:8466`) and `stems_plan_action`
    # (`Lib/categories.py:8882`). Both are guarded by the SAME predicate,
    # `_target_has_guid(_iter_lex_entries(context.target_handle), src_guid)`
    # (:8465 and :8881), so the object the skip found is a `LexEntry` and
    # can be nothing else.
    #
    # The walk goes on to transfer that entry's owned closure -- senses,
    # MSAs, allomorphs -- but the SKIP asserts only the entry, and the
    # candidate set is what the skip asserts. Widening it to the closure
    # would withhold the strong basis from `MoStemMsa` and the allomorph
    # rows on the strength of a match that never named them, which is the
    # over-poisoning T048f exists to prevent.
    "AFFIXES": frozenset({"LexEntry"}),
    "STEMS": frozenset({"LexEntry"}),
    # POS_INFLECTABLE_FEATS wires an EXISTING `IFsFeatDefn` into an EXISTING
    # POS's `InflectableFeatsRC` -- "No new LCM object is created"
    # (`Lib/categories.py:2859`, and again at :2758). Its one identity-skip
    # site (`Lib/categories.py:2829`) fires when that reference is already
    # in `InflectableFeatsRC`, and the `source_guid` it carries is the
    # COMPOUND key `"pos_guid::feat_guid"` -- not any object's GUID, and so
    # not a GUID the census could match a row against at all.
    "POS_INFLECTABLE_FEATS": _LINK_ONLY_IDENTITY_SKIP,
}


def identity_skip_class_table() -> tuple:
    """`(table, available)` -- `{category NAME: LCM class}` for identity skips.

    Read from `Lib/preview._LCM_CLASS_FOR_CATEGORY`, THE one-to-one table, and
    re-keyed by the category's `name` because that is what a run report's
    `skips[].category` carries (`report.to_snapshot_json` writes
    `s.category.name`). Deliberately not a copy: a second table next to a CLI
    is the drift this feature exists to end, and the same reasoning is already
    written down at `categories._lcm_class_for_category`, which reaches for the
    same table through the same kind of lazy import.

    The import is lazy and total-failure-tolerant for the reason this module's
    header states: nothing may pull a live-FLEx dependency in at module scope.
    `available` False means NO identity skip can be attributed, so every one of
    them becomes an unattributed match and every row keeps the `baseline_gross`
    basis -- the capped, advisory direction, which is the safe one.
    """
    try:
        if __package__:
            from .Lib.preview import _LCM_CLASS_FOR_CATEGORY as table
        else:  # pragma: no cover - script-mode import shim
            from Lib.preview import (  # type: ignore
                _LCM_CLASS_FOR_CATEGORY as table,
            )
    except Exception:  # noqa: BLE001 -- an unavailable table names no class
        return {}, False
    out = {}
    for category, name in table.items():
        key = getattr(category, "name", None)
        if isinstance(key, str) and key and isinstance(name, str) and name:
            out[key] = name
    return out, True


@dataclass(frozen=True)
class IdentitySkipTally:
    """What a run report's `ALREADY_PRESENT_BY_GUID` skips add to the census.

    `by_class` is the per-LCM-class count to ADD to the report's own
    `matched_to_source.by_object_class` tally. `withheld` is the set of classes
    that may not claim the `baseline_matched` basis because an identity skip
    that could have belonged to them went unattributed. `unbounded` is the same
    fact with no bound at all -- a category neither table knows -- and it
    withholds the stronger basis from EVERY class, which is the pre-T048b
    behaviour of `matched_class_is_complete` and the correct answer when the
    damage cannot be located.

    `measured` False means the report carried no `skips` list, which is NOT a
    zero: it is a report that predates the surface, and reading it as "no
    identity skips" would be the absent-read-as-zero error
    `census.unmatched_starter` refuses to make.
    """

    by_class: dict = field(default_factory=dict)
    unattributed_by_category: dict = field(default_factory=dict)
    withheld: frozenset = frozenset()
    unbounded: bool = False
    measured: bool = False
    counted: int = 0
    deduped: int = 0

    def total(self) -> int:
        return sum(self.by_class.values())


def identity_skips_from_report(path: Path) -> IdentitySkipTally:
    """The `ALREADY_PRESENT_BY_GUID` skips in a run report, tallied by class.

    Each such skip is one destination object the run found by GUID and left
    alone -- a match, and the strongest kind. Attributed through
    `identity_skip_class_table` and NOTHING else; a skip whose category is not
    one-to-one is counted as unattributed rather than guessed at, and takes the
    `baseline_matched` basis away from the classes it might have been (or from
    all of them, when even that is unknown).

    DEDUPED AGAINST THE ENRICHMENTS by GUID, so an object that was both matched
    and enriched is counted once. The report's `by_object_class` tally already
    counts every enrichment, and an identity skip's `source_guid` is also its
    target GUID, so the two surfaces can be compared directly. Measured on run
    `CENSUS-20260820-094825` the two sets are disjoint (3 enriched
    `PartOfSpeech` GUIDs, 2 skipped ones, no overlap) -- as they should be,
    since a whole-object skip and an enrichment are different dispositions of
    the same object and data-model.md section 7 permits only one of them per
    object. The dedup is not there because the overlap was observed; it is
    there because double-counting a match would OVERSTATE
    `starter_matched_to_source`, which under-subtracts and can hide a real
    shortfall -- the one direction this instrument must never be wrong in.
    """
    data = _load_json(path, "run report")
    skips = data.get("skips")
    if not isinstance(skips, list):
        return IdentitySkipTally()

    # Every GUID the report's own matched tally has already accounted for
    # through an enrichment record. Both GUID fields are read: `target_guid` is
    # the destination object and is what a skip's `source_guid` equals on a
    # GUID match, and `source_guid` is included because on this path the two
    # name the same object and a producer that emitted only one of them must
    # still be deduped.
    already: set = set()
    records = data.get("enrichments")
    if isinstance(records, list):
        for record in records:
            if not isinstance(record, dict):
                continue
            for key in ("target_guid", "source_guid"):
                guid = record.get(key)
                if isinstance(guid, str) and guid:
                    already.add(guid)

    table, available = identity_skip_class_table()
    by_class: dict = {}
    unattributed: dict = {}
    withheld: set = set()
    unbounded = False
    counted = 0
    deduped = 0
    seen: set = set()
    for skip in skips:
        if not isinstance(skip, dict):
            continue
        if skip.get("reason") != IDENTITY_SKIP_REASON:
            continue
        guid = skip.get("source_guid")
        guid = guid if isinstance(guid, str) else ""
        if guid and (guid in already or guid in seen):
            deduped += 1
            continue
        if guid:
            seen.add(guid)
        category = skip.get("category")
        category = category if isinstance(category, str) else ""
        object_class = table.get(category, "") if available else ""
        if object_class:
            by_class[object_class] = by_class.get(object_class, 0) + 1
            counted += 1
            continue
        unattributed[category] = unattributed.get(category, 0) + 1
        candidates = _AMBIGUOUS_IDENTITY_SKIP_CLASSES.get(category)
        if candidates is None:
            unbounded = True
        else:
            withheld |= set(candidates)
    return IdentitySkipTally(
        by_class=dict(sorted(by_class.items())),
        unattributed_by_category=dict(sorted(unattributed.items())),
        withheld=frozenset(withheld),
        unbounded=unbounded,
        measured=True,
        counted=counted,
        deduped=deduped,
    )


def merge_identity_skip_matches(matched_by_class: dict, tally) -> dict:
    """`matched_by_class` plus the identity skips, as a new sorted dict.

    A class present in only one of the two sources appears with that source's
    count; the report's tally and the skip tally count DISJOINT dispositions of
    disjoint objects (a match that wrote or enriched, versus a match that did
    neither), so they add rather than override.
    """
    merged = dict(matched_by_class)
    for name, count in getattr(tally, "by_class", {}).items():
        merged[name] = merged.get(name, 0) + count
    return dict(sorted(merged.items()))


# ---------------------------------------------------------------------------
# T048f: AN UNATTRIBUTED MATCH POISONS ONLY THE CLASSES IT COULD HAVE BEEN
#
# Raised by the T039 idempotence re-run (journal/T039-idempotence-rerun.md).
# `PhPhoneme` and `PhNCSegments` fell from `baseline_matched` to
# `baseline_gross` between two runs whose destination counts were IDENTICAL,
# manufacturing a 21-object and a 2-object phantom shortfall on a run that
# lost nothing. Their tallies were not missing: run 2's
# `matched_to_source.by_object_class` carried `PhPhoneme: 21` and
# `PhNCSegments: 2`, byte-for-byte what run 1 carried. They were REFUSED,
# because `matched_by_class_from_report` reports completeness as ONE GLOBAL
# BOOLEAN and run 2 left 11 matches unattributed in three unrelated
# categories (`GRAM_CATEGORIES`, `INFLECTION_FEATURES`, `VARIANT_TYPES`).
# Every one of the 75 rows lost the stronger basis for it.
#
# T048b already settled the principle for the OTHER incompleteness signal, in
# this same file, twenty lines from the site this fixes: an unattributable
# identity skip withholds `baseline_matched` "from only the classes it could
# have been" (`_AMBIGUOUS_IDENTITY_SKIP_CLASSES`). This applies that rule to
# the report's own unattributed matches, using the same two tables and the
# same unbounded fallback. Nothing new is trusted; a second signal stops
# being blunter than the first.
#
# `matched_to_source` already publishes `unattributed_by_category`, which is
# exactly the bounding data the rule needs -- so the bound is READ, never
# guessed. A category neither table knows is UNBOUNDED and still withholds
# the stronger basis from every class, which is the pre-T048f behaviour and
# the honest answer when the damage cannot be located.
#
# Why a third GUID audit would NOT have fixed this: T048d's
# `starter_matched_lower_bound` rescues `PartOfSpeech` on run 2 because its
# starters match by GUID. It is blind to `PhPhoneme` BY CONSTRUCTION -- a
# natural-key match links a source object to a destination object with a
# DIFFERENT guid, so `B - |D \ Q|` counts those 21 starters as
# destination-only. The bound below is the only thing that reaches them.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MatchedTallyBound:
    """Which classes a report's UNATTRIBUTED matches put at risk.

    `withheld` is the set of LCM classes whose `matched_to_source` tally may be
    understated, and which therefore may not claim the `baseline_matched`
    basis. `unbounded` is the same fact with no bound -- an incompleteness
    whose category neither attribution table knows, or an incompleteness the
    report asserts without saying where -- and it withholds the stronger basis
    from EVERY class.

    `measured` False means the report carried no `matched_to_source` block at
    all. That is not a clean bill of health, but it needs no bound either: with
    no block there is no per-class tally, so no row can reach the matched basis
    in the first place.
    """
    withheld: frozenset = frozenset()
    unbounded: bool = False
    measured: bool = False
    unattributed_by_category: dict = field(default_factory=dict)


def matched_tally_bound_from_report(path: Path) -> MatchedTallyBound:
    """Bound the damage from a report's unattributed matches.

    Resolution order per category, deliberately the same as
    `identity_skips_from_report`'s and for the same reason -- there is ONE
    authority for "which class does this category name":

    1. `preview._LCM_CLASS_FOR_CATEGORY`, the one-to-one table. A
       `GRAM_CATEGORIES` match can only ever have been a `PartOfSpeech`, so
       that is the only row it may poison.
    2. `_AMBIGUOUS_IDENTITY_SKIP_CLASSES`, the closed candidate sets for the
       categories that table deliberately omits.
    3. Neither -> `unbounded`.

    An `unattributed_by_category` entry with a non-positive count is not a
    risk and contributes nothing. A report claiming `complete is False` while
    publishing no `unattributed_by_category` is `unbounded`: it asserts an
    incompleteness and declines to locate it, which is precisely the case the
    global flag used to handle and the one case where being blunt is right.
    """
    data = _load_json(path, "run report")
    block = data.get("matched_to_source")
    if not isinstance(block, dict):
        return MatchedTallyBound()

    raw = block.get("unattributed_by_category")
    unattributed = {}
    if isinstance(raw, dict):
        for category, count in raw.items():
            if isinstance(category, str) and isinstance(count, int) and count > 0:
                unattributed[category] = count

    complete = block.get("complete")
    if not unattributed:
        # Nothing to bound. An explicit `complete is False` with no breakdown
        # is an unlocatable incompleteness; `complete` True or absent-with-no
        # -breakdown is a clean tally.
        return MatchedTallyBound(
            unbounded=complete is False,
            measured=True,
        )

    one_to_one, available = identity_skip_class_table()
    withheld = set()
    unbounded = False
    for category in unattributed:
        named = one_to_one.get(category) if available else None
        if named:
            withheld.add(named)
            continue
        candidates = _AMBIGUOUS_IDENTITY_SKIP_CLASSES.get(category)
        if candidates is not None:
            # KEY PRESENCE, not truthiness, and the sibling
            # `identity_skips_from_report` tests the same way. A category whose
            # candidate set is legitimately EMPTY -- `_LINK_ONLY_IDENTITY_SKIP`,
            # a match on a reference rather than on an object -- is bounded, and
            # bounded to nothing. Reading that empty set as "no answer" would
            # fall through to `unbounded` and withhold the strong basis from
            # every row in the census on the strength of a match that could not
            # have been any of them.
            withheld.update(candidates)
            continue
        # A category no table knows. Bounding it would be a guess, and a wrong
        # bound lets a row claim a basis its tally cannot support.
        unbounded = True

    return MatchedTallyBound(
        withheld=frozenset(withheld),
        unbounded=unbounded,
        measured=True,
        unattributed_by_category=dict(sorted(unattributed.items())),
    )


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
# ------------------- THE VOCABULARY GAP, NOW CLOSED ------------------------
# This block used to describe a gap. `fidelity-census.md` 7.1 had no token for
# "the source referent is legitimately absent, and the engine required it", so
# the least-wrong member of the closed enum was stamped instead, under a
# `TODO(contract)` and a `PROVISIONAL` marker in every emitted line's `detail`.
# Contract commit b2cb356 (2026-08-20) appended `SOURCE_REFERENT_ABSENT` to
# both places the closed vocabulary lives, and this module now stamps it. The
# TODO is discharged; the history is kept because it names what the substitute
# was costing.
#
# WHAT THE SUBSTITUTE COST, beyond being the wrong word. While the constant
# held "DEPENDENCY_UNRESOLVED", the source-side and destination-side drops were
# THE SAME TOKEN, so `dropped_by_class_from_report` grouped them into ONE
# accounting line per class -- two different causes, one number, no way to tell
# them apart in the artifact -- and the `detail ==` test below stamped the
# PROVISIONAL wording onto genuine destination-side drops that were never
# provisional at all. Measured on GT-20260821-184426 (census-038-t091-ngoreme):
# 4 classes, 1890 accounted items, every one of them carrying a `detail` that
# said the referent was absent on the SOURCE. A least-wrong token is not a
# smaller version of the right one; it is a collision.
#
# Why each rejected candidate stays rejected (b2cb356's argument, kept here so
# the next reader does not have to reopen the enum to re-derive it):
#
#     DEPENDENCY_UNRESOLVED | shortfall | A required referent is absent in the
#                                         destination (FR-017).
#
# "absent in the destination" is NOT this case: an MSA whose `PartOfSpeechRA`
# is empty ON THE SOURCE was never resolvable anywhere, and nothing about the
# destination would fix it. `NO_CREATE_PATH` is wrong too -- there IS a create
# path for `MoStemMsa` and the motivating run exercised it 162 times -- and so
# is `UNSUPPORTED_SUBTYPE`, which is about a subtype the engine cannot
# reproduce. The token is still a NAMED CONSTANT rather than a literal buried
# in the mapping below, because the mapping is not where a reader looks to ask
# "which token means which side of the transfer".
# ---------------------------------------------------------------------------

#: The token stamped on a drop whose referent was absent on the SOURCE
#: (`fidelity-census.md` 7.1; `$defs.reasonToken.enum`). The source-side
#: sibling of `DEPENDENCY_UNRESOLVED`, which is destination-side (FR-017); the
#: two are not interchangeable and no longer collide.
SOURCE_REFERENT_ABSENT_TOKEN: str = "SOURCE_REFERENT_ABSENT"

#: Said in every line that token produces. It used to explain a SUBSTITUTION,
#: and there is no longer a substitution to explain -- leaving that text in
#: place would put a false statement ("PROVISIONAL TOKEN ... the vocabulary has
#: no member for this") into every artifact line the token produces, which is
#: the same defect one layer down. Rewritten, not deleted: the `detail` slot is
#: what tells a reader of the ARTIFACT which side of the transfer the referent
#: was missing from, and that is worth saying in the artifact rather than only
#: in this source file.
SOURCE_REFERENT_ABSENT_DETAIL: str = (
    "the referent was absent ON THE SOURCE, so the dependent object was never "
    "transferable; distinct from DEPENDENCY_UNRESOLVED, which is absence in "
    "the destination (fidelity-census.md 7.1)"
)

#: `(substring of DroppedItemRecord.reason, FR-013 token)`, most specific first.
#: ORDER RE-VERIFIED when `SOURCE_REFERENT_ABSENT` landed (T096). The three
#: needles are mutually exclusive on the reasons `Lib/categories.py` actually
#: emits: `_resolve_or_none` picks "is empty on source" XOR "not resolvable in
#: target" for the same slot, `_null_pos_fallback_blocked` extends the former
#: and matches only it, and "is not reproducible by this engine" comes from a
#: different producer entirely. No needle is a substring of another, so nothing
#: shadows the new row and "most specific first" still holds by construction
#: rather than by luck.
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
    an ABSENT accounting line, never an 18th token.
    """
    if not isinstance(reason, str):
        return None
    for needle, token in DROP_REASON_TOKENS:
        if needle in reason:
            return token
    return None


# ---------------------------------------------------------------------------
# T087: a rule that IS reported reads as unexplained, because nothing here
# consumed `RunReport.rules_not_reproduced` (`process_rules` in the report
# JSON) at all -- only `dropped_items`, via `drop_reason_token` above.
#
# `Lib/categories.py._reproduce_affix_process._skip(reason)` writes the
# IDENTICAL `reason` string to BOTH a `DroppedItemRecord`
# (`item_name="MoAffixProcess", item_guid=<rule guid>`) and a
# `ProcessRuleTransferRecord` (`source_guid=<rule guid>,
# not_reproducible_reason=<same string>`) in the same call -- so a
# non-reproduction is corroborated on TWO independent report surfaces before
# this ever runs, and `process_rules_by_class_from_report` below requires
# BOTH to agree (same guid, same reason, verbatim) before crediting anything.
# Trusting either surface alone would be weaker than the evidence actually
# available, and the live corroboration ratio is 6/6
# (`_run_reports/038-phase6-mbugwe-report.json`, GT-20260821-020541).
#
# THIS TABLE IS KEPT SEPARATE FROM `DROP_REASON_TOKENS`, not merged into it.
# Folding the needle below into the general table would make
# `dropped_by_class_from_report` classify the SAME `MoAffixProcess` drop a
# second time on its own (free-text, uncorroborated) path, and merging the
# two classifications would double-credit one lost rule as two accounted
# objects -- the over-accounting R-2 forbids. `MoAffixProcess` process-rule
# non-reproductions are therefore accounted EXCLUSIVELY through this table;
# `dropped_by_class_from_report` never needs to be told to skip them, because
# none of `DROP_REASON_TOKENS`' three needles occur in any reason
# `_reproduce_affix_process` produces (verified against every `_skip(...)`
# call site in `Lib/categories.py`, 2026-08-22).
#
# "which this rule does NOT own -- it belongs to the shared project-level
# PhPhonData.ContextsOS and is absent from the destination" (create-path
# contract condition 4, the T063/T064 live run's 6 skips) and its two
# siblings in the same function (an unresolved `PhSimpleContextSeg` /
# `PhSimpleContextNC` referent, and an unresolved `MoInsertPhones` terminal)
# all read "... is absent from the destination ...", and all three are the
# SAME shape: a reference the rule cannot own resolving to nothing in the
# target. `DEPENDENCY_UNRESOLVED` (FR-017, destination-side absence) is the
# exact existing token for that shape -- not a new, 18th one (FR-013).
PROCESS_RULE_REASON_TOKENS: tuple = (
    ("is absent from the destination", "DEPENDENCY_UNRESOLVED"),
)


def process_rule_reason_match(reason):
    """-> `(needle, token)` for one free-text `not_reproducible_reason`, or
    None. The NEEDLE is returned as well as the token so the accounting
    line's `detail` can quote the text that produced the classification
    rather than merely asserting one (see `_process_rule_detail`).
    """
    if not isinstance(reason, str):
        return None
    for needle, token in PROCESS_RULE_REASON_TOKENS:
        if needle in reason:
            return (needle, token)
    return None


def process_rule_reason_token(reason):
    """-> the FR-013 token for one free-text `not_reproducible_reason`, or
    None. Sibling of `drop_reason_token`, over a separate, smaller table
    (see `PROCESS_RULE_REASON_TOKENS` for why it is not the same table).
    """
    matched = process_rule_reason_match(reason)
    return None if matched is None else matched[1]


def _process_rule_detail(needle: str, count: int, run_id: str) -> str:
    """The `AccountedLine.detail` for one process-rule accounting line.

    T087's requirement is that an `accounted_for` entry carry the report
    reference AND the reason, "so a shortfall is only ever explained by
    evidence that actually exists". The GUIDs are in `report_ref.record_ids`
    and the classified reason is the line's `reason` token, but neither says
    WHICH report surfaces were read or that they were required to agree --
    and `accounted_for_drops`' default detail names only the
    `DroppedItemRecord`, which would describe half the evidence this line
    actually rests on. So the corroboration is stated, with the matched
    needle quoted verbatim: a reader who disagrees with the classification
    can see exactly what text produced it without opening the report.
    """
    return (
        "reproduced=False on " + str(count) + " ProcessRuleTransferRecord(s), "
        "each corroborated by a DroppedItemRecord carrying the SAME reason "
        "verbatim on run " + (run_id or "(unstamped)") + "; classified from "
        + repr(needle) + " -- see report_ref.record_ids for the rule GUIDs "
        "and the report for each full reason"
    )


def process_rules_by_class_from_report(path: Path, classes=()) -> dict:
    """`{"MoAffixProcess": ((token, census.ReportRef, detail), ...)}` from the
    STRUCTURED `process_rules` array (FR-023..FR-025), corroborated against
    `dropped_items`.

    The third element is the per-line `detail` override `accounted_for_drops`
    accepts (see `_process_rule_detail`); `dropped_by_class_from_report`
    emits 2-tuples and takes that function's default.

    Every `ProcessRuleTransferRecord` is an outcome of transferring one
    source `MoAffixProcess` (`Lib/models.py` docstring), so the object class
    is not read off the record at all -- it is the one constant this
    function ever emits, and it is emitted only when `"MoAffixProcess"` is
    one of `classes`.

    CORROBORATION IS REQUIRED, NOT ASSUMED. A `reproduced=False` record is
    credited only when `dropped_items` ALSO carries a `DroppedItemRecord`
    with `item_name="MoAffixProcess"`, the same `item_guid` as this record's
    `source_guid`, and the SAME `reason` text verbatim. Two independent
    surfaces of the same run report agreeing is stronger evidence than
    either alone, and it means a future producer bug -- a
    `ProcessRuleTransferRecord` written without its paired
    `DroppedItemRecord`, or with a reason that drifted between the two -- is
    read as UNCLASSIFIABLE rather than silently trusted.

    Classification of the (corroborated) reason is via
    `process_rule_reason_token`, not `drop_reason_token` -- see
    `PROCESS_RULE_REASON_TOKENS` for why the two tables must not merge. A
    reason neither table can read (the source-side "empty MembersRS in the
    SOURCE" skips, for instance) yields no line, per FR-013: unclassified is
    an absent line, never a guess.
    """
    if "MoAffixProcess" not in frozenset(classes):
        return {}
    data = _load_json(path, "run report")
    rules = data.get("process_rules")
    if not isinstance(rules, list):
        return {}
    dropped = data.get("dropped_items")
    corroborated: dict = {}
    if isinstance(dropped, list):
        for record in dropped:
            if not isinstance(record, dict):
                continue
            if record.get("item_name") != "MoAffixProcess":
                continue
            guid = record.get("item_guid")
            reason = record.get("reason")
            if isinstance(guid, str) and guid and isinstance(reason, str):
                corroborated.setdefault(guid, set()).add(reason)

    context = data.get("context") or {}
    run_id = data.get("run_id") or context.get("run_id") or ""
    if not (isinstance(run_id, str) and _RUN_ID_PATTERN.match(run_id)):
        run_id = ""

    by_token: dict = {}
    for record in rules:
        if not isinstance(record, dict) or record.get("reproduced"):
            continue
        guid = record.get("source_guid")
        reason = record.get("not_reproducible_reason")
        if not isinstance(guid, str) or not guid:
            continue
        if not isinstance(reason, str) or not reason:
            continue
        if reason not in corroborated.get(guid, ()):
            continue  # the two surfaces disagree (or the drop is absent)
        matched = process_rule_reason_match(reason)
        if matched is None:
            continue
        needle, token = matched
        by_token.setdefault((token, needle), []).append(guid)

    if not by_token:
        return {}
    return {"MoAffixProcess": tuple(
        (token, census.ReportRef(
            kind="dropped_item",
            count_in_report=len(guids),
            run_id=run_id,
            report_path=str(path),
            record_ids=tuple(guids),
        ), _process_rule_detail(needle, len(guids), run_id))
        for (token, needle), guids in sorted(by_token.items())
    )}


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


def _merge_by_class_tokens(a: dict, b: dict) -> dict:
    """Union two `{object_class: ((token, ReportRef[, detail]), ...)}` maps.

    Concatenation, not replacement: `dropped_by_class_from_report` and
    `process_rules_by_class_from_report` (T087) read two DIFFERENT report
    arrays for two DISJOINT sets of tokens by construction (see the latter's
    module comment), so a class present in both never collides on a token --
    but nothing here assumes that to stay safe. Two lines with the same
    reason on the same class is still one room-capped claim per line at the
    `accounted_for_drops` seam (R-2), never a double credit of one object.
    """
    if not b:
        return a
    if not a:
        return b
    merged = {cls: list(pairs) for cls, pairs in a.items()}
    for cls, pairs in b.items():
        merged.setdefault(cls, []).extend(pairs)
    return {cls: tuple(pairs) for cls, pairs in merged.items()}


def read_report_evidence(path: Optional[Path], classes=()) -> ReportEvidence:
    """`ReportEvidence` for a run report, or the empty one for no report."""
    if path is None:
        return ReportEvidence()
    enriched, measured = enriched_by_class_from_report(path)
    return ReportEvidence(
        present=True,
        enriched_by_class=enriched,
        enriched_measured=measured,
        dropped_by_class=_merge_by_class_tokens(
            dropped_by_class_from_report(path, classes),
            process_rules_by_class_from_report(path, classes),
        ),
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

    A `drops` entry is `(token, ref)` or `(token, ref, detail)`. The optional
    third element OVERRIDES the default detail, which names only a
    `DroppedItemRecord` -- true of `dropped_by_class_from_report`'s entries
    and only half the story for `process_rules_by_class_from_report`'s, which
    require two report surfaces to agree (T087). The cap suffix is appended to
    whichever detail applies, so an overridden line still says it was capped.
    """
    if difference is None or difference >= 0:
        return ()
    room = -difference
    lines = []
    for entry in drops:
        token, ref = entry[0], entry[1]
        override = entry[2] if len(entry) > 2 else None
        if room <= 0:
            break
        count = min(ref.count_in_report, room)
        detail = override if override else (
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


#: T109 -- the token, spelled once. Not re-declared as a literal at the emit
#: site, for the same reason `SOURCE_REFERENT_ABSENT_TOKEN` is not.
GOVERNED_BY_OTHER_FEATURE_TOKEN = "GOVERNED_BY_OTHER_FEATURE"


def accounted_for_governed_class(
        object_class, difference, existing=(), notes=None) -> tuple:
    """-> `(census.AccountedLine,)` when this class is another feature's, else ().

    T109. `census.governed_by_other_feature` is the roster lookup and the ONLY
    one; this function is the arithmetic, and the arithmetic is the lock.

    T109 LOCK 2 -- THE CAP, at `max(0, -difference)` less whatever the row's
    existing lines already claim in the same direction. This is not merely an
    R-2 safety rail ("the census must not explain away more than actually
    happened"): `census.unexplained_counts` computes
    `max(0, -difference) - sum(shortfall lines)`, and `census._phase_5` fails a
    row whose `unexplained_shortfall` is still nonzero AFTER accounting, so the
    cap is also the exact figure that makes a stamped row PASS. A claim that
    under-shoots leaves the row red anyway; one that over-shoots is
    `CENSUS_ERROR` at `census.over_accounted_directions`. There is one right
    number and it is the room.

    Unlike `accounted_for_drops`, the count here is derived from the row's OWN
    difference rather than from a run-report tally, and that is what makes the
    cap airtight rather than best-effort: there is no external number to
    outrun, and no shared tally that two rows could both spend. (It is also why
    an Amendment A1 split row would be safe -- each half's difference is its
    own measurement -- where a report drop count is not. No rostered class is
    an A1 split class, so the case does not arise.)

    THE TWO NON-SHORTFALL DIRECTIONS, ruled on explicitly rather than falling
    out of an inequality:

    * `difference is None` -> NOTHING. T099: a null difference is not a zero.
      `census.row_verdict_class` makes such a row NOT_EVALUATED, `_phase_5`
      skips it, and `class_row_artifact` zeroes both unexplained counts for it,
      so a line here would claim objects nobody counted against a row the gate
      does not read. The schema's `count` has `minimum: 1`, so there is not
      even a zero-count line available to express it with.
    * `difference >= 0` -> NOTHING. The contract's table gives this token
      direction "either", so the token itself would permit a surplus line, and
      the refusal is a judgment rather than a limitation: a destination holding
      MORE objects of a governed class than the source is not something another
      feature failed to do, it is something that DID happen, and naming an
      owner for it would excuse an over-creation nobody has attributed. Every
      governed non-MATCHED row on all three sanctioned pairs is SHORTFALL, so
      this is a refusal made before it was needed rather than after.
    """
    entry = census.governed_by_other_feature(object_class)
    if entry is None:
        return ()
    if difference is None or difference >= 0:
        return ()
    room = -difference - census.accounted_in_direction(existing, "shortfall")
    if room <= 0:
        if notes is not None and existing:
            notes.append(
                object_class + " is governed by " + entry[0] + " but its "
                "shortfall of " + str(-difference) + " is already fully "
                "claimed by " + str(len(tuple(existing))) + " earlier "
                "accounting line(s), so NO GOVERNED_BY_OTHER_FEATURE line was "
                "emitted (R-2: the census must not explain away more than "
                "actually happened)"
            )
        return ()
    owner, _reason = entry
    detail = (
        "governed by " + owner + ": this feature reports the figure and does "
        "not fix it (spec.md Assumptions; fidelity-census.md's reason table "
        "for GOVERNED_BY_OTHER_FEATURE). Needs no report_ref -- invariant 5 "
        "exempts the token, because there is no run-report line to resolve "
        "against: the objects were never this run's to create"
    )
    if room != -difference:
        capped = (
            object_class + " is governed by " + owner + " and its shortfall is "
            + str(-difference) + ", of which "
            + str(census.accounted_in_direction(existing, "shortfall"))
            + " is already claimed by earlier accounting line(s), so the "
            "GOVERNED_BY_OTHER_FEATURE line claims only " + str(room)
            + " (R-2: the census must not explain away more than actually "
            "happened)"
        )
        if notes is not None:
            notes.append(capped)
        detail = detail + " -- CLAIM CAPPED, see notes"
    return (census.AccountedLine(
        reason=GOVERNED_BY_OTHER_FEATURE_TOKEN, count=room,
        direction="shortfall", detail=detail),)


# ---------------------------------------------------------------------------
# T048d: THE IDENTITY AUDIT, WIRED
#
# `census.starter_matched_lower_bound` proves the arithmetic; this is where the
# two GUID sets it needs get read. The pass runs inside the SAME open as the
# counts -- in `_open_source` / `_open_destination`, beside `_count_split` and
# `duplicate_reports_for` -- because `census.read_project` closes the handle in
# a `finally` before it returns, and a second open of either project to finish
# reading would widen the digest window that function exists to close.
#
# WHICH CLASSES ARE AUDITED IS DERIVED, NOT LISTED. A class the baseline counts
# as ZERO cannot carry a phantom shortfall: gross subtraction subtracts nothing
# from it, so the two bases already agree. Only a class with a NONZERO baseline
# count can be over-subtracted, and that set comes from the baseline document
# itself. A hand-maintained list of "the FW-global classes" would be the drift
# this feature exists to end -- and it would also be wrong, because which
# classes a starter project ships is a property of the FieldWorks version that
# made it, not of this source file.
#
# THE COST IS BOUNDED BY THE BASELINE. The audited classes hold 3014 objects on
# the measured starter baseline, and the pass enumerates each such class once
# per project. `--no-identity-audit` turns it off for a project where even that
# is too much; the consequence is stated where the flag is declared.
# ---------------------------------------------------------------------------


def identity_audit_classes(baseline, measurable) -> tuple:
    """The classes worth a GUID pass: nonzero baseline count, and measurable.

    Sorted, so two runs enumerate in the same order and a slow run is
    diagnosable. Empty for a missing baseline -- there is no B to bound, so
    every row would decline anyway and the pass would be pure cost.
    """
    if baseline.is_missing:
        return ()
    wanted = set(measurable)
    return tuple(sorted(
        entry.object_class for entry in baseline.entries
        if entry.count > 0 and entry.object_class in wanted
    ))


def _row_for_entry(
    entry, source_counts, destination_counts, baseline,
    matched_by_class=None, matched_complete=False,
    *, evidence: Optional[ReportEvidence] = None,
    withheld_classes=frozenset(),
    source_guids=None, destination_guids=None,
    source_unmeasurable=frozenset(), destination_unmeasurable=frozenset(),
    source_name: str = "", destination_name: str = "",
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

    T048D ADDS A SECOND WAY TO EARN THE SAME BASIS, and it is deliberately
    SUBORDINATE to the first. The identity audit
    (`census.starter_matched_lower_bound`) is consulted only when the three
    conditions above did NOT hold, so no row that already reads its matched
    count off the run report changes behaviour: the audit can only move rows
    that were on `baseline_gross`, which is exactly the population T048d is
    about. Where both could speak they agree in kind but not in strength -- the
    report's tally is an attribution, the audit is a measurement -- and mixing
    them by taking the larger would be the one arithmetic that can HIDE a
    shortfall.
    """
    matched_by_class = matched_by_class or {}
    evidence = evidence or ReportEvidence()
    withheld_classes = withheld_classes or frozenset()
    source_guids = source_guids or {}
    destination_guids = destination_guids or {}
    audited = None
    matched_effective = None
    # T099: nullability is decided PER SIDE, because unmeasurability is a
    # property of one project. `in_class_list_via == 'excluded_not_measurable'`
    # is the class-wide case (an abstract LCM base, never asked for in either
    # project); the two `*_unmeasurable` sets are the per-project case (the
    # accessor did not resolve THERE). A class can be countable in the source
    # and not in the destination, and reporting the source count as unknown
    # because the destination's accessor drifted would lose a number the census
    # actually holds.
    #
    # Indexing stays `[...]`, not `.get(..., None)`, for the measured sides: a
    # class absent from `counts` with no recorded reason is a bug in the
    # counting pass, and a KeyError says so where a defaulted None would look
    # exactly like an honest "could not count".
    in_class_list = entry.in_class_list_via != "excluded_not_measurable"
    source_ok = in_class_list and entry.object_class not in source_unmeasurable
    destination_ok = (
        in_class_list and entry.object_class not in destination_unmeasurable)
    measured = source_ok and destination_ok
    notes = []
    source_count = source_counts[entry.object_class] if source_ok else None
    destination_count = (
        destination_counts[entry.object_class] if destination_ok else None)
    if not in_class_list:
        notes.append(_NOT_MEASURED_NOTE)
    else:
        for ok, project in ((source_ok, source_name),
                            (destination_ok, destination_name)):
            if not ok:
                notes.append(_UNRESOLVED_ACCESSOR_NOTE.format(
                    project=repr(project) if project else "the project"))

    # Looked up by `row_key`, not by class: an A1 split row's key is not in the
    # baseline, so both halves land on `absent_from_baseline` and the class's
    # single baseline count cannot be subtracted twice.
    baseline_count = (
        None if baseline.is_missing else baseline.count_for(entry.row_key)
    )
    # T099: the `else` arm below does arithmetic on both counts, so it must be
    # unreachable when either is null. It is, by construction -- a baseline is
    # captured over `_measurable_classes` only, so an unmeasured class cannot
    # appear in a baseline document and `baseline_count` is None for it -- and
    # this raise is here so that "by construction" stays checked rather than
    # remembered. Doing the arithmetic on a null would produce a TypeError deep
    # inside a note string, which is a worse way to learn the same thing.
    if not measured and baseline_count is not None:
        raise census.CensusError(
            "class " + repr(entry.object_class) + " could not be counted but "
            "the baseline document carries a count of " + str(baseline_count)
            + " for it -- a baseline is captured over measurable classes only, "
            "so this baseline and this class list disagree about what is "
            "countable, and subtracting the one from the other would be "
            "arithmetic over an unknown"
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
        # T048b: a class whose tally may be understated by an identity skip
        # nobody could attribute does not reach the stronger basis. Same rule
        # as `matched_complete`, bounded to the classes actually at risk --
        # see `_AMBIGUOUS_IDENTITY_SKIP_CLASSES`.
        withheld = entry.object_class in withheld_classes
        if (
            matched_complete
            and matched is not None
            and entry.owning_feature_system is None
            and not withheld
        ):
            basis = "baseline_matched"
            # T048b: THE TALLY IS CAPPED AT THE BASELINE, and the cap is not
            # cosmetic. `starter_matched_to_source` counts STARTER objects the
            # run matched, so it cannot exceed the number of starter objects
            # that exist. On a SECOND run against the same destination every
            # object the first run created is matched too -- measured on T039's
            # run 2, 164 `MoStemMsa` matches against a starter baseline of 0 --
            # and `census.unmatched_starter` does not clamp, so an uncapped
            # tally would return -164, be subtracted as a NEGATIVE, and inflate
            # `destination_count_net` by 164. That hides a real shortfall,
            # which is the one direction this instrument must never be wrong
            # in. Capping errs the other way: it subtracts more, so a capped
            # row can only ever report a shortfall it does not have, and the
            # note below says so out loud (the T023c rule -- a capped number is
            # never silent).
            matched_effective = min(matched, baseline_count)
            if matched_effective != matched:
                notes.append(
                    "starter_matched_to_source CAPPED from " + str(matched)
                    + " to the starter baseline of " + str(baseline_count)
                    + ": a matched count above the baseline names objects that "
                    "were not in the starter (a re-run matches what the "
                    "previous run created), and only starter objects may be "
                    "subtracted"
                )
            starter_excluded = census.unmatched_starter(
                baseline_count, matched_effective)
            notes.append(
                "starter_matched_to_source=" + str(matched_effective)
                + " read from the run report; subtracting "
                + str(starter_excluded) + " unmatched starter object(s) rather "
                "than the gross baseline of " + str(baseline_count)
            )
        else:
            # T048d: no report tally reached this row. Before falling back to
            # gross subtraction, ask the projects directly. `withheld` is NOT
            # consulted here: it exists because an unattributable identity skip
            # may have understated the TALLY, and the audit does not read the
            # tally -- it reads two GUID sets -- so the tally's incompleteness
            # cannot corrupt it.
            audited = (
                census.starter_matched_lower_bound(
                    baseline_count,
                    destination_count,
                    destination_guids.get(entry.object_class),
                    source_guids.get(entry.object_class),
                )
                if entry.owning_feature_system is None else None
            )
            audited_excluded = (
                census.unmatched_starter(baseline_count, audited)
                if audited is not None else None
            )
            # A LOWER BOUND IS CONCLUSIVE IN EXACTLY ONE CASE, and this is the
            # test for it. `audited` bounds the matched count from BELOW, so
            # `audited_excluded` bounds the subtraction from ABOVE and the
            # audited difference is the MOST NEGATIVE the row can be. When that
            # figure is already >= 0 the row is PROVED to have lost nothing,
            # and the matched basis states a fact.
            #
            # When it is still negative the audit has only narrowed an
            # interval: the true difference lies somewhere between the audited
            # figure and the gross one, and nothing here knows where. Taking
            # the matched basis then would be a category error with a
            # consequence -- `census.is_gross_basis_row` is the single
            # predicate 5.2's verdict cap turns on, so a `baseline_matched` row
            # is EVIDENCE and its unexplained shortfall FAILS the run. Measured
            # on run CENSUS-20260820-125034, promoting the unresolved rows took
            # the verdict from CENSUS_ACCOUNTED to UNEXPLAINED_SHORTFALL on
            # numbers that are upper bounds -- the cap's own rationale ("it
            # reports a shortfall on a correct run") reappearing one basis to
            # the left. So an unresolved audit keeps the gross basis and puts
            # its finding in a NOTE, where it is visible without being
            # load-bearing.
            audit_resolves = (
                audited is not None
                and destination_count - audited_excluded - source_count >= 0
            )
            if audit_resolves:
                basis = "baseline_matched"
                starter_excluded = audited_excluded
                notes.append(
                    "starter_matched_to_source=" + str(audited)
                    + " from the T048d IDENTITY AUDIT, not from the run "
                    "report: this class has no matched tally of any kind (no "
                    "action, no overwrite, no skip), which is what FW-global "
                    "fixed content looks like. The number is a PROVABLE LOWER "
                    "BOUND, the starter baseline of " + str(baseline_count)
                    + " minus the "
                    + str(len(set(destination_guids.get(entry.object_class))
                              - set(source_guids.get(entry.object_class))))
                    + " destination object(s) whose GUID is absent from the "
                    "source; subtracting " + str(audited_excluded)
                    + " unmatched starter object(s) rather than the gross "
                    "baseline of " + str(baseline_count) + ". The bound "
                    "RESOLVES this row: it is the most negative the difference "
                    "can be, and it is not negative, so no source object of "
                    "this class failed to arrive."
                )
            else:
                basis = "baseline_gross"
                starter_excluded = baseline_count
                if audited is not None:
                    notes.append(
                        "the T048d IDENTITY AUDIT narrows this row's shortfall "
                        "to AT MOST " + str(abs(min(
                            0, destination_count - audited_excluded
                            - source_count)))
                        + " (starter_matched_to_source >= " + str(audited)
                        + " by GUID), against the "
                        + str(abs(min(
                            0,
                            destination_count - baseline_count - source_count)))
                        + " the gross basis reports. The row KEEPS the gross "
                        "basis and its shortfall stays advisory: the audit "
                        "supplies a lower bound on the matched count, so the "
                        "narrowed figure is an UPPER bound on the loss and not "
                        "the loss itself, and 5.2's cap exists for exactly the "
                        "arithmetic that can over-report a shortfall."
                    )
            if withheld:
                notes.append(
                    "the `baseline_matched` basis is WITHHELD from this class "
                    "(T048b): the run report carries an identity skip whose "
                    "LCM class could not be determined and which could have "
                    "been a " + entry.object_class + ", so this class's "
                    "matched tally may be understated. Shortfalls on this row "
                    "are advisory (fidelity-census.md 5.2)."
                )

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
        # T099: None when either count is. `ClassCensusRow` enforces the same
        # rule from the other side, so a caller cannot pass 0 here instead.
        difference=(
            None if (source_count is None or destination_count is None)
            else destination_count - starter_excluded - source_count
        ),
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
        # The CAPPED value, because it is the number actually subtracted --
        # publishing the raw tally beside a different subtraction would make
        # the artifact's own arithmetic unreproducible. The raw value is in
        # `notes` whenever the cap bit.
        # T048d: `audited` is the same field from the other evidence source,
        # and the two are mutually exclusive by construction -- the audit is
        # only consulted on the branch where `matched_effective` stayed None.
        kwargs["starter_matched_to_source"] = (
            matched_effective if matched_effective is not None else audited
        )

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

    # ---- T109: a class another feature GOVERNS is accounting -------------
    # AFTER the reported drops, and reading them, because the cap is the ROOM
    # LEFT and not the whole difference. A reported drop is the more specific
    # claim -- it names run-report content invariant 5 can resolve -- so it
    # gets the room first and the governance line takes what is left. Ordering
    # it the other way would let the residual claim swallow the difference and
    # leave the specific, evidenced line with nothing to pay down.
    #
    # Note this can produce a row with a governed line AND a non-admissible
    # one, which `census._phase_5` still fails ("real accounting but not
    # phase-5 done"). That is correct and deliberate: the governance line says
    # who owns the class, not that the row is finished.
    #
    # NO out-of-scope guard, matching `accounted_for_drops`. A row carrying a
    # `not_evaluated_reason` is NOT_EVALUATED, `_phase_5` skips it outright, and
    # `class_row_artifact` zeroes both residues for it -- so a line on such a
    # row cannot buy a pass and R-5 still balances. (No rostered class carries
    # one today: `CmAnthroItem` is the artifact's only out-of-scope class.)
    lines = lines + accounted_for_governed_class(
        entry.object_class, row.difference, lines, notes)
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
    identity_audit: bool = True,
) -> int:
    """Census one source -> destination pair, write the artifact, gate it.

    The artifact is written even when the verdict fails -- 5.3's "no baseline;
    the counts are still written, the run cannot pass". The exit code is the
    gate's, taken from `census.gate_artifact`.
    """
    # T098: the instrument's own provenance, checked before a project is
    # opened. `NaturalKeyDefinition.roster_source` names the document that
    # admits each natural key, and until T098 nothing read it -- so six entries
    # went on naming 038's proposal for two days after 035 admitted them. A
    # census that is wrong about which classes can fail its own duplicate gate
    # should not be measuring anything, so this raises rather than warns.
    base = census.repo_root() if root is None else Path(root)
    census.verify_roster_sources(base)
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

    # T048d: the GUID pass, over the classes the baseline counts as nonzero.
    audit_classes = (
        identity_audit_classes(baseline, wanted) if identity_audit else ()
    )
    source_guids: dict = {}
    destination_guids: dict = {}
    audit_unreadable: dict = {}
    if audit_classes:
        _info("identity audit " + str(len(audit_classes))
              + " class(es) with a nonzero starter baseline, by GUID")
    elif identity_audit and not baseline.is_missing:
        _info("identity audit skipped: no class carries a nonzero starter "
              "baseline count, so no row can be over-subtracted")

    def _count_split(handle, into: dict) -> None:
        for split_class in split_classes:
            into[split_class] = census.count_by_feature_system(
                handle, split_class)

    def _audit_guids(handle, into: dict) -> None:
        if not audit_classes:
            return
        found, unreadable = census.guid_sets_for(handle, audit_classes)
        into.update(found)
        # Merged rather than assigned: a class unreadable on EITHER side must
        # decline, and `starter_matched_lower_bound` declines on a missing set
        # from either project, so recording both sides' failures is what makes
        # the message name the real reason.
        for name, why in unreadable.items():
            audit_unreadable.setdefault(name, why)

    def _open_source(name: str):
        handle = opener(name)
        _count_split(handle, source_split)
        _audit_guids(handle, source_guids)
        return handle

    def _open_destination(name: str):
        handle = opener(name)
        # Every extra pass runs while the handle is open, because
        # `read_project` closes it in a `finally` before it returns.
        duplicates.update(census.duplicate_reports_for(
            handle, wanted, admitted=admitted))
        _count_split(handle, destination_split)
        _audit_guids(handle, destination_guids)
        return handle

    # T099: an unresolved accessor is REPORTED, not raised. It prints as a
    # [FAIL] line, becomes an `errors[]` entry (CENSUS_ERROR / exit 7 in
    # `census.recompute_verdict`), and leaves the class a null-counted
    # NOT_EVALUATED row -- so the run still fails, and now the artifact says
    # which class, in which project, and why. Before this the run raised and
    # produced no artifact at all: loud in the console, silent in the record.
    census_errors: list = []
    source_reading = census.read_project(
        source, wanted, projects_root=projects_root,
        open_project=_open_source)
    if source_reading.counts.unmeasurable:
        census_errors.extend(_print_unmeasurable(source_reading))

    destination_reading = census.read_project(
        destination, wanted,
        projects_root=projects_root,
        declared_freshly_created=destination_freshly_created or None,
        open_project=_open_destination,
    )
    if destination_reading.counts.unmeasurable:
        census_errors.extend(_print_unmeasurable(destination_reading))

    source_counts = dict(source_reading.counts.counts)
    destination_counts = dict(destination_reading.counts.counts)
    source_unmeasurable = frozenset(source_reading.counts.unmeasurable)
    destination_unmeasurable = frozenset(
        destination_reading.counts.unmeasurable)

    # T024d-b: per-class matched tallies, when the run report carries them.
    matched_by_class, matched_complete = (
        matched_by_class_from_report(run_report)
        if run_report is not None else ({}, False)
    )
    # T048b: an `ALREADY_PRESENT_BY_GUID` skip is a match the report's own
    # tally never counted, because `report.build_from_plan` calls
    # `_count_matched` on the actions and overwrites loops and not on the skips
    # loop. Read them here and add them in, deduped by GUID against the
    # enrichments the report DID count.
    identity_skips = (
        identity_skips_from_report(run_report)
        if run_report is not None else IdentitySkipTally()
    )
    if identity_skips.by_class:
        matched_by_class = merge_identity_skip_matches(
            matched_by_class, identity_skips)
        # `matched_complete` is the report's claim about the tally IT built. An
        # identity skip this instrument attributed itself is attributed by
        # construction -- it went into `by_class` precisely because the
        # one-to-one table named its class -- so counting it cannot make the
        # merged tally less complete than the report's was.
        matched_complete = matched_complete or bool(matched_by_class)
    # T048f: bound the report's OWN unattributed matches the way T048b bounds
    # unattributable identity skips, instead of collapsing every row on one
    # global flag.
    matched_bound = (
        matched_tally_bound_from_report(run_report)
        if run_report is not None else MatchedTallyBound()
    )
    withheld_classes = frozenset(identity_skips.withheld) | matched_bound.withheld
    if identity_skips.unbounded or matched_bound.unbounded:
        # No bound on which class the unattributed evidence belonged to, so the
        # stronger basis is withheld from every class -- the pre-T048b
        # behaviour, and the honest answer when the damage cannot be located.
        matched_complete = False
    elif matched_by_class:
        # T048f: every incompleteness this report carries is now LOCATED, and
        # `withheld_classes` above names exactly the rows it can have
        # understated. A class outside that set has a tally that provably
        # cannot be understated, so `matched_complete` -- which the report
        # states globally -- must not keep denying it. This is the same move
        # T048b's line above makes for the skip tally, and it is safe for the
        # same reason: the per-row `withheld` check, not this flag, is what
        # protects the rows actually at risk.
        matched_complete = True
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
                matched_by_class, matched_complete, evidence=evidence,
                withheld_classes=withheld_classes,
                source_guids=source_guids,
                destination_guids=destination_guids,
                source_unmeasurable=source_unmeasurable,
                destination_unmeasurable=destination_unmeasurable,
                source_name=source_reading.name,
                destination_name=destination_reading.name)
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
                withheld_classes=withheld_classes,
                source_unmeasurable=source_unmeasurable,
                destination_unmeasurable=destination_unmeasurable,
                source_name=source_reading.name,
                destination_name=destination_reading.name,
            )
            # No GUID sets, for the same reason a split row cannot reach the
            # matched basis from the report: a GUID set is per LCM CLASS, and
            # crediting one class's audit to a feature-system half would
            # subtract the same starter objects twice. `_row_for_entry` guards
            # this independently on `owning_feature_system`.
            # No natural-key definition covers a split class, and a whole-class
            # duplicate report attached to one half would double-count it.
            duplicate_report = None
        rows.append(census.class_row_artifact(
            row, entry, duplicates=duplicate_report, **kwargs))

    if audit_unreadable:
        _warn(
            "T048d: the identity audit could not read "
            + str(len(audit_unreadable)) + " class(es) ("
            + ", ".join(sorted(audit_unreadable)) + "), so each of them keeps "
            "the gross basis and its shortfall stays advisory. First reason: "
            + audit_unreadable[sorted(audit_unreadable)[0]]
        )
    audited_rows = tuple(sorted(
        row["class"] for row in rows
        if row.get("starter_subtraction_basis") == "baseline_matched"
        and any("IDENTITY AUDIT" in note for note in row.get("notes", ()))
    ))
    if audited_rows:
        _info(
            "T048d: the identity audit earned the `baseline_matched` basis for "
            + str(len(audited_rows)) + " row(s) that no run-report tally "
            "reached: " + ", ".join(audited_rows)
            + " -- FW-global fixed content arrives correct and is recorded "
            "nowhere, so the evidence has to come from the projects."
        )
    if identity_skips.measured and identity_skips.total():
        _info(
            "T048b: counted " + str(identity_skips.total())
            + " ALREADY_PRESENT_BY_GUID skip(s) as starter matches across "
            + str(len(identity_skips.by_class)) + " class(es)"
            + (" (" + str(identity_skips.deduped)
               + " deduped against the enrichments)"
               if identity_skips.deduped else "")
            + " -- an identity skip is a match, and the strongest kind."
        )
    if identity_skips.unattributed_by_category:
        _warn(
            "T048b: " + str(sum(identity_skips.unattributed_by_category.values()))
            + " identity skip(s) name a category whose LCM class is not "
            "one-to-one ("
            + ", ".join(
                name + "=" + str(count) for name, count
                in identity_skips.unattributed_by_category.items()
            )
            + "), so they are counted as matches for NO class rather than "
            "guessed at. The `baseline_matched` basis is withheld from "
            + ("EVERY class (a category neither table bounds)"
               if identity_skips.unbounded else
               str(len(identity_skips.withheld))
               + " class(es) they could have been: "
               + ", ".join(sorted(identity_skips.withheld)))
            + "."
        )
    if matched_bound.unattributed_by_category:
        _warn(
            "T048f: the run report left "
            + str(sum(matched_bound.unattributed_by_category.values()))
            + " match(es) unattributed ("
            + ", ".join(
                name + "=" + str(count) for name, count
                in matched_bound.unattributed_by_category.items()
            )
            + "), so its own `complete` flag is False. The `baseline_matched` "
            "basis is withheld from "
            + ("EVERY class (a category neither table bounds)"
               if matched_bound.unbounded else
               str(len(matched_bound.withheld))
               + " class(es) those matches could have been: "
               + ", ".join(sorted(matched_bound.withheld))
               + " -- and from those only, rather than from every row")
            + "."
        )

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

    # T099: the producer's own prohibition, checked before anything is written.
    _refuse_uncorroborated_nulls(rows, census_errors)

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
        # T099: a non-empty `errors[]` is CENSUS_ERROR on its own, which is
        # what makes the reported-not-raised unresolved accessor above a
        # FAILING outcome rather than a note.
        errors=tuple(census_errors),
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
    run.add_argument(
        "--no-identity-audit", dest="identity_audit", action="store_false",
        help=("skip the T048d GUID pass over the classes with a nonzero "
              "starter baseline. The pass is what lets a class that arrives "
              "correct and is recorded NOWHERE (FW-global fixed content such "
              "as MoMorphType) reach the `baseline_matched` basis; without it "
              "those rows stay on gross subtraction and report a shortfall "
              "they do not have"))

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
            projects_root=args.projects_root,
            identity_audit=args.identity_audit)
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
