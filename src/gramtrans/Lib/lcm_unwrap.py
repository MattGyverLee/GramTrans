"""Shared flexicon-wrapper unwrap helper (issue #130 follow-up).

flexicon's ``LCMObjectWrapper`` keeps the raw LCM object in ``_concrete`` (a
concrete-interface cast) and ``_obj`` (the base interface). Only a few wrapper
classes (AffixTemplate, CompoundRule, Allomorph) expose a public ``.concrete``;
``AffixSlot`` and others do not, so a ``.concrete``-only unwrap returned the
WRAPPER unchanged and ``SlotsRC.Add(wrapper)`` failed on a live LCM.
"""
from __future__ import annotations

from typing import Any


def unwrap(obj: Any) -> Any:
    """Return the raw LCM object behind a flexicon wrapper.

    Order: ``.concrete`` -> ``_concrete`` -> ``_obj`` -> ``obj`` itself.
    Raw LCM objects and offline fakes lacking all three pass through unchanged.
    """
    if obj is None:
        return None
    for attr in ("concrete", "_concrete", "_obj"):
        try:
            inner = getattr(obj, attr, None)
        except Exception:  # noqa: BLE001 -- hostile __getattr__
            inner = None
        if inner is not None:
            return inner
    return obj
