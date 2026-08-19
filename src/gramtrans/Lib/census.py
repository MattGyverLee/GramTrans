"""Feature 038 -- the per-object-class fidelity census (FR-009..FR-013).

THE CONTRACT THIS IMPLEMENTS
---------------------------
- `specs/038-transfer-fidelity-gaps/contracts/fidelity-census.md` -- the human
  contract, including every rule the schema cannot express.
- `specs/038-transfer-fidelity-gaps/contracts/census-artifact.schema.json` --
  the sole authority for anything EMITTED. Every object in it is
  `additionalProperties: false`, so an extra key is a hard validation failure
  rather than a harmless addition.
- `tests/integration/test_object_census.py` -- the executable specification of
  the symbol surface below.

TWO NAMING LAYERS, ON PURPOSE (see `Lib/models.py`'s feature-038 block). The
in-memory dataclasses keep `data-model.md`'s field names; the artifact uses the
schema's. The reconciliation is `models.CLASS_CENSUS_ROW_ARTIFACT_FIELDS` and
its two siblings, and the emitters here are driven BY those tables -- there is
deliberately no third, hand-written set of names.

THE VOCABULARIES ARE RE-EXPORTS, NEVER RE-DECLARATIONS. `REASON_TOKENS` and
friends are bound to the `CENSUS_*` constants in `models.py`. The dependency
direction is census -> models and never the reverse (models has to reject an
out-of-vocabulary token at construction, and cannot import from here), so one
literal list carries two names and cannot drift.

NO LIVE-FLEx IMPORT AT MODULE SCOPE. Every `flexicon` / `SIL.LCModel` /
`FLExInit` import in this module is function-level. That is load-bearing, not
style: `tests/integration/test_object_census.py` imports this module and must
stay runnable with no FieldWorks host and no project (it currently collects in
under a second), and `tests/integration/test_034_standalone_preview_live.py`
demonstrates what an unconditional `FLExInitialize()` at import time does to a
test session on this machine (`Windows fatal exception: access violation`).
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .models import (
    CENSUS_NOT_EVALUATED_REASONS,
    CENSUS_REASON_TOKENS,
    CENSUS_REASONS_NOT_REQUIRING_REPORT_REF,
    CENSUS_ROW_VERDICT_CLASSES,
    CENSUS_SCHEMA_VERSION as _MODELS_CENSUS_SCHEMA_VERSION,
)

# ---------------------------------------------------------------------------
# Re-exported vocabularies (T020 assigns the rest; these three are needed from
# T016 onward because the class-list loader stamps NOT_EVALUATED reasons).
#
# RE-EXPORT, NOT RE-DECLARATION. `models.py` owns the literals.
# ---------------------------------------------------------------------------

#: `census-artifact.schema.json` top-level `schema_version`.
CENSUS_SCHEMA_VERSION: int = _MODELS_CENSUS_SCHEMA_VERSION

#: FR-013's closed 16-token reason vocabulary, in schema enum order.
REASON_TOKENS: tuple = CENSUS_REASON_TOKENS

#: The four tokens exempt from `accountedLine.report_ref` (R-1).
REASONS_NOT_REQUIRING_REPORT_REF: frozenset = (
    CENSUS_REASONS_NOT_REQUIRING_REPORT_REF
)

#: The three reasons that make a row NOT_EVALUATED rather than measured.
NOT_EVALUATED_REASONS: frozenset = CENSUS_NOT_EVALUATED_REASONS

#: `$defs.classRow.verdict_class.enum`.
ROW_VERDICT_CLASSES: tuple = CENSUS_ROW_VERDICT_CLASSES


# ---------------------------------------------------------------------------
# Failure types
#
# Each carries the VERDICT it maps to, so a caller never has to re-derive the
# verdict from an exception class name, and every message names the offending
# class (CP-1..CP-4 all fail "by class name").
# ---------------------------------------------------------------------------


class CensusFailure(Exception):
    """Base for a census failure that has a verdict token."""

    #: Overridden per subclass; one of the nine `verdictToken` members.
    verdict: str = "CENSUS_ERROR"

    def __init__(self, message: str, classes: tuple = ()) -> None:
        super().__init__(message)
        #: The classes this failure names. Never empty for CP-1/CP-4.
        self.classes: tuple = tuple(classes)


class CoverageIncomplete(CensusFailure):
    """CP-1 derivation mismatch, a missing `classes` row, or a class present in
    BOTH the 035 coverage floor and this feature's additions ledger (CP-4).

    Verdict `COVERAGE_INCOMPLETE`, exit 6. FR-012 coverage is PROVEN, not
    asserted: the derivation runs on every census invocation rather than being
    pinned to a stored digest, so drift in the truth source cannot pass
    unnoticed.
    """

    verdict = "COVERAGE_INCOMPLETE"


class CensusError(CensusFailure):
    """An R-1/R-2 accounting violation, a Section 8 tally mismatch, an
    `fwdata_sha256` that changed under the census, a mis-declared baseline
    kind, an unclassifiable reason, or an unhandled exception.

    Verdict `CENSUS_ERROR`, exit 7.
    """

    verdict = "CENSUS_ERROR"


# ---------------------------------------------------------------------------
# Truth-source locations (fidelity-census.md 3.1)
#
# 038 READS these. 038 does not fork them: the floor and the natural-key
# roster are owned by feature 035, and edits to either are coordinated with
# that live session.
# ---------------------------------------------------------------------------

INVENTORY_DOCUMENT = "specs/035-fullsweep-fidelity/object-inventory.md"
COVERAGE_FLOOR_DOCUMENT = (
    "specs/035-fullsweep-fidelity/contracts/coverage-floor.json"
)
NATURAL_KEY_ROSTER_DOCUMENT = (
    "specs/035-fullsweep-fidelity/contracts/natural-key-identity-roster.json"
)

#: The tables of `object-inventory.md` the class list is derived from. TABLE 3
#: (ride-along owned children) and TABLE 4 (writing-system / configuration
#: artifacts) are deliberately NOT derivation inputs -- see `CENSUS_ADDITIONS`,
#: where `PhCode` is carried explicitly precisely because it lives in TABLE 3.
DERIVATION_TABLES: tuple = ("TABLE 1", "TABLE 2")

#: `$defs.classRow.inventory_tables` tokens, keyed by the heading above.
_INVENTORY_TABLE_TOKENS = {
    "TABLE 1": "TABLE_1",
    "TABLE 2": "TABLE_2",
    "TABLE 3": "TABLE_3",
    "TABLE 4": "TABLE_4",
}

#: An LCM class name as the inventory writes it: an initial capital, then
#: letters and digits only. Deliberately strict, so prose cells ("Writing
#: system", "(no object created)", "(reference CREATE arm)") cannot be mistaken
#: for classes -- the derivation is an equality proof and a false positive in it
#: is a failed census run, not a warning.
_CLASS_NAME_RE = re.compile(r"^[A-Z][A-Za-z0-9]+$")


# ---------------------------------------------------------------------------
# CP-3 / CP-4 ledgers
# ---------------------------------------------------------------------------

#: CP-4 -- the three classes measured in `census-evidence.md` section 0 that are
#: absent from the 035 floor. Each is `owed_to_035: true`: the addition must be
#: dropped in the same change that adds it to the floor, so the ledger cannot
#: rot into a second truth source (a class in BOTH is `COVERAGE_INCOMPLETE`).
CENSUS_ADDITIONS: tuple = (
    {
        "class": "MoAffixProcess",
        "rationale": (
            "Absent from object-inventory.md entirely, because the engine has "
            "no create path for it -- the class the transfer silently "
            "downgraded. A truth-source gap, not a corpus gap."
        ),
        "measured_evidence": "Ejagham 13 -> 0, Ngoreme 1 -> 0",
        "owed_to_035": True,
    },
    {
        "class": "PhCode",
        "rationale": (
            "object-inventory.md TABLE 3 (ride-along): flexicon's phoneme "
            "GetSyncableProperties explicitly does not include CodesOS, so "
            "nothing carries it and nothing reports the drop."
        ),
        "measured_evidence": "43 -> 25, 89 -> 25",
        "owed_to_035": True,
    },
    {
        "class": "CmTranslation",
        "rationale": (
            "Reached through the texts path; never projected into the floor."
        ),
        "measured_evidence": "Ngoreme 7925 -> 2",
        "owed_to_035": True,
    },
)

#: CP-3 -- the classes `object-inventory.md` TABLE 2 records as NEVER created
#: by any path. They are `gate_scope: "advisory"` and cannot by themselves fail
#: the gate; SC-005's scope is exactly the `required` set.
NEVER_CREATED_CLASSES: frozenset = frozenset({
    "LexRefType", "LexAppendix", "PhBdryMarker",
})

#: Classes that get a NOT_EVALUATED row with a stated reason rather than a
#: measurement. `MoForm` / `MoMorphSynAnalysis` are abstract LCM bases with no
#: factory (035's `excluded_not_measurable`); `CmAnthroItem` is in the floor but
#: out of THIS feature's scope, so its measured 859 -> 0 on Ejagham stays
#: visible and is explicitly not counted against the gate.
NOT_EVALUATED_CLASS_REASONS: dict = {
    "MoForm": "ABSENT_BY_CONSTRUCTION",
    "MoMorphSynAnalysis": "ABSENT_BY_CONSTRUCTION",
    "CmAnthroItem": "OUT_OF_SCOPE_CLASS",
}

#: CP-1's arithmetic: `in_scope_classes` (69) + `census_additions` (3). Held as
#: a constant so a change in either truth source has to be a deliberate edit
#: here as well as there.
#:
#: NOTE ON THE TWO COUNTS. This is the REQUIRED class count of
#: fidelity-census.md 3.2 ("therefore 72"). It is NOT necessarily
#: `len(classes)`: the same section also requires a NOT_EVALUATED row for each
#: `excluded_not_measurable` class, and `$defs.classRow.in_class_list_via` has
#: an `"excluded_not_measurable"` member precisely so those rows can say how
#: they got in. The artifact's `required_class_count` is therefore emitted as
#: the ROW count (invariant 1 is `len(classes) == required_class_count` and is
#: what the validator enforces); `REQUIRED_CLASS_COUNT` stays the CP-1 figure.
REQUIRED_CLASS_COUNT: int = 72


# ---------------------------------------------------------------------------
# Locating the truth sources
# ---------------------------------------------------------------------------


def repo_root(start: Optional[Path] = None) -> Path:
    """The repository root, found by walking UP for the 035 contracts.

    Walked rather than hard-coded so the census runs from a worktree, a
    checkout, or an editable install without a path constant to keep in sync.
    """
    base = Path(__file__).resolve() if start is None else Path(start).resolve()
    for parent in (base, *base.parents):
        if (parent / COVERAGE_FLOOR_DOCUMENT).is_file():
            return parent
    raise CensusError(
        "could not locate the repository root: no ancestor of "
        + str(base) + " holds " + COVERAGE_FLOOR_DOCUMENT
        + " -- the census re-derives its class list from that document at run "
        "time (CP-1) and cannot make a coverage claim without it"
    )


def sha256_of(path: Path) -> str:
    """The lowercase hex SHA-256 of a file, as the artifact records it.

    Used for both the truth-source digests (provenance for the reader) and the
    `fwdata_sha256_before`/`_after` pair that proves the census wrote nothing.
    """
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# Parsing `object-inventory.md` TABLE 1 + TABLE 2 -- at RUN TIME (CP-1)
# ---------------------------------------------------------------------------


def _iter_table_rows(text: str, heading: str):
    """Yield the cell lists of one `## <heading> ...` markdown table.

    The inventory's tables are separated by `##` headings, so a heading switch
    ends the table. The header row and its `---` separator are skipped.
    """
    inside = False
    for line in text.splitlines():
        if line.startswith("## "):
            inside = line.startswith("## " + heading)
            continue
        if not inside or not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells or not cells[0]:
            continue
        if cells[0] in ("Object (class)",) or set(cells[0]) <= {"-", ":"}:
            continue
        yield cells


def _classes_in_cell(cell: str) -> tuple:
    """The LCM class names one first-column cell names.

    The inventory writes a first column three ways, all of which appear:
    `PartOfSpeech`; `CmPossibility (\\`LexDbOA.SenseTypesOA\\`)` -- the class
    plus the owning field, which is NOT part of the class name; and
    `PhNCSegments / PhNCFeatures` -- two classes sharing one row. Prose cells
    (`Writing system`, `(no object created)`) name no class and yield nothing.
    """
    without_parens = re.sub(r"\([^)]*\)", " ", cell)
    found = []
    for part in without_parens.split("/"):
        name = part.strip().strip("`").strip()
        if name and _CLASS_NAME_RE.match(name) and name not in found:
            found.append(name)
    return tuple(found)


def parse_inventory_tables(
    text: str, tables: tuple = DERIVATION_TABLES,
) -> dict:
    """Parse `object-inventory.md` and return `{class_name: (table tokens,)}`.

    This is CP-1's derivation, run on EVERY census invocation. It is not
    checked against a stored digest, because a stored digest proves only that
    the document has not changed -- not that the floor still agrees with it.
    """
    seen: dict = {}
    for heading in tables:
        token = _INVENTORY_TABLE_TOKENS[heading]
        rows = list(_iter_table_rows(text, heading))
        if not rows:
            raise CoverageIncomplete(
                "object-inventory.md has no parseable " + heading
                + " -- the census derives its class list from "
                + ", ".join(tables) + " at run time (CP-1) and a truth source "
                "it cannot read is a coverage failure, not an empty result"
            )
        for cells in rows:
            for name in _classes_in_cell(cells[0]):
                tokens = seen.setdefault(name, [])
                if token not in tokens:
                    tokens.append(token)
    return {name: tuple(tokens) for name, tokens in seen.items()}


def load_coverage_floor(path: Path) -> dict:
    """035's `coverage-floor.json`, as a dict. Read, never forked."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    for key in ("in_scope_classes", "excluded_not_measurable"):
        if key not in data:
            raise CoverageIncomplete(
                "coverage-floor.json is missing " + repr(key)
                + " -- the census cannot prove FR-012 coverage against a "
                "floor that does not declare its own scope"
            )
    return data


# ---------------------------------------------------------------------------
# The class list
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ClassListEntry:
    """One class's PLACE in the census, decided before anything is counted.

    Separate from `models.ClassCensusRow` on purpose. The row is the
    measurement; this is the provenance the measurement is reported under, and
    it answers three of the four REQUIRED `classRow` keys that are not
    functions of the row itself (`CLASS_CENSUS_ROW_ARTIFACT_FIELDS`'s
    docstring names them): `gate_scope`, `in_class_list_via` and
    `inventory_tables`. Carrying them here rather than passing them to the
    emitter keeps CP-3's advisory marking and CP-4's floor-vs-additions
    provenance in ONE place -- the loader that actually knows them -- instead
    of being re-decided per emission.
    """

    object_class: str                        # -> artifact `class`
    in_class_list_via: str                   # -> artifact `in_class_list_via`
    gate_scope: str                          # -> artifact `gate_scope`
    engine_can_create: bool                  # -> artifact `engine_can_create`
    inventory_tables: tuple = ()             # -> artifact `inventory_tables`
    not_evaluated_reason: Optional[str] = None   # -> `not_evaluated_reason`
    #: A1 (T018): the owning feature system for a class reachable from both,
    #: e.g. `FsFeatStrucType`. `None` for every ordinary class.
    owning_feature_system: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.object_class:
            raise CensusError("ClassListEntry.object_class must be non-empty")
        if self.in_class_list_via not in (
                "coverage_floor", "census_additions", "excluded_not_measurable"):
            raise CensusError(
                "ClassListEntry.in_class_list_via for "
                + repr(self.object_class) + " is "
                + repr(self.in_class_list_via)
                + ", outside the schema's in_class_list_via enum"
            )
        if self.gate_scope not in ("required", "advisory"):
            raise CensusError(
                "ClassListEntry.gate_scope for " + repr(self.object_class)
                + " is " + repr(self.gate_scope) + ", not 'required' or "
                "'advisory'"
            )
        if (self.not_evaluated_reason is not None
                and self.not_evaluated_reason not in NOT_EVALUATED_REASONS):
            raise CensusError(
                "ClassListEntry.not_evaluated_reason for "
                + repr(self.object_class) + " is "
                + repr(self.not_evaluated_reason) + ", not one of "
                + repr(tuple(sorted(NOT_EVALUATED_REASONS)))
            )

    @property
    def is_not_evaluated(self) -> bool:
        """True when the class is reported without being measured."""
        return self.not_evaluated_reason is not None

    @property
    def row_key(self) -> str:
        """The identity this entry's row is emitted under.

        Equal to `object_class` for every ordinary class. For an A1-split class
        it carries the owning feature system as well, because a single summed
        row would let a shortfall in one system be masked by a surplus in the
        other -- see `split_class_label` (T018).
        """
        if self.owning_feature_system is None:
            return self.object_class
        return split_class_label(self.object_class, self.owning_feature_system)


@dataclass(frozen=True)
class ClassList:
    """The full census roster plus the evidence that it is complete.

    `entries` is one entry per emitted row, in a stable order: the required
    classes (floor, then additions) alphabetically, then the
    `excluded_not_measurable` rows. `derivation_check` and `provenance` are
    emitted verbatim into `class_list_provenance`.
    """

    entries: tuple
    derivation_check: dict
    provenance: dict

    def __post_init__(self) -> None:
        seen = set()
        for entry in self.entries:
            if entry.row_key in seen:
                raise CoverageIncomplete(
                    "the class list carries two rows for " + repr(entry.row_key)
                    + " -- exactly one row per class (CP-2)",
                    (entry.object_class,),
                )
            seen.add(entry.row_key)

    # ---- derived views -------------------------------------------------

    @property
    def classes(self) -> tuple:
        """Every emitted row key, in emission order."""
        return tuple(e.row_key for e in self.entries)

    @property
    def required_classes(self) -> tuple:
        """The CP-1 class set: coverage floor union census additions.

        DISTINCT class names, so an A1 split (one class, two rows -- see
        `split_feature_system_entries`) leaves this count untouched, exactly as
        Amendment A1 requires: "it adds no class to the required list and does
        not alter the 72-class count". The row count is `required_class_count`.
        """
        return tuple(dict.fromkeys(
            e.object_class for e in self.entries
            if e.in_class_list_via in ("coverage_floor", "census_additions")
        ))

    @property
    def required_class_count(self) -> int:
        """-> artifact `required_class_count`.

        The ROW count, because invariant 1 is `len(classes) ==
        required_class_count` and a validator recomputes it. See the note on
        `REQUIRED_CLASS_COUNT` for why the two numbers differ by the
        `excluded_not_measurable` rows.
        """
        return len(self.entries)

    def entry_for(self, class_or_row_key: str) -> Optional[ClassListEntry]:
        """The entry for one class or row key, or None when absent -- which is
        itself a coverage defect (FR-012 requires a row per class)."""
        for entry in self.entries:
            if class_or_row_key in (entry.object_class, entry.row_key):
                return entry
        return None

    def entries_for(self, object_class: str) -> tuple:
        """Every entry for one class. More than one only for an A1 split."""
        return tuple(e for e in self.entries if e.object_class == object_class)


def _gate_scope_for(object_class: str, engine_can_create: bool) -> str:
    """CP-3: `gate_scope` is explicit per row, and advisory is not a judgement.

    Rows the engine can create are `required`; the classes no path creates are
    `advisory` and cannot by themselves fail the gate.
    """
    return "required" if engine_can_create else "advisory"


def derive_class_list(
    root: Optional[Path] = None,
    *,
    additions: tuple = CENSUS_ADDITIONS,
) -> ClassList:
    """Derive the census class list from the truth sources, and PROVE it.

    Four executable checks, each failing by class name:

    - **CP-1** the class set parsed out of `object-inventory.md` TABLE 1 +
      TABLE 2 must equal `in_scope_classes` union `excluded_not_measurable`.
      A class added to the inventory and not to the floor, or the reverse,
      fails the run and names the class.
    - **CP-2** exactly one row per class; a class with no instances anywhere is
      NOT_EVALUATED, never omitted (enforced by `ClassList.__post_init__` and
      by invariant 1 downstream).
    - **CP-3** `LexRefType` / `LexAppendix` / `PhBdryMarker` are advisory.
    - **CP-4** a class in both the floor and the additions ledger is
      `COVERAGE_INCOMPLETE`.

    Raises `CoverageIncomplete` (verdict `COVERAGE_INCOMPLETE`, exit 6) on any
    of them.
    """
    base = repo_root() if root is None else Path(root)
    inventory_path = base / INVENTORY_DOCUMENT
    floor_path = base / COVERAGE_FLOOR_DOCUMENT
    roster_path = base / NATURAL_KEY_ROSTER_DOCUMENT

    if not inventory_path.is_file():
        raise CoverageIncomplete(
            "the class-list truth source is missing: " + str(inventory_path)
            + " -- CP-1 re-derives the class set from it on every invocation"
        )

    derived = parse_inventory_tables(
        inventory_path.read_text(encoding="utf-8"))
    floor = load_coverage_floor(floor_path)

    in_scope = tuple(floor["in_scope_classes"])
    excluded = tuple(
        (e["class"], e.get("reason", "")) for e in floor["excluded_not_measurable"]
    )
    excluded_names = tuple(name for name, _ in excluded)
    addition_names = tuple(a["class"] for a in additions)

    # -- CP-4, checked BEFORE CP-1 so a double-listed class is reported as the
    # ledger error it is rather than as a derivation surplus.
    both = tuple(sorted(set(in_scope) & set(addition_names)))
    if both:
        raise CoverageIncomplete(
            "these classes are in BOTH coverage-floor.json in_scope_classes "
            "and the census additions ledger: " + ", ".join(both)
            + " -- an addition must be dropped in the same change that adds it "
            "to the floor, so the ledger cannot rot into a second truth source "
            "(CP-4)",
            both,
        )

    # -- CP-1, the derivation proof.
    expected = set(in_scope) | set(excluded_names)
    in_inventory_not_in_floor = tuple(sorted(set(derived) - expected))
    in_floor_not_in_inventory = tuple(sorted(expected - set(derived)))
    matched = not in_inventory_not_in_floor and not in_floor_not_in_inventory

    derivation_check = {
        "performed": True,
        "result": "match" if matched else "mismatch",
        "derived_class_count": len(derived),
        "in_inventory_not_in_floor": list(in_inventory_not_in_floor),
        "in_floor_not_in_inventory": list(in_floor_not_in_inventory),
    }

    if not matched:
        raise CoverageIncomplete(
            "CP-1 derivation mismatch between " + INVENTORY_DOCUMENT + " and "
            + COVERAGE_FLOOR_DOCUMENT + ": in the inventory and not the floor: "
            + (", ".join(in_inventory_not_in_floor) or "(none)")
            + "; in the floor and not the inventory: "
            + (", ".join(in_floor_not_in_inventory) or "(none)"),
            in_inventory_not_in_floor + in_floor_not_in_inventory,
        )

    entries = []
    for name in sorted(in_scope):
        engine_can_create = name not in NEVER_CREATED_CLASSES
        entries.append(ClassListEntry(
            object_class=name,
            in_class_list_via="coverage_floor",
            gate_scope=_gate_scope_for(name, engine_can_create),
            engine_can_create=engine_can_create,
            inventory_tables=derived.get(name, ("NONE",)),
            not_evaluated_reason=NOT_EVALUATED_CLASS_REASONS.get(name),
        ))
    for addition in additions:
        name = addition["class"]
        # An addition is carried BECAUSE the engine has no path for it
        # (MoAffixProcess) or because nothing carries it (PhCode); it is still
        # gate-required, because that is the point of measuring it. Only the
        # three never-created classes are advisory (CP-3).
        engine_can_create = name not in NEVER_CREATED_CLASSES
        entries.append(ClassListEntry(
            object_class=name,
            in_class_list_via="census_additions",
            gate_scope=_gate_scope_for(name, engine_can_create),
            engine_can_create=engine_can_create,
            inventory_tables=derived.get(name, ("NONE",)),
            not_evaluated_reason=NOT_EVALUATED_CLASS_REASONS.get(name),
        ))
    for name, _reason in excluded:
        # Abstract LCM bases with no factory. Reported, never measured, and
        # never omitted: an absent row is indistinguishable from a class the
        # census forgot.
        entries.append(ClassListEntry(
            object_class=name,
            in_class_list_via="excluded_not_measurable",
            gate_scope="advisory",
            engine_can_create=False,
            inventory_tables=derived.get(name, ("NONE",)),
            not_evaluated_reason=NOT_EVALUATED_CLASS_REASONS.get(
                name, "ABSENT_BY_CONSTRUCTION"),
        ))

    required_count = sum(
        1 for e in entries
        if e.in_class_list_via in ("coverage_floor", "census_additions")
    )
    if required_count != REQUIRED_CLASS_COUNT:
        raise CoverageIncomplete(
            "the derived required class count is " + str(required_count)
            + ", not the " + str(REQUIRED_CLASS_COUNT) + " of "
            "fidelity-census.md 3.2 (" + str(len(in_scope)) + " floor + "
            + str(len(addition_names)) + " additions) -- a change in either "
            "truth source must be a deliberate edit to REQUIRED_CLASS_COUNT "
            "as well, so coverage cannot drift silently",
            tuple(sorted(set(in_scope) | set(addition_names))),
        )

    provenance = {
        "inventory_document": INVENTORY_DOCUMENT,
        "inventory_sha256": sha256_of(inventory_path),
        "coverage_floor_document": COVERAGE_FLOOR_DOCUMENT,
        "coverage_floor_sha256": sha256_of(floor_path),
        "census_additions": [dict(a) for a in additions],
        "excluded_not_measurable": [
            {"class": name, "reason": reason} for name, reason in excluded
        ],
        "in_scope_class_count": len(in_scope),
    }
    if roster_path.is_file():
        provenance["natural_key_roster_document"] = NATURAL_KEY_ROSTER_DOCUMENT
        provenance["natural_key_roster_sha256"] = sha256_of(roster_path)

    return ClassList(
        entries=tuple(entries),
        derivation_check=derivation_check,
        provenance=provenance,
    )


def class_list_provenance_artifact(class_list: ClassList) -> dict:
    """-> artifact `class_list_provenance`.

    `required_class_count` is the ROW count so invariant 1 (`len(classes) ==
    required_class_count`) holds by construction.
    """
    block = dict(class_list.provenance)
    block["derivation_check"] = dict(class_list.derivation_check)
    block["required_class_count"] = class_list.required_class_count
    return block


# ---------------------------------------------------------------------------
# T018 places the A1 seam here; declared now so `ClassListEntry.row_key` can
# reference it without a forward-declaration dance.
# ---------------------------------------------------------------------------


def split_class_label(object_class: str, owner: str) -> str:
    """PROVISIONAL (A1): the row label for a class split by owning collection.

    The two candidate encodings are documented at `A1_OWNER_ENCODING` below --
    this string form ("class_string") needs no contract edit but is unvalidated;
    the alternative adds `owning_feature_system` to `$defs.classRow`. Every
    emission goes through `encode_split_owner`, which is the one seam that
    chooses.
    """
    return object_class + "(" + owner + ")"


# ===========================================================================
# T017 -- the READ-ONLY counting pass
#
# READ-ONLY, WITHOUT EXCEPTION (fidelity-census.md section 2). Both projects
# are opened `writeEnabled=False`, the `.fwdata` digest is taken before and
# after, and a digest that MOVED is `CENSUS_ERROR` -- not a warning, not a
# note. `Ejagham Mini`, `Esperanto` and `Mbugwe LizzieHC practice` are
# read-only test projects, and the digest pair is the evidence that they stayed
# that way. `$defs.projectRef.opened_read_only` is `const: true`, so a census
# that opened a write handle cannot produce a valid artifact at all.
#
# AN UNRESOLVED ACCESSOR IS A REPORTED OUTCOME, NEVER A SKIP.
# `tests/integration/harness/full_run.py:230` is the precedent to avoid: its
# counting loop does `except Exception: continue`, so a renamed accessor turns
# into a silently absent number and the harness reports success over it. Here a
# class whose repository cannot be resolved lands in `unresolved_accessors`,
# becomes an `errors[]` entry with the class named, and drives the run to
# CENSUS_ERROR. The census may fail to measure a class; it may not fail
# QUIETLY.
# ===========================================================================

#: Where FLEx projects live when no root is supplied. The same literal
#: `Lib/api.py` defaults to, so the census and the transfer cannot disagree
#: about where a project is.
DEFAULT_PROJECTS_ROOT = r"C:\ProgramData\SIL\FieldWorks\Projects"

#: `<languageproject version="7000072">` on the second line of every `.fwdata`.
_DATA_MODEL_VERSION_RE = re.compile(rb'<languageproject\s+version="(\d+)"')

#: Process-wide latch for `FLExInitialize()`; see `_ensure_flex_initialized`.
_FLEX_INITIALIZED = False


def _ensure_flex_initialized() -> None:
    """Call `flexicon.FLExInitialize()` exactly once per process.

    A non-FlexTools-host process MUST initialise the FieldWorks libraries
    before any `OpenProject`; skipping it surfaces as
    `RegistryHelper.get_CompanyKey()` throwing `ArgumentNullException` on the
    first open. The import is function-level on purpose -- see this module's
    docstring on why nothing here may touch FieldWorks at import time.
    """
    global _FLEX_INITIALIZED
    if _FLEX_INITIALIZED:
        return
    from flexicon import FLExInitialize  # noqa: PLC0415 -- see module docstring

    FLExInitialize()
    _FLEX_INITIALIZED = True


def fwdata_path_for(
    project_name: str,
    projects_root: Optional[str] = None,
    handle=None,
) -> Path:
    """The `.fwdata` file whose digest proves the census wrote nothing.

    Prefers the OPEN handle's own `ProjectId.Path` (the accessor
    `Lib/config_views.py` and `Lib/api.py` already use), because that is the
    file LCM actually has open rather than a guess from the project name.
    Falls back to `<root>/<name>/<name>.fwdata`, research R5's definition of
    what a FLEx project looks like on disk.
    """
    if handle is not None:
        try:
            candidate = str(handle.project.ProjectId.Path)
        except Exception:  # noqa: BLE001 -- fake handles / API drift
            candidate = ""
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    root = projects_root or DEFAULT_PROJECTS_ROOT
    return Path(root) / project_name / (project_name + ".fwdata")


def read_data_model_version(fwdata: Path) -> Optional[int]:
    """The `.fwdata` header's data-model version, or None when unreadable.

    Read from the file rather than from the cache because it is needed BEFORE
    and AFTER the open, and because baseline staleness is judged against it
    (fidelity-census.md 5.3): a destination whose `data_model_version` exceeds
    the baseline's makes the baseline stale.
    """
    try:
        with open(fwdata, "rb") as handle:
            head = handle.read(4096)
    except OSError:
        return None
    found = _DATA_MODEL_VERSION_RE.search(head)
    return int(found.group(1)) if found else None


# ---------------------------------------------------------------------------
# Per-class counts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ClassCounts:
    """One project's per-class instance counts, plus what could NOT be counted.

    `counts` holds only classes that were actually measured. A class the census
    could not measure is in `unmeasurable` and its reason is in
    `unresolved_accessors` -- it is never silently absent from `counts` and
    never defaulted to zero, because zero is a positive claim ("this project
    holds none of these") and an unresolved accessor supports no claim at all.
    """

    project_name: str
    counts: dict
    unmeasurable: tuple = ()
    unresolved_accessors: Optional[dict] = None
    object_count_total: Optional[int] = None

    def __post_init__(self) -> None:
        if self.unresolved_accessors is None:
            object.__setattr__(self, "unresolved_accessors", {})
        missing = tuple(
            name for name in self.unmeasurable
            if name not in self.unresolved_accessors
        )
        if missing:
            raise CensusError(
                "these classes are unmeasurable with no recorded reason: "
                + ", ".join(sorted(missing))
                + " -- an unmeasurable class must say WHY, or it is "
                "indistinguishable from a class the census forgot",
                missing,
            )
        both = tuple(sorted(set(self.counts) & set(self.unmeasurable)))
        if both:
            raise CensusError(
                "these classes are both counted and unmeasurable: "
                + ", ".join(both),
                both,
            )

    def count_for(self, object_class: str) -> Optional[int]:
        """The count for one class, or None when it could not be measured.

        None is `unmeasurable`, NOT zero. The caller must report it rather than
        subtract it.
        """
        return self.counts.get(object_class)

    @property
    def is_complete(self) -> bool:
        """True when every requested class yielded a number."""
        return not self.unmeasurable


def _repository_interface(object_class: str):
    """The `SIL.LCModel.I<Class>Repository` interface, or None when absent.

    LCM generates one repository per class, so this resolves for every class in
    the roster; returning None rather than raising lets the caller record an
    `unresolved_accessors` entry naming the class instead of aborting the whole
    pass on one drifted name.
    """
    import SIL.LCModel as lcm  # noqa: PLC0415 -- see module docstring

    return getattr(lcm, "I" + object_class + "Repository", None)


def count_classes(handle, class_names, *, project_name: str = "") -> ClassCounts:
    """Count each class ONCE against an open, read-only project handle.

    One `repository.Count` read per class -- no per-object enumeration and no
    per-object re-query, which is what makes the pass affordable over the 74
    rows of a real project. `handle.ObjectCountFor(iface)` is flexicon's own
    accessor for exactly this (`FLExProject.ObjectCountFor` ->
    `ServiceLocator.GetService(repository).Count`).

    Every failure mode is recorded and named: a missing repository interface, a
    service locator that returns nothing, a raising accessor, and a count that
    is not an integer are four distinct `unresolved_accessors` reasons.
    """
    requested = tuple(dict.fromkeys(class_names))
    counts: dict = {}
    unresolved: dict = {}

    for name in requested:
        iface = _repository_interface(name)
        if iface is None:
            unresolved[name] = (
                "SIL.LCModel exposes no I" + name + "Repository -- the class "
                "was renamed, removed, or is not a first-class LCM class"
            )
            continue
        try:
            value = handle.ObjectCountFor(iface)
        except Exception as exc:  # noqa: BLE001 -- LCM raises many types
            unresolved[name] = (
                "I" + name + "Repository resolved but counting raised "
                + type(exc).__name__ + ": " + str(exc)
            )
            continue
        if value is None:
            unresolved[name] = (
                "the service locator returned no I" + name + "Repository"
            )
            continue
        try:
            counts[name] = int(value)
        except (TypeError, ValueError):
            unresolved[name] = (
                "I" + name + "Repository.Count is not an integer: "
                + repr(value)
            )

    total: Optional[int] = None
    try:
        import SIL.LCModel as lcm  # noqa: PLC0415

        repo = handle.ObjectRepository(lcm.ICmObjectRepository)
        total = int(repo.Count) if repo is not None else None
    except Exception:  # noqa: BLE001 -- advisory figure only
        total = None

    return ClassCounts(
        project_name=project_name or str(getattr(handle, "ProjectName", "")),
        counts=counts,
        unmeasurable=tuple(sorted(unresolved)),
        unresolved_accessors=unresolved,
        object_count_total=total,
    )


def objects_in_class(handle, object_class: str) -> list:
    """Every instance of one class, enumerated ONCE.

    T018's duplicate grouping is the only caller: grouping by natural key needs
    the objects themselves, not just their number. Raises `CensusError` rather
    than yielding nothing when the class cannot be enumerated, so a duplicate
    count of 0 always means "measured, and none" and never "could not look".
    """
    iface = _repository_interface(object_class)
    if iface is None:
        raise CensusError(
            "cannot enumerate " + repr(object_class)
            + ": SIL.LCModel exposes no I" + object_class + "Repository",
            (object_class,),
        )
    try:
        return list(handle.ObjectsIn(iface))
    except Exception as exc:  # noqa: BLE001
        raise CensusError(
            "cannot enumerate " + repr(object_class) + ": "
            + type(exc).__name__ + ": " + str(exc),
            (object_class,),
        ) from exc


# ---------------------------------------------------------------------------
# One project's reading
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProjectCensusReading:
    """-> artifact `projects.source` / `projects.destination`.

    `opened_read_only` is not stored: it is emitted as the literal `True` the
    schema pins as `const`, and it is true because `read_project` is the only
    way to build one of these and it passes `writeEnabled=False`. A caller who
    counted through a write handle has no way to express that here, which is
    the intended shape.
    """

    name: str
    path: str
    counted_at: str
    fwdata_sha256_before: str
    fwdata_sha256_after: str
    counts: ClassCounts
    data_model_version: Optional[int] = None
    declared_freshly_created: Optional[bool] = None

    @property
    def digest_unchanged(self) -> bool:
        """Invariant 7's per-project half: the census wrote nothing."""
        return self.fwdata_sha256_before == self.fwdata_sha256_after

    def artifact(self) -> dict:
        """The `$defs.projectRef` block."""
        block = {
            "name": self.name,
            "path": self.path,
            "opened_read_only": True,
            "counted_at": self.counted_at,
            "fwdata_sha256_before": self.fwdata_sha256_before,
            "fwdata_sha256_after": self.fwdata_sha256_after,
        }
        if self.data_model_version is not None:
            block["data_model_version"] = self.data_model_version
        if self.declared_freshly_created is not None:
            block["declared_freshly_created"] = self.declared_freshly_created
        if self.counts.object_count_total is not None:
            block["object_count_total"] = self.counts.object_count_total
        return block


def _now_iso() -> str:
    """`counted_at` / `generated_at`, second resolution, ISO-8601."""
    import datetime  # noqa: PLC0415 -- keeps the import surface uniform

    return datetime.datetime.now().replace(microsecond=0).isoformat()


def read_project(
    project_name: str,
    class_names,
    *,
    projects_root: Optional[str] = None,
    declared_freshly_created: Optional[bool] = None,
    open_project=None,
) -> ProjectCensusReading:
    """Open one project READ-ONLY, count every class once, and prove no write.

    The digest is taken before the open and again after the CLOSE, because a
    write LCM only flushes on `CloseProject()` would not show up in a digest
    taken while the handle is still open. A digest that moved raises
    `CensusError` (verdict `CENSUS_ERROR`, exit 7): the census's whole claim to
    be a safe instrument rests on that comparison, so it is the feature, not a
    formality.

    `open_project` is an injection seam -- it must accept `(project_name)` and
    return a handle whose `ObjectCountFor` works. The default opens a real
    flexicon handle with `writeEnabled=False`.
    """
    fwdata = fwdata_path_for(project_name, projects_root)
    if not fwdata.is_file():
        raise CensusError(
            "no .fwdata for project " + repr(project_name) + " at "
            + str(fwdata) + " -- the census cannot prove it wrote nothing to a "
            "file it cannot digest"
        )
    before = sha256_of(fwdata)
    model_version = read_data_model_version(fwdata)
    counted_at = _now_iso()
    resolved = fwdata

    handle = None
    try:
        if open_project is not None:
            handle = open_project(project_name)
        else:
            from flexicon import FLExProject  # noqa: PLC0415

            _ensure_flex_initialized()
            handle = FLExProject()
            handle.OpenProject(projectName=project_name, writeEnabled=False)
        resolved = fwdata_path_for(project_name, projects_root, handle)
        counts = count_classes(handle, class_names, project_name=project_name)
    except CensusFailure:
        raise
    except Exception as exc:  # noqa: BLE001 -- LCM raises many types
        raise CensusError(
            "could not open " + repr(project_name) + " read-only for counting: "
            + type(exc).__name__ + ": " + str(exc)
        ) from exc
    finally:
        if handle is not None:
            try:
                handle.CloseProject()
            except Exception:  # noqa: BLE001 -- nothing was written to lose
                pass

    after = sha256_of(fwdata)
    if before != after:
        raise CensusError(
            "the .fwdata digest for " + repr(project_name) + " CHANGED under "
            "the census (" + before[:12] + "... -> " + after[:12] + "...) at "
            + str(fwdata) + " -- the census is read-only without exception "
            "(fidelity-census.md section 2), so a moved digest invalidates the "
            "whole run rather than one row"
        )

    return ProjectCensusReading(
        name=project_name,
        path=str(Path(resolved).parent),
        counted_at=counted_at,
        fwdata_sha256_before=before,
        fwdata_sha256_after=after,
        counts=counts,
        data_model_version=model_version,
        declared_freshly_created=declared_freshly_created,
    )


def projects_artifact(
    source: ProjectCensusReading, destination: ProjectCensusReading,
) -> dict:
    """-> artifact `projects`. Both readings, both digest pairs."""
    return {
        "source": source.artifact(),
        "destination": destination.artifact(),
    }


def unmeasurable_errors(*readings) -> tuple:
    """-> artifact `errors[]` entries, one per unresolved accessor.

    EMITTED, not logged. The `errors` array is what carries an unresolved
    accessor to its reader, and `recompute_verdict` treats a non-empty `errors`
    array as CENSUS_ERROR, so the failure cannot be read as a pass.
    """
    out = []
    for reading in readings:
        for name in reading.counts.unmeasurable:
            out.append({
                "code": "UNHANDLED_EXCEPTION",
                "message": (
                    "class " + name + " could not be counted in project "
                    + reading.name + "; the census makes no claim about it"
                ),
                "class": name,
                "evidence": reading.counts.unresolved_accessors[name],
            })
    return tuple(out)


# ===========================================================================
# T018 -- duplicate natural-key grouping, and Amendment A1's FsFeatStrucType
#        split by owning feature system
#
# WHY DUPLICATES ARE NOT OPTIONAL (fidelity-census.md section 6). A class row
# passes only when BOTH `difference == 0` (or every unit accounted) AND
# `duplicates.extra_objects == 0` (or each group accounted). The measured
# phoneme row is the proof: source 41, destination 64, starter 23, so
# 64 - 23 = 41 and `difference` is 0 -- on a run that had matched NONE of the
# 23 starter phonemes and created 41 beside them, with 21 duplicate names. The
# FIXED run gives the same 0. Baseline arithmetic cannot tell those two apart;
# grouping by natural key can, and is what makes this a gate for SC-002 rather
# than only for SC-005.
#
# COMPARISON STRICTNESS. Exact, case-sensitive, NO Unicode normalisation, NO
# case folding, NO whitespace trimming -- `Nasals`, `nasals` and
# `Nasal Consonants` were measured as three distinct natural classes. An object
# with no name in the scoped writing system has NO KEY and is excluded from
# grouping entirely: an empty key must never match another empty key, so two
# unnamed objects are not duplicates of each other.
# ===========================================================================

#: Writing-system scope tokens. The scope differs BY CLASS and in opposite
#: directions -- `PhPhoneme` keys on the default VERNACULAR (measured 97/97,
#: against only 44/97 in the analysis WS) while every other admitted class keys
#: on the default ANALYSIS WS -- so the scope is stored per class rather than
#: assumed once for all of them.
WS_SCOPE_VERNACULAR = "default_vernacular"
WS_SCOPE_ANALYSIS = "default_analysis"


@dataclass(frozen=True)
class NaturalKeyDefinition:
    """How one class's duplicate key is computed, and how it is described.

    `description` is emitted verbatim as `duplicates.key_definition`, so a
    reader of the artifact can tell WHICH key produced a duplicate group
    without reading this file. `roster_source` records which document admits the
    class, because admission to gate-failing duplicate detection is by roster
    enumeration only (FR-003's rule for matching, applied to duplicates).
    """

    object_class: str
    property_name: str
    ws_scope: str
    description: str
    roster_source: str = "roster_extension_038"

    def __post_init__(self) -> None:
        if self.ws_scope not in (WS_SCOPE_VERNACULAR, WS_SCOPE_ANALYSIS):
            raise CensusError(
                "NaturalKeyDefinition.ws_scope for "
                + repr(self.object_class) + " is " + repr(self.ws_scope)
            )


#: The classes whose duplicate keys the census can compute. Transcribed from
#: 035's `natural-key-identity-roster.json` (the three entries it already
#: carries) and 038's `natural-key-roster-extension.json` (the six proposed by
#: FR-005). A class absent from this table gets NO `duplicates` block rather
#: than an `extra_objects: 0` block, because 0 would claim the census looked.
NATURAL_KEY_DEFINITIONS: dict = {
    "PhPhoneme": NaturalKeyDefinition(
        "PhPhoneme", "Name", WS_SCOPE_VERNACULAR,
        "Name (default vernacular alt), exact and case-sensitive",
    ),
    "PhNCSegments": NaturalKeyDefinition(
        "PhNCSegments", "Name", WS_SCOPE_ANALYSIS,
        "Name (default analysis alt), exact and case-sensitive, within the "
        "PhPhonData natural-class list and restricted to PhNCSegments",
    ),
    "PhNCFeatures": NaturalKeyDefinition(
        "PhNCFeatures", "Name", WS_SCOPE_ANALYSIS,
        "Name (default analysis alt), exact and case-sensitive, within the "
        "PhPhonData natural-class list and restricted to PhNCFeatures",
    ),
    "PartOfSpeech": NaturalKeyDefinition(
        "PartOfSpeech", "Name", WS_SCOPE_ANALYSIS,
        "Name (default analysis alt), exact and case-sensitive, project-wide "
        "over the recursive hierarchy; the owning parent is NOT part of the key",
    ),
    "MoMorphType": NaturalKeyDefinition(
        "MoMorphType", "Name", WS_SCOPE_ANALYSIS,
        "Name (default analysis alt), exact and case-sensitive, within the "
        "lexicon's morph-types list",
    ),
    "LexEntryInflType": NaturalKeyDefinition(
        "LexEntryInflType", "Name", WS_SCOPE_ANALYSIS,
        "Name (default analysis alt), exact and case-sensitive, within the "
        "variant-entry-types list and restricted to LexEntryInflType",
    ),
    "WfiWordform": NaturalKeyDefinition(
        "WfiWordform", "Form", WS_SCOPE_VERNACULAR,
        "Form (default vernacular alt), exact and case-sensitive",
        roster_source="natural_key_identity_roster_035",
    ),
}


def roster_admitted_classes(root: Optional[Path] = None) -> frozenset:
    """The classes 035's roster ADMITS, read at run time.

    Admission is what makes a duplicate group able to FAIL the gate. A duplicate
    name on an unadmitted class is surfaced as advisory instead, because
    homographs are legitimate content and the roster -- not this file -- decides
    which classes have a key. Reading the file rather than hard-coding the three
    current entries means the six entries feature 038 proposes (T028) become
    gate-failing the moment 035 merges them, with no edit here.
    """
    base = repo_root() if root is None else Path(root)
    path = base / NATURAL_KEY_ROSTER_DOCUMENT
    if not path.is_file():
        return frozenset()
    data = json.loads(path.read_text(encoding="utf-8"))
    return frozenset(
        entry["class"] for entry in data.get("entries", ())
        if entry.get("class")
    )


def _ws_handle_for(handle, ws_scope: str):
    """The writing-system handle one key scope names, or None.

    None means the key is NOT COMPUTABLE for this project, which the caller must
    report -- never silently fall back to another writing system. Matching a
    secondary vernacular would have fabricated 16 matches on `Yi Sichuan`
    alone (the roster's measured counterexample).
    """
    getter = (
        "GetDefaultVernacularWSHandle" if ws_scope == WS_SCOPE_VERNACULAR
        else "GetDefaultAnalysisWSHandle"
    )
    method = getattr(handle, getter, None)
    if callable(method):
        try:
            return method()
        except Exception:  # noqa: BLE001
            return None
    cache = getattr(handle, "Cache", None)
    attr = "DefaultVernWs" if ws_scope == WS_SCOPE_VERNACULAR else "DefaultAnalWs"
    return getattr(cache, attr, None)


def natural_key_of(obj, definition: NaturalKeyDefinition, ws_handle) -> Optional[str]:
    """One object's natural key, or None when it HAS no key.

    Exact string, taken from the named property's alt in the scoped writing
    system. Returned unchanged: no `.strip()`, no `.casefold()`, no
    `unicodedata.normalize`. None (no such property, no alt, empty alt) means
    the object has no key and must not be grouped -- an empty key never matches
    another empty key.
    """
    if ws_handle is None:
        return None
    prop = getattr(obj, definition.property_name, None)
    if prop is None:
        return None
    try:
        alt = prop.get_String(ws_handle)
    except Exception:  # noqa: BLE001 -- not a multistring on this subclass
        alt = None
    text = getattr(alt, "Text", None)
    if text is None:
        return None
    text = str(text)
    return text if text else None


@dataclass(frozen=True)
class DuplicateReport:
    """-> artifact `$defs.duplicates` for one class row.

    `groups` counts keys held by MORE THAN ONE destination object;
    `extra_objects` is `sum(group_size - 1)` over those groups -- the number of
    objects that would not exist if matching had worked. `examples` is NEVER
    truncated (invariant 2): truncation is legal only in the console summary,
    which must state how many items it omitted.
    """

    object_class: str
    roster_admitted: bool
    key_definition: str
    groups: int
    extra_objects: int
    examples: tuple = ()

    def __post_init__(self) -> None:
        for name in ("groups", "extra_objects"):
            if getattr(self, name) < 0:
                raise CensusError(
                    "DuplicateReport." + name + " must be >= 0 on class "
                    + repr(self.object_class)
                )
        if self.groups and not self.extra_objects:
            raise CensusError(
                "DuplicateReport for " + repr(self.object_class) + " claims "
                + str(self.groups) + " duplicate groups but 0 extra objects -- "
                "a group of size > 1 contributes at least one extra object"
            )

    def artifact(self) -> dict:
        block = {
            "roster_admitted": self.roster_admitted,
            "key_definition": self.key_definition,
            "groups": self.groups,
            "extra_objects": self.extra_objects,
            "examples": [dict(e) for e in self.examples],
        }
        return block


def group_by_natural_key(objects, definition: NaturalKeyDefinition, ws_handle) -> dict:
    """`{key: [objects]}` over the objects that HAVE a key, insertion-ordered.

    Objects with no key are omitted rather than collected under a shared
    sentinel, which is the whole point: two unnamed phonemes are two unnamed
    phonemes, not a duplicate pair.
    """
    grouped: dict = {}
    for obj in objects:
        key = natural_key_of(obj, definition, ws_handle)
        if key is None:
            continue
        grouped.setdefault(key, []).append(obj)
    return grouped


def _guid_str(obj) -> str:
    try:
        return str(obj.Guid)
    except Exception:  # noqa: BLE001
        return ""


def duplicate_report(
    object_class: str,
    objects,
    *,
    ws_handle,
    definition: Optional[NaturalKeyDefinition] = None,
    roster_admitted: bool = False,
) -> Optional[DuplicateReport]:
    """Group one class's destination objects by natural key and count the extras.

    Returns None when the class has no key definition at all -- the honest
    answer, because an `extra_objects: 0` block would claim a measurement that
    never happened.
    """
    spec = definition or NATURAL_KEY_DEFINITIONS.get(object_class)
    if spec is None:
        return None
    grouped = group_by_natural_key(objects, spec, ws_handle)
    examples = []
    groups = 0
    extra = 0
    for key, members in grouped.items():
        if len(members) < 2:
            continue
        groups += 1
        extra += len(members) - 1
        examples.append({
            "key": key,
            "count": len(members),
            "guids": [g for g in (_guid_str(m) for m in members) if g],
        })
    return DuplicateReport(
        object_class=object_class,
        roster_admitted=roster_admitted,
        key_definition=spec.description,
        groups=groups,
        extra_objects=extra,
        examples=tuple(examples),
    )


def duplicate_reports_for(
    handle,
    class_names,
    *,
    admitted: Optional[frozenset] = None,
    objects_for=None,
) -> dict:
    """`{class: DuplicateReport}` for every class that has a key definition.

    `objects_for(handle, class_name)` is the enumeration seam; it defaults to
    `objects_in_class`, which enumerates each class exactly ONCE and raises
    rather than returning an empty list when the class cannot be enumerated.
    """
    admitted_set = (
        roster_admitted_classes() if admitted is None else admitted
    )
    enumerate_objects = objects_for or objects_in_class
    handles: dict = {}
    out: dict = {}
    for name in dict.fromkeys(class_names):
        spec = NATURAL_KEY_DEFINITIONS.get(name)
        if spec is None:
            continue
        if spec.ws_scope not in handles:
            handles[spec.ws_scope] = _ws_handle_for(handle, spec.ws_scope)
        report = duplicate_report(
            name,
            enumerate_objects(handle, name),
            ws_handle=handles[spec.ws_scope],
            definition=spec,
            roster_admitted=name in admitted_set,
        )
        if report is not None:
            out[name] = report
    return out


# ---------------------------------------------------------------------------
# Amendment A1 -- `FsFeatStrucType` is counted PER FEATURE SYSTEM
#
# A FieldWorks project has TWO feature systems, and both own
# `FsFeatStrucType`: `LangProject.MsFeatureSystemOA` (morphosyntactic) and
# `LangProject.PhFeatureSystemOA` (phonological). A single summed row is
# ambiguous, because a shortfall in one system is masked by a surplus in the
# other -- the same masking defect section 6 rule 2 exists to prevent for
# duplicate identity. Each part is evaluated INDEPENDENTLY against section 9.
#
# ####################################################################
# # PROVISIONAL (A1): THE OWNER ENCODING IS NOT SETTLED.             #
# ####################################################################
# `fidelity-census.md:650-673` requires the row to "carry the owner", but
# `$defs.classRow` is `additionalProperties: false` with `class` as a bare
# string and NO owner property. Two encodings are possible and exactly one seam
# below decides between them:
#
#   1. "class_string"  -- `class: "FsFeatStrucType(MsFeatureSystem)"`.
#      Needs no contract edit, validates today, but NOTHING checks the owner:
#      it is an unvalidated convention inside a string, and a consumer
#      splitting on class name sees two unknown classes.
#   2. "row_property"  -- add `owning_feature_system` to `$defs.classRow`.
#      Validated, self-describing, and additive under the schema's own
#      EVOLUTION RULE (a new OPTIONAL property) -- but it EDITS A CONTRACT
#      under `specs/`, which this task is not permitted to do.
#
# "class_string" is the provisional default so the suite can run. Switching is
# one constant: set `A1_OWNER_ENCODING = "row_property"`. RECOMMENDATION is
# recorded in the T018 journal entry; the orchestrator settles it.
# ---------------------------------------------------------------------------

#: The A1 seam. `"class_string"` (provisional) or `"row_property"`.
A1_OWNER_ENCODING = "class_string"

#: The two owning feature systems, in `LangProject` attribute order.
FEATURE_SYSTEM_OWNERS: tuple = ("MsFeatureSystem", "PhFeatureSystem")

#: `LangProject` attribute per owner token.
FEATURE_SYSTEM_ATTRS: dict = {
    "MsFeatureSystem": "MsFeatureSystemOA",
    "PhFeatureSystem": "PhFeatureSystemOA",
}

#: Classes reachable from BOTH feature systems, which A1 therefore splits. A1's
#: closing sentence extends the requirement to "any other class reachable from
#: both feature systems", so this is a set rather than a single class name.
FEATURE_SYSTEM_SPLIT_CLASSES: frozenset = frozenset({"FsFeatStrucType"})


def encode_split_owner(row: dict, object_class: str, owner: Optional[str]) -> dict:
    """THE A1 SEAM. Put the owning feature system into an emitted class row.

    Every A1-aware emission goes through here, so the encoding is decided in
    exactly one place. See the PROVISIONAL block above for the two options and
    why the string form is the current default.
    """
    if owner is None:
        row["class"] = object_class
        return row
    if A1_OWNER_ENCODING == "row_property":
        # Requires `owning_feature_system` on `$defs.classRow`. Until that
        # property exists the artifact is additionalProperties:false and this
        # branch produces an INVALID document -- deliberately, rather than
        # silently degrading to the other encoding.
        row["class"] = object_class
        row["owning_feature_system"] = owner
        return row
    row["class"] = split_class_label(object_class, owner)
    return row


def split_feature_system_entries(class_list: ClassList) -> ClassList:
    """Expand each A1 class into one entry PER OWNING FEATURE SYSTEM.

    An accounting change only: the CP-1 required class count is untouched (A1's
    own words -- it "adds no class to the required list"), because both parts
    carry the same `object_class`. `ClassList.required_classes` therefore still
    reports `FsFeatStrucType` twice for one class, while `row_key` keeps the two
    rows distinct so neither can be summed into the other.
    """
    entries = []
    for entry in class_list.entries:
        if (entry.object_class not in FEATURE_SYSTEM_SPLIT_CLASSES
                or entry.owning_feature_system is not None):
            entries.append(entry)
            continue
        for owner in FEATURE_SYSTEM_OWNERS:
            entries.append(ClassListEntry(
                object_class=entry.object_class,
                in_class_list_via=entry.in_class_list_via,
                gate_scope=entry.gate_scope,
                engine_can_create=entry.engine_can_create,
                inventory_tables=entry.inventory_tables,
                not_evaluated_reason=entry.not_evaluated_reason,
                owning_feature_system=owner,
            ))
    return ClassList(
        entries=tuple(entries),
        derivation_check=dict(class_list.derivation_check),
        provenance=dict(class_list.provenance),
    )


def count_by_feature_system(handle, object_class: str) -> dict:
    """`{owner: count}` for one A1 class, counted through each owning system.

    Counted from `LangProject.<system>OA.TypesOC` rather than from the class
    repository, because the repository total is exactly the ambiguous summed
    figure A1 forbids. An owning system that is absent counts 0 -- a project
    with no phonological feature system genuinely owns no phonological types,
    which is a measurement and not an unresolved accessor.
    """
    counts: dict = {}
    lang_project = getattr(handle, "lp", None)
    if lang_project is None:
        lang_project = getattr(getattr(handle, "project", None),
                               "LangProject", None)
    for owner in FEATURE_SYSTEM_OWNERS:
        system = getattr(lang_project, FEATURE_SYSTEM_ATTRS[owner], None)
        if system is None:
            counts[owner] = 0
            continue
        types = getattr(system, "TypesOC", None)
        if types is None:
            counts[owner] = 0
            continue
        try:
            counts[owner] = int(types.Count)
        except Exception as exc:  # noqa: BLE001
            raise CensusError(
                "cannot count " + object_class + " under "
                + FEATURE_SYSTEM_ATTRS[owner] + ": " + type(exc).__name__
                + ": " + str(exc) + " -- A1 requires the two feature systems "
                "to be counted separately, and a summed fallback is exactly "
                "the ambiguity it forbids",
                (object_class,),
            ) from exc
    return counts


# ===========================================================================
# T019 -- the accounting arithmetic, and the artifact emitter
#
# THE THREE COUNTS AND THE SIGN CONVENTION (fidelity-census.md 4, 5.2, 7):
#
#     unmatched_starter     = starter_baseline_count - starter_matched_to_source
#     destination_count_net = destination_count_total - unmatched_starter
#     difference            = destination_count_net - source_count
#     difference_raw        = destination_count_total - source_count
#
#     difference <  0  SHORTFALL   difference == 0  MATCHED   > 0  SURPLUS
#
# The subtrahend is the starter objects NOT matched to a source object, never
# the gross baseline. Gross subtraction is wrong the moment natural-key
# matching works: on the fixed phoneme run (source 41, destination 43, starter
# 23 of which 21 matched) gross gives 43 - 23 = 20 and reports -21, a shortfall
# on a CORRECT run. Matched gives 43 - 2 = 41, difference 0.
#
# NO CROSS-CLASS NETTING, EVER. Every function here takes ONE row's numbers.
# There is deliberately no signature anywhere in this module that can see two
# classes' differences at once, and `build_totals` reports `total_shortfall` and
# `total_surplus` separately and never sums them: Ejagham's MoAffixProcess
# 13 -> 0 and MoAffixAllomorph +13 are the SAME defect seen twice, and netting
# them to zero is precisely the SC-010 failure this feature exists to end.
#
# WHAT THIS TASK HAD TO SUPPLY ITSELF (T015's open disagreement 1).
# `$defs.classRow` REQUIRES 13 keys; `models.ClassCensusRow` has 9, and four of
# the required keys are not functions of those 9. Resolution:
#   * `gate_scope`, `in_class_list_via` (+ optional `inventory_tables`) come
#     from T016's `ClassListEntry`, carried through -- the loader is the only
#     thing that actually knows CP-3's advisory marking and CP-4's provenance,
#     so re-deciding them at emission time would be a second source of truth.
#   * `accounted_for` is an EMITTER ARGUMENT (`AccountedLine` objects): the row
#     carries only reason TOKENS, never their counts, directions or report refs.
#   * `unexplained_shortfall` / `unexplained_surplus` are DERIVED here from the
#     difference and the lines by section 7's formula -- never passed in, so a
#     caller cannot understate them.
# `ClassCensusRow` itself is unchanged: it is `data-model.md`'s frozen shape and
# `models.py` is the wrong place for artifact-only provenance.
# ===========================================================================

#: Precedence for picking the ONE `not_evaluated_reason` out of a row's reason
#: TUPLE (T015's open disagreement 3: `data-model.md`:112 is a tuple, schema
#: `:427-430` is a single token). Most absolute first: a class that cannot exist
#: at all outranks one that is merely outside this feature's scope, which
#: outranks one another feature governs. Chosen against the named set
#: `CENSUS_NOT_EVALUATED_REASONS` so the choice is auditable rather than
#: incidental to tuple order.
NOT_EVALUATED_REASON_PRECEDENCE: tuple = (
    "ABSENT_BY_CONSTRUCTION",
    "OUT_OF_SCOPE_CLASS",
    "GOVERNED_BY_OTHER_FEATURE",
)

#: `$defs.accountedLine.direction`.
DIRECTIONS: tuple = ("shortfall", "surplus")

#: `$defs.classRow.starter_subtraction_basis`.
SUBTRACTION_BASES: tuple = ("baseline_matched", "baseline_gross", "no_baseline")

#: `$defs.classRow.starter_baseline_source`.
BASELINE_SOURCES: tuple = (
    "baseline_document", "absent_from_baseline", "assumed_zero_not_permitted",
)


def select_not_evaluated_reason(reasons) -> Optional[str]:
    """The ONE `not_evaluated_reason` for a row, or None when it was measured.

    `NOT_EVALUATED_REASON_PRECEDENCE` decides when a row carries more than one
    qualifying token; anything outside `CENSUS_NOT_EVALUATED_REASONS` is ignored
    here (a measured row's accounting reasons are not evaluation reasons).
    """
    present = {r for r in reasons if r in NOT_EVALUATED_REASONS}
    for token in NOT_EVALUATED_REASON_PRECEDENCE:
        if token in present:
            return token
    return None


# ---------------------------------------------------------------------------
# One accounting line
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReportRef:
    """-> `$defs.reportRef`. What makes a line resolvable to real content."""

    kind: str
    count_in_report: int
    run_id: str = ""
    report_path: str = ""
    record_ids: tuple = ()

    def artifact(self) -> dict:
        block = {"kind": self.kind, "count_in_report": self.count_in_report}
        if self.run_id:
            block["run_id"] = self.run_id
        if self.report_path:
            block["report_path"] = self.report_path
        if self.record_ids:
            block["record_ids"] = list(self.record_ids)
        return block


@dataclass(frozen=True)
class AccountedLine:
    """-> `$defs.accountedLine`. One claim against one direction of one class.

    R-1 is enforced AT CONSTRUCTION: every reason outside the four exempt tokens
    must carry a `report_ref` whose `count_in_report >= count`. A line with no
    resolvable report content is not accounting, so it cannot be built and then
    validated away -- the emitter never gets the chance to write one.
    """

    reason: str
    count: int
    direction: str
    report_ref: Optional[ReportRef] = None
    detail: str = ""

    def __post_init__(self) -> None:
        if self.reason not in REASON_TOKENS:
            raise CensusError(
                "accounting reason " + repr(self.reason) + " is outside the "
                "closed 16-token vocabulary -- there is no UNEXPLAINED and no "
                "OTHER token: unexplained is the ABSENCE of a line and cannot "
                "be laundered into one"
            )
        if self.direction not in DIRECTIONS:
            raise CensusError(
                "accounting direction " + repr(self.direction)
                + " must be 'shortfall' or 'surplus'"
            )
        if self.count < 1:
            raise CensusError(
                "an accounting line must claim at least 1 object, got "
                + repr(self.count) + " for reason " + repr(self.reason)
            )
        if self.reason in REASONS_NOT_REQUIRING_REPORT_REF:
            return
        if self.report_ref is None:
            raise CensusError(
                "reason " + repr(self.reason) + " requires a report_ref (R-1): "
                "only STARTER_CONTENT, ABSENT_BY_CONSTRUCTION, "
                "OUT_OF_SCOPE_CLASS and GOVERNED_BY_OTHER_FEATURE account "
                "without one"
            )
        if self.report_ref.count_in_report < self.count:
            raise CensusError(
                "accounting line for " + repr(self.reason) + " claims "
                + str(self.count) + " against a report naming only "
                + str(self.report_ref.count_in_report)
                + " -- a line that outruns its evidence is CENSUS_ERROR, not a "
                "pass (R-1)"
            )

    def artifact(self) -> dict:
        block = {
            "reason": self.reason,
            "count": self.count,
            "direction": self.direction,
        }
        if self.report_ref is not None:
            block["report_ref"] = self.report_ref.artifact()
        if self.detail:
            block["detail"] = self.detail
        return block


# ---------------------------------------------------------------------------
# The arithmetic. One row at a time, on purpose.
# ---------------------------------------------------------------------------


def unmatched_starter(
    starter_baseline_count: Optional[int],
    starter_matched_to_source: Optional[int],
) -> Optional[int]:
    """`starter_baseline_count - starter_matched_to_source`, or None.

    None when either input is unknown: with no baseline there is nothing to
    subtract, and with no run report the matched count cannot be known. Neither
    may be silently read as zero -- a zero baseline is a positive claim that the
    destination shipped empty (5.3), and a zero matched count is the broken run.
    """
    if starter_baseline_count is None:
        return None
    if starter_matched_to_source is None:
        return None
    return starter_baseline_count - starter_matched_to_source


def net_destination_count(
    destination_count_total: Optional[int], unmatched: Optional[int],
) -> Optional[int]:
    """`destination_count_total - unmatched_starter`.

    With `unmatched` None the net IS the total (5.2's `no_baseline` row: "net =
    total; the run cannot pass") -- the number is still reported, and the
    verdict, not the arithmetic, is what refuses to pass.
    """
    if destination_count_total is None:
        return None
    return destination_count_total - (unmatched or 0)


def signed_difference(
    destination_count_net: Optional[int], source_count: Optional[int],
) -> Optional[int]:
    """`destination_count_net - source_count`, the GATE quantity."""
    if destination_count_net is None or source_count is None:
        return None
    return destination_count_net - source_count


def row_verdict_class(
    difference: Optional[int], not_evaluated_reason: Optional[str] = None,
) -> str:
    """MATCHED / SHORTFALL / SURPLUS / NOT_EVALUATED.

    NOT_EVALUATED wins over the sign, and an unmeasurable count is
    NOT_EVALUATED rather than MATCHED: a row that was never measured must not be
    reported as agreeing because two numbers nobody trusts happen to be equal.
    """
    if not_evaluated_reason is not None or difference is None:
        return "NOT_EVALUATED"
    if difference == 0:
        return "MATCHED"
    return "SHORTFALL" if difference < 0 else "SURPLUS"


def accounted_in_direction(lines, direction: str) -> int:
    """`sum(count)` over the lines claiming ONE direction of ONE class.

    R-3: a shortfall line never offsets a surplus, and a line on one class never
    touches another. That rule is expressed as a signature: this function cannot
    be handed two classes' lines because the caller only ever holds one row's.
    """
    return sum(line.count for line in lines if line.direction == direction)


def unexplained_counts(difference: Optional[int], lines) -> tuple:
    """`(unexplained_shortfall, unexplained_surplus)` for one row.

        unexplained_shortfall = max(0, -difference) - sum(shortfall lines)
        unexplained_surplus   = max(0,  difference) - sum(surplus lines)

    Clamped at 0, because a NEGATIVE residue means over-accounting, which is
    R-2's `CENSUS_ERROR` and is detected by `validate_artifact` rather than
    hidden by being folded into an unexplained count.
    """
    if difference is None:
        return (0, 0)
    shortfall = max(0, -difference) - accounted_in_direction(lines, "shortfall")
    surplus = max(0, difference) - accounted_in_direction(lines, "surplus")
    return (max(0, shortfall), max(0, surplus))


def over_accounted_directions(difference: Optional[int], lines) -> tuple:
    """The directions whose accounting EXCEEDS the difference (R-2).

    Separate from `unexplained_counts` on purpose: over-accounting is a
    different failure from under-accounting and must not be clamped away. "The
    census must not be able to explain away more than actually happened."
    """
    if difference is None:
        return ()
    out = []
    if accounted_in_direction(lines, "shortfall") > max(0, -difference):
        out.append("shortfall")
    if accounted_in_direction(lines, "surplus") > max(0, difference):
        out.append("surplus")
    return tuple(out)


# ---------------------------------------------------------------------------
# Match-basis tallies (section 8, invariant 11)
# ---------------------------------------------------------------------------

#: The four tallies that must sum to `source_count`. `enriched` is deliberately
#: ABSENT: it is a SUBSET of `identity + natural_key` (an object can be matched
#: and then gain owned children), so including it would double-count every
#: enriched object and turn a correct run into a tally mismatch.
MATCH_BASIS_SUMMANDS: tuple = (
    "identity", "natural_key", "created_new", "unmatched_reported",
)


@dataclass(frozen=True)
class MatchBasis:
    """-> `$defs.matchBasis`. How each source object was accounted for.

    FR-006 requires every natural-key match to be distinguishable from an
    identity match, and this is where that distinction survives into the gate
    artifact instead of being report-only prose.
    """

    basis_source: str = "run_report"
    identity: Optional[int] = None
    natural_key: Optional[int] = None
    created_new: Optional[int] = None
    enriched: Optional[int] = None
    unmatched_reported: Optional[int] = None
    ambiguous_key_reported: Optional[int] = None

    def __post_init__(self) -> None:
        if self.basis_source not in ("run_report", "unavailable"):
            raise CensusError(
                "MatchBasis.basis_source must be 'run_report' or "
                "'unavailable', got " + repr(self.basis_source)
            )
        if self.basis_source == "unavailable":
            populated = tuple(
                name for name in (
                    "identity", "natural_key", "created_new", "enriched",
                    "unmatched_reported", "ambiguous_key_reported")
                if getattr(self, name) is not None
            )
            if populated:
                raise CensusError(
                    "MatchBasis(basis_source='unavailable') must leave every "
                    "tally null, but these are populated: "
                    + ", ".join(populated) + " -- with no run report the census "
                    "does not know them and must say so (section 8)"
                )

    @property
    def summed(self) -> Optional[int]:
        """`identity + natural_key + created_new + unmatched_reported`, or None
        when any summand is unknown. `enriched` is excluded."""
        values = [getattr(self, name) for name in MATCH_BASIS_SUMMANDS]
        if any(v is None for v in values):
            return None
        return sum(values)

    def sums_to(self, source_count: Optional[int]) -> bool:
        """Invariant 11, on a `required` row whose basis is `run_report`."""
        total = self.summed
        if total is None or source_count is None:
            return True
        return total == source_count

    def artifact(self) -> dict:
        block = {"basis_source": self.basis_source}
        for name in ("identity", "natural_key", "created_new", "enriched",
                     "unmatched_reported", "ambiguous_key_reported"):
            value = getattr(self, name)
            if value is not None:
                block[name] = value
        return block


def match_basis_sum_error(
    object_class: str, basis: Optional[MatchBasis], source_count: Optional[int],
    *, gate_scope: str = "required",
) -> Optional[str]:
    """The invariant-11 failure string for one row, or None when it holds.

    A MISMATCH IS A FAIL, not a note: it means the census's own account of what
    happened to each source object does not add up to the number of source
    objects, so no statement it makes about that class can be trusted.
    """
    if basis is None or gate_scope != "required":
        return None
    if basis.basis_source != "run_report":
        return None
    if basis.sums_to(source_count):
        return None
    return (
        object_class + ": match_basis identity + natural_key + created_new + "
        "unmatched_reported == " + str(basis.summed) + " but source_count is "
        + str(source_count) + " (enriched is a SUBSET of the matches and is "
        "excluded from the sum, section 8)"
    )


# ---------------------------------------------------------------------------
# Emitting one class row
# ---------------------------------------------------------------------------


def class_row_artifact(
    row,
    entry: ClassListEntry,
    *,
    accounted_for=(),
    starter_baseline_count: Optional[int] = None,
    starter_matched_to_source: Optional[int] = None,
    starter_subtraction_basis: Optional[str] = None,
    starter_baseline_source: Optional[str] = None,
    match_basis: Optional[MatchBasis] = None,
    duplicates: Optional[DuplicateReport] = None,
    notes=(),
) -> dict:
    """-> one `$defs.classRow`, from a `models.ClassCensusRow` plus its entry.

    DRIVEN BY THE TRANSLATION TABLE. The internal-to-artifact key mapping is
    read out of `models.CLASS_CENSUS_ROW_ARTIFACT_FIELDS`, where a `None` target
    means internal-only and MUST NOT be emitted; every object in the artifact is
    `additionalProperties: false`, so an extra key is a hard failure and not a
    harmless addition. Nothing here re-derives a name the table already states.
    """
    from .models import CLASS_CENSUS_ROW_ARTIFACT_FIELDS  # noqa: PLC0415

    block: dict = {}
    for internal, artifact_key in CLASS_CENSUS_ROW_ARTIFACT_FIELDS.items():
        if artifact_key is None:  # internal-only: never emitted
            continue
        block[artifact_key] = getattr(row, internal)

    # Derived properties on the row -- read, never recomputed, so the emitter
    # cannot arrive at a second answer.
    block["destination_count_net"] = row.destination_count_net
    block["difference_raw"] = row.difference_raw

    lines = tuple(accounted_for)
    not_evaluated_reason = select_not_evaluated_reason(row.reasons)
    if entry.not_evaluated_reason is not None:
        not_evaluated_reason = select_not_evaluated_reason(
            tuple(row.reasons) + (entry.not_evaluated_reason,))

    block["verdict_class"] = row_verdict_class(
        row.difference, not_evaluated_reason)
    if not_evaluated_reason is not None:
        block["not_evaluated_reason"] = not_evaluated_reason

    # The four required keys `ClassCensusRow` cannot supply (see the task
    # header): two carried from the class-list entry, one an argument, one
    # derived.
    block["gate_scope"] = entry.gate_scope
    block["in_class_list_via"] = entry.in_class_list_via
    if entry.inventory_tables:
        block["inventory_tables"] = list(entry.inventory_tables)
    block["accounted_for"] = [line.artifact() for line in lines]
    shortfall, surplus = unexplained_counts(row.difference, lines)
    if block["verdict_class"] == "NOT_EVALUATED":
        # A row that was not measured explains nothing and owes nothing.
        shortfall, surplus = 0, 0
    block["unexplained_shortfall"] = shortfall
    block["unexplained_surplus"] = surplus

    if starter_baseline_count is not None:
        block["starter_baseline_count"] = starter_baseline_count
    if starter_matched_to_source is not None:
        block["starter_matched_to_source"] = starter_matched_to_source
    if starter_subtraction_basis is not None:
        if starter_subtraction_basis not in SUBTRACTION_BASES:
            raise CensusError(
                "starter_subtraction_basis " + repr(starter_subtraction_basis)
                + " is outside the schema enum " + repr(SUBTRACTION_BASES)
            )
        block["starter_subtraction_basis"] = starter_subtraction_basis
    if starter_baseline_source is not None:
        if starter_baseline_source not in BASELINE_SOURCES:
            raise CensusError(
                "starter_baseline_source " + repr(starter_baseline_source)
                + " is outside the schema enum " + repr(BASELINE_SOURCES)
            )
        block["starter_baseline_source"] = starter_baseline_source
    if match_basis is not None:
        block["match_basis"] = match_basis.artifact()
    if duplicates is not None:
        block["duplicates"] = duplicates.artifact()
    if notes:
        block["notes"] = list(notes)

    # A1: the one seam that decides how a split row carries its owner.
    return encode_split_owner(
        block, entry.object_class, entry.owning_feature_system)


def build_totals(rows) -> dict:
    """-> artifact `totals`. Shortfall and surplus are NEVER summed together.

    `total_shortfall` and `total_surplus` are reported separately and there is
    deliberately no net figure anywhere in this block: a net of zero over
    MoAffixProcess -13 and MoAffixAllomorph +13 would report a run clean while a
    whole class changed kind (section 4).
    """
    required = [r for r in rows if r.get("gate_scope") == "required"]
    diffs = [r["difference"] for r in required if r.get("difference") is not None]
    totals = {
        "classes_reported": len(rows),
        "classes_matched": sum(
            1 for r in rows if r.get("verdict_class") == "MATCHED"),
        "classes_shortfall": sum(
            1 for r in rows if r.get("verdict_class") == "SHORTFALL"),
        "classes_surplus": sum(
            1 for r in rows if r.get("verdict_class") == "SURPLUS"),
        "classes_not_evaluated": sum(
            1 for r in rows if r.get("verdict_class") == "NOT_EVALUATED"),
        "total_shortfall": sum(max(0, -d) for d in diffs),
        "total_surplus": sum(max(0, d) for d in diffs),
        "unexplained_shortfall": sum(
            r.get("unexplained_shortfall", 0) for r in required),
        "unexplained_surplus": sum(
            r.get("unexplained_surplus", 0) for r in required),
        "duplicate_extra_objects": sum(
            r.get("duplicates", {}).get("extra_objects", 0) for r in rows
            if r.get("duplicates", {}).get("roster_admitted")
        ),
        "accounted_shortfall": sum(
            line["count"] for r in rows for line in r.get("accounted_for", ())
            if line.get("direction") == "shortfall"
        ),
        "accounted_surplus": sum(
            line["count"] for r in rows for line in r.get("accounted_for", ())
            if line.get("direction") == "surplus"
        ),
        "advisory_shortfall": sum(
            max(0, -r["difference"]) for r in rows
            if r.get("gate_scope") == "advisory"
            and r.get("difference") is not None
        ),
    }
    return totals


def starter_baseline_artifact(baseline) -> dict:
    """-> artifact `starter_baseline`, driven by the translation table.

    `entries`, `content_hash` and the in-memory `schema_version` are
    internal-only (`STARTER_BASELINE_ARTIFACT_FIELDS` maps them to None);
    `class_count` and `carries_natural_keys` are derived properties, so they
    cannot drift from the entries they describe. `staleness` is NOT emitted from
    the baseline: it is a judgement the gate computes (T020), and finding a
    pre-baked answer here to trust would defeat the point.
    """
    from .models import STARTER_BASELINE_ARTIFACT_FIELDS  # noqa: PLC0415

    block: dict = {}
    for internal, artifact_key in STARTER_BASELINE_ARTIFACT_FIELDS.items():
        if artifact_key is None:
            continue
        value = getattr(baseline, internal)
        if internal == "kind":
            block[artifact_key] = value.value
            continue
        if value in ("", None):
            continue
        block[artifact_key] = value
    if not baseline.is_missing:
        block["class_count"] = baseline.class_count
        block["carries_natural_keys"] = baseline.carries_natural_keys
    return block


def build_artifact(
    census,
    class_list: ClassList,
    rows,
    *,
    projects: dict,
    instrument: dict,
    transfer_run: Optional[dict] = None,
    verdict: str = "",
    exit_code: Optional[int] = None,
    verdict_human_label: str = "",
    errors=(),
    notes=(),
) -> dict:
    """Assemble the whole census artifact from already-emitted class rows.

    Driven by `models.FIDELITY_CENSUS_ARTIFACT_FIELDS`, whose `gate_pass -> None`
    entry is why no `gate_pass` key appears at top level: the artifact is
    `additionalProperties: false` and carries `verdict` + `exit_code`, and the
    gate RECOMPUTES both rather than trusting a stored boolean.

    `verdict` / `exit_code` may be left empty and stamped by T020's
    `stamp_verdict`, which is the only path that computes them from evidence.
    """
    rows = list(rows)
    artifact = {
        "schema_version": census.schema_version,
        "census_id": census.run_id,
        "generated_at": census.taken_at,
        "instrument": dict(instrument),
        "projects": dict(projects),
        "class_list_provenance": class_list_provenance_artifact(class_list),
        "starter_baseline": starter_baseline_artifact(census.baseline),
        "classes": rows,
        "totals": build_totals(rows),
    }
    if transfer_run:
        artifact["transfer_run"] = dict(transfer_run)
    if verdict:
        artifact["verdict"] = verdict
        artifact["exit_code"] = (
            exit_code if exit_code is not None else exit_code_for(verdict)
        )
        artifact["verdict_human_label"] = (
            verdict_human_label or VERDICT_HUMAN_LABELS[verdict]
        )
    if errors:
        artifact["errors"] = [dict(e) for e in errors]
    if notes:
        artifact["notes"] = list(notes)
    return artifact
