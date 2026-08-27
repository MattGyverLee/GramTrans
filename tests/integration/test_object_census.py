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
6. The closed 17-token reason vocabulary: no `UNEXPLAINED`, no `OTHER`, and
   exactly four tokens exempt from `report_ref`.

THE SURFACE T015-T021 MUST CREATE (this file is the specification of it)
-----------------------------------------------------------------------
`gramtrans.Lib.census`:

- `CENSUS_SCHEMA_VERSION: int`                          -- 1
- `REASON_TOKENS: tuple[str, ...] | frozenset[str]`     -- the closed 17
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
import tempfile
from pathlib import Path

import pytest

# Deliberately at module scope: collection must fail with a legible
# ModuleNotFoundError naming the not-yet-written census modules.
from gramtrans.Lib.census import (  # noqa: F401  (imported for the contract)
    CENSUS_SCHEMA_VERSION,
    CensusError,
    GROSS_BASIS_CAPPED_VERDICTS,
    GROSS_BASIS_VERDICT_CAP,
    GROSS_SUBTRACTION_BASIS,
    PASSING_VERDICTS,
    PHASE_1_MATCHED_CLASSES,
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
    phase_classes,
    phase_scoped_suppressions,
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
    # Appended by contract commit b2cb356 (2026-08-20). APPEND-ONLY: this
    # tuple is transcribed from `$defs.reasonToken.enum` in enum order, and
    # `test_tokens_match_the_schema_enum_exactly` compares the two as LISTS,
    # so a reorder here is a failure even when the sets agree.
    "SOURCE_REFERENT_ABSENT",
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
#
# T110 CARVED ONE CASE OUT OF THE RULE QUOTED ABOVE, and the two citations are
# left verbatim because they are citations -- the contract now states the
# carve-out at the same lines. A row whose `starter_baseline_count` is an
# integer 0 from a real `baseline_document` is NOT capped: there is no starter
# object to double-subtract, so the paragraph below does not describe it and
# gross computes the EXACT difference rather than an upper bound. Absent or
# `null`, or any other `starter_baseline_source`, stays capped -- absent is not
# zero. `census.is_gross_basis_row` is the one predicate all of it turns on,
# which is why the helpers below have to name a nonzero baseline to build a
# genuinely capped row.
# ===========================================================================

def gross_basis_rows(rows=None, *, phoneme_baseline=23, baselines=None):
    """`rows` (default `phase_rows()`) rewritten as a no-run-report census: no
    `starter_matched_to_source`, gross subtraction, no match_basis tallies.

    `baselines` names the classes whose starter baseline is NONZERO, which
    since T110 is what makes a gross-basis row actually capped: over a baseline
    of 0 the gross and matched bases compute the same integer, so
    `is_gross_basis_row` returns False and the row's shortfall is evidence.
    Every class not named gets 0, which is a MEASURED zero here -- these rows
    all carry `starter_baseline_source: "baseline_document"` -- so the default
    output is a census of exact rows plus one capped `PhPhoneme`.
    """
    rows = list(phase_rows() if rows is None else rows)
    counts = {"PhPhoneme": phoneme_baseline}
    counts.update(baselines or {})
    for row in rows:
        row["starter_baseline_count"] = counts.get(row["class"], 0)
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
        free to drift from the first.

        The row carries a NONZERO baseline (T110): a gross basis over a
        baseline of 0 subtracts nothing and is exact, so the sign question
        would not even arise on a zero-baseline row. net = 13 - 4 = 9 against a
        source of 3, so `difference` +6."""
        rows = gross_basis_rows(
            replace_row(
                phase_rows(), "MoInflClass", source_count=3,
                destination_count_total=13, destination_count_net=9,
                verdict_class="SURPLUS", unexplained_surplus=6),
            baselines={"MoInflClass": 4})
        artifact = gross_basis_artifact(rows)
        assert gross_basis_suppressions(artifact) == (
            ("MoInflClass", "surplus", 6),)
        assert recompute_verdict(artifact) == "CENSUS_ACCOUNTED"
        assert gate_artifact(artifact).exit_code == 0


# ===========================================================================
# 3a-bis. T110 -- a ZERO starter baseline is not a gross basis
#
# 5.2's cap exists for ONE arithmetic error: gross subtraction removes the
# starter objects the transfer correctly MATCHED, once as starter objects and
# once as the source objects they now stand in for, so it reports a shortfall on
# a correct run (43 - 23 = 20 against a source of 41). Where the baseline is a
# measured ZERO that error is impossible -- nothing is subtracted, so nothing
# can be subtracted twice, and `total - 0` on the gross basis equals
# `total - (0 - 0)` on the matched one. The row is exact and its shortfall is
# evidence.
#
# THREE STATES, NOT TWO. What separates the exempt row from the still-capped one
# is the corroboration, not the arithmetic: an `absent_from_baseline` row also
# subtracts 0, but because nobody counted rather than because there was nothing
# to count. Its true starter population is unknown, so its arithmetic is not
# exact and the cap keeps applying. The tests below pin all three states, and
# the ABSENT one is the regression that matters -- reading a missing count as a
# measured zero is the "absent read as zero" error `census.unmatched_starter`
# was written to refuse.
# ===========================================================================

class TestT110AZeroBaselineIsNotAGrossBasis:
    """The predicate, one state per test, on forged rows."""

    def test_a_measured_zero_is_exact_so_the_row_is_not_capped(self):
        """State 1. `MoStemMsa` 5 -> 0 over a baseline document that says 0 for
        it: `starter_excluded` 0, net == total, and the two bases agree to the
        integer. The 5 is a loss, not arithmetic noise."""
        rows = gross_basis_rows(replace_row(
            phase_rows(), "MoStemMsa", source_count=5,
            destination_count_total=0, destination_count_net=0,
            verdict_class="SHORTFALL", unexplained_shortfall=5))
        row = [r for r in rows if r["class"] == "MoStemMsa"][0]
        assert row["starter_subtraction_basis"] == GROSS_SUBTRACTION_BASIS
        assert row["starter_baseline_count"] == 0
        assert row["starter_baseline_source"] == "baseline_document"
        assert row["destination_count_net"] == row["destination_count_total"]
        assert is_gross_basis_row(row) is False
        # The identity the whole task turns on, spelled out rather than argued:
        # gross and matched compute the same net.
        gross = row["destination_count_total"] - row["starter_baseline_count"]
        matched = row["destination_count_total"] - (
            row["starter_baseline_count"] - 0)
        assert gross == matched == row["destination_count_net"]

    def test_an_absent_baseline_count_is_still_capped(self):
        """State 2, and THE regression. No `starter_baseline_count` key at all
        -- what `baseline.is_missing` and an Amendment A1 split row both
        produce -- must NOT be read as a measured zero. Absent is not zero, so
        the row stays capped and its shortfall stays advisory."""
        rows = gross_basis_rows(replace_row(
            phase_rows(), "MoStemMsa", source_count=5,
            destination_count_total=0, destination_count_net=0,
            verdict_class="SHORTFALL", unexplained_shortfall=5))
        for row in rows:
            if row["class"] == "MoStemMsa":
                del row["starter_baseline_count"]
                row["starter_baseline_source"] = "absent_from_baseline"
        row = [r for r in rows if r["class"] == "MoStemMsa"][0]
        assert "starter_baseline_count" not in row
        assert is_gross_basis_row(row) is True
        assert ("MoStemMsa", "shortfall", 5) in gross_basis_suppressions(
            gross_basis_artifact(rows))

    def test_a_present_but_null_count_is_still_capped(self):
        """The same refusal one notch subtler. `$defs.classRow` types
        `starter_baseline_count` as `["integer", "null"]`, so a null can be
        PRESENT -- and a null is a missing measurement wearing a key. Key
        presence alone would therefore have been the wrong test."""
        rows = gross_basis_rows(replace_row(
            phase_rows(), "MoStemMsa", source_count=5,
            destination_count_total=0, destination_count_net=0,
            verdict_class="SHORTFALL", unexplained_shortfall=5))
        for row in rows:
            if row["class"] == "MoStemMsa":
                row["starter_baseline_count"] = None
        row = [r for r in rows if r["class"] == "MoStemMsa"][0]
        assert is_gross_basis_row(row) is True

    def test_a_zero_without_the_document_corroboration_is_still_capped(self):
        """And the third way to get a zero that is not a measurement: a 0 whose
        `starter_baseline_source` does not say a baseline document produced it.
        The exemption is a claim the artifact has to MAKE, exactly as the cap
        is -- the predicate's own first rule, applied in the other
        direction."""
        rows = gross_basis_rows(replace_row(
            phase_rows(), "MoStemMsa", source_count=5,
            destination_count_total=0, destination_count_net=0,
            verdict_class="SHORTFALL", unexplained_shortfall=5))
        for row in rows:
            if row["class"] == "MoStemMsa":
                row["starter_baseline_source"] = "absent_from_baseline"
        assert is_gross_basis_row(
            [r for r in rows if r["class"] == "MoStemMsa"][0]) is True
        for row in rows:
            if row["class"] == "MoStemMsa":
                del row["starter_baseline_source"]
        assert is_gross_basis_row(
            [r for r in rows if r["class"] == "MoStemMsa"][0]) is True

    def test_a_nonzero_baseline_is_unchanged(self):
        """State 3, untouched: 5.2's own worked example. A baseline of 23 CAN be
        over-subtracted, so the phantom 21 stays suppressed and the run stays
        `CENSUS_ACCOUNTED`. If this ever moved, T110 would have broken the cap
        rather than bounded it."""
        artifact = gross_basis_artifact()
        row = [r for r in artifact["classes"] if r["class"] == "PhPhoneme"][0]
        assert row["starter_baseline_count"] == 23
        assert is_gross_basis_row(row) is True
        assert gross_basis_suppressions(artifact) == (
            ("PhPhoneme", "shortfall", 21),)
        assert recompute_verdict(artifact) == "CENSUS_ACCOUNTED"
        assert gate_artifact(artifact).exit_code == 0

    def test_the_latent_consequence_a_duplicate_free_run_no_longer_passes(
            self):
        """THE LATENT DEFECT T110 NAMES, forged to size. An artifact with no
        duplicates, no errors, no stale baseline and no accounting lines --
        nothing at all that could outrank the cap -- whose ONLY failure is a
        zero-baseline shortfall. Before T110 the cap suppressed it and the run
        read `CENSUS_ACCOUNTED` / exit 0; now it reads `UNEXPLAINED_SHORTFALL` /
        exit 1.

        Measured on T078's three artifacts the same change moved 2602 / 57,955 /
        8849 objects out of "advisory" and altered no verdict, because
        `DUPLICATE_IDENTITY` outranks the cap on all three. That is why the
        defect survived: the only artifacts that could show it are the
        duplicate-free ones, and the two committed pre-fix censuses -- see
        `TestCappedExitZeroCoexistsWithFailingRows` -- are exactly those.
        """
        rows = gross_basis_rows(replace_row(
            phase_rows(), "MoStemMsa", source_count=90,
            destination_count_total=0, destination_count_net=0,
            verdict_class="SHORTFALL", unexplained_shortfall=90))
        artifact = gross_basis_artifact(rows)
        assert not any(census.duplicates_unaccounted(r) for r in artifact["classes"])
        assert not artifact.get("errors")
        assert not any(r["accounted_for"] for r in artifact["classes"])
        assert recompute_verdict(artifact) == "UNEXPLAINED_SHORTFALL"
        assert gate_artifact(artifact).exit_code == 1
        assert gate_artifact(artifact).passed is False
        # The 90 is no longer announced as advisory, and the note array says so.
        assert not any(label == "MoStemMsa" for label, _, _
                       in gross_basis_suppressions(artifact))

    def test_the_same_run_over_a_real_baseline_still_reads_accounted(self):
        """The falsifier for the test above, and the proof T110 did not simply
        delete the cap: give that same 90-object shortfall a starter baseline of
        90 -- a baseline big enough for gross subtraction to have manufactured
        the whole thing -- and the run is capped back to `CENSUS_ACCOUNTED`."""
        rows = gross_basis_rows(
            replace_row(
                phase_rows(), "MoStemMsa", source_count=90,
                destination_count_total=90, destination_count_net=0,
                verdict_class="SHORTFALL", unexplained_shortfall=90),
            baselines={"MoStemMsa": 90})
        artifact = gross_basis_artifact(rows)
        assert recompute_verdict(artifact) == "CENSUS_ACCOUNTED"
        assert gate_artifact(artifact).exit_code == 0
        assert ("MoStemMsa", "shortfall", 90) in gross_basis_suppressions(
            artifact)

    def test_the_cap_notes_and_the_exit_code_move_together(self):
        """T024b's rule, which is why T110 is one predicate and not three call
        sites: the cap, the notes it renders and `census_cli`'s capped-pass exit
        code must never disagree about which rows are capped. On the
        zero-baseline artifact the de-capped row appears in NONE of the three."""
        rows = gross_basis_rows(replace_row(
            phase_rows(), "MoStemMsa", source_count=90,
            destination_count_total=0, destination_count_net=0,
            verdict_class="SHORTFALL", unexplained_shortfall=90))
        artifact = gross_basis_artifact(rows)
        assert not any("MoStemMsa" in note
                       for note in gross_basis_cap_notes(artifact))
        assert not any("MoStemMsa" in note
                       for note in artifact["notes"])
        # ...and it is still in the row evidence, where it belongs.
        row = [r for r in artifact["classes"] if r["class"] == "MoStemMsa"][0]
        assert row["unexplained_shortfall"] == 90
        assert row_passes(row) is False

    def test_the_declared_basis_string_is_never_rewritten(self):
        """The one thing T110 must NOT touch. `starter_subtraction_basis` stays
        `baseline_gross` on a de-capped row, because that is the subtraction the
        census actually performed and the artifact's arithmetic has to stay
        reproducible from what it published -- the validator's invariant 4 and
        `SUBTRACTION_BASES` are both written against that vocabulary. The
        predicate reads the string; it never edits it."""
        rows = gross_basis_rows(replace_row(
            phase_rows(), "MoStemMsa", source_count=90,
            destination_count_total=0, destination_count_net=0,
            verdict_class="SHORTFALL", unexplained_shortfall=90))
        artifact = gross_basis_artifact(rows)
        for row in artifact["classes"]:
            assert row["starter_subtraction_basis"] == GROSS_SUBTRACTION_BASIS
            assert row["starter_subtraction_basis"] in census.SUBTRACTION_BASES
        assert validate_artifact(artifact) == ()
        assert census.BASELINE_SOURCE_DOCUMENT in census.BASELINE_SOURCES


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
# 5. The closed 17-token reason vocabulary
# ===========================================================================

class TestReasonVocabulary:
    def test_exactly_seventeen_tokens(self):
        """16 until contract commit b2cb356 appended `SOURCE_REFERENT_ABSENT`.
        The count moves ONLY alongside the schema; it is pinned so an
        accidental token cannot arrive without this line being touched."""
        assert len(EXPECTED_REASON_TOKENS) == 17
        assert set(REASON_TOKENS) == set(EXPECTED_REASON_TOKENS)
        assert len(set(REASON_TOKENS)) == 17

    def test_tokens_match_the_schema_enum_exactly(self, census_schema):
        enum = census_schema["$defs"]["reasonToken"]["enum"]
        assert list(enum) == list(EXPECTED_REASON_TOKENS)
        assert set(REASON_TOKENS) == set(enum)

    def test_the_source_side_token_is_emittable_and_schema_valid(
            self, census_schema):
        """T096. A vocabulary member nothing can emit is not a vocabulary
        member; it is a comment in an enum. `SOURCE_REFERENT_ABSENT` is the
        newest member and the one with no live producer in any corpus this
        feature can reach today (measured: 0 `MoInflAffMsa` and 0
        `MoDerivAffMsa` with a null required POS across `Ngoreme FLEx`,
        `Ejagham W Mini`, `Mbugwe LizzieHC practice` and `Esperanto`), so the
        emit path is pinned HERE rather than left to a live run that cannot
        currently exercise it."""
        rows = replace_row(
            phase_rows(), "MoStemMsa",
            source_count=164, destination_count_total=162,
            destination_count_net=162, verdict_class="SHORTFALL",
            accounted_for=[make_accounted(
                "SOURCE_REFERENT_ABSENT", 2, "shortfall")])
        artifact = make_artifact(rows, verdict="CENSUS_ACCOUNTED")

        assert schema_errors(artifact, census_schema) == []
        assert list(validate_artifact(artifact)) == []
        assert artifact["schema_version"] == 1, (
            "b2cb356 appended the token WITHOUT bumping schema_version, and "
            "an append is exactly what the schema's own EVOLUTION RULE "
            "$comment sanctions"
        )

    def test_the_two_referent_absent_tokens_are_distinct(self):
        """They name opposite sides of the transfer. `DEPENDENCY_UNRESOLVED`
        is absence in the DESTINATION (FR-017); `SOURCE_REFERENT_ABSENT` is
        absence on the SOURCE. Collapsing them -- which is what stamping the
        least-wrong token did -- makes the artifact unable to say which."""
        assert "DEPENDENCY_UNRESOLVED" in REASON_TOKENS
        assert "SOURCE_REFERENT_ABSENT" in REASON_TOKENS
        assert reason_requires_report_ref("SOURCE_REFERENT_ABSENT") is True

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
    def test_the_duplicates_DO_raise_the_verdict_now_that_t028_landed(
            self, pair):
        """T024's finding, INVERTED by T028 -- and the inversion is the point.

        T024's brief expected `DUPLICATE_IDENTITY` (severity above the
        gross-basis cap, exit 3) here, and it did NOT fire. The reason was
        neither the cap nor a bug: `PhPhoneme` was not in 035's natural-key
        roster, so `duplicates.roster_admitted` was False and
        `census.duplicates_unaccounted` returned 0 for unadmitted classes BY
        DESIGN -- "a duplicate name on an unadmitted class is advisory, because
        homographs are legitimate content" (census.py). The consequence was a
        real gap: `totals.duplicate_extra_objects` read 0 on a destination
        holding 20-21 duplicate phonemes, and only the phase-1 predicate in the
        test above stopped the transfer being called done.

        T028 admitted `PhPhoneme` (2026-08-19, commit `d8635d9`), and this test
        is what that closes. It reads a LIVE census, so `roster_admitted` is
        derived from the roster as it stands at run time (`census.py:1810`) --
        no re-derivation helper needed here, unlike the committed snapshots in
        `TestDuplicatePhonemesWereInertUntilT028Landed`, which predate the
        landing and are kept as the before-picture.

        The old assertion's own remedy note demanded exactly this rewrite, and
        `test_admitting_phphoneme_to_the_roster_makes_the_duplicates_fail`
        proved beforehand that admission was the ONLY thing in the way -- so
        census.py is untouched, as predicted.

        The headline total is asserted as `>=` the phoneme count, not `==`:
        T028 admitted six classes, and `PhNCFeatures` / `PhNCSegments` carry
        duplicates of their own on these pairs."""
        artifact = _t024_census(*pair)
        row = _t024_row(artifact, "PhPhoneme")
        expected = T024_EXPECTED_PHONEME_DUPLICATES[pair]

        assert "PhPhoneme" in census.roster_admitted_classes(_repo_root()), (
            "PhPhoneme has LEFT 035's roster -- its duplicates would be "
            "advisory again, so this test must go back to the pre-T028 "
            "expectation it replaced")
        assert row["duplicates"]["roster_admitted"] is True
        assert census.duplicates_unaccounted(row) == expected
        assert census.row_passes(row) is False
        assert census.gate_artifact(artifact).verdict == "DUPLICATE_IDENTITY"
        assert census.exit_code_for(
            census.gate_artifact(artifact).verdict) == 3
        assert artifact["totals"]["duplicate_extra_objects"] >= expected, (
            "the artifact's headline duplicate tally counts admitted classes "
            "only, and T028 admitted six -- so it is at least the "
            + str(expected) + " phoneme duplicates, plus any PhNCFeatures / "
            "PhNCSegments duplicates on this pair")

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
# 2. `DUPLICATE_IDENTITY` for the duplicate phonemes -- on the snapshot AS
#    STORED. It did not fire while `PhPhoneme` was off 035's roster, and
#    the raw fixtures still carry that pre-admission derivation. T028 has
#    since landed, so the verdict IS asserted now, against the re-derived
#    artifact -- see `TestDuplicatePhonemesWereInertUntilT028Landed`.
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


#: The date `PhPhoneme` and five siblings joined 035's roster (T028, commit
#: `d8635d9`, 2026-08-19 22:15). The two measured snapshots were committed at
#: 13:47 the SAME DAY, so their stored `duplicates.roster_admitted: false` was
#: correct when written and is stale now.
ROSTER_T028_LANDED_AT = "2026-08-19T22:15:04"

#: What T028 admitted, in the roster's own order. Pinned so a later change to
#: 035's roster is visible here rather than silently altering what
#: `with_current_roster_admission` derives.
T028_ADMITTED_CLASSES = (
    "PhPhoneme", "PhNCSegments", "PhNCFeatures",
    "PartOfSpeech", "MoMorphType", "LexEntryInflType",
)


def with_current_roster_admission(artifact) -> dict:
    """A COPY of `artifact` with `duplicates.roster_admitted` re-derived from
    035's roster AS IT STANDS TODAY.

    `roster_admitted` is not a measurement. `census._class_row` computes it at
    run time as `name in roster_admitted_classes()` (`census.py:1810`), and
    `roster_admitted_classes` reads the roster file precisely so that "the six
    entries feature 038 proposes (T028) become gate-failing the moment 035
    merges them, with no edit here" (`census.py:1604`). The stored flag is a
    cached derivation, and T028 landed AFTER these snapshots were written.

    So this is not forging a measurement: it re-runs the one derived field
    against the current roster and refreshes the one total that reads it
    (`census.py:2708`), leaving every measured count -- groups, extra objects,
    example GUIDs, differences -- exactly as measured. It is what a census
    would derive today from the same observations.

    What it deliberately does NOT do is stand in for a live re-census. Under
    natural-key matching the transfer should now MATCH those phonemes instead
    of duplicating them, so a real re-run would measure FEWER duplicates, not
    the same ones re-derived. That measurement is `038-NK-P3`, owned by T082.
    """
    from copy import deepcopy

    admitted = census.roster_admitted_classes(_repo_root())
    out = deepcopy(artifact)
    for row in out.get("classes", ()):
        duplicates = row.get("duplicates")
        if isinstance(duplicates, dict):
            duplicates["roster_admitted"] = row.get("class") in admitted
    totals = out.get("totals")
    if isinstance(totals, dict):
        totals["duplicate_extra_objects"] = sum(
            (r.get("duplicates") or {}).get("extra_objects", 0)
            for r in out.get("classes", ())
            if (r.get("duplicates") or {}).get("roster_admitted")
        )
    return out


def with_recomputed_verdict(artifact) -> dict:
    """A COPY of `artifact` with `verdict` / `exit_code` / `verdict_human_label`
    re-stamped from the artifact's own evidence.

    Same kind of refresh as `with_current_roster_admission` and for the same
    reason: those three fields are DERIVATIONS, not measurements --
    `census.stamp_verdict` is "the ONLY sanctioned way those three fields get
    their values" -- so re-running the derivation over unchanged counts is not
    forging anything. Every measured quantity is left exactly as measured.

    It exists because T110 changed the derivation. These snapshots were written
    while `is_gross_basis_row` said a row with a MEASURED-ZERO baseline was
    gross-basis, so their stored `CENSUS_ACCOUNTED` is the pre-T110 answer.
    Nothing about the observations changed; what changed is that the census no
    longer excuses arithmetic that could not have been wrong.
    """
    from copy import deepcopy

    return census.stamp_verdict(deepcopy(artifact))


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
        malformed document rather than measured evidence.

        Checked against the artifact's own re-derived verdict, because T110
        moved the derivation and these two files were written before it. Every
        MEASURED field is validated as it sits on disk; only the three derived
        verdict fields are refreshed. See `with_recomputed_verdict`."""
        assert validate_artifact(
            with_recomputed_verdict(load_measured_census(pair))) == ()

    @pytest.mark.parametrize("pair", sorted(MEASURED_CENSUS_SNAPSHOTS))
    def test_the_stored_verdict_is_the_pre_t110_answer_and_only_that(
            self, pair):
        """The one invariant the raw snapshot now breaks, named rather than
        tolerated. Invariant 8 is exactly "the gate recomputes the verdict
        rather than trusting it", so a stale stored token is what it is FOR --
        and the single failure it reports is the whole delta T110 made. If a
        later change adds a second failure here, this snapshot has a new problem
        that is not T110's."""
        raw = load_measured_census(pair)
        failures = validate_artifact(raw)
        assert len(failures) == 1, failures
        assert failures[0].startswith("invariant 8:")
        assert "stores verdict 'CENSUS_ACCOUNTED'" in failures[0]
        assert "own evidence gives 'UNEXPLAINED_SHORTFALL'" in failures[0]

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
        """5.2's cap is the RUN verdict only, and since T110 it does not reach
        this row at all. The declared basis is still `baseline_gross` -- that is
        the subtraction the census performed and the artifact has to stay
        reproducible from what it published -- but the baseline it subtracted
        was a MEASURED ZERO from the baseline document, so `total - 0` and
        `total - (0 - 0)` are the same integer and there is no over-subtraction
        for the cap to compensate for. `is_gross_basis_row` therefore says
        False, and the 1949 is evidence rather than advice."""
        row = measured_row(ngoreme_census, "MoStemMsa")
        assert row["starter_subtraction_basis"] == GROSS_SUBTRACTION_BASIS
        assert row["starter_baseline_count"] == 0
        assert row["starter_baseline_source"] == "baseline_document"
        assert row["destination_count_net"] == row["destination_count_total"]
        assert is_gross_basis_row(row) is False
        assert row["difference"] == -1949
        assert row["unexplained_shortfall"] == 1949
        assert row_passes(row) is False

    def test_the_same_row_would_still_be_capped_over_a_real_baseline(
            self, ngoreme_census):
        """The falsifier for the test above: the de-capping is the ZERO, not
        the class and not the size of the loss. Give the same row a starter
        baseline of 3 -- which is what an over-subtractable row looks like --
        and the cap applies again."""
        row = json.loads(json.dumps(measured_row(ngoreme_census, "MoStemMsa")))
        assert is_gross_basis_row(row) is False
        row["starter_baseline_count"] = 3
        assert is_gross_basis_row(row) is True

    def test_an_absent_baseline_count_is_not_a_measured_zero(
            self, ngoreme_census):
        """And the other falsifier, the one that matters more: T110 exempts a
        MEASURED zero, never a missing measurement. Drop the count key (or the
        `baseline_document` corroboration) and the row goes straight back to
        being capped -- absent is not zero, which is the same refusal
        `census.unmatched_starter` makes."""
        base = measured_row(ngoreme_census, "MoStemMsa")
        no_key = json.loads(json.dumps(base))
        no_key.pop("starter_baseline_count")
        assert is_gross_basis_row(no_key) is True
        nulled = json.loads(json.dumps(base))
        nulled["starter_baseline_count"] = None
        assert is_gross_basis_row(nulled) is True
        unmentioned = json.loads(json.dumps(base))
        unmentioned["starter_baseline_source"] = "absent_from_baseline"
        assert is_gross_basis_row(unmentioned) is True

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
        `MoAffixProcess` -> `MoAffixAllomorph` is not one of the 17 reason
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
# FINDING 2 -- the capped exit 0. Documented, then FIXED at the predicate.
#
# T024b recorded the surprise: both ruined pairs stamped `CENSUS_ACCOUNTED` /
# exit 0 while 44-47 rows failed and 7,357-74,157 units were unexplained,
# because the real baseline is count-only so EVERY row declared
# `baseline_gross` and on that basis a tally was "advisory rather than
# evidence". T110 found the half of that reasoning that was never true. The cap
# compensates for gross subtraction removing the MATCHED starter objects twice;
# on a row whose baseline document counted ZERO for its class there are none to
# remove, `total - 0` and `total - (0 - 0)` are the same integer, and the tally
# is exact. Those rows are the overwhelming majority here -- 31 of 44 on
# ejagham, 33 of 46 on ngoreme -- so both artifacts now recompute to
# `UNEXPLAINED_SHORTFALL` / exit 1.
#
# The class is kept, with its numbers moved, because the finding is still the
# thing worth pinning: the two snapshots STILL STORE the passing token they
# were stamped with, 13 rows apiece are still genuinely capped, and the gap
# between "stored" and "recomputed" is now the test evidence instead of a
# paragraph of prose. Nothing here may be read as "the transfer was fine".
# ---------------------------------------------------------------------------

class TestCappedExitZeroCoexistsWithFailingRows:
    """What the two snapshots stored, against what their evidence now gives."""

    @pytest.mark.parametrize("pair", sorted(MEASURED_CENSUS_SNAPSHOTS))
    def test_the_stored_verdict_still_says_the_run_passed(self, pair):
        """The instrument's own output, unedited. This is what a reader of the
        committed file sees, and it is why T110 is a correctness fix rather
        than a tightening: the document on disk claims exit 0."""
        artifact = load_measured_census(pair)
        assert artifact["verdict"] == GROSS_BASIS_VERDICT_CAP
        assert artifact["verdict"] == "CENSUS_ACCOUNTED"
        assert artifact["exit_code"] == 0
        assert is_passing_verdict(artifact["verdict"]) is True

    @pytest.mark.parametrize("pair", sorted(MEASURED_CENSUS_SNAPSHOTS))
    def test_the_recomputed_verdict_no_longer_passes(self, pair):
        """T110. The cap still applies to the 13 rows with a real nonzero
        baseline, so the token is not `CENSUS_CLEAN` and never could be -- but
        it no longer applies to the zero-baseline rows, and one unsuppressed
        required shortfall is all `UNEXPLAINED_SHORTFALL` needs."""
        artifact = load_measured_census(pair)
        assert recompute_verdict(artifact) == "UNEXPLAINED_SHORTFALL"
        assert is_passing_verdict(recompute_verdict(artifact)) is False
        assert gate_artifact(artifact).passed is False
        assert gate_artifact(artifact).exit_code == 1
        # Still a capped run, just not a capped PASS: the rows with a genuine
        # baseline to over-subtract keep their suppression.
        assert gross_basis_suppressions(artifact)

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
        # exit 1 since T110, and the rows are the reason rather than the
        # counterpoint to it.
        assert gate_artifact(artifact).exit_code == 1
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

    @pytest.mark.parametrize("pair,declared,de_capped", [
        ("ngoreme", 46, 33), ("ejagham", 44, 31)])
    def test_the_declared_basis_is_uniform_but_the_cap_is_not(
            self, pair, declared, de_capped):
        """Every row DECLARES `baseline_gross` -- the baseline is count-only, so
        no row could earn `baseline_matched` -- and that was once the whole
        story. Since T110 the declaration is necessary and not sufficient, and
        these artifacts hold all three states at once:

        * 12 rows with a NONZERO count from the baseline document: an
          over-subtraction really is possible, so the cap applies;
        * 1 row (an Amendment A1 `FsFeatStrucType` half) with NO count at all,
          `starter_baseline_source: "absent_from_baseline"`: still capped, and
          for the opposite reason -- nobody counted, so nothing is known, and
          reading that as a measured zero is the error the whole gate refuses;
        * 31 / 33 rows with a MEASURED ZERO: exact, and no longer capped.

        13 = 12 + 1, which is why the suppression count is not just the
        nonzero-baseline count."""
        artifact = load_measured_census(pair)
        bases = {row["starter_subtraction_basis"] for row in artifact["classes"]}
        assert bases == {GROSS_SUBTRACTION_BASIS}
        once_capped = [
            row for row in artifact["classes"]
            if row["gate_scope"] == "required"
            and (row.get("unexplained_shortfall", 0)
                 or row.get("unexplained_surplus", 0))
        ]
        assert len(once_capped) == declared
        still = [row for row in once_capped if is_gross_basis_row(row)]
        assert len(gross_basis_suppressions(artifact)) == len(still) == 13
        assert len(once_capped) - len(still) == de_capped

        nonzero = [row for row in still
                   if row["starter_baseline_source"] == "baseline_document"]
        unmeasured = [row for row in still
                      if row["starter_baseline_source"] == "absent_from_baseline"]
        assert len(nonzero) == 12
        assert all(row["starter_baseline_count"] > 0 for row in nonzero)
        assert [row["class"] for row in unmeasured] == ["FsFeatStrucType"]
        assert all("starter_baseline_count" not in row for row in unmeasured)

        # Every de-capped row is a MEASURED zero and nothing else -- no row
        # loses its cap for want of a baseline read.
        for row in once_capped:
            if row in still:
                continue
            assert row["starter_baseline_source"] == "baseline_document"
            assert row["starter_baseline_count"] == 0
            assert row["destination_count_net"] == row["destination_count_total"]

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
        """`--phase` refused these runs even while the default passed them,
        because the phase predicates were never relaxed by the cap. T110 makes
        the default agree with them; this test is what it agreed WITH."""
        artifact = load_measured_census(pair)
        assert gate_artifact(artifact).passed is False
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
        """The cap only ever removed the two tokens below its ceiling. Add a
        single error to the SAME artifact and it becomes CENSUS_ERROR -- which
        held while this artifact recomputed to `CENSUS_ACCOUNTED` and still
        holds now that it recomputes to `UNEXPLAINED_SHORTFALL`, because the
        ceiling was never a floor."""
        from copy import deepcopy

        assert recompute_verdict(ngoreme_census) == "UNEXPLAINED_SHORTFALL"
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

class TestDuplicatePhonemesWereInertUntilT028Landed:
    """21 duplicate phoneme names in the Ejagham destination (20 in Ngoreme).
    While `PhPhoneme` was absent from 035's natural-key roster,
    `duplicates.roster_admitted` was False, `duplicates_unaccounted()` returned
    0 BY DESIGN -- a duplicate name on an unadmitted class is advisory, because
    homographs are legitimate content -- and `DUPLICATE_IDENTITY` never fired.
    The correct assertion then was PHASE 1 UNSATISFIED.

    **T028 LANDED** (2026-08-19 22:15, commit `d8635d9`), admitting all six of
    038's proposed classes. The tripwire that guarded this block fired, and
    these tests are its remedy: the duplicate assertions have moved from
    "phase 1 unsatisfied" to `DUPLICATE_IDENTITY` / exit 3, derived through
    `with_current_roster_admission`.

    THE SNAPSHOTS ARE NOT REGENERATED, AND CANNOT BE. Three separate reasons,
    each sufficient:

    * `roster_admitted` is a DERIVED field, not a measurement
      (`census.py:1810`), so the stale flag needs re-deriving, not re-measuring.
    * The source projects have moved since: the T024 live block a few hundred
      lines up already skips itself because `Ejagham W Mini` and `Ngoreme FLEx`
      no longer match their recorded digests. A census run today measures a
      different world.
    * `Ngoreme Target` is pinned in `MEASURED_PROJECT_DIGESTS` as
      "irreplaceable evidence of a ruined transfer: it must never be
      write-enabled or restored".

    What a real re-run WOULD show is a different thing again, and better: under
    natural-key matching the transfer should match these phonemes instead of
    duplicating them, so the duplicates should largely disappear. That is
    `038-NK-P3` ("recovery verified by re-census"), owned by **T082**, and it
    is the measurement that will eventually replace these fixtures.

    NOT ONLY PhPhoneme. T028's remedy note named the phoneme row, but T028
    admitted six classes and three of them carry duplicates here, so the
    artifact-level total moves further than the row does -- see
    `test_admission_moves_the_headline_total_past_the_phoneme_row`."""

    @pytest.mark.parametrize("pair,groups", [("ngoreme", 20),
                                             ("ejagham", 21)])
    def test_the_duplicates_are_measured_and_recorded(self, pair, groups):
        """Unchanged by T028: these are OBSERVATIONS, and roster admission
        decides what they mean, never whether they happened."""
        row = measured_row(load_measured_census(pair), "PhPhoneme")
        duplicates = row["duplicates"]
        assert duplicates["groups"] == groups
        assert duplicates["extra_objects"] == groups
        assert len(duplicates["examples"]) == groups
        assert all(example["count"] == 2
                   for example in duplicates["examples"])
        assert all(len(set(example["guids"])) == 2
                   for example in duplicates["examples"])

    # -- the moved assertions ---------------------------------------------

    @pytest.mark.parametrize("pair,extra", [("ngoreme", 20), ("ejagham", 21)])
    def test_the_duplicates_are_now_gate_failing(self, pair, extra):
        """THE MOVED ASSERTION -- what the spent tripwire required. With
        `PhPhoneme` admitted, the same measurement yields `DUPLICATE_IDENTITY`
        and exit 3 rather than an advisory 0."""
        artifact = with_current_roster_admission(load_measured_census(pair))
        row = measured_row(artifact, "PhPhoneme")

        assert row["duplicates"]["roster_admitted"] is True
        assert census.duplicates_unaccounted(row) == extra
        assert row_passes(row) is False, (
            "the phoneme row used to PASS on its own conditions; admission is "
            "what makes the duplicated identity able to fail it")
        assert recompute_verdict(artifact) == "DUPLICATE_IDENTITY"
        assert exit_code_for(recompute_verdict(artifact)) == 3
        assert gate_artifact(artifact).passed is False

    @pytest.mark.parametrize("pair,phonemes,total", [("ngoreme", 20, 42),
                                                     ("ejagham", 21, 25)])
    def test_admission_moves_the_headline_total_past_the_phoneme_row(
            self, pair, phonemes, total):
        """T028 admitted SIX classes, and three of them carry duplicates in
        these snapshots -- `PhPhoneme`, `PhNCFeatures` and `PhNCSegments`. The
        remedy note named only the phoneme row, so pin the rest: Ngoreme's
        `PhNCFeatures` alone contributes 21 extra objects across 12 groups,
        slightly MORE than its 20 duplicate phonemes.

        `totals.duplicate_extra_objects` counts admitted classes only
        (`census.py:2708`), which is why a number that read 0 on a destination
        holding dozens of duplicates now reads the real figure."""
        artifact = with_current_roster_admission(load_measured_census(pair))

        assert artifact["totals"]["duplicate_extra_objects"] == total
        contributors = {
            row["class"]: row["duplicates"]["extra_objects"]
            for row in artifact["classes"]
            if (row.get("duplicates") or {}).get("roster_admitted")
            and row["duplicates"].get("extra_objects")
        }
        assert set(contributors) == {"PhPhoneme", "PhNCFeatures",
                                     "PhNCSegments"}
        assert contributors["PhPhoneme"] == phonemes
        assert sum(contributors.values()) == total

    @pytest.mark.parametrize("pair,extra", [("ngoreme", 20), ("ejagham", 21)])
    def test_phase_1_catches_it_with_the_sc_002_wording(self, pair, extra):
        """`census.py`'s dedicated PhPhoneme check in `_phase_1`, which reads
        `duplicates.extra_objects` and NOT admission -- so it caught this
        before T028 and still catches it after. Asserted on BOTH readings of
        the artifact, because the two surfaces are independent: this predicate
        is what stood between the inertness and a transfer being called done,
        and it must not quietly become redundant now the verdict fires too."""
        for artifact in (load_measured_census(pair),
                         with_current_roster_admission(
                             load_measured_census(pair))):
            result = evaluate_phase(artifact, 1)
            assert result.satisfied is False
            matching = [f for f in result.failures
                        if "PhPhoneme" in f and "duplicates.extra_objects" in f]
            assert len(matching) == 1, result.failures
            failure = matching[0]
            assert "duplicates.extra_objects is " + str(extra) in failure
            assert "difference is 0" in failure
            assert ("baseline arithmetic alone would have passed this row"
                    in failure)
            assert "SC-002" in failure

    # -- what the snapshots still record, and why it disagrees -------------

    @pytest.mark.parametrize("pair", sorted(MEASURED_CENSUS_SNAPSHOTS))
    def test_the_snapshot_still_stores_the_pre_admission_derivation(self, pair):
        """The BEFORE-PICTURE, asserted deliberately rather than tolerated.

        Read raw, the snapshot still says `roster_admitted: false` and
        `duplicate_extra_objects: 0` on a destination holding 20-21 duplicate
        phonemes. That was correct when written, and it is exactly the reading
        the old tripwire existed to stop anyone taking as a clean result. It
        stays because it is the measured state the fix gets compared against."""
        artifact = load_measured_census(pair)
        row = measured_row(artifact, "PhPhoneme")

        assert row["duplicates"]["roster_admitted"] is False
        assert census.duplicates_unaccounted(row) == 0
        assert artifact["totals"]["duplicate_extra_objects"] == 0
        assert recompute_verdict(artifact) != "DUPLICATE_IDENTITY"
        assert row_passes(row) is True

    @pytest.mark.parametrize("pair", sorted(MEASURED_CENSUS_SNAPSHOTS))
    def test_the_snapshots_predate_the_roster_landing(self, pair):
        """THE REPLACEMENT TRIPWIRE. The old one asked "has T028 landed yet?",
        and its answer is now permanently yes, so it can no longer detect
        anything. This asks the question that stays live: are these fixtures
        still the pre-admission measurement they are documented to be?

        It fires if a snapshot is regenerated -- at which point
        `roster_admitted` arrives already True, `with_current_roster_admission`
        becomes a no-op, and the before/after split this class is built on has
        to be retired rather than quietly kept."""
        artifact = load_measured_census(pair)
        assert artifact["generated_at"] < ROSTER_T028_LANDED_AT, (
            "a census-038 snapshot was regenerated after T028 landed. Its "
            "`roster_admitted` flags now come from the CURRENT roster, so "
            "`with_current_roster_admission` no longer changes anything and "
            "`test_the_snapshot_still_stores_the_pre_admission_derivation` is "
            "asserting a state that no longer exists. Retire the before/after "
            "split here rather than re-pointing this date."
        )

    def test_t028_has_landed_and_admitted_all_six_proposed_classes(self):
        """What replaced `test_t028_has_not_yet_admitted_phphoneme_to_the_
        roster`. That test's job was to FAIL the moment T028 landed; it did,
        and this records the outcome instead of re-arming a spent tripwire.

        The six are asserted as a SUBSET rather than as the roster's full
        ordered tuple, deliberately: pinning the exact list would fire again on
        any later 035 admission, and a seventh class joining is not by itself a
        reason to revisit these fixtures. What matters here is that 038's six
        are in, and that 035's original three were APPENDED to, not rewritten
        (the T028 journal pins 512 insertions, 0 deletions)."""
        roster = json.loads(
            (_repo_root() / "specs" / "035-fullsweep-fidelity" / "contracts"
             / "natural-key-identity-roster.json").read_text(encoding="utf-8")
        )
        admitted = tuple(entry["class"] for entry in roster["entries"])

        assert admitted[:3] == (
            "WfiWordform", "ReversalIndex", "ReversalIndexEntry")
        assert set(T028_ADMITTED_CLASSES) <= set(admitted)
        assert "PhPhoneme" in admitted
        assert census.roster_admitted_classes(_repo_root()) >= frozenset(
            T028_ADMITTED_CLASSES)

    def test_the_detector_was_never_broken_only_ungated(self):
        """The old `test_the_inertness_is_roster_gating_not_a_broken_detector`
        proved this by flipping the flag ON. Now that admission is real, prove
        it the other way: force the flag back OFF and the inertness returns
        exactly. Neither reading is a code path that rotted -- both are the
        roster speaking, which is the design."""
        artifact = with_current_roster_admission(
            load_measured_census("ejagham"))
        assert recompute_verdict(artifact) == "DUPLICATE_IDENTITY"

        for row in artifact["classes"]:
            duplicates = row.get("duplicates")
            if isinstance(duplicates, dict):
                duplicates["roster_admitted"] = False
        artifact["totals"]["duplicate_extra_objects"] = 0

        assert census.duplicates_unaccounted(
            measured_row(artifact, "PhPhoneme")) == 0
        assert recompute_verdict(artifact) != "DUPLICATE_IDENTITY"

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
    # T090, second site. The PRESENCE of `<project>.fwdata.lock` was the whole
    # test here too, and it is not a fact about a file -- it is a claim about a
    # process. Every driver that opens a project read-only and exits without
    # closing leaves that claim behind naming a dead PID, and this refusal then
    # turns live coverage into skips for no reason. `read_project_lock` asks
    # whether the recorded PID is still running and answers asymmetrically:
    # only a PID that is DEFINITIVELY gone unlocks the project, so a live
    # FieldWorks session is still refused. Nothing here deletes a lock file.
    import sys as _sys  # noqa: PLC0415

    _here = str(Path(__file__).resolve().parent)
    if _here not in _sys.path:
        _sys.path.insert(0, _here)
    from harness import full_run  # noqa: PLC0415

    lock = full_run.read_project_lock(name, projects_root=root)
    if lock.blocks_open:
        pytest.skip(
            "live project " + repr(name) + " is locked; the census correctly "
            "refuses a locked project (FP_FileLockedError -> CENSUS_ERROR "
            "exit 7), so this test skips rather than measuring a half-written "
            "file -- " + lock.detail
        )
    if lock.state == full_run.LOCK_STALE:
        print("[WARN] %s: %s -- measuring anyway (T090)" % (name, lock.detail))
    return fwdata


#: T103. An APPEND-ONLY ledger of `sha256(.fwdata) -> (MoStemMsa, PhPhoneme)`.
#:
#: The test below used to assert `{'Ngoreme FLEx': (1949, 41), 'Ngoreme':
#: (1945, 37)}` outright. `Ngoreme FLEx` is a project a human is still working
#: in, and that number moved three times -- 1949 when the test was written,
#: 1952 at T087, 1953 at T100/T101 -- so what kept failing was never the claim
#: the test is named for but the decision to hardcode an exact count of a
#: living project. (The 1952 reading has no row here: it was observed in a
#: failure message, and no digest was recorded with it. A count without the
#: bytes it was counted from is exactly what this ledger exists to stop.)
#:
#: Keying on the digest is what makes the number safe to keep. At UNCHANGED
#: bytes an exact count is a real tripwire -- the same file must count the same
#: way, and a counting regression would show here. At CHANGED bytes it is a
#: statement about a file that no longer exists, so the block stands down and
#: REPORTS, which is what `_t024_census` already does for snapshot-based
#: blocks. Appending a row is optional and never required to keep the suite
#: green; nothing needs re-pinning when the user edits a project again.
#:
#: The PREMISE is asserted unconditionally, below, against whatever is on disk.
_NGOREME_OBSERVATIONS = {
    "Ngoreme FLEx": {
        # 2026-08-19: the digest the committed `ngoreme` snapshot was measured
        # at (`MEASURED_PROJECT_DIGESTS['Ngoreme FLEx']`).
        "052243ea76405eed520c17e3d61562f09fa5efd171f65eb02f1abf1c8f09843b":
            (1949, 41),
        # 2026-08-22, T103: the user edited the project. MoStemMsa moved,
        # PhPhoneme did not, and the premise is untouched either way.
        "e10a44ef1b745e59e13f86e37f1fbda2f9b15eebd08ce4b0bcba53e3bd6ef330":
            (1953, 41),
    },
    "Ngoreme": {
        # 2026-08-22, T103. `Ngoreme` has read 1945/37 on every run since
        # 2026-08-19; this is the first one to record the bytes it read them
        # from, which is what lets the exact pair stay asserted.
        "6d35c9575fc6094089dff757da4f54f266aa5a0d7e4ea16cd1fd3bd64abe472d":
            (1945, 37),
    },
}


class TestCorrectedPremiseNgoremeFlexIsTheSource:
    """tasks.md named `Ngoreme` as the 1949-object source. It is not.

    The premise, and the whole of it: `Ngoreme FLEx` and `Ngoreme` are
    DIFFERENT projects, and `Ngoreme FLEx` is the larger one -- more MoStemMsa
    AND more PhPhoneme. The snapshots pin `Ngoreme FLEx`; only a live open can
    pin that `Ngoreme` is a different project, which is what stops a future
    reader "correcting" the name back.

    T103: the premise is asserted against whatever is on disk. The exact counts
    are asserted only against bytes they were actually measured from -- see
    `_NGOREME_OBSERVATIONS`.
    """

    @pytest.mark.integration
    def test_every_recorded_observation_satisfies_the_premise(self):
        """Offline, and it runs on a host with no FieldWorks at all.

        The digest gate below can stand down; this cannot. It stops the ledger
        from becoming a place where a row that CONTRADICTS the premise could be
        appended to make a live run go green, and it stops the whole block from
        quietly becoming a no-op if the ledger were emptied.
        """
        flex = _NGOREME_OBSERVATIONS["Ngoreme FLEx"]
        ngoreme = _NGOREME_OBSERVATIONS["Ngoreme"]
        assert flex and ngoreme, "an empty ledger asserts nothing"
        for digest, counts in list(flex.items()) + list(ngoreme.items()):
            assert len(digest) == 64, digest
            assert all(n > 0 for n in counts), (digest, counts)
        for f_digest, f_counts in flex.items():
            for n_digest, n_counts in ngoreme.items():
                assert f_counts[0] > n_counts[0], (f_digest, n_digest)
                assert f_counts[1] > n_counts[1], (f_digest, n_digest)

    @pytest.mark.integration
    def test_ngoreme_flex_is_a_different_and_larger_project_than_ngoreme(self):
        """Read-only, both projects, digests checked before open and after
        close. Neither is a transfer target, so nothing here can write."""
        import hashlib

        pytest.importorskip(
            "flexicon", reason="the FlexTools host is not available")

        paths = {name: _live_project_or_skip(name)
                 for name in _NGOREME_OBSERVATIONS}

        def digest(path: Path) -> str:
            return hashlib.sha256(path.read_bytes()).hexdigest()

        before = {name: digest(path) for name, path in paths.items()}
        measured = {}
        for name in _NGOREME_OBSERVATIONS:
            handle = census_cli._read_only_handle(name)  # noqa: SLF001
            try:
                counts = census.count_classes(
                    handle, ("MoStemMsa", "PhPhoneme"))
                measured[name] = (counts.count_for("MoStemMsa"),
                                  counts.count_for("PhPhoneme"))
            finally:
                handle.CloseProject()
        after = {name: digest(path) for name, path in paths.items()}
        assert after == before, "a read-only census changed a .fwdata"

        # ---- THE PREMISE. Unconditional, measured live, no constants. ------
        flex = measured["Ngoreme FLEx"]
        ngoreme = measured["Ngoreme"]
        assert all(n > 0 for n in flex + ngoreme), (
            "a premise about which project is larger cannot be settled by two "
            "projects that count zero of everything: " + repr(measured))
        assert flex != ngoreme, (
            "`Ngoreme FLEx` and `Ngoreme` measured identically " + repr(flex)
            + " -- if they are the same project the corrected premise is "
            "wrong and tasks.md's original name should be restored")
        assert flex[0] > ngoreme[0], (
            "`Ngoreme FLEx` no longer holds MORE MoStemMsa than `Ngoreme`: "
            + repr(measured))
        assert flex[1] > ngoreme[1], (
            "`Ngoreme FLEx` no longer holds MORE PhPhoneme than `Ngoreme`: "
            + repr(measured))

        # ---- THE EXACT COUNTS. Only against bytes they were measured from. -
        stood_down = []
        for name, counts in measured.items():
            recorded = _NGOREME_OBSERVATIONS[name].get(before[name])
            if recorded is None:
                stood_down.append(name)
                print(
                    "[INFO] %s has moved since any recorded observation (%s..."
                    "). Measured live: MoStemMsa=%d PhPhoneme=%d. The premise "
                    "above is asserted against these numbers; the EXACT-count "
                    "check stands down rather than failing on an edit somebody "
                    "made to their own project. Appending "
                    '"%s": %r to _NGOREME_OBSERVATIONS[%r] restores it.'
                    % (name, before[name][:12], counts[0], counts[1],
                       before[name], counts, name))
                continue
            assert counts == recorded, (
                name + " counted " + repr(counts) + " at the SAME bytes that "
                "previously counted " + repr(recorded) + " (" + before[name][:12]
                + "...). The file did not move, so this is the counting code "
                "changing, not the data")

        # ---- THE SNAPSHOT TIE. Same rule, one level up. --------------------
        if before["Ngoreme FLEx"] == MEASURED_PROJECT_DIGESTS["Ngoreme FLEx"]:
            snapshot = load_measured_census("ngoreme")
            assert measured["Ngoreme FLEx"] == (
                measured_row(snapshot, "MoStemMsa")["source_count"],
                measured_row(snapshot, "PhPhoneme")["source_count"],
            )
        else:
            print(
                "[INFO] `Ngoreme FLEx` has moved since the committed snapshot "
                "was measured (" + before["Ngoreme FLEx"][:12] + "... vs "
                + MEASURED_PROJECT_DIGESTS["Ngoreme FLEx"][:12] + "...), so "
                "the snapshot's source_count is a count of different bytes and "
                "is not compared here. It is the SNAPSHOT-based blocks that "
                "stand down on drift, via `_t024_census`; the premise above "
                "does not.")

        assert sorted(stood_down) != sorted(_NGOREME_OBSERVATIONS), (
            "BOTH projects have drifted off the ledger, so no exact count was "
            "checked anywhere in this run. The premise still held, but nothing "
            "is watching the counting code any more -- append the measurements "
            "printed above to `_NGOREME_OBSERVATIONS`")


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
# criterion and was filed separately, as T048f and then T048g. T039's own text
# forecloses reading it as a failure here: "Any increase is a duplicate-creation
# defect REGARDLESS of what either census's own verdict says."
#
# BOTH HALVES ARE NOW CLOSED, AND THIS SNAPSHOT PREDATES THE SECOND. T048f
# stopped an unattributed match from poisoning every class; T048g removed the
# last reason to declare the damage unlocatable at all, by bounding the three
# categories that were in neither attribution table -- `AFFIXES` and `STEMS`
# to `LexEntry` (both skip on a `_iter_lex_entries` GUID hit and nothing else)
# and `POS_INFLECTABLE_FEATS` to the empty set (it wires a reference and
# creates no object). On run 2 those three produce 286 of the identity skips,
# which is what set `IdentitySkipTally.unbounded` and cost all 75 rows the
# strong basis.
#
# So the `baseline_gross` this file reads off run 2 for `PhPhoneme` and
# `PhNCSegments` is a RECORD OF THE DEFECT, not of current behaviour: a third
# live run would now leave both on `baseline_matched`, as run 1 already does.
# Nothing here asserts that value, and the snapshot is deliberately NOT
# regenerated -- it is the committed evidence the two fixes were measured
# against, and re-running it would destroy the before-picture while proving
# nothing the unit tests
# (`tests/unit/test_038_identity_skip_matches.py`,
# `tests/unit/test_038_matched_tally_bound.py`) do not already pin.
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


# ---------------------------------------------------------------------------
# T086 -- the phase gate's third clause, and why it needed amending
#
# T038 (P1), T075 (P2) and T048 (P3) each state three clauses: the classes the
# phase names are MATCHED, the phase-specific extra condition holds, and the
# gate "exits 0". As of `CENSUS-20260820-150540` all three predicates are
# SATISFIED and the gate still exits 8, because `census_cli`'s
# CAPPED_PASS_EXIT_CODE (T024b) is a PROJECT-WIDE property: any 5.2 suppression
# anywhere denies exit 0. The 13 suppressions on that run are `CmPossibility`,
# `FsClosedValue`, `FsFeatStruc`, `PunctuationForm`, `ReversalIndex`,
# `ReversalIndexEntry`, `StText`, `StTxtPara`, `WfiAnalysis`, `WfiGloss`,
# `WfiMorphBundle`, `WfiWordform` and `PhCode` -- texts and wordforms (governed
# by their own feature), R7 report-only residue (T079) and T081's scope. Not one
# is named by P1, P2, P3 or P4.
#
# So the third clause as written made every early phase wait on Phase 9's
# accounting: P1 could not be declared done until T079 gave the residual
# classes their report lines, which inverts the phase ordering the plan depends
# on.
#
# TWO WAYS OUT WERE ON THE TABLE, AND THE OTHER ONE WAS REJECTED. Bounding
# `census_cli`'s capped-pass exit code to the named phase would have closed all
# three tasks with no test at all -- and it would have made `gate --phase 1`
# exit 0 on a run that lost 1643 objects, which is exactly the "loss reported,
# review advisable, exit success" shape section 9 says it deliberately does not
# provide, and which T024b was filed to remove. The gate is therefore UNCHANGED
# and stays project-wide; what changed is the clause, from "exits 0" to "exits
# 0 OR exits 8 with every capped row provably outside this phase's scope", and
# the proof is these tests rather than a sentence in tasks.md.
#
# The clause is falsifiable, which is the only reason it is worth having: on the
# two pre-fix snapshots (`census-038-ejagham`, `census-038-ngoreme`, T024b's own
# 44/46-capped measurements) the capped rows DO land inside every phase's scope,
# and `test_the_amended_clause_refuses_the_pre_fix_runs` pins that it refuses
# them.
# ---------------------------------------------------------------------------

T086_SNAPSHOT = "census-038-t039d-run1.json"

#: The census the three predicates were measured on. Same live run as
#: `idempotence-038-t039.json`'s `run1` half -- one restore, one transfer, one
#: census -- committed here as the RAW artifact rather than a distillation, so
#: every assertion below is recomputed from the measurement instead of read out
#: of a summary of it.
T086_CENSUS_ID = "CENSUS-20260820-150540"

#: Every row the 5.2 cap suppressed on that run. Pinned as data because "none
#: of them is P1's" is the finding, and a finding that is not written down
#: cannot be checked later.
#: The rows 5.2's cap suppresses on the T086 snapshot, AFTER T110. Eight of the
#: thirteen T086 originally recorded -- FsClosedValue 46, FsFeatStruc 23,
#: PunctuationForm 586, ReversalIndexEntry 1, WfiAnalysis 136, WfiGloss 135,
#: WfiMorphBundle 219, WfiWordform 49, together 1195 of the 1643 -- had a
#: MEASURED-ZERO starter baseline, so gross subtraction removed nothing from
#: them and both bases computed the same integer. They were never advisory and
#: are no longer suppressed. The five that remain are the five with a real
#: nonzero baseline to over-subtract.
T086_CAPPED_ROWS = {
    "CmPossibility": 304,
    "ReversalIndex": 2,
    "StText": 17,
    "StTxtPara": 91,
    "PhCode": 34,
}

#: What T086 measured before T110, kept so the delta is a fact in the test
#: rather than a sentence in a journal.
T086_CAPPED_ROWS_PRE_T110_TOTAL = 1643

#: The phases whose third clause this closes, and the task that owns each.
T086_GATED_PHASES = ((1, "T038"), (2, "T075"), (3, "T048"))


def t086_snapshot_path() -> Path:
    return Path(__file__).resolve().parent / "_snapshots" / T086_SNAPSHOT


def load_t086_snapshot() -> dict:
    path = t086_snapshot_path()
    assert path.is_file(), (
        "the T086 phase-gate snapshot is missing: " + str(path)
        + " -- it is committed repo data recording a live census, not a "
        "regenerable temp file; restore it from git rather than re-running a "
        "transfer against a FLEx project"
    )
    return json.loads(path.read_text(encoding="utf-8"))


class TestT086PhaseScopeIsDeclaredNotGuessed:
    """`phase_classes` is read off the predicate, so it cannot drift from it."""

    def test_every_phase_declares_a_scope(self):
        for phase in sorted(PHASE_PREDICATES):
            # Constructing the dict at import time already refused an empty
            # tuple; this pins that all five are reachable through the
            # accessor.
            scope = phase_classes(phase)
            assert scope is None or scope, phase

    def test_the_transcribed_p1_tuple_matches_the_predicate(self):
        """`PHASE_1_CLASSES` in this module is transcribed from
        fidelity-census.md 9.1; `PHASE_1_CLASSES` in census.py is built from the
        predicate's own constants. They must agree, and neither is derived from
        the other."""
        assert phase_classes(1) == frozenset(PHASE_1_CLASSES) | {"PhPhoneme"}

    def test_the_transcribed_p2_and_p4_tuples_match_the_predicates(self):
        assert phase_classes(2) == frozenset(PHASE_2_CLASSES)
        assert phase_classes(4) == frozenset(PHASE_4_CLASSES)

    def test_p1_scope_includes_the_class_it_does_not_require_matched(self):
        """A phase's scope is every class it NAMES, not only the ones it counts.
        P1 names `PhPhoneme` on the duplicates condition (SC-002) and never
        requires it MATCHED, so a suppression on the phoneme row is P1's
        business even though the predicate would still be satisfied with it.
        Get this wrong in the other direction and P1 could pass its amended
        clause while its own phoneme row was capped."""
        assert "PhPhoneme" in phase_classes(1)
        assert "PhPhoneme" not in frozenset(PHASE_1_MATCHED_CLASSES)

    def test_p3_scope_includes_part_of_speech(self):
        """Same shape: P3 names `PartOfSpeech` on the enrichment condition
        (`match_basis.enriched > 0`) rather than on MATCHED."""
        assert "PartOfSpeech" in phase_classes(3)

    def test_p5_is_unbounded_so_t081_gets_no_escape_hatch(self):
        """P5's predicate is "every remaining required row", so its scope is the
        whole artifact and it can never call a suppressed row somebody else's
        problem. This is the one property that keeps the amended clause from
        being a general-purpose way to pass a gate."""
        assert phase_classes(5) is None
        artifact = load_t086_snapshot()
        assert (phase_scoped_suppressions(artifact, 5)
                == gross_basis_suppressions(artifact))
        assert not evaluate_phase(artifact, 5).satisfied

    def test_an_empty_scope_is_refused(self):
        """`None` means "every required row"; an empty tuple would mean "no row
        is in scope", which turns every capped row into somebody else's and
        makes the phase-scoped reading unfalsifiable. Constructing one must
        fail, not quietly produce the most permissive possible phase."""
        template = PHASE_PREDICATES[1]
        with pytest.raises(CensusError):
            type(template)(1, template.name, template.description,
                           template.check, ())


class TestT086TheAmendedThirdClause:
    """T038 / T075 / T048's third clause, checked instead of asserted in
    prose."""

    def test_the_snapshot_is_committed_repo_data(self):
        path = t086_snapshot_path()
        root = Path(__file__).resolve().parents[2]
        assert (root / "tests" / "integration" / "_snapshots") == path.parent

    def test_the_snapshot_is_the_census_the_tasks_name(self):
        artifact = load_t086_snapshot()
        assert artifact["census_id"] == T086_CENSUS_ID
        projects = artifact["projects"]
        assert projects["source"]["name"] == "Ejagham Mini"
        assert projects["destination"]["name"] == "GT038 T039d Target"

    @pytest.mark.parametrize("phase,task", T086_GATED_PHASES,
                             ids=[t for _, t in T086_GATED_PHASES])
    def test_clause_one_and_two_the_predicate_is_satisfied(self, phase, task):
        result = evaluate_phase(load_t086_snapshot(), phase)
        assert result.satisfied, (
            task + " (P" + str(phase) + ") is not satisfied: "
            + "; ".join(result.failures))

    @pytest.mark.parametrize("phase,task", T086_GATED_PHASES,
                             ids=[t for _, t in T086_GATED_PHASES])
    def test_clause_three_no_capped_row_is_in_the_phases_scope(
            self, phase, task):
        """The amended clause. Not "the gate exits 0" -- it does not, and must
        not -- but "every row the 5.2 cap suppressed lies outside the classes
        this phase names"."""
        artifact = load_t086_snapshot()
        in_scope = phase_scoped_suppressions(artifact, phase)
        assert in_scope == (), (
            task + " (P" + str(phase) + ") has capped rows inside its own "
            "scope, so its third clause is NOT satisfied: " + repr(in_scope))

    def test_the_gate_does_not_exit_zero_and_that_is_the_point(self):
        """The clause was amended; the gate was not. Nothing here may be read as
        "the run is clean", and SC-010's refusal to provide a "loss reported,
        exit success" outcome is intact.

        The refusal used to be `CAPPED_PASS_EXIT_CODE` 8 -- a pass the cap
        turned non-zero. Since T110 it is a plain exit 1: 8 of the 13 suppressed
        rows had a measured-zero baseline, so the artifact's own evidence gives
        `UNEXPLAINED_SHORTFALL` and there is no pass left to cap. The phase
        predicate is satisfied either way, which is exactly the separation
        T086's clause rests on -- the run verdict got stricter and P1's answer
        did not move. Exit 8 itself is untouched and still reachable; its own
        test is `test_a_capped_pass_does_not_exit_zero`, over a row with a
        nonzero baseline."""
        artifact = load_t086_snapshot()
        outcome = gate_artifact(artifact, phase=1)
        assert outcome.verdict == "UNEXPLAINED_SHORTFALL"
        assert outcome.exit_code == 1
        assert outcome.phase.satisfied
        assert gross_basis_suppressions(artifact), (
            "this snapshot is supposed to still BE partly capped")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "census.json"
            path.write_text(json.dumps(artifact), encoding="utf-8")
            code = cli_exit(["gate", "--artifact", str(path), "--phase", "1"])
        assert code == 1
        assert code != census_cli.CAPPED_PASS_EXIT_CODE == 8

    def test_the_capped_rows_are_the_ones_recorded(self):
        """If a later change moves these, the tasks' prose is stale and the
        finding needs re-stating rather than the test relaxing. T110 moved
        them, and this is the re-statement: 5 rows and 448 objects, down from
        13 and 1643. Every row that left had a measured-zero baseline."""
        artifact = load_t086_snapshot()
        measured = {label: count
                    for label, _direction, count
                    in gross_basis_suppressions(artifact)}
        assert measured == T086_CAPPED_ROWS
        assert sum(measured.values()) == 448
        assert sum(measured.values()) < T086_CAPPED_ROWS_PRE_T110_TOTAL
        for row in artifact["classes"]:
            if row["class"] in measured:
                assert row["starter_baseline_count"] > 0, row["class"]

    def test_no_capped_row_belongs_to_any_bounded_phase(self):
        """Stronger than the per-phase clause, and the reason it is safe to
        amend three tasks at once: the 13 suppressions are disjoint from P1, P2,
        P3 AND P4's scopes together, so no bounded phase is being excused."""
        artifact = load_t086_snapshot()
        capped = {label for label, _, _ in gross_basis_suppressions(artifact)}
        bounded = set()
        for phase in sorted(PHASE_PREDICATES):
            scope = phase_classes(phase)
            if scope is not None:
                bounded |= scope
        assert capped & bounded == set()

    @pytest.mark.parametrize("pre_fix", ["census-038-ejagham",
                                        "census-038-ngoreme"])
    def test_the_amended_clause_refuses_the_pre_fix_runs(self, pre_fix):
        """Falsifiability, on real data. These are T024b's own measurements --
        44 and 46 capped rows, `CENSUS_ACCOUNTED`, exit 0 at the time -- and
        every gated phase must still be REFUSED on them.

        T110 changed how each refusal is reached, and the change is worth
        pinning per phase rather than averaging away. P1 and P3 still hold an
        in-scope capped row (`PartOfSpeech`, plus `MoMorphType` for P3 -- the
        classes with a real nonzero starter baseline). P2's two classes,
        `MoInflAffixSlot` and `MoInflAffixTemplate`, both had a MEASURED-ZERO
        baseline, so their shortfalls were never advisory: P2's clause three is
        now VACUOUSLY satisfied on these runs and the refusal comes from
        clauses one and two instead. That is the right direction -- the loss
        stopped being excused and started being counted -- but a clause-three
        assertion alone would no longer refuse P2, which is exactly why the
        first assertion in this loop is the predicate itself."""
        path = (Path(__file__).resolve().parent / "_snapshots"
                / (pre_fix + ".json"))
        artifact = json.loads(path.read_text(encoding="utf-8"))
        in_scope = {}
        for phase, _task in T086_GATED_PHASES:
            assert not evaluate_phase(artifact, phase).satisfied, phase
            in_scope[phase] = {label for label, _, _
                               in phase_scoped_suppressions(artifact, phase)}
        assert in_scope[1] == {"PartOfSpeech"}
        assert in_scope[2] == set()
        assert in_scope[3] == {"MoMorphType", "PartOfSpeech"}
        # And the run itself is no longer a pass at all, which is the answer
        # T086 could not give while the cap covered 44-46 rows.
        assert recompute_verdict(artifact) == "UNEXPLAINED_SHORTFALL"

    def test_a_suppression_inside_the_scope_would_fail_the_clause(self):
        """The synthetic complement of the two tests above: move one capped row
        INTO P1's scope and the clause must fail. Guards against a bound so
        narrow that nothing could ever land in it.

        The perturbation now has to give the row a NONZERO starter baseline as
        well as the gross basis, because since T110 those are two different
        claims: `baseline_gross` over a measured zero is exact arithmetic and is
        not capped at all. Setting the basis alone would build a row that no
        longer demonstrates anything -- which is how this test caught the change
        rather than absorbing it."""
        artifact = json.loads(json.dumps(load_t086_snapshot()))
        for row in artifact["classes"]:
            if row["class"] == "MoStemMsa":
                assert row["starter_baseline_count"] == 0
                row["starter_subtraction_basis"] = GROSS_SUBTRACTION_BASIS
                row["starter_baseline_count"] = 5
                row["unexplained_shortfall"] = 7
                break
        else:
            pytest.fail("the snapshot has no MoStemMsa row to perturb")
        assert phase_scoped_suppressions(artifact, 1) == (
            ("MoStemMsa", "shortfall", 7),)

    def test_the_same_perturbation_without_a_baseline_is_not_a_suppression(
            self):
        """The other half of the pair, and the T110 regression that matters: a
        row perturbed to `baseline_gross` while its baseline stays a measured
        zero produces NO suppression, in scope or out. If this ever starts
        returning a suppression again, the cap has gone back to excusing exact
        arithmetic."""
        artifact = json.loads(json.dumps(load_t086_snapshot()))
        for row in artifact["classes"]:
            if row["class"] == "MoStemMsa":
                row["starter_subtraction_basis"] = GROSS_SUBTRACTION_BASIS
                row["unexplained_shortfall"] = 7
                break
        assert phase_scoped_suppressions(artifact, 1) == ()
        assert not any(label == "MoStemMsa"
                       for label, _, _ in gross_basis_suppressions(artifact))


# ---------------------------------------------------------------------------
# T099: null is not a smaller zero
#
# THE ARTIFACT-LEVEL HALF. `tests/unit/test_038_null_counts.py` pins the model
# and the emitter; what belongs here is the MEASUREMENT, because feature 038's
# acceptance rule is "a phase is not done when its unit tests pass; it is done
# when the census run for its predicate exits 0 with the predicate satisfied" --
# so a change to emitted COUNTS has to be judged on two real census runs, not on
# a hand-built row.
#
# The pair below is one census run of `Ngoreme FLEx` -> `GT038 Ngoreme After`
# taken immediately before the fix and one immediately after, with the SAME
# baseline, the SAME run report, and both projects unchanged between them (the
# `.fwdata` digests are asserted equal, which is what makes the delta
# attributable to the instrument and nothing else).
# ---------------------------------------------------------------------------

T099_BEFORE = "census-038-t099-ngoreme-before.json"
T099_AFTER = "census-038-t099-ngoreme-after.json"

#: The two classes the defect touched, and the only two it could touch: the
#: `excluded_not_measurable` arm of the class list holds exactly these.
T099_NULLED_CLASSES = ("MoForm", "MoMorphSynAnalysis")

#: The five row quantities that went 0 -> null. All five are derived from the
#: two counts, and three of them (`source_count`, `destination_count_total`,
#: `difference`) are REQUIRED in `$defs.classRow` -- which is why the emitter
#: had to learn to emit a null instead of dropping the key.
T099_NULLED_FIELDS = (
    "source_count", "destination_count_total", "destination_count_net",
    "difference", "difference_raw",
)


def _t099(name: str) -> dict:
    path = _repo_root() / "tests" / "integration" / "_snapshots" / name
    assert path.is_file(), "missing T099 measurement artifact: " + str(path)
    return json.loads(path.read_text(encoding="utf-8"))


class TestT099TheMeasuredDelta:
    """Two real runs, one instrument change, and a stated delta."""

    @pytest.mark.parametrize("name", [T099_BEFORE, T099_AFTER])
    def test_both_artifacts_validate_against_the_published_schema(
            self, name, census_schema):
        errors = schema_errors(_t099(name), census_schema)
        assert errors == [], "; ".join(errors[:5])

    @pytest.mark.parametrize("name", [T099_BEFORE, T099_AFTER])
    def test_both_artifacts_pass_the_section_11_invariants(self, name):
        """Invariant 3 recomputes both differences from the counts. It is
        SKIPPED on a null rather than failing, and a skipped invariant is the
        thing to be suspicious of -- hence the schema check above, which is
        what actually holds a null row to its shape."""
        assert validate_artifact(_t099(name)) == ()

    def test_neither_project_moved_between_the_two_runs(self):
        """Without this the delta below could be data drift rather than the
        fix. `Ngoreme FLEx` is a live project and HAS drifted during this
        feature (the T096 snapshot reads 21 shortfall lower than a re-run on
        2026-08-21), which is exactly why the pair is measured back to back and
        pinned by digest."""
        before, after = _t099(T099_BEFORE), _t099(T099_AFTER)
        for role in ("source", "destination"):
            for key in ("fwdata_sha256_before", "fwdata_sha256_after",
                        "object_count_total"):
                assert (before["projects"][role][key]
                        == after["projects"][role][key]), role + "." + key

    def test_the_gate_quantities_are_byte_identical(self):
        """THE HEADLINE. The fix changes what two rows SAY and nothing a phase
        gate adds up: `build_totals` skips a null difference, so
        `total_shortfall` is 70659 on both sides and the verdict is unchanged.
        A count change that moved the gate quantity would need its own
        argument; this one does not."""
        before, after = _t099(T099_BEFORE), _t099(T099_AFTER)
        assert before["totals"] == after["totals"]
        assert before["totals"]["total_shortfall"] == 70659
        assert before["totals"]["classes_not_evaluated"] == 3
        assert (before["verdict"], before["exit_code"]) == (
            "DUPLICATE_IDENTITY", 3)
        assert (after["verdict"], after["exit_code"]) == (
            "DUPLICATE_IDENTITY", 3)

    def test_exactly_two_rows_changed(self):
        before = {r["class"]: r for r in _t099(T099_BEFORE)["classes"]}
        after = {r["class"]: r for r in _t099(T099_AFTER)["classes"]}
        assert set(before) == set(after)
        changed = tuple(sorted(
            cls for cls in before
            if json.dumps(before[cls], sort_keys=True)
            != json.dumps(after[cls], sort_keys=True)
        ))
        assert changed == tuple(sorted(T099_NULLED_CLASSES))

    @pytest.mark.parametrize("object_class", T099_NULLED_CLASSES)
    def test_the_knowingly_false_zero_became_a_null(self, object_class):
        before = {r["class"]: r for r in _t099(T099_BEFORE)["classes"]}
        after = {r["class"]: r for r in _t099(T099_AFTER)["classes"]}
        for field in T099_NULLED_FIELDS:
            assert before[object_class][field] == 0, (
                field + " was expected to be the old placeholder 0")
            assert after[object_class][field] is None, field
        # The row was ALREADY NOT_EVALUATED. That is the point: the verdict was
        # right and the numbers under it were false, so no reader checking the
        # verdict would have found the defect.
        assert before[object_class]["verdict_class"] == "NOT_EVALUATED"
        assert after[object_class]["verdict_class"] == "NOT_EVALUATED"
        assert (after[object_class]["in_class_list_via"]
                == "excluded_not_measurable")

    @pytest.mark.parametrize("object_class", T099_NULLED_CLASSES)
    def test_the_note_stopped_apologising_for_its_own_data(self, object_class):
        before = {r["class"]: r for r in _t099(T099_BEFORE)["classes"]}
        after = {r["class"]: r for r in _t099(T099_AFTER)["classes"]}
        assert any("placeholder" in n for n in before[object_class]["notes"])
        assert not any("placeholder" in n for n in after[object_class]["notes"])
        assert any("null, not 0" in n for n in after[object_class]["notes"])

    def test_the_committed_measurement_satisfies_the_producer_guard(self):
        """PROVENANCE, and it is here because the order of work matters.
        `_refuse_uncorroborated_nulls` was written AFTER these two artifacts
        were measured (it closes a hole T099's own fix opens -- see
        `TestT099TheAbortBecameARowWithoutBecomingQuiet`). A guard added after a
        measurement is worth nothing unless the measurement is re-checked
        against it, and re-running the census was not available: `Ngoreme FLEx`
        was opened in FieldWorks at 23:43, eleven minutes after the second run,
        and the census correctly refuses a locked project. So the guard is run
        over the committed rows instead, which is the same check the producer
        would have made."""
        from gramtrans import census_cli

        for name in (T099_BEFORE, T099_AFTER):
            artifact = _t099(name)
            census_cli._refuse_uncorroborated_nulls(
                artifact["classes"], artifact.get("errors", ()))

    def test_no_other_row_gained_a_null_count(self):
        """The direction a careless fix breaks: sweeping a genuine zero into
        null. Every other row must still carry integers."""
        after = _t099(T099_AFTER)["classes"]
        for row in after:
            if row["class"] in T099_NULLED_CLASSES:
                continue
            for field in T099_NULLED_FIELDS:
                assert isinstance(row[field], int), (
                    row["class"] + "." + field + " is " + repr(row[field])
                    + " -- a genuine zero is 0, never null")


class TestT099TheAbortBecameARowWithoutBecomingQuiet:
    """The other half of the same root cause, from the opposite direction."""

    def _rows_with_an_uncounted_class(self):
        rows = [make_row("PhPhoneme", source_count=23)]
        uncounted = make_row(
            "MoStemMsa", verdict_class="NOT_EVALUATED", gate_scope="required")
        for field in T099_NULLED_FIELDS:
            uncounted[field] = None
        uncounted["notes"] = [
            "not measured: this repository accessor could not be resolved in "
            "the destination, so the count is null rather than 0."
        ]
        rows.append(uncounted)
        return rows

    def _errors(self):
        return [{
            "code": "UNHANDLED_EXCEPTION",
            "message": ("class MoStemMsa could not be counted in project Dst; "
                        "the census makes no claim about it"),
            "class": "MoStemMsa",
            "evidence": "IMoStemMsaRepository could not be resolved",
        }]

    def test_the_artifact_that_used_to_not_exist_now_validates(
            self, census_schema):
        """Before T099 an unresolved accessor raised and NOTHING was written,
        so the one document that could name the uncounted class did not exist.
        The abort was loud in the console and silent in the record."""
        artifact = make_artifact(
            self._rows_with_an_uncounted_class(),
            verdict="CENSUS_ERROR", errors=self._errors())
        assert schema_errors(artifact, census_schema) == []

    def test_an_uncounted_class_is_census_error_not_a_pass(self):
        """The reason the abort becoming a row is not a silencing: a non-empty
        `errors[]` array is CENSUS_ERROR on its own, and the gate RECOMPUTES the
        verdict rather than reading the stored one."""
        artifact = make_artifact(
            self._rows_with_an_uncounted_class(),
            verdict="CENSUS_ERROR", errors=self._errors())
        assert recompute_verdict(artifact) == "CENSUS_ERROR"
        assert gate_artifact(artifact).exit_code == 7

    def test_the_producer_refuses_an_uncorroborated_null_on_a_required_row(
            self):
        """The failure mode to be afraid of, and the one T099 itself could have
        opened. An uncounted row is NOT_EVALUATED and `row_passes` returns True
        for NOT_EVALUATED, so nulling a required class would retire its
        shortfall without measuring anything. Before T099 the MODEL made that
        unreachable by refusing to hold a null at all; it no longer does, so the
        producer states the prohibition instead."""
        from gramtrans import census_cli
        from gramtrans.Lib import census as census_mod

        rows = self._rows_with_an_uncounted_class()
        with pytest.raises(census_mod.CensusError, match="uncorroborated null"):
            census_cli._refuse_uncorroborated_nulls(rows, ())
        # With the class named in `errors[]` the same rows are admissible --
        # that entry is CENSUS_ERROR, so the run still fails.
        census_cli._refuse_uncorroborated_nulls(rows, self._errors())

    def test_an_advisory_null_row_needs_no_errors_entry(self):
        """The `excluded_not_measurable` case, which is every null this CLI
        emits on a healthy run. `census.derive_class_list` hardcodes those
        entries `gate_scope: advisory`, so they can neither fail a gate nor
        excuse one."""
        from gramtrans import census_cli

        row = make_row("MoForm", verdict_class="NOT_EVALUATED",
                       gate_scope="advisory", engine_can_create=False,
                       in_class_list_via="excluded_not_measurable",
                       not_evaluated_reason="ABSENT_BY_CONSTRUCTION")
        for field in T099_NULLED_FIELDS:
            row[field] = None
        census_cli._refuse_uncorroborated_nulls([row], ())

    def test_the_gate_now_refuses_a_forged_null(self):
        """T101, and this is the DELIBERATE EDIT the pin asked for. Until
        invariant 12 landed this same artifact passed `validate_artifact` with
        0 failures and gated CENSUS_CLEAN / exit 0, and the assertions below
        read `== ()` and `== 0`. The old test named itself
        `test_the_gate_alone_does_not_yet_refuse_a_forged_null` and said in its
        own docstring: "When T101 lands, THIS TEST FAILS and must be updated
        deliberately." It landed; this is that update, and the numbers it
        asserts are the ones that moved."""
        forged = make_artifact(
            self._rows_with_an_uncounted_class(),
            verdict="CENSUS_CLEAN", errors=())
        failures = validate_artifact(forged)
        assert len(failures) == 2, failures
        # The new invariant names the row and says what nulling it would buy.
        assert failures[0].startswith("UNCORROBORATED_NULL: MoStemMsa")
        assert "retires the class's shortfall without measuring it" in failures[0]
        # And invariant 8 fires SECOND, as a consequence rather than a
        # duplicate: the recomputed verdict is now CENSUS_ERROR, so the stored
        # CENSUS_CLEAN stops agreeing with the artifact's own evidence. Before
        # T101 the two agreed, which is exactly why the forgery passed.
        assert failures[1].startswith("invariant 8:")
        assert "CENSUS_CLEAN" in failures[1] and "CENSUS_ERROR" in failures[1]
        # CENSUS_ERROR, not merely a non-passing gate: the recomputed verdict
        # moves too, so the exit code cannot stay 0.
        assert recompute_verdict(forged) == "CENSUS_ERROR"
        outcome = gate_artifact(forged)
        assert outcome.exit_code == 7
        assert outcome.passed is False

    def test_a_null_counted_row_cannot_forge_a_clean_run(self):
        """T101's headline, and the test that FAILED when T099 wrote it -- it
        was written to prove the opposite and could not. One `gate_scope:
        required` row whose `source_count`, `destination_count_total` and
        `difference` are ALL null, with an EMPTY `errors[]`, must not be able
        to buy exit 0.

        Note what is NOT asserted: that the row fails. `row_passes` still
        returns True for NOT_EVALUATED, which is 5.2's rule and not an
        oversight -- a row nobody measured proves nothing, in either direction.
        The refusal is the artifact's, at the one place the corroboration
        lives."""
        forged = make_artifact(
            self._rows_with_an_uncounted_class(),
            verdict="CENSUS_CLEAN", errors=())
        nulled = next(r for r in forged["classes"] if r["class"] == "MoStemMsa")
        assert nulled["gate_scope"] == "required"
        for field in T099_NULLED_FIELDS:
            assert nulled[field] is None, field
        assert not forged.get("errors")
        assert row_passes(nulled) is True, (
            "5.2's rule is unchanged: NOT_EVALUATED passes the row test, and "
            "T101 is not closed by breaking that")
        assert gate_artifact(forged).exit_code != 0

    def test_the_two_legitimate_null_rows_are_exempt_by_scope_not_tolerance(
            self):
        """THE FIX NOT TO MAKE, pinned from the other side. `MoForm` and
        `MoMorphSynAnalysis` are abstract LCM bases with no factory; every
        artifact carries them null, and a validator that failed a row on a null
        count would fail both. They pass because they are `advisory` -- a row
        that can neither fail a gate nor excuse one -- and NOT because a null is
        tolerated on a row that could."""
        advisory = make_row(
            "MoForm", verdict_class="NOT_EVALUATED", gate_scope="advisory",
            engine_can_create=False,
            in_class_list_via="excluded_not_measurable",
            not_evaluated_reason="ABSENT_BY_CONSTRUCTION")
        for field in T099_NULLED_FIELDS:
            advisory[field] = None
        artifact = make_artifact(
            [make_row("PhPhoneme", source_count=23), advisory],
            verdict="CENSUS_CLEAN", errors=())
        assert census.uncorroborated_null_rows(artifact) == ()
        assert validate_artifact(artifact) == ()
        assert gate_artifact(artifact).exit_code == 0

        # The SAME row promoted to `required` is refused, which is what proves
        # the exemption is scope and not the null.
        advisory["gate_scope"] = "required"
        advisory.pop("not_evaluated_reason")
        assert [label for label, _ in
                census.uncorroborated_null_rows(artifact)] == ["MoForm"]

    def test_a_declared_reason_corroborates_a_required_null(self):
        """The second admissible corroboration (T100). A `not_evaluated_reason`
        is a vocabulary-bound CLAIM about why the class was not measured, which
        is what distinguishes an excuse from a silence -- so a required row
        carrying one is admissible with no `errors[]` entry, and the run does
        not become CENSUS_ERROR on its account."""
        governed = make_row(
            "MoStemMsa", verdict_class="NOT_EVALUATED", gate_scope="required",
            not_evaluated_reason="GOVERNED_BY_OTHER_FEATURE")
        for field in T099_NULLED_FIELDS:
            governed[field] = None
        artifact = make_artifact(
            [make_row("PhPhoneme", source_count=23), governed],
            verdict="CENSUS_CLEAN", errors=())
        assert census.uncorroborated_null_rows(artifact) == ()
        assert validate_artifact(artifact) == ()
        assert recompute_verdict(artifact) == "CENSUS_CLEAN"

    def test_the_corroborated_null_still_cannot_buy_a_passing_exit(self):
        """Corroboration by `errors[]` admits the ROW; it does not admit the
        RUN. A non-empty `errors[]` is CENSUS_ERROR on its own, so the shape
        invariant 12 accepts still exits 7 -- which is why accepting it is not
        a loophole."""
        artifact = make_artifact(
            self._rows_with_an_uncounted_class(),
            verdict="CENSUS_ERROR", errors=self._errors())
        assert census.uncorroborated_null_rows(artifact) == ()
        assert validate_artifact(artifact) == ()
        assert gate_artifact(artifact).exit_code == 7

    def test_a_null_net_count_alone_is_invariant_3s_business(self):
        """The field deliberately left out of `NULLABLE_COUNT_FIELDS`.
        `destination_count_net` is DERIVED from `destination_count_total`, so a
        null net beside integer counts is an arithmetic defect, not an
        unmeasured class -- and folding it in here would have made invariant 12
        report a class nobody failed to measure."""
        assert "destination_count_net" not in census.NULLABLE_COUNT_FIELDS
        row = make_row("MoStemMsa", source_count=164)
        row["destination_count_net"] = None
        artifact = make_artifact([row], verdict="CENSUS_CLEAN")
        assert census.uncorroborated_null_rows(artifact) == ()

    def test_a_p1_class_that_could_not_be_counted_fails_its_phase(self):
        """`_require_matched` reads `verdict_class`, so an uncounted P1 class
        reports NOT_EVALUATED and FAILS -- the safe direction. Pinned because
        the other direction (a phase quietly skipping a class nobody counted)
        is the shape this feature keeps meeting."""
        artifact = make_artifact(
            self._rows_with_an_uncounted_class(),
            verdict="CENSUS_ERROR", errors=self._errors())
        outcome = gate_artifact(artifact, phase=1)
        assert outcome.phase is not None
        assert not outcome.phase.satisfied
        assert any("MoStemMsa" in line and "NOT_EVALUATED" in line
                   for line in outcome.phase.failures)

class TestT101TheCommittedCorpusIsUnmovedByInvariant12:
    """T101's before/after, which is what let the invariant land at all.

    Adding an invariant changes what the gate refuses about every artifact
    ALREADY COMMITTED, and that is why T099 bounded the producer instead and
    filed this half. Measured over every committed census artifact under
    `_snapshots/`: **0 refused, before and after**. The exemption doing the work
    is SCOPE -- 6 advisory null rows across the corpus, and not one required row
    carrying a null anywhere in it.
    """

    def _artifacts(self):
        directory = _repo_root() / "tests" / "integration" / "_snapshots"
        out = []
        for path in sorted(directory.glob("*.json")):
            artifact = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(artifact, dict) and "classes" in artifact:
                out.append((path.name, artifact))
        return out

    def test_the_corpus_is_the_size_the_measurement_was_taken_over(self):
        """A count, so the claims below cannot quietly shrink their own scope:
        a corpus test that silently stopped finding artifacts would pass."""
        assert len(self._artifacts()) >= 18

    def test_no_committed_artifact_is_newly_refused(self):
        for name, artifact in self._artifacts():
            assert census.uncorroborated_null_rows(artifact) == (), name

    def test_no_committed_artifact_carries_a_null_on_a_required_row(self):
        """The reason the invariant costs nothing: the shape it refuses does not
        occur in anything this repo has measured. It is reachable only by hand
        or by a producer bug, which is precisely what it is for."""
        for name, artifact in self._artifacts():
            for row in artifact["classes"]:
                if row.get("gate_scope") != "required":
                    continue
                for field in census.NULLABLE_COUNT_FIELDS:
                    assert row.get(field) is not None, (
                        name + ": " + str(row.get("class")) + "." + field)

    def test_every_committed_null_row_is_advisory(self):
        """The same fact stated positively -- and the count is pinned so a
        future artifact that nulls a row cannot arrive unremarked.

        T076/T077 (2026-08-22) are the first artifacts to arrive since this
        pin was written, and they took the count 6 -> 10. Read rather than
        bumped: the four new nulls are `MoForm` and `MoMorphSynAnalysis` on
        `census-038-t077-mbugwe-phase6.json` and
        `census-038-t076-registered.json` -- the SAME two
        `excluded_not_measurable` rows T099 nulled in the other three, from
        the same post-T099 producer. Nothing new is being nulled.

        T089 (2026-08-22) took it 10 -> 12, and the reading is stronger than
        "same two rows again". `census-038-t089-fixed.json` is asserted
        ELSEWHERE to reproduce `census-038-t076-registered.json` ROW FOR ROW
        (`test_038_closure_edge_audit.py::
        test_t089_reproduces_the_previous_census_row_for_row`), which is the
        whole point of that run -- T089 changes a producer whose relationship
        is unregistered, so the transfer must be the same transfer. Its two
        nulls are therefore not merely the same CLASSES as T076's, they are
        the same ROWS, and an artifact of that provenance nulling anything
        else would have failed that comparison before reaching this one.

        T104 (2026-08-22) took it 12 -> 14, and the reading is the SAME
        reading as T089's, for the same structural reason. T104 registers
        `MSA_TO_INFL_FEATURE`, whose closure edges exist only under an
        AFFIXES-only selection; the census is taken under a FULL COPY, where
        that row contributes nothing at all. So
        `census-038-t104-registered.json` is asserted ELSEWHERE to reproduce
        `census-038-t076-registered.json` ROW FOR ROW
        (`test_038_closure_edge_audit.py::
        test_the_t104_census_reproduces_the_previous_one_row_for_row`, 74
        classes, 0 differing rows, every total equal). Its two nulls are
        therefore the same ROWS, not merely the same classes, and an artifact
        of that provenance nulling anything else would have failed that
        comparison before reaching this one.

        THE PIN IS NOW THREE CLAIMS RATHER THAN ONE MAGIC NUMBER, because a
        bare total that has to be edited for every new artifact degrades into
        a number nobody can interpret -- and a number nobody interprets gets
        bumped rather than read, which is how a real finding slips through a
        tripwire that is technically still there. So:

          1. every artifact that nulls anything nulls exactly `MoForm` and
             `MoMorphSynAnalysis` -- this is the one that fails on a
             genuinely new null, and it holds no matter how the corpus grows;
          2. the artifact COUNT is pinned, so a new census arriving is still
             a deliberate edit here;
          3. the total is the product of the two, asserted as such rather
             than written out, so it cannot drift away from them.
        """
        by_artifact: dict = {}
        advisory_nulls = 0
        for name, artifact in self._artifacts():
            for row in artifact["classes"]:
                if any(row.get(f) is None
                       for f in census.NULLABLE_COUNT_FIELDS):
                    assert row.get("gate_scope") == "advisory", (
                        name + ": " + str(row.get("class")))
                    advisory_nulls += 1
                    by_artifact.setdefault(name, set()).add(row.get("class"))

        for name, classes in sorted(by_artifact.items()):
            assert classes == {"MoForm", "MoMorphSynAnalysis"}, (
                name + " nulls something other than the two "
                "excluded_not_measurable rows: " + repr(sorted(classes)))
        # 7 -> 9 on 2026-08-24 (T095): `census-038-t095-ngoreme.json` and
        # `census-038-t095-ejagham.json` arrived from T095's live pair. Each
        # nulls exactly the two `excluded_not_measurable` rows, so clause 1
        # above -- the one that fails on a genuinely NEW null -- passed
        # untouched; only the deliberate-edit count moved.
        #
        # 9 -> 12 on 2026-08-25 (T078): the three post-037 baseline censuses
        # `census-038-t078-ejagham.json`, `-ngoreme.json` and `-mbugwe.json`
        # arrived. THIS TRIPWIRE FIRED FIRST AND WAS EDITED SECOND, on the
        # evidence: each of the three nulls exactly `MoForm` and
        # `MoMorphSynAnalysis`, so clause 1 passed untouched, and each is
        # asserted ELSEWHERE to reproduce its predecessor ROW FOR ROW
        # (`TestT078ThePost037Baseline::
        # test_each_baseline_reproduces_its_predecessor_row_for_row`) -- so as
        # with T089's and T104's links these are the same ROWS, not merely the
        # same classes. Not relaxed: the count is still a deliberate edit.
        #
        # 12 -> 14 on 2026-08-25 (T107): `census-038-t107-ejagham.json` and
        # `census-038-t107-mbugwe-phase6.json` arrived from T107's live
        # acceptance runs. THE FIRED-FIRST, EDITED-SECOND DISCIPLINE AGAIN,
        # and this pair is the first where the reading is NOT "reproduces its
        # predecessor row for row" -- the Ejagham one MOVES FIVE ROWS on
        # purpose, which is the whole point of T107. Clause 1 is therefore
        # carrying the weight alone here, and it passed untouched: each of the
        # two nulls exactly `MoForm` and `MoMorphSynAnalysis`, the same
        # `excluded_not_measurable` pair the post-T099 producer nulls in all
        # twelve predecessors, and `uncorroborated_null_rows` is empty on
        # both. The Mbugwe one IS asserted to reproduce its predecessor row
        # for row (`TestT107...::test_the_mbugwe_pair_is_unmoved_to_the_row`),
        # so only the Ejagham artifact rests on clause 1 by itself -- and its
        # five moved rows are each pinned by number in
        # `T107_EJAGHAM_MOVED`, which is a stronger check than a row-for-row
        # equality could have been.
        #
        # 14 -> 17 on 2026-08-27 (T124): `census-038-t124-ejagham.json`,
        # `-ngoreme.json` and `-mbugwe.json` arrived from T124's re-census of
        # the three sanctioned pairs into FRESH throwaway destinations
        # (`GT038 T124 Ejagham` / `Ngoreme` / `Mbugwe`). THE FIRED-FIRST,
        # EDITED-SECOND DISCIPLINE AGAIN: this tripwire failed on the count
        # alone, clause 1 passed untouched for all three, and the
        # `gate_scope == "advisory"` assertion above passed for all six nulls.
        # Each of the three nulls exactly `MoForm` and `MoMorphSynAnalysis`.
        #
        # Like T107's pair and unlike T078's, these are NOT asserted to
        # reproduce a predecessor row for row -- they are a deliberately NEW
        # comparand, measured against the Wave 2 code, and they move rows on
        # purpose (`PhCode` net 0 -> 41 / 87 / 79, `CmPossibility` 0 -> 1 / 3,
        # ngoreme `FsFeatStruc` 80 -> 120, mbugwe 231 -> 266). Clause 1 is
        # therefore carrying the weight alone for all three, and the rows they
        # move are each pinned by number in the `TestT124*` classes at the end
        # of this file rather than by a row-for-row equality that would have
        # been false by construction.
        #
        # The T078 trio is deliberately still here and still counted: T124
        # re-pinned the DESTINATION half into new projects precisely so those
        # three artifacts stay valid historical evidence rather than being
        # overwritten, and all three were verified to still hash to their
        # recorded `.fwdata` digests after T124's three live transfers.
        assert len(by_artifact) == 17, (
            "a census artifact arrived or left; the corpus that nulls the two "
            "excluded_not_measurable rows is now "
            + repr(sorted(by_artifact)))
        assert advisory_nulls == 2 * len(by_artifact) == 34


class TestT100TheVocabularyStaysClosedAtSeventeen:
    """T100: the `$comment` overreached, and the enum was right all along.

    `$defs.classRow.not_evaluated_reason` said "Required when verdict_class is
    NOT_EVALUATED" while being absent from `$defs.classRow.required` and
    unenforced by `validate_artifact`. The resolution was to narrow the prose,
    NOT to mint an 18th token -- and the tests below are the evidence for that
    choice rather than a restatement of it.
    """

    def test_an_eighteenth_token_would_be_admissible_as_an_accounting_line(
            self, census_schema):
        """THE DECIDING FACT. `not_evaluated_reason` and `accountedLine.reason`
        are the SAME `$ref`, so a token minted to say "this class could not be
        counted" would immediately be usable to ACCOUNT FOR a shortfall -- to
        retire units nobody measured, which is T101's defect one field to the
        left."""
        classrow = census_schema["$defs"]["classRow"]["properties"]
        line = census_schema["$defs"]["accountedLine"]["properties"]
        assert classrow["not_evaluated_reason"]["$ref"] == "#/$defs/reasonToken"
        assert line["reason"]["$ref"] == "#/$defs/reasonToken"

    def test_the_vocabulary_did_not_grow(self, census_schema):
        """No token was appended, so `schema_version` stays 1 and the
        exact-match tripwire (`test_tokens_match_the_schema_enum_exactly`) is
        untouched."""
        assert len(census_schema["$defs"]["reasonToken"]["enum"]) == 17
        assert len(REASON_TOKENS) == 17

    def test_no_member_of_the_vocabulary_is_true_of_an_unresolved_accessor(
            self):
        """Why the least-wrong token was not stamped. `ABSENT_BY_CONSTRUCTION`
        is the abstract-LCM-base case -- what `MoForm` and `MoMorphSynAnalysis`
        correctly carry -- and asserting it of a class whose repository name
        merely DRIFTED would claim the class cannot exist. That is a different
        and false statement, and emitting a false statement in the artifact is
        the defect T099 had just closed one field to the left."""
        from gramtrans.Lib.models import CENSUS_NOT_EVALUATED_REASONS

        assert CENSUS_NOT_EVALUATED_REASONS == frozenset({
            "ABSENT_BY_CONSTRUCTION",
            "OUT_OF_SCOPE_CLASS",
            "GOVERNED_BY_OTHER_FEATURE",
        })
        assert CENSUS_NOT_EVALUATED_REASONS <= set(REASON_TOKENS)

    def test_the_comment_no_longer_claims_the_field_is_required(
            self, census_schema):
        """The narrowing itself, read from the contract rather than asserted
        about it -- and the `required` list it now agrees with."""
        comment = (census_schema["$defs"]["classRow"]["properties"]
                   ["not_evaluated_reason"]["$comment"])
        assert "Required when verdict_class is NOT_EVALUATED" not in comment
        assert "WHEN THERE IS ONE" in comment
        assert ("not_evaluated_reason"
                not in census_schema["$defs"]["classRow"]["required"])

    def test_a_not_evaluated_row_with_no_reason_is_schema_legal(
            self, census_schema):
        """The row T099 emits, validated against the narrowed contract: legal
        without a reason, and refused by invariant 12 unless corroborated --
        the two halves that make the narrowing non-permissive."""
        row = make_row("MoStemMsa", verdict_class="NOT_EVALUATED",
                       gate_scope="required")
        for field in T099_NULLED_FIELDS:
            row[field] = None
        assert "not_evaluated_reason" not in row
        errors = [{
            "code": "UNHANDLED_EXCEPTION",
            "message": "class MoStemMsa could not be counted in project Dst",
            "class": "MoStemMsa",
            "evidence": "IMoStemMsaRepository could not be resolved",
        }]
        artifact = make_artifact([row], verdict="CENSUS_ERROR", errors=errors)
        assert schema_errors(artifact, census_schema) == []
        assert validate_artifact(artifact) == ()
        assert gate_artifact(artifact).exit_code == 7

        # ... and uncorroborated, the same schema-legal row is refused.
        bare = make_artifact([row], verdict="CENSUS_CLEAN", errors=())
        assert schema_errors(bare, census_schema) == []
        assert [label for label, _ in
                census.uncorroborated_null_rows(bare)] == ["MoStemMsa"]



# ---------------------------------------------------------------------------
# T098: the roster provenance field, and the second-corpus confirmation
#
# The artifact below is a live read-only census of `Ejagham W Mini` ->
# `GT038 Ejagham After` taken WITH `census.verify_roster_sources` in the run
# path, which is the measurement T098 owes: the pre-flight check does not break
# a real run, and all seven natural-key classes report `roster_admitted: true`
# on live data. It doubles as T099's second corpus.
# ---------------------------------------------------------------------------

T098_EJAGHAM = "census-038-t098-ejagham.json"


class TestT098RosterAdmissionIsLive:

    def test_the_artifact_validates_and_holds_its_invariants(
            self, census_schema):
        artifact = _t099(T098_EJAGHAM)
        assert schema_errors(artifact, census_schema) == []
        assert validate_artifact(artifact) == ()

    def test_every_natural_key_class_is_roster_admitted_on_live_data(self):
        """The designed tripwire, measured rather than reasoned about.
        `roster_admitted` is computed by `census.roster_admitted_classes`, which
        reads 035's roster at run time -- so this is the assertion that 035's
        2026-08-19 merge actually made the six 038 classes able to FAIL the gate,
        with no edit in `NATURAL_KEY_DEFINITIONS`."""
        from gramtrans.Lib import census as census_mod

        rows = {r["class"]: r for r in _t099(T098_EJAGHAM)["classes"]}
        for name in sorted(census_mod.NATURAL_KEY_DEFINITIONS):
            duplicates = rows[name].get("duplicates")
            assert duplicates is not None, name
            assert duplicates["roster_admitted"] is True, name

    def test_an_admitted_class_actually_fails_the_run(self):
        """Admission is only meaningful if it can fail something. `PhNCFeatures`
        carries 1 duplicate group / 3 extra objects on this pair and the run is
        DUPLICATE_IDENTITY exit 3 -- one of the six classes 038 proposed, doing
        the job it was proposed for."""
        artifact = _t099(T098_EJAGHAM)
        rows = {r["class"]: r for r in artifact["classes"]}
        assert rows["PhNCFeatures"]["duplicates"]["extra_objects"] == 3
        assert artifact["totals"]["duplicate_extra_objects"] == 3
        assert (artifact["verdict"], artifact["exit_code"]) == (
            "DUPLICATE_IDENTITY", 3)

    def test_t099s_nulls_reproduce_on_a_second_corpus(self):
        rows = {r["class"]: r for r in _t099(T098_EJAGHAM)["classes"]}
        for name in T099_NULLED_CLASSES:
            for field in T099_NULLED_FIELDS:
                assert rows[name][field] is None, name + "." + field
            assert rows[name]["verdict_class"] == "NOT_EVALUATED"


# ---------------------------------------------------------------------------
# T078: the post-037 baseline, and the re-scoped report-only residual set
#
# T078's task line reads "re-run the census after 037 lands to obtain the
# post-037 baseline, then re-scope the report-only residual set". THE FIRST
# HALF OF THAT PREMISE HAD ALREADY EXPIRED WHEN IT WAS WRITTEN DOWN: 037 was
# merged into this branch at `a824b8d` on 2026-08-19 (it reached `main` in the
# same commit), so EVERY census this feature has taken since -- T077's, T095's,
# T098's, T099's -- was already post-037. The re-run below therefore adds no
# number that was not already on disk. What it adds is the PROOF that the
# numbers on disk are the current ones, taken from a clean `2482a53` with a
# `Lib/census.py` that has not changed since `8169f6f`.
#
# THE THREE ARTIFACTS. Read-only `census_cli run` over the three sanctioned
# pairs, 2026-08-25, all three DUPLICATE_IDENTITY / exit 3 (`PhNCFeatures`
# duplicates -- T082's remaining item, not T078's):
#
#   census-038-t078-ejagham.json  Ejagham W Mini           -> GT038 Ejagham After
#   census-038-t078-ngoreme.json  Ngoreme FLEx             -> GT038 Ngoreme After
#   census-038-t078-mbugwe.json   Mbugwe LizzieHC practice -> GT038 Phase6 Target
#
# Each reproduces its predecessor ROW FOR ROW -- `census-038-t095-*.json` for
# the first two, `census-038-t077-mbugwe-phase6.json` for the third -- with
# every total equal. The only fields that differ at all are two path strings
# (`starter_baseline.path`, `transfer_run.report_path`, absolute vs relative).
#
# WHICH ARTIFACTS ARE STILL THE BASELINE, measured the way T102 taught: from
# each artifact's own recorded digests against the files on disk. T098's and
# T099's are NOT -- their destinations have since been re-transferred, and
# `Ngoreme FLEx` itself moved. That is why "T098/T099 already did the re-run"
# is not the answer either: they were post-037, and they are now stale.
# ---------------------------------------------------------------------------

T078_BASELINES = {
    "ejagham": "census-038-t078-ejagham.json",
    "ngoreme": "census-038-t078-ngoreme.json",
    "mbugwe": "census-038-t078-mbugwe.json",
}

#: Each T078 baseline and the artifact it must reproduce row for row.
T078_PREDECESSORS = {
    "census-038-t078-ejagham.json": "census-038-t095-ejagham.json",
    "census-038-t078-ngoreme.json": "census-038-t095-ngoreme.json",
    "census-038-t078-mbugwe.json": "census-038-t077-mbugwe-phase6.json",
}

#: The row fields the reproduction claim is about. Deliberately the same four
#: T102 narrowed its chain to (`_CENSUS_COUNT_FIELDS` in
#: `test_038_closure_edge_audit.py`) and for the same reason: `verdict_class`
#: and `unexplained_shortfall` are the instrument's READING of the counts, and
#: the instrument is allowed to improve. Here it has not -- `Lib/census.py` is
#: untouched since `8169f6f` -- so the readings match too, and that is asserted
#: separately rather than folded in.
T078_COUNT_FIELDS = (
    "source_count", "destination_count_total", "destination_count_net",
    "difference",
)

#: R7's report-only classes that the post-037 measurement CLOSES: MATCHED on
#: all three corpora, so nothing is hiding behind their report line.
#:
#: `MoInflClass` and the `LexEntryInflType` +1 excess are the two R7 named as
#: "expected to close as a side effect of Phases 1/3 and verified by re-census
#: rather than coded separately". They did. `FsSymFeatVal` and
#: `FsClosedFeature` are two of the four `Fs*` cascade members R7 expected to
#: close; the other two did not (see `T078_STILL_OPEN`). `FsComplexFeature`
#: R7 kept report-only BY DECISION and it is green anyway -- which is exactly
#: the "report-only class rots behind a green gate" risk R7 recorded, and is
#: T079's `status: "unmeasurable"` to answer, not this test's.
T078_CLOSED_BY_MEASUREMENT = (
    "MoInflClass",
    "LexEntryInflType",
    "FsSymFeatVal",
    "FsClosedFeature",
    "FsComplexFeature",
)

#: R7's report-only classes that are STILL OPEN, with the difference measured
#: on each corpus, in the order `(ejagham, ngoreme, mbugwe)`. Pinned as numbers
#: rather than as "still failing" so a later change that closes one, or reopens
#: one, has to come here and say which.
T078_STILL_OPEN = {
    # The phonological-context family. R7 deferred all six to "the post-037
    # re-census since 037's structural-rebuild path may already move these".
    # It did not: 037 moved none of them. T076/T077 moved three (see below).
    # T107 (2026-08-25) MOVED FOUR OF THESE ON THE EJAGHAM PAIR. The figures
    # here are T078's and stay as they are -- they are asserted against T078's
    # committed artifacts, which are a fixed measurement, not a live reading.
    # The post-T107 numbers live in `TestT107TheBoundaryContextCreatePath`
    # (`PhSimpleContextBdry` -9 -> 0 MATCHED, `PhSequenceContext` -40 -> -6,
    # `PhSimpleContextNC` -38 -> -2, `PhSimpleContextSeg` -27 -> -1). Read
    # this table as "as of T078", never as "as of now".
    "PhSequenceContext": (-40, -2, -11),
    "PhSimpleContextNC": (-38, -7, -23),
    "PhSimpleContextSeg": (-27, -3, -21),
    "PhSimpleContextBdry": (-9, -4, -15),
    "PhCode": (-43, -89, -79),
    "PhFeatureConstraint": (0, -47, -32),
    # Named individually by R7 outside the phonology family.
    "LexReference": (0, -5, 0),
    "CmFile": (0, -2, -2173),
    # The half of the `Fs*` cascade that did NOT close.
    "FsFeatStruc": (-138, -1691, -198),
    "FsClosedValue": (-562, -2045, -630),
}

#: The three rows T076/T077 MOVED, with the previous figure beside the current
#: one on the corpus that moved. Kept as a table because "T076 closed the
#: phonological-context family" is the reading T078 has to refuse: it moved
#: three rows on one corpus and closed none of them.
T078_T077_MOVED_NOT_CLOSED = {
    # class: (mbugwe before T076/T077, mbugwe now)
    "PhSequenceContext": (-17, -11),
    "PhSimpleContextNC": (-28, -23),
    "PhSimpleContextSeg": (-23, -21),
}

T078_PROCESS_RULES = "process-rules-038-t078-corpus.json"


def _t078(name: str) -> dict:
    path = _repo_root() / "tests" / "integration" / "_snapshots" / name
    assert path.is_file(), "missing T078 measurement artifact: " + str(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _t078_rows(name: str) -> dict:
    """Rows by class name. `FsFeatStrucType` is split by owning feature system
    (the fidelity-census.md amendment R7's third finding forced), so it is
    excluded here and asserted on its own."""
    return {r["class"]: r for r in _t078(name)["classes"]
            if r["class"] != "FsFeatStrucType"}


def _t078_fwdata_status(project_block) -> str:
    """`absent` / `match` / `drifted`, from the artifact's own recorded
    `fwdata_sha256_after` against the file on disk. Mirrors
    `test_038_closure_edge_audit._fwdata_status` deliberately rather than
    importing it: a test module is not a library, and the duplication is four
    lines against a cross-module import of a private helper."""
    import hashlib

    path = Path(project_block["path"]) / (project_block["name"] + ".fwdata")
    if not path.is_file():
        return "absent"
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return ("match" if digest == project_block["fwdata_sha256_after"]
            else "drifted")


class TestT078ThePost037Baseline:
    """Three read-only censuses, and the claim that they are the baseline."""

    @pytest.mark.parametrize("pair", sorted(T078_BASELINES))
    def test_the_artifact_validates_and_holds_its_invariants(
            self, pair, census_schema):
        artifact = _t078(T078_BASELINES[pair])
        assert schema_errors(artifact, census_schema) == []
        assert validate_artifact(artifact) == ()

    @pytest.mark.parametrize("pair", sorted(T078_BASELINES))
    def test_every_baseline_was_taken_read_only(self, pair):
        """The safety claim, from the artifact rather than from the commit
        message. A census that wrote to a project cannot be a baseline for a
        feature whose corpus includes projects that must never be written."""
        projects = _t078(T078_BASELINES[pair])["projects"]
        for side in ("source", "destination"):
            block = projects[side]
            assert block["opened_read_only"] is True, side
            assert (block["fwdata_sha256_before"]
                    == block["fwdata_sha256_after"]), side

    @pytest.mark.parametrize("pair", sorted(T078_BASELINES))
    def test_the_recorded_exit_code_is_reported_and_not_laundered(self, pair):
        """All three exit 3, and the number is written down here so nobody can
        later read this section as "the post-037 baseline was clean". The
        verdict is `DUPLICATE_IDENTITY`, driven by `PhNCFeatures` duplicates --
        T082's remaining `038-NK-P3` item, which T098 already narrowed to that
        one class. It is not T078's, and it is not hidden."""
        artifact = _t078(T078_BASELINES[pair])
        assert (artifact["verdict"], artifact["exit_code"]) == (
            "DUPLICATE_IDENTITY", 3)
        assert artifact["totals"]["duplicate_extra_objects"] > 0

    #: Per pair, what each side of T078's artifacts hashes to TODAY.
    #:
    #: **T107 (2026-08-25) DRIFTED TWO OF THESE, and that is the mechanism
    #: working rather than failing.** T078's own version of this test asserted
    #: `match` on all six readings, and its accompanying test recorded exactly
    #: this happening to T098's and T099's artifacts when T095 re-transferred
    #: their destinations. T107 re-transferred `GT038 Ejagham After` and
    #: `GT038 Phase6 Target` to take its own acceptance, so T078's recorded
    #: destination digests for those two pairs are now history. THE SOURCES
    #: ARE UNMOVED on all three, which is the claim that actually matters:
    #: every census this feature takes is read-only, so a source that drifted
    #: would mean the corpus itself changed under the measurement.
    #:
    #: Ngoreme is untouched because T107's acceptance did not name it -- see
    #: `TestT107...::test_the_ngoreme_pair_was_not_re_measured_and_says_so`.
    T078_FWDATA_STATUS_TODAY = {
        "ejagham": {"source": "match", "destination": "drifted"},
        "mbugwe": {"source": "match", "destination": "drifted"},
        "ngoreme": {"source": "match", "destination": "match"},
    }

    @pytest.mark.parametrize("pair", sorted(T078_BASELINES))
    def test_each_baseline_is_reproducible_against_the_live_projects(
            self, pair):
        """T102's test, applied to the artifacts that replaced the drifted
        ones -- and now recording their own drift, per side, with the run that
        caused it named.

        Asserted as an exact table rather than as "match everywhere" so that a
        `drifted` reverting to `match` is as loud as the other direction: a
        destination that re-acquired T078's digest would mean somebody
        restored over T107's evidence."""
        artifact = _t078(T078_BASELINES[pair])
        expected = self.T078_FWDATA_STATUS_TODAY[pair]
        for side in ("source", "destination"):
            assert _t078_fwdata_status(artifact["projects"][side]) \
                == expected[side], pair + "." + side

    def test_the_artifacts_t078_supersedes_are_named_and_measured(self):
        """WHY A RE-RUN WAS NEEDED AT ALL, given that 037 landed six days
        earlier. T098's and T099's artifacts were post-037 and are now stale:
        their destinations were re-transferred by T095's runs on 2026-08-24 and
        `Ngoreme FLEx` itself moved. This is meant to go red the day either
        drifts back or a project is deleted -- a `drifted` becoming `match` is
        as much a change of evidence as the other direction."""
        assert _t078_fwdata_status(
            _t078("census-038-t098-ejagham.json")["projects"]["source"]
        ) == "match"
        assert _t078_fwdata_status(
            _t078("census-038-t098-ejagham.json")["projects"]["destination"]
        ) == "drifted"
        for side in ("source", "destination"):
            assert _t078_fwdata_status(
                _t078("census-038-t099-ngoreme-after.json")["projects"][side]
            ) == "drifted", side

    def test_the_instrument_has_not_moved_since_the_predecessors_were_taken(
            self):
        """The other half of "these numbers are current". A row-for-row match
        between two artifacts proves nothing about the instrument if the
        instrument changed between them -- T102's finding exactly. So the claim
        is made where it can be checked: `Lib/census.py` and `census_cli.py`
        are byte-identical to what produced `census-038-t095-*` (`4ec8fff`) and
        `census-038-t077-mbugwe-phase6` (`8169f6f`), which is why the
        reproduction below extends to `verdict_class` and not only to counts.
        Asserted as the observable consequence rather than by shelling out to
        git: every reading matches, on every row, on all three pairs."""
        for later, earlier in sorted(T078_PREDECESSORS.items()):
            new_rows = _t078(later)["classes"]
            old_rows = _t078(earlier)["classes"]
            assert len(new_rows) == len(old_rows) == 75, later
            for a, b in zip(old_rows, new_rows):
                assert a["class"] == b["class"], later
                assert a["verdict_class"] == b["verdict_class"], (
                    later + ":" + str(a["class"]))
                assert (a["unexplained_shortfall"]
                        == b["unexplained_shortfall"]), (
                    later + ":" + str(a["class"]))

    @pytest.mark.parametrize("later", sorted(T078_PREDECESSORS))
    def test_each_baseline_reproduces_its_predecessor_row_for_row(self, later):
        """The measurement that makes T078 a confirmation rather than a
        discovery: 75 rows, 0 differing, every total equal. Nothing about the
        transfer or the instrument moved between the predecessor and this run,
        so the post-037 baseline was already on disk and this proves it."""
        earlier = T078_PREDECESSORS[later]
        new_rows = _t078(later)["classes"]
        old_rows = _t078(earlier)["classes"]
        assert len(new_rows) == len(old_rows)
        differing = []
        for a, b in zip(old_rows, new_rows):
            assert a["class"] == b["class"]
            for field in T078_COUNT_FIELDS:
                if a[field] != b[field]:
                    differing.append((a["class"], field, a[field], b[field]))
        assert differing == [], later
        assert _t078(later)["totals"] == _t078(earlier)["totals"], later

    @pytest.mark.parametrize("later", sorted(T078_PREDECESSORS))
    def test_both_sides_of_each_reproduction_name_the_same_pair(self, later):
        """A row-for-row match between censuses of DIFFERENT pairs would be
        meaningless, and T102's chain shows that is not a hypothetical."""
        earlier = T078_PREDECESSORS[later]
        for side in ("source", "destination"):
            assert (_t078(later)["projects"][side]["name"]
                    == _t078(earlier)["projects"][side]["name"]), side


class TestT078TheRescopedReportOnlyResidualSet:
    """R7's report-only list, re-scoped class by class against the baseline.

    This is the input T079 consumes. Every class R7 named appears in exactly
    one of the two tables, and the tables are asserted DISJOINT and COMPLETE
    against R7's list, so a class cannot fall out of scope by being forgotten
    -- which is the failure mode a prose re-scoping has.
    """

    #: Every class R7 lists as report-only, plus the one it rules on
    #: explicitly (`FsComplexFeature`). `CmAnthroItem` and the texts/wordforms
    #: path are governed separately and are asserted on their own below;
    #: `FsFeatStrucType` is NOT here because R7 promoted it out of report-only
    #: to a Phase 1 prerequisite.
    R7_NAMED = (
        "PhSequenceContext", "PhSimpleContextNC", "PhSimpleContextBdry",
        "PhSimpleContextSeg", "PhCode", "PhFeatureConstraint",
        "LexReference", "CmFile", "MoInflClass", "LexEntryInflType",
        "FsFeatStruc", "FsClosedValue", "FsSymFeatVal", "FsClosedFeature",
        "FsComplexFeature",
    )

    def test_every_class_r7_named_is_scoped_exactly_once(self):
        closed = set(T078_CLOSED_BY_MEASUREMENT)
        still_open = set(T078_STILL_OPEN)
        assert closed & still_open == set()
        assert closed | still_open == set(self.R7_NAMED)

    @pytest.mark.parametrize("cls", sorted(T078_CLOSED_BY_MEASUREMENT))
    def test_a_closed_class_is_matched_on_all_three_corpora(self, cls):
        for pair, name in sorted(T078_BASELINES.items()):
            row = _t078_rows(name)[cls]
            assert row["difference"] == 0, pair + ":" + cls
            assert row["verdict_class"] == "MATCHED", pair + ":" + cls
            assert row["unexplained_shortfall"] == 0, pair + ":" + cls

    @pytest.mark.parametrize("cls", sorted(T078_STILL_OPEN))
    def test_a_still_open_class_carries_the_difference_recorded_here(
            self, cls):
        """The numbers, not the adjective. A residual class that quietly gets
        worse is the thing a report line cannot catch on its own."""
        expected = T078_STILL_OPEN[cls]
        measured = tuple(
            _t078_rows(T078_BASELINES[pair])[cls]["difference"]
            for pair in ("ejagham", "ngoreme", "mbugwe"))
        assert measured == expected, cls

    def test_the_two_r7_figures_that_were_a_single_corpus_all_along(self):
        """R7 records `LexReference` 5 -> 0 and `CmFile` 2 -> 0 as if they were
        properties of the transfer. Both are `Ngoreme FLEx` readings: on the
        Mbugwe corpus `CmFile` is 2173 -> 0, three orders of magnitude larger.
        The class stays report-only; the NUMBER behind it does not survive
        re-scoping, and that is worth a test rather than a footnote."""
        ngoreme = _t078_rows(T078_BASELINES["ngoreme"])
        mbugwe = _t078_rows(T078_BASELINES["mbugwe"])
        assert (ngoreme["LexReference"]["source_count"],
                ngoreme["LexReference"]["destination_count_total"]) == (5, 0)
        assert (ngoreme["CmFile"]["source_count"],
                ngoreme["CmFile"]["destination_count_total"]) == (2, 0)
        assert (mbugwe["CmFile"]["source_count"],
                mbugwe["CmFile"]["destination_count_total"]) == (2173, 0)

    def test_t076_and_t077_moved_three_phonology_rows_and_closed_none(self):
        """The reading T078 has to refuse. T077's own note states the delta
        (`PhSequenceContext` -17 -> -11, `PhSimpleContextNC` -28 -> -23,
        `PhSimpleContextSeg` -23 -> -21 on Mbugwe) and it is real -- but a row
        that moves is not a row that closes, and all three are still SHORTFALL
        on all three corpora. So the phonological-context family stays
        report-only, with a smaller number on one corpus."""
        mbugwe = _t078_rows(T078_BASELINES["mbugwe"])
        for cls, (before, now) in sorted(T078_T077_MOVED_NOT_CLOSED.items()):
            assert now > before, cls          # less negative
            assert mbugwe[cls]["difference"] == now, cls
            assert mbugwe[cls]["verdict_class"] == "SHORTFALL", cls

    def test_fsfeatstructype_is_split_by_feature_system_and_both_halves_match(
            self):
        """R7 PROMOTED this class out of report-only to a Phase 1 prerequisite,
        on the ground that ~2,083 restored MSAs would otherwise carry an
        unsatisfiable `TypeRA`. The post-037 baseline says the prerequisite is
        met: R7's evidence recorded `FsFeatStrucType` 4 -> 0 in both projects,
        and it is now 3 + 1 -> 3 + 1 on both, MATCHED on each half.

        R7's third finding is visible in the same rows: there are TWO feature
        systems, so the class is reported as two rows disambiguated by
        `owning_feature_system` rather than as one ambiguous total."""
        for pair, name in sorted(T078_BASELINES.items()):
            halves = {r["owning_feature_system"]: r
                      for r in _t078(name)["classes"]
                      if r["class"] == "FsFeatStrucType"}
            assert set(halves) == {"LangProject.MsFeatureSystemOA",
                                   "LangProject.PhFeatureSystemOA"}, pair
            for system, row in sorted(halves.items()):
                assert row["verdict_class"] == "MATCHED", pair + ":" + system
                assert row["difference"] == 0, pair + ":" + system
        ejagham = {r["owning_feature_system"]: r["source_count"]
                   for r in _t078(T078_BASELINES["ejagham"])["classes"]
                   if r["class"] == "FsFeatStrucType"}
        assert sorted(ejagham.values()) == [1, 3]

    def test_cmanthroitem_is_still_excluded_from_the_delta(self):
        """R7's decision, unchanged by the re-scoping: `CmAnthroItem` 859 -> 0
        is EXCLUDED rather than reported as a shortfall. Pinned so the
        exclusion cannot quietly become a shortfall or a match."""
        for pair, name in sorted(T078_BASELINES.items()):
            row = _t078_rows(name)["CmAnthroItem"]
            assert row["verdict_class"] == "NOT_EVALUATED", pair
            assert row["unexplained_shortfall"] == 0, pair

    def test_the_texts_and_wordforms_path_is_still_report_only_and_lossy(self):
        """Governed by its own feature, so nothing here fixes it -- but the
        magnitude is what makes `total_shortfall` unusable as a headline, and
        R7's "the whole texts/wordforms path" deserves the number. On Ngoreme
        these seven classes alone account for over fifty thousand objects."""
        rows = _t078_rows(T078_BASELINES["ngoreme"])
        texts = ("WfiWordform", "WfiAnalysis", "WfiGloss", "WfiMorphBundle",
                 "StTxtPara", "StText", "Segment")
        for cls in texts:
            assert rows[cls]["verdict_class"] == "SHORTFALL", cls
        assert sum(-rows[cls]["difference"] for cls in texts) > 50000


class TestT078PhSimpleContextBdryIsExercisedAfterAll:
    """THE ONE FINDING THE RE-SCOPING PRODUCED, and it falsifies a premise this
    repo has written down in four places.

    T076 left `PhSimpleContextBdry` and `PhIterationContext` behind
    `_PROCESS_UNEXERCISED_CLASSES` on an explicit, measured ground: `Mbugwe
    LizzieHC practice` holds 22 and 11 of them in `ContextsOS` and **not one is
    referenced by any of its 18 affix process rules**, so admitting them "would
    ship a create path no corpus can check". That measurement is correct and
    the conclusion drawn from it is not, because it was taken on one corpus.

    `Ejagham W Mini` holds 13 `MoAffixProcess` rules and **13 of 13 are
    reported-and-skipped naming `PhSimpleContextBdry`** -- 8 as a direct input
    member, 5 through a `PhSequenceContext` in `PhPhonData.ContextsOS` that
    references one. Across the whole sanctioned corpus: 32 rules, 19
    reproduced, 13 not, and `PhSimpleContextBdry` is the ONLY blocking class.

    WHAT T078 DID NOT DO. It did not admit the class. That is a create-path
    change in `categories.py`, US5's territory and a live-behaviour change that
    needs its own census -- filed as T107. What T078 owes is the measurement,
    the re-scoping (`PhSimpleContextBdry` stops being "deferred to the post-037
    re-census" and becomes report-only with a named owner and a number), and
    the correction of the premise where it is written down.

    SC-010 is NOT violated by any of this: all 13 rules are dropped WITH A
    REASON that names the blocking class, which is why the census row for
    `MoAffixProcess` (13 -> 0 on Ejagham) has an explanation to point at.
    """

    def test_the_evidence_artifact_is_committed_repo_data(self):
        path = (_repo_root() / "tests" / "integration" / "_snapshots"
                / T078_PROCESS_RULES)
        assert path.is_file()

    def test_the_corpus_wide_tally(self):
        totals = _t078(T078_PROCESS_RULES)["corpus_totals"]
        assert totals["rules_total"] == 32
        assert totals["rules_reproduced"] == 19
        assert totals["rules_not_reproduced"] == 13
        assert totals["distinct_blocking_classes"] == ["PhSimpleContextBdry"]

    def test_the_per_corpus_split(self):
        by_label = {c["label"]: c
                    for c in _t078(T078_PROCESS_RULES)["corpora"]}
        assert (by_label["mbugwe"]["rules_total"],
                by_label["mbugwe"]["rules_reproduced"]) == (18, 18)
        assert (by_label["ngoreme"]["rules_total"],
                by_label["ngoreme"]["rules_reproduced"]) == (1, 1)
        assert (by_label["ejagham"]["rules_total"],
                by_label["ejagham"]["rules_reproduced"]) == (13, 0)

    def test_all_thirteen_ejagham_rules_are_blocked_by_the_same_class(self):
        ejagham = next(c for c in _t078(T078_PROCESS_RULES)["corpora"]
                       if c["label"] == "ejagham")
        assert ejagham["blocked_by"] == [
            {"classes": ["PhSimpleContextBdry"], "rules": 13}]
        assert ejagham["blocked_as_direct_input_member"] == {
            "PhSimpleContextBdry": 8}

    def test_the_class_left_the_unexercised_gate_at_t107(self):
        """**T107 CLOSED THIS, and the assertions are inverted rather than
        deleted.** T078's version read "still held behind the gate", and its
        passing was the statement that T107 was open. Inverting it keeps the
        same fact under measurement from the other side: the class now has a
        create path on BOTH routes T078 found -- `_PROCESS_INPUT_FACTORIES`
        for the 8 rules that own a boundary context directly, and
        `_PROCESS_SHARED_CONTEXT_CLASSES` for the 5 that reach the single
        `PhPhonData`-owned one through a `PhSequenceContext`.

        `PhIterationContext` is asserted to have stayed put, because T107's
        scope was one class and the gate is what keeps that true."""
        from gramtrans.Lib import categories as _cats

        assert ("PhSimpleContextBdry"
                not in _cats._PROCESS_UNEXERCISED_CLASSES)
        assert "PhSimpleContextBdry" in _cats._PROCESS_INPUT_FACTORIES
        assert "PhSimpleContextBdry" in _cats._PROCESS_SHARED_CONTEXT_CLASSES
        assert "PhIterationContext" in _cats._PROCESS_UNEXERCISED_CLASSES
        assert ("PhIterationContext"
                not in _cats._PROCESS_SHARED_CONTEXT_CLASSES)

    def test_the_census_row_the_block_produces_is_reported_not_silent(self):
        """`MoAffixProcess` 13 -> 0 on the Ejagham pair. The row is a
        SHORTFALL and the loss is explained by the 13 skip reasons -- which is
        the difference between this and the silent losses this feature exists
        to end."""
        row = _t078_rows(T078_BASELINES["ejagham"])["MoAffixProcess"]
        assert (row["source_count"], row["destination_count_total"]) == (13, 0)
        assert row["verdict_class"] == "SHORTFALL"
        ejagham = next(c for c in _t078(T078_PROCESS_RULES)["corpora"]
                       if c["label"] == "ejagham")
        assert ejagham["rules_not_reproduced"] == row["source_count"]

    def test_the_other_two_corpora_do_not_hide_the_finding(self):
        """Mbugwe 18/18 and Ngoreme 1/1: on either of them alone
        `MoAffixProcess` is MATCHED and there is nothing to see. The corpus
        lesson of this feature, one more time -- a gate is only as good as the
        pair it ran on."""
        for pair in ("ngoreme", "mbugwe"):
            row = _t078_rows(T078_BASELINES[pair])["MoAffixProcess"]
            assert row["verdict_class"] == "MATCHED", pair
            assert row["difference"] == 0, pair

    def test_the_skip_reason_the_engine_emits_is_now_factually_wrong(self):
        """A DEBT PINNED RATHER THAN FIXED, and named so nobody has to
        rediscover it.

        The live drop reason reads "a class with zero instances in any
        sanctioned corpus". Every sanctioned source in this corpus holds
        `PhSimpleContextBdry`: 10 on Ejagham, 13 on Ngoreme, 24 on Mbugwe. The
        sentence is false about all three, and it is the sentence a user reads
        to find out why 13 of their rules did not arrive.

        NOT corrected in T078, on the same reasoning T106 used for its own
        filing: it is live run-report output for four classes, and changing it
        is a reporting change with no census behind it. It belongs to **T107**
        (which owns the class) or to T079 (which owns report lines). What T078
        owes is the number that makes the sentence false, asserted here.

        **T107 CORRECTED IT (2026-08-25), and not the way this docstring
        anticipated.** Deferring paid: the sentence turned out to be false of
        `PhIterationContext` too -- Mbugwe holds 11 in `ContextsOS` and a live
        run created 9 more under transferred phonological rules -- so deleting
        the one false case would have left a false sentence standing. The
        claim is now the per-RULE one every remaining member satisfies: "a
        class no affix process rule in any sanctioned corpus uses". THE
        NUMBERS BELOW ARE UNCHANGED and still assert exactly what T078 owed,
        because they are properties of the SOURCES, not of the string."""
        counts = {
            pair: _t078_rows(name)["PhSimpleContextBdry"]["source_count"]
            for pair, name in T078_BASELINES.items()
        }
        assert counts == {"ejagham": 10, "ngoreme": 13, "mbugwe": 24}
        assert min(counts.values()) > 0


# ===========================================================================
# T107 -- the boundary context's create path, and the blocker behind it
# ===========================================================================
#
# T078 measured the block and filed this task with an acceptance spelled out:
# a restored-target Ejagham run showing `MoAffixProcess` 13 -> 13 with the
# context classes moving by an accounted delta, plus a Mbugwe re-run proving
# 18/18 is unmoved.
#
# THE FIGURE IS 13 -> 12, AND THE THIRTEENTH IS NOT THIS CLASS. Rule
# `24ed706a` is refused because its `OutputOS[0]` is a `MoCopyFromInput` whose
# `Content` is EMPTY IN THE SOURCE -- a copy step with nothing to copy.
# `_resolve_process_graph` checks input members before output steps, so the
# boundary-context block fired first on all 13 rules and masked it. T078's
# "the ONLY blocking class anywhere" was true of the reasons the ENGINE
# EMITTED, which is all a skip reason can ever report: one blocker per rule,
# the first one found. **A single-blocker census is a lower bound on the work,
# never a count of it.** Asserted below rather than explained away.

T107_EJAGHAM = "census-038-t107-ejagham.json"
T107_MBUGWE = "census-038-t107-mbugwe-phase6.json"
T107_MBUGWE_RULES = "process-rules-038-t107-mbugwe.json"

#: The per-rule evidence, DERIVED read-only from the run report and COMMITTED,
#: because `_run_reports/` is gitignored -- asserting against the raw report
#: would make these tests pass only on the machine that produced it. Exactly
#: T078's arrangement with `process-rules-038-t078-corpus.json`.
T107_EJAGHAM_RULES = "process-rules-038-t107-ejagham.json"

#: The rule the boundary-context fix does NOT reach, and why. Named here so a
#: later run that reproduces 13 of 13 has to come here and say what changed
#: about the SOURCE -- because nothing in this engine can rebuild a copy step
#: whose `ContentRA` is absent.
T107_SOURCE_DEFECT_RULE = "24ed706a-7df2-4609-a37b-2bfa28853ccc"

#: The Ejagham rows T107 moved, `class -> (before_diff, after_diff)`, against
#: T078's committed measurement of the same pair. EXACTLY these five and no
#: others: the value of this table is as much in what is absent from it as in
#: what is in it, since a create path that moved an unrelated row would be
#: doing something nobody measured.
T107_EJAGHAM_MOVED = {
    "MoAffixProcess": (-13, -1),
    "PhSequenceContext": (-40, -6),
    "PhSimpleContextBdry": (-9, 0),
    "PhSimpleContextNC": (-38, -2),
    "PhSimpleContextSeg": (-27, -1),
}

#: Every source object still missing after T107, by class, with the owner that
#: accounts for it. Established by a read-only GUID diff of the two `.fwdata`
#: files rather than inferred from counts, because "the number went down" and
#: "the right objects arrived" are different claims.
T107_EJAGHAM_RESIDUAL_OWNERS = {
    "MoAffixProcess": {"the source-defect rule": 1},
    "PhSequenceContext": {"the source-defect rule": 5, "PhSegRuleRHS": 1},
    "PhSimpleContextNC": {"PhPhonData": 2},
    "PhSimpleContextSeg": {"PhPhonData": 1},
}


def _t107_rules() -> dict:
    return _t078(T107_EJAGHAM_RULES)


class TestT107TheBoundaryContextCreatePath:
    """The live acceptance, from committed artifacts rather than a re-run."""

    def test_the_boundary_context_class_now_arrives_whole(self):
        """THE HEADLINE. `PhSimpleContextBdry` 10 -> 1 becomes 10 -> 10
        MATCHED on the pair that exercises it. All ten, which includes the one
        owned by a `PhSegRuleRHS` that 037's phonological-rule path brings
        across -- so this row is not evidence for T107 alone, which is why the
        rule count below is asserted too."""
        row = _t078_rows(T107_EJAGHAM)["PhSimpleContextBdry"]
        assert (row["source_count"], row["destination_count_total"]) == (10, 10)
        assert row["difference"] == 0
        assert row["verdict_class"] == "MATCHED"

    def test_twelve_of_thirteen_rules_arrive(self):
        """13 -> 12, not the 13 -> 13 the task asked for, and the difference
        is a finding rather than a shortfall in the fix.

        Asserted as an exact figure both ways: 12 arrived, and the row is
        still a SHORTFALL of exactly 1. A test that only checked "more than
        before" would pass on a partial fix."""
        row = _t078_rows(T107_EJAGHAM)["MoAffixProcess"]
        assert (row["source_count"], row["destination_count_total"]) == (13, 12)
        assert row["difference"] == -1
        assert row["verdict_class"] == "SHORTFALL"

    def test_the_thirteenth_rule_is_blocked_by_an_empty_source_copy_step(self):
        """The blocker behind the blocker, from the run report the census
        judges. The reason must name `MoCopyFromInput` and must NOT name
        `PhSimpleContextBdry` -- if it did, the create path would not be
        working and this whole task would be reporting someone else's
        success."""
        rules = _t107_rules()
        assert rules["rules_total"] == 13
        assert rules["rules_reproduced"] == 12
        blocked = rules["rules_not_reproduced"]
        assert len(blocked) == 1
        assert blocked[0]["source_guid"] == T107_SOURCE_DEFECT_RULE
        reason = " ".join(blocked[0]["reason"].split())
        assert "MoCopyFromInput" in reason
        assert "no ContentRA" in reason
        assert "PhSimpleContextBdry" not in reason

    def test_no_surviving_skip_reason_names_the_boundary_context(self):
        """The claim T107 actually owes, stated over EVERY unreproduced rule
        rather than only over the one that failed: the class is gone from the
        engine's vocabulary of blockers on this pair."""
        for rule in _t107_rules()["rules_not_reproduced"]:
            assert "PhSimpleContextBdry" not in (rule["reason"] or ""), \
                rule["source_guid"]

    def test_the_boundary_context_is_reported_on_the_rules_that_use_it(self):
        """SC-010: a context this run created inside a rule is not a silent
        write. **Eight** of Ejagham's boundary contexts are direct `InputOS`
        members -- the count predicted from the source's object graph before a
        line was written -- so `input_contexts` must name the class on exactly
        eight rules. Otherwise the MATCHED row above could be satisfied by
        contexts that arrived some other way.

        And each must name the marker it was wired to: a context reported with
        an empty `referent_guid` is one that matches nothing, the outcome the
        resolvability test exists to refuse. All eight name the WORD boundary,
        `3bde17ce-...cb56`, which is fixed FLEx content present on both sides
        -- which is why no closure edge is owed one hop out."""
        rules = _t107_rules()
        direct = rules["boundary_context_input_members"]
        assert len(direct) == 8
        assert len({d["rule"] for d in direct}) == 8
        assert all(d["referent_guid"] == "3bde17ce-e39a-4bae-8a5c-a8d96fd4cb56"
                   for d in direct)
        assert rules["input_context_class_totals"]["PhSimpleContextBdry"] == 8

    @pytest.mark.parametrize("cls", sorted(T107_EJAGHAM_MOVED))
    def test_each_moved_row_moved_by_the_measured_amount(self, cls):
        """Numbers, not directions. Each of the five is pinned to its before
        and after difference, so a later change that moves one has to come
        here and say so."""
        before, after = T107_EJAGHAM_MOVED[cls]
        assert _t078_rows(T078_BASELINES["ejagham"])[cls]["difference"] \
            == before, cls
        assert _t078_rows(T107_EJAGHAM)[cls]["difference"] == after, cls

    def test_exactly_those_five_rows_moved_and_nothing_else(self):
        """The other half of the same claim, and the stronger half. 74 rows
        are compared field for field; five differ. A create path that moved an
        unrelated row would be doing something nobody measured, and `PhCode`
        -43 staying put is the specific case worth naming -- it is R7 residue
        that a careless widening of the phonology create surface would have
        disturbed."""
        before = _t078_rows(T078_BASELINES["ejagham"])
        after = _t078_rows(T107_EJAGHAM)
        assert set(before) == set(after)
        fields = ("source_count", "destination_count_total", "difference",
                  "verdict_class")
        moved = {c for c in before
                 if tuple(before[c][f] for f in fields)
                 != tuple(after[c][f] for f in fields)}
        assert moved == set(T107_EJAGHAM_MOVED)
        assert after["PhCode"]["difference"] == -43

    def test_every_residual_object_has_an_owner_outside_this_task(self):
        """The delta is ACCOUNTED, which is what the acceptance asked for and
        is a different claim from "the number went down".

        The counts here come from a read-only GUID diff of the two `.fwdata`
        files: every source object still absent is owned either by the one
        source-defect rule, by a `PhSegRuleRHS` (a phonological rule, 037's
        successor's), or directly by `PhPhonData` (the shared pool no affix
        process rule reaches). Asserted against the census difference so the
        table cannot drift from the measurement it explains."""
        after = _t078_rows(T107_EJAGHAM)
        for cls, owners in sorted(T107_EJAGHAM_RESIDUAL_OWNERS.items()):
            assert after[cls]["difference"] == -sum(owners.values()), cls
        # And no OTHER class in the moved set has a residual to account for.
        accounted = set(T107_EJAGHAM_RESIDUAL_OWNERS)
        for cls in sorted(set(T107_EJAGHAM_MOVED) - accounted):
            assert after[cls]["difference"] == 0, cls

    def test_the_shortfall_moved_out_of_unexplained_not_into_an_excuse(self):
        """`total_shortfall` 4781 -> 4664 and `unexplained_shortfall`
        3063 -> 2946: the SAME -117. If the two figures had moved by different
        amounts, objects would have been reclassified into an accounting line
        rather than actually transferred, which is the laundering this
        feature's whole census exists to make visible."""
        b = _t078(T078_BASELINES["ejagham"])["totals"]
        a = _t078(T107_EJAGHAM)["totals"]
        assert b["total_shortfall"] - a["total_shortfall"] == 117
        assert b["unexplained_shortfall"] - a["unexplained_shortfall"] == 117
        assert a["accounted_shortfall"] == b["accounted_shortfall"] == 0

    def test_the_duplicate_identity_verdict_is_unchanged_and_not_laundered(
            self):
        """Both censuses are DUPLICATE_IDENTITY / exit 3 on the same 3
        `PhNCFeatures` duplicate extras. That is T082's remaining
        `038-NK-P3`, untouched by T107 -- recorded rather than quietly
        dropped, because a task that improved one row and silently inherited a
        red verdict would be reporting a pass it did not earn."""
        b = _t078(T078_BASELINES["ejagham"])
        a = _t078(T107_EJAGHAM)
        assert b["verdict"] == a["verdict"] == "DUPLICATE_IDENTITY"
        assert b["totals"]["duplicate_extra_objects"] == 3
        assert a["totals"]["duplicate_extra_objects"] == 3

    def test_the_mbugwe_pair_is_unmoved_to_the_row(self):
        """The other half of the acceptance, and the reason T076 was not
        wrong. Not one of Mbugwe's 18 rules references a boundary context, so
        admitting the class must move NOTHING there: 18/18 reproduced, and 74
        census rows plus every total identical to T078's."""
        rules = _t078(T107_MBUGWE_RULES)["report"]
        assert rules["process_rules_total"] == 18
        assert rules["process_rules_reproduced"] == 18
        assert rules["process_rules_not_reproduced"] == []

        before = _t078_rows(T078_BASELINES["mbugwe"])
        after = _t078_rows(T107_MBUGWE)
        assert set(before) == set(after)
        fields = ("source_count", "destination_count_total", "difference",
                  "verdict_class")
        for cls in sorted(before):
            assert tuple(before[cls][f] for f in fields) \
                == tuple(after[cls][f] for f in fields), cls
        assert (_t078(T078_BASELINES["mbugwe"])["totals"]
                == _t078(T107_MBUGWE)["totals"])

    def test_mbugwes_boundary_contexts_are_still_short_and_that_is_correct(
            self):
        """-15 on Mbugwe, unmoved, and it is the RIGHT answer rather than a
        miss. Those contexts sit in `ContextsOS` and under phonological rules;
        no affix process rule reaches them, so nothing in US5 co-creates them.
        This is T076's measurement standing, which is the distinction T078's
        re-scoping turned on."""
        after = _t078_rows(T107_MBUGWE)
        assert after["PhSimpleContextBdry"]["difference"] == -15
        assert after["MoAffixProcess"]["difference"] == 0

    def test_the_ngoreme_pair_was_not_re_measured_and_says_so(self):
        """THE GAP, ASSERTED RATHER THAN LEFT IMPLICIT. T107's acceptance
        named two runs and this is neither of them: Ngoreme's single affix
        process rule already reproduced under T078, so nothing T107 changed
        can reach that pair, and its `PhSimpleContextBdry` -4 is entirely
        phonological-rule and shared-pool content. The number carried in R7's
        residue roster is therefore T078's, and the roster's reason string
        says which -- this test is what keeps that admission from being
        quietly dropped later."""
        from gramtrans.Lib import models as _models

        _owner, reason = _models.CENSUS_REPORT_ONLY_RESIDUE[
            "PhSimpleContextBdry"]
        assert "ngoreme -4" in reason
        assert "NOT re-measured" in reason
        # The premise: that pair's one rule was already reproduced.
        row = _t078_rows(T078_BASELINES["ngoreme"])["MoAffixProcess"]
        assert (row["source_count"], row["difference"]) == (1, 0)

    @pytest.mark.parametrize("name", [T107_EJAGHAM, T107_MBUGWE])
    def test_these_artifacts_are_the_ones_that_now_reproduce(self, name):
        """T102's chain, one link further on. T078's artifacts are `drifted`
        on the destination side of these two pairs *because* these runs
        happened; the counterpart claim -- that T107's own artifacts hash to
        the projects as they stand -- is what makes them the current
        measurement rather than merely the newest files. Without both halves
        the drift above would be an unexplained regression instead of a
        handover."""
        artifact = _t078(name)
        for side in ("source", "destination"):
            assert _t078_fwdata_status(artifact["projects"][side]) \
                == "match", name + "." + side

    @pytest.mark.parametrize("name", [T107_EJAGHAM, T107_MBUGWE])
    def test_both_censuses_opened_both_projects_read_only(self, name):
        """Invariant 7, on the artifacts this task is judged by. A census that
        wrote to either project is not evidence of anything, so this is
        checked before any number above is trusted."""
        for role, block in sorted(_t078(name)["projects"].items()):
            assert block["opened_read_only"] is True, role
            assert (block["fwdata_sha256_before"]
                    == block["fwdata_sha256_after"]), role


# ===========================================================================
# T108 -- the field that was fixed too late for the run that needed it
# ===========================================================================
#
# T076 added `ProcessContextSpec.co_created_shared` so a write into the
# shared, project-level `PhPhonData.ContextsOS` would not be a silent write
# (SC-010) -- and asserted it on the IN-MEMORY record only.
# `report._process_rule_json` dropped it, so the claim was true of the object
# and FALSE of the artifact anybody reads, from T076 until T107 found it.
#
# T107 fixed the serializer and its own committed run PREDATES the fix, so its
# evidence covers the direct boundary route (8 rules, 8 reported input
# members) and the shared route's refusals and resolution -- but not the
# shared route's live CO-CREATION. Both `_create_shared_process_context` and
# the phonological-rule path (`_copy_context_cell`) write that collection, so
# the destination's one `PhPhonData`-owned `PhSimpleContextBdry` could not be
# attributed to either.
#
# T108 IS THAT ONE RUN, and it lands in a target of its own. Re-transferring
# `GT038 Ejagham After` would have drifted T107's censuses off the digests
# they are asserted to hash to -- T102's failure one link further on again --
# so `debug/run038_before_after_pairs.py` gained an `ejagham-t108` pair and a
# `--no-census` flag, and refuses outright to re-transfer an evidence target.
#
# THE ANSWER IS POSITIVE, which was not the only possible outcome: the field
# could have come back empty on all 13 rules, meaning the phonological-rule
# path got there first, and that would have been an answer too.

T108_EJAGHAM_RULES = "process-rules-038-t108-ejagham.json"

#: The one `PhPhonData`-owned boundary context on this pair -- the single
#: object the whole task is about -- and the rule that created it.
T108_SHARED_BOUNDARY = "391e8cba-b951-4f1b-a64a-c5dc5fbe19c9"
T108_CREATING_RULE = "de6df83e-3556-42f8-82fc-30d22d4a68b9"

#: Every shared `PhPhonData.ContextsOS` member this run co-created, by class.
#: The boundary context is ONE of thirteen: the co-create leg is not a
#: boundary-context special case, and a table that named only the boundary
#: would hide that the same leg carries twelve other shared contexts.
T108_CO_CREATED_BY_CLASS = {
    "PhSimpleContextBdry": 1,
    "PhSimpleContextNC": 7,
    "PhSimpleContextSeg": 5,
}


def _t108_rules() -> dict:
    return _t078(T108_EJAGHAM_RULES)


class TestT108TheSharedRouteAttribution:
    """The co-create leg, attributed live from a run report that carries the
    field -- and taken without disturbing T107's evidence."""

    def test_the_run_did_not_land_on_t107s_evidence(self):
        """THE TRAP THIS TASK WAS FILED WITH, asserted rather than trusted to
        the driver. Same source, DIFFERENT destination, different run: a T108
        artifact naming `GT038 Ejagham After` would mean the re-run had
        overwritten the project T107's committed censuses are asserted to
        hash to, and every number in `TestT107...` would be describing a
        project that no longer exists."""
        t108, t107 = _t108_rules(), _t107_rules()
        assert t108["source_project"] == t107["source_project"] \
            == "Ejagham W Mini"
        assert t108["destination_project"] == "GT038 T108 Target"
        assert t108["destination_project"] != t107["destination_project"]
        assert t108["run_id"] and t108["run_id"] != t107["run_id"]

    def test_t107s_own_censuses_still_hash_to_their_projects(self):
        """The other half of the same claim, and the half that could actually
        go red. The guard above is about a string in an artifact; this is
        about the files on disk. T107's two censuses must still reproduce
        after T108's run -- which is exactly what a re-run into the wrong
        target would break."""
        for name in (T107_EJAGHAM, T107_MBUGWE):
            for side in ("source", "destination"):
                assert _t078_fwdata_status(_t078(name)["projects"][side]) \
                    == "match", name + "." + side

    def test_the_field_reached_every_reported_context(self):
        """SC-010 landing in the artifact rather than in the object. 104
        input contexts are reported on this run and every one carries
        `co_created_shared` -- emitted unconditionally, so `[]` means "this
        context created nothing shared" instead of meaning nothing at all.
        The derivation refuses a report with a single entry missing the key,
        so this asserts what that refusal guarantees.

        Pinned through the real serializer too, because an artifact can only
        show that the field was present on the day it was written."""
        rules = _t108_rules()
        assert rules["input_contexts_total"] == 104
        assert (rules["input_contexts_carrying_co_created_shared"]
                == rules["input_contexts_total"])

        from gramtrans.Lib import models as _models
        from gramtrans.Lib.report import _process_rule_json

        payload = _process_rule_json(_models.ProcessRuleTransferRecord(
            source_guid="r", reproduced=True, target_guid="r",
            input_contexts=(_models.ProcessContextSpec(
                context_class="PhSequenceContext", index=0,
                co_created_shared=("shared-1",)),)))
        assert payload["input_contexts"][0]["co_created_shared"] == \
            ["shared-1"]

    def test_the_boundary_context_came_from_the_affix_process_leg(self):
        """THE HEADLINE, and the question T108 exists for. ONE
        `PhSimpleContextBdry` was co-created into `PhPhonData.ContextsOS` by
        this run, it is the one `PhPhonData`-owned boundary context on the
        pair, and the rule that made it is named. So the destination's copy
        came from `categories._create_shared_process_context` and NOT from the
        phonological-rule path -- both write that collection, which is why
        T107 could not tell them apart without this field."""
        boundary = _t108_rules()["co_created_shared_boundary_contexts"]
        assert len(boundary) == 1
        found = boundary[0]
        assert found["guid"] == T108_SHARED_BOUNDARY
        assert found["source_owner_class"] == "PhPhonData"
        assert found["created_by_rule"] == T108_CREATING_RULE

    def test_five_rules_reach_it_and_exactly_one_reports_creating_it(self):
        """T076's route, measured end to end. Five rules reach the shared
        boundary context through a rule-owned `PhSequenceContext` -- which
        reproduces T107's read-only count of five from the source graph -- and
        exactly one reports co-creating it, because `_resolve_process_graph`
        consults `member_targets` before the co-create leg. The other four
        found what the first one made, and one of THOSE is the source-defect
        rule that never gets as far as its input members.

        This is the distinction the count would otherwise hide: 13 co-created
        members is a count of OBJECTS CREATED, never of rules that use them."""
        rules = _t108_rules()
        found = rules["co_created_shared_boundary_contexts"][0]
        reaching = found["rules_reaching_it"]
        assert len(reaching) == 5
        assert T108_CREATING_RULE in reaching
        assert T107_SOURCE_DEFECT_RULE in reaching
        creators = {c["rule"] for c in rules["co_created_shared_members"]
                    if c["guid"] == T108_SHARED_BOUNDARY}
        assert creators == {T108_CREATING_RULE}

    def test_every_shared_write_went_into_phphondata_and_is_accounted(self):
        """The scope of the leg, so "it created the boundary context" is not
        read as "it created only that". Thirteen members across four rules,
        every one owned by `PhPhonData` in the source -- which is what makes
        them shared, project-level writes and therefore SC-010's subject
        rather than ordinary rule-owned content."""
        rules = _t108_rules()
        assert rules["co_created_shared_total"] == 13
        assert rules["co_created_shared_by_class"] == T108_CO_CREATED_BY_CLASS
        assert rules["co_created_shared_owner_classes"] == {"PhPhonData": 13}
        assert len({c["rule"]
                    for c in rules["co_created_shared_members"]}) == 4
        assert sum(T108_CO_CREATED_BY_CLASS.values()) \
            == rules["co_created_shared_total"]

    def test_this_run_reproduces_t107s_per_rule_figures_on_a_new_target(self):
        """A SECOND TARGET IS A REAL CHECK, not bookkeeping. T107's numbers
        were taken once, into one project; if any of them depended on that
        project's starting state rather than on the source and the engine,
        this run would say so. It does not: same 13 rules, same 12
        reproduced, same single refusal for the same reason, same 8 direct
        boundary input members, same input-context class totals."""
        t108, t107 = _t108_rules(), _t107_rules()
        assert (t108["rules_total"], t108["rules_reproduced"]) \
            == (t107["rules_total"], t107["rules_reproduced"]) == (13, 12)
        assert (t108["input_context_class_totals"]
                == t107["input_context_class_totals"])
        assert (t108["boundary_context_input_members"]
                == t107["boundary_context_input_members"])
        blocked = t108["rules_not_reproduced"]
        assert len(blocked) == 1
        assert blocked[0]["source_guid"] == T107_SOURCE_DEFECT_RULE
        reason = " ".join(blocked[0]["reason"].split())
        assert "MoCopyFromInput" in reason
        assert "PhSimpleContextBdry" not in reason

    def test_the_t107_artifact_no_longer_says_it_cannot_be_determined(self):
        """The note T108 was filed to replace, replaced -- and replaced with
        an attribution rather than with silence. A reader who reaches T107's
        artifact must be sent to the measurement instead of being told the
        question is open, and must be told which run made it, since it is not
        the run that artifact describes."""
        note = _t107_rules()["shared_context_attribution"]
        assert "NOT DETERMINABLE" not in note.upper()
        assert T108_EJAGHAM_RULES in note
        assert T108_SHARED_BOUNDARY in note
        assert "GT038 T108 Target" in note

    def test_the_attribution_string_states_which_way_it_came_out(self):
        """An empty field would have been an answer too -- the
        phonological-rule path got there first -- so the artifact has to say
        WHICH answer it is, in a form that cannot be satisfied by a hedge."""
        note = _t108_rules()["shared_context_attribution"]
        assert note.startswith("MEASURED AND ATTRIBUTED")
        assert "THE BOUNDARY CONTEXT IS AMONG THEM" in note
        assert T108_CREATING_RULE in note


# ===========================================================================
# T109 -- the admissible accounting line P5 was built around, and the three
#         locks that make it safe to be load-bearing
# ===========================================================================
#
# T081 measured that P5's own admissible route had never been wired: 66 of its
# 69 failures across the three sanctioned pairs were "is SHORTFALL and carries
# NO accounting line", and `contracts/fidelity-census.md:373` asks for the
# `GOVERNED_BY_OTHER_FEATURE` line by name while validator invariant 5 exempts
# it from `report_ref` precisely so it can be emitted.
#
# T079 REFUSED THE TOKEN AND WAS RIGHT ABOUT A DIFFERENT FIELD. The token is a
# member of three vocabularies. As a `not_evaluated_reason` it flips
# `verdict_class` to NOT_EVALUATED and DELETES the measured shortfall from the
# totals and from the gate -- laundering, and T079's refusal stands. As an
# `accounted_for` LINE reason (`REASON_TOKENS` +
# `REASONS_NOT_REQUIRING_REPORT_REF`) it does neither: `_phase_5` reads
# `accounted_for`, `unexplained_counts` subtracts the line, `verdict_class`
# never moves, and `build_totals`' `total_shortfall` is a function of
# `difference` alone.
#
# WHICH MAKES THIS LINE LOAD-BEARING WHERE T079'S `report_only` STATE IS INERT,
# and by construction a way to turn a red row green. Hence three locks, all
# pinned below:
#
#   1. IMPORT-TIME DISJOINTNESS from the phase predicates' own class sets
#      (`Lib/census.py`, beside `PHASE_5_CLASSES`). A class 038 gates on must
#      be UNABLE to appear on the roster -- not merely asserted absent by a
#      test a `-k` selection can skip.
#   2. THE CAP at `max(0, -difference)` less whatever the row's existing lines
#      already claim (`census_cli.accounted_for_governed_class`). R-2, and also
#      the exact figure that makes a stamped row PASS: `_phase_5` fails a row
#      whose `unexplained_shortfall` is nonzero after accounting, so a claim
#      that under-shoots leaves the row red and one that over-shoots is
#      CENSUS_ERROR.
#   3. GATE-INERTNESS OF THE ROSTER ITSELF: emptying it restores the emitted
#      artifact byte for byte.
#
# THE MEASUREMENT CORRECTS T081 ON TWO OF THREE CORPORA, and the difference is
# exactly `CmFile` + `CmFolder` -- see `T109_T081_EXCLUDED` and the ruling in
# `models.CENSUS_GOVERNED_BY_OTHER_FEATURE_CLASSES`.

#: P5 failure count on T078's artifacts, BEFORE -> AFTER the governed line.
T109_P5_FAILURES = {
    "ejagham": (19, 10),
    "ngoreme": (27, 16),
    "mbugwe": (23, 14),
}

#: `(rows stamped, objects claimed)` per corpus. Every object is one this
#: feature's own census measured as missing; the line names an owner for it and
#: does not reduce it.
T109_STAMPED = {
    "ejagham": (9, 1885),
    "ngoreme": (11, 64618),
    "mbugwe": (9, 5841),
}

#: `(total_shortfall, unexplained_shortfall before, unexplained_shortfall
#: after)`. `total_shortfall` is the number that must NOT move: it is
#: `sum(max(0, -difference))` over the required rows and no accounting line is
#: in that arithmetic. What moves is which bucket the objects sit in.
T109_TOTALS = {
    "ejagham": (4781, 3063, 1178),
    "ngoreme": (70646, 68928, 4310),
    "mbugwe": (10243, 9384, 3543),
}

#: THE TWO CLASSES T081's PROBE ROSTERED AND THIS ONE DOES NOT, with their
#: measured difference on (ejagham, ngoreme, mbugwe). T081 reported 9 / 13 / 11
#: stampable rows carrying 1885 / 64,621 / 8017 objects; this roster measures
#: 9 / 11 / 9 carrying 1885 / 64,618 / 5841, and the whole delta is these two
#: rows -- 0 objects on ejagham (both MATCHED there), 3 on ngoreme, 2176 on
#: mbugwe. The ruling is in the roster's own declaration: the Assumptions hand
#: over SENSE PICTURES, `CmPicture` is 0 -> 0 on all three pairs, and objects
#: in `CmFile` / `CmFolder` with no `CmPicture` anywhere to refer to them are
#: the project's media folder, which nothing names an owner for.
T109_T081_EXCLUDED = {
    "CmFile": (0, -2, -2173),
    "CmFolder": (0, -1, -3),
}

#: T081's own figures, kept so the correction is a fact in the test file and
#: not only in a journal.
T109_T081_PREDICTED = {
    "ejagham": (9, 1885),
    "ngoreme": (13, 64621),
    "mbugwe": (11, 8017),
}

#: Explicitly NOT rostered, with the reason each is out. Asserted so a later
#: hand cannot quietly widen the roster into the residue that T079 and T081
#: both refused to attribute.
T109_DELIBERATELY_OUT = (
    "PhSequenceContext", "PhSimpleContextBdry", "PhSimpleContextNC",
    "PhSimpleContextSeg", "PhCode", "PhFeatureConstraint",
    "FsFeatStruc", "FsClosedValue", "CmPossibility", "MoAffixProcess",
    "PhNCFeatures", "CmFile", "CmFolder",
)


def _t109_line_stand_ins(lines):
    """The `(count, direction)` view `census.accounted_in_direction` needs.

    A committed artifact holds accounting lines as DICTS; the room arithmetic
    reads `.count` / `.direction` off `census.AccountedLine`. Rebuilding the
    real dataclass is not possible for every stored line -- one carrying a
    non-exempt reason needs the `report_ref` its constructor demands, and R-1
    is checked there -- so this is the minimum shape the arithmetic touches,
    and it is deliberately the only test-local glue in the stamp below.
    """
    return [
        type("_Line", (), {"count": line["count"],
                           "direction": line["direction"]})()
        for line in lines
    ]


def _t109_stamped(name: str) -> dict:
    """A COPY of one T078 artifact with the T109 line applied to every row.

    EVERY DERIVATION IS THE REAL ONE. The line comes from
    `census_cli.accounted_for_governed_class` (the emitter's own function, cap
    included), the residues from `census.unexplained_counts`, the totals from
    `census.build_totals`, the verdict from `census.stamp_verdict`. Nothing
    here re-implements the emitter; what is test-local is only the glue that
    re-runs it over rows a live census already measured -- the same move
    `with_current_roster_admission` and `with_recomputed_verdict` make, and for
    the same reason: re-running a derivation over unchanged observations is not
    forging a measurement.
    """
    from copy import deepcopy

    out = deepcopy(_t078(name))
    for row in out["classes"]:
        existing = list(row.get("accounted_for", ()))
        new = census_cli.accounted_for_governed_class(
            row["class"], row.get("difference"),
            _t109_line_stand_ins(existing))
        if not new:
            continue
        row["accounted_for"] = existing + [line.artifact() for line in new]
        shortfall, surplus = census.unexplained_counts(
            row.get("difference"),
            _t109_line_stand_ins(row["accounted_for"]))
        if row.get("verdict_class") == "NOT_EVALUATED":
            shortfall, surplus = 0, 0
        row["unexplained_shortfall"] = shortfall
        row["unexplained_surplus"] = surplus
    out["totals"] = census.build_totals(out["classes"])
    return census.stamp_verdict(out)


def _t109_governed_rows(artifact) -> list:
    return [
        row for row in artifact["classes"]
        if any(line["reason"] == "GOVERNED_BY_OTHER_FEATURE"
               for line in row.get("accounted_for", ()))
    ]


class TestT109TheRosterIsDerivedNotInvented:
    """The roster's contents, and the derivation that decides them."""

    def test_every_rostered_class_lies_on_one_of_the_spec_three_paths(self):
        """`spec.md`'s Assumptions name THREE paths -- sense pictures, reversal
        indexes, the texts/wordforms path -- and the owner string of every
        entry has to name one of them. The check is on the OWNER rather than on
        a second list of classes, because the owner is the half of the entry
        that makes the line actionable (SC-010) and a class whose owner does
        not resolve to a named path is the unowned claim T081 refused."""
        from gramtrans.Lib import models as _models

        paths = ("the texts/wordforms feature", "the reversal-index feature",
                 "the sense-pictures feature")
        roster = _models.CENSUS_GOVERNED_BY_OTHER_FEATURE_CLASSES
        assert roster, "the roster must not be empty in the shipped source"
        for cls, (owner, reason) in sorted(roster.items()):
            assert any(owner.startswith(p) for p in paths), (cls, owner)
            assert "spec.md Assumptions" in owner, cls
            assert reason.strip(), cls

    def test_every_entry_carries_its_measured_evidence_or_admits_it_has_none(
            self):
        """An entry is a measurement or an admitted promise, never a belief.
        `TextTag` and `CmPicture` have `source_count` 0 on all three pairs, so
        no committed census can stamp them; their reason strings say so in
        those words, and this test is what stops a third such entry arriving
        without saying it."""
        from gramtrans.Lib import models as _models

        promises = set()
        for cls, (_owner, reason) in sorted(
                _models.CENSUS_GOVERNED_BY_OTHER_FEATURE_CLASSES.items()):
            if "A PROMISE, NOT AN ACCOUNTING LINE" in reason:
                promises.add(cls)
                continue
            assert reason.startswith("measured "), cls
        assert promises == {"TextTag", "CmPicture"}
        # And the admission is true: 0 source objects on all three pairs.
        for cls in sorted(promises):
            for pair in sorted(T078_BASELINES):
                assert _t078_rows(T078_BASELINES[pair])[cls]["source_count"] \
                    == 0, (cls, pair)

    def test_the_measured_figures_in_the_reason_strings_are_the_real_ones(
            self):
        """A roster whose evidence string can drift from the artifacts is a
        roster that will. Each `measured a, b, c` is parsed back out and
        checked against T078's three censuses, in the declaration's own stated
        order (ejagham, ngoreme, mbugwe)."""
        from gramtrans.Lib import models as _models

        order = ("ejagham", "ngoreme", "mbugwe")
        rows = {p: _t078_rows(T078_BASELINES[p]) for p in order}
        checked = 0
        for cls, (_owner, reason) in sorted(
                _models.CENSUS_GOVERNED_BY_OTHER_FEATURE_CLASSES.items()):
            match = re.match(r"measured (-?\d+), (-?\d+), (-?\d+)", reason)
            if match is None:
                continue
            declared = tuple(int(g) for g in match.groups())
            actual = tuple(rows[p][cls]["difference"] for p in order)
            assert declared == actual, cls
            checked += 1
        assert checked == 12

    @pytest.mark.parametrize("object_class", T109_DELIBERATELY_OUT)
    def test_the_unowned_residue_stays_out(self, object_class):
        """The phonology family, the Fs* cascade, `CmPossibility`,
        `MoAffixProcess`, `PhNCFeatures`, `CmFile` and `CmFolder`. Every one of
        them is a REQUIRED row with a real loss on at least one pair, which is
        exactly what makes rostering them tempting; none has a named owner, and
        `MoAffixProcess` / `PhNCFeatures` are 038's own defects. This is the
        dodge the locks exist to prevent, pinned class by class."""
        from gramtrans.Lib import models as _models

        assert object_class not in \
            _models.CENSUS_GOVERNED_BY_OTHER_FEATURE_CLASSES
        assert census.governed_by_other_feature(object_class) is None
        assert census_cli.accounted_for_governed_class(
            object_class, -500) == ()

    def test_the_roster_is_not_the_report_only_residue_and_says_so(self):
        """The two rosters are deliberately different sets, and the difference
        is the whole argument: the residue roster carries the phonology family
        and the Fs* cascade under an owner that names no existing feature,
        which this one refuses. Neither is derivable from the other, so a
        later hand that tries to collapse them into one list fails here.

        **AMENDED BY T113.** As written, this test recorded `Text`, `TextTag`,
        `ReversalIndex`, `ReversalIndexEntry` and `CmPicture` as being on the
        governed roster and NOT the residue -- and read that as evidence the
        two are different sets. T113 measured it as a GAP instead: those five
        are two of the spec's three named paths, and leaving them off the
        residue made `report._census_row_tier` print `report_only` for
        `StText` and plain `accounted` for the `Text` that owns it. The five
        were added to the residue and `report.report_only_roster_defects`
        gained a completeness check, so the containment below is now enforced
        rather than incidental.

        THE ARGUMENT IS UNCHANGED AND IS STILL PINNED HERE: the residue is a
        strict SUPERSET, never the same set, and it is the `residue -
        governed` direction that carries it -- a class can be report-only with
        no successor feature (`PhCode`, `CmFile`) and that is exactly what
        must never become a gate-bearing accounting line."""
        from gramtrans.Lib import models as _models

        governed = set(_models.CENSUS_GOVERNED_BY_OTHER_FEATURE_CLASSES)
        residue = set(_models.CENSUS_REPORT_ONLY_RESIDUE)
        # T113: the containment holds, and `report_only_roster_defects`
        # check 5 is what keeps it holding.
        assert governed - residue == set()
        assert governed != residue
        for unowned in ("PhCode", "CmFile", "FsClosedValue",
                        "PhSimpleContextNC"):
            assert unowned in residue - governed, unowned

    def test_the_lookup_is_the_only_one(self):
        """`census.governed_by_other_feature` reads the module global at call
        time, which is both how the emitter reaches the roster and how Lock 3
        can empty it. A second, direct read of the dict anywhere in the emitter
        would make the roster un-emptiable, so the emitter's own source is
        checked for one."""
        source = Path(census_cli.__file__).read_text(encoding="utf-8")
        assert "GOVERNED_BY_OTHER_FEATURE_CLASSES" not in source
        assert "census.governed_by_other_feature(" in source


class TestT109Lock1ImportTimeDisjointness:
    """A class 038 has an executable gate on must be UNABLE to be rostered."""

    def test_the_roster_is_disjoint_from_every_phase_predicate_scope(self):
        """Checked against the predicates' OWN class sets, not against
        `models.CENSUS_PHASE_GATED_CLASSES`. T079's equivalent has to check the
        mirror as well, because `models.py` cannot import `census.py`; this one
        is inside `census.py` and reads the real thing, so there is no mirror
        to drift. `PHASE_5_CLASSES` is excluded because it is `None` -- "every
        required row" -- and folding it in would make the roster necessarily
        empty."""
        from gramtrans.Lib import models as _models

        owned = (
            frozenset(census.PHASE_1_CLASSES)
            | frozenset(census.PHASE_2_MATCHED_CLASSES)
            | frozenset(census.PHASE_3_CLASSES)
            | frozenset(census.PHASE_4_CLASSES)
        )
        assert census.PHASE_5_CLASSES is None
        assert not (set(census.GOVERNED_BY_OTHER_FEATURE_CLASSES) & owned)
        # And the same answer against T079's mirror, so the two locks agree.
        assert not (set(_models.CENSUS_GOVERNED_BY_OTHER_FEATURE_CLASSES)
                    & _models.CENSUS_PHASE_GATED_CLASSES)

    def test_a_phase_owned_class_makes_the_module_refuse_to_import(self):
        """THE LOCK, EXERCISED. Poisoning the roster with `MoStemMsa` -- a
        class P1 requires MATCHED -- in a fresh interpreter must make
        `import gramtrans.Lib.census` FAIL. An assertion in a test would not
        do: a test can be deselected and the artifact would still be written.
        Run in a subprocess because the lock is import-time by design and this
        session already holds the module."""
        import subprocess

        code = (
            "import gramtrans.Lib.models as m\n"
            "m.CENSUS_GOVERNED_BY_OTHER_FEATURE_CLASSES['MoStemMsa'] = "
            "('somebody else', 'measured -1, -1, -1')\n"
            "import gramtrans.Lib.census\n"
            "print('IMPORTED')\n"
        )
        done = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True,
            env=_t109_subprocess_env())
        assert done.returncode != 0, done.stdout
        assert "IMPORTED" not in done.stdout
        assert "T109" in done.stderr
        assert "MoStemMsa" in done.stderr
        assert "turn its own red row green" in done.stderr

    def test_an_entry_with_no_owner_makes_the_module_refuse_to_import(self):
        """The second half of Lock 1. "A report line the user cannot act on is
        not a report" (SC-010) is twice as true of a line that also retires a
        measured shortfall, so a blank or malformed entry is a source defect
        and not a lenient default."""
        import subprocess

        code = (
            "import gramtrans.Lib.models as m\n"
            "m.CENSUS_GOVERNED_BY_OTHER_FEATURE_CLASSES['LexAppendix'] = "
            "('', 'measured 0, 0, 0')\n"
            "import gramtrans.Lib.census\n"
            "print('IMPORTED')\n"
        )
        done = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True,
            env=_t109_subprocess_env())
        assert done.returncode != 0, done.stdout
        assert "LexAppendix" in done.stderr
        assert "names no owner" in done.stderr

    def test_the_unpoisoned_module_imports_cleanly(self):
        """The falsifier for the two above: they must fail because of the
        poison and not because the subprocess could not import the package at
        all."""
        import subprocess

        done = subprocess.run(
            [sys.executable, "-c",
             "import gramtrans.Lib.census\nprint('IMPORTED')\n"],
            capture_output=True, text=True, env=_t109_subprocess_env())
        assert done.returncode == 0, done.stderr
        assert "IMPORTED" in done.stdout


class TestT109Lock2TheCapIsTheRoom:
    """A line can never outrun the loss (R-2) -- and never undershoot it,
    because an undershoot leaves the row red and hides that fact behind an
    accounting line that looks like progress."""

    def test_the_claim_is_exactly_the_shortfall(self):
        lines = census_cli.accounted_for_governed_class("Segment", -26666)
        assert len(lines) == 1
        line = lines[0]
        assert (line.reason, line.count, line.direction) == (
            "GOVERNED_BY_OTHER_FEATURE", 26666, "shortfall")
        assert line.report_ref is None
        assert census.unexplained_counts(-26666, lines) == (0, 0)
        assert census.over_accounted_directions(-26666, lines) == ()

    def test_the_line_needs_no_report_ref_and_that_is_invariant_5s_doing(self):
        """R-1 is enforced in `AccountedLine.__post_init__`, so a token that
        needed a `report_ref` could not be constructed here at all. This line
        exists because the contract's table and invariant 5 both exempt the
        token -- there IS no run-report content to resolve against, since the
        objects were never this run's to create."""
        assert "GOVERNED_BY_OTHER_FEATURE" in \
            census.REASONS_NOT_REQUIRING_REPORT_REF
        assert census.reason_requires_report_ref(
            "GOVERNED_BY_OTHER_FEATURE") is False

    def test_a_null_difference_gets_no_line(self):
        """T099: a null difference is not a zero. Such a row is NOT_EVALUATED,
        `_phase_5` skips it and `class_row_artifact` zeroes both residues for
        it, so a line would claim objects nobody counted against a row the gate
        does not read."""
        assert census_cli.accounted_for_governed_class("Segment", None) == ()

    @pytest.mark.parametrize("difference", [0, 1, 7923])
    def test_a_matched_or_surplus_row_gets_no_line(self, difference):
        """The token's contract direction is "either", so this is a judgment
        and not a limitation: a destination holding MORE objects of a governed
        class is not something another feature failed to do. Every governed
        non-MATCHED row on all three pairs is SHORTFALL, so the refusal was
        made before it was needed."""
        assert census_cli.accounted_for_governed_class(
            "Segment", difference) == ()

    def test_an_earlier_line_takes_the_room_first_and_the_cap_bites(self):
        """A reported drop is the MORE SPECIFIC claim -- it names run-report
        content invariant 5 can resolve -- so it gets the room first and the
        governance line takes what is left. The note says the claim was capped:
        a capped number is never silent (T023c)."""
        ref = census.ReportRef(
            kind="dropped_items", count_in_report=100, run_id="GT-20260826-000000")
        drop = census.AccountedLine(
            reason="DEPENDENCY_UNRESOLVED", count=100, direction="shortfall",
            report_ref=ref)
        notes = []
        lines = census_cli.accounted_for_governed_class(
            "WfiAnalysis", -822, (drop,), notes)
        assert len(lines) == 1
        assert lines[0].count == 722
        assert "CLAIM CAPPED" in lines[0].detail
        assert any("claims only 722" in note for note in notes)
        both = (drop,) + lines
        assert census.unexplained_counts(-822, both) == (0, 0)
        assert census.over_accounted_directions(-822, both) == ()

    def test_a_fully_claimed_row_gets_no_line_and_says_why(self):
        """R-2 from the other side. When earlier lines already claim the whole
        shortfall there is no room, and the refusal is recorded rather than
        being an absence a reader has to notice."""
        ref = census.ReportRef(
            kind="dropped_items", count_in_report=17, run_id="GT-20260826-000000")
        drop = census.AccountedLine(
            reason="NO_CREATE_PATH", count=17, direction="shortfall",
            report_ref=ref)
        notes = []
        assert census_cli.accounted_for_governed_class(
            "StText", -17, (drop,), notes) == ()
        assert any("NO GOVERNED_BY_OTHER_FEATURE line was emitted" in note
                   for note in notes)

    def test_the_cap_is_what_makes_a_stamped_row_pass_not_merely_safe(self):
        """The point the task line makes, and the reason the number matters. A
        row whose line under-claims is still red: `_phase_5` fails a row with a
        nonzero `unexplained_shortfall` AFTER accounting. Forged one short, to
        show the failure the exact cap avoids."""
        short = census.AccountedLine(
            reason="GOVERNED_BY_OTHER_FEATURE", count=16,
            direction="shortfall")
        assert census.unexplained_counts(-17, (short,)) == (1, 0)
        exact = census_cli.accounted_for_governed_class("StText", -17)
        assert census.unexplained_counts(-17, exact) == (0, 0)


# --- Lock 3: the roster is gate-inert, proved by emptying it ----------------
#
# The forge below emits a FULL artifact through the real path
# (`census_cli._row_for_entry` -> `census.class_row_artifact` ->
# `census.build_artifact` -> `census.stamp_verdict`) and serialises it with the
# exact `json.dumps(..., indent=2, ensure_ascii=False) + "\n"` that
# `census_cli.run` writes to disk, so "byte for byte" means the bytes of the
# artifact file and not a dict comparison.

T109_FORGE_CLASSES = (
    # (class, source, destination, baseline) -- one rostered class with a real
    # loss, one rostered class that agrees, one UNROSTERED class with the
    # IDENTICAL loss (the leak detector), one class P1 gates on.
    ("Segment", 200, 60, 0),
    ("ReversalIndexEntry", 5, 5, 0),
    ("PhCode", 200, 60, 0),
    ("MoStemMsa", 40, 40, 0),
)


def _t109_subprocess_env() -> dict:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(p for p in sys.path if p)
    return env


def _t109_forged_artifact() -> str:
    """The serialised artifact bytes, from the real emitter, as text."""
    from gramtrans.Lib import models as _models

    entries = tuple(
        census.ClassListEntry(
            object_class=name, in_class_list_via="coverage_floor",
            gate_scope="required", engine_can_create=True)
        for name, _s, _d, _b in T109_FORGE_CLASSES
    )
    class_list = census.ClassList(
        entries=entries,
        derivation_check={"performed": True, "method": "T109 forge",
                          "matches": True},
        provenance={"coverage_floor_source": "T109 forge"},
    )
    baseline = _models.StarterBaseline(
        kind=_models.StarterBaselineKind.PRE_TRANSFER_CENSUS,
        flex_version="9.2.7", captured_at="2026-08-26T00:00:00",
        captured_from="T109 forge",
        entries=tuple(
            _models.StarterBaselineEntry(object_class=name, count=base)
            for name, _s, _d, base in T109_FORGE_CLASSES),
    )
    source_counts = {n: s for n, s, _d, _b in T109_FORGE_CLASSES}
    destination_counts = {n: d for n, _s, d, _b in T109_FORGE_CLASSES}
    rows = []
    for entry in entries:
        row, kwargs = census_cli._row_for_entry(
            entry, source_counts, destination_counts, baseline,
            source_name="T109 source", destination_name="T109 destination")
        rows.append(census.class_row_artifact(row, entry, **kwargs))
    identity = census_cli._CensusIdentity(
        run_id="CENSUS-20260826-000000", taken_at="2026-08-26T00:00:00",
        baseline=baseline)
    artifact = census.build_artifact(
        identity, class_list, rows,
        projects={
            role: {
                "name": "T109 " + role, "opened_read_only": True,
                "fwdata_sha256_before": "0" * 64,
                "fwdata_sha256_after": "0" * 64,
            }
            for role in ("source", "destination")
        },
        instrument={"name": census_cli.INSTRUMENT_NAME,
                    "version": "T109", "invocation": "T109 forge"},
    )
    census.stamp_verdict(artifact)
    return json.dumps(artifact, indent=2, ensure_ascii=False) + "\n"


class TestT109Lock3TheRosterIsGateInert:
    """Emptying the roster restores the artifact byte for byte -- so putting a
    class ON it cannot buy anything the roster is not visibly responsible
    for."""

    def test_emptying_the_roster_restores_the_artifact_byte_for_byte(
            self, monkeypatch):
        with_roster = _t109_forged_artifact()
        monkeypatch.setattr(census, "GOVERNED_BY_OTHER_FEATURE_CLASSES", {})
        without_roster = _t109_forged_artifact()
        assert "GOVERNED_BY_OTHER_FEATURE" not in without_roster
        assert "GOVERNED_BY_OTHER_FEATURE" in with_roster
        # THE FALSIFIER FOR THE FALSIFIER: the emptied artifact is not merely
        # missing the token, it is the artifact the pre-T109 emitter wrote.
        # Every row's `accounted_for` is empty and every residue is the full
        # difference, which is precisely T081's "carries NO accounting line".
        empty = json.loads(without_roster)
        for row in empty["classes"]:
            assert row["accounted_for"] == [], row["class"]
            assert row["unexplained_shortfall"] == max(
                0, -row["difference"]), row["class"]
        assert empty["totals"]["accounted_shortfall"] == 0
        assert with_roster != without_roster

    def test_a_roster_of_classes_this_artifact_does_not_hold_changes_nothing(
            self, monkeypatch):
        """THE LEAK DETECTOR. If the emitter could produce a governed line from
        anywhere other than the roster lookup -- a hardcoded class list, a
        `reasons` fallback, an owner string matched by prefix -- this artifact
        would differ from the emptied one even though no class in it is
        rostered. `PhCode` is in the forge at the SAME -140 as `Segment`
        precisely so a leak keyed on the difference rather than on the class
        would show up."""
        monkeypatch.setattr(census, "GOVERNED_BY_OTHER_FEATURE_CLASSES", {})
        emptied = _t109_forged_artifact()
        monkeypatch.setattr(
            census, "GOVERNED_BY_OTHER_FEATURE_CLASSES",
            {"CmAgent": ("somebody", "measured 0, 0, 0")})
        irrelevant = _t109_forged_artifact()
        assert irrelevant == emptied

    def test_only_the_rostered_row_moves(self):
        """`Segment` and `PhCode` are the same -140 in the same artifact; only
        the rostered one gets a line, and the rostered class that agrees at 0
        gets nothing either. One rostered row moving and one not is what
        distinguishes a roster from a blanket."""
        with_roster = json.loads(_t109_forged_artifact())
        rows = {row["class"]: row for row in with_roster["classes"]}
        assert rows["Segment"]["difference"] == rows["PhCode"]["difference"]
        assert [line["reason"] for line in rows["Segment"]["accounted_for"]] \
            == ["GOVERNED_BY_OTHER_FEATURE"]
        assert rows["PhCode"]["accounted_for"] == []
        assert rows["ReversalIndexEntry"]["accounted_for"] == []
        assert rows["MoStemMsa"]["accounted_for"] == []
        assert rows["Segment"]["verdict_class"] == "SHORTFALL"
        assert rows["Segment"]["unexplained_shortfall"] == 0
        assert rows["PhCode"]["unexplained_shortfall"] == 140

    def test_the_forged_artifact_is_valid_and_p5_reads_it_as_intended(self):
        """The forge is only evidence if the artifact it writes is one the
        validator and the gate accept. P5 must fail on `PhCode` -- the
        unrostered loss -- and say nothing about `Segment`."""
        artifact = json.loads(_t109_forged_artifact())
        assert census.validate_artifact(artifact) == ()
        failures = census.evaluate_phase(artifact, 5).failures
        assert len(failures) == 1
        assert "PhCode" in failures[0]
        assert not any("Segment" in f for f in failures)


class TestT109TheMeasuredEffectOnTheThreeCorpora:
    """MEASURED, not argued -- on T078's three committed artifacts."""

    @pytest.mark.parametrize("pair", sorted(T109_P5_FAILURES))
    def test_p5_failures_before_and_after(self, pair):
        before, after = T109_P5_FAILURES[pair]
        assert len(census.evaluate_phase(
            _t078(T078_BASELINES[pair]), 5).failures) == before
        assert len(census.evaluate_phase(
            _t109_stamped(T078_BASELINES[pair]), 5).failures) == after

    @pytest.mark.parametrize("pair", sorted(T109_STAMPED))
    def test_the_rows_and_objects_the_line_accounts_for(self, pair):
        rows_expected, objects_expected = T109_STAMPED[pair]
        stamped = _t109_governed_rows(_t109_stamped(T078_BASELINES[pair]))
        assert len(stamped) == rows_expected
        assert sum(
            line["count"] for row in stamped
            for line in row["accounted_for"]
            if line["reason"] == "GOVERNED_BY_OTHER_FEATURE"
        ) == objects_expected

    @pytest.mark.parametrize("pair", sorted(T109_STAMPED))
    def test_no_stamped_row_stops_being_a_shortfall(self, pair):
        """THE WHOLE DIFFERENCE FROM T079'S REFUSAL. As a
        `not_evaluated_reason` this token flips `verdict_class` to
        NOT_EVALUATED and deletes the row from the totals; as an accounting
        line it does neither. Every stamped row stays SHORTFALL and stays
        counted."""
        stamped = _t109_stamped(T078_BASELINES[pair])
        rows = _t109_governed_rows(stamped)
        assert rows
        for row in rows:
            assert row["verdict_class"] == "SHORTFALL", row["class"]
            assert "not_evaluated_reason" not in row, row["class"]
            assert row["difference"] < 0, row["class"]

    @pytest.mark.parametrize("pair", sorted(T109_TOTALS))
    def test_the_shortfall_is_reclassified_and_never_reduced(self, pair):
        """`total_shortfall` pinned, to the object, on all three pairs: it is
        `sum(max(0, -difference))` over the required rows and no accounting
        line appears in that arithmetic. What moves is
        `unexplained_shortfall` -> `accounted_shortfall`, and the two must move
        by the SAME amount -- if they did not, objects would have gone
        somewhere neither bucket names."""
        total, unexplained_before, unexplained_after = T109_TOTALS[pair]
        before = _t078(T078_BASELINES[pair])["totals"]
        after = _t109_stamped(T078_BASELINES[pair])["totals"]
        assert before["total_shortfall"] == after["total_shortfall"] == total
        assert before["unexplained_shortfall"] == unexplained_before
        assert after["unexplained_shortfall"] == unexplained_after
        assert before["accounted_shortfall"] == 0
        assert after["accounted_shortfall"] == \
            unexplained_before - unexplained_after
        assert after["accounted_shortfall"] == T109_STAMPED[pair][1]
        assert before["total_surplus"] == after["total_surplus"] == 0

    @pytest.mark.parametrize("pair", sorted(T109_STAMPED))
    def test_the_run_verdict_is_unmoved(self, pair):
        """`DUPLICATE_IDENTITY` / exit 3 before and after, on all three. That
        is T082's remaining `038-NK-P3` and it outranks everything the line
        could reach -- recorded rather than inherited, because a task that
        improved nine rows and silently kept a red verdict would be reporting a
        pass it did not earn. Re-derived here rather than copied from T081,
        because T110 changed what the recompute returns."""
        before = with_recomputed_verdict(_t078(T078_BASELINES[pair]))
        after = _t109_stamped(T078_BASELINES[pair])
        assert before["verdict"] == after["verdict"] == "DUPLICATE_IDENTITY"
        assert before["exit_code"] == after["exit_code"] == 3

    @pytest.mark.parametrize("pair", sorted(T109_STAMPED))
    def test_the_stamped_artifact_still_satisfies_every_invariant(self, pair):
        """Invariant 5 (no `report_ref` needed for this token), R-2 (no
        over-accounting), R-5 (the residues equal the difference less the
        lines) and invariant 8 (the stored verdict matches the recomputed
        one) -- all checked by the real validator over the stamped
        document."""
        assert census.validate_artifact(
            _t109_stamped(T078_BASELINES[pair])) == ()

    @pytest.mark.parametrize("pair", sorted(T109_STAMPED))
    def test_the_committed_artifacts_are_untouched_on_disk(self, pair):
        """T109 changes the EMITTER, not any committed file. Every T078
        artifact still carries `accounted_for: []` on every row and
        `accounted_shortfall: 0` -- so nothing above can be an artifact that
        was quietly edited into agreement."""
        artifact = _t078(T078_BASELINES[pair])
        assert artifact["totals"]["accounted_shortfall"] == 0
        assert all(row.get("accounted_for") == []
                   for row in artifact["classes"])


class TestT109WhereT081WasWrongAndByExactlyHowMuch:
    """T081 predicted 9 / 13 / 11 stampable rows carrying 1885 / 64,621 / 8017
    objects. Ejagham reproduces exactly; the other two do not, and the delta is
    `CmFile` plus `CmFolder` to the object."""

    def test_ejagham_reproduces_t081_exactly(self):
        assert T109_STAMPED["ejagham"] == T109_T081_PREDICTED["ejagham"]

    @pytest.mark.parametrize("pair", ["ngoreme", "mbugwe"])
    def test_the_correction_is_cmfile_plus_cmfolder_and_nothing_else(
            self, pair):
        """Adding the two excluded rows back reproduces T081's figure exactly,
        which is what makes this a scope ruling rather than a measurement
        disagreement. Their own numbers are asserted from the artifacts, so the
        arithmetic cannot be satisfied by two other rows summing the same."""
        index = ("ejagham", "ngoreme", "mbugwe").index(pair)
        rows = _t078_rows(T078_BASELINES[pair])
        extra_rows, extra_objects = 0, 0
        for cls, measured in sorted(T109_T081_EXCLUDED.items()):
            assert rows[cls]["difference"] == measured[index], cls
            if measured[index] < 0:
                extra_rows += 1
                extra_objects += -measured[index]
        mine_rows, mine_objects = T109_STAMPED[pair]
        assert (mine_rows + extra_rows, mine_objects + extra_objects) \
            == T109_T081_PREDICTED[pair]

    def test_the_ruling_is_measured_no_sense_picture_exists_to_own_them(self):
        """THE RULING, as data. The Assumptions hand over SENSE PICTURES;
        `CmPicture` is the class that is sense pictures and it is 0 -> 0 on all
        three pairs. So the 2176 objects `CmFile` and `CmFolder` lose between
        them cannot be sense-picture content -- there is no picture anywhere to
        refer to them -- and they are the project's media folder, which the
        Assumptions name nowhere. An accounting line for them would be the
        unowned claim T081 refused for the phonological contexts."""
        for pair in sorted(T078_BASELINES):
            rows = _t078_rows(T078_BASELINES[pair])
            assert rows["CmPicture"]["source_count"] == 0, pair
            assert rows["CmPicture"]["difference"] == 0, pair
        mbugwe = _t078_rows(T078_BASELINES["mbugwe"])
        assert mbugwe["CmFile"]["source_count"] == 2173
        assert mbugwe["CmFile"]["difference"] == -2173
        # And the class the ruling turns on is rostered, as an admitted
        # promise, so the derivation covers all three named paths.
        assert census.governed_by_other_feature("CmPicture") is not None
        assert census.governed_by_other_feature("CmFile") is None
        assert census.governed_by_other_feature("CmFolder") is None

    def test_the_task_lines_own_scope_clause_is_narrower_than_its_authority(
            self):
        """A FINDING, PINNED. T109's task line scopes itself to
        "texts/wordforms/reversals only -- the classes the spec Assumptions
        already hand to another feature", and the spec Assumptions hand over
        THREE paths, not two: "Sense pictures, reversal indexes, and the
        texts/wordforms path". The contract row the task line cites as its
        authority says the same ("Texts/wordforms, reversals, and sense
        pictures"). The scope clause is therefore narrower than both its cited
        authority and its own stated justification. This test asserts the
        contract text, so the discrepancy cannot be resolved later by quietly
        editing the table."""
        root = Path(__file__).resolve().parents[2]
        contract = (
            root / "specs" / "038-transfer-fidelity-gaps" / "contracts"
            / "fidelity-census.md").read_text(encoding="utf-8")
        row = [
            line for line in contract.splitlines()
            if line.startswith("| `GOVERNED_BY_OTHER_FEATURE`")
        ]
        assert len(row) == 1
        assert "Texts/wordforms, reversals, and sense pictures" in row[0]
        assert "Needs no `report_ref`" in row[0]
        spec = (
            root / "specs" / "038-transfer-fidelity-gaps" / "spec.md"
        ).read_text(encoding="utf-8")
        assert ("**Sense pictures, reversal indexes, and the texts/wordforms "
                "path** are governed" in spec)


# ---------------------------------------------------------------------------
# T124: the re-census, pinned
# ---------------------------------------------------------------------------
#
# Feature 038 T124. Every reading below was taken live on 2026-08-27 against
# three FRESH throwaway destinations produced by the Wave 2 code
# (`GT038 T124 Ejagham` / `Ngoreme` / `Mbugwe`, each restored from
# `backups/Target 2026-07-06 0218.fwbackup`), by
# `debug/run038_t124_recensus.py`.
#
# WHY THESE TESTS EXIST AT ALL. T119-T123 all landed with host-free unit tests
# only, and their acceptance lines are stated per OWNING FIELD, per OWNING
# LIST, per MAPPING TYPE and per NESTING SHAPE -- four dimensions the census
# does not have and no test in this repo read. So the measurements that decide
# five tasks lived in one console transcript. These tests read the committed
# summary artifacts instead, so a later run that quietly contradicts them goes
# RED rather than unnoticed. They are hermetic: no FLEx host, no live project.
#
# They pin the MEASUREMENT, not the desired outcome. Four of them assert a
# LOSS. When the underlying defect is fixed, these tests are supposed to fail
# and be re-stated against the new artifact -- that is the point of pinning a
# number rather than describing it in prose.


def _t124_summary(pair: str) -> dict:
    path = (Path(__file__).resolve().parent / "_snapshots"
            / ("recensus-038-t124-%s.json" % pair))
    return json.loads(path.read_text(encoding="utf-8"))


class TestT124TheRecensusComparand:
    """Obligation 1: what was compared against what, and why."""

    def test_all_three_sources_were_on_their_t078_pins(self):
        """T081 said the sources had drifted. They had not.

        The digests are asserted by `TestT078ThePost037Baseline` against live
        disk; what is recorded HERE is the consequence -- that T124 re-ran the
        sanctioned pairs as they stand rather than naming fresh ones, which is
        only legitimate if the source halves were unchanged.
        """
        for pair in ("ejagham", "ngoreme", "mbugwe"):
            summary = _t124_summary(pair)
            assert summary["t078_status"] == (
                "historical; destination not touched by this run")

    def test_no_t078_destination_was_used_as_a_t124_destination(self):
        """The comparand cannot be the thing being measured.

        Re-transferring into a T078 destination would move its digest, and
        `T078_FWDATA_STATUS_TODAY` asserts that table in both directions with
        no backup of any of the three as they now stand.
        """
        protected = {"GT038 Ejagham After", "GT038 Ngoreme After",
                     "GT038 Phase6 Target"}
        used = {_t124_summary(p)["destination"]
                for p in ("ejagham", "ngoreme", "mbugwe")}
        assert used == {"GT038 T124 Ejagham", "GT038 T124 Ngoreme",
                        "GT038 T124 Mbugwe"}
        assert not (used & protected)

    def test_mbugwe_is_the_one_pair_whose_net_column_is_not_comparable(self):
        """T078's mbugwe baseline document was re-captured over in place.

        `phase6-starter.json` read `captured_at 2026-08-22T08:38:06` when the
        mbugwe comparand was taken and now reads `2026-08-25T14:35:56`; the
        08-22 capture is committed nowhere. Saying so is the difference
        between a diff that is comparable and one that merely looks it.
        """
        assert _t124_summary("ejagham")["baseline_comparable_to_t078"] is True
        assert _t124_summary("ngoreme")["baseline_comparable_to_t078"] is True
        assert _t124_summary("mbugwe")["baseline_comparable_to_t078"] is False


class TestT124PhaseFiveIsStillUnsatisfied:
    """Obligation 2. T081 stays open for a third time."""

    #: pair -> (P5 failure count) measured 2026-08-27.
    T124_P5_FAILURES = {"ejagham": 9, "ngoreme": 16, "mbugwe": 13}

    def test_p5_is_unsatisfied_on_every_pair(self):
        for pair, expected in self.T124_P5_FAILURES.items():
            phase = _t124_summary(pair)["phase_5"]
            assert phase["satisfied"] is False
            assert len(phase["failures"]) == expected

    def test_every_p5_failure_is_the_same_shape_or_a_duplicate(self):
        """66-of-69 was one shape at T081 and it still is.

        Either "SHORTFALL carrying NO accounting line" or the `PhNCFeatures`
        duplicate row, which is T082's `038-NK-P3` and excluded from P5 by
        construction. A NEW shape appearing here means the residue changed
        character, not just size.
        """
        for pair in self.T124_P5_FAILURES:
            for line in _t124_summary(pair)["phase_5"]["failures"]:
                assert ("carries NO accounting line" in line
                        or "unaccounted duplicate objects" in line), line

    def test_the_verdict_outranks_the_phase_so_the_exit_code_cannot_be_read(self):
        """`DUPLICATE_IDENTITY` forces exit 3 whether or not P5 holds.

        This is why T124 read `evaluate_phase` in-process. A future reader who
        "checks the gate" by looking at the exit code would learn nothing about
        P5 at all.
        """
        for pair in self.T124_P5_FAILURES:
            summary = _t124_summary(pair)
            assert summary["verdict"] == "DUPLICATE_IDENTITY"
            assert summary["exit_code"] == 3


class TestT124T119PerOwningField:
    """T119's acceptance, per pair AND per owning field."""

    def test_the_headline_owner_is_a_total_loss_on_every_pair(self):
        """`MoStemMsa.MsFeatures` 117 / 782 / 104 -> 0 / 0 / 0.

        1,003 objects, the largest single block in the P5 residue, while
        `MoStemMsa` itself is count-MATCHED -- so no counts-only gate can see
        it. This is the reading that keeps T119 unchecked.
        """
        expected_source = {"ejagham": 117, "ngoreme": 782, "mbugwe": 104}
        field = "MoStemMsa.MsFeatures (flid=5001001)"
        for pair, src in expected_source.items():
            row = _t124_summary(pair)["t119_per_owning_field"][field]
            assert row["source"] == src
            assert row["dest"] == 0
            assert row["verdict"] == "TOTAL_LOSS"

    def test_three_of_the_eight_new_owners_do_work_and_only_mbugwe_holds_them(self):
        """Wave 1 measured all three as 0 in the destination.

        Recording the PASSES matters as much as the failures: without them
        T119 reads as wholly ineffective, which the measurement does not
        support.
        """
        rows = _t124_summary("mbugwe")["t119_per_owning_field"]
        for field, count in (
            ("MoDerivAffMsa.FromMsFeatures (flid=5031001)", 17),
            ("MoDerivAffMsa.ToMsFeatures (flid=5031002)", 17),
            ("MoAffixAllomorph.MsEnvFeatures (flid=5027001)", 1),
        ):
            assert rows[field]["source"] == count
            assert rows[field]["dest"] == count
            assert rows[field]["verdict"] == "OK"
        # ...and the other two pairs hold none of them, so they cannot
        # corroborate and must not be read as if they could.
        for pair in ("ejagham", "ngoreme"):
            other = _t124_summary(pair)["t119_per_owning_field"]
            for field in ("MoDerivAffMsa.FromMsFeatures (flid=5031001)",
                          "MoAffixAllomorph.MsEnvFeatures (flid=5027001)"):
                assert other[field]["verdict"] == "NO_DATA"

    def test_the_t119_open_question_is_answered_on_ngoreme(self):
        """`MoInflAffMsa.InflFeats` was 38 -> 18 and is now 38 -> 38.

        T119 asked why the owner measured working on two pairs differed on the
        third, and named `FsComplexValue` as the suspect. The complex-value
        reader closed it, and `FsComplexValue.Value` itself moves 0 -> 20.
        """
        rows = _t124_summary("ngoreme")["t119_per_owning_field"]
        infl = rows["MoInflAffMsa.InflFeats (flid=5038001)"]
        assert (infl["source"], infl["dest"]) == (38, 38)
        complex_value = rows["FsComplexValue.Value (flid=53001)"]
        assert complex_value["source"] == 825
        assert complex_value["dest"] == 20

    def test_reference_forms_is_inconsistent_across_pairs(self):
        """10 -> 10 on ejagham but 44 -> 0 on ngoreme.

        T119 scoped `PartOfSpeech.ReferenceForms` out by citing T045's
        documented depth limit, which predicts an EMPTY SHELL uniformly. A
        total loss on one pair and a clean pass on another is not that, so the
        scoping reason does not cover what was measured.
        """
        field = "PartOfSpeech.ReferenceForms (flid=5049010)"
        assert _t124_summary("ejagham")["t119_per_owning_field"][field][
            "verdict"] == "OK"
        ngoreme = _t124_summary("ngoreme")["t119_per_owning_field"][field]
        assert (ngoreme["source"], ngoreme["dest"]) == (44, 0)
        assert ngoreme["verdict"] == "TOTAL_LOSS"


class TestT124T122PerOwningList:
    """T122's acceptance: the in-scope list, and only it, has to be matched."""

    def test_the_one_in_scope_list_is_matched_on_both_pairs_that_hold_it(self):
        """`MoMorphData.ProdRestrict` -- ruled IN SCOPE, 1/1 and 3/3.

        `cmpossibility-list-rulings.md` measured -1 on ngoreme and -3 on
        mbugwe. Both are now zero.
        """
        key = "MoMorphData.ProdRestrict (flid=5040009) | name=None"
        for pair, count in (("ngoreme", 1), ("mbugwe", 3)):
            row = _t124_summary(pair)["t122_per_owning_list"][key]
            assert row["source"] == count
            assert row["dest"] == count

    def test_ejagham_holds_no_in_scope_list_so_it_cannot_corroborate(self):
        """The ruling records "--" for ejagham, and the probe agrees."""
        lists = _t124_summary("ejagham")["t122_per_owning_list"]
        assert not [k for k in lists if "ProdRestrict" in k]

    def test_every_remaining_deficit_is_in_a_list_the_ruling_excludes(self):
        """The -308 / -397 / -332 class row is out-of-scope content.

        Asserted as a SUBSET rather than an equality: the ruling excludes more
        lists than any one pair happens to hold.
        """
        excluded = (
            "Scripture.NoteCategories", "LexDb.Languages",
            "LangProject.GenreList", "DsDiscourseData.ChartMarkers",
            "LangProject.CheckLists", "LexDb.DialectLabels",
            "LangProject.Status", "DsDiscourseData.ConstChartTempl",
            "LexDb.ExtendedNoteTypes",
        )
        for pair in ("ejagham", "ngoreme", "mbugwe"):
            for key, row in _t124_summary(pair)["t122_per_owning_list"].items():
                if row["dest"] >= row["source"]:
                    continue
                assert any(name in key for name in excluded), (pair, key, row)

    def test_the_ruling_predicted_a_surplus_and_a_shortfall_in_one_list(self):
        """`ChartMarkers` +30 on ngoreme, -10 on mbugwe.

        The ruling called this out as the thing a class-level verdict could
        not express and a net figure would have cancelled. It reproduces.
        """
        key = "DsDiscourseData.ChartMarkers (flid=5124003) | name=None"
        ngoreme = _t124_summary("ngoreme")["t122_per_owning_list"][key]
        mbugwe = _t124_summary("mbugwe")["t122_per_owning_list"][key]
        assert ngoreme["dest"] - ngoreme["source"] == 30
        assert mbugwe["dest"] - mbugwe["source"] == -10


class TestT124T123LexReferenceAndNesting:
    """Obligations 3 and 4."""

    def test_no_lex_reference_survives_and_ngoreme_is_the_only_witness(self):
        source = _t124_summary("ngoreme")["t123_lex_references"]["source"]
        dest = _t124_summary("ngoreme")["t123_lex_references"]["destination"]
        assert source["lex_references_total"] == 5
        assert dest["lex_references_total"] == 0
        for pair in ("ejagham", "mbugwe"):
            both = _t124_summary(pair)["t123_lex_references"]
            assert both["source"]["lex_references_total"] == 0
            assert both["destination"]["lex_references_total"] == 0

    def test_the_five_distribute_as_three_tree_one_collection_one_sequence(self):
        """The distribution T123 and T124 both predicted, measured.

        `MappingType` 3 is TREE, 0 is COLLECTION, 4 is SEQUENCE.
        """
        by_type = _t124_summary("ngoreme")["t123_lex_references"]["source"][
            "by_owning_type"]
        assert by_type["Specific | MappingType=3"]["references"] == 3
        assert by_type["Synonyms | MappingType=0"]["references"] == 1
        assert by_type["Calendar | MappingType=4"]["references"] == 1
        assert (by_type["Calendar | MappingType=4"]["targets_per_reference"]
                == [13])

    def test_the_nesting_demotions_are_named_and_counted_per_guid(self):
        """4 on ejagham, 0 on ngoreme, 1 on mbugwe.

        Per GUID, because the restored backup carries `LexEntryInflType` of
        its own and the count buckets alone mix starter items with
        transferred ones. `absent=0` / `dest_only=0` on ejagham is what makes
        its 6/1 -> 2/5 arithmetic closed rather than suggestive.
        """
        ejagham = _t124_summary("ejagham")["t123_nesting_verdict_by_guid"][
            "LexEntryInflType"]
        changed = ejagham["matched_guid_nesting_CHANGED"]
        assert len(changed) == 4
        assert {row["name"] for row in changed} == {
            "Perfective", "Hortative", "Conditional", "Retrospective"}
        for row in changed:
            assert row["source_nesting"] == "nested"
            assert row["destination_nesting"] == "top_level"
        assert not ejagham["source_guid_absent_from_destination"]
        assert not ejagham["destination_only_guids"]

        ngoreme = _t124_summary("ngoreme")["t123_nesting_verdict_by_guid"][
            "LexEntryInflType"]
        assert not ngoreme["matched_guid_nesting_CHANGED"]

        mbugwe = _t124_summary("mbugwe")["t123_nesting_verdict_by_guid"][
            "LexEntryInflType"]
        assert len(mbugwe["matched_guid_nesting_CHANGED"]) == 1
        assert mbugwe["matched_guid_nesting_CHANGED"][0]["name"] == "Class 10"

    def test_the_lex_entry_type_loss_is_one_named_object_not_twelve(self):
        """`straggler-rulings.md` section 3: the target is -1/-1, not -12/-12.

        Confirmed by identity, and both objects named -- which the census
        cannot do, because gross-basis subtraction reports -12.
        """
        ngoreme = _t124_summary("ngoreme")["t123_nesting_verdict_by_guid"][
            "LexEntryType"]["source_guid_absent_from_destination"]
        assert len(ngoreme) == 1
        assert ngoreme[0]["name"] == "Perfective"
        assert ngoreme[0]["source_nesting"] == "nested"

        mbugwe = _t124_summary("mbugwe")["t123_nesting_verdict_by_guid"][
            "LexEntryType"]["source_guid_absent_from_destination"]
        assert len(mbugwe) == 1
        assert mbugwe[0]["name"] == "Periphrastic Form"
        assert mbugwe[0]["source_nesting"] == "top_level"


class TestT124T121PhCodeBothHalves:
    """T121's acceptance, stated separately for the two halves."""

    _PHONEME = "PhTerminalUnit.Codes (flid=5090003) [runtime=PhPhoneme]"
    _BOUNDARY = "PhTerminalUnit.Codes (flid=5090003) [runtime=PhBdryMarker]"

    def test_the_phoneme_half_moved_off_the_baseline_on_every_pair(self):
        """starter 23 + source = destination, exactly, three times over."""
        expected = {"ejagham": (41, 64), "ngoreme": (87, 110),
                    "mbugwe": (77, 100)}
        for pair, (src, dest) in expected.items():
            row = _t124_summary(pair)["t121_starter_baseline_readings"]["PhCode"]
            assert row["source_owners_raw"][self._PHONEME] == src
            assert row["destination_owners_raw"][self._PHONEME] == dest
            assert dest == 23 + src
            assert row["moved_off_baseline"] is True

    def test_the_boundary_half_clause_is_unsatisfiable_by_construction(self):
        """2 = 2 = 2 on every sanctioned pair.

        Source holds 2 boundary-marker codes, the starter holds 2, the
        destination holds 2. "The destination stops reading exactly the
        starter baseline" therefore CANNOT become true for this half however
        correct the transfer is -- a count cannot distinguish an
        identity-match from an untouched starter object. This test pins the
        clause as mis-stated (T086-style) rather than the code as defective;
        closing it needs an identity check or a different corpus.
        """
        for pair in ("ejagham", "ngoreme", "mbugwe"):
            row = _t124_summary(pair)["t121_starter_baseline_readings"]["PhCode"]
            assert row["source_owners_raw"][self._BOUNDARY] == 2
            assert row["destination_owners_raw"][self._BOUNDARY] == 2
            assert row["starter_baseline_total"] == 25


class TestT124T120TheRulesArriveAndTheirContentsDoNot:
    """T120's acceptance: which right-hand sides raise, on which pairs."""

    def test_every_phonological_rule_is_matched_while_its_contents_are_lost(self):
        """`PhRegularRule` MATCHED 3/3; 14 `PhSegRuleRHS` gone.

        Read off the census artifacts rather than the summary, because this is
        a per-class row and the point is that the CLASS-level reading is where
        the loss is visible while the rule row stays green.
        """
        expected = {"ejagham": (6, 6, 6, 6), "ngoreme": (21, 21, 21, 18),
                    "mbugwe": (39, 39, 39, 28)}
        for pair, (rule_src, rule_net, rhs_src, rhs_net) in expected.items():
            path = (Path(__file__).resolve().parent / "_snapshots"
                    / ("census-038-t124-%s.json" % pair))
            rows = {r["class"]: r
                    for r in json.loads(path.read_text(encoding="utf-8"))[
                        "classes"]}
            assert rows["PhRegularRule"]["source_count"] == rule_src
            assert rows["PhRegularRule"]["destination_count_net"] == rule_net
            assert rows["PhRegularRule"]["verdict_class"] == "MATCHED"
            assert rows["PhSegRuleRHS"]["source_count"] == rhs_src
            assert rows["PhSegRuleRHS"]["destination_count_net"] == rhs_net
