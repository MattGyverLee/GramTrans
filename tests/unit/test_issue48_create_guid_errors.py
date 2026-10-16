"""Issue #48 -- a failed factory.Create(Guid) must not be reported as a missing API.

A real failure (System.InvalidOperationException "Can not create more than one
object with identical GUIDs": the GUID was already in the target) used to be
reported as "IPhSimpleContextNCFactory does not support Create(Guid)".  Only
AttributeError / TypeError (pythonnet's "no such method / no matching overload")
mean "API missing"; everything else must carry the real type and text.

Host-free: fake factories and a fake target, no LCM.  A stub `System.Guid` is
injected so the helpers' `from System import Guid` works without pythonnet.
"""
from __future__ import annotations

import sys
import types

import pytest

from gramtrans.Lib import categories

GUID = "11111111-2222-3333-4444-555555555555"
DUP_TEXT = "Can not create more than one object with identical GUIDs"


class InvalidOperationException(Exception):
    """Stands in for System.InvalidOperationException (matched by name)."""


class _DotNetLike(Exception):
    """Mimics a pythonnet-wrapped .NET exception exposing GetType().FullName."""

    def GetType(self):
        return types.SimpleNamespace(FullName="System.InvalidOperationException")


class _Factory:
    def __init__(self, exc):
        self._exc = exc

    def Create(self, guid):
        if self._exc is not None:
            raise self._exc
        return types.SimpleNamespace(Guid=guid)


def _target(exc):
    factory = _Factory(exc)
    locator = types.SimpleNamespace(GetService=lambda iface: factory)
    return types.SimpleNamespace(Cache=types.SimpleNamespace(ServiceLocator=locator))


class _IFake:
    __name__ = "IFakeFactory"


class _Owner:
    def __init__(self):
        self.items = []

    def Add(self, obj):
        self.items.append(obj)


@pytest.fixture(autouse=True)
def _stub_system(monkeypatch):
    mod = types.ModuleType("System")
    mod.Guid = types.SimpleNamespace(Parse=lambda s: s)
    monkeypatch.setitem(sys.modules, "System", mod)


def _call_with_guid(exc):
    return categories._create_with_guid(_IFake, _Owner(), GUID, _target(exc))


def _call_with_guid_oa(exc):
    return categories._create_with_guid_oa(_IFake, GUID, _target(exc))


CALLERS = [_call_with_guid, _call_with_guid_oa]


@pytest.mark.parametrize("caller", CALLERS)
@pytest.mark.parametrize("exc", [TypeError("no overload"), AttributeError("no Create")])
def test_api_missing_shapes_keep_does_not_support(caller, exc):
    with pytest.raises(RuntimeError) as ei:
        caller(exc)
    msg = str(ei.value)
    assert "does not support Create(Guid)" in msg
    assert GUID in msg
    assert ei.value.__cause__ is exc


@pytest.mark.parametrize("caller", CALLERS)
def test_duplicate_guid_passes_real_error_through(caller):
    exc = InvalidOperationException(DUP_TEXT)
    with pytest.raises(RuntimeError) as ei:
        caller(exc)
    msg = str(ei.value)
    assert "InvalidOperationException" in msg
    assert DUP_TEXT in msg
    assert "does not support" not in msg
    assert "already exists in the target" in msg
    assert ei.value.__cause__ is exc


@pytest.mark.parametrize("caller", CALLERS)
def test_normal_path_unchanged(caller):
    result = caller(None)
    obj = result[0] if isinstance(result, tuple) else result
    assert obj.Guid == GUID


def test_helper_returns_not_raises():
    err = categories._create_guid_failure("F", GUID, TypeError("x"))
    assert isinstance(err, RuntimeError)


def test_helper_prefers_dotnet_full_name():
    err = categories._create_guid_failure("F", GUID, _DotNetLike(DUP_TEXT))
    assert "System.InvalidOperationException: " + DUP_TEXT in str(err)
    assert "does not support" not in str(err)


def test_helper_other_failure_no_duplicate_hint():
    err = categories._create_guid_failure("F", GUID, ValueError("boom"))
    msg = str(err)
    assert "ValueError: boom" in msg
    assert "does not support" not in msg
    assert "already exists" not in msg


def test_helper_keeps_detail_on_both_paths():
    note = "(a no-GUID create would produce a duplicate feature on re-run)"
    api = categories._create_guid_failure("F", GUID, TypeError("x"), detail=note)
    real = categories._create_guid_failure("F", GUID, ValueError("y"), detail=note)
    assert note in str(api) and "does not support" in str(api)
    assert note in str(real) and "does not support" not in str(real)


# ---------------------------------------------------------------------------
# Hand-rolled Create(Guid) sites (not routed through _create_with_guid*):
# driven through the real *_execute_action entry points with a stubbed
# SIL.LCModel, fake handles, and a factory whose Create raises.
# ---------------------------------------------------------------------------

_FACTORY_NAMES = (
    "IFsClosedFeatureFactory", "IFsSymFeatValFactory", "IFsComplexFeatureFactory",
    "IMoInflClassFactory", "IMoStemNameFactory",
)
_IDENTITY_NAMES = (
    "IFsClosedFeature", "IFsSymFeatVal", "IFsComplexFeature", "IMoInflClass",
    "IMoStemName", "IPartOfSpeech", "ICmObject",
)


@pytest.fixture
def lcm(monkeypatch):
    """Stub SIL.LCModel: factory interfaces are distinct markers, casts are identity."""
    mod = types.ModuleType("SIL.LCModel")
    for n in _FACTORY_NAMES:
        setattr(mod, n, type(n, (), {}))
    for n in _IDENTITY_NAMES:
        setattr(mod, n, lambda o: o)
    sil = types.ModuleType("SIL")
    sil.LCModel = mod
    monkeypatch.setitem(sys.modules, "SIL", sil)
    monkeypatch.setitem(sys.modules, "SIL.LCModel", mod)
    return mod


def _classify(call, exc_kind):
    """Run `call(exc)`; return the RuntimeError for the given failure shape."""
    exc = (InvalidOperationException(DUP_TEXT) if exc_kind == "dup"
           else TypeError("no overload"))
    with pytest.raises(RuntimeError) as ei:
        call(exc)
    assert ei.value.__cause__ is exc
    return str(ei.value)


def _check(msg, factory_name, exc_kind, guid=GUID):
    assert factory_name in msg
    assert guid in msg
    if exc_kind == "dup":
        assert "InvalidOperationException" in msg
        assert DUP_TEXT in msg
        assert "does not support" not in msg
    else:
        assert "does not support Create(Guid)" in msg


class _Coll(list):
    def Add(self, o):
        self.append(o)


def _services(lcm, **by_name):
    """GetService(iface) -> the fake registered under iface.__name__."""
    reg = {getattr(lcm, k): v for k, v in by_name.items()}
    return types.SimpleNamespace(GetService=lambda iface: reg[iface])


def _handle(services):
    cache = types.SimpleNamespace(
        DefaultAnalWs=1, ServiceLocator=services,
        LangProject=types.SimpleNamespace(
            MsFeatureSystemOA=types.SimpleNamespace(FeaturesOC=_Coll())))
    infl = types.SimpleNamespace(
        GetSyncableProperties=lambda o: {},
        ApplySyncableProperties=lambda *a, **k: None)
    return types.SimpleNamespace(Cache=cache, InflectionFeatures=infl)


def _run_features(lcm, src_feat, **factories):
    source = types.SimpleNamespace(
        InflectionFeatures=types.SimpleNamespace(
            FeatureGetAll=lambda: [src_feat],
            GetSyncableProperties=lambda o: {}))
    target = _handle(_services(lcm, **factories))
    ctx = types.SimpleNamespace(source_handle=source, target_handle=target)
    action = types.SimpleNamespace(source_guid=GUID)
    return categories.inflection_features_execute_action(action, ctx, {}, None)


@pytest.mark.parametrize("kind", ["dup", "api"])
def test_complex_feature_site(lcm, kind):
    feat = types.SimpleNamespace(guid=GUID, ClassName="FsComplexFeature")
    msg = _classify(
        lambda e: _run_features(lcm, feat, IFsComplexFeatureFactory=_Factory(e)), kind)
    _check(msg, "IFsComplexFeatureFactory", kind)


@pytest.mark.parametrize("kind", ["dup", "api"])
def test_closed_feature_site(lcm, kind):
    feat = types.SimpleNamespace(guid=GUID, ClassName="FsClosedFeature", ValuesOC=[])
    msg = _classify(
        lambda e: _run_features(lcm, feat, IFsClosedFeatureFactory=_Factory(e),
                                IFsSymFeatValFactory=_Factory(None)), kind)
    _check(msg, "IFsClosedFeatureFactory", kind)


@pytest.mark.parametrize("kind", ["dup", "api"])
def test_sym_feat_val_site(lcm, kind):
    val_guid = "99999999-2222-3333-4444-555555555555"
    val = types.SimpleNamespace(guid=val_guid)
    feat = types.SimpleNamespace(guid=GUID, ClassName="FsClosedFeature", ValuesOC=[val])
    msg = _classify(
        lambda e: _run_features(
            lcm, feat,
            IFsClosedFeatureFactory=types.SimpleNamespace(
                Create=lambda g: types.SimpleNamespace(guid=g, ValuesOC=_Coll())),
            IFsSymFeatValFactory=_Factory(e)), kind)
    _check(msg, "IFsSymFeatValFactory", kind, guid=val_guid)


def _pos_source(**owned):
    pos = types.SimpleNamespace(guid="aaaaaaaa-0000-0000-0000-000000000000", **owned)
    pos.Guid = pos.guid
    return types.SimpleNamespace(
        POS=types.SimpleNamespace(GetAll=lambda recursive=True: [pos]))


@pytest.mark.parametrize("kind", ["dup", "api"])
def test_inflection_class_site(lcm, monkeypatch, kind):
    item = types.SimpleNamespace(guid=GUID)
    source = _pos_source(InflectionClassesOC=[item])
    target_pos = types.SimpleNamespace(InflectionClassesOC=_Coll())
    monkeypatch.setattr(categories, "_resolve_target_pos", lambda *a, **k: target_pos)

    def call(e):
        target = _handle(_services(lcm, IMoInflClassFactory=_Factory(e)))
        ctx = types.SimpleNamespace(source_handle=source, target_handle=target)
        return categories.inflection_classes_execute_action(
            types.SimpleNamespace(source_guid=GUID), ctx, {}, None)

    _check(_classify(call, kind), "IMoInflClassFactory", kind)


@pytest.mark.parametrize("kind", ["dup", "api"])
def test_stem_name_site(lcm, monkeypatch, kind):
    item = types.SimpleNamespace(guid=GUID)
    source = _pos_source(StemNamesOC=[item])
    target_pos = types.SimpleNamespace(StemNamesOC=_Coll())
    monkeypatch.setattr(categories, "_target_pos_for_source_guid",
                        lambda *a, **k: target_pos)

    def call(e):
        target = _handle(_services(lcm, IMoStemNameFactory=_Factory(e)))
        ctx = types.SimpleNamespace(source_handle=source, target_handle=target)
        return categories.stem_names_execute_action(
            types.SimpleNamespace(source_guid=GUID), ctx, {}, None)

    _check(_classify(call, kind), "IMoStemNameFactory", kind)


# ---------------------------------------------------------------------------
# Issue #71: first-line trim of the surfaced .NET message, and the variant-
# type / complex-form-type / semantic-domain sites routed through the helper.
# ---------------------------------------------------------------------------

def test_helper_trims_stack_trace_line_keeps_type():
    exc = _DotNetLike(DUP_TEXT + "\n   at SIL.LCModel.Foo.Create()\n   at Bar")
    msg = str(categories._create_guid_failure("F", GUID, exc))
    assert "System.InvalidOperationException: " + DUP_TEXT in msg
    assert "\n" not in msg
    assert "   at " not in msg
    assert "already exists in the target" in msg


def test_helper_trims_plain_exception_multiline():
    msg = str(categories._create_guid_failure(
        "F", GUID, ValueError("first line\nsecond line")))
    assert "ValueError: first line" in msg
    assert "second line" not in msg


def test_create_guid_sites_use_the_helper():
    """The three hand-rolled `Create(Guid) failed ... {e!r}` strings are gone."""
    import inspect
    for fn in (categories.variant_types_execute_action,
               categories.complex_form_types_execute_action,
               categories.semantic_domains_execute_action):
        src = inspect.getsource(fn)
        assert "_create_guid_failure(" in src, fn.__name__
        assert "Create(Guid) failed for" not in src, fn.__name__
