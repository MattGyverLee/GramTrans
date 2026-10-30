"""Shared fakes for the 027 LexEntryRef (complex forms & variants) unit tests.

Issue #32 (P2 test-fixture DRY): `_FakeRefSeq`, the guid-only lexeme fake,
`_make_ctx`, `_ref_record` and the `_ctx_create` / `_ctx_create_and_wire`
plan-carrying contexts were copied, with small drifts, across
``test_027_entryref_reproduction.py``, ``test_027_entry_type_resolve.py`` and
``test_phase3c_post_pass_a.py``. They live here once; each test module
imports them under its historical private names.

No pythonnet required: every fake exposes a lowercase ``.guid`` so
``categories._guid_str_from`` resolves host-free.
"""
from __future__ import annotations

import types

from gramtrans.Lib.models import RunContext


class FakeRefSeq:
    """LCM owning/reference sequence stand-in: records Add calls in order."""

    def __init__(self, initial=()) -> None:
        self._items = list(initial)
        self.add_log = []

    def Add(self, obj) -> None:
        self._items.append(obj)
        self.add_log.append(obj)

    def __iter__(self):
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    @property
    def Count(self) -> int:
        return len(self._items)


class FakeLexeme:
    """Anything addressed by GUID and referenced as a component/primary/
    show-in lexeme (entry or sense)."""

    def __init__(self, guid: str) -> None:
        self.guid = guid


def make_ctx(run_id: str = "GT-20260713-000000",
             started_at: str = "2026-07-13T00:00:00") -> RunContext:
    return RunContext(
        source_handle=object(),
        source_project_name="Src",
        source_project_path="/src",
        target_handle=object(),
        target_project_name="Tgt",
        target_project_path="/tgt",
        run_id=run_id,
        started_at=started_at,
    )


def ref_record(ref_guid, ref_type=0, components=(), primaries=(),
               variant_entry_types=(), complex_entry_types=(),
               show_complex_forms_in=()):
    """One `plan.entryref_create_bindings` per-ref record (data-model.md);
    `show_complex_forms_in` holds lexeme GUIDs (issue #32)."""
    return {
        "ref_guid": ref_guid,
        "ref_type": ref_type,
        "components": list(components),
        "primaries": list(primaries),
        "variant_entry_types": list(variant_entry_types),
        "complex_entry_types": list(complex_entry_types),
        "show_complex_forms_in": list(show_complex_forms_in),
    }


def ctx_create_and_wire(entryref_create_bindings, lexentry_ref_bindings=None,
                        identity_remap=None, in_plan_entries=None,
                        dropped=None, ctx=None) -> RunContext:
    """A context whose `_run_plan` carries everything C1
    (`_run_entryref_create_pass`) and C2 (`_run_post_pass_a`) read, so both
    can run over the SAME ctx in the STEMS-tail create-then-wire order."""
    ctx = ctx if ctx is not None else make_ctx()
    plan = types.SimpleNamespace(
        entryref_create_bindings={
            k: list(v) for k, v in entryref_create_bindings.items()
        },
        lexentry_ref_bindings=dict(lexentry_ref_bindings or {}),
        in_plan_entries=dict(in_plan_entries or {}),
        identity_remap=dict(identity_remap or {}),
    )
    object.__setattr__(ctx, "_run_plan", plan)
    object.__setattr__(ctx, "_dropped", [] if dropped is None else dropped)
    return ctx
