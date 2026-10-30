"""Issue #22 Part 1 -- real Merge.

Covers the merge write decision (fill-empty, update-diverged, empty-source
preserved, target-only writing-system alternative preserved, one-sided key
written), the auditable partial apply (per-field failures and flexicon's
silent skips reach the report sink), and the routing of the legacy persisted
"merge" mode to the Merge (UPDATE) executor, including loading an old config
whose modes are plain strings.

Pure fakes; no LCM host required.
"""
from __future__ import annotations

import pytest

import gramtrans.Lib.categories as categories
import gramtrans.Lib.transfer as transfer
from gramtrans.Lib.conflict import (
    ItemDisposition,
    apply_update_semantic,
    compute_disposition,
    compute_merge_fillable,
)
from gramtrans.Lib.models import (
    ConflictMode,
    GrammarCategory,
    PlannedOverwrite,
    RunContext,
    RunPlan,
    Selection,
    WSMapping,
)


class _Sink:
    def __init__(self):
        self.messages = []

    def Info(self, m): self.messages.append(("I", m))
    def Warning(self, m): self.messages.append(("W", m))
    def Error(self, m): self.messages.append(("E", m))
    def Blank(self): pass

    def warnings(self):
        return [m for k, m in self.messages if k == "W"]


class _StoreOps:
    """A fake Operations class backed by a per-object props store that behaves
    like flexicon: a multistring write sets only the alternatives given (other
    alternatives untouched), empty fields are omitted on read, and any key in
    `silently_skip` is accepted without being stored (the `_apply_props_loop`
    silent-skip shape)."""

    def __init__(self, store, silently_skip=(), skip_ws=()):
        self.store = store
        self.silently_skip = set(silently_skip)
        self.skip_ws = set(skip_ws)
        self.calls = []

    def ApplySyncableProperties(self, obj, props, ws_map=None, fill_gaps=False):
        self.calls.append(dict(props))
        for key, val in props.items():
            if key in self.silently_skip:
                continue
            if isinstance(val, dict):
                cur = dict(self.store.get(key) or {})
                for ws, text in val.items():
                    ws_t = ws_map.get(ws, ws) if ws_map else ws
                    if ws_t in self.skip_ws:
                        continue
                    cur[ws_t] = text
                self.store[key] = cur
            else:
                self.store[key] = val

    def GetSyncableProperties(self, obj):
        return {k: (dict(v) if isinstance(v, dict) else v)
                for k, v in self.store.items() if v not in (None, "", {})}


# ---------------------------------------------------------------------------
# The Merge write decision
# ---------------------------------------------------------------------------

def _merge(src, tgt, **kw):
    store = {k: (dict(v) if isinstance(v, dict) else v) for k, v in tgt.items()}
    ops = _StoreOps(store, **{k: kw.pop(k) for k in ("silently_skip", "skip_ws") if k in kw})
    sink = _Sink()
    n = apply_update_semantic(src, ops.GetSyncableProperties(None), ops, object(),
                              report_sink=sink, label="[pos] guid=abcd1234", **kw)
    return n, store, ops, sink


def test_fill_empty_target_field():
    n, store, _ops, sink = _merge(
        {"Name": {"en": "Verb"}, "Abbreviation": {"en": "v"}},
        {"Name": {"en": "Verb"}, "Abbreviation": {}},
    )
    assert n == 1
    assert store["Abbreviation"] == {"en": "v"}
    assert sink.warnings() == []


def test_update_diverged_field():
    n, store, _ops, _sink = _merge({"Name": {"en": "Verb"}}, {"Name": {"en": "Verb-OLD"}})
    assert n == 1
    assert store["Name"] == {"en": "Verb"}


def test_empty_source_never_blanks_target():
    # Description: absent from the source dict (flexicon omits empty fields)
    # AND present-but-empty; Abbreviation alternative "***" (empty sentinel).
    n, store, ops, _sink = _merge(
        {"Name": {"en": "Verb"}, "Gloss": "", "Abbreviation": {"en": "***"}},
        {"Name": {"en": "Verb"}, "Gloss": "keep", "Abbreviation": {"en": "v"},
         "Description": {"en": "target only"}},
    )
    assert n == 0 and ops.calls == []
    assert store["Gloss"] == "keep"
    assert store["Abbreviation"] == {"en": "v"}
    assert store["Description"] == {"en": "target only"}


def test_target_only_ws_alternative_preserved_and_only_delta_written():
    n, store, ops, _sink = _merge(
        {"Name": {"en": "Verb", "swh": "kitenzi"}},
        {"Name": {"en": "Verb-OLD", "swh": "kitenzi", "fr": "verbe"}},
    )
    assert n == 1
    # Only the diverged alternative is handed to flexicon.
    assert ops.calls == [{"Name": {"en": "Verb"}}]
    assert store["Name"] == {"en": "Verb", "swh": "kitenzi", "fr": "verbe"}


def test_one_sided_source_key_is_written():
    n, store, _ops, _sink = _merge(
        {"Name": {"en": "Verb"}, "CatalogSourceId": "Verb"},
        {"Name": {"en": "Verb"}},
    )
    assert n == 1
    assert store["CatalogSourceId"] == "Verb"


def test_matching_alt_plus_target_only_alt_is_not_a_divergence():
    """Re-run idempotency: {"en": "x"} vs {"en": "x", "fr": "z"} is in sync.
    The old whole-dict compare made this an UPDATE on every run."""
    src = {"Name": {"en": "x"}}
    tgt = {"Name": {"en": "x", "fr": "z"}}
    assert compute_merge_fillable(src, tgt) == {}
    assert compute_disposition(src, tgt, ConflictMode.UPDATE) == ItemDisposition.SKIP
    n, _store, ops, _sink = _merge(src, tgt)
    assert n == 0 and ops.calls == []


def test_empty_source_only_difference_is_skip_disposition():
    src = {"Name": {"en": "x"}, "Gloss": ""}
    tgt = {"Name": {"en": "x"}, "Gloss": "keep"}
    assert compute_disposition(src, tgt, ConflictMode.UPDATE) == ItemDisposition.SKIP


def test_ws_map_is_honoured_by_delta_and_disposition():
    src = {"Name": {"src-vern": "dog"}}
    tgt = {"Name": {"tgt-vern": "dog"}}
    ws_map = {"src-vern": "tgt-vern"}
    assert compute_merge_fillable(src, tgt, ws_map=ws_map) == {}
    assert compute_disposition(src, tgt, ConflictMode.UPDATE,
                               ws_map=ws_map) == ItemDisposition.SKIP
    assert compute_merge_fillable(src, {"Name": {"tgt-vern": "cat"}}, ws_map=ws_map)


def test_text_compare_is_exact_like_the_preview_planner():
    """The planner compares per-WS text exactly; the writer must agree, so an
    NFC/NFD pair is a divergence on both sides (no silent Preview/Move gap)."""
    nfc, nfd = "é", "é"
    assert compute_merge_fillable({"Name": {"en": nfc}}, {"Name": {"en": nfd}})


# ---------------------------------------------------------------------------
# Auditable partial applies (audit blind spot 5)
# ---------------------------------------------------------------------------

def test_per_field_exception_reaches_report_sink_and_is_not_counted():
    class _Raising(_StoreOps):
        def ApplySyncableProperties(self, obj, props, ws_map=None, fill_gaps=False):
            if "Bad" in props:
                raise TypeError("simulated")
            super().ApplySyncableProperties(obj, props, ws_map=ws_map)

    store = {"Good": "old", "Bad": "old"}
    ops = _Raising(store)
    sink = _Sink()
    n = apply_update_semantic({"Good": "new", "Bad": "new"}, dict(store), ops,
                              object(), report_sink=sink, label="[x]")
    assert n == 1
    assert len(sink.warnings()) == 1
    assert "'Bad'" in sink.warnings()[0] and "TypeError" in sink.warnings()[0]


def test_flexicon_silent_skip_detected_by_read_back():
    n, store, _ops, sink = _merge(
        {"Name": {"en": "Verb"}, "StratumGuid": "1234"},
        {"Name": {"en": "Verb-OLD"}},
        silently_skip={"StratumGuid"},
    )
    assert n == 1  # Name only; StratumGuid accepted but never stored
    assert "StratumGuid" not in store
    (w,) = sink.warnings()
    assert "'StratumGuid'" in w and "not present on read-back" in w
    assert w.strip().startswith("[pos] guid=abcd1234")


def test_silent_skip_of_one_ws_alternative_names_the_ws():
    n, _store, _ops, sink = _merge(
        {"Name": {"en": "Verb", "mgz": "kit"}},
        {"Name": {"en": "Verb-OLD"}},
        skip_ws={"mgz"},
    )
    assert n == 0
    (w,) = sink.warnings()
    assert "'Name'" in w and "mgz" in w


def test_read_back_failure_reports_unverified_writes():
    class _NoRead(_StoreOps):
        def GetSyncableProperties(self, obj):
            raise RuntimeError("COM gone")

    ops = _NoRead({"Name": {"en": "old"}})
    sink = _Sink()
    n = apply_update_semantic({"Name": {"en": "new"}}, {"Name": {"en": "old"}},
                              ops, object(), report_sink=sink)
    assert n == 1
    assert "unverified" in sink.warnings()[0]


# ---------------------------------------------------------------------------
# Persisted "merge" routing + legacy-config load
# ---------------------------------------------------------------------------

def test_conflict_mode_parses_legacy_merge_as_update():
    assert ConflictMode("merge") is ConflictMode.UPDATE
    assert ConflictMode(" Merge ") is ConflictMode.UPDATE
    assert ConflictMode("merge") is not ConflictMode.LINK


@pytest.mark.parametrize("raw,expected", [
    ("merge", ConflictMode.UPDATE),
    ("update", ConflictMode.UPDATE),
    ("LINK", ConflictMode.LINK),
    ("overwrite", ConflictMode.OVERWRITE),
    ("add_new", ConflictMode.ADD_NEW),
])
def test_legacy_string_config_loads_to_enum_members(raw, expected):
    """An old saved config (category and mode as plain strings) loads, and the
    stored dict holds enum members -- so a reader comparing against
    ConflictMode members (the Move dispatch) cannot fall through to the
    OVERWRITE `else` branch on a raw string."""
    sel = Selection(category_conflict_modes={"pos": raw})
    assert sel.category_conflict_modes == {GrammarCategory.POS: expected}
    assert sel.conflict_mode_for(GrammarCategory.POS) is expected


def test_unknown_mode_fails_loudly():
    with pytest.raises(ValueError):
        Selection(category_conflict_modes={GrammarCategory.POS: "smash"})


def test_replace_conflict_modes_also_normalises():
    sel = Selection()._replace_conflict_modes({GrammarCategory.POS: "merge"})
    assert sel.category_conflict_modes[GrammarCategory.POS] is ConflictMode.UPDATE


@pytest.fixture
def _quiet_tail(monkeypatch):
    monkeypatch.setattr(categories, "reproduce_all_lexical_relations", lambda *a, **k: None)
    monkeypatch.setattr(categories, "reproduce_reversal_entries", lambda *a, **k: None)
    monkeypatch.setattr(transfer, "_ensure_171_subpass", lambda *a, **k: None)
    monkeypatch.setattr(transfer, "_ensure_owner_feat_strucs", lambda *a, **k: None)


def _route(monkeypatch, mode):
    calls = []
    monkeypatch.setattr(transfer, "_execute_update_semantic",
                        lambda ow, *a, **k: calls.append(("update", ow.category)) or [])
    monkeypatch.setattr(transfer, "_execute_overwrite",
                        lambda ow, *a, **k: calls.append(("overwrite", ow.category)) or [])
    ctx = RunContext(
        source_handle=object(), source_project_name="S", source_project_path="/s",
        target_handle=object(), target_project_name="T", target_project_path="/t",
        run_id="GT-20261030-120000", started_at="2026-10-30T12:00:00",
    )
    plan = RunPlan(
        context=ctx,
        selection=Selection(category_conflict_modes={"pos": mode}),
        ws_mapping=WSMapping(entries=()),
        overwrites=(PlannedOverwrite(
            category=GrammarCategory.POS, source_guid="p-1", target_guid="p-1",
            match_via="guid", write_mode="merge", summary="Merge p-1"),),
    )
    transfer.execute(plan, object(), object(), _Sink(), tag=None)
    return calls


@pytest.mark.parametrize("mode", ["merge", "update", ConflictMode.UPDATE])
def test_persisted_merge_routes_to_the_merge_executor(monkeypatch, _quiet_tail, mode):
    assert _route(monkeypatch, mode) == [("update", GrammarCategory.POS)]


def test_link_still_writes_nothing(monkeypatch, _quiet_tail):
    assert _route(monkeypatch, "link") == []


def test_pick_driven_pos_merge_is_wired():
    """`pos_plan_action` stamps merges GrammarCategory.POS; the Merge executor
    must resolve an ops accessor for it instead of the 'not wired' no-op."""
    assert transfer._OPS_ACCESSOR_FOR_CATEGORY[GrammarCategory.POS] == "POS"


def test_unwired_merges_are_one_warning_per_category(monkeypatch, _quiet_tail):
    """Measured live: 1730 SEMANTIC_DOMAINS merges planned, none applied (no
    UPDATE ops accessor). The run report says so once, as a Warning."""
    ctx = RunContext(
        source_handle=object(), source_project_name="S", source_project_path="/s",
        target_handle=object(), target_project_name="T", target_project_path="/t",
        run_id="GT-20261030-120000", started_at="2026-10-30T12:00:00",
    )
    plan = RunPlan(
        context=ctx, selection=Selection(), ws_mapping=WSMapping(entries=()),
        overwrites=tuple(PlannedOverwrite(
            category=GrammarCategory.SEMANTIC_DOMAINS, source_guid=g,
            target_guid=g, match_via="guid", write_mode="merge", summary="m")
            for g in ("sd-1", "sd-2")),
    )
    sink = _Sink()
    transfer.execute(plan, object(), object(), sink, tag=None)
    hits = [w for w in sink.warnings() if "planned merge(s) NOT applied" in w]
    assert hits == ["  [semantic_domains] 2 planned merge(s) NOT applied: the "
                    "UPDATE (Merge) executor is not wired for this category"]
