"""Feature 038 (transfer fidelity gaps) -- the census GATE test (T014).

WRITTEN BEFORE THE IMPLEMENTATION, AND EXPECTED TO FAIL ON COLLECTION until
T015-T021 land. The modules imported below do not exist yet:

- `src/gramtrans/Lib/census.py`   (T016-T020)
- `src/gramtrans/census_cli.py`   (T021)

so this module raises `ModuleNotFoundError: No module named
'gramtrans.Lib.census'` at import time. That is the correct, legible failure
for a TDD task: the test is the contract, and it fails because the contract is
not yet honoured -- not because of a path or a fixture problem. Everything else
in this file (the schema locator, the artifact builders, the fallback
validator) is exercised by the same run and must not be the thing that breaks.

WHAT THIS PINS
--------------
1. The artifact validates against
   `specs/038-transfer-fidelity-gaps/contracts/census-artifact.schema.json`.
2. The Phase 1..5 acceptance predicates of `contracts/fidelity-census.md` 9.1
   (mirrored in `quickstart.md` section 5), one test per predicate.
3. A missing or stale baseline is a FAILING VERDICT, never a warning.
   `fidelity-census.md` 5.3: "Staleness and absence are verdicts, not warnings.
   There is no path on which a missing baseline yields exit 0." The bypass
   sweep below is the point of this task: every plausible flag combination,
   including any escape hatch the CLI may grow, must exit non-zero when the
   baseline is absent -- and a forged artifact that *claims* CENSUS_CLEAN with
   `exit_code: 0` over `starter_baseline.kind == "none"` must still be refused,
   because the gate recomputes the verdict instead of trusting it.
4. The published severity ordering, which is NOT the exit-code integer and must
   not be derived from it (`fidelity-census.md` 9).
5. PASS iff the verdict is `CENSUS_CLEAN` or `CENSUS_ACCOUNTED`. There is
   deliberately no verdict meaning "loss reported, review advisable, exit
   success" (SC-010).
6. The closed 16-token reason vocabulary: no `UNEXPLAINED`, no `OTHER`, and
   exactly four tokens exempt from `report_ref`.

THE SURFACE T015-T021 MUST CREATE (this file is the specification of it)
-----------------------------------------------------------------------
`gramtrans.Lib.census`:

- `CENSUS_SCHEMA_VERSION: int`                          -- 1
- `REASON_TOKENS: tuple[str, ...] | frozenset[str]`     -- the closed 16
- `REASONS_NOT_REQUIRING_REPORT_REF: frozenset[str]`    -- the 4 exempt tokens
- `VERDICT_EXIT_CODES: Mapping[str, int]`               -- the 9 verdicts -> 0..7
- `VERDICT_HUMAN_LABELS: Mapping[str, str]`             -- console labels
- `VERDICT_SEVERITY_ORDER: tuple[str, ...]`             -- most severe FIRST
- `PASSING_VERDICTS: frozenset[str]`                    -- exactly two members
- `PHASE_PREDICATES: Mapping[int, object]`              -- keys 1..5
- `reason_requires_report_ref(reason: str) -> bool`     -- raises on an unknown token
- `exit_code_for(verdict: str) -> int`                  -- raises on an unknown token
- `is_passing_verdict(verdict: str) -> bool`
- `most_severe_verdict(verdicts: Iterable[str]) -> str`
- `recompute_verdict(artifact: dict) -> str`            -- never trusts artifact["verdict"]
- `validate_artifact(artifact: dict) -> Sequence[str]`  -- section 11 invariants; () when clean
- `evaluate_phase(artifact: dict, phase: int) -> PhaseResult`
- `gate_artifact(artifact: dict, phase: int | None = None) -> GateOutcome`
- `PhaseResult`  -- attrs `phase: int`, `satisfied: bool`, `failures: Sequence[str]`
- `GateOutcome`  -- attrs `verdict: str`, `exit_code: int`, `passed: bool`,
                    `failures: Sequence[str]`, `phase: PhaseResult | None`

`gramtrans.census_cli`:

- `SUBCOMMANDS: tuple[str, ...]` == ("capture-baseline", "run", "gate", "diff")
- `build_parser() -> argparse.ArgumentParser`
- `main(argv: Sequence[str]) -> int`   -- returns the exit code

NO LIVE PROJECT IS REQUIRED. Every artifact here is built in-memory and written
into `tmp_path`, so the module carries no `pytest.mark.integration` at module
scope on purpose (that marker means "requires the FlexTools host + a live LCM
project pair"). T024's live sanity checks land in this same file later and MUST
carry the marker individually.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
from pathlib import Path

import pytest

# Deliberately at module scope: collection must fail with a legible
# ModuleNotFoundError naming the not-yet-written census modules.
from gramtrans.Lib.census import (  # noqa: F401  (imported for the contract)
    CENSUS_SCHEMA_VERSION,
    GROSS_BASIS_CAPPED_VERDICTS,
    GROSS_BASIS_VERDICT_CAP,
    GROSS_SUBTRACTION_BASIS,
    PASSING_VERDICTS,
    PHASE_PREDICATES,
    REASON_TOKENS,
    REASONS_NOT_REQUIRING_REPORT_REF,
    VERDICT_EXIT_CODES,
    VERDICT_HUMAN_LABELS,
    VERDICT_SEVERITY_ORDER,
    evaluate_phase,
    exit_code_for,
    gate_artifact,
    is_passing_verdict,
    most_severe_verdict,
    recompute_verdict,
    gross_basis_cap_notes,
    gross_basis_suppressions,
    is_gross_basis_row,
    reason_requires_report_ref,
    row_passes,
    stamp_verdict,
    validate_artifact,
)
from gramtrans import census_cli

# ---------------------------------------------------------------------------
# Contract constants, transcribed from the authorities (NOT from memory)
# ---------------------------------------------------------------------------

# contracts/census-artifact.schema.json  $defs.reasonToken.enum
EXPECTED_REASON_TOKENS = (
    "MATCHED_EXISTING_IDENTITY",
    "MATCHED_EXISTING_NATURAL_KEY",
    "ENRICHED_EXISTING",
    "STARTER_CONTENT",
    "NO_CREATE_PATH",
    "UNSUPPORTED_SUBTYPE",
    "DEPENDENCY_UNRESOLVED",
    "DEPENDENCY_DESELECTED",
    "NOT_SELECTED",
    "UNMAPPED_WS",
    "IDENTITY_COLLISION",
    "AMBIGUOUS_NATURAL_KEY",
    "DUPLICATE_CREATED",
    "GOVERNED_BY_OTHER_FEATURE",
    "OUT_OF_SCOPE_CLASS",
    "ABSENT_BY_CONSTRUCTION",
)

# contracts/fidelity-census.md R-1 / invariant 5, and the schema's accountedLine
# $comment on report_ref.
EXPECTED_REASONS_WITHOUT_REPORT_REF = frozenset({
    "STARTER_CONTENT",
    "ABSENT_BY_CONSTRUCTION",
    "OUT_OF_SCOPE_CLASS",
    "GOVERNED_BY_OTHER_FEATURE",
})

# contracts/fidelity-census.md section 9, verdict / label / exit-code table.
EXPECTED_VERDICT_EXIT_CODES = {
    "CENSUS_CLEAN": 0,
    "CENSUS_ACCOUNTED": 0,
    "UNEXPLAINED_SHORTFALL": 1,
    "UNEXPLAINED_SURPLUS": 2,
    "DUPLICATE_IDENTITY": 3,
    "BASELINE_MISSING": 4,
    "BASELINE_STALE": 5,
    "COVERAGE_INCOMPLETE": 6,
    "CENSUS_ERROR": 7,
}

EXPECTED_VERDICT_HUMAN_LABELS = {
    "CENSUS_CLEAN": "Census clean",
    "CENSUS_ACCOUNTED": "Census accounted",
    "UNEXPLAINED_SHORTFALL": "Unexplained shortfall",
    "UNEXPLAINED_SURPLUS": "Unexplained surplus",
    "DUPLICATE_IDENTITY": "Duplicate identity",
    "BASELINE_MISSING": "Baseline missing",
    "BASELINE_STALE": "Baseline stale",
    "COVERAGE_INCOMPLETE": "Coverage incomplete",
    "CENSUS_ERROR": "Census error",
}

# contracts/fidelity-census.md section 9, "Published severity ordering", most
# severe FIRST. This is NOT the exit-code integer and MUST NOT be derived from it.
EXPECTED_SEVERITY_ORDER = (
    "CENSUS_ERROR",
    "COVERAGE_INCOMPLETE",
    "BASELINE_MISSING",
    "BASELINE_STALE",
    "DUPLICATE_IDENTITY",
    "UNEXPLAINED_SHORTFALL",
    "UNEXPLAINED_SURPLUS",
    "CENSUS_ACCOUNTED",
    "CENSUS_CLEAN",
)

EXPECTED_PASSING_VERDICTS = frozenset({"CENSUS_CLEAN", "CENSUS_ACCOUNTED"})

# contracts/fidelity-census.md 9.1 / quickstart.md section 5.
PHASE_1_CLASSES = (
    "MoStemMsa",
    "MoInflAffMsa",
    "MoDerivAffMsa",
    "MoUnclassifiedAffixMsa",
    "PartOfSpeech",
)
PHASE_2_CLASSES = ("MoInflAffixTemplate", "MoInflAffixSlot")
PHASE_4_CLASSES = ("MoAffixProcess", "MoAffixAllomorph")

# The census CLI subcommand set (recorded decision; quickstart.md section 2/3/5).
EXPECTED_SUBCOMMANDS = ("capture-baseline", "run", "gate", "diff")

# Every escape hatch a future maintainer might reach for to turn an absent
# baseline into a pass. Any of these that EXISTS must still exit non-zero.
CANDIDATE_BYPASS_FLAGS = (
    "--force",
    "--allow-missing",
    "--allow-missing-baseline",
    "--no-baseline",
    "--skip-baseline",
    "--ignore-baseline",
    "--baseline-optional",
    "--assume-empty-destination",
    "--assume-zero-baseline",
    "--warn-only",
    "--warnings-only",
    "--soft-fail",
    "--advisory",
    "--advisory-only",
    "--exit-zero",
    "--no-fail",
    "--non-strict",
)

_HEX64 = "ab" * 32


# ---------------------------------------------------------------------------
# Locating the contract, by walking up rather than by absolute path
# ---------------------------------------------------------------------------

def _repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "specs" / "038-transfer-fidelity-gaps" / "contracts").is_dir():
            return parent
    raise RuntimeError(
        "could not locate the repo root: no ancestor of "
        f"{Path(__file__).resolve()} holds "
        "specs/038-transfer-fidelity-gaps/contracts/"
    )


def _schema_path() -> Path:
    return (
        _repo_root()
        / "specs"
        / "038-transfer-fidelity-gaps"
        / "contracts"
        / "census-artifact.schema.json"
    )


@pytest.fixture(scope="module")
def census_schema() -> dict:
    path = _schema_path()
    assert path.is_file(), f"census artifact schema not found at {path}"
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Schema validation: jsonschema when available, a focused validator otherwise
# ---------------------------------------------------------------------------

def _jsonschema_errors(instance, schema) -> list[str]:
    from jsonschema import Draft202012Validator

    validator = Draft202012Validator(schema)
    return [
        "$" + "".join(f"[{p!r}]" for p in err.absolute_path) + ": " + err.message
        for err in sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))
    ]


def _type_ok(instance, names) -> bool:
    for name in names:
        if name == "null" and instance is None:
            return True
        if name == "boolean" and isinstance(instance, bool):
            return True
        if name == "integer" and isinstance(instance, int) and not isinstance(instance, bool):
            return True
        if name == "number" and isinstance(instance, (int, float)) and not isinstance(instance, bool):
            return True
        if name == "string" and isinstance(instance, str):
            return True
        if name == "array" and isinstance(instance, list):
            return True
        if name == "object" and isinstance(instance, dict):
            return True
    return False


def _structural_errors(instance, schema, root=None, path="$") -> list[str]:
    """A deliberately small validator covering exactly the JSON Schema subset
    census-artifact.schema.json uses: $ref to #/$defs, oneOf, type (scalar or
    list), enum, const, pattern, minimum/maximum, minItems, required,
    properties, additionalProperties:false, items. Used only when the
    `jsonschema` package is unavailable, so the gate test never needs a new
    dependency to run.
    """
    root = schema if root is None else root
    errors: list[str] = []

    if "$ref" in schema:
        ref = schema["$ref"]
        if not ref.startswith("#/$defs/"):
            return [f"{path}: unsupported $ref {ref!r}"]
        return _structural_errors(instance, root["$defs"][ref.split("/")[-1]], root, path)

    if "oneOf" in schema:
        branches = [_structural_errors(instance, sub, root, path) for sub in schema["oneOf"]]
        if not any(not b for b in branches):
            errors.append(f"{path}: matched none of oneOf")
        return errors

    declared = schema.get("type")
    if declared is not None:
        names = [declared] if isinstance(declared, str) else list(declared)
        if not _type_ok(instance, names):
            return [f"{path}: {type(instance).__name__} is not of type {names}"]

    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: {instance!r} is not the const {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: {instance!r} is not one of {schema['enum']}")
    if "pattern" in schema and isinstance(instance, str):
        if not re.search(schema["pattern"], instance):
            errors.append(f"{path}: {instance!r} does not match {schema['pattern']!r}")
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{path}: {instance} < minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append(f"{path}: {instance} > maximum {schema['maximum']}")

    if isinstance(instance, dict):
        for key in schema.get("required", ()):
            if key not in instance:
                errors.append(f"{path}: missing required property {key!r}")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in instance:
                if key not in props:
                    errors.append(f"{path}: unexpected property {key!r}")
        for key, sub in props.items():
            if key in instance:
                errors.extend(_structural_errors(instance[key], sub, root, f"{path}[{key!r}]"))

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append(f"{path}: {len(instance)} items < minItems {schema['minItems']}")
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(instance):
                errors.extend(_structural_errors(item, item_schema, root, f"{path}[{index}]"))

    return errors


def schema_errors(instance, schema) -> list[str]:
    try:
        import jsonschema  # noqa: F401
    except ImportError:
        return _structural_errors(instance, schema)
    return _jsonschema_errors(instance, schema)


# ---------------------------------------------------------------------------
# Artifact builders -- everything in memory, no live project
# ---------------------------------------------------------------------------

def make_report_ref(count_in_report: int = 1, kind: str = "dropped_item") -> dict:
    return {
        "kind": kind,
        "run_id": "GT-20260819-030049",
        "record_ids": ["rec-1"],
        "count_in_report": count_in_report,
    }


def make_accounted(reason: str, count: int, direction: str, *, report_ref="auto") -> dict:
    line = {"reason": reason, "count": count, "direction": direction}
    if report_ref == "auto":
        if reason not in EXPECTED_REASONS_WITHOUT_REPORT_REF:
            line["report_ref"] = make_report_ref(count)
    elif report_ref is not None:
        line["report_ref"] = report_ref
    return line


def make_row(
    object_class: str,
    *,
    source_count: int = 1,
    destination_count_total: int | None = None,
    destination_count_net: int | None = None,
    verdict_class: str = "MATCHED",
    gate_scope: str = "required",
    engine_can_create: bool = True,
    in_class_list_via: str = "coverage_floor",
    accounted_for=(),
    unexplained_shortfall: int = 0,
    unexplained_surplus: int = 0,
    duplicates_extra: int = 0,
    duplicates_groups: int = 0,
    roster_admitted: bool = True,
    match_basis: dict | None = None,
    enriched: int | None = None,
    not_evaluated_reason: str | None = None,
) -> dict:
    """One `classRow`. Defaults produce a MATCHED, duplicate-free required row
    whose arithmetic satisfies invariant 3 (difference == net - source).
    """
    total = source_count if destination_count_total is None else destination_count_total
    net = total if destination_count_net is None else destination_count_net
    row = {
        "class": object_class,
        "engine_can_create": engine_can_create,
        "gate_scope": gate_scope,
        "in_class_list_via": in_class_list_via,
        "source_count": source_count,
        "destination_count_total": total,
        "destination_count_net": net,
        "difference": net - source_count,
        "difference_raw": total - source_count,
        "verdict_class": verdict_class,
        "accounted_for": list(accounted_for),
        "unexplained_shortfall": unexplained_shortfall,
        "unexplained_surplus": unexplained_surplus,
        "duplicates": {
            "roster_admitted": roster_admitted,
            "key_definition": "Name (vernacular alt), case-sensitive",
            "groups": duplicates_groups,
            "extra_objects": duplicates_extra,
            "examples": [],
        },
    }
    if not_evaluated_reason is not None:
        row["not_evaluated_reason"] = not_evaluated_reason
    if match_basis is not None:
        row["match_basis"] = match_basis
    elif enriched is not None:
        # Section 8: identity + natural_key + created_new + unmatched_reported
        # == source_count; `enriched` is a SUBSET of the matches, not a summand.
        row["match_basis"] = {
            "identity": source_count,
            "natural_key": 0,
            "created_new": 0,
            "enriched": enriched,
            "unmatched_reported": 0,
            "ambiguous_key_reported": 0,
            "basis_source": "run_report",
        }
    return row


def make_baseline(kind: str = "pre_transfer_census", **overrides) -> dict:
    baseline = {"kind": kind}
    if kind != "none":
        baseline.update({
            "path": "specs/038-transfer-fidelity-gaps/contracts/starter-baseline.json",
            "captured_at": "2026-08-18T12:00:00",
            "project_name": "GT Starter Baseline",
            "fwdata_sha256": _HEX64,
            "flex_version": "9.2.5",
            "data_model_version": 7000072,
            "class_count": 72,
            "carries_natural_keys": True,
        })
        if kind == "pre_transfer_census":
            baseline["source_census_id"] = "CENSUS-20260819-030000"
    baseline.update(overrides)
    return baseline


def make_totals(rows) -> dict:
    required = [r for r in rows if r["gate_scope"] == "required"]
    diffs = [r["difference"] for r in required if r["difference"] is not None]
    return {
        "classes_reported": len(rows),
        "classes_matched": sum(1 for r in rows if r["verdict_class"] == "MATCHED"),
        "classes_shortfall": sum(1 for r in rows if r["verdict_class"] == "SHORTFALL"),
        "classes_surplus": sum(1 for r in rows if r["verdict_class"] == "SURPLUS"),
        "classes_not_evaluated": sum(1 for r in rows if r["verdict_class"] == "NOT_EVALUATED"),
        "total_shortfall": sum(max(0, -d) for d in diffs),
        "total_surplus": sum(max(0, d) for d in diffs),
        "unexplained_shortfall": sum(r["unexplained_shortfall"] for r in required),
        "unexplained_surplus": sum(r["unexplained_surplus"] for r in required),
        "duplicate_extra_objects": sum(
            r.get("duplicates", {}).get("extra_objects", 0)
            for r in rows
            if r.get("duplicates", {}).get("roster_admitted")
        ),
    }


def make_project(name: str, *, freshly_created: bool | None = None,
                 data_model_version: int = 7000072, digest_moved: bool = False) -> dict:
    project = {
        "name": name,
        "path": rf"C:\ProgramData\SIL\FieldWorks\Projects\{name}",
        "opened_read_only": True,
        "counted_at": "2026-08-19T03:05:00",
        "fwdata_sha256_before": _HEX64,
        "fwdata_sha256_after": ("cd" * 32) if digest_moved else _HEX64,
        "data_model_version": data_model_version,
        "object_count_total": 1000,
    }
    if freshly_created is not None:
        project["declared_freshly_created"] = freshly_created
    return project


def make_artifact(
    rows,
    *,
    baseline: dict | None = None,
    verdict: str = "CENSUS_CLEAN",
    exit_code: int | None = None,
    destination_freshly_created: bool | None = None,
    destination_data_model_version: int = 7000072,
    instrument_flex_version: str = "9.2.5",
    derivation_result: str = "match",
    with_transfer_run: bool = True,
    errors=(),
) -> dict:
    rows = list(rows)
    baseline = make_baseline() if baseline is None else baseline
    artifact = {
        "schema_version": 1,
        "census_id": "CENSUS-20260819-031500",
        "generated_at": "2026-08-19T03:15:00",
        "instrument": {
            "name": "gramtrans.census_cli",
            "version": "1.0.0",
            "gramtrans_sha": "073995d",
            "gramtrans_dirty": False,
            "flexicon_version": "4.5.2",
            "flexicon_path": r"D:\Github\_Projects\_LEX\flexicon\flexicon\__init__.py",
            "python_version": "3.11.9",
            "flex_version": instrument_flex_version,
        },
        "projects": {
            "source": make_project("Ejagham W Mini"),
            "destination": make_project(
                "Ejagham W Target",
                freshly_created=destination_freshly_created,
                data_model_version=destination_data_model_version,
            ),
        },
        "class_list_provenance": {
            "inventory_document": "specs/035-fullsweep-fidelity/object-inventory.md",
            "inventory_sha256": _HEX64,
            "coverage_floor_document": "specs/035-fullsweep-fidelity/contracts/coverage-floor.json",
            "coverage_floor_sha256": _HEX64,
            "natural_key_roster_document":
                "specs/035-fullsweep-fidelity/contracts/natural-key-identity-roster.json",
            "natural_key_roster_sha256": _HEX64,
            "derivation_check": {
                "performed": True,
                "result": derivation_result,
                "derived_class_count": len(rows),
                "in_inventory_not_in_floor": [],
                "in_floor_not_in_inventory": [],
            },
            "in_scope_class_count": len(rows),
            # Invariant 1: len(classes) == required_class_count.
            "required_class_count": len(rows),
        },
        "starter_baseline": baseline,
        "classes": rows,
        "totals": make_totals(rows),
        "verdict": verdict,
        "exit_code": EXPECTED_VERDICT_EXIT_CODES[verdict] if exit_code is None else exit_code,
        "verdict_human_label": EXPECTED_VERDICT_HUMAN_LABELS[verdict],
        "notes": [],
    }
    if with_transfer_run:
        artifact["transfer_run"] = {
            "run_id": "GT-20260819-030049",
            "mode": "MOVE",
            "report_path": "scratchpad/038_census/GT-20260819-030049-report.json",
            "started_at": "2026-08-19T03:00:49",
            "finished_at": "2026-08-19T03:04:00",
            "selected_categories": ["GRAM_CATEGORIES", "AFFIXES", "PHONOLOGY"],
        }
    if errors:
        artifact["errors"] = list(errors)
    return artifact


def phase_rows() -> list[dict]:
    """A clean row set carrying every class the Phase 1..5 predicates name."""
    rows = [make_row(cls, source_count=5) for cls in PHASE_1_CLASSES if cls != "PartOfSpeech"]
    # Phase 3 wants PartOfSpeech to have been ENRICHED, not merely matched.
    rows.append(make_row("PartOfSpeech", source_count=5, enriched=2))
    rows.append(make_row("PhPhoneme", source_count=41, destination_count_total=41,
                         duplicates_extra=0, duplicates_groups=0))
    rows.extend(make_row(cls, source_count=8) for cls in PHASE_2_CLASSES)
    rows.append(make_row("MoAffixProcess", source_count=13))
    rows.append(make_row("MoAffixAllomorph", source_count=13))
    # Owned-child classes Phase 3 enriches (FR-020's owned collections). The
    # POS-owned MoInflAffixTemplate / MoInflAffixSlot rows are already above.
    rows.extend(make_row(cls, source_count=3) for cls in
                ("MoInflClass", "MoStemName", "MoStemAllomorph", "MoMorphType"))
    return rows


def replace_row(rows, object_class: str, **changes) -> list[dict]:
    """Return `rows` with one class's row rebuilt from `changes`."""
    out = []
    for row in rows:
        if row["class"] != object_class:
            out.append(row)
            continue
        kwargs = {
            "source_count": row["source_count"],
            "destination_count_total": row["destination_count_total"],
            "destination_count_net": row["destination_count_net"],
            "verdict_class": row["verdict_class"],
            "gate_scope": row["gate_scope"],
            "accounted_for": row["accounted_for"],
            "unexplained_shortfall": row["unexplained_shortfall"],
            "unexplained_surplus": row["unexplained_surplus"],
            "duplicates_extra": row["duplicates"]["extra_objects"],
            "duplicates_groups": row["duplicates"]["groups"],
            "match_basis": row.get("match_basis"),
        }
        kwargs.update(changes)
        out.append(make_row(object_class, **kwargs))
    return out


def write_artifact(tmp_path: Path, artifact: dict, name: str = "census.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    return path


def cli_exit(argv) -> int:
    """Run the CLI and return its exit code, whether it returns or raises."""
    try:
        result = census_cli.main(list(argv))
    except SystemExit as exc:  # argparse's own exits count too
        code = exc.code
        if code is None:
            return 0
        return code if isinstance(code, int) else 1
    return 0 if result is None else int(result)


def option_strings(parser) -> set[str]:
    """Every option string the parser or any of its subparsers accepts."""
    found: set[str] = set()

    def walk(node):
        for action in getattr(node, "_actions", ()):
            found.update(getattr(action, "option_strings", ()) or ())
            choices = getattr(action, "choices", None)
            if isinstance(choices, dict):
                for sub in choices.values():
                    walk(sub)

    walk(parser)
    return found


# ===========================================================================
# 1. Schema validation
# ===========================================================================

class TestArtifactSchema:
    def test_clean_artifact_validates(self, census_schema):
        artifact = make_artifact(phase_rows())
        assert schema_errors(artifact, census_schema) == []

    def test_accounted_artifact_validates(self, census_schema):
        rows = replace_row(
            phase_rows(), "MoAffixProcess",
            destination_count_total=0, destination_count_net=0,
            verdict_class="SHORTFALL",
            accounted_for=[make_accounted("NO_CREATE_PATH", 13, "shortfall")],
        )
        artifact = make_artifact(rows, verdict="CENSUS_ACCOUNTED")
        assert schema_errors(artifact, census_schema) == []

    def test_schema_version_matches_the_implementation(self):
        assert CENSUS_SCHEMA_VERSION == 1

    def test_unknown_top_level_property_is_rejected(self, census_schema):
        artifact = make_artifact(phase_rows())
        artifact["gate_pass"] = True  # data-model.md's dataclass field name
        assert schema_errors(artifact, census_schema), (
            "the artifact is additionalProperties:false; an unknown top-level "
            "property must not validate"
        )

    def test_write_enabled_handle_cannot_validate(self, census_schema):
        """projects.*.opened_read_only is const true (section 2, READ-ONLY
        without exception)."""
        artifact = make_artifact(phase_rows())
        artifact["projects"]["destination"]["opened_read_only"] = False
        assert schema_errors(artifact, census_schema)

    def test_skipped_derivation_cannot_validate(self, census_schema):
        """derivation_check.performed is const true (CP-1): a census that
        skipped the derivation cannot make a coverage claim."""
        artifact = make_artifact(phase_rows())
        artifact["class_list_provenance"]["derivation_check"]["performed"] = False
        assert schema_errors(artifact, census_schema)

    def test_exit_code_above_seven_is_rejected(self, census_schema):
        artifact = make_artifact(phase_rows())
        artifact["exit_code"] = 8
        assert schema_errors(artifact, census_schema)

    def test_empty_classes_array_is_rejected(self, census_schema):
        """classes has minItems 1 and one row per required class (CP-2)."""
        artifact = make_artifact(phase_rows())
        artifact["classes"] = []
        assert schema_errors(artifact, census_schema)

    def test_census_id_prefix_is_pinned(self, census_schema):
        artifact = make_artifact(phase_rows())
        artifact["census_id"] = "GT-20260819-031500"
        assert schema_errors(artifact, census_schema), (
            "a census id must not be confusable with a transfer run id"
        )

    def test_validator_accepts_the_clean_artifact(self):
        """The census's own section-11 validator, not the schema."""
        assert list(validate_artifact(make_artifact(phase_rows()))) == []

    def test_validator_recomputes_the_difference(self):
        """Invariant 3: difference == destination_count_net - source_count."""
        artifact = make_artifact(phase_rows())
        artifact["classes"][0]["difference"] = 0
        artifact["classes"][0]["destination_count_net"] = 3
        artifact["classes"][0]["source_count"] = 5
        assert list(validate_artifact(artifact)), (
            "a stored difference inconsistent with the counts must be reported"
        )

    def test_validator_rejects_a_missing_class_row(self):
        """Invariant 1: len(classes) == required_class_count."""
        artifact = make_artifact(phase_rows())
        artifact["class_list_provenance"]["required_class_count"] = len(artifact["classes"]) + 1
        assert list(validate_artifact(artifact))

    def test_validator_rejects_a_moved_project_digest(self):
        """Invariant 7: before == after for both projects."""
        artifact = make_artifact(phase_rows())
        artifact["projects"]["destination"] = make_project("Ejagham W Target", digest_moved=True)
        assert list(validate_artifact(artifact))
        assert recompute_verdict(artifact) == "CENSUS_ERROR"

    def test_validator_rejects_over_accounting(self):
        """R-2: a per-direction sum exceeding the difference is CENSUS_ERROR."""
        rows = replace_row(
            phase_rows(), "MoAffixProcess",
            destination_count_total=0, destination_count_net=0,
            verdict_class="SHORTFALL",
            accounted_for=[make_accounted("NO_CREATE_PATH", 20, "shortfall")],
        )
        artifact = make_artifact(rows, verdict="CENSUS_ACCOUNTED")
        assert list(validate_artifact(artifact))
        assert recompute_verdict(artifact) == "CENSUS_ERROR"

    def test_validator_rejects_a_line_the_report_does_not_carry(self):
        """R-1: count_in_report >= count, else CENSUS_ERROR -- a line claiming
        13 against a report naming 2 is not accounting."""
        rows = replace_row(
            phase_rows(), "MoAffixProcess",
            destination_count_total=0, destination_count_net=0,
            verdict_class="SHORTFALL",
            accounted_for=[make_accounted("NO_CREATE_PATH", 13, "shortfall",
                                          report_ref=make_report_ref(2))],
        )
        artifact = make_artifact(rows, verdict="CENSUS_ACCOUNTED")
        assert list(validate_artifact(artifact))
        assert recompute_verdict(artifact) == "CENSUS_ERROR"

    def test_validator_rejects_a_match_basis_that_does_not_sum(self):
        """Invariant 11 / section 8: identity + natural_key + created_new +
        unmatched_reported == source_count, with `enriched` excluded."""
        artifact = make_artifact(phase_rows())
        pos = next(r for r in artifact["classes"] if r["class"] == "PartOfSpeech")
        pos["match_basis"]["identity"] = 1  # source_count is 5
        assert list(validate_artifact(artifact))

    def test_validator_rejects_cross_class_netting(self):
        """Section 4 / R-3: MoAffixProcess -13 against MoAffixAllomorph +13 is
        two failures, not zero. Neither row may be accounted by the other."""
        rows = phase_rows()
        rows = replace_row(rows, "MoAffixProcess", destination_count_total=0,
                           destination_count_net=0, verdict_class="SHORTFALL",
                           unexplained_shortfall=13)
        rows = replace_row(rows, "MoAffixAllomorph", destination_count_total=26,
                           destination_count_net=26, verdict_class="SURPLUS",
                           unexplained_surplus=13)
        artifact = make_artifact(rows, verdict="UNEXPLAINED_SHORTFALL")
        assert artifact["totals"]["total_shortfall"] == 13
        assert artifact["totals"]["total_surplus"] == 13
        assert recompute_verdict(artifact) == "UNEXPLAINED_SHORTFALL"
        assert not gate_artifact(artifact).passed


# ===========================================================================
# 2. Phase predicates P1..P5 (contracts/fidelity-census.md 9.1)
# ===========================================================================

class TestPhasePredicates:
    def test_all_five_phases_are_declared(self):
        assert set(PHASE_PREDICATES) == {1, 2, 3, 4, 5}

    # -- P1 ---------------------------------------------------------------
    def test_p1_identity_predicate_holds(self):
        """P1: 'MoStemMsa, MoInflAffMsa, MoDerivAffMsa,
        MoUnclassifiedAffixMsa, PartOfSpeech rows MATCHED;
        PhPhoneme.duplicates.extra_objects == 0.' (SC-001, SC-002)"""
        result = evaluate_phase(make_artifact(phase_rows()), 1)
        assert result.satisfied, f"P1 should hold: {list(result.failures)}"

    @pytest.mark.parametrize("lost_class", PHASE_1_CLASSES)
    def test_p1_fails_when_any_msa_or_pos_class_is_not_matched(self, lost_class):
        rows = replace_row(phase_rows(), lost_class, destination_count_total=0,
                           destination_count_net=0, verdict_class="SHORTFALL",
                           unexplained_shortfall=5)
        result = evaluate_phase(make_artifact(rows, verdict="UNEXPLAINED_SHORTFALL"), 1)
        assert not result.satisfied
        assert any(lost_class in f for f in result.failures), (
            "the predicate must name the class it failed on"
        )

    def test_p1_fails_on_duplicate_phonemes_even_at_difference_zero(self):
        """The measured PhPhoneme row: difference 0, verdict_class MATCHED, and
        21 duplicate names. Baseline arithmetic cannot see a duplicate, so a
        gate built on counts alone would pass the worst phoneme outcome."""
        rows = replace_row(phase_rows(), "PhPhoneme", duplicates_extra=21,
                           duplicates_groups=21)
        artifact = make_artifact(rows, verdict="DUPLICATE_IDENTITY")
        row = next(r for r in artifact["classes"] if r["class"] == "PhPhoneme")
        assert row["difference"] == 0 and row["verdict_class"] == "MATCHED"
        result = evaluate_phase(artifact, 1)
        assert not result.satisfied
        assert recompute_verdict(artifact) == "DUPLICATE_IDENTITY"
        assert not gate_artifact(artifact, phase=1).passed

    # -- P2 ---------------------------------------------------------------
    def test_p2_closure_predicate_holds(self):
        """P2: 'MoInflAffixTemplate and MoInflAffixSlot rows MATCHED.' (SC-004)"""
        result = evaluate_phase(make_artifact(phase_rows()), 2)
        assert result.satisfied, f"P2 should hold: {list(result.failures)}"

    @pytest.mark.parametrize("lost_class", PHASE_2_CLASSES)
    def test_p2_fails_when_a_template_or_slot_row_is_lost(self, lost_class):
        rows = replace_row(phase_rows(), lost_class, destination_count_total=0,
                           destination_count_net=0, verdict_class="SHORTFALL",
                           unexplained_shortfall=8)
        result = evaluate_phase(make_artifact(rows, verdict="UNEXPLAINED_SHORTFALL"), 2)
        assert not result.satisfied
        assert any(lost_class in f for f in result.failures)

    # -- P3 ---------------------------------------------------------------
    def test_p3_enrichment_predicate_holds(self):
        """P3: 'match_basis.enriched > 0 on PartOfSpeech, and the owned-child
        classes MATCHED.' (SC-007)"""
        result = evaluate_phase(make_artifact(phase_rows()), 3)
        assert result.satisfied, f"P3 should hold: {list(result.failures)}"

    def test_p3_fails_when_nothing_was_enriched(self):
        """A whole-object SKIP decided by GUID presence alone (defect G3) shows
        up here as enriched == 0 with everything still MATCHED."""
        rows = replace_row(phase_rows(), "PartOfSpeech",
                           match_basis={
                               "identity": 5, "natural_key": 0, "created_new": 0,
                               "enriched": 0, "unmatched_reported": 0,
                               "basis_source": "run_report",
                           })
        result = evaluate_phase(make_artifact(rows), 3)
        assert not result.satisfied
        assert any("enrich" in f.lower() for f in result.failures)

    def test_p3_fails_when_an_owned_child_class_is_lost(self):
        rows = replace_row(phase_rows(), "MoStemAllomorph",
                           destination_count_total=0, destination_count_net=0,
                           verdict_class="SHORTFALL", unexplained_shortfall=3)
        result = evaluate_phase(make_artifact(rows, verdict="UNEXPLAINED_SHORTFALL"), 3)
        assert not result.satisfied

    # -- P4 ---------------------------------------------------------------
    def test_p4_process_rule_predicate_holds(self):
        """P4: 'MoAffixProcess MATCHED and MoAffixAllomorph difference == 0 --
        both, because either alone can be satisfied by the defect itself.'
        (SC-006)"""
        result = evaluate_phase(make_artifact(phase_rows()), 4)
        assert result.satisfied, f"P4 should hold: {list(result.failures)}"

    def test_p4_fails_on_the_measured_downgrade(self):
        """The measured run turned 13 MoAffixProcess into 13 extra
        MoAffixAllomorph. Checking either half alone would pass a downgrade."""
        rows = phase_rows()
        rows = replace_row(rows, "MoAffixProcess", destination_count_total=0,
                           destination_count_net=0, verdict_class="SHORTFALL",
                           unexplained_shortfall=13)
        rows = replace_row(rows, "MoAffixAllomorph", destination_count_total=26,
                           destination_count_net=26, verdict_class="SURPLUS",
                           unexplained_surplus=13)
        result = evaluate_phase(make_artifact(rows, verdict="UNEXPLAINED_SHORTFALL"), 4)
        assert not result.satisfied
        assert any("MoAffixProcess" in f for f in result.failures)
        assert any("MoAffixAllomorph" in f for f in result.failures)

    def test_p4_fails_when_only_the_allomorph_half_holds(self):
        rows = replace_row(phase_rows(), "MoAffixProcess",
                           destination_count_total=0, destination_count_net=0,
                           verdict_class="SHORTFALL", unexplained_shortfall=13)
        result = evaluate_phase(make_artifact(rows, verdict="UNEXPLAINED_SHORTFALL"), 4)
        assert not result.satisfied

    def test_p4_fails_when_only_the_process_half_holds(self):
        rows = replace_row(phase_rows(), "MoAffixAllomorph",
                           destination_count_total=26, destination_count_net=26,
                           verdict_class="SURPLUS", unexplained_surplus=13)
        result = evaluate_phase(make_artifact(rows, verdict="UNEXPLAINED_SURPLUS"), 4)
        assert not result.satisfied

    # -- P5 ---------------------------------------------------------------
    def test_p5_residual_predicate_holds_with_a_valid_accounting_line(self):
        """P5: 'Every remaining required row is either MATCHED or carries a
        valid GOVERNED_BY_OTHER_FEATURE / NO_CREATE_PATH line.' (SC-005)"""
        rows = replace_row(
            phase_rows(), "MoMorphType",
            destination_count_total=0, destination_count_net=0,
            verdict_class="SHORTFALL",
            accounted_for=[make_accounted("NO_CREATE_PATH", 3, "shortfall")],
        )
        artifact = make_artifact(rows, verdict="CENSUS_ACCOUNTED")
        result = evaluate_phase(artifact, 5)
        assert result.satisfied, f"P5 should hold: {list(result.failures)}"
        assert gate_artifact(artifact, phase=5).passed

    def test_p5_fails_when_a_shortfall_carries_no_line(self):
        """R-5: absence of an accounted_for list is not an excuse."""
        rows = replace_row(phase_rows(), "MoMorphType", destination_count_total=0,
                           destination_count_net=0, verdict_class="SHORTFALL",
                           accounted_for=[], unexplained_shortfall=3)
        artifact = make_artifact(rows, verdict="UNEXPLAINED_SHORTFALL")
        result = evaluate_phase(artifact, 5)
        assert not result.satisfied
        assert not gate_artifact(artifact, phase=5).passed

    def test_p5_rejects_a_reason_outside_the_two_admissible_tokens(self):
        """P5 admits GOVERNED_BY_OTHER_FEATURE / NO_CREATE_PATH only. A
        DUPLICATE_CREATED line is real accounting but is not phase-5 done."""
        rows = replace_row(
            phase_rows(), "MoMorphType",
            destination_count_total=6, destination_count_net=6,
            verdict_class="SURPLUS",
            accounted_for=[make_accounted("DUPLICATE_CREATED", 3, "surplus")],
        )
        result = evaluate_phase(make_artifact(rows, verdict="CENSUS_ACCOUNTED"), 5)
        assert not result.satisfied

    def test_a_phase_is_done_only_when_the_run_also_exits_zero(self):
        """'A phase is not done when its unit tests pass; it is done when the
        census run for its predicate exits 0 with the predicate satisfied.'
        Here P1 holds but the baseline is absent, so the phase is NOT done."""
        artifact = make_artifact(phase_rows(), baseline=make_baseline("none"),
                                 verdict="BASELINE_MISSING")
        assert evaluate_phase(artifact, 1).satisfied
        outcome = gate_artifact(artifact, phase=1)
        assert outcome.exit_code != 0
        assert not outcome.passed


# ===========================================================================
# 3. Baseline absence and staleness are VERDICTS, not warnings
# ===========================================================================

class TestBaselineIsAFailingVerdict:
    def test_missing_baseline_is_baseline_missing_with_exit_four(self):
        """fidelity-census.md 5.3: kind 'none' -> BASELINE_MISSING, exit 4. The
        artifact is still complete; it just must not report a pass."""
        artifact = make_artifact(phase_rows(), baseline=make_baseline("none"),
                                 verdict="BASELINE_MISSING")
        assert recompute_verdict(artifact) == "BASELINE_MISSING"
        outcome = gate_artifact(artifact)
        assert outcome.verdict == "BASELINE_MISSING"
        assert outcome.exit_code == 4
        assert not outcome.passed

    def test_missing_baseline_is_never_a_substituted_zero(self):
        """'MUST NOT substitute zero for the baseline. A zero baseline is a
        claim that the destination shipped empty.'"""
        artifact = make_artifact(phase_rows(), baseline=make_baseline("none"),
                                 verdict="BASELINE_MISSING")
        for row in artifact["classes"]:
            assert row.get("starter_baseline_source") != "assumed_zero_not_permitted"
        assert recompute_verdict(artifact) != "CENSUS_CLEAN"

    def test_a_forged_clean_verdict_over_no_baseline_is_still_refused(self):
        """The gate RECOMPUTES; it does not trust artifact['verdict'] or
        artifact['exit_code']. This is the bypass an artifact could otherwise
        buy by simply writing 0 into the file."""
        artifact = make_artifact(phase_rows(), baseline=make_baseline("none"),
                                 verdict="CENSUS_CLEAN", exit_code=0)
        assert artifact["verdict"] == "CENSUS_CLEAN" and artifact["exit_code"] == 0
        assert recompute_verdict(artifact) == "BASELINE_MISSING"
        outcome = gate_artifact(artifact)
        assert outcome.exit_code == 4
        assert not outcome.passed
        assert list(validate_artifact(artifact)), (
            "invariant 8: verdict and exit_code must agree with the section 9 "
            "table and with the most severe applicable token"
        )

    @pytest.mark.parametrize("stale_shape,overrides,artifact_kwargs", [
        ("explicit staleness marker",
         {"staleness": {"verdict": "stale", "detail": "captured under FLEx 9.1.24"}},
         {}),
        ("flex_version differs from the running FieldWorks",
         {"flex_version": "9.1.24"},
         {"instrument_flex_version": "9.2.5"}),
        ("destination data_model_version exceeds the baseline's",
         {"data_model_version": 7000072},
         {"destination_data_model_version": 7000073}),
    ])
    def test_stale_baseline_is_baseline_stale_with_exit_five(
            self, stale_shape, overrides, artifact_kwargs):
        """fidelity-census.md 5.3: 'A baseline is stale when the destination's
        data_model_version exceeds the baseline's, or the recorded flex_version
        differs from the running FieldWorks version. Verdict BASELINE_STALE,
        exit 5.'"""
        baseline = make_baseline("starter_capture", **overrides)
        artifact = make_artifact(phase_rows(), baseline=baseline,
                                 verdict="BASELINE_STALE",
                                 destination_freshly_created=True,
                                 **artifact_kwargs)
        assert recompute_verdict(artifact) == "BASELINE_STALE", stale_shape
        outcome = gate_artifact(artifact)
        assert outcome.exit_code == 5, stale_shape
        assert not outcome.passed, stale_shape

    def test_starter_capture_against_an_undeclared_destination_is_census_error(self):
        """5.3 mis-declared: a starter_capture baseline used against a
        destination the operator did not declare freshly created. An edited
        starter inventory is not disposable."""
        artifact = make_artifact(phase_rows(), baseline=make_baseline("starter_capture"),
                                 verdict="CENSUS_ERROR",
                                 destination_freshly_created=False)
        assert recompute_verdict(artifact) == "CENSUS_ERROR"
        assert gate_artifact(artifact).exit_code == 7

    def test_no_baseline_subtraction_basis_cannot_pass(self):
        """5.2's table: 'no_baseline: net = total; the run cannot pass.'"""
        rows = phase_rows()
        for row in rows:
            row["starter_subtraction_basis"] = "no_baseline"
            row["starter_baseline_source"] = "absent_from_baseline"
        artifact = make_artifact(rows, baseline=make_baseline("none"),
                                 verdict="BASELINE_MISSING")
        assert not gate_artifact(artifact).passed

    # -- the point of T014: prove there is no bypass ----------------------
    def test_no_flag_combination_yields_exit_zero_without_a_baseline(self, tmp_path):
        """'There is no path on which a missing baseline yields exit 0.'

        Every plausible invocation of the gate over a baseline-less artifact
        must be non-zero -- including any escape-hatch flag the CLI grows. A
        flag that does not exist cannot be a bypass; a flag that DOES exist is
        exercised and must still fail.
        """
        artifact = make_artifact(phase_rows(), baseline=make_baseline("none"),
                                 verdict="BASELINE_MISSING")
        honest = write_artifact(tmp_path, artifact, "no-baseline.json")
        # ... and the same artifact lying about its own verdict.
        forged = write_artifact(
            tmp_path,
            make_artifact(phase_rows(), baseline=make_baseline("none"),
                          verdict="CENSUS_CLEAN", exit_code=0),
            "no-baseline-forged.json",
        )

        base_invocations = []
        for path in (honest, forged):
            base_invocations.append(["gate", "--artifact", str(path)])
            for phase in (1, 2, 3, 4, 5):
                base_invocations.append(
                    ["gate", "--artifact", str(path), "--phase", str(phase)])

        known = option_strings(census_cli.build_parser())
        escape_hatches = [f for f in CANDIDATE_BYPASS_FLAGS if f in known]

        invocations = list(base_invocations)
        for flag in escape_hatches:
            for argv in base_invocations:
                invocations.append(argv + [flag])

        failures = [argv for argv in invocations if cli_exit(argv) == 0]
        assert failures == [], (
            "these invocations exited 0 over an absent baseline, which "
            f"fidelity-census.md 5.3 forbids: {failures}"
        )

    def test_no_flag_combination_yields_exit_zero_on_a_stale_baseline(self, tmp_path):
        artifact = make_artifact(
            phase_rows(),
            baseline=make_baseline("starter_capture", flex_version="9.1.24"),
            verdict="BASELINE_STALE",
            destination_freshly_created=True,
            instrument_flex_version="9.2.5",
        )
        path = write_artifact(tmp_path, artifact, "stale-baseline.json")
        known = option_strings(census_cli.build_parser())
        invocations = [["gate", "--artifact", str(path)]]
        invocations += [["gate", "--artifact", str(path), "--phase", str(p)]
                       for p in (1, 2, 3, 4, 5)]
        invocations += [argv + [flag]
                        for flag in CANDIDATE_BYPASS_FLAGS if flag in known
                        for argv in list(invocations)]
        failures = [argv for argv in invocations if cli_exit(argv) == 0]
        assert failures == [], f"stale baseline exited 0 for: {failures}"

    def test_gate_over_a_baseline_bearing_artifact_can_still_pass(self, tmp_path):
        """The counterweight: the bypass sweep above must be failing for the
        RIGHT reason (no baseline), not because the gate refuses everything."""
        path = write_artifact(tmp_path, make_artifact(phase_rows()), "clean.json")
        assert cli_exit(["gate", "--artifact", str(path)]) == 0
        assert cli_exit(["gate", "--artifact", str(path), "--phase", "1"]) == 0



# ===========================================================================
# 3b. T023a -- 5.2's GROSS-BASIS VERDICT CAP
#
# `fidelity-census.md:251`: on `baseline_gross`, "every row is advisory for
# SHORTFALL purposes and the run verdict cannot exceed `CENSUS_ACCOUNTED`".
# `census-artifact.schema.json:408` says the same: "caps the run verdict at
# CENSUS_ACCOUNTED".
#
# This is not leniency. Gross subtraction subtracts the WHOLE baseline count, so
# a starter object the transfer correctly matched is subtracted twice -- once as
# a starter object and once as the source object it stands in for. 5.2's own
# worked example is a 21-object shortfall reported on a run that lost nothing.
# And `census-artifact.schema.json:337` makes this the NORMAL path: "a
# count-only baseline forces starter_subtraction_basis 'baseline_gross'", which
# every whole-project baseline is, because a blank FieldWorks project holds
# objects in 11 classes that carry no name to key on at all.
# ===========================================================================

def gross_basis_rows(rows=None, *, phoneme_baseline=23):
    """`rows` (default `phase_rows()`) rewritten as a no-run-report census: no
    `starter_matched_to_source`, gross subtraction, no match_basis tallies."""
    rows = list(phase_rows() if rows is None else rows)
    for row in rows:
        row["starter_baseline_count"] = (
            phoneme_baseline if row["class"] == "PhPhoneme" else 0)
        row["starter_matched_to_source"] = None
        row["starter_subtraction_basis"] = GROSS_SUBTRACTION_BASIS
        row["starter_baseline_source"] = "baseline_document"
        row["match_basis"] = {"basis_source": "unavailable"}
    return rows


def five_two_worked_example_rows():
    """fidelity-census.md 5.2's FIXED run, verbatim: "21 starter phonemes
    matched by name, 20 new created, destination total 43. Gross subtraction
    gives 43 - 23 = 20, so `difference` **-21** -- a shortfall reported on a
    *correct* run."
    """
    rows = replace_row(phase_rows(), "PartOfSpeech", source_count=5)
    rows = replace_row(
        rows, "PhPhoneme",
        source_count=41,               # the source's 41 phonemes
        destination_count_total=43,    # 21 matched starters + 20 created + 2 left
        destination_count_net=20,      # GROSS: 43 - 23
        verdict_class="SHORTFALL",
        unexplained_shortfall=21,      # difference -21, and no line explains it
    )
    return gross_basis_rows(rows)


def gross_basis_artifact(rows=None, **overrides):
    """A stamped artifact over gross-basis rows. A `starter_capture` baseline
    with `carries_natural_keys` False is exactly what forces the gross basis,
    and an absent `transfer_run` is the condition 5.2's table names."""
    overrides.setdefault("baseline", make_baseline(
        "starter_capture", carries_natural_keys=False))
    overrides.setdefault("destination_freshly_created", True)
    overrides.setdefault("with_transfer_run", False)
    artifact = make_artifact(
        five_two_worked_example_rows() if rows is None else rows, **overrides)
    return stamp_verdict(artifact)


class TestGrossBasisVerdictCap:
    def test_the_cap_constants_match_the_contract(self):
        assert GROSS_SUBTRACTION_BASIS == "baseline_gross"
        assert GROSS_BASIS_VERDICT_CAP == "CENSUS_ACCOUNTED"
        # The cap suppresses exactly the two tokens BELOW the ceiling and above
        # CENSUS_CLEAN, and nothing above the ceiling.
        assert set(GROSS_BASIS_CAPPED_VERDICTS) == {
            "UNEXPLAINED_SHORTFALL", "UNEXPLAINED_SURPLUS"}
        order = list(VERDICT_SEVERITY_ORDER)
        cap = order.index(GROSS_BASIS_VERDICT_CAP)
        for token in GROSS_BASIS_CAPPED_VERDICTS:
            assert order.index(token) < cap
            assert order.index(token) < order.index("CENSUS_CLEAN")

    def test_the_basis_is_a_row_property_in_the_schema(self, census_schema):
        """Granularity: `starter_subtraction_basis` lives on `$defs.classRow`,
        while the cap sentence speaks of the RUN verdict. The two agree because
        an absent report forces the gross basis on EVERY row."""
        row_props = census_schema["$defs"]["classRow"]["properties"]
        assert "starter_subtraction_basis" in row_props
        assert GROSS_SUBTRACTION_BASIS in row_props[
            "starter_subtraction_basis"]["enum"]
        assert "starter_subtraction_basis" not in census_schema["properties"]

    def test_the_five_two_worked_example_reports_accounted_not_shortfall(self):
        """THE HEADLINE. 5.2: source 41, destination 43, starter 23, gross
        43 - 23 = 20, difference -21 -- "a shortfall reported on a *correct*
        run". Uncapped, this correct transfer exits 1."""
        artifact = gross_basis_artifact()
        row = [r for r in artifact["classes"] if r["class"] == "PhPhoneme"][0]
        assert row["destination_count_net"] == 43 - 23 == 20
        assert row["difference"] == -21
        assert row["unexplained_shortfall"] == 21

        assert recompute_verdict(artifact) == "CENSUS_ACCOUNTED"
        outcome = gate_artifact(artifact)
        assert outcome.exit_code == 0
        assert outcome.passed
        assert list(validate_artifact(artifact)) == []

    def test_the_same_shortfall_on_the_matched_basis_still_fails(self):
        """The counterweight: the cap must be doing its work because of the
        BASIS, not because the gate stopped noticing shortfalls at all."""
        rows = five_two_worked_example_rows()
        for row in rows:
            if row["class"] == "PhPhoneme":
                # invariant 4: net == total - (baseline - matched) == 43 - 23.
                row["starter_subtraction_basis"] = "baseline_matched"
                row["starter_matched_to_source"] = 0
        artifact = make_artifact(
            rows, baseline=make_baseline("starter_capture"),
            destination_freshly_created=True, with_transfer_run=False,
            verdict="UNEXPLAINED_SHORTFALL")
        assert recompute_verdict(artifact) == "UNEXPLAINED_SHORTFALL"
        assert gate_artifact(artifact).exit_code == 1

    def test_one_matched_basis_row_still_fails_a_mostly_gross_artifact(self):
        """Granularity, decided conservatively: the suppression is PER ROW, so a
        `baseline_matched` row's shortfall -- which IS trustworthy evidence --
        still fails the run alongside gross-basis rows. One gross-basis row caps
        only its own contribution, never the whole artifact."""
        rows = five_two_worked_example_rows()
        for row in rows:
            if row["class"] == "MoStemMsa":
                row["starter_subtraction_basis"] = "baseline_matched"
                row["starter_matched_to_source"] = 0
                row["destination_count_total"] = 3
                row["destination_count_net"] = 3
                row["difference"] = 3 - row["source_count"]
                row["difference_raw"] = 3 - row["source_count"]
                row["verdict_class"] = "SHORTFALL"
                row["unexplained_shortfall"] = row["source_count"] - 3
        artifact = make_artifact(
            rows, baseline=make_baseline("starter_capture",
                                         carries_natural_keys=False),
            destination_freshly_created=True, with_transfer_run=False,
            verdict="UNEXPLAINED_SHORTFALL")
        assert recompute_verdict(artifact) == "UNEXPLAINED_SHORTFALL"
        assert gate_artifact(artifact).exit_code == 1

    def test_a_row_declaring_no_basis_is_not_capped(self):
        """The cap is a claim the artifact must MAKE, never a default: a row
        carrying no `starter_subtraction_basis` at all keeps failing."""
        rows = five_two_worked_example_rows()
        for row in rows:
            row.pop("starter_subtraction_basis", None)
        assert not any(is_gross_basis_row(r) for r in rows)
        artifact = make_artifact(
            rows, baseline=make_baseline("starter_capture"),
            destination_freshly_created=True, with_transfer_run=False,
            verdict="UNEXPLAINED_SHORTFALL")
        assert recompute_verdict(artifact) == "UNEXPLAINED_SHORTFALL"

    @pytest.mark.parametrize("verdict,mutate", [
        ("CENSUS_ERROR", lambda kw: kw.update(errors=[{
            "code": "UNHANDLED_EXCEPTION", "message": "boom"}])),
        ("COVERAGE_INCOMPLETE", lambda kw: kw.update(
            derivation_result="mismatch")),
        ("BASELINE_MISSING", lambda kw: kw.update(
            baseline=make_baseline("none"))),
        ("BASELINE_STALE", lambda kw: kw.update(
            baseline=make_baseline("starter_capture",
                                   carries_natural_keys=False,
                                   data_model_version=7000070),
            destination_data_model_version=7000072)),
    ])
    def test_every_more_severe_verdict_still_beats_the_cap(self, verdict, mutate):
        """'Capped' is a CEILING, not a floor. Every token above
        CENSUS_ACCOUNTED in the published ordering still wins, which is why
        5.3's "there is no path on which a missing baseline yields exit 0"
        survives the cap verbatim."""
        kwargs = {}
        mutate(kwargs)
        artifact = gross_basis_artifact(**kwargs)
        assert recompute_verdict(artifact) == verdict
        outcome = gate_artifact(artifact)
        assert outcome.exit_code == EXPECTED_VERDICT_EXIT_CODES[verdict]
        assert not outcome.passed

    def test_duplicate_identity_still_beats_the_cap(self):
        """Section 6 is "not optional" on the gross basis either: baseline
        arithmetic cannot see a duplicate, so the cap must not hide one."""
        rows = five_two_worked_example_rows()
        for row in rows:
            if row["class"] == "PhPhoneme":
                row["duplicates"] = dict(
                    row["duplicates"], groups=21, extra_objects=21,
                    examples=[{"key": "k%d" % i, "count": 2, "guids": []}
                              for i in range(21)])
        artifact = gross_basis_artifact(rows)
        assert recompute_verdict(artifact) == "DUPLICATE_IDENTITY"
        assert gate_artifact(artifact).exit_code == 3

    def test_a_missing_baseline_over_gross_rows_is_still_exit_four(self, tmp_path):
        """5.3's bypass sweep, narrowed to the cap: no flag combination may let
        the gross basis turn an absent baseline into exit 0."""
        artifact = make_artifact(five_two_worked_example_rows(),
                                 baseline=make_baseline("none"),
                                 with_transfer_run=False,
                                 verdict="BASELINE_MISSING")
        path = write_artifact(tmp_path, artifact, "gross-no-baseline.json")
        known = option_strings(census_cli.build_parser())
        invocations = [["gate", "--artifact", str(path)]]
        invocations += [["gate", "--artifact", str(path), "--phase", str(p)]
                        for p in (1, 2, 3, 4, 5)]
        invocations += [argv + [flag]
                        for flag in CANDIDATE_BYPASS_FLAGS if flag in known
                        for argv in list(invocations)]
        zeros = [argv for argv in invocations if cli_exit(argv) == 0]
        assert zeros == [], f"gross basis bought exit 0 with no baseline: {zeros}"

    def test_census_clean_is_not_reachable_by_capping(self):
        """The cap's ceiling is CENSUS_ACCOUNTED. A suppressed 21-object
        shortfall must never read as "nothing needed explaining"."""
        artifact = gross_basis_artifact()
        assert recompute_verdict(artifact) != "CENSUS_CLEAN"
        assert gross_basis_suppressions(artifact) == (
            ("PhPhoneme", "shortfall", 21),)

    def test_a_genuinely_clean_gross_basis_run_is_still_census_clean(self):
        """...and the floor is not a blanket downgrade either: a gross-basis run
        with nothing to explain keeps CENSUS_CLEAN on its own merits."""
        artifact = gross_basis_artifact(gross_basis_rows())
        assert gross_basis_suppressions(artifact) == ()
        assert recompute_verdict(artifact) == "CENSUS_CLEAN"
        assert gate_artifact(artifact).passed
        assert artifact.get("notes") == []

    def test_the_cap_is_visible_in_the_artifact(self):
        """A capped CENSUS_ACCOUNTED must SAY it was capped, so nobody reads it
        as "no shortfall found". The carrier is the schema's `notes` array --
        the document is `additionalProperties: false` throughout and offers no
        verdict-annotation property to add without a breaking change."""
        artifact = gross_basis_artifact()
        notes = artifact["notes"]
        assert notes, "a capped verdict with no note is a silent cap"
        blob = " ".join(notes)
        assert "CAPPED" in blob
        assert GROSS_BASIS_VERDICT_CAP in blob
        assert GROSS_SUBTRACTION_BASIS in blob
        assert "PhPhoneme" in blob and "21" in blob
        assert "5.2" in blob
        assert tuple(notes) == gross_basis_cap_notes(artifact)

    def test_the_capped_artifact_still_validates_against_the_schema(
            self, census_schema):
        assert schema_errors(gross_basis_artifact(), census_schema) == []

    def test_stamping_twice_does_not_duplicate_the_notes(self):
        artifact = gross_basis_artifact()
        first = list(artifact["notes"])
        stamp_verdict(artifact)
        stamp_verdict(artifact)
        assert artifact["notes"] == first

    def test_no_verdict_depends_on_a_note(self):
        """Invariant 9: notes are reportage. Deleting them must not change the
        verdict -- the cap reads `starter_subtraction_basis`, never a note --
        and a hand-written note must not BUY a cap."""
        artifact = gross_basis_artifact()
        with_notes = recompute_verdict(artifact)
        artifact["notes"] = []
        assert recompute_verdict(artifact) == with_notes

        forged = make_artifact(
            replace_row(phase_rows(), "PhPhoneme", source_count=41,
                        destination_count_total=20, destination_count_net=20,
                        verdict_class="SHORTFALL", unexplained_shortfall=21),
            verdict="UNEXPLAINED_SHORTFALL")
        forged["notes"] = list(gross_basis_cap_notes(gross_basis_artifact()))
        assert recompute_verdict(forged) == "UNEXPLAINED_SHORTFALL"

    def test_the_cap_does_not_relax_row_passes_or_the_phase_predicates(self):
        """5.2 caps "the RUN verdict". A phase declaring itself DONE needs
        trustworthy evidence and gross-basis arithmetic is by construction not
        that, so `census gate --phase N` still refuses what the run verdict now
        passes."""
        artifact = gross_basis_artifact()
        row = [r for r in artifact["classes"] if r["class"] == "PhPhoneme"][0]
        assert row_passes(row) is False
        phase_5 = evaluate_phase(artifact, 5)
        assert not phase_5.satisfied
        assert any("PhPhoneme" in f for f in phase_5.failures)
        assert not gate_artifact(artifact, phase=5).passed

    def test_recompute_still_ignores_a_forged_verdict_on_a_capped_artifact(self):
        artifact = gross_basis_artifact()
        artifact["verdict"] = "CENSUS_CLEAN"
        artifact["exit_code"] = 0
        assert recompute_verdict(artifact) == "CENSUS_ACCOUNTED"

    def test_a_gross_basis_surplus_is_capped_the_same_way(self):
        """`UNEXPLAINED_SURPLUS` sits below `CENSUS_ACCOUNTED` in the ordering
        exactly as the shortfall does. Gross subtraction over-subtracts, so it
        manufactures shortfalls rather than surpluses -- but 5.2's table caps on
        the BASIS, not on the sign, and a one-sided cap would be a second rule
        free to drift from the first."""
        rows = gross_basis_rows(replace_row(
            phase_rows(), "MoInflClass", source_count=3,
            destination_count_total=9, destination_count_net=9,
            verdict_class="SURPLUS", unexplained_surplus=6))
        artifact = gross_basis_artifact(rows)
        assert gross_basis_suppressions(artifact) == (
            ("MoInflClass", "surplus", 6),)
        assert recompute_verdict(artifact) == "CENSUS_ACCOUNTED"
        assert gate_artifact(artifact).exit_code == 0


# ===========================================================================
# 3b. T023c -- the cap must be VISIBLE where people actually look
#
# T023a made a capped verdict visible IN THE ARTIFACT (`notes`). Neither
# console surface rendered `notes` at all, so a capped `CENSUS_ACCOUNTED` /
# exit 0 printed identically to a run that lost nothing -- the exact silence
# the cap's own warning text exists to break. These tests pin the RENDERING on
# both surfaces, and pin that rendering it did not make a note load-bearing.
# ===========================================================================

def render_census_section(artifact) -> str:
    """`Lib/report.py`'s human-readable census section, as one blob."""
    from gramtrans.Lib.report import _render_census_lines
    return "\n".join(_render_census_lines(artifact))


class TestCappedVerdictIsVisibleInRenderedOutput:
    def test_the_run_report_console_section_prints_the_cap_note(self):
        """The bug T023c fixes: `_render_census_lines` printed the capped token
        and nothing at all about the cap."""
        artifact = gross_basis_artifact()
        assert recompute_verdict(artifact) == GROSS_BASIS_VERDICT_CAP
        rendered = render_census_section(artifact)
        assert GROSS_BASIS_VERDICT_CAP in rendered
        for note in gross_basis_cap_notes(artifact):
            assert note in rendered, "a capped verdict rendered without its note"
        assert "CAPPED" in rendered
        assert "PhPhoneme" in rendered and "21" in rendered
        assert "5.2" in rendered

    def test_a_clean_run_renders_no_notes_block(self):
        """The note block is conditional: a run with nothing to explain must
        render byte-identically to before T023c."""
        artifact = gross_basis_artifact(gross_basis_rows())
        assert artifact.get("notes") == []
        rendered = render_census_section(artifact)
        assert "Census notes" not in rendered
        assert "CAPPED" not in rendered
        assert "CENSUS_CLEAN" in rendered

    def test_a_more_severe_verdict_is_not_crowded_out_by_the_cap_note(self):
        """A cap note is written whenever the gross basis suppressed a tally,
        including on a run a MORE severe verdict then decides. The real failure
        must still be the headline, and the note must not read as though the
        run finished at the ceiling."""
        artifact = gross_basis_artifact(baseline=make_baseline("none"))
        assert recompute_verdict(artifact) == "BASELINE_MISSING"
        rendered = render_census_section(artifact)
        assert "[FAIL] Census verdict: BASELINE_MISSING" in rendered
        assert "exit 4" in rendered
        assert "gate FAILED" in rendered
        # ...and the note is qualified rather than left to contradict it.
        assert "did NOT decide this run" in rendered
        assert "more severe than the " + GROSS_BASIS_VERDICT_CAP in rendered

    def test_the_cli_gate_announces_a_capped_pass(self, tmp_path, capsys):
        """The release-gate surface. A pass that only happened because of the
        subtraction basis must not exit 0 (T024b).

        Measured before T024b: both live sanity pairs reported
        `CENSUS_ACCOUNTED` / exit 0 / `passed=True` while carrying 44-47 failing
        rows and 74,157 units of unexplained shortfall. The cap was behaving as
        specified and the headline still said success, so a caller keying on
        exit 0 -- which is every CI script -- credited a catastrophically
        incomplete transfer. The verdict TOKEN is deliberately unchanged; what
        changed is that exit 0 now means "nothing was lost" and nothing else.
        """
        artifact = gross_basis_artifact()
        path = write_artifact(tmp_path, artifact, "capped.json")
        code = cli_exit(["gate", "--artifact", str(path)])
        out = capsys.readouterr().out
        assert code == census_cli.CAPPED_PASS_EXIT_CODE
        assert code != 0, "a capped pass must never be readable as success"
        assert "verdict " + GROSS_BASIS_VERDICT_CAP in out
        assert "CAPPED" in out
        for note in gross_basis_cap_notes(artifact):
            assert note in out, "the gate passed a capped census silently"

    def test_the_capped_exit_code_is_not_a_verdict_code(self):
        """`CAPPED_PASS_EXIT_CODE` must not collide with section 9's table.

        A non-verdict outcome that borrows a verdict's code is indistinguishable
        from that verdict to every caller -- 3 would read as DUPLICATE_IDENTITY.
        """
        assert census_cli.CAPPED_PASS_EXIT_CODE not in set(
            VERDICT_EXIT_CODES.values())

    def test_the_cli_gate_prints_no_notes_for_a_clean_census(self, tmp_path,
                                                             capsys):
        path = write_artifact(
            tmp_path, gross_basis_artifact(gross_basis_rows()), "clean.json")
        assert cli_exit(["gate", "--artifact", str(path)]) == 0
        out = capsys.readouterr().out
        assert "census note(s)" not in out
        assert "CAPPED" not in out

    def test_rendering_notes_did_not_make_them_load_bearing(self, tmp_path):
        """Invariant 9 survives T023c. Deleting every note changes neither the
        verdict nor the exit code on either surface -- the cap reads
        `starter_subtraction_basis`, and the renderer regenerates the sentence
        from `gross_basis_cap_notes` rather than believing the array."""
        artifact = gross_basis_artifact()
        before = (recompute_verdict(artifact), gate_artifact(artifact).exit_code)

        stripped = json.loads(json.dumps(artifact))
        stripped["notes"] = []
        assert (recompute_verdict(stripped),
                gate_artifact(stripped).exit_code) == before

        absent = json.loads(json.dumps(artifact))
        absent.pop("notes", None)
        assert (recompute_verdict(absent),
                gate_artifact(absent).exit_code) == before

        # The CLI's code is compared against the CLI's own code on the SAME
        # artifact with its notes intact -- not against the library's, which
        # since T024b legitimately differs (the capped-pass code is a property
        # of the process outcome, not of the document).
        with_notes = write_artifact(tmp_path, artifact, "with-notes.json")
        cli_before = cli_exit(["gate", "--artifact", str(with_notes)])
        path = write_artifact(tmp_path, absent, "no-notes.json")
        assert cli_exit(["gate", "--artifact", str(path)]) == cli_before
        # ...and the cap is STILL announced, because the accessor derives the
        # sentence from the basis instead of reading the array back.
        assert "CAPPED" in render_census_section(absent)

    def test_a_fabricated_cap_note_does_not_buy_a_cap_on_either_surface(
            self, tmp_path, capsys):
        """A hand-written note is rendered but cannot change anything: the
        verdict line and the exit code both stay at the real failure."""
        forged = make_artifact(
            replace_row(phase_rows(), "PhPhoneme", source_count=41,
                        destination_count_total=20, destination_count_net=20,
                        verdict_class="SHORTFALL", unexplained_shortfall=21),
            verdict="UNEXPLAINED_SHORTFALL")
        forged["notes"] = list(gross_basis_cap_notes(gross_basis_artifact()))
        assert not any(is_gross_basis_row(r) for r in forged["classes"])
        assert recompute_verdict(forged) == "UNEXPLAINED_SHORTFALL"

        rendered = render_census_section(forged)
        assert "[FAIL] Census verdict: UNEXPLAINED_SHORTFALL" in rendered
        assert "did NOT decide this run" in rendered

        path = write_artifact(tmp_path, forged, "forged.json")
        assert cli_exit(["gate", "--artifact", str(path)]) == 1
        assert "verdict UNEXPLAINED_SHORTFALL" in capsys.readouterr().out

    def test_a_long_note_list_states_what_it_omitted(self):
        """Invariant 2: a console summary may shorten a list only while saying
        how many it left out. The artifact is never truncated."""
        from gramtrans.Lib import report as report_module
        artifact = gross_basis_artifact()
        artifact["notes"] = list(artifact["notes"]) + [
            "[WARN] filler note %d" % index for index in range(60)]
        rendered = render_census_section(artifact)
        budget = report_module._CONSOLE_MAX_ROWS
        omitted = len(artifact["notes"]) - budget
        assert "... and %d more not shown here" % omitted in rendered
        assert "%d total" % len(artifact["notes"]) in rendered
        # The cap note is first in the array, so truncation can never hide it.
        assert "CAPPED" in rendered


# ===========================================================================
# 4. Verdicts, exit codes, severity ordering, PASS predicate
# ===========================================================================

class TestVerdictModel:
    def test_the_nine_verdict_tokens_and_their_exit_codes(self):
        assert dict(VERDICT_EXIT_CODES) == EXPECTED_VERDICT_EXIT_CODES
        for verdict, code in EXPECTED_VERDICT_EXIT_CODES.items():
            assert exit_code_for(verdict) == code

    def test_verdict_tokens_match_the_schema_enum(self, census_schema):
        enum = census_schema["$defs"]["verdictToken"]["enum"]
        assert set(VERDICT_EXIT_CODES) == set(enum)

    def test_human_labels_are_stored_so_console_and_artifact_cannot_drift(self):
        assert dict(VERDICT_HUMAN_LABELS) == EXPECTED_VERDICT_HUMAN_LABELS

    def test_published_severity_ordering(self):
        assert tuple(VERDICT_SEVERITY_ORDER) == EXPECTED_SEVERITY_ORDER

    def test_severity_ordering_is_not_derived_from_the_exit_code(self):
        """'The severity ordering is NOT the exit_code integer and must not be
        derived from it.' Sorting the tokens by exit code descending gives a
        DIFFERENT sequence, which is the proof the two are independent."""
        by_exit_desc = tuple(sorted(EXPECTED_VERDICT_EXIT_CODES,
                                    key=lambda v: -EXPECTED_VERDICT_EXIT_CODES[v]))
        assert tuple(VERDICT_SEVERITY_ORDER) != by_exit_desc
        # Concretely: BASELINE_MISSING (exit 4) outranks DUPLICATE_IDENTITY
        # (exit 3), so severity does not follow the integer at all.
        order = list(VERDICT_SEVERITY_ORDER)
        assert order.index("BASELINE_MISSING") < order.index("DUPLICATE_IDENTITY")
        assert EXPECTED_VERDICT_EXIT_CODES["BASELINE_MISSING"] > \
            EXPECTED_VERDICT_EXIT_CODES["DUPLICATE_IDENTITY"]

    def test_most_severe_verdict_uses_the_published_ordering(self):
        assert most_severe_verdict(["CENSUS_CLEAN"]) == "CENSUS_CLEAN"
        assert most_severe_verdict(
            ["UNEXPLAINED_SHORTFALL", "BASELINE_MISSING"]) == "BASELINE_MISSING"
        assert most_severe_verdict(
            ["BASELINE_MISSING", "DUPLICATE_IDENTITY"]) == "BASELINE_MISSING"
        assert most_severe_verdict(
            ["COVERAGE_INCOMPLETE", "CENSUS_ERROR", "CENSUS_CLEAN"]) == "CENSUS_ERROR"

    def test_pass_is_exactly_the_two_success_verdicts(self):
        assert set(PASSING_VERDICTS) == EXPECTED_PASSING_VERDICTS
        for verdict in EXPECTED_VERDICT_EXIT_CODES:
            expected = verdict in EXPECTED_PASSING_VERDICTS
            assert is_passing_verdict(verdict) is expected, verdict

    def test_only_the_two_success_verdicts_map_to_exit_zero(self):
        """SC-010: there is deliberately no verdict meaning 'loss reported,
        review advisable, exit success'."""
        zero = {v for v, c in EXPECTED_VERDICT_EXIT_CODES.items() if c == 0}
        assert zero == EXPECTED_PASSING_VERDICTS
        for verdict in EXPECTED_VERDICT_EXIT_CODES:
            assert (exit_code_for(verdict) == 0) is is_passing_verdict(verdict)

    def test_an_unknown_verdict_token_is_refused(self):
        with pytest.raises(Exception):
            exit_code_for("CENSUS_PROBABLY_FINE")

    def test_unexplained_shortfall_outranks_unexplained_surplus(self):
        """Section 9: UNEXPLAINED_SURPLUS is assigned only when 'no unexplained
        shortfall outranks it'."""
        order = list(VERDICT_SEVERITY_ORDER)
        assert order.index("UNEXPLAINED_SHORTFALL") < order.index("UNEXPLAINED_SURPLUS")

    def test_clean_and_accounted_are_distinguished(self):
        clean = make_artifact(phase_rows())
        assert recompute_verdict(clean) == "CENSUS_CLEAN"
        rows = replace_row(
            phase_rows(), "MoAffixProcess",
            destination_count_total=0, destination_count_net=0,
            verdict_class="SHORTFALL",
            accounted_for=[make_accounted("NO_CREATE_PATH", 13, "shortfall")],
        )
        accounted = make_artifact(rows, verdict="CENSUS_ACCOUNTED")
        assert recompute_verdict(accounted) == "CENSUS_ACCOUNTED"
        assert gate_artifact(accounted).passed

    def test_coverage_mismatch_is_coverage_incomplete(self):
        """CP-1: FR-012 coverage is PROVEN, not asserted."""
        artifact = make_artifact(phase_rows(), verdict="COVERAGE_INCOMPLETE",
                                 derivation_result="mismatch")
        assert recompute_verdict(artifact) == "COVERAGE_INCOMPLETE"
        assert gate_artifact(artifact).exit_code == 6


# ===========================================================================
# 5. The closed 16-token reason vocabulary
# ===========================================================================

class TestReasonVocabulary:
    def test_exactly_sixteen_tokens(self):
        assert len(EXPECTED_REASON_TOKENS) == 16
        assert set(REASON_TOKENS) == set(EXPECTED_REASON_TOKENS)
        assert len(set(REASON_TOKENS)) == 16

    def test_tokens_match_the_schema_enum_exactly(self, census_schema):
        enum = census_schema["$defs"]["reasonToken"]["enum"]
        assert list(enum) == list(EXPECTED_REASON_TOKENS)
        assert set(REASON_TOKENS) == set(enum)

    def test_there_is_no_unexplained_and_no_other_token(self):
        """'Unexplained is the ABSENCE of an accounting line, so it cannot be
        laundered into one.'"""
        for forbidden in ("UNEXPLAINED", "OTHER", "UNKNOWN", "UNCLASSIFIED", "MISC"):
            assert forbidden not in set(REASON_TOKENS)

    def test_only_four_tokens_are_exempt_from_report_ref(self):
        assert set(REASONS_NOT_REQUIRING_REPORT_REF) == EXPECTED_REASONS_WITHOUT_REPORT_REF
        for token in EXPECTED_REASON_TOKENS:
            expected = token not in EXPECTED_REASONS_WITHOUT_REPORT_REF
            assert reason_requires_report_ref(token) is expected, token

    def test_an_unknown_reason_token_is_refused_not_absorbed(self):
        """'A reason the census cannot classify is CENSUS_ERROR, never a
        free-text pass.'"""
        with pytest.raises(Exception):
            reason_requires_report_ref("UNEXPLAINED")

    def test_schema_rejects_an_unknown_reason_token(self, census_schema):
        rows = replace_row(
            phase_rows(), "MoAffixProcess",
            destination_count_total=0, destination_count_net=0,
            verdict_class="SHORTFALL",
            accounted_for=[{"reason": "UNEXPLAINED", "count": 13,
                            "direction": "shortfall"}],
        )
        artifact = make_artifact(rows, verdict="CENSUS_ACCOUNTED")
        assert schema_errors(artifact, census_schema)

    def test_validator_rejects_an_unknown_reason_token(self):
        rows = replace_row(
            phase_rows(), "MoAffixProcess",
            destination_count_total=0, destination_count_net=0,
            verdict_class="SHORTFALL",
            accounted_for=[{"reason": "OTHER", "count": 13, "direction": "shortfall"}],
        )
        artifact = make_artifact(rows, verdict="CENSUS_ACCOUNTED")
        assert list(validate_artifact(artifact))
        assert recompute_verdict(artifact) == "CENSUS_ERROR"

    @pytest.mark.parametrize("exempt", sorted(EXPECTED_REASONS_WITHOUT_REPORT_REF))
    def test_the_four_exempt_tokens_account_without_a_report_ref(self, exempt):
        direction = "surplus" if exempt == "STARTER_CONTENT" else "shortfall"
        if direction == "surplus":
            rows = replace_row(phase_rows(), "MoMorphType",
                               destination_count_total=6, destination_count_net=6,
                               verdict_class="SURPLUS",
                               accounted_for=[make_accounted(exempt, 3, "surplus")])
        else:
            rows = replace_row(phase_rows(), "MoMorphType",
                               destination_count_total=0, destination_count_net=0,
                               verdict_class="SHORTFALL",
                               accounted_for=[make_accounted(exempt, 3, "shortfall")])
        artifact = make_artifact(rows, verdict="CENSUS_ACCOUNTED")
        line = next(r for r in artifact["classes"]
                    if r["class"] == "MoMorphType")["accounted_for"][0]
        assert "report_ref" not in line
        assert list(validate_artifact(artifact)) == []
        assert gate_artifact(artifact).passed

    @pytest.mark.parametrize("needy", sorted(
        set(EXPECTED_REASON_TOKENS) - EXPECTED_REASONS_WITHOUT_REPORT_REF))
    def test_every_other_token_without_a_report_ref_is_census_error(self, needy):
        """R-1 / invariant 5: 'a line with no resolvable report content is not
        accounting'."""
        rows = replace_row(
            phase_rows(), "MoMorphType",
            destination_count_total=0, destination_count_net=0,
            verdict_class="SHORTFALL",
            accounted_for=[{"reason": needy, "count": 3, "direction": "shortfall"}],
        )
        artifact = make_artifact(rows, verdict="CENSUS_ACCOUNTED")
        assert list(validate_artifact(artifact)), needy
        assert recompute_verdict(artifact) == "CENSUS_ERROR", needy


# ===========================================================================
# 6. The CLI surface (recorded decisions)
# ===========================================================================

class TestCensusCliSurface:
    def test_four_subcommands(self):
        assert tuple(census_cli.SUBCOMMANDS) == EXPECTED_SUBCOMMANDS

    def test_parser_exposes_all_four_subcommands(self):
        parser = census_cli.build_parser()
        choices: set[str] = set()
        for action in getattr(parser, "_actions", ()):
            sub = getattr(action, "choices", None)
            if isinstance(sub, dict):
                choices.update(sub)
        assert set(EXPECTED_SUBCOMMANDS) <= choices

    def test_the_flag_is_destination_not_target(self):
        """Recorded decision: 'destination' is the schema and contract
        vocabulary throughout, so R2's --target is not the surface."""
        known = option_strings(census_cli.build_parser())
        assert "--destination" in known
        assert "--target" not in known

    def test_instrument_is_not_a_debug_script(self):
        """SC-009: 'a release gate cannot live in unsupported scratch.' The
        instrument names the supported module surface, not debug/."""
        artifact = make_artifact(phase_rows())
        assert "debug/" not in artifact["instrument"]["name"]
        assert (_repo_root() / "src" / "gramtrans" / "census_cli.py").exists()
        assert (_repo_root() / "src" / "gramtrans" / "Lib" / "census.py").exists()

    def test_gate_needs_an_artifact(self):
        assert cli_exit(["gate"]) != 0

    def test_missing_artifact_file_is_not_a_pass(self, tmp_path):
        assert cli_exit(["gate", "--artifact", str(tmp_path / "nope.json")]) != 0


# The T023b block below is APPENDED on purpose: it is the only part of this
# file that needs the census module as a MODULE (it patches one seam), and a
# local import here keeps the addition purely additive to a file two tasks
# were editing at once.
from gramtrans.Lib import census  # noqa: E402


# ===========================================================================
# T023b -- the census counts the EXACT class, never the polymorphic subtree
#
# The fakes below are not invented numbers. They reproduce, object for object,
# what LCM reports on a blank FieldWorks starter project (the
# `Ngoreme Target 2026-08-19 0831` backup, `.fwdata` digest bc91a75b...), with
# the own-class counts read straight out of `.fwdata` as independent ground
# truth:
#
#     class            I<Class>Repository.Count    own <rt> rows
#     CmPossibility                       3014              302
#     LexEntryType                          14               11
#
# so `OWN_OBJECTS` is the answer the instrument must give and `cumulative()`
# is what LCM hands back if nobody corrects for inheritance. A future reader who
# "simplifies" the exact-class filter back to a bare `ObjectCountFor` /
# `ObjectsIn` fails this class with the same two numbers that found the defect.
# ===========================================================================

#: `{class: direct subclasses}` -- exactly what LCM's metadata cache answered
#: for these classes on liblcm 11.0.0 (trimmed to the classes that hold objects
#: in the starter, plus the two that make the arithmetic interesting).
STARTER_HIERARCHY: dict = {
    "CmPossibility": (
        "CmAnthroItem", "CmSemanticDomain", "CmPerson", "PartOfSpeech",
        "LexRefType", "LexEntryType", "MoMorphType", "CmAnnotationDefn",
    ),
    "LexEntryType": ("LexEntryInflType",),
}

#: `{class: own objects}` -- counted from `<rt class="...">` in the starter's
#: `.fwdata`, i.e. NOT through LCM at all. This is the ground truth.
OWN_OBJECTS: dict = {
    "CmPossibility": 302,
    "CmSemanticDomain": 1792,
    "CmAnthroItem": 859,
    "CmAnnotationDefn": 15,
    "MoMorphType": 19,
    "LexEntryType": 11,
    "LexEntryInflType": 3,
    "LexRefType": 7,
    "PartOfSpeech": 5,
    "CmPerson": 1,
    "PhPhoneme": 23,
}


def starter_cumulative(object_class: str) -> int:
    """What `I<Class>Repository.Count` reports: the whole inheritance subtree."""
    return OWN_OBJECTS[object_class] + sum(
        starter_cumulative(sub)
        for sub in STARTER_HIERARCHY.get(object_class, ())
    )


class FakeCmObject:
    """An LCM proxy, reduced to the one property that identifies its class."""

    def __init__(self, class_name: str, index: int = 0) -> None:
        self.ClassName = class_name
        self.Guid = "%s-%04d" % (class_name, index)


class NamelessCmObject:
    """A proxy that will not say what it is. `ClassName` is deliberately absent."""

    def __init__(self) -> None:
        self.Guid = "nameless-0000"


class FakeMetaDataCache:
    """`IFwMetaDataCacheManaged`, reduced to the three hierarchy accessors."""

    def __init__(self, hierarchy: dict, known: tuple) -> None:
        self._hierarchy = hierarchy
        self._ids = {name: 1000 + i for i, name in enumerate(known)}
        self._names = {clid: name for name, clid in self._ids.items()}

    def GetClassId(self, class_name):  # noqa: N802 -- LCM's spelling
        return self._ids.get(class_name, 0)

    def GetClassName(self, clid):  # noqa: N802 -- LCM's spelling
        return self._names[int(clid)]

    def GetDirectSubclasses(self, clid):  # noqa: N802 -- LCM's spelling
        return [
            self._ids[sub]
            for sub in self._hierarchy.get(self._names[int(clid)], ())
        ]


class FakeLcmCache:
    def __init__(self, mdc) -> None:
        self.MetaDataCacheAccessor = mdc


class FakeProjectHandle:
    """A `FLExProject` reduced to the census's counting surface.

    `ObjectCountFor` is POLYMORPHIC, like the real one -- that is the whole
    point of the fake. It records every read so T017's "each class enumerated
    once" contract can be asserted rather than asserted-about.
    """

    ProjectName = "T023b fake starter"

    def __init__(self, *, with_metadata: bool = True, raising: tuple = ()) -> None:
        self.count_reads: list = []
        self.enumerations: list = []
        self._raising = set(raising)
        if with_metadata:
            self.project = FakeLcmCache(FakeMetaDataCache(
                STARTER_HIERARCHY, tuple(OWN_OBJECTS)))

    def ObjectCountFor(self, iface):  # noqa: N802 -- flexicon's spelling
        self.count_reads.append(iface)
        if iface in self._raising:
            raise RuntimeError("LCM service locator refused " + iface)
        return starter_cumulative(iface)

    def ObjectsIn(self, iface):  # noqa: N802 -- flexicon's spelling
        self.enumerations.append(iface)
        objects = []
        stack = [iface]
        while stack:
            name = stack.pop()
            objects.extend(
                FakeCmObject(name, i) for i in range(OWN_OBJECTS[name]))
            stack.extend(STARTER_HIERARCHY.get(name, ()))
        return objects

    def ObjectRepository(self, iface):  # noqa: N802 -- flexicon's spelling
        raise RuntimeError("no ICmObjectRepository in the fake")


@pytest.fixture()
def exact_class_seam(monkeypatch):
    """Make `I<Class>Repository` the class name itself.

    `census._repository_interface` imports `SIL.LCModel`, which this file must
    never do (see the module docstring). Patching it is what keeps the T023b
    tests running with no FieldWorks host, and the identity mapping keeps the
    fake handle's bookkeeping readable.
    """
    monkeypatch.setattr(
        census, "_repository_interface", lambda name: name, raising=True)


class TestExactClassCounting:
    """T023b: one object, one class row. No object counted twice."""

    def test_the_fake_reproduces_the_measured_polymorphic_inflation(self):
        """If this drifts, the rest of the class stops testing the real defect.

        3014 = 302 own + the whole CmPossibility subtree; 14 = 11 + 3.
        """
        assert starter_cumulative("CmPossibility") == 3014
        assert starter_cumulative("LexEntryType") == 14
        assert starter_cumulative("PhPhoneme") == 23

    def test_counts_are_the_exact_class_not_the_subtree(self, exact_class_seam):
        handle = FakeProjectHandle()
        counts = census.count_classes(handle, tuple(OWN_OBJECTS))
        assert counts.unmeasurable == ()
        assert counts.counts == OWN_OBJECTS

    def test_the_two_measured_inflations_are_gone(self, exact_class_seam):
        counts = census.count_classes(
            FakeProjectHandle(), ("CmPossibility", "LexEntryType"))
        assert counts.count_for("CmPossibility") == 302
        assert counts.count_for("LexEntryType") == 11

    def test_rows_partition_the_project(self, exact_class_seam):
        """Section 4's whole premise: the rows are disjoint.

        The polymorphic sum double-counts by 2731 objects on the starter; the
        exact sum is the object population itself.
        """
        counts = census.count_classes(FakeProjectHandle(), tuple(OWN_OBJECTS))
        assert sum(counts.counts.values()) == sum(OWN_OBJECTS.values())
        assert sum(counts.cumulative_counts.values()) > sum(OWN_OBJECTS.values())

    def test_a_grandchild_is_subtracted_once_not_twice(self, exact_class_seam):
        """`LexEntryInflType` sits under `LexEntryType` sits under
        `CmPossibility`. Subtracting ALL subclasses instead of the DIRECT ones
        would charge its 3 objects twice and report 299."""
        counts = census.count_classes(FakeProjectHandle(), ("CmPossibility",))
        assert counts.count_for("CmPossibility") == 302

    def test_a_leaf_class_is_unaffected(self, exact_class_seam):
        counts = census.count_classes(FakeProjectHandle(), ("PhPhoneme",))
        assert counts.count_for("PhPhoneme") == 23
        assert counts.cumulative_count_for("PhPhoneme") == 23

    def test_cumulative_is_retained_under_a_name_that_cannot_be_confused(
            self, exact_class_seam):
        counts = census.count_classes(FakeProjectHandle(), ("CmPossibility",))
        assert counts.cumulative_count_for("CmPossibility") == 3014
        assert counts.count_for("CmPossibility") == 302

    def test_t017_one_repository_read_per_class(self, exact_class_seam):
        """The efficiency contract survives: exact counting is arithmetic over
        O(1) reads, not a walk. Every read is memoised, so a class that is
        several classes' subclass is still read once, and no object is
        enumerated at all."""
        handle = FakeProjectHandle()
        census.count_classes(
            handle, ("CmPossibility", "LexEntryType", "LexEntryInflType"))
        assert len(handle.count_reads) == len(set(handle.count_reads))
        assert handle.enumerations == []

    def test_the_basis_is_recorded_as_subtraction(self, exact_class_seam):
        counts = census.count_classes(FakeProjectHandle(), tuple(OWN_OBJECTS))
        assert set(counts.count_basis.values()) == {
            census.COUNT_BASIS_SUBTRACTION}
        assert counts.enumerated_classes == ()

    def test_no_metadata_falls_back_to_a_walk_and_says_so(
            self, exact_class_seam):
        """A silent O(n) fallback would be a cost regression nobody could see.
        It is still EXACT -- correctness never degrades, only speed."""
        handle = FakeProjectHandle(with_metadata=False)
        counts = census.count_classes(handle, ("CmPossibility", "PhPhoneme"))
        assert counts.count_for("CmPossibility") == 302
        assert counts.count_for("PhPhoneme") == 23
        assert counts.enumerated_classes == ("CmPossibility", "PhPhoneme")
        assert set(counts.count_basis.values()) == {
            census.COUNT_BASIS_ENUMERATION}
        assert handle.enumerations == ["CmPossibility", "PhPhoneme"]

    def test_an_unreadable_subclass_is_unmeasurable_not_polymorphic(
            self, exact_class_seam):
        """The tempting fallback -- publish the subtree total -- is the defect.
        The class goes to `unresolved_accessors` instead, naming the subclass."""
        handle = FakeProjectHandle(raising=("CmSemanticDomain",))
        counts = census.count_classes(handle, ("CmPossibility", "PhPhoneme"))
        assert counts.count_for("CmPossibility") is None
        assert "CmPossibility" in counts.unmeasurable
        reason = counts.unresolved_accessors["CmPossibility"]
        assert "CmSemanticDomain" in reason
        assert "3014" in reason
        assert counts.count_for("PhPhoneme") == 23

    def test_objects_in_class_enumerates_only_the_exact_class(
            self, exact_class_seam):
        """T018's duplicate grouping sees 302 CmPossibility objects, not 3014
        objects of nine classes -- otherwise a `PartOfSpeech` name collision is
        reported as a duplicate `CmPossibility`."""
        handle = FakeProjectHandle()
        objects = census.objects_in_class(handle, "CmPossibility")
        assert len(objects) == 302
        assert {obj.ClassName for obj in objects} == {"CmPossibility"}
        assert len(handle.ObjectsIn("CmPossibility")) == 3014

    def test_objects_in_class_enumerates_exactly_once(self, exact_class_seam):
        handle = FakeProjectHandle()
        census.objects_in_class(handle, "LexEntryType")
        assert handle.enumerations == ["LexEntryType"]

    def test_an_object_that_will_not_name_its_class_is_refused(
            self, exact_class_seam, monkeypatch):
        """Keeping it "just in case" is how the subtree gets back in."""
        handle = FakeProjectHandle()
        monkeypatch.setattr(
            handle, "ObjectsIn",
            lambda iface: [FakeCmObject("PhPhoneme", 0), NamelessCmObject()])
        with pytest.raises(census.CensusError):
            census.objects_in_class(handle, "PhPhoneme")

    def test_a_negative_subtraction_is_not_a_measurement(
            self, exact_class_seam, monkeypatch):
        """LCM contradicting itself must surface as unmeasurable, never as a
        negative "count" that then flows into a difference."""
        handle = FakeProjectHandle()
        real = handle.ObjectCountFor

        def understated(iface):
            value = real(iface)
            return 1 if iface == "CmPossibility" else value

        monkeypatch.setattr(handle, "ObjectCountFor", understated)
        counts = census.count_classes(handle, ("CmPossibility",))
        assert counts.count_for("CmPossibility") is None
        assert "negative count is not a measurement" in (
            counts.unresolved_accessors["CmPossibility"])

    def test_the_polymorphism_is_documented_at_the_counting_site(self):
        """A future reader must not be able to reach `ObjectCountFor` without
        meeting the reason it is not the answer (T023b: `census.py` mentioned
        the polymorphism nowhere, which is how it survived T017-T023a)."""
        source = (_repo_root() / "src" / "gramtrans" / "Lib" / "census.py"
                  ).read_text(encoding="utf-8")
        assert "POLYMORPHIC" in source
        assert "3014" in source and "302" in source
        for symbol in ("COUNT_BASIS_SUBTRACTION", "COUNT_BASIS_ENUMERATION",
                       "cumulative_count_for", "direct_subclass_names"):
            assert symbol in source


# ===========================================================================
# T024 -- THE ADVERSARIAL SANITY CHECK: the instrument must SEE a real loss
# ===========================================================================
#
# Everything above this line is hermetic: synthetic artifacts in `tmp_path`, no
# FieldWorks host, no project. That property is load-bearing (the census gate
# has to stay runnable on a machine with no LCM) and this block does NOT change
# it -- every live test below carries `@pytest.mark.integration` INDIVIDUALLY,
# the module still has no module-scoped marker, and nothing here imports
# `flexicon` at module scope. `-m "not integration"` runs the hermetic suite.
#
# WHY THIS BLOCK EXISTS
# ---------------------
# A census that reports a known-destroyed transfer as clean is worse than no
# census, because it launders the loss. So before any green result from this
# instrument is trusted, it has to be shown FAILING on transfers whose damage
# is already known from the `.fwdata` on disk.
#
# THE PAIRS, AS MEASURED (2026-08-19) -- NOT AS ASSUMED
# ----------------------------------------------------
# T024's brief named pairs that turned out not to be the ones on disk. The
# figures below were read straight out of each `.fwdata` (`<rt class="X"`
# counts) and then reproduced by the instrument. Where brief and disk
# disagree, THE DISK WINS and the discrepancy is recorded here:
#
#   * `MoStemMsa` 1949 -> 0 is `Ngoreme FLEx` -> `Ngoreme Target`.
#     It is NOT the project called `Ngoreme`, which holds MoStemMsa 1945 and
#     PhPhoneme 37. `Ngoreme FLEx` holds exactly 1949 and 41.
#   * `PhPhoneme` 41 -> 64 holds on BOTH pairs, because both sources happen to
#     carry 41 phonemes. 23 starter + 41 source == 64, so this row is the
#     clearest available test of whether starter subtraction works at all.
#   * `MoInflAffixTemplate` 8 -> 0 / `MoInflAffixSlot` 11 -> 0 is the EJAGHAM
#     pair. The Ngoreme pair loses 13 and 19 instead.
#   * `MoAffixProcess` 13 -> 0 is the EJAGHAM pair. But the other half of that
#     story -- `MoAffixAllomorph` +13 -- IS NOT REPRODUCIBLE from any state on
#     disk: `Ejagham W Target` holds ZERO MoAffixAllomorph, so the pair shows
#     130 -> 0, both classes destroyed outright rather than one converted into
#     the other. No project on this machine holds the 143 that +13 needs.
#     `test_moaffixallomorph_plus_13_is_not_reproducible_from_disk` pins that
#     honestly instead of manufacturing the pair with a transfer.
#     The conversion SIGNATURE is still reproducible, at scale 1, on the
#     Ngoreme pair: MoAffixProcess 1 -> 0 beside MoAffixAllomorph 146 -> 147.
#
# WHAT THESE TWO PAIRS ACTUALLY ARE -- AND WHY ONLY ONE IS DAMNING
# ---------------------------------------------------------------
# NEITHER destination is a blank project, and the two tell different stories.
# Read this before citing either as proof of a transfer defect.
#
#   * `Ngoreme Target` IS POPULATED: 1415 LexEntry, 1552 LexSense, 1534
#     MoStemAllomorph, 147 MoAffixAllomorph, 50 Text, 2271 Segment. A broad
#     transfer plainly ran and moved a great deal. And yet ZERO of the source's
#     1949 MoStemMsa arrived, along with 0 of 134 MoInflAffMsa, 0 of 13
#     templates and 0 of 19 slots. That is the genuinely damning pair: the
#     lexicon arrived STRIPPED OF ITS MORPHO-SYNTACTIC ANALYSES. It is not "a
#     blank project reads 0"; it is a populated project missing exactly the
#     grammar layer, which is the loss class 038 exists to catch.
#
#   * `Ejagham W Target` IS NEARLY EMPTY: 0 LexEntry, 0 LexSense, 64 PhPhoneme.
#     That is consistent with a deliberately PHONOLOGY-ONLY run (feature 037's
#     territory), so its zeros are "losses" only relative to a full-transfer
#     expectation. THE CENSUS CANNOT KNOW A RUN'S INTENDED SCOPE: with no
#     `--run-report` it compares every class source -> destination and reports
#     what is missing, which is the correct conservative behaviour. Supplying
#     the run report is what moves those rows from `unexplained_shortfall` into
#     `accounted_for`. So the Ejagham rows below pin THAT THE INSTRUMENT SEES
#     the absences -- not that the transfer was buggy to produce them.
#
# The distinction matters for what a green result would have meant: on the
# Ngoreme pair a clean census would be a false negative on a real defect; on
# the Ejagham pair it would be a false negative on an out-of-scope class.
#
# THE GROSS-BASIS CAP MEANS THE RUN VERDICT IS NOT THE EVIDENCE
# ------------------------------------------------------------
# The real baseline is a `starter_capture` with `carries_natural_keys: false`,
# so every row lands on `baseline_gross`, so `fidelity-census.md` 5.2 caps the
# RUN verdict at `CENSUS_ACCOUNTED` and suppresses `UNEXPLAINED_SHORTFALL`.
# Both pairs therefore exit 0 while having lost whole classes. That is correct
# behaviour and it is exactly why these tests assert on ROW-level evidence --
# `difference`, `unexplained_shortfall`, `verdict_class`, `census.row_passes`,
# `census.evaluate_phase` -- which the cap deliberately leaves untouched.
# `test_the_capped_run_verdict_is_not_a_clean_transfer` pins the trap itself so
# nobody can later cite "exit 0" as evidence the transfer was lossless.

T024_NGOREME_SOURCE = "Ngoreme FLEx"
T024_NGOREME_DESTINATION = "Ngoreme Target"
T024_EJAGHAM_SOURCE = "Ejagham W Mini"
T024_EJAGHAM_DESTINATION = "Ejagham W Target"

T024_NGOREME_PAIR = (T024_NGOREME_SOURCE, T024_NGOREME_DESTINATION)
T024_EJAGHAM_PAIR = (T024_EJAGHAM_SOURCE, T024_EJAGHAM_DESTINATION)

#: Every loss this task must prove the instrument can see, keyed by pair:
#: `(source_count, destination_count_total, difference, unexplained_shortfall,
#:   unexplained_surplus, verdict_class)`. `row_passes` must be False for all
#: of them -- that is the single most important assertion in this block.
T024_EXPECTED_LOSSES = {
    T024_NGOREME_PAIR: {
        "MoStemMsa":           (1949, 0, -1949, 1949, 0, "SHORTFALL"),
        "MoAffixProcess":      (1, 0, -1, 1, 0, "SHORTFALL"),
        "MoAffixAllomorph":    (146, 147, 1, 0, 1, "SURPLUS"),
        "MoInflAffixTemplate": (13, 0, -13, 13, 0, "SHORTFALL"),
        "MoInflAffixSlot":     (19, 0, -19, 19, 0, "SHORTFALL"),
    },
    T024_EJAGHAM_PAIR: {
        "MoStemMsa":           (153, 0, -153, 153, 0, "SHORTFALL"),
        "MoAffixProcess":      (13, 0, -13, 13, 0, "SHORTFALL"),
        "MoAffixAllomorph":    (130, 0, -130, 130, 0, "SHORTFALL"),
        "MoInflAffixTemplate": (8, 0, -8, 8, 0, "SHORTFALL"),
        "MoInflAffixSlot":     (11, 0, -11, 11, 0, "SHORTFALL"),
    },
}

#: `PhPhoneme` duplicate-name groups per pair, under the census's OWN key
#: definition: the Name's DEFAULT VERNACULAR alternative, exact and
#: case-sensitive (T018).
#:
#: The Ejagham pair yields the expected 21. The Ngoreme pair yields 20, and the
#: difference is the instrument being RIGHT: a ws-agnostic scan of
#: `Ngoreme Target.fwdata` finds THREE phonemes whose Name contains "b", but
#: the third is `{en: "b", ngq: "bh"}` and `ngq` is the default vernacular, so
#: its key is "bh" and it is not a duplicate at all. Counting it would have
#: been exactly the fabrication `census._ws_handle_for` exists to prevent.
T024_EXPECTED_PHONEME_DUPLICATES = {
    T024_NGOREME_PAIR: 20,
    T024_EJAGHAM_PAIR: 21,
}

#: 23 starter + 41 source == 64 destination, on both pairs.
T024_PHONEME_STARTER_BASELINE = 23
T024_PHONEME_SOURCE_COUNT = 41
T024_PHONEME_DESTINATION_TOTAL = 64

#: Live runs are expensive (the Ngoreme source is a 76 MB `.fwdata`), so each
#: pair is censused at most ONCE per session and every test reads the cached
#: artifact. Keyed by pair; the value is the artifact dict or a skip reason.
_T024_CACHE: dict = {}


T024_BASELINE_RELPATH = (
    "specs/038-transfer-fidelity-gaps/contracts/starter-baseline.json")

#: Materialised copies of the baseline pulled out of git, kept for the session
#: so `git show` runs at most once.
_T024_BASELINE_CACHE: dict = {}


def _t024_starter_baseline() -> Path:
    """The recaptured starter baseline, found from ANY worktree.

    THIS IS NOT OVER-ENGINEERING, IT IS THE PROJECT'S GIT PROTOCOL. CLAUDE.md:
    "if it lives under `specs/`, commit it to `main`; otherwise commit it on
    the feature worktree." The baseline is a spec artifact, so it lives on
    `main` (commit 69f4097) and a feature worktree checked out at a branch tip
    that predates it DOES NOT HAVE THE FILE. Resolving only against
    `_repo_root()` therefore skipped all 23 live tests on the very worktree
    they are meant to run in -- a clean skip, but a silent one, and a green
    "137 passed, 23 skipped" is exactly the false comfort T024 exists to
    prevent.

    So: prefer the working tree, then ask git for it on `main`, and only then
    give up and let the caller skip.
    """
    direct = _repo_root() / Path(T024_BASELINE_RELPATH)
    if direct.is_file():
        return direct
    if "path" in _T024_BASELINE_CACHE:
        return _T024_BASELINE_CACHE["path"]

    import subprocess  # noqa: PLC0415 -- only needed on the fallback path
    import tempfile  # noqa: PLC0415

    for ref in ("main", "origin/main"):
        try:
            blob = subprocess.run(
                ["git", "show", ref + ":" + T024_BASELINE_RELPATH],
                cwd=str(_repo_root()), capture_output=True, timeout=60,
                check=False)
        except (OSError, subprocess.SubprocessError):
            break
        if blob.returncode == 0 and blob.stdout.strip():
            out = (Path(tempfile.mkdtemp(prefix="gt038-t024-baseline-"))
                   / "starter-baseline.json")
            out.write_bytes(blob.stdout)
            _T024_BASELINE_CACHE["path"] = out
            return out
    return direct


def _t024_fwdata(project_name: str) -> Path:
    """Where the project's `.fwdata` would be. Pure path arithmetic --
    `census.fwdata_path_for` touches no LCM and imports no flexicon, so this
    stays safe to call during collection on a host with no FieldWorks."""
    return census.fwdata_path_for(project_name)


def _t024_census(source: str, destination: str) -> dict:
    """The census artifact for one live pair, or `pytest.skip`.

    Skips rather than errors on every absence this machine can present: a
    missing project, a missing baseline, a project another program holds open
    (FieldWorks takes an exclusive `.fwdata.lock` and flexicon then raises
    `FP_FileLockedError`, which the CLI reports as CENSUS_ERROR / exit 7 with
    no artifact written), or a host with no FieldWorks at all.

    READ-ONLY IS NOT ASSUMED HERE, IT IS CHECKED. The CLI's `run` path digests
    each `.fwdata` before the open and again after the CLOSE and refuses the
    whole run if either moved, so reaching a written artifact is itself proof;
    `test_the_census_wrote_nothing_to_either_project` then re-reads both files
    off disk and compares them against the recorded digests.
    """
    key = (source, destination)
    if key in _T024_CACHE:
        cached = _T024_CACHE[key]
        if isinstance(cached, str):
            pytest.skip(cached)
        return cached

    def refuse(reason: str):
        _T024_CACHE[key] = reason
        pytest.skip(reason)

    baseline = _t024_starter_baseline()
    if not baseline.is_file():
        refuse("T024: no starter baseline at " + str(baseline))
    for name in (source, destination):
        path = _t024_fwdata(name)
        if not path.is_file():
            refuse("T024: project " + repr(name) + " has no .fwdata at "
                   + str(path))

    # T024c: this block asserts fixed figures against projects AS THEY HAPPEN
    # TO SIT ON DISK, and nothing binds either project to the state T024
    # measured. When one moves, the assertions below stop describing anything
    # -- they do not become wrong about the transfer, they become wrong about
    # WHICH transfer, which is worse because the failure reads like a
    # regression. So the pair is checked against the recorded digests first and
    # the block STANDS DOWN rather than reporting a loss it can no longer
    # attribute.
    #
    # This is not coverage being dropped. Every figure these tests assert is
    # also asserted hermetically against the committed artifacts in
    # `_snapshots/census-038-*.json` (TestMeasuredCensusSnapshots and the
    # blocks below it), which is why those keep passing while these skip. And
    # the LIVE coverage is now `TestT024cTheSanityCheckProducesItsOwnTransfer`,
    # which restores the destination and performs the transfer itself instead
    # of hoping the last session left the right one behind.
    import hashlib  # noqa: PLC0415

    for name in (source, destination):
        recorded = MEASURED_PROJECT_DIGESTS.get(name)
        if recorded is None:
            continue
        actual = hashlib.sha256(
            _t024_fwdata(name).read_bytes()).hexdigest()
        if actual != recorded:
            refuse(
                "T024/T024c: " + repr(name) + " has changed since T024 "
                "measured it (digest " + actual[:12] + "... != recorded "
                + recorded[:12] + "...), so the fixed figures in this block no "
                "longer describe this file. The hermetic snapshot assertions "
                "still cover every one of them; the live coverage is "
                "TestT024cTheSanityCheckProducesItsOwnTransfer, which produces "
                "the transfer it measures instead of measuring whatever is on "
                "disk.")

    import tempfile  # noqa: PLC0415 -- only needed on the live path

    out = Path(tempfile.mkdtemp(prefix="gt038-t024-")) / "census.json"
    argv = [
        "run",
        "--source", source,
        "--destination", destination,
        "--baseline", str(baseline),
        "--destination-freshly-created",
        "--out", str(out),
    ]
    try:
        code = cli_exit(argv)
    except Exception as exc:  # noqa: BLE001 -- no FieldWorks host, COM, ...
        refuse("T024: could not census " + repr(source) + " -> "
               + repr(destination) + ": " + type(exc).__name__ + ": "
               + str(exc))
    if not out.is_file():
        refuse("T024: the census of " + repr(source) + " -> "
               + repr(destination) + " wrote no artifact (exit " + str(code)
               + ") -- most often CENSUS_ERROR because a project is open in "
               "FieldWorks and holds its .fwdata.lock")
    artifact = json.loads(out.read_text(encoding="utf-8"))
    _T024_CACHE[key] = artifact
    return artifact


def _t024_row(artifact: dict, object_class: str) -> dict:
    """One class row, insisting the row EXISTS.

    A missing row is the worst failure available to this block: it is the
    instrument not looking, which reads identically to a clean result in every
    summary. `MoAffixProcess` is the live example -- it is in the class list
    only via `census_additions` with `inventory_tables: ["NONE"]`, i.e. no
    transfer table claims to move it, and it is precisely the class the
    Ejagham transfer destroyed 13 of.
    """
    for row in artifact.get("classes", ()):
        if row.get("class") == object_class:
            return row
    raise AssertionError(
        "no census row for " + repr(object_class) + " -- the instrument cannot "
        "report a loss in a class it never counted. Rows present: "
        + str(sorted(r.get("class") for r in artifact.get("classes", ())))
    )


def _t024_pair_id(pair) -> str:
    return pair[0] + " -> " + pair[1]


T024_PAIRS = [
    pytest.param(T024_NGOREME_PAIR, id="ngoreme"),
    pytest.param(T024_EJAGHAM_PAIR, id="ejagham"),
]


class TestT024KnownBadPairsAreSeen:
    """Every expected loss, asserted at ROW level so the gross-basis verdict
    cap cannot hide a regression behind a green run verdict."""

    @pytest.mark.integration
    @pytest.mark.parametrize("pair", T024_PAIRS)
    def test_no_expected_loss_row_is_reported_clean(self, pair):
        """THE headline assertion of T024. If any row in the expected table
        passes section 6, the instrument is laundering a known loss and no
        green result from it means anything."""
        artifact = _t024_census(*pair)
        clean = []
        for object_class in T024_EXPECTED_LOSSES[pair]:
            row = _t024_row(artifact, object_class)
            if census.row_passes(row):
                clean.append(
                    object_class + ": source " + str(row["source_count"])
                    + " -> destination " + str(row["destination_count_total"])
                    + ", difference " + str(row["difference"])
                    + ", verdict_class " + str(row["verdict_class"]))
        assert not clean, (
            _t024_pair_id(pair) + ": the census reported " + str(len(clean))
            + " KNOWN-BAD row(s) as PASSING -- " + "; ".join(clean))

    @pytest.mark.integration
    @pytest.mark.parametrize("pair", T024_PAIRS)
    def test_every_expected_loss_row_reproduces_its_measured_figures(self, pair):
        """Not merely "it failed" but "it failed with the right numbers", so a
        regression that changes WHAT is counted is caught as well as one that
        stops counting altogether."""
        artifact = _t024_census(*pair)
        actual, expected = {}, {}
        for object_class, figures in T024_EXPECTED_LOSSES[pair].items():
            row = _t024_row(artifact, object_class)
            actual[object_class] = (
                row["source_count"],
                row["destination_count_total"],
                row["difference"],
                row["unexplained_shortfall"],
                row["unexplained_surplus"],
                row["verdict_class"],
            )
            expected[object_class] = figures
        assert actual == expected, _t024_pair_id(pair)

    @pytest.mark.integration
    def test_mostemmsa_1949_to_0_is_a_total_loss_the_census_reports(self):
        """The brief's flagship pair. `Ngoreme Target` holds ZERO MoStemMsa
        against a source of 1949 -- every morpho-syntactic analysis of every
        stem, gone. A census that cannot see this can see nothing."""
        artifact = _t024_census(*T024_NGOREME_PAIR)
        row = _t024_row(artifact, "MoStemMsa")
        assert row["source_count"] == 1949
        assert row["destination_count_total"] == 0
        assert row["destination_count_net"] == 0
        assert row["starter_baseline_count"] == 0, (
            "the blank starter holds no MoStemMsa, so gross subtraction cannot "
            "excuse any part of this shortfall")
        assert row["difference"] == -1949
        assert row["unexplained_shortfall"] == 1949
        assert row["verdict_class"] == "SHORTFALL"
        assert row["accounted_for"] == [], (
            "nothing explains the loss, so it must stay unexplained rather "
            "than acquire an accounting line")
        assert census.row_passes(row) is False

    @pytest.mark.integration
    @pytest.mark.parametrize("pair", T024_PAIRS)
    def test_the_total_loss_is_named_by_the_phase_predicates(self, pair):
        """Row figures are the evidence; the phase predicates are how a phase
        is stopped from declaring itself done over them. Both must NAME the
        class, because a failure that does not say what broke is not usable."""
        artifact = _t024_census(*pair)
        for phase in (1, 5):
            result = census.evaluate_phase(artifact, phase)
            assert result.satisfied is False, (
                _t024_pair_id(pair) + ": phase " + str(phase) + " declared "
                "itself satisfied over a destroyed transfer")
            named = [f for f in result.failures if "MoStemMsa" in f]
            assert named, (
                _t024_pair_id(pair) + ": phase " + str(phase) + " failed but "
                "never named MoStemMsa: " + str(list(result.failures)[:5]))
            assert census.gate_artifact(artifact, phase=phase).passed is False

    @pytest.mark.integration
    def test_moinflaffixtemplate_8_and_slot_11_to_zero_ejagham(self):
        """The inflectional templates and their slots, both wiped. Asserted on
        the Ejagham pair because that is where 8 and 11 actually live; the
        Ngoreme pair loses 13 and 19 and is covered by the table above."""
        artifact = _t024_census(*T024_EJAGHAM_PAIR)
        for object_class, source_count in (
                ("MoInflAffixTemplate", 8), ("MoInflAffixSlot", 11)):
            row = _t024_row(artifact, object_class)
            assert row["source_count"] == source_count, object_class
            assert row["destination_count_total"] == 0, object_class
            assert row["difference"] == -source_count, object_class
            assert row["unexplained_shortfall"] == source_count, object_class
            assert census.row_passes(row) is False, object_class


class TestT024PhonemeStarterSubtraction:
    """`PhPhoneme` 41 -> 64 is the one row that tests starter subtraction
    itself: the destination total is LARGER than the source, and only
    subtracting the 23 starter phonemes reveals the transfer is square."""

    @pytest.mark.integration
    @pytest.mark.parametrize("pair", T024_PAIRS)
    def test_starter_subtraction_nets_64_minus_23_to_the_source_41(self, pair):
        artifact = _t024_census(*pair)
        row = _t024_row(artifact, "PhPhoneme")
        assert row["source_count"] == T024_PHONEME_SOURCE_COUNT
        assert row["destination_count_total"] == T024_PHONEME_DESTINATION_TOTAL
        assert row["starter_baseline_count"] == T024_PHONEME_STARTER_BASELINE
        assert row["starter_baseline_source"] == "baseline_document"
        # The whole point: net == total - baseline, and that equals the source.
        assert row["destination_count_net"] == (
            T024_PHONEME_DESTINATION_TOTAL - T024_PHONEME_STARTER_BASELINE)
        assert row["destination_count_net"] == T024_PHONEME_SOURCE_COUNT
        assert row["difference"] == 0
        assert row["verdict_class"] == "MATCHED"
        # And the UNSUBTRACTED reading is retained and is NOT the answer, so a
        # reader can see what subtraction bought: +23 became 0.
        assert row["difference_raw"] == 23

    @pytest.mark.integration
    @pytest.mark.parametrize("pair", T024_PAIRS)
    def test_the_duplicate_phoneme_names_are_detected(self, pair):
        """Exact, case-sensitive matching on the default vernacular Name alt --
        T018's contract. The counts differ per pair BECAUSE that key definition
        is honoured; see `T024_EXPECTED_PHONEME_DUPLICATES`."""
        artifact = _t024_census(*pair)
        row = _t024_row(artifact, "PhPhoneme")
        duplicates = row.get("duplicates")
        assert isinstance(duplicates, dict), (
            _t024_pair_id(pair) + ": PhPhoneme carries NO duplicates block, so "
            "the census never looked for duplicate identities -- and an absent "
            "block is not the same claim as extra_objects 0")
        expected = T024_EXPECTED_PHONEME_DUPLICATES[pair]
        assert duplicates["extra_objects"] == expected, (
            _t024_pair_id(pair) + ": expected " + str(expected) + " extra "
            "phoneme objects, got " + str(duplicates["extra_objects"]))
        assert duplicates["groups"] > 0
        assert "case-sensitive" in duplicates["key_definition"]
        # Examples must be real, distinct objects, not one GUID repeated.
        for group in duplicates.get("examples", ()):
            assert group["count"] >= 2, group
            assert len(set(group["guids"])) == len(group["guids"]), group

    @pytest.mark.integration
    @pytest.mark.parametrize("pair", T024_PAIRS)
    def test_the_duplicates_fail_phase_1_even_though_the_arithmetic_passes(
            self, pair):
        """SC-002, and the reason the phoneme row is in this block at all.

        `difference` is 0 and `verdict_class` is MATCHED, so BASELINE
        ARITHMETIC ALONE WOULD HAVE PASSED THIS ROW. The duplicate check is the
        only thing that catches the transfer having created second copies of
        starter phonemes instead of matching the starters by name."""
        artifact = _t024_census(*pair)
        row = _t024_row(artifact, "PhPhoneme")
        assert row["difference"] == 0 and row["verdict_class"] == "MATCHED"
        assert census.row_passes(row) is True, (
            "if this ever becomes False the SC-002 story here is no longer the "
            "interesting one, and this test needs rewriting, not silencing")
        result = census.evaluate_phase(artifact, 1)
        assert result.satisfied is False
        named = [f for f in result.failures
                 if "PhPhoneme" in f and "extra_objects" in f]
        assert named, (
            _t024_pair_id(pair) + ": phase 1 did not fail on the duplicate "
            "phonemes: " + str(list(result.failures)))
        assert str(T024_EXPECTED_PHONEME_DUPLICATES[pair]) in named[0]

    @pytest.mark.integration
    @pytest.mark.parametrize("pair", T024_PAIRS)
    def test_the_duplicates_do_NOT_raise_the_verdict_to_duplicate_identity(
            self, pair):
        """A FINDING, pinned as behaviour rather than quietly filed as a defect.

        T024's brief expected `DUPLICATE_IDENTITY` (severity above the
        gross-basis cap, exit 3) here. It does NOT fire, and the reason is
        neither the cap nor a bug: `PhPhoneme` is not in 035's natural-key
        roster, so `duplicates.roster_admitted` is False, and
        `census.duplicates_unaccounted` returns 0 for unadmitted classes BY
        DESIGN -- "a duplicate name on an unadmitted class is advisory, because
        homographs are legitimate content" (census.py).

        Consequence, and it is a real gap worth staring at:
        `totals.duplicate_extra_objects` reads 0 on a destination holding 20-21
        duplicate phonemes, and the run exits 0. Only the phase-1 predicate in
        the test above stops the transfer being called done.

        `test_admitting_phphoneme_to_the_roster_makes_the_duplicates_fail`
        proves roster admission is the ONLY thing in the way, so 038's roster
        extension flips this without touching census.py."""
        artifact = _t024_census(*pair)
        row = _t024_row(artifact, "PhPhoneme")
        assert row["duplicates"]["roster_admitted"] is False
        assert census.duplicates_unaccounted(row) == 0
        assert "PhPhoneme" not in census.roster_admitted_classes(_repo_root()), (
            "PhPhoneme has joined the roster -- its duplicates are now "
            "gate-failing, so this test and the totals expectation below must "
            "be updated to the DUPLICATE_IDENTITY behaviour T024 predicted")
        assert census.gate_artifact(artifact).verdict != "DUPLICATE_IDENTITY"
        assert artifact["totals"]["duplicate_extra_objects"] == 0, (
            "the artifact's headline duplicate tally counts admitted classes "
            "only; the per-row block is where the "
            + str(T024_EXPECTED_PHONEME_DUPLICATES[pair])
            + " duplicates are visible")

    def test_admitting_phphoneme_to_the_roster_makes_the_duplicates_fail(self):
        """Hermetic counterpart to the finding above -- NO live project needed,
        so the gap stays pinned on a machine with no FieldWorks.

        Take 5.2's worked example (gross basis, capped verdict) carrying 21
        duplicate phonemes and flip ONLY `roster_admitted`. `DUPLICATE_IDENTITY`
        outranks the `CENSUS_ACCOUNTED` ceiling, so the verdict must move and
        the exit code must leave 0. That isolates roster admission as the whole
        difference, which is what makes the live finding a ROSTER gap rather
        than a census-engine defect.

        `gross_basis_rows` is re-applied after `replace_row` on purpose:
        `replace_row` rebuilds the row through `make_row`, which does not carry
        `starter_baseline_count` / `starter_subtraction_basis`, so without it
        the phoneme row would silently leave the gross basis and the cap under
        test would not apply to it."""
        advisory_rows = gross_basis_rows(replace_row(
            five_two_worked_example_rows(), "PhPhoneme",
            source_count=41, destination_count_total=64,
            destination_count_net=41, verdict_class="MATCHED",
            unexplained_shortfall=0, unexplained_surplus=0,
            duplicates_extra=21, duplicates_groups=21, roster_admitted=False))
        # Invariant 2: `duplicates.examples` is NEVER truncated, so 21 groups
        # must carry 21 example groups. `make_row` leaves the list empty, and
        # the census caught that -- which is itself a small vote of confidence.
        examples = [
            {"key": f"p{n}", "count": 2,
             "guids": [f"00000000-0000-4000-8000-0000000000{2 * n:02d}",
                       f"00000000-0000-4000-8000-0000000000{2 * n + 1:02d}"]}
            for n in range(21)
        ]
        for candidate in advisory_rows:
            if candidate["class"] == "PhPhoneme":
                candidate["duplicates"]["examples"] = examples
        advisory = gross_basis_artifact(advisory_rows)
        advisory_row = _t024_row(advisory, "PhPhoneme")
        assert advisory_row["duplicates"]["roster_admitted"] is False
        assert advisory_row["starter_subtraction_basis"] == (
            GROSS_SUBTRACTION_BASIS)
        assert census.duplicates_unaccounted(advisory_row) == 0
        # The advisory artifact comes out CENSUS_CLEAN rather than merely
        # capped, and that is the sharpest possible form of this test: zeroing
        # 5.2's phantom phoneme shortfall leaves the cap nothing to suppress,
        # so NOTHING is wrong with this artifact except 21 duplicate phonemes
        # on an unadmitted class -- and it still exits 0.
        advisory_outcome = census.gate_artifact(advisory)
        assert advisory_outcome.verdict != "DUPLICATE_IDENTITY"
        assert census.exit_code_for(advisory_outcome.verdict) == 0
        assert advisory_outcome.passed is True, (
            "21 duplicate phonemes bought no failure at all while PhPhoneme is "
            "outside the roster -- that is the gap this test exists to record")

        admitted_rows = gross_basis_rows(replace_row(
            advisory_rows, "PhPhoneme", roster_admitted=True))
        admitted = gross_basis_artifact(admitted_rows)
        admitted_row = _t024_row(admitted, "PhPhoneme")
        assert admitted_row["duplicates"]["extra_objects"] == 21
        assert census.duplicates_unaccounted(admitted_row) == 21
        outcome = census.gate_artifact(admitted)
        assert outcome.verdict == "DUPLICATE_IDENTITY"
        assert outcome.passed is False
        assert census.exit_code_for(outcome.verdict) != 0


class TestT024ClassConversionAndUnreproduciblePairs:
    """`MoAffixProcess` -> `MoAffixAllomorph`: one class silently becoming
    another. Both halves have to appear, because a census showing only the
    shortfall reports a deletion where the truth is a substitution."""

    @pytest.mark.integration
    def test_moaffixprocess_13_to_0_is_seen_on_the_ejagham_pair(self):
        artifact = _t024_census(*T024_EJAGHAM_PAIR)
        row = _t024_row(artifact, "MoAffixProcess")
        assert row["source_count"] == 13
        assert row["destination_count_total"] == 0
        assert row["difference"] == -13
        assert row["unexplained_shortfall"] == 13
        assert census.row_passes(row) is False
        # It is measured only because the census ADDED it: no transfer
        # inventory table claims to move MoAffixProcess at all. A census built
        # from the tables alone would have had no row here, and would have
        # reported this pair clean on this class.
        assert row["in_class_list_via"] == "census_additions"
        assert row["inventory_tables"] == ["NONE"]
        assert row["gate_scope"] == "required"

    @pytest.mark.integration
    def test_moaffixallomorph_plus_13_is_not_reproducible_from_disk(self):
        """AN HONEST NEGATIVE RESULT, deliberately not manufactured.

        T024's brief expects `MoAffixProcess` 13 -> 0 to appear *against*
        `MoAffixAllomorph` +13, i.e. 13 affix processes converted into 13 affix
        allomorphs. `Ejagham W Target` holds ZERO MoAffixAllomorph, so what is
        actually on disk is 130 -> 0: both classes destroyed outright. No
        project on this machine holds the 143 the +13 reading needs.

        Producing that pair would mean running a transfer, which T024 is not
        authorised to do, so this test asserts the TRUE state and names the
        gap. If a future session does create the +13 destination this test
        fails and should be REPLACED by the conversion assertion -- it must not
        be deleted quietly."""
        artifact = _t024_census(*T024_EJAGHAM_PAIR)
        row = _t024_row(artifact, "MoAffixAllomorph")
        assert row["source_count"] == 130
        assert row["destination_count_total"] == 0, (
            "Ejagham W Target has grown MoAffixAllomorph objects -- the +13 "
            "conversion pair may now be reproducible here")
        assert row["difference"] == -130
        assert row["unexplained_surplus"] == 0
        assert census.row_passes(row) is False

    @pytest.mark.integration
    def test_the_conversion_signature_is_reproducible_at_scale_one(self):
        """The `Ngoreme FLEx` -> `Ngoreme Target` pair carries the conversion
        story the Ejagham pair cannot: MoAffixProcess 1 -> 0 while
        MoAffixAllomorph goes 146 -> 147. The starter contributes 0 of either,
        so the +1 is a genuine surplus and not starter arithmetic.

        BOTH halves must be in the SAME artifact and must NOT be netted against
        each other -- a shortfall of 1 in one class beside a surplus of 1 in
        another is two findings, not zero."""
        artifact = _t024_census(*T024_NGOREME_PAIR)
        lost = _t024_row(artifact, "MoAffixProcess")
        gained = _t024_row(artifact, "MoAffixAllomorph")

        assert (lost["source_count"], lost["destination_count_total"]) == (1, 0)
        assert lost["difference"] == -1
        assert lost["unexplained_shortfall"] == 1
        assert lost["starter_baseline_count"] == 0

        assert (gained["source_count"],
                gained["destination_count_total"]) == (146, 147)
        assert gained["difference"] == 1
        assert gained["verdict_class"] == "SURPLUS"
        assert gained["unexplained_surplus"] == 1
        assert gained["starter_baseline_count"] == 0

        assert census.row_passes(lost) is False
        assert census.row_passes(gained) is False

        # No cross-class netting: the totals carry the surplus AND the
        # shortfall, and the surplus is not cancelled by the far larger
        # shortfall sitting beside it.
        totals = artifact["totals"]
        assert totals["unexplained_surplus"] >= 1
        assert totals["unexplained_shortfall"] >= 1949
        assert totals["classes_surplus"] >= 1
        assert totals["classes_shortfall"] >= 1


class TestT024TheGreenVerdictIsNotEvidence:
    """The gross-basis cap makes both of these catastrophic transfers exit 0.
    That is contract-correct and it is a trap, so it is pinned here rather than
    left for someone to discover by citing it as proof of a clean transfer."""

    @pytest.mark.integration
    @pytest.mark.parametrize("pair", T024_PAIRS)
    def test_the_capped_run_verdict_is_not_a_clean_transfer(self, pair):
        artifact = _t024_census(*pair)
        # Every row is on the gross basis, which is what triggers the cap.
        assert all(row.get("starter_subtraction_basis")
                   == GROSS_SUBTRACTION_BASIS
                   for row in artifact["classes"])
        assert artifact["starter_baseline"]["kind"] == "starter_capture"
        assert artifact["starter_baseline"]["carries_natural_keys"] is False

        outcome = census.gate_artifact(artifact)
        assert outcome.verdict == GROSS_BASIS_VERDICT_CAP
        assert census.exit_code_for(outcome.verdict) == 0
        assert outcome.verdict != "CENSUS_CLEAN", (
            "a capped run must never read as CLEAN -- CENSUS_ACCOUNTED is the "
            "ceiling precisely so that distinction survives")

        # ...and yet the artifact is full of failing rows, and no phase passes.
        failing = [row["class"] for row in artifact["classes"]
                   if not census.row_passes(row)]
        assert len(failing) >= 40, (
            _t024_pair_id(pair) + ": only " + str(len(failing)) + " failing "
            "rows on a transfer that lost whole classes")
        assert census.gate_artifact(artifact, phase=5).passed is False

        # The cap must be AUDIBLE: the artifact says so in its own notes.
        notes = " ".join(artifact.get("notes", ()))
        assert GROSS_BASIS_VERDICT_CAP in notes and "ADVISORY" in notes

    @pytest.mark.integration
    @pytest.mark.parametrize("pair", T024_PAIRS)
    def test_the_census_wrote_nothing_to_either_project(self, pair):
        """Read-only, proved twice: by the digest pair the run itself recorded
        across the open AND the close, and by re-reading both files here."""
        artifact = _t024_census(*pair)
        for role in ("source", "destination"):
            block = artifact["projects"][role]
            assert block["opened_read_only"] is True, role
            assert (block["fwdata_sha256_before"]
                    == block["fwdata_sha256_after"]), role
            fwdata = _t024_fwdata(block["name"])
            assert census.sha256_of(fwdata) == block["fwdata_sha256_before"], (
                block["name"] + "'s .fwdata has changed since the census read "
                "it at " + str(fwdata))


# ===========================================================================
# T024 -- the instrument, sanity-checked against KNOWN-BAD live pairs
#
# WHY THIS EXISTS
# ---------------
# Every test above proves the census is INTERNALLY consistent: given an
# artifact, the verdict, the phases and the invariants follow. None of them
# proves the census SEES A REAL LOSS. A counter that always returns
# `difference: 0` would pass all 136 of them.
#
# So T024 measured two pairs whose losses were already known from feature
# 035/037 work, and pins the measured numbers here. If the instrument ever
# starts reporting these pairs as clean, these tests say so.
#
# WHERE THE DATA LIVES, AND WHY
# -----------------------------
# `tests/integration/_snapshots/census-038-{ngoreme,ejagham}.json` -- committed
# beside `full_e2e_post.json`, which established the directory. They are the
# BYTE-FOR-BYTE artifacts `census run` wrote on 2026-08-19 against the four
# live projects; nothing was trimmed, reordered or hand-edited.
#
# Not trimmed on purpose. `recompute_verdict` reconciles
# `class_list_provenance.required_class_count` against `len(classes)` and
# `derivation_check`, so dropping the 69 rows these tests do not name would
# turn the artifact into COVERAGE_INCOMPLETE and destroy the single most
# important property below -- that a run carrying 44-47 failing rows still
# reports exit 0. A trimmed fixture could not pin the surprise it exists to
# pin. 137 KB for both, against the 467 KB snapshot already in that directory.
#
# Not a scratchpad path on purpose either: a test that reads
# `%TEMP%/claude/.../scratchpad` passes for exactly one agent on one machine.
# `test_the_snapshots_are_committed_repo_data` pins that.
#
# HERMETIC vs LIVE
# ----------------
# Everything here is hermetic (JSON off disk) EXCEPT
# `TestCorrectedPremiseNgoremeFlexIsTheSource`, which carries
# `@pytest.mark.integration` on the one test that opens projects. Per T014's
# module docstring the module itself must stay marker-free and runnable with
# no live project: `-m "not integration"` must collect and pass everything
# else. Do not promote the marker to module scope.
#
# TWO THINGS DELIBERATELY NOT ASSERTED
# ------------------------------------
# 1. The RUN VERDICT / EXIT CODE of a shortfall pair. Both artifacts are on the
#    `baseline_gross` basis (the real baseline is count-only), so 5.2's cap
#    makes the run verdict `CENSUS_ACCOUNTED` / exit 0 BY DESIGN. That is
#    pinned as the documented surprise in
#    `TestCappedExitZeroCoexistsWithFailingRows`, not treated as a pass.
#    Loss evidence is asserted per row (`difference`,
#    `unexplained_shortfall`, `verdict_class`, `row_passes`) and through
#    `evaluate_phase` / `gate_artifact(phase=N)`, which the cap never touches.
# 2. `DUPLICATE_IDENTITY` for the duplicate phonemes. It does not fire and
#    must not be asserted -- see `TestDuplicatePhonemesAreInertUntilT028`.
# ===========================================================================

MEASURED_CENSUS_SNAPSHOTS = {
    "ngoreme": "census-038-ngoreme.json",
    "ejagham": "census-038-ejagham.json",
}

#: The four projects the two snapshots were measured against, with the
#: `.fwdata` digest recorded before AND after each read-only open. `Ngoreme
#: Target` is irreplaceable evidence of a ruined transfer: it must never be
#: write-enabled or restored, and its digest is pinned here so a later run
#: that touched it cannot pass these tests quietly.
MEASURED_PROJECT_DIGESTS = {
    "Ngoreme FLEx":
        "052243ea76405eed520c17e3d61562f09fa5efd171f65eb02f1abf1c8f09843b",
    "Ngoreme Target":
        "dda21971829a36030f749d60a5a020444cb291376056a2e37043e430104af3b1",
    "Ejagham W Mini":
        "c174f0b455982a1245b12ec6213ff92366603eb3c000e45fcf81cbd01c9924e6",
    "Ejagham W Target":
        "1cbef60c9550360181d61ee11efb0907811cb0cb6829d681f71de2b7bed094cc",
}


def measured_snapshot_path(pair: str) -> Path:
    return (
        Path(__file__).resolve().parent / "_snapshots"
        / MEASURED_CENSUS_SNAPSHOTS[pair]
    )


def load_measured_census(pair: str) -> dict:
    path = measured_snapshot_path(pair)
    assert path.is_file(), (
        "the T024 measured census snapshot is missing: " + str(path)
        + " -- it is committed repo data, not a regenerable temp file; "
        "restore it from git rather than re-running the 76 MB Ngoreme open"
    )
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture()
def ngoreme_census() -> dict:
    """`Ngoreme FLEx` -> `Ngoreme Target`, measured 2026-08-19."""
    return load_measured_census("ngoreme")


@pytest.fixture()
def ejagham_census() -> dict:
    """`Ejagham W Mini` -> `Ejagham W Target`, measured 2026-08-19."""
    return load_measured_census("ejagham")


def measured_row(artifact, object_class: str) -> dict:
    for row in artifact["classes"]:
        if row["class"] == object_class:
            return row
    raise AssertionError(
        "no census row for " + object_class + " in the measured artifact for "
        + repr(artifact["projects"]["source"]["name"]) + " -> "
        + repr(artifact["projects"]["destination"]["name"])
        + "; rows present: "
        + ", ".join(sorted(r["class"] for r in artifact["classes"]))
    )


def failing_rows(artifact) -> list:
    return [row for row in artifact["classes"] if not row_passes(row)]


# ---------------------------------------------------------------------------
# The snapshots themselves: real, valid, and committed
# ---------------------------------------------------------------------------

class TestMeasuredCensusSnapshots:
    """The fixtures are genuine instrument output, not hand-authored JSON."""

    @pytest.mark.parametrize("pair", sorted(MEASURED_CENSUS_SNAPSHOTS))
    def test_the_snapshot_parses_and_is_schema_version_1(self, pair):
        artifact = load_measured_census(pair)
        assert artifact["schema_version"] == CENSUS_SCHEMA_VERSION

    @pytest.mark.parametrize("pair", sorted(MEASURED_CENSUS_SNAPSHOTS))
    def test_the_snapshot_validates_against_the_published_schema(
            self, pair, census_schema):
        errors = schema_errors(load_measured_census(pair), census_schema)
        assert errors == [], (
            "the measured " + pair + " artifact does not validate against "
            + str(_schema_path()) + ": " + "; ".join(errors[:5])
        )

    @pytest.mark.parametrize("pair", sorted(MEASURED_CENSUS_SNAPSHOTS))
    def test_the_snapshot_passes_the_section_11_invariants(self, pair):
        """A real loss must be reportable WITHOUT breaking an invariant. If
        `validate_artifact` complained here, the failing rows below would be a
        malformed document rather than measured evidence."""
        assert validate_artifact(load_measured_census(pair)) == ()

    def test_the_snapshots_name_the_pairs_the_journal_names(
            self, ngoreme_census, ejagham_census):
        """Corrected premise 1: the 1949-object source is `Ngoreme FLEx`, NOT
        `Ngoreme`. tasks.md said `Ngoreme`; `Ngoreme` holds 1945/37."""
        assert ngoreme_census["projects"]["source"]["name"] == "Ngoreme FLEx"
        assert (ngoreme_census["projects"]["destination"]["name"]
                == "Ngoreme Target")
        assert ejagham_census["projects"]["source"]["name"] == "Ejagham W Mini"
        assert (ejagham_census["projects"]["destination"]["name"]
                == "Ejagham W Target")

    @pytest.mark.parametrize("pair", sorted(MEASURED_CENSUS_SNAPSHOTS))
    def test_every_project_was_opened_read_only_with_an_unchanged_digest(
            self, pair):
        artifact = load_measured_census(pair)
        for role, block in artifact["projects"].items():
            assert block["opened_read_only"] is True, role
            assert (block["fwdata_sha256_before"]
                    == block["fwdata_sha256_after"]), role
            assert (block["fwdata_sha256_before"]
                    == MEASURED_PROJECT_DIGESTS[block["name"]]), (
                block["name"] + " was measured at a different digest than the "
                "one T024 recorded -- either the snapshot was regenerated or "
                "the project was written to"
            )

    def test_the_destination_projects_are_declared_freshly_created(
            self, ngoreme_census, ejagham_census):
        for artifact in (ngoreme_census, ejagham_census):
            assert (artifact["projects"]["destination"]
                    ["declared_freshly_created"] is True)

    @pytest.mark.parametrize("pair", sorted(MEASURED_CENSUS_SNAPSHOTS))
    def test_the_snapshots_are_committed_repo_data(self, pair):
        """A test that reads a session scratchpad passes for one agent on one
        machine and fails for everybody else. These live under `tests/`."""
        path = measured_snapshot_path(pair)
        root = _repo_root()
        assert root in path.parents
        assert (root / "tests" / "integration" / "_snapshots") == path.parent
        lowered = [part.lower() for part in path.parts]
        assert "temp" not in lowered and "tmp" not in lowered

    @pytest.mark.parametrize("pair", sorted(MEASURED_CENSUS_SNAPSHOTS))
    def test_the_snapshot_records_the_instrument_that_produced_it(self, pair):
        instrument = load_measured_census(pair)["instrument"]
        assert instrument["name"] == "gramtrans.census_cli"
        assert instrument["gramtrans_dirty"] is False
        assert instrument["flexicon_version"] == "4.5.2"
        assert instrument["flex_version"] == "9.3.10"


# ---------------------------------------------------------------------------
# MoStemMsa 1949 -> 0: the loss that started feature 038
# ---------------------------------------------------------------------------

class TestMoStemMsaTotalLoss:
    """`Ngoreme FLEx` -> `Ngoreme Target`: every one of 1949 stem MSAs gone."""

    def test_mostemmsa_is_1949_to_0(self, ngoreme_census):
        row = measured_row(ngoreme_census, "MoStemMsa")
        assert row["source_count"] == 1949
        assert row["destination_count_total"] == 0
        assert row["starter_baseline_count"] == 0
        assert row["destination_count_net"] == 0
        assert row["difference"] == -1949
        assert row["difference_raw"] == -1949
        assert row["unexplained_shortfall"] == 1949
        assert row["unexplained_surplus"] == 0
        assert row["verdict_class"] == "SHORTFALL"
        assert row["gate_scope"] == "required"

    def test_the_row_does_not_pass(self, ngoreme_census):
        assert row_passes(measured_row(ngoreme_census, "MoStemMsa")) is False

    def test_nothing_claims_to_account_for_it(self, ngoreme_census):
        """R-5: an empty `accounted_for` is not an excuse. 1949 units are
        unexplained and stay unexplained."""
        row = measured_row(ngoreme_census, "MoStemMsa")
        assert row["accounted_for"] == []
        assert row["unexplained_shortfall"] == -row["difference"]

    def test_the_gross_basis_does_not_soften_the_row(self, ngoreme_census):
        """5.2's cap is the RUN verdict only. The row-level evidence the cap
        leaves untouched is what these tests assert on."""
        row = measured_row(ngoreme_census, "MoStemMsa")
        assert row["starter_subtraction_basis"] == GROSS_SUBTRACTION_BASIS
        assert is_gross_basis_row(row) is True
        assert row["difference"] == -1949
        assert row["unexplained_shortfall"] == 1949
        assert row_passes(row) is False

    def test_the_ejagham_pair_loses_its_stem_msas_too(self, ejagham_census):
        """Not a Ngoreme quirk: the same class is 153 -> 0 on the other pair."""
        row = measured_row(ejagham_census, "MoStemMsa")
        assert row["source_count"] == 153
        assert row["destination_count_total"] == 0
        assert row["difference"] == -153
        assert row_passes(row) is False


# ---------------------------------------------------------------------------
# PhPhoneme 41 -> 64: the row net arithmetic gets RIGHT
# ---------------------------------------------------------------------------

class TestPhonemeRowIsMatchedByNetArithmetic:
    """The counterpart to MoStemMsa: a destination total LARGER than the
    source, which naive subtraction would call a surplus and gross
    subtraction would call a shortfall. Net arithmetic calls it MATCHED, and
    that is correct -- 23 of the 64 are the starter project's own phonemes."""

    @pytest.mark.parametrize("pair", sorted(MEASURED_CENSUS_SNAPSHOTS))
    def test_41_to_64_over_a_baseline_of_23_is_matched(self, pair):
        row = measured_row(load_measured_census(pair), "PhPhoneme")
        assert row["source_count"] == 41
        assert row["destination_count_total"] == 64
        assert row["starter_baseline_count"] == 23
        assert row["destination_count_net"] == 41
        assert row["difference"] == 0
        assert row["verdict_class"] == "MATCHED"
        assert row["unexplained_shortfall"] == 0
        assert row["unexplained_surplus"] == 0

    @pytest.mark.parametrize("pair", sorted(MEASURED_CENSUS_SNAPSHOTS))
    def test_the_raw_difference_is_a_plus_23_the_baseline_explains(self, pair):
        """`difference_raw` is kept precisely so the +23 is visible rather
        than silently absorbed: 64 - 41 = +23, and 64 - 23 = 41 = source."""
        row = measured_row(load_measured_census(pair), "PhPhoneme")
        assert row["difference_raw"] == 23
        assert (row["difference_raw"]
                == row["destination_count_total"] - row["source_count"])
        assert (row["destination_count_net"]
                == row["destination_count_total"] - row["starter_baseline_count"])
        assert row["destination_count_net"] == row["source_count"]

    @pytest.mark.parametrize("pair", sorted(MEASURED_CENSUS_SNAPSHOTS))
    def test_the_matched_row_still_carries_its_duplicate_evidence(self, pair):
        """MATCHED on count does not mean clean: the same row records 20-21
        duplicate names. Section 6 needs BOTH conditions, which is why
        `row_passes` reads `duplicates` and not just `difference`."""
        row = measured_row(load_measured_census(pair), "PhPhoneme")
        assert row["difference"] == 0
        assert row["duplicates"]["groups"] >= 20
        assert row["duplicates"]["extra_objects"] >= 20

    @pytest.mark.parametrize("pair", sorted(MEASURED_CENSUS_SNAPSHOTS))
    def test_the_phoneme_row_is_a_leaf_count_not_a_subtree_count(self, pair):
        """T023b: `PhPhoneme` has no subclasses, so 64 is 64 and the exact /
        cumulative distinction cannot hide anything on this row."""
        row = measured_row(load_measured_census(pair), "PhPhoneme")
        assert row["in_class_list_via"] == "coverage_floor"
        assert "TABLE_1" in row["inventory_tables"]


# ---------------------------------------------------------------------------
# Process morphology: the class the truth source never listed
# ---------------------------------------------------------------------------

class TestProcessMorphologyLoss:
    """`MoAffixProcess` is absent from 035's `object-inventory.md` entirely,
    because the engine has no create path for it -- so nothing measured it and
    nothing reported the drop. It reaches the census as a `census_additions`
    row, which is the point: a class missing from the truth source is a
    TRUTH-SOURCE gap, not a corpus gap."""

    def test_ejagham_moaffixprocess_is_13_to_0(self, ejagham_census):
        row = measured_row(ejagham_census, "MoAffixProcess")
        assert row["source_count"] == 13
        assert row["destination_count_total"] == 0
        assert row["starter_baseline_count"] == 0
        assert row["difference"] == -13
        assert row["difference_raw"] == -13
        assert row["unexplained_shortfall"] == 13
        assert row["verdict_class"] == "SHORTFALL"
        assert row_passes(row) is False

    def test_the_row_arrives_via_census_additions_with_no_inventory_table(
            self, ejagham_census):
        row = measured_row(ejagham_census, "MoAffixProcess")
        assert row["in_class_list_via"] == "census_additions"
        assert row["inventory_tables"] == ["NONE"]
        assert row["gate_scope"] == "required", (
            "a class the inventory forgot must still be REQUIRED, or the "
            "census inherits the very blind spot it was built to close"
        )

    @pytest.mark.parametrize("pair", sorted(MEASURED_CENSUS_SNAPSHOTS))
    def test_the_addition_is_declared_as_owed_back_to_035(self, pair):
        artifact = load_measured_census(pair)
        additions = {
            entry["class"]: entry
            for entry in artifact["class_list_provenance"]["census_additions"]
        }
        assert "MoAffixProcess" in additions
        entry = additions["MoAffixProcess"]
        assert entry["owed_to_035"] is True
        assert "13 -> 0" in entry["measured_evidence"]
        assert "1 -> 0" in entry["measured_evidence"]

    def test_ngoreme_moaffixprocess_is_1_to_0(self, ngoreme_census):
        """Scale 1. Small, but the same defect, and it is what makes the
        conversion signature below reproducible on one pair."""
        row = measured_row(ngoreme_census, "MoAffixProcess")
        assert row["source_count"] == 1
        assert row["destination_count_total"] == 0
        assert row["difference"] == -1
        assert row["unexplained_shortfall"] == 1
        assert row_passes(row) is False


# ---------------------------------------------------------------------------
# Templates and slots: the Ejagham pair, 8 and 11
# ---------------------------------------------------------------------------

class TestTemplateAndSlotLoss:
    """Corrected premise 2: `MoInflAffixTemplate` 8 / `MoInflAffixSlot` 11 is
    the EJAGHAM pair. tasks.md attributed it to Ngoreme, which loses 13 and
    19 -- also total, just different numbers."""

    def test_ejagham_template_is_8_to_0(self, ejagham_census):
        row = measured_row(ejagham_census, "MoInflAffixTemplate")
        assert row["source_count"] == 8
        assert row["destination_count_total"] == 0
        assert row["difference"] == -8
        assert row["unexplained_shortfall"] == 8
        assert row["verdict_class"] == "SHORTFALL"
        assert row_passes(row) is False

    def test_ejagham_slot_is_11_to_0(self, ejagham_census):
        row = measured_row(ejagham_census, "MoInflAffixSlot")
        assert row["source_count"] == 11
        assert row["destination_count_total"] == 0
        assert row["difference"] == -11
        assert row["unexplained_shortfall"] == 11
        assert row["verdict_class"] == "SHORTFALL"
        assert row_passes(row) is False

    def test_the_ngoreme_pair_loses_13_and_19_not_8_and_11(
            self, ngoreme_census):
        assert measured_row(
            ngoreme_census, "MoInflAffixTemplate")["source_count"] == 13
        assert measured_row(
            ngoreme_census, "MoInflAffixTemplate")["difference"] == -13
        assert measured_row(
            ngoreme_census, "MoInflAffixSlot")["source_count"] == 19
        assert measured_row(
            ngoreme_census, "MoInflAffixSlot")["difference"] == -19

    @pytest.mark.parametrize("pair", sorted(MEASURED_CENSUS_SNAPSHOTS))
    def test_phase_2_is_unsatisfied_and_names_both_classes(self, pair):
        """A template with no slots is not a partial transfer; it is an
        unusable one. Phase 2's predicate is where that surfaces."""
        result = evaluate_phase(load_measured_census(pair), 2)
        assert result.satisfied is False
        blob = " | ".join(result.failures)
        assert "MoInflAffixTemplate" in blob
        assert "MoInflAffixSlot" in blob


# ---------------------------------------------------------------------------
# THE PROPERTY THAT MATTERS MOST: a conversion is TWO facts, never one net
# ---------------------------------------------------------------------------

class TestConversionSignatureIsNotNetted:
    """When the engine silently DOWNGRADES a class -- reads an
    `MoAffixProcess`, writes an `MoAffixAllomorph` -- the object count barely
    moves. A census that netted the two halves would report nothing at all.

    tasks.md described this as `MoAffixProcess` 13 -> 0 beside
    `MoAffixAllomorph` +13. That +13 DOES NOT EXIST ON DISK: no project on
    this machine holds 143 affix allomorphs, and `Ejagham W Target` lost BOTH
    classes outright (130 -> 0 and 13 -> 0). It was not manufactured to make a
    test pass -- see `test_no_plus_13_allomorph_row_was_fabricated`.

    The SIGNATURE is nonetheless reproducible at scale 1 on the Ngoreme pair,
    and that is what is pinned: a shortfall row and a surplus row, both
    present in ONE artifact, neither cancelling the other."""

    def test_both_halves_are_present_in_one_artifact(self, ngoreme_census):
        shortfall = measured_row(ngoreme_census, "MoAffixProcess")
        surplus = measured_row(ngoreme_census, "MoAffixAllomorph")

        assert shortfall["source_count"] == 1
        assert shortfall["destination_count_total"] == 0
        assert shortfall["difference"] == -1
        assert shortfall["unexplained_shortfall"] == 1
        assert shortfall["verdict_class"] == "SHORTFALL"

        assert surplus["source_count"] == 146
        assert surplus["destination_count_total"] == 147
        assert surplus["starter_baseline_count"] == 0
        assert surplus["difference"] == 1
        assert surplus["difference_raw"] == 1
        assert surplus["unexplained_surplus"] == 1
        assert surplus["verdict_class"] == "SURPLUS"

    def test_the_two_halves_are_not_netted_against_each_other(
            self, ngoreme_census):
        """The defect this guards against: -1 + +1 == 0, so a netting census
        prints a clean line and the downgrade is invisible forever. Both
        tallies must survive into `totals` separately."""
        totals = ngoreme_census["totals"]
        assert totals["unexplained_shortfall"] == 74157
        assert totals["unexplained_surplus"] == 1
        assert totals["total_surplus"] == 1
        assert totals["classes_surplus"] == 1
        assert totals["classes_shortfall"] == 47
        assert totals["accounted_shortfall"] == 0
        assert totals["accounted_surplus"] == 0

    def test_neither_half_claims_the_other_as_its_explanation(
            self, ngoreme_census):
        """There is no accounting line linking them, and there must not be:
        `MoAffixProcess` -> `MoAffixAllomorph` is not one of the 16 reason
        tokens, so a conversion CANNOT be explained away as bookkeeping."""
        for name in ("MoAffixProcess", "MoAffixAllomorph"):
            assert measured_row(ngoreme_census, name)["accounted_for"] == []
        assert not any(
            "CONVER" in token or "DOWNGRAD" in token
            for token in REASON_TOKENS
        )

    def test_both_halves_are_required_rows_so_both_can_fail_a_phase(
            self, ngoreme_census):
        for name in ("MoAffixProcess", "MoAffixAllomorph"):
            row = measured_row(ngoreme_census, name)
            assert row["gate_scope"] == "required"
            assert row_passes(row) is False

    def test_phase_5_is_unsatisfied_and_names_both_halves(
            self, ngoreme_census):
        result = evaluate_phase(ngoreme_census, 5)
        assert result.satisfied is False
        blob = " | ".join(result.failures)
        assert "MoAffixProcess" in blob
        assert "MoAffixAllomorph" in blob

    def test_no_plus_13_allomorph_row_was_fabricated(
            self, ngoreme_census, ejagham_census):
        """tasks.md's `MoAffixAllomorph +13` is not on disk and was NOT
        invented to satisfy the brief. On Ejagham the class is 130 -> 0; on
        Ngoreme it is 146 -> 147. Neither is +13, and no source count of 130
        can produce a destination of 143."""
        ejagham = measured_row(ejagham_census, "MoAffixAllomorph")
        assert ejagham["source_count"] == 130
        assert ejagham["destination_count_total"] == 0
        assert ejagham["difference"] == -130
        assert ejagham["verdict_class"] == "SHORTFALL"

        ngoreme = measured_row(ngoreme_census, "MoAffixAllomorph")
        assert ngoreme["difference"] == 1
        for row in (ejagham, ngoreme):
            assert row["difference"] != 13
            assert row["destination_count_total"] != 143


# ---------------------------------------------------------------------------
# FINDING 2 -- the capped exit 0. Documented, not treated as a pass.
# ---------------------------------------------------------------------------

class TestCappedExitZeroCoexistsWithFailingRows:
    """Both ruined pairs report `CENSUS_ACCOUNTED` / exit 0.

    That is 5.2's gross-basis cap behaving exactly as specified -- the real
    baseline is count-only, so EVERY row is `baseline_gross`, and on that
    basis a shortfall tally is advisory rather than evidence. It is pinned
    here so the behaviour is DISCOVERED FROM A TEST rather than rediscovered
    from a green release gate: the headline says success while 44-47 rows fail
    and 7,357-74,157 units are unexplained. Recorded as T024b.

    These are the tests that must NOT be read as "the transfer was fine"."""

    @pytest.mark.parametrize("pair", sorted(MEASURED_CENSUS_SNAPSHOTS))
    def test_the_run_verdict_is_capped_to_a_passing_token(self, pair):
        artifact = load_measured_census(pair)
        assert artifact["verdict"] == GROSS_BASIS_VERDICT_CAP
        assert artifact["verdict"] == "CENSUS_ACCOUNTED"
        assert artifact["exit_code"] == 0
        assert recompute_verdict(artifact) == "CENSUS_ACCOUNTED"
        assert is_passing_verdict(recompute_verdict(artifact)) is True
        assert gate_artifact(artifact).passed is True
        assert gate_artifact(artifact).exit_code == 0

    @pytest.mark.parametrize(
        "pair,failing,shortfall_rows,unexplained",
        [("ngoreme", 46, 47, 74157), ("ejagham", 44, 46, 7357)],
    )
    def test_the_same_artifact_carries_dozens_of_failing_rows(
            self, pair, failing, shortfall_rows, unexplained):
        """The two halves of the surprise, asserted together on purpose.

        `failing` is one or two fewer than `shortfall_rows` because
        `LexRefType` and `PhBdryMarker` are `gate_scope: advisory` on both
        pairs (CP-3: an advisory row cannot by itself fail the gate), while
        Ngoreme's required SURPLUS row `MoAffixAllomorph` fails and is not a
        shortfall row at all."""
        artifact = load_measured_census(pair)
        assert gate_artifact(artifact).exit_code == 0
        assert len(failing_rows(artifact)) == failing
        assert artifact["totals"]["classes_shortfall"] == shortfall_rows
        assert artifact["totals"]["unexplained_shortfall"] == unexplained
        assert "MoStemMsa" in {row["class"] for row in failing_rows(artifact)}
        advisory = {row["class"] for row in artifact["classes"]
                    if row["verdict_class"] == "SHORTFALL"
                    and row["gate_scope"] != "required"}
        assert advisory == {"LexRefType", "PhBdryMarker"}

    @pytest.mark.parametrize(
        "pair,shortfall,unexplained,matched,short_rows,advisory",
        [("ngoreme", 75016, 74157, 24, 47, 9),
         ("ejagham", 8216, 7357, 26, 46, 12)],
    )
    def test_the_measured_totals(self, pair, shortfall, unexplained, matched,
                                 short_rows, advisory):
        totals = load_measured_census(pair)["totals"]
        assert totals["classes_reported"] == 75
        assert totals["classes_matched"] == matched
        assert totals["classes_shortfall"] == short_rows
        assert totals["classes_not_evaluated"] == 3
        assert totals["total_shortfall"] == shortfall
        assert totals["unexplained_shortfall"] == unexplained
        assert totals["advisory_shortfall"] == advisory

    @pytest.mark.parametrize("pair,suppressed", [("ngoreme", 46),
                                                ("ejagham", 44)])
    def test_every_row_is_on_the_gross_basis_which_is_why_the_cap_applies(
            self, pair, suppressed):
        artifact = load_measured_census(pair)
        bases = {row["starter_subtraction_basis"] for row in artifact["classes"]}
        assert bases == {GROSS_SUBTRACTION_BASIS}
        assert len(gross_basis_suppressions(artifact)) == suppressed

    @pytest.mark.parametrize("pair", sorted(MEASURED_CENSUS_SNAPSHOTS))
    def test_the_cap_is_audible_rather_than_silent(self, pair):
        """T023c. An exit 0 that printed nothing about the cap would be the
        worst of both worlds."""
        artifact = load_measured_census(pair)
        assert artifact["notes"], "a capped run must carry its cap notes"
        headline = artifact["notes"][0]
        assert "CAPPED at CENSUS_ACCOUNTED" in headline
        assert "ADVISORY" in headline
        assert "NOT a statement that nothing was lost" in headline
        assert any(
            "CAPPED at CENSUS_ACCOUNTED" in note
            for note in gross_basis_cap_notes(artifact)
        ), "the sentence must be regenerable from the basis, not only stored"

    @pytest.mark.parametrize("pair", sorted(MEASURED_CENSUS_SNAPSHOTS))
    def test_the_failing_evidence_is_reachable_through_phase(self, pair):
        """The information exists; only the DEFAULT is wrong. `--phase` turns
        the same artifact into a refusal."""
        artifact = load_measured_census(pair)
        assert gate_artifact(artifact).passed is True
        for phase in (1, 2, 5):
            outcome = gate_artifact(artifact, phase=phase)
            assert outcome.passed is False, phase
            assert outcome.phase is not None
            assert outcome.phase.satisfied is False

    @pytest.mark.parametrize("pair", sorted(MEASURED_CENSUS_SNAPSHOTS))
    def test_phase_1_and_phase_5_name_mostemmsa_and_moaffixprocess(self, pair):
        artifact = load_measured_census(pair)
        phase_1 = evaluate_phase(artifact, 1)
        phase_5 = evaluate_phase(artifact, 5)
        assert phase_1.satisfied is False
        assert phase_5.satisfied is False
        assert any("MoStemMsa" in f for f in phase_1.failures)
        assert any("MoStemMsa" in f for f in phase_5.failures)
        assert any("MoAffixProcess" in f for f in phase_5.failures)

    def test_the_cap_is_a_ceiling_on_tallies_not_on_severity(
            self, ngoreme_census):
        """Proof the exit 0 is the cap and not a blind instrument: add a
        single error to the SAME artifact and it becomes CENSUS_ERROR."""
        from copy import deepcopy

        assert recompute_verdict(ngoreme_census) == "CENSUS_ACCOUNTED"
        forged = deepcopy(ngoreme_census)
        forged["errors"] = [{
            "class": "MoStemMsa",
            "message": "synthetic, to prove severity still escapes the cap",
        }]
        assert recompute_verdict(forged) == "CENSUS_ERROR"
        assert exit_code_for(recompute_verdict(forged)) == 7

    def test_a_baseline_matched_row_would_defeat_the_cap(self, ngoreme_census):
        """And the fix is not a code change: supply a run report, the basis
        stops being gross, and the 1949 becomes evidence rather than advice."""
        from copy import deepcopy

        forged = deepcopy(ngoreme_census)
        for row in forged["classes"]:
            if row["class"] == "MoStemMsa":
                row["starter_subtraction_basis"] = "baseline_matched"
        assert recompute_verdict(forged) == "UNEXPLAINED_SHORTFALL"
        assert exit_code_for(recompute_verdict(forged)) == 1


# ---------------------------------------------------------------------------
# FINDING 1 -- the duplicate phonemes are INERT, and that is a T028 dependency
# ---------------------------------------------------------------------------

class TestDuplicatePhonemesAreInertUntilT028:
    """21 duplicate phoneme names in the Ejagham destination (20 in Ngoreme),
    and `DUPLICATE_IDENTITY` NEVER FIRES. `totals.duplicate_extra_objects`
    reads 0.

    Not a bug and not the cap: `PhPhoneme` is absent from 035's natural-key
    roster (admitted: `WfiWordform`, `ReversalIndex`, `ReversalIndexEntry`), so
    `duplicates.roster_admitted` is False and `duplicates_unaccounted()`
    returns 0 BY DESIGN -- a duplicate name on an unadmitted class is advisory,
    because homographs are legitimate content.

    So the correct assertion is PHASE 1 UNSATISFIED, not `DUPLICATE_IDENTITY`.
    `test_t028_has_not_yet_admitted_phphoneme_to_the_roster` is the tripwire
    that makes the inertness stop reading as correctness once T028 lands."""

    @pytest.mark.parametrize("pair,groups", [("ngoreme", 20),
                                             ("ejagham", 21)])
    def test_the_duplicates_are_measured_and_recorded(self, pair, groups):
        row = measured_row(load_measured_census(pair), "PhPhoneme")
        duplicates = row["duplicates"]
        assert duplicates["groups"] == groups
        assert duplicates["extra_objects"] == groups
        assert len(duplicates["examples"]) == groups
        assert all(example["count"] == 2
                   for example in duplicates["examples"])
        assert all(len(set(example["guids"])) == 2
                   for example in duplicates["examples"])

    @pytest.mark.parametrize("pair", sorted(MEASURED_CENSUS_SNAPSHOTS))
    def test_duplicate_identity_does_not_fire_and_must_not_be_asserted(
            self, pair):
        artifact = load_measured_census(pair)
        row = measured_row(artifact, "PhPhoneme")
        assert row["duplicates"]["roster_admitted"] is False
        assert census.duplicates_unaccounted(row) == 0
        assert artifact["totals"]["duplicate_extra_objects"] == 0
        assert recompute_verdict(artifact) != "DUPLICATE_IDENTITY"
        assert row_passes(row) is True, (
            "the phoneme row PASSES on its own conditions -- which is exactly "
            "why the loss has to be caught somewhere else"
        )

    @pytest.mark.parametrize("pair,extra", [("ngoreme", 20), ("ejagham", 21)])
    def test_phase_1_catches_it_with_the_sc_002_wording(self, pair, extra):
        """`census.py`'s dedicated PhPhoneme check in `_phase_1`. Its wording
        is the whole point: SC-002 exists because count arithmetic alone
        cannot see a duplicated identity."""
        result = evaluate_phase(load_measured_census(pair), 1)
        assert result.satisfied is False
        matching = [f for f in result.failures
                    if "PhPhoneme" in f and "duplicates.extra_objects" in f]
        assert len(matching) == 1, result.failures
        failure = matching[0]
        assert "duplicates.extra_objects is " + str(extra) in failure
        assert "difference is 0" in failure
        assert "baseline arithmetic alone would have passed this row" in failure
        assert "SC-002" in failure

    @pytest.mark.parametrize("pair,extra", [("ngoreme", 20), ("ejagham", 21)])
    def test_the_inertness_is_roster_gating_not_a_broken_detector(
            self, pair, extra):
        """Admit the class on a COPY and the detector fires immediately, with
        the right count and the right verdict. So nothing is broken: the
        roster is simply not populated yet."""
        from copy import deepcopy

        artifact = deepcopy(load_measured_census(pair))
        row = measured_row(artifact, "PhPhoneme")
        row["duplicates"]["roster_admitted"] = True

        assert census.duplicates_unaccounted(row) == extra
        assert row_passes(row) is False
        assert recompute_verdict(artifact) == "DUPLICATE_IDENTITY"
        assert exit_code_for(recompute_verdict(artifact)) == 3
        assert gate_artifact(artifact).passed is False

    def test_t028_has_not_yet_admitted_phphoneme_to_the_roster(self):
        """THE TRIPWIRE. This test FAILS THE MOMENT T028 lands, and that is
        its job: the moment `PhPhoneme` is admitted, the two snapshots above
        become stale (they were measured with `roster_admitted: false`) and
        the duplicate assertions must be re-run and moved from "phase 1
        unsatisfied" to `DUPLICATE_IDENTITY` / exit 3.

        Without this, a future reader finds `duplicate_extra_objects: 0` and
        reads DESIGNED INERTNESS as A CLEAN RESULT."""
        roster = json.loads(
            (_repo_root() / "specs" / "035-fullsweep-fidelity" / "contracts"
             / "natural-key-identity-roster.json").read_text(encoding="utf-8")
        )
        admitted = tuple(entry["class"] for entry in roster["entries"])
        assert admitted == (
            "WfiWordform", "ReversalIndex", "ReversalIndexEntry"), (
            "035's natural-key roster changed. If T028 landed, REGENERATE "
            "tests/integration/_snapshots/census-038-*.json and move the "
            "duplicate assertions in "
            "TestDuplicatePhonemesAreInertUntilT028 from 'phase 1 "
            "unsatisfied' to DUPLICATE_IDENTITY / exit 3. Do not simply "
            "update this list."
        )
        assert "PhPhoneme" not in admitted

    def test_the_038_proposal_exists_and_names_phphoneme(self):
        """The other half of the T028 dependency: the extension document is
        written, so the inertness is a SEQUENCING fact with an owner, not an
        oversight nobody noticed."""
        extension = json.loads(
            (_repo_root() / "specs" / "038-transfer-fidelity-gaps"
             / "contracts" / "natural-key-roster-extension.json"
             ).read_text(encoding="utf-8")
        )
        proposed = [entry["class"]
                    for entry in extension["proposed_entries"]]
        assert "PhPhoneme" in proposed
        assert extension["target_file"] == (
            "specs/035-fullsweep-fidelity/contracts/"
            "natural-key-identity-roster.json")

    def test_ngoreme_has_20_groups_not_21_because_bh_is_a_distinct_key(self):
        """The 20-vs-21 gap is the instrument being MORE right than the brief.
        A writing-system-agnostic scan finds three `b` phonemes in `Ngoreme
        Target`, but the third is `{en: "b", ngq: "bh"}` and `ngq` is the
        default vernacular -- so its key is `bh`, not a duplicate.
        `census._ws_handle_for`'s no-fallback rule is what stops a match being
        fabricated out of the English alternative."""
        ngoreme = measured_row(load_measured_census("ngoreme"), "PhPhoneme")
        ejagham = measured_row(load_measured_census("ejagham"), "PhPhoneme")

        for row in (ngoreme, ejagham):
            assert row["duplicates"]["key_definition"] == (
                "Name (default vernacular alt), exact and case-sensitive")

        keys = [example["key"] for example in ngoreme["duplicates"]["examples"]]
        assert keys.count("b") == 1
        assert "bh" not in keys
        assert len(keys) == 20 == len(set(keys))
        assert len(ejagham["duplicates"]["examples"]) == 21


# ---------------------------------------------------------------------------
# A locked project is a verdict, not a traceback (hermetic)
# ---------------------------------------------------------------------------

class TestALockedProjectIsACensusError:
    """During T024 both target projects were open in FieldWorks and the first
    census attempt CORRECTLY refused with `FP_FileLockedError`. Reading a
    half-written `.fwdata` and reporting counts from it would be far worse
    than failing. Pinned without a live project by raising at the one seam
    that opens one."""

    def test_a_locked_project_is_census_error_exit_7(self, tmp_path,
                                                     monkeypatch, capsys):
        class FP_FileLockedError(Exception):  # noqa: N801 -- flexicon's name
            pass

        def refuse(project_name):
            raise FP_FileLockedError(
                "The FieldWorks project is locked: " + project_name)

        monkeypatch.setattr(census_cli, "_read_only_handle", refuse)
        code = census_cli.main([
            "run",
            "--source", "Ngoreme FLEx",
            "--destination", "Ngoreme Target",
            "--out", str(tmp_path / "census.json"),
        ])
        assert code == exit_code_for("CENSUS_ERROR") == 7
        combined = capsys.readouterr()
        assert "FP_FileLockedError" in combined.out + combined.err

    def test_the_locked_refusal_is_not_a_passing_verdict(self):
        assert is_passing_verdict("CENSUS_ERROR") is False
        assert exit_code_for("CENSUS_ERROR") == 7


# ---------------------------------------------------------------------------
# The one LIVE test: the corrected premise no artifact can settle
# ---------------------------------------------------------------------------

def _live_projects_root() -> Path:
    return Path("C:/ProgramData/SIL/FieldWorks/Projects")


def _live_project_or_skip(name: str) -> Path:
    root = _live_projects_root()
    fwdata = root / name / (name + ".fwdata")
    if not fwdata.is_file():
        pytest.skip("live project not on this machine: " + str(fwdata))
    if (root / name / (name + ".fwdata.lock")).exists():
        pytest.skip(
            "live project " + repr(name) + " is locked by FieldWorks; the "
            "census correctly refuses a locked project (FP_FileLockedError -> "
            "CENSUS_ERROR exit 7), so this test skips rather than measuring a "
            "half-written file"
        )
    return fwdata


class TestCorrectedPremiseNgoremeFlexIsTheSource:
    """tasks.md named `Ngoreme` as the 1949-object source. It is not:
    `Ngoreme` holds 1945 MoStemMsa / 37 PhPhoneme, and `Ngoreme FLEx` holds
    exactly 1949 / 41. The snapshots pin `Ngoreme FLEx`; only a live open can
    pin that `Ngoreme` is a DIFFERENT project, which is what stops a future
    reader "correcting" the name back."""

    @pytest.mark.integration
    def test_ngoreme_flex_holds_1949_and_ngoreme_holds_1945(self):
        """Read-only, both projects, digests checked before open and after
        close. Neither is a transfer target, so nothing here can write."""
        import hashlib

        pytest.importorskip(
            "flexicon", reason="the FlexTools host is not available")

        expected = {"Ngoreme FLEx": (1949, 41), "Ngoreme": (1945, 37)}
        paths = {name: _live_project_or_skip(name) for name in expected}

        def digest(path: Path) -> str:
            return hashlib.sha256(path.read_bytes()).hexdigest()

        before = {name: digest(path) for name, path in paths.items()}
        # NOT asserted equal to MEASURED_PROJECT_DIGESTS. That constant means
        # "the digest the COMMITTED SNAPSHOT was measured at" and must stay
        # fixed for `TestMeasuredCensusSnapshots`; this test does not read the
        # snapshot at all -- it opens both projects and counts them itself, so
        # a moved file makes it MORE useful, not less. Measured 2026-08-19: the
        # user edited `Ngoreme FLEx` between the snapshot and this run, and the
        # premise survived unchanged (1949/41 and 1945/37 both still exact), so
        # a hard digest equality here would have failed a test whose subject
        # was still true. Drift is reported, and read-only-ness is proved by
        # the before/after comparison below rather than by a recorded constant.
        if before["Ngoreme FLEx"] != MEASURED_PROJECT_DIGESTS["Ngoreme FLEx"]:
            print("[INFO] `Ngoreme FLEx` has moved since the committed "
                  "snapshot was measured (" + before["Ngoreme FLEx"][:12]
                  + "... vs " + MEASURED_PROJECT_DIGESTS["Ngoreme FLEx"][:12]
                  + "...). The counts below are measured live, so the premise "
                  "is still settled here; it is the SNAPSHOT-based blocks that "
                  "stand down on drift, via `_t024_census`.")

        measured = {}
        for name in expected:
            handle = census_cli._read_only_handle(name)  # noqa: SLF001
            try:
                counts = census.count_classes(
                    handle, ("MoStemMsa", "PhPhoneme"))
                measured[name] = (counts.count_for("MoStemMsa"),
                                  counts.count_for("PhPhoneme"))
            finally:
                handle.CloseProject()

        assert measured == expected, (
            "the corrected premise no longer holds: measured " + repr(measured)
        )
        after = {name: digest(path) for name, path in paths.items()}
        assert after == before, "a read-only census changed a .fwdata"

        snapshot = load_measured_census("ngoreme")
        assert measured["Ngoreme FLEx"] == (
            measured_row(snapshot, "MoStemMsa")["source_count"],
            measured_row(snapshot, "PhPhoneme")["source_count"],
        )


# ---------------------------------------------------------------------------
# T024c -- the sanity check PRODUCES the transfer it measures
# ---------------------------------------------------------------------------
#
# `_t024_census` above censuses two projects AS THEY HAPPEN TO SIT ON DISK.
# Nothing else in this file restores a target or executes a transfer, so the
# destination's provenance lives only in a session log: touch either project
# and the suite measures a different, equally unattributable delta while still
# claiming to be a sanity check. A sanity check for an instrument that gates
# transfers must itself produce the transfer.
#
# The corrected shape, which the code already supports end to end:
#
#   restore_target("Ngoreme Target", <0831 backup>)
#     -> census run --pre-transfer --destination ... --out pre.json
#     -> run_full_transfer(..., exclude=frozenset(), ws_mapping_mode="full",
#                          report_path=report.json)
#     -> census run --source ... --destination ... --baseline pre.json
#                   --run-report report.json --out post.json
#
# Two corrections to earlier drafts of this block, both measured:
#
#   * `--destination-freshly-created` was NOT a false declaration on the old
#     runs. The 0831 backup is a genuinely blank starter (LexEntry 0,
#     LexSense 0, MoStemMsa 0, PhPhoneme 23, PartOfSpeech 5) and
#     `census.baseline_misdeclared` tests the DECLARATION, not emptiness at
#     census time. It is dropped below only because a `--pre-transfer`
#     baseline measures the destination directly and makes the declaration
#     redundant -- not because it was untrue.
#   * A `pre_transfer_census` baseline does NOT lift the 5.2 verdict cap, and
#     neither does `--run-report` on its own. The cap keys off
#     `starter_subtraction_basis`, and only classes the run report can
#     ATTRIBUTE reach `baseline_matched` (T024d-b). The assertions below say so
#     explicitly rather than letting a future reader expect CENSUS_CLEAN.
#
# DESTRUCTIVE: this restores and writes `Ngoreme Target`. It is gated on
# GRAMTRANS_E2E=1 like every other live-write module in this suite, and on an
# anchored allowlist, so a bare `pytest tests/integration` can never fire it.

T024C_SOURCE = "Ngoreme FLEx"
T024C_DESTINATION = "Ngoreme Target"

#: Deny-by-default, anchored FULL match. The destination is the only project
#: this block may ever open write-enabled, and it may never equal the source.
T024C_WRITE_ALLOWLIST = frozenset({"Ngoreme Target"})

T024C_BACKUP_RELPATH = "backups/Ngoreme Target 2026-08-19 0831.fwbackup"

_T024C_CACHE: dict = {}


def _t024c_backup() -> Path:
    """The 0831 starter backup, wherever this checkout can reach it.

    `backups/` is NOT shared across git worktrees and is not tracked, so a
    feature worktree has no copy of it -- which is precisely why an earlier
    sweep concluded the backup did not exist and mis-blamed the
    `--destination-freshly-created` declaration. Look in this checkout first,
    then in the MAIN worktree, which `git worktree list --porcelain` names
    authoritatively rather than by guessing a sibling directory name.
    """
    here = _repo_root() / T024C_BACKUP_RELPATH
    if here.is_file():
        return here
    import subprocess  # noqa: PLC0415

    try:
        out = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=str(_repo_root()), capture_output=True, text=True, check=True,
        ).stdout
    except Exception:  # noqa: BLE001
        return here
    for line in out.splitlines():
        if line.startswith("worktree "):
            candidate = Path(line[len("worktree "):].strip()) / T024C_BACKUP_RELPATH
            if candidate.is_file():
                return candidate
            break  # the FIRST worktree line is the main one; do not scan on
    return here


def _t024c_assert_write_safe(destination: str, source: str) -> None:
    """035 FR-011/FR-012: the write target is checked, not assumed."""
    assert destination in T024C_WRITE_ALLOWLIST, (
        "refusing to write " + repr(destination) + " -- not in the anchored "
        "allowlist " + repr(sorted(T024C_WRITE_ALLOWLIST))
    )
    assert destination != source, (
        "refusing a transfer whose destination IS its source")


def _t024c_live_run() -> dict:
    """Restore -> pre-census -> transfer -> post-census, once per session.

    Returns `{"pre", "post", "report", "plan", "run_report_path"}`. Skips --
    never errors -- on every absence this machine can present.
    """
    if "result" in _T024C_CACHE:
        cached = _T024C_CACHE["result"]
        if isinstance(cached, str):
            pytest.skip(cached)
        return cached

    def refuse(reason: str):
        _T024C_CACHE["result"] = reason
        pytest.skip(reason)

    if os.environ.get("GRAMTRANS_E2E") != "1":
        refuse("T024c: GRAMTRANS_E2E != 1; set it to opt into the live "
               "restore-and-transfer run that this sanity check requires")
    if importlib.util.find_spec("flexicon") is None:
        refuse("T024c: flexicon not importable; no live FLEx host here")

    _t024c_assert_write_safe(T024C_DESTINATION, T024C_SOURCE)

    backup = _t024c_backup()
    if not backup.is_file():
        refuse("T024c: no starter backup at " + str(backup))
    for name in (T024C_SOURCE, T024C_DESTINATION):
        path = _t024_fwdata(name)
        if not path.is_file():
            refuse("T024c: project " + repr(name) + " has no .fwdata at "
                   + str(path))
    # Only the DESTINATION's lock is disqualifying, and the asymmetry is
    # measured rather than assumed: a read-only flexicon open of a project
    # FieldWorks holds open SUCCEEDS (the whole T024 block above censuses
    # `Ngoreme FLEx` while FieldWorks has it), but a restore cannot replace a
    # locked `.fwdata` and a write-enabled open cannot take it. A locked source
    # is still recorded, because the destination's provenance is only as exact
    # as the source it was read from.
    dest_lock = Path(str(_t024_fwdata(T024C_DESTINATION)) + ".lock")
    if dest_lock.exists():
        refuse(
            "T024c: the destination " + repr(T024C_DESTINATION) + " is locked "
            "by FieldWorks -- a restore cannot replace a locked .fwdata and a "
            "write-enabled open cannot take it. Close it and re-run.")
    source_locked = Path(str(_t024_fwdata(T024C_SOURCE)) + ".lock").exists()
    if source_locked:
        print("[WARN] T024c: the source " + repr(T024C_SOURCE) + " is open in "
              "FieldWorks. The read-only open still succeeds and the on-disk "
              ".fwdata is a committed state, but any UNSAVED edit in that "
              "session is invisible here -- recorded, not assumed away.")

    harness_dir = str(_repo_root() / "tests" / "integration")
    if harness_dir not in sys.path:
        sys.path.insert(0, harness_dir)
    try:
        from harness import full_run, restore  # noqa: PLC0415
    except Exception as exc:  # noqa: BLE001
        refuse("T024c: live harness unimportable: " + repr(exc))

    import tempfile  # noqa: PLC0415

    workdir = Path(tempfile.mkdtemp(prefix="gt038-t024c-"))
    pre = workdir / "pre.json"
    post = workdir / "post.json"
    run_report = workdir / "report.json"

    # 1. Restore the destination blank. This is what binds the measurement to a
    #    known starting state instead of to whatever the last session left.
    try:
        restore.restore_target(T024C_DESTINATION, backup_path=backup)
    except Exception as exc:  # noqa: BLE001
        refuse("T024c: restore failed: " + repr(exc))

    # 2. Pre-transfer census of the DESTINATION ONLY -> the exact baseline.
    #    `starter_baseline_count` becomes MEASURED rather than modelled.
    code = cli_exit(["run", "--pre-transfer",
                     "--destination", T024C_DESTINATION,
                     "--out", str(pre)])
    if not pre.is_file():
        refuse("T024c: the pre-transfer census wrote no artifact (exit "
               + str(code) + ")")

    # 3. The transfer this block exists to measure. `exclude=frozenset()`
    #    because a FULL copy must not exclude STEMS -- the default does.
    #    `ws_mapping_mode="full"` because an unmapped source alternative
    #    carries a handle the target cannot resolve (T024g).
    _t024c_assert_write_safe(T024C_DESTINATION, T024C_SOURCE)
    try:
        plan, report = full_run.run_full_transfer(
            T024C_SOURCE, T024C_DESTINATION,
            str(_t024_fwdata(T024C_DESTINATION).parent),
            exclude=frozenset(),
            ws_mapping_mode="full",
            report_path=str(run_report),
        )
    except Exception as exc:  # noqa: BLE001
        refuse("T024c: the transfer raised: " + type(exc).__name__ + ": "
               + str(exc))

    # 4. Post-transfer census, judged against the measured baseline AND the run
    #    report that names the run.
    code = cli_exit(["run",
                     "--source", T024C_SOURCE,
                     "--destination", T024C_DESTINATION,
                     "--baseline", str(pre),
                     "--run-report", str(run_report),
                     "--out", str(post)])
    if not post.is_file():
        refuse("T024c: the post-transfer census wrote no artifact (exit "
               + str(code) + ")")

    result = {
        "pre": json.loads(pre.read_text(encoding="utf-8")),
        "post": json.loads(post.read_text(encoding="utf-8")),
        "report": report,
        "plan": plan,
        "run_report_path": run_report,
        "exit_code": code,
        "source_locked": source_locked,
        "workdir": workdir,
    }
    _T024C_CACHE["result"] = result
    return result


@pytest.mark.integration
class TestT024cTheSanityCheckProducesItsOwnTransfer:
    """The live half of T024, rebuilt so the thing measured is a transfer this
    test performed, from a backup it restored, attributed to one named run."""

    def test_the_baseline_is_measured_not_declared(self):
        """`--pre-transfer` censuses the destination directly, so
        `starter_baseline_count` is a measurement of the project about to be
        written -- not a model of what a blank project ships with."""
        result = _t024c_live_run()
        pre = result["pre"]
        kinds = {pre.get("baseline_kind"), pre.get("kind"),
                 (pre.get("baseline") or {}).get("kind")}
        assert "pre_transfer_census" in kinds, (
            "the pre-transfer artifact does not declare itself a "
            "pre_transfer_census baseline: " + repr(sorted(pre)))

    def test_the_destination_is_attributable_to_this_run(self):
        """The pairing is ENFORCED, not conventional. The run report names the
        run, and the census artifact cites it."""
        result = _t024c_live_run()
        block = result["post"].get("transfer_run") or {}
        assert block.get("run_id"), (
            "the post-transfer census carries no transfer_run.run_id, so "
            "nothing in it could be cited as evidence")
        assert block["run_id"] == result["report"].context.run_id
        assert Path(block["report_path"]) == result["run_report_path"]

    def test_the_meaningful_delta_is_the_unaccounted_rows(self):
        """THE reading T024's disk-state census could not produce. Every row
        whose `difference` is non-zero and which the run report does not
        account for is a candidate loss with a named owner -- reproducible from
        a backup and attributable to one run."""
        result = _t024c_live_run()
        rows = result["post"].get("classes", ())
        assert rows, "the post-transfer census produced no class rows"

        unaccounted = [
            {"class": r.get("class"),
             "difference": r.get("difference"),
             "basis": r.get("starter_subtraction_basis"),
             "verdict": r.get("verdict_class"),
             "unexplained_shortfall": r.get("unexplained_shortfall"),
             "unexplained_surplus": r.get("unexplained_surplus")}
            for r in rows
            if r.get("difference")
            and (r.get("unexplained_shortfall") or r.get("unexplained_surplus"))
        ]
        # Reported, not asserted empty: this block's job is to make the delta
        # MEANINGFUL. A non-empty list is a finding for the phase gates
        # (T038/T039) to act on, not a failure of the instrument.
        print("[INFO] T024c unaccounted rows: %d" % len(unaccounted))
        for row in unaccounted[:40]:
            print("[INFO]   %s" % (row,))

        assert all(isinstance(r.get("difference"), int) for r in rows), (
            "every row must carry an integer difference for the delta to be "
            "readable at all")

    def test_the_cap_survives_a_measured_baseline(self):
        """Pinned because two earlier drafts of T024c got this wrong in
        opposite directions. A `pre_transfer_census` baseline does NOT lift the
        5.2 verdict cap, and neither does supplying `--run-report`: only rows
        the report can ATTRIBUTE reach `baseline_matched` (T024d-b). So a class
        the report does not cover stays on `baseline_gross`, and the run
        verdict stays capped at CENSUS_ACCOUNTED."""
        result = _t024c_live_run()
        bases = {r.get("starter_subtraction_basis")
                 for r in result["post"].get("classes", ())}
        assert bases <= {"baseline_gross", "baseline_matched", None}, (
            "unexpected subtraction basis token(s): " + repr(sorted(
                b for b in bases if b is not None)))
        verdict = result["post"].get("verdict")
        assert verdict != "CENSUS_CLEAN" or "baseline_gross" not in bases, (
            "CENSUS_CLEAN was reported while at least one row was still on the "
            "gross basis -- the 5.2 cap did not fire")

    def test_the_transfer_actually_persisted(self):
        """T024g's regression guard, in the place that would notice. A report
        claiming additions over a byte-identical destination is the silent-loss
        class this whole feature exists to eliminate.

        The two sides are read from DIFFERENT shapes on purpose, and getting
        that wrong is how this assertion goes quietly vacuous: a
        `--pre-transfer` artifact is a BASELINE document (`kind`,
        `entries[{class,count,names}]`, `content_hash`) and carries no
        `classes` array at all, while the post artifact is a census
        (`classes[{destination_count_total,...}]`). Summing `classes` on the
        baseline yields 0 and would make any comparison pass."""
        result = _t024c_live_run()
        pre_entries = result["pre"].get("entries", ())
        assert pre_entries, (
            "the pre-transfer baseline carries no entries -- it is not a "
            "measurement of anything")
        pre_total = sum(int(e.get("count") or 0) for e in pre_entries)
        post_total = sum(int(r.get("destination_count_total") or 0)
                         for r in result["post"].get("classes", ()))
        added = sum(int(getattr(c, "added", 0) or 0)
                    for c in (result["report"].per_category or {}).values())
        print("[INFO] T024c destination totals: pre=%d post=%d report_added=%d"
              % (pre_total, post_total, added))
        assert added > 0, (
            "the run report claims no additions at all, so this run measured "
            "nothing -- that is a broken harness, not a clean transfer")
        assert post_total > pre_total, (
            "the run report claims " + str(added) + " additions but the "
            "destination census total did not grow (" + str(pre_total)
            + " -> " + str(post_total) + ") -- nothing persisted (T024g)")

    def test_no_row_reaches_the_matched_basis_before_phase_4(self):
        """MEASURED 2026-08-19, and the reason the verdict is still capped
        even though `--run-report` WAS supplied.

        The report carries `matched_to_source.total: 1806`, but
        `by_object_class` is `{}` and `complete` is False: all 1,806 matches
        landed in `unattributed_by_category` (SEMANTIC_DOMAINS 1792,
        COMPLEX_FORM_TYPES 7, VARIANT_TYPES 7). T024d-a attributes ONLY from
        `MatchBasisRecord.object_class` and `EnrichmentRecord.object_class`,
        and Phase 4 (T028-T037) has not landed, so NO `MatchBasisRecord` is
        produced at all -- every match is unattributable BY CONSTRUCTION, and
        T024d-b's conservative rule then forbids `baseline_matched` on every
        row.

        So the chain is: no matcher -> no attribution -> no `baseline_matched`
        -> the 5.2 cap fires on every row -> the verdict cannot exceed
        CENSUS_ACCOUNTED. This is T024d behaving exactly as specified ("an
        absent tally is no evidence the matcher ran -- never a zero"), not a
        defect in it. It is pinned here because it is the sequencing fact that
        makes the phase gates T038/T039 unreachable until Phase 4 lands, and
        because a reader who supplies `--run-report` and still sees a capped
        verdict deserves to find the reason written down rather than rediscover
        it."""
        result = _t024c_live_run()
        matched = (json.loads(
            result["run_report_path"].read_text(encoding="utf-8"))
            .get("matched_to_source") or {})
        assert matched.get("total"), (
            "the run matched nothing at all; this test's premise no longer "
            "holds and the chain below needs re-deriving")
        assert matched.get("by_object_class") == {} , (
            "a per-class matched tally EXISTS now -- Phase 4 has landed. "
            "Re-run this block: rows the report covers should reach "
            "baseline_matched and the cap should stop firing on them.")
        assert matched.get("complete") is False
        bases = {r.get("starter_subtraction_basis")
                 for r in result["post"].get("classes", ())}
        assert bases == {"baseline_gross"}, (
            "not every row is on the gross basis any more: " + repr(bases))
        assert result["post"].get("verdict") == "CENSUS_ACCOUNTED"


# ---------------------------------------------------------------------------
# T039 -- SC-008 IDEMPOTENCE, MEASURED ON A SECOND LIVE RUN
#
# Re-measured 2026-08-20 after enrichment (T042..T047) landed. The earlier
# measurement (journal/T039-idempotence.md) could evaluate only two of the
# three criteria because enrichment did not yet exist; this block is the
# re-run that criterion 3 was waiting for.
#
# The pair is two CONSECUTIVE full transfers of `Ejagham Mini` into a
# `GT038 T039c Target` restored pristine from the committed starter backup --
# no restore between the runs, which is the whole point.
#
# WHAT THE THREE CRITERIA MEASURED:
#
#   1. run 2 plans no PlannedAction whose `match_basis.basis` is
#      `MatchBasis.NONE` for any class run 1 created  -- PASS, and by the
#      widest possible margin: run 2 plans ZERO actions of any kind.
#   2. every class's `destination_count_total` is unchanged -- PASS on all
#      75 census entries (74 classes plus the A1 `FsFeatStrucType` split).
#   3a. every `EnrichedCollection.added == 0` on run 2 -- PASS, strictly:
#      all 10 collections across run 2's 4 enrichment records read 0.
#   3b. `already_present` equal to run 1's `added` -- **PASS**, on 10
#      collections across 3 objects, every one equal. This became evaluable
#      only with T048e; before it, the criterion could not be answered at all.
#
# WHY 3b NEEDED T048e FIRST. The two runs enrich DISJOINT object sets, and
# inherently so: run 1 enriches Noun / Pronoun / Verb (the starter POSes it
# filled), run 2 finds those complete and enriches Adjective / Demonstrative /
# Numeral / Interrogative instead (POSes run 1 CREATED). So the enrichment
# surface alone can NEVER answer 3b -- the objects it asks about are not on it.
#
# On run 2 those three arrive at `_plan_gold_reserved_edit` (`categories.py`),
# whose owned-collection pass runs BEFORE either early skip and finds every
# collection already complete. T043 was working all along: the comparison
# happens, so the constitutional SKIP clause (data-model.md 9 -- "emitting SKIP
# requires that every scalar field and all seven owned collections were
# compared") was satisfied. The gap was evidentiary, not decisional -- the
# computed `collections` tuple, holding exactly the `already_present` tallies
# 3b wants, was DISCARDED, and the skip detail named only the writing-system
# slots ("all WS slots equal."). T048e carries it on
# `Skip.collections_compared`, and 3b reads BOTH surfaces.
#
# The basis drift these runs also show (`PhPhoneme` and `PhNCSegments` losing
# `baseline_matched` on run 2 while their counts do not move) is NOT a T039
# criterion and is filed separately as T048f. T039's own text forecloses
# reading it as a failure here: "Any increase is a duplicate-creation defect
# REGARDLESS of what either census's own verdict says."
# ---------------------------------------------------------------------------

T039_SNAPSHOT = "idempotence-038-t039.json"

#: The three POSes run 1 enriched, and the four run 2 enriched. Pinned as
#: labels because the emptiness of the intersection is the finding.
T039_RUN1_ENRICHED_LABELS = frozenset({"Noun", "Pronoun", "Verb"})
T039_RUN2_ENRICHED_LABELS = frozenset(
    {"Adjective", "Demonstrative", "Numeral", "Interrogative"})


def t039_snapshot_path() -> Path:
    return Path(__file__).resolve().parent / "_snapshots" / T039_SNAPSHOT


def load_t039_snapshot() -> dict:
    path = t039_snapshot_path()
    assert path.is_file(), (
        "the T039 idempotence snapshot is missing: " + str(path)
        + " -- it is committed repo data recording a two-run live "
        "measurement, not a regenerable temp file; restore it from git "
        "rather than re-running two full transfers"
    )
    return json.loads(path.read_text(encoding="utf-8"))


class TestT039IdempotenceIsMeasured:
    """SC-008 read off the committed two-run measurement. No live project."""

    def test_the_snapshot_is_committed_repo_data(self):
        path = t039_snapshot_path()
        root = Path(__file__).resolve().parents[2]
        assert (root / "tests" / "integration" / "_snapshots") == path.parent

    def test_the_snapshot_records_two_consecutive_runs_on_one_destination(self):
        snap = load_t039_snapshot()
        assert sorted(snap["runs"]) == ["run1", "run2"]
        assert snap["source"] == "Ejagham Mini"
        assert snap["destination"] == "GT038 T039d Target"
        # A restore between the runs would void the whole measurement; the
        # starter digest is recorded once because there is ONE restore.
        assert snap["starter_baseline_digest"] == "ab37b1cd60dd"
        assert (snap["runs"]["run1"]["census_id"]
                != snap["runs"]["run2"]["census_id"])

    # -- criterion 1 ------------------------------------------------------
    def test_criterion_1_run_2_plans_no_creation_at_all(self):
        """Zero actions is the strong form of "no PlannedAction with basis
        NONE": there is no action of any basis to inspect."""
        snap = load_t039_snapshot()
        assert snap["runs"]["run1"]["plan_action_count"] == 329
        assert snap["runs"]["run2"]["plan_action_count"] == 0
        assert snap["runs"]["run2"]["plan_actions_by_class_and_basis"] == {}

    def test_criterion_1_is_unfalsifiable_as_literally_written(self):
        """The criterion names `match_basis.basis is MatchBasis.NONE`, but NO
        `PlannedAction` carries a `match_basis` at all -- `transfer.py` says so
        in as many words ("With `match_basis=None` (every plan built today)").
        Run 1's 329 actions are all unattributed, so a duplicate create on run
        2 would arrive with `match_basis is None`, and `None.basis` is not
        `MatchBasis.NONE`. The load-bearing assertion is therefore the action
        COUNT above, not the basis predicate. Pinned so that a later reader
        does not mistake the basis clause for a working tripwire, and so that
        populating `PlannedAction.match_basis` trips this test rather than
        silently making the clause meaningful."""
        snap = load_t039_snapshot()
        by_basis = snap["runs"]["run1"]["plan_actions_by_class_and_basis"]
        assert by_basis == {"<unattributed>|None": 329}, (
            "run 1's actions now carry a match_basis -- criterion 1's basis "
            "clause has become meaningful and should be asserted directly "
            "instead of leaning on the action count: " + repr(by_basis))

    # -- criterion 2 ------------------------------------------------------
    def test_criterion_2_every_destination_count_is_unchanged(self):
        snap = load_t039_snapshot()
        a = snap["runs"]["run1"]["destination_count_total"]
        b = snap["runs"]["run2"]["destination_count_total"]
        assert set(a) == set(b), (
            "the two censuses do not cover the same entries: "
            + repr(sorted(set(a) ^ set(b))))
        assert len(a) == 75, (
            "expected 74 classes plus the A1 FsFeatStrucType split, got "
            + str(len(a)))
        changed = {k: (a[k], b[k]) for k in a if a[k] != b[k]}
        assert changed == {}, (
            "a re-run changed a destination count -- SC-008 is broken and "
            "this is a duplicate-creation defect regardless of either "
            "census's verdict: " + repr(changed))

    # -- criterion 3 ------------------------------------------------------
    def test_criterion_3a_run_2_adds_nothing_to_any_collection(self):
        snap = load_t039_snapshot()
        offenders = [
            (rec["label"], field, coll)
            for rec in snap["runs"]["run2"]["enrichments"]
            for field, coll in rec["collections"].items()
            if coll["added"] != 0
        ]
        assert offenders == [], (
            "run 2 added children to an owned collection: " + repr(offenders))

    def test_criterion_3a_run_2_dropped_nothing_either(self):
        """`dropped != 0` would mean a child could not be added on a re-run
        that should have needed no writes at all."""
        snap = load_t039_snapshot()
        offenders = [
            (rec["label"], field, coll)
            for rec in snap["runs"]["run2"]["enrichments"]
            for field, coll in rec["collections"].items()
            if coll["dropped"] != 0
        ]
        assert offenders == []

    def test_the_two_runs_enrich_disjoint_object_sets(self):
        """Inherent to idempotence, not a defect: run 1 fills the three starter
        POSes, run 2 finds those complete and instead enriches the four POSes
        run 1 CREATED. So the enrichment surface alone can never answer 3b --
        which is why T048e made the skip surface carry the other half."""
        snap = load_t039_snapshot()
        r1 = {r["source_guid"]: r for r in snap["runs"]["run1"]["enrichments"]}
        r2 = {r["source_guid"]: r for r in snap["runs"]["run2"]["enrichments"]}
        assert {r["label"] for r in r1.values()} == T039_RUN1_ENRICHED_LABELS
        assert {r["label"] for r in r2.values()} == T039_RUN2_ENRICHED_LABELS
        assert set(r1) & set(r2) == set()

    def test_criterion_3b_run_2_already_has_exactly_what_run_1_added(self):
        """The criterion, evaluated -- what T048e unblocked.

        Run 2's `already_present` is read from BOTH surfaces: the enrichment
        records, and (T048e) the `collections_compared` evidence on the
        identity skips, which is where the three objects run 1 enriched report
        on a re-run. Measured: 10 collections across 3 objects, every one
        equal."""
        snap = load_t039_snapshot()
        gained = {r["source_guid"]: r["collections"]
                  for r in snap["runs"]["run1"]["enrichments"]}
        have = {}
        for rec in snap["runs"]["run2"]["enrichments"]:
            have.setdefault(rec["source_guid"], {}).update(
                {f: c["already_present"] for f, c in rec["collections"].items()})
        for guid, colls in snap["runs"]["run2"][
                "skip_collections_compared"].items():
            have.setdefault(guid, {}).update(
                {f: c["already_present"] for f, c in colls.items()})

        assert set(gained) <= set(have), (
            "an object run 1 enriched has NO run-2 record on either surface, "
            "so 3b is unevaluable again: "
            + repr(sorted(set(gained) - set(have))))

        mismatches = [
            (guid, field, coll["added"], have[guid].get(field))
            for guid, colls in gained.items()
            for field, coll in colls.items()
            if have[guid].get(field) != coll["added"]
        ]
        assert mismatches == [], (
            "run 2 does not already hold exactly what run 1 added -- "
            "(guid, field, run1_added, run2_already_present): "
            + repr(mismatches))
        # Pin the shape too, so the assertion above cannot pass vacuously on a
        # future run that records nothing.
        assert len(gained) == 3
        assert sum(len(c) for c in gained.values()) == 10

    def test_criterion_3b_is_not_vacuous_the_skip_surface_carries_it(self):
        """3b passes only because T048e exists. If `collections_compared` were
        dropped again, the three objects would vanish from run 2 entirely and
        the test above would fail on its `set(gained) <= set(have)` guard --
        this pins the mechanism directly so the reason stays visible."""
        snap = load_t039_snapshot()
        run1_guids = {r["source_guid"]
                      for r in snap["runs"]["run1"]["enrichments"]}
        evidence = snap["runs"]["run2"]["skip_collections_compared"]
        assert run1_guids <= set(evidence), (
            "the run-1 enriched objects are not carrying T048e evidence on "
            "run 2: " + repr(sorted(run1_guids - set(evidence))))
        # And the evidence really is a no-op record, not a disguised write.
        for guid in run1_guids:
            for field, coll in evidence[guid].items():
                assert coll["added"] == 0, (guid, field)
                assert coll["dropped"] == 0, (guid, field)

    def test_the_totals_coincide_but_that_is_not_criterion_3b(self):
        """Both runs total 16 children, which is a coincidence of this corpus
        and NOT evidence for 3b -- the 16 belong to different objects. Pinned
        so nobody promotes the coincidence into a pass."""
        snap = load_t039_snapshot()
        added1 = sum(c["added"]
                     for rec in snap["runs"]["run1"]["enrichments"]
                     for c in rec["collections"].values())
        already2 = sum(c["already_present"]
                       for rec in snap["runs"]["run2"]["enrichments"]
                       for c in rec["collections"].values())
        assert added1 == 16 and already2 == 16

        # ... and the per-collection distributions differ, which is the proof
        # that the equal totals are not the same 16 children.
        def by_field(tag, key):
            out = {}
            for rec in snap["runs"][tag]["enrichments"]:
                for field, coll in rec["collections"].items():
                    out[field] = out.get(field, 0) + coll[key]
            return out

        assert by_field("run1", "added") != by_field("run2", "already_present")

    # -- the drift that is NOT a T039 criterion (evidence for T048f) ------
    def test_two_rows_lose_the_matched_basis_on_run_2_without_moving(self):
        """`PhPhoneme` and `PhNCSegments` keep identical destination counts and
        still fall from `baseline_matched` to `baseline_gross`, manufacturing a
        21-object and a 2-object phantom shortfall. Filed as T048f: the
        `matched_complete` signal is a single GLOBAL boolean, while T048b's
        equivalent withholding is bounded to the classes actually at risk."""
        snap = load_t039_snapshot()
        r1, r2 = snap["runs"]["run1"], snap["runs"]["run2"]
        drifted = {
            k: (r1["starter_subtraction_basis"][k],
                r2["starter_subtraction_basis"][k])
            for k in r1["starter_subtraction_basis"]
            if (r1["starter_subtraction_basis"][k]
                != r2["starter_subtraction_basis"][k])
        }
        assert drifted == {
            "PhPhoneme": ("baseline_matched", "baseline_gross"),
            "PhNCSegments": ("baseline_matched", "baseline_gross"),
        }, repr(drifted)
        for cls in ("PhPhoneme", "PhNCSegments"):
            assert (r1["destination_count_total"][cls]
                    == r2["destination_count_total"][cls]), cls
            assert r2["starter_matched_to_source"][cls] is None, cls

    def test_the_run_report_still_holds_the_tallies_the_census_refused(self):
        """T048f's whole point: the counts are NOT missing from run 2's report
        -- `by_object_class` carries `PhPhoneme: 21` and `PhNCSegments: 2`,
        identical to run 1. They are refused because 11 matches in three OTHER
        categories went unattributed and `matched_complete` is global."""
        snap = load_t039_snapshot()
        for tag in ("run1", "run2"):
            block = snap["runs"][tag]["matched_to_source"]
            assert block["by_object_class"]["PhPhoneme"] == 21, tag
            assert block["by_object_class"]["PhNCSegments"] == 2, tag
        assert snap["runs"]["run1"]["matched_to_source"]["complete"] is True
        assert snap["runs"]["run2"]["matched_to_source"]["complete"] is False
        assert (snap["runs"]["run2"]["matched_to_source"]
                ["unattributed_by_category"]
                == {"GRAM_CATEGORIES": 5, "INFLECTION_FEATURES": 5,
                    "VARIANT_TYPES": 1})

    def test_partofspeech_does_NOT_drift_because_T048b_and_T048d_reach_it(self):
        """The contrast that localises T048f. `PartOfSpeech` holds
        `baseline_matched` on BOTH runs -- T048d's GUID audit rescues it
        because its starters match by GUID. The audit cannot rescue
        `PhPhoneme`: a natural-key match links objects with DIFFERENT GUIDs,
        so a GUID-set comparison is blind to it by construction. That is why
        T048f needs the bounded-withholding fix and not another audit."""
        snap = load_t039_snapshot()
        for tag in ("run1", "run2"):
            basis = snap["runs"][tag]["starter_subtraction_basis"]
            assert basis["PartOfSpeech"] == "baseline_matched", tag
            assert snap["runs"][tag][
                "starter_matched_to_source"]["PartOfSpeech"] == 5, tag

    def test_the_three_run1_enriched_poses_are_skipped_on_run_2(self):
        """Where they go on a re-run: all three are among run 2's eleven
        GRAM_CATEGORIES `ALREADY_PRESENT_BY_GUID` skips. The skip is correct --
        T043's collection pass ran and found nothing to write -- and since
        T048e it also carries the evidence of that comparison."""
        snap = load_t039_snapshot()
        r1_guids = {r["source_guid"]
                    for r in snap["runs"]["run1"]["enrichments"]}
        skipped = set(snap["runs"]["run2"]["gram_category_skips"])
        assert len(skipped) == 11
        assert r1_guids <= skipped, (
            "a POS enriched on run 1 is neither enriched nor skipped on run "
            "2: " + repr(sorted(r1_guids - skipped)))
