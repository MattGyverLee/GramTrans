"""Feature 035 T045b -- the anti-silence instrumentation.

This module does NOT measure the transfer. It measures whether the instrument
is telling the truth about its own coverage, which is why it survived the 038
cut intact: 038's census can say how many objects arrived, but nothing in it
can say "the enumeration that produced this number silently dropped eleven
objects it could not read".

Three accumulators live here, one per failure mode the sweep could previously
have suffered in silence:

``AccessorCounters`` (FR-103)
    ``audit_guid_preservation.inventory_all`` swallows every per-object read
    failure with ``except Exception: continue``. The object vanishes from the
    census and the census reports a smaller, cleaner number. This counts them
    at the exact point they are swallowed -- the swallow itself is KEPT,
    because aborting a 500k-object enumeration on one unreadable object trades
    a partial measurement for none; what changes is that the partial
    measurement now says so.

``OperationLog`` (FR-104 and FR-108)
    Every project-handle operation -- open, reopen, close, initialize -- with
    its outcome. A close that failed or hung invalidates every measurement
    taken after it, and until now both ``inventory_all`` and
    ``run_full_transfer`` closed inside a bare ``except`` that discarded the
    evidence.

``TruncationCounters`` (FR-105)
    Whether the DURABLE artifact omitted anything. FR-105 requires two zeros;
    hardcoding them would be a claim rather than a measurement, so they are
    obtained by comparing the in-memory artifact against the document actually
    serialized from it.

THE RULE THIS MODULE FOLLOWS, EVERYWHERE: an accumulator that was never given
to a call site stays ``None`` at the driver and its guard reports
``not-evaluated``. Every out-parameter added by this task defaults to ``None``
and every call site that passes nothing behaves byte-identically to before.
An accumulator that WAS threaded reports what it saw, including zero -- and a
zero from a threaded accumulator is a measurement, which is the whole
difference this module exists to make.
"""
from __future__ import annotations

import json
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# FR-103 -- the four accessor counters
# ---------------------------------------------------------------------------

#: ``guards.ACCESSOR_COUNTERS``, restated here so this module can be read
#: without the guard module open. The two are pinned equal by a test rather
#: than by an import, because an import would let a rename in either file pass
#: unnoticed in the other.
ACCESSOR_COUNTER_NAMES: tuple[str, ...] = (
    "unreadable_identifiers",
    "unreadable_names",
    "enumeration_failures",
    "skipped_source_objects",
)


@dataclass
class AccessorCounters:
    """FR-103's four counters, plus the scope each increment came from.

    **The aggregation question, and how it is answered.** The four
    ``census_project`` calls in one ``run_one_project`` span TWO projects
    (the target three times, the source once), FR-103 reads as per-project,
    and ``RunContext`` has exactly one ``accessor_counters`` field. Rather
    than pick one project and discard the other's failures, this object
    aggregates over the RUN and keeps a per-scope breakdown beside the totals.

    That is the correct unit for the guard's question. ACCESSOR-INTEGRITY
    fails a run whose measurements cannot be trusted, and a census triple in
    which the SOURCE enumeration dropped objects is exactly as untrustworthy
    as one in which a target enumeration did -- the reconciliation subtracts
    one from the other. The totals answer "can this run's numbers be
    believed"; ``by_scope`` answers "where did it go wrong", which is a
    diagnostic question and belongs in the evidence, not in the verdict.
    """

    unreadable_identifiers: int = 0
    unreadable_names: int = 0
    enumeration_failures: int = 0
    skipped_source_objects: int = 0
    #: One entry per distinct (scope, accessor, error type) -- capped detail,
    #: uncapped counts. The guard reads this list into its evidence.
    failed_accessors: list = field(default_factory=list)
    #: scope -> {counter: n}. A scope names the project AND the measurement
    #: step, e.g. ``"Ejagham Mini:source_inventory"``.
    by_scope: dict = field(default_factory=dict)
    #: How many distinct scopes were instrumented. Zero totals from zero
    #: scopes is not a measurement; the driver refuses to deposit that.
    scopes_instrumented: int = 0

    #: At most this many distinct failure shapes are detailed. The COUNTS are
    #: never capped -- only the per-shape sample list, and the cap being hit
    #: is itself recorded so the artifact never quietly shortens a list
    #: (FR-105 applies to this module's own output too).
    detail_cap: int = 200
    detail_omitted: int = 0

    def open_scope(self, scope: str) -> None:
        """Declare that ``scope`` was instrumented, before anything fails.

        Without this, a scope in which nothing went wrong is indistinguishable
        from a scope that was never instrumented at all -- and that is the
        distinction FR-103 turns on, since all four counters at zero is the
        PASS condition.
        """
        self.by_scope.setdefault(scope, {n: 0 for n in ACCESSOR_COUNTER_NAMES})
        self.scopes_instrumented = len(self.by_scope)

    def record(
        self,
        counter: str,
        *,
        scope: str,
        accessor: str = "",
        error: Optional[BaseException] = None,
        detail: str = "",
    ) -> None:
        """Increment ``counter``, attributing it to ``scope``."""
        if counter not in ACCESSOR_COUNTER_NAMES:
            raise ValueError(
                "[FR-103] %r is not one of the four accessor counters %r. "
                "Adding a fifth is a contract change (guards.ACCESSOR_COUNTERS "
                "and contracts/guards.md both name them), not a call-site "
                "decision." % (counter, ACCESSOR_COUNTER_NAMES)
            )
        setattr(self, counter, getattr(self, counter) + 1)
        self.open_scope(scope)
        self.by_scope[scope][counter] += 1

        shape: dict = {
            "scope": scope,
            "counter": counter,
            "accessor": accessor,
            "error_type": type(error).__name__ if error is not None else "",
            "error_message": ("%s" % error) if error is not None else detail,
        }
        # Dedup by shape so one broken accessor firing 40,000 times does not
        # produce 40,000 identical rows. ``occurrences`` keeps the count
        # honest; the totals above are incremented unconditionally either way.
        for existing in self.failed_accessors:
            if all(existing.get(k) == shape[k] for k in
                   ("scope", "counter", "accessor", "error_type")):
                existing["occurrences"] += 1
                return
        if len(self.failed_accessors) >= self.detail_cap:
            self.detail_omitted += 1
            return
        shape["occurrences"] = 1
        self.failed_accessors.append(shape)

    def total(self) -> int:
        return sum(getattr(self, n) for n in ACCESSOR_COUNTER_NAMES)

    def as_dict(self) -> dict:
        """The shape ``guard_accessor_integrity`` reads.

        The four counters are top-level because the guard indexes them by name
        and treats a missing one as ``not-evaluated``. Everything else is
        diagnostic.
        """
        out = {n: getattr(self, n) for n in ACCESSOR_COUNTER_NAMES}
        out.update({
            "failed_accessors": list(self.failed_accessors),
            "by_scope": {k: dict(v) for k, v in sorted(self.by_scope.items())},
            "scopes_instrumented": self.scopes_instrumented,
            "detail_shapes_omitted": self.detail_omitted,
        })
        return out


# ---------------------------------------------------------------------------
# FR-104 / FR-108 -- the project-handle operation log
# ---------------------------------------------------------------------------

OP_OPEN = "open"
OP_REOPEN = "reopen"
OP_CLOSE = "close"
OP_INITIALIZE = "initialize"

#: FR-104's vocabulary, verbatim: "open, reopen, close, or initialize".
HANDLE_OPERATION_KINDS: tuple[str, ...] = (
    OP_OPEN, OP_REOPEN, OP_CLOSE, OP_INITIALIZE,
)


@dataclass
class HandleOperation:
    """One project-handle operation, as it happened.

    ONE record type, TWO projections -- see ``OperationLog``. The record
    carries every fact both guards need; each projection emits only the keys
    its own guard reads, because a guard handed keys it does not read will
    silently ignore a fact it should have failed on.
    """

    operation: str
    project: str
    ok: bool
    seq: int = 0
    kind: str = OP_OPEN
    error_type: str = ""
    error_message: str = ""
    duration_s: float = 0.0
    timed_out: bool = False
    #: Measurement step names noted after this operation, filled by the log.
    followed_by: tuple = ()

    def handle_record(self) -> dict:
        """FR-104's shape, read by ``guard_handle_integrity``.

        ``error_type`` and ``error_message`` are the two facts that guard
        records for a failure; ``timed_out`` is deliberately absent because
        FR-104 does not distinguish a hang from a throw -- FR-108 does, for
        closes, and that is the other projection.
        """
        return {
            "operation": self.operation,
            "kind": self.kind,
            "project": self.project,
            "ok": bool(self.ok),
            "error_type": self.error_type,
            "error_message": self.error_message,
            "duration_s": round(self.duration_s, 3),
        }

    def close_record(self) -> dict:
        """FR-108's shape, read by ``guard_clean_close``.

        ``timed_out`` and ``followed_by`` are the two facts THIS guard turns
        on: a close that hung invalidates every measurement after it, so the
        record has to name them.
        """
        return {
            "operation": self.operation,
            "project": self.project,
            "ok": bool(self.ok),
            "timed_out": bool(self.timed_out),
            "error_message": self.error_message,
            "duration_s": round(self.duration_s, 3),
            "followed_by": list(self.followed_by),
        }


class OperationLog:
    """One shared record list; two projections onto it.

    **Why not two lists.** T045b's own task text observes that FR-104 covers
    "open, reopen, close, or initialize" while FR-108 covers close
    specifically, that the two guards read different keys
    (``error_type`` vs ``timed_out``/``followed_by``), and concludes that "one
    shared record list satisfies neither". That is true of one shared record
    SHAPE. It is not true of one shared record list with two projections, and
    the alternative -- two independently appended lists -- is how a close ends
    up in one and not the other. A close is a handle operation AND a close;
    both guards must see it, each in its own shape.

    **Why ``timed_out`` is wall-clock.** ``api._close_project_watchdog`` only
    LOGS after its deadline; a wedged .NET call cannot be interrupted from
    Python, so the call returns normally (eventually) and raises nothing. A
    timeout is therefore not observable from an exception and has to be
    derived by timing the call against ``api._SCHEMA_CLOSE_TIMEOUT_S``.
    """

    #: Mirrors ``api._SCHEMA_CLOSE_TIMEOUT_S``'s own default. The real value is
    #: read from ``api`` when the driver builds the log; this is the fallback
    #: for pure-unit use, where importing ``api`` would pull in FieldWorks.
    DEFAULT_TIMEOUT_S = 90.0

    def __init__(self, *, timeout_s: Optional[float] = None, clock=time.monotonic):
        self.timeout_s = self.DEFAULT_TIMEOUT_S if timeout_s is None else float(timeout_s)
        self._clock = clock
        self._records: list = []
        #: (seq, name) for every measurement step, so ``followed_by`` is
        #: derived from the real order rather than from a caller's memory.
        self._measurements: list = []
        self._seq = 0

    # -- recording ---------------------------------------------------------

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def note_measurement(self, name: str) -> None:
        """Record that a measurement was taken, here, in sequence.

        FR-108's ``followed_by`` is "the measurements taken after this close",
        and a close only invalidates what came AFTER it. Deriving that from a
        shared sequence counter is the only way it stays true when a step is
        reordered.
        """
        self._measurements.append((self._next_seq(), name))

    def record(
        self,
        operation: str,
        project: str,
        *,
        ok: bool,
        kind: str = OP_OPEN,
        error: Optional[BaseException] = None,
        duration_s: float = 0.0,
    ) -> HandleOperation:
        if kind not in HANDLE_OPERATION_KINDS:
            raise ValueError(
                "[FR-104] %r is not one of %r. FR-104 names exactly these four "
                "handle operations; widening the vocabulary is a contract "
                "change." % (kind, HANDLE_OPERATION_KINDS)
            )
        rec = HandleOperation(
            operation=operation, project=project, ok=bool(ok),
            seq=self._next_seq(), kind=kind,
            error_type=type(error).__name__ if error is not None else "",
            error_message=("%s" % error) if error is not None else "",
            duration_s=float(duration_s),
            # A close is judged timed out on wall clock, never on the absence
            # of an exception -- see the class docstring.
            timed_out=(kind == OP_CLOSE and float(duration_s) >= self.timeout_s),
        )
        self._records.append(rec)
        return rec

    @contextmanager
    def watch(self, operation: str, project: str, *, kind: str = OP_OPEN):
        """Time an operation and record its outcome, success or failure.

        The exception is RE-RAISED. This context manager is instrumentation,
        not error handling: a caller that wants to swallow a close failure
        still writes its own ``try``/``except`` around this, and the record is
        written either way. That ordering is the point -- the bare excepts
        this task exists to fix swallowed the evidence along with the error.
        """
        started = self._clock()
        try:
            yield
        except BaseException as exc:   # noqa: BLE001 -- recorded, then re-raised
            self.record(operation, project, ok=False, kind=kind, error=exc,
                        duration_s=self._clock() - started)
            raise
        else:
            self.record(operation, project, ok=True, kind=kind,
                        duration_s=self._clock() - started)

    # -- projections -------------------------------------------------------

    def _followed_by(self, rec: HandleOperation) -> tuple:
        return tuple(name for seq, name in self._measurements if seq > rec.seq)

    def handle_operations(self) -> list:
        """FR-104: EVERY operation, closes included."""
        return [r.handle_record() for r in self._records]

    def close_operations(self) -> list:
        """FR-108: the closes only, each carrying what followed it."""
        out = []
        for rec in self._records:
            if rec.kind != OP_CLOSE:
                continue
            rec.followed_by = self._followed_by(rec)
            out.append(rec.close_record())
        return out

    def as_dict(self) -> dict:
        return {
            "timeout_s": self.timeout_s,
            "operations": self.handle_operations(),
            "closes": self.close_operations(),
            "measurements": [name for _, name in self._measurements],
        }

    def __len__(self) -> int:
        return len(self._records)


# ---------------------------------------------------------------------------
# FR-105 -- durable-artifact omission counters
# ---------------------------------------------------------------------------

#: The artifact fields whose LENGTH is a detail count. A row missing from any
#: of these between the object and the document it serialized to is an
#: omission FR-105 forbids in the durable artifact.
DETAIL_BEARING_FIELDS: tuple[str, ...] = (
    "findings", "link_findings", "assertions", "errors",
    "excluded_category_records", "phases_completed",
)


def serialized_view(document: dict) -> dict:
    """What the artifact looks like AFTER going through the writer.

    ``_atomic_write_json`` serializes with ``json.dumps(..., default=str)``
    and that is not an identity map. ``default=str`` turns any object json
    cannot encode into its ``repr`` -- a ``LinkResult`` becomes the STRING
    ``"LinkResult(verdict='SILENTLY_UNSET', ...)"``, which reads as evidence,
    parses as nothing, and fails no test. Non-string dict keys are coerced,
    and two keys that differ only by type collapse into one.

    Comparing the in-memory artifact against ITSELF would therefore measure
    nothing at all: the comparison has to be against the document as the
    writer leaves it. This round-trips in memory rather than re-reading the
    file, which is equivalent -- ``os.replace`` of a fully-written temp file
    does not alter bytes -- and cheap enough to run on all ten flushes.
    """
    return json.loads(json.dumps(document, indent=2, default=str))


def count_document_omissions(artifact_obj: dict, document: dict) -> dict:
    """Compare an artifact against the document serialized from it.

    FR-105 wants two counters and both at zero in the DURABLE artifact.
    Hardcoding them to zero would be a claim; this is the measurement behind
    the claim, and it is a real one because it can come back non-zero -- a
    caller that passed a ``console_truncate``d list into a ``ProjectArtifact``
    field (exactly what ``console_truncate``'s docstring forbids) produces a
    document shorter than the drop channel it was built from, and that shows
    up here.

    ``dropped_breakdown_omitted``
        Drop-reason buckets present in the transfer's own ``by_reason``
        summary but missing from the document's, plus any transfer key
        missing outright.

    ``detail_omitted``
        Detail rows missing from the document across every detail-bearing
        list, including each transfer's drop ``records``.
    """
    breakdown_omitted = 0
    detail_omitted = 0
    where: list = []

    src_drops = artifact_obj.get("drops") or {}
    doc_drops = document.get("drops") or {}
    for key, src_block in src_drops.items():
        doc_block = doc_drops.get(key)
        if doc_block is None:
            breakdown_omitted += len((src_block or {}).get("by_reason", {}) or {})
            detail_omitted += len((src_block or {}).get("records", []) or [])
            where.append({"field": "drops.%s" % key, "omitted": "the whole block"})
            continue
        src_reasons = (src_block or {}).get("by_reason", {}) or {}
        doc_reasons = (doc_block or {}).get("by_reason", {}) or {}
        missing_reasons = [r for r in src_reasons if r not in doc_reasons]
        if missing_reasons:
            breakdown_omitted += len(missing_reasons)
            where.append({"field": "drops.%s.by_reason" % key,
                          "omitted": missing_reasons})
        src_records = (src_block or {}).get("records", []) or []
        doc_records = (doc_block or {}).get("records", []) or []
        # The reason total is the authority on how many records there SHOULD
        # be: a records list shorter than the counts it was summarized from is
        # precisely the truncation FR-105 forbids.
        expected = max(len(src_records), sum(src_reasons.values()) if src_reasons else 0)
        if len(doc_records) < expected:
            detail_omitted += expected - len(doc_records)
            where.append({"field": "drops.%s.records" % key,
                          "expected": expected, "written": len(doc_records)})

    for name in DETAIL_BEARING_FIELDS:
        src_list = artifact_obj.get(name)
        if not isinstance(src_list, (list, tuple)):
            continue
        doc_list = document.get(name)
        written = len(doc_list) if isinstance(doc_list, (list, tuple)) else 0
        if written < len(src_list):
            detail_omitted += len(src_list) - written
            where.append({"field": name, "expected": len(src_list),
                          "written": written})

    return {
        "dropped_breakdown_omitted": breakdown_omitted,
        "detail_omitted": detail_omitted,
        "where": where,
    }


@dataclass
class TruncationCounters:
    """FR-105's two counters, accumulated across every flush of one artifact.

    **The ordering problem, and how it is closed.** ``run_one_project`` reads
    its guard inputs inside ``finally`` and flushes the artifact immediately
    AFTER, so the last write is unmeasured by construction -- the 2026-08-19
    survey recorded this as open. It is closed by measuring the document
    BEFORE the guards run (``measure_pending``, a dry-run serialization of the
    artifact as it then stands) rather than only after each real flush.

    What the final flush adds on top of that dry run is bounded and named:
    ``guards`` (a fifteen-key block whose completeness ``assert_guard_block_
    complete`` asserts independently, twice), ``verdict``, ``exit_code``,
    ``guard_inputs_measured`` and ``finished_at``. None of them is a
    detail-bearing list, so none can be truncated. ``final_flush_scope`` says
    so on the record, and ``verify_final`` re-reads the written file to prove
    it -- a mismatch there is reported, never assumed absent.
    """

    dropped_breakdown_omitted: int = 0
    detail_omitted: int = 0
    flushes_measured: int = 0
    by_flush: list = field(default_factory=list)
    final_flush_verified: bool = False
    final_flush_mismatch: list = field(default_factory=list)

    #: The fields the final flush adds after the dry run. Named, so "the last
    #: write is unmeasured" is a bounded statement rather than a shrug.
    FINAL_FLUSH_ADDS: tuple = (
        "guards", "verdict", "exit_code", "guard_inputs_measured",
        "finished_at", "truncation",
    )

    def observe(self, label: str, artifact_obj: dict, document: dict) -> dict:
        counts = count_document_omissions(artifact_obj, document)
        self.dropped_breakdown_omitted += counts["dropped_breakdown_omitted"]
        self.detail_omitted += counts["detail_omitted"]
        self.flushes_measured += 1
        self.by_flush.append({
            "flush": label,
            "dropped_breakdown_omitted": counts["dropped_breakdown_omitted"],
            "detail_omitted": counts["detail_omitted"],
            "where": counts["where"],
        })
        return counts

    def verify_final(self, artifact_obj: dict, written_document: dict) -> dict:
        """Re-read the FINAL written document and prove the bound above.

        Called after the last flush. It does not feed the guard -- the verdict
        is already computed by then, and quietly changing it here would make
        the artifact disagree with itself. It records, loudly, whether the
        bound held, and the driver surfaces a mismatch on the artifact's own
        error list and in the CLI's exit code.
        """
        counts = count_document_omissions(artifact_obj, written_document)
        self.final_flush_verified = True
        if counts["dropped_breakdown_omitted"] or counts["detail_omitted"]:
            self.final_flush_mismatch = counts["where"]
        return counts

    def as_dict(self) -> dict:
        """The shape ``guard_no_truncation`` reads."""
        return {
            "dropped_breakdown_omitted": self.dropped_breakdown_omitted,
            "detail_omitted": self.detail_omitted,
            "flushes_measured": self.flushes_measured,
            "by_flush": list(self.by_flush),
            "final_flush_scope": {
                "measured_by": "a dry-run serialization taken immediately "
                               "before the guards run",
                "adds_after_measurement": list(self.FINAL_FLUSH_ADDS),
                "none_is_a_detail_bearing_list": True,
                "verified": self.final_flush_verified,
                "mismatch": list(self.final_flush_mismatch),
            },
        }
