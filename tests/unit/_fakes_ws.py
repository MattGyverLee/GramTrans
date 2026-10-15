"""Shared fake of ``flexicon.WritingSystemOperations`` faithful to flexicon
>= 4.8.0 (issue #250).

The "project" is a plain dict:

* ``store``   -- tags with an LDML in the writing-system store (list)
* ``active``  -- tags in the active vernacular/analysis lists (list)
* ``created`` -- ``(tag, name, is_vernacular)`` for every ``Create`` call that
  made a NEW writing system (a stored tag being re-activated is NOT recorded)
* ``activated`` -- tags a ``Create`` call re-activated from the store
* ``refuse``  -- tags whose ``Create`` raises RuntimeError
* ``names``   -- optional Id -> display name for ``GetDisplayName``
* ``no_activate`` -- tags whose ``Create`` silently leaves them inactive

Real semantics modelled: ``GetAll`` is the active list; ``Exists`` is
ACTIVE-ONLY; ``ExistsInStore`` checks store membership; ``Create`` on a stored
tag only activates it (``name`` ignored).
"""
from __future__ import annotations


class FakeWS:
    def __init__(self, ws_id: str) -> None:
        self.Id = ws_id


def make_project(active=(), store=None, **extra) -> dict:
    active = list(active)
    proj = {"store": list(store) if store is not None else list(active),
            "active": active, "created": [], "activated": []}
    for t in active:
        if t not in proj["store"]:
            proj["store"].append(t)
    proj.update(extra)
    return proj


class FakeWSOps:
    def __init__(self, proj: dict) -> None:
        self.proj = proj

    def GetAll(self):  # noqa: N802
        return [FakeWS(i) for i in self.proj["active"]]

    def Exists(self, tag):  # noqa: N802 -- active-only since flexicon 4.8.0
        return tag in self.proj["active"]

    def ExistsInStore(self, tag):  # noqa: N802
        return tag in self.proj["store"]

    def GetDisplayName(self, ws):  # noqa: N802
        return self.proj.get("names", {}).get(ws.Id, "")

    def Create(self, tag, name, is_vernacular=True):  # noqa: N802
        if tag in self.proj.get("refuse", ()):
            raise RuntimeError(f"cannot create {tag}")
        if tag in self.proj["store"]:
            # Reuse the stored LDML: activate only; `name` is ignored.
            if tag in self.proj.get("no_activate", ()):
                return FakeWS(tag)
            if tag not in self.proj["active"]:
                self.proj["active"].append(tag)
                self.proj["activated"].append(tag)
            return FakeWS(tag)
        self.proj["store"].append(tag)
        self.proj["active"].append(tag)
        self.proj["created"].append((tag, name, is_vernacular))
        return FakeWS(tag)


class FakeWSOpsNoStore(FakeWSOps):
    """flexicon < 4.8.0: no ExistsInStore attribute at all."""

    def __getattribute__(self, name):
        if name == "ExistsInStore":
            raise AttributeError(name)
        return super().__getattribute__(name)
