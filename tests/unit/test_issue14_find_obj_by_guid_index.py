"""Issue #14 (NEW-3): _find_obj_by_guid builds one guid index per ops."""
from gramtrans.Lib import transfer


class _Obj:
    def __init__(self, guid):
        self.Guid = guid


class _Ops:
    def __init__(self, objs):
        self.objs = objs
        self.calls = 0

    def GetAll(self):
        self.calls += 1
        return list(self.objs)


def test_uncached_lookup_finds_and_misses():
    ops = _Ops([_Obj("AAA"), _Obj("bbb")])
    assert transfer._find_obj_by_guid(ops, "aaa") is ops.objs[0]
    assert transfer._find_obj_by_guid(ops, "zzz") is None


def test_cached_lookup_scans_once_for_hits():
    ops = _Ops([_Obj(f"g{i}") for i in range(50)])
    cache = {}
    for i in range(50):
        assert transfer._find_obj_by_guid(ops, f"G{i}", cache) is ops.objs[i]
    assert ops.calls == 1


def test_cached_miss_rescans_and_finds_late_object():
    ops = _Ops([_Obj("a")])
    cache = {}
    assert transfer._find_obj_by_guid(ops, "a", cache) is not None
    late = _Obj("late")
    ops.objs.append(late)
    assert transfer._find_obj_by_guid(ops, "late", cache) is late


def test_getall_raising_returns_none():
    class Bad:
        def GetAll(self):
            raise RuntimeError("x")
    assert transfer._find_obj_by_guid(Bad(), "a", {}) is None
