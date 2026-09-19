"""Feature 035 -- Group I: CAPABILITY PREFLIGHT (T022 of
specs/035-fullsweep-fidelity/tasks.md Phase 3 / US4).

Source: spec.md Section I (FR-124..FR-132), SC-008.

Load-bearing fact this module exists to guard against, in the spec's own
words: *a breaking default changed in the transfer engine's dependency while
its version string stayed fixed, so a version string alone cannot be
trusted.* Everything here therefore introspects ACTUAL BEHAVIOR and INTERFACE
SHAPES -- parameter names, default values, symbol presence -- and the version
string is RECORDED (FR-126) but never decides the outcome (FR-125).

Posture (FR-132): there is no "best effort, survive drift" path. Any drift is
a finding requiring a deliberate, recorded update to the pinned expectation.
An UNPINNED fingerprint is itself a mismatch: a preflight that cannot say
what it expected has not checked anything, and must not read as a pass.

This module touches no database and performs no restore and no write
(SC-008), except where ``check_accessors`` is explicitly handed an opened,
read-only project handle by its caller (FR-129).
"""
from __future__ import annotations

import inspect
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CONTRACTS_DIR = _ROOT / "specs" / "035-fullsweep-fidelity" / "contracts"
CAPABILITY_FINGERPRINT_NAME = "flexicon-capability.json"

#: FR-131: the four kinds a field-by-field difference may carry. Verbatim.
DIFF_KIND_MISSING = "missing"
DIFF_KIND_ADDED = "added"
DIFF_KIND_CHANGED = "changed"
DIFF_KIND_RENAMED = "renamed"

DIFF_KINDS: tuple[str, ...] = (
    DIFF_KIND_MISSING, DIFF_KIND_ADDED, DIFF_KIND_CHANGED, DIFF_KIND_RENAMED,
)

#: The verdict a mismatch assigns, and its exit code -- both owned by
#: ``verdict.py``; named here only so this module's callers need not
#: hardcode them.
PREFLIGHT_MISMATCH_VERDICT = "PREFLIGHT_MISMATCH"


class PreflightError(RuntimeError):
    """The preflight could not be PERFORMED (the dependency would not import,
    the pinned fingerprint is unreadable). Distinct from a MISMATCH, which is
    a normal, reportable outcome carrying a diff."""


# ===========================================================================
# FR-127..FR-130: what is introspected
# ===========================================================================

#: FR-127: interfaces the sweep depends on for opening/closing projects and
#: for reading/writing syncable properties. Parameter NAMES and DEFAULT
#: VALUES are both recorded, because FR-125's named failure mode is a default
#: changing under a fixed version string.
SIGNATURE_TARGETS: tuple[tuple[str, str], ...] = (
    ("flexicon.FLExProject", "OpenProject"),
    ("flexicon.FLExProject", "CloseProject"),
    ("flexicon.code.BaseOperations.BaseOperations", "GetSyncableProperties"),
    ("flexicon.code.BaseOperations.BaseOperations", "ApplySyncableProperties"),
)

#: FR-128: the identity-preserving object-creation surface the transfer
#: engine's identity-preservation guarantee depends on. A missing capability
#: here MUST fail loudly at preflight rather than surface later as a
#: laundered, generic creation failure (this repo's CLAUDE.md documents
#: exactly that laundering: ``_safe``/``except Exception`` swallow the
#: ``TypeError`` an older flexicon raises for every ``guid=`` kwarg).
GUID_CREATE_TARGETS: tuple[tuple[str, str], ...] = (
    ("flexicon.code.BaseOperations.BaseOperations", "_CreateWithGuid"),
    ("flexicon.code.TextsWords.TextOperations.TextOperations", "Create"),
    ("flexicon.code.TextsWords.ParagraphOperations.ParagraphOperations", "Create"),
    ("flexicon.code.TextsWords.SegmentOperations.SegmentOperations", "AppendSentence"),
    ("flexicon.code.TextsWords.WordformOperations.WordformOperations", "Create"),
    ("flexicon.code.TextsWords.WfiAnalysisOperations.WfiAnalysisOperations", "Create"),
    ("flexicon.code.TextsWords.WfiGlossOperations.WfiGlossOperations", "Create"),
    ("flexicon.code.TextsWords.WfiMorphBundleOperations.WfiMorphBundleOperations", "Create"),
)

#: The names this repo's CLAUDE.md uses for the same surface (``Texts``,
#: ``Wordforms``, ...) are the FLExProject ACCESSOR names, not the class
#: names, and the classes live under ``flexicon.code.TextsWords.*``. Recorded
#: here because looking for the CLAUDE.md spelling as a module attribute
#: yields ``<missing>`` for the entire guid-preserving surface -- which under
#: FR-132's no-degradation posture would refuse every run for a reason that
#: is an introspection defect, not real drift.
GUID_CREATE_ACCESSOR_ALIASES: dict = {
    "TextOperations": "Texts", "ParagraphOperations": "Paragraphs",
    "SegmentOperations": "Segments", "WordformOperations": "Wordforms",
    "WfiAnalysisOperations": "WfiAnalyses", "WfiGlossOperations": "WfiGlosses",
    "WfiMorphBundleOperations": "WfiMorphBundles",
}

#: FR-129: accessors the count and inventory layers depend on. These resolve
#: BY NAME on a real, opened, read-only project handle -- see
#: ``check_accessors``, which the caller supplies a handle to. Recorded here
#: with the dead accessor named explicitly so a future edit cannot quietly
#: reintroduce it.
ACCESSOR_TARGETS: tuple[str, ...] = (
    "LexiconNumberOfEntries",
)
DEAD_ACCESSORS: tuple[str, ...] = (
    "lexicon",  # removed; must NOT resolve, and must never be depended on
)

#: FR-130: the eight Grammar Operations subclasses that declare an
#: ``ApplySyncableProperties`` override for MCP-indexer visibility (this
#: repo's CLAUDE.md: the indexer's static analysis does not follow
#: inheritance). An override missing here is an indexer-visibility
#: regression, not a behavioral one -- but FR-130 requires it verified.
GRAMMAR_OVERRIDE_CLASSES: tuple[str, ...] = (
    "POSOperations", "MorphRuleOperations", "GramCatOperations",
    "InflectionFeatureOperations", "NaturalClassOperations",
    "EnvironmentOperations", "PhonologicalRuleOperations", "PhonemeOperations",
)
GRAMMAR_OVERRIDE_METHOD = "ApplySyncableProperties"


# ===========================================================================
# Introspection
# ===========================================================================

def _lookup(owner, method: str):
    """Fetch ``method`` from ``owner``'s own class dictionary (walking the
    MRO), NOT via ``getattr``.

    ``getattr`` on a flexicon Operations class runs the ``OperationsMethod``
    descriptor's ``__get__``, which hands back a generic
    ``(project, *args, **kwargs)`` dispatch wrapper. Introspecting THAT
    records the wrapper's shape for every method -- identical for all of
    them, and blind to exactly the parameter names and defaults FR-127
    exists to pin. The class dictionary holds the descriptor itself, whose
    ``.func`` is the real function.
    """
    for klass in getattr(owner, "__mro__", [owner]):
        if method in vars(klass):
            return vars(klass)[method]
    return getattr(owner, method)


def _unwrap(fn):
    """Return the underlying function behind flexicon's ``OperationsMethod``
    descriptor.

    ``inspect.signature`` raises ``TypeError: not a callable object`` on the
    raw descriptor, so an un-unwrapped probe reports every ``Create`` as
    missing. The descriptor exposes the real function as ``.func``;
    ``functools.wraps``-style ``__wrapped__`` is honored too, so an upstream
    change of wrapper style does not silently reintroduce the false miss.
    """
    for attr in ("func", "__wrapped__"):
        inner = getattr(fn, attr, None)
        if inner is not None and callable(inner):
            return inner
    return fn


def _signature_shape(fn) -> dict:
    """``{param_name: default_repr_or_"<required>"}`` plus the ordered
    parameter-name list, so a RENAME is distinguishable from a
    missing+added pair (FR-131's ``renamed`` kind)."""
    sig = inspect.signature(_unwrap(fn))
    params = {}
    for name, param in sig.parameters.items():
        if param.default is inspect.Parameter.empty:
            params[name] = "<required>"
        else:
            params[name] = repr(param.default)
    return {"parameters": params, "order": list(sig.parameters)}


def _resolve(dotted: str):
    """Resolve ``package.module.Attr`` without importing anything the caller
    did not name. Walks right-to-left so a class living several packages deep
    (``flexicon.code.TextsWords.TextOperations.TextOperations``) resolves as
    readily as a top-level re-export."""
    import importlib
    parts = dotted.split(".")
    for split in range(len(parts) - 1, 0, -1):
        module_name = ".".join(parts[:split])
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue
        obj = module
        for attr in parts[split:]:
            obj = getattr(obj, attr)
        return obj
    raise AttributeError("could not resolve %r" % (dotted,))


def dependency_provenance() -> dict:
    """FR-126: the dependency's reported version, its installation
    provenance, and its own revision identity.

    A dependency resolved from a stale PACKAGED copy rather than the tracked
    working installation MUST fail the preflight -- so ``from_site_packages``
    is measured here and consumed as a hard failure by ``run_preflight``.
    """
    try:
        import flexicon
    except Exception as exc:  # noqa: BLE001
        raise PreflightError(
            "[FR-124] the transfer engine's runtime dependency could not be "
            "imported: %s: %s" % (type(exc).__name__, exc)
        ) from exc
    path = Path(flexicon.__file__).resolve()
    parts = {p.lower() for p in path.parts}
    from .artifact import flexicon_revision
    return {
        "reported_version": getattr(flexicon, "__version__", None),
        "resolved_path": str(path),
        "from_site_packages": bool(parts & {"site-packages", "dist-packages"}),
        "revision": flexicon_revision(),
    }


def introspect_capabilities() -> dict:
    """Measure the dependency's ACTUAL interface shapes (FR-125/FR-127..
    FR-130). Returns the ``introspected`` block of a capability fingerprint.

    Every probe records what it FOUND, including ``"<missing>"`` -- never a
    silent omission, because an omitted key and a missing symbol would then
    be indistinguishable in the diff.
    """
    out: dict = {"signatures": {}, "guid_create_surface": {},
                 "grammar_overrides": {}, "dead_accessors": {}}

    for dotted, method in SIGNATURE_TARGETS:
        key = "%s.%s" % (dotted, method)
        try:
            owner = _resolve(dotted)
            fn = _lookup(owner, method)
            out["signatures"][key] = _signature_shape(fn)
        except Exception as exc:  # noqa: BLE001 -- recorded as missing, never silent
            out["signatures"][key] = {"error": "%s: %s" % (type(exc).__name__, exc)}

    for dotted, method in GUID_CREATE_TARGETS:
        key = "%s.%s" % (dotted, method)
        try:
            owner = _resolve(dotted)
            fn = _lookup(owner, method)
            shape = _signature_shape(fn)
            shape["accepts_guid_kwarg"] = "guid" in shape["parameters"]
            out["guid_create_surface"][key] = shape
        except Exception as exc:  # noqa: BLE001
            out["guid_create_surface"][key] = {"error": "%s: %s" % (type(exc).__name__, exc)}

    for cls_name in GRAMMAR_OVERRIDE_CLASSES:
        key = "flexicon.%s.%s" % (cls_name, GRAMMAR_OVERRIDE_METHOD)
        try:
            cls = _resolve("flexicon.%s" % cls_name)
            # FR-130 is about a DECLARED override, so check the class's own
            # __dict__ -- an inherited method is exactly what the indexer
            # cannot see, and is therefore not an override for this purpose.
            out["grammar_overrides"][key] = {
                "declared": GRAMMAR_OVERRIDE_METHOD in vars(cls),
            }
        except Exception as exc:  # noqa: BLE001
            out["grammar_overrides"][key] = {"error": "%s: %s" % (type(exc).__name__, exc)}

    for dead in DEAD_ACCESSORS:
        try:
            proj_cls = _resolve("flexicon.FLExProject")
            out["dead_accessors"][dead] = {"present": hasattr(proj_cls, dead)}
        except Exception as exc:  # noqa: BLE001
            out["dead_accessors"][dead] = {"error": "%s: %s" % (type(exc).__name__, exc)}

    return out


def check_accessors(project_handle) -> dict:
    """FR-129: every accessor the sweep's count and inventory layers depend on
    MUST resolve BY NAME on a REAL, OPENED, READ-ONLY project handle. An
    unresolvable accessor fails the preflight.

    Separated from ``introspect_capabilities`` because it is the one probe
    that needs an opened project; the SC-008 "touches no database" guarantee
    holds for everything else, and for the ``preflight`` subcommand, which
    does not call this.
    """
    result = {}
    for name in ACCESSOR_TARGETS:
        result[name] = {"resolves": hasattr(project_handle, name)}
    for name in DEAD_ACCESSORS:
        result[name] = {"resolves": hasattr(project_handle, name),
                        "expected_resolves": False}
    return result


# ===========================================================================
# FR-131: the field-by-field difference report
# ===========================================================================

@dataclass
class CapabilityDiff:
    """FR-131: symbol, expected value, actual value, and which of the four
    kinds the difference is."""
    symbol: str
    expected: object
    actual: object
    kind: str

    def __post_init__(self) -> None:
        if self.kind not in DIFF_KINDS:
            raise ValueError("[FR-131] diff kind must be one of %r, got %r"
                              % (DIFF_KINDS, self.kind))

    def as_dict(self) -> dict:
        return {"symbol": self.symbol, "expected": self.expected,
                "actual": self.actual, "kind": self.kind}


def _flatten(node, prefix: str = "") -> dict:
    """Flatten a nested introspection block into ``{dotted.path: leaf}`` so
    the diff can be genuinely FIELD-BY-FIELD (FR-131) rather than
    block-by-block."""
    out = {}
    if isinstance(node, dict):
        for k, v in node.items():
            out.update(_flatten(v, "%s.%s" % (prefix, k) if prefix else str(k)))
    elif isinstance(node, (list, tuple)):
        out[prefix] = list(node)
    else:
        out[prefix] = node
    return out


def _detect_renames(missing: dict, added: dict) -> list:
    """A symbol whose parent path and VALUE are unchanged but whose leaf name
    differs is a RENAME, not a missing+added pair (FR-131's fourth kind)."""
    renames = []
    for m_key, m_val in list(missing.items()):
        m_parent, _, m_leaf = m_key.rpartition(".")
        for a_key, a_val in list(added.items()):
            a_parent, _, a_leaf = a_key.rpartition(".")
            if m_parent == a_parent and m_leaf != a_leaf and m_val == a_val:
                renames.append(CapabilityDiff(
                    symbol="%s: %s -> %s" % (m_parent, m_leaf, a_leaf),
                    expected=m_key, actual=a_key, kind=DIFF_KIND_RENAMED,
                ))
                missing.pop(m_key, None)
                added.pop(a_key, None)
                break
    return renames


def diff_capabilities(expected: dict, actual: dict) -> list:
    """FR-131: a field-by-field difference report between the pinned
    expectation and what was measured."""
    exp_flat = _flatten(expected)
    act_flat = _flatten(actual)
    missing = {k: v for k, v in exp_flat.items() if k not in act_flat}
    added = {k: v for k, v in act_flat.items() if k not in exp_flat}
    diffs = _detect_renames(missing, added)
    diffs += [CapabilityDiff(symbol=k, expected=v, actual=None,
                              kind=DIFF_KIND_MISSING)
              for k, v in sorted(missing.items())]
    diffs += [CapabilityDiff(symbol=k, expected=None, actual=v,
                              kind=DIFF_KIND_ADDED)
              for k, v in sorted(added.items())]
    for k in sorted(set(exp_flat) & set(act_flat)):
        if exp_flat[k] != act_flat[k]:
            diffs.append(CapabilityDiff(symbol=k, expected=exp_flat[k],
                                         actual=act_flat[k], kind=DIFF_KIND_CHANGED))
    return diffs


# ===========================================================================
# The pinned fingerprint and the preflight itself
# ===========================================================================

def fingerprint_path(contracts_dir: Optional[Path] = None) -> Path:
    return Path(contracts_dir or DEFAULT_CONTRACTS_DIR) / CAPABILITY_FINGERPRINT_NAME


def load_pinned_fingerprint(contracts_dir: Optional[Path] = None) -> dict:
    """Load the pinned, git-tracked capability fingerprint (FR-125).

    Trackedness is asserted here (FR-149): a capability expectation that is
    not under version control cannot pin anything, because the next
    contributor's checkout does not have it.
    """
    from .safety import assert_tracked, EVIDENCE_KIND_CAPABILITY
    path = fingerprint_path(contracts_dir)
    if not path.is_file():
        raise PreflightError(
            "[FR-125] pinned capability fingerprint not found at %r" % (str(path),)
        )
    assert_tracked(path, kind=EVIDENCE_KIND_CAPABILITY)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise PreflightError(
            "[FR-125] pinned capability fingerprint %r is unreadable/corrupt: "
            "%s: %s" % (str(path), type(exc).__name__, exc)
        ) from exc


def is_pinned(fingerprint: dict) -> bool:
    """A fingerprint is PINNED only when it actually records an introspected
    expectation. The ``schema_version: 1`` scaffold written by T010 -- with
    ``introspected: {}`` -- is NOT pinned, and per FR-132 must read as a
    mismatch rather than as a pass."""
    introspected = fingerprint.get("introspected")
    return bool(isinstance(introspected, dict) and introspected)


@dataclass
class PreflightResult:
    ok: bool
    verdict: str
    exit_code: int
    provenance: dict = field(default_factory=dict)
    diffs: list = field(default_factory=list)
    measured: dict = field(default_factory=dict)
    fingerprint_path: str = ""
    reason: str = ""

    def as_dict(self) -> dict:
        return {
            "ok": self.ok, "verdict": self.verdict, "exit_code": self.exit_code,
            "provenance": self.provenance,
            "diffs": [d.as_dict() for d in self.diffs],
            "measured": self.measured, "fingerprint_path": self.fingerprint_path,
            "reason": self.reason,
        }


def run_preflight(contracts_dir: Optional[Path] = None) -> PreflightResult:
    """FR-124: performed ONCE at startup, BEFORE any restore or write.

    Returns a ``PreflightResult``; a mismatch carries ``verdict
    PREFLIGHT_MISMATCH`` and exit code 6, and the caller MUST NOT proceed to
    any restore or write. No best-effort degradation and no runtime path
    selection around a mismatch (FR-132/FR-133): the only two outcomes are
    "matched, proceed" and "refuse".
    """
    from .verdict import exit_code_for

    path = fingerprint_path(contracts_dir)
    pinned = load_pinned_fingerprint(contracts_dir)
    provenance = dependency_provenance()
    measured = introspect_capabilities()

    def _mismatch(diffs, reason):
        return PreflightResult(
            ok=False, verdict=PREFLIGHT_MISMATCH_VERDICT,
            exit_code=exit_code_for(PREFLIGHT_MISMATCH_VERDICT),
            provenance=provenance, diffs=diffs, measured=measured,
            fingerprint_path=str(path), reason=reason,
        )

    if not is_pinned(pinned):
        return _mismatch(
            [CapabilityDiff(symbol="introspected", expected="<pinned expectation>",
                             actual=pinned.get("introspected"),
                             kind=DIFF_KIND_MISSING)],
            "[FR-125/FR-132] the capability fingerprint at %r is a scaffold, "
            "not a pinned expectation. A preflight that cannot say what it "
            "expected has checked nothing; refusing rather than degrading to "
            "a best-effort pass." % (str(path),),
        )

    if provenance["from_site_packages"]:
        return _mismatch(
            [CapabilityDiff(symbol="flexicon.__file__",
                             expected="<tracked working installation>",
                             actual=provenance["resolved_path"],
                             kind=DIFF_KIND_CHANGED)],
            "[FR-126] the dependency resolved from a packaged copy (%s) rather "
            "than the tracked working installation."
            % (provenance["resolved_path"],),
        )

    diffs = diff_capabilities(pinned["introspected"], measured)
    if diffs:
        return _mismatch(
            diffs,
            "[FR-125/FR-132] %d capability difference(s) against the pinned "
            "fingerprint. Capability drift is a finding requiring a "
            "deliberate, recorded update to the pinned expectation -- never "
            "silently tolerated." % (len(diffs),),
        )

    return PreflightResult(
        ok=True, verdict="", exit_code=0, provenance=provenance, diffs=[],
        measured=measured, fingerprint_path=str(path), reason="",
    )


def format_diff_report(result: PreflightResult, max_rows: Optional[int] = None) -> str:
    """FR-131: the field-by-field report, ASCII-only (Windows-terminal safe),
    for the console. The DURABLE artifact always carries the full list --
    ``max_rows`` truncates the console rendering only, and states the
    omitted count when it does (FR-144)."""
    lines = ["[PREFLIGHT] %s" % ("MATCH" if result.ok else "MISMATCH")]
    lines.append("  fingerprint: %s" % result.fingerprint_path)
    prov = result.provenance
    lines.append("  dependency:  version=%s path=%s rev=%s"
                  % (prov.get("reported_version"), prov.get("resolved_path"),
                     (prov.get("revision") or {}).get("sha")))
    if result.reason:
        lines.append("  reason: %s" % result.reason)
    rows = result.diffs if max_rows is None else result.diffs[:max_rows]
    for d in rows:
        lines.append("  [%-8s] %s" % (d.kind, d.symbol))
        lines.append("      expected: %r" % (d.expected,))
        lines.append("      actual:   %r" % (d.actual,))
    omitted = len(result.diffs) - len(rows)
    if omitted > 0:
        lines.append("  ... %d further difference(s) omitted from this console "
                      "summary; the artifact carries all %d."
                      % (omitted, len(result.diffs)))
    return "\n".join(lines)


def write_preflight_artifact(result: PreflightResult, artifacts_dir: Path) -> Path:
    """FR-131: the difference report goes to a DURABLE artifact as well as the
    console."""
    import os
    out = Path(artifacts_dir) / "preflight.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(result.as_dict(), indent=2, default=str), encoding="utf-8")
    os.replace(str(tmp), str(out))
    return out
