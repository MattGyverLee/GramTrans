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

import json
import re
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
