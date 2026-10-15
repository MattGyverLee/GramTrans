"""Issue #38: ``_closed_value_label`` must label ``FsComplexValue`` specs.

Display-only (Preview merge pane).  All fakes are duck-typed; ``_lcm_cast``
returns the object unchanged when SIL.LCModel is unavailable (headless).
"""

from __future__ import annotations

from gramtrans.Lib.merge_preview import (
    _closed_value_label,
    _natural_class_features,
    _phoneme_feature_labels,
)


class _Defn:
    def __init__(self, abbr="", name=""):
        self.Abbreviation = {"en": abbr} if abbr else {}
        self.Name = {"en": name} if name else {}


class _Closed:
    """Duck-typed IFsClosedValue."""

    def __init__(self, long_name=None, feat=None, val=None, class_name=None):
        if class_name is not None:
            self.ClassName = class_name
        if long_name is not None:
            self.LongName = long_name
        if feat is not None:
            self.FeatureRA = _Defn(abbr=feat)
        if val is not None:
            self.ValueRA = _Defn(abbr=val)


class _FeatStruc:
    def __init__(self, specs, long_name=None):
        self.FeatureSpecsOC = specs
        if long_name is not None:
            self.LongName = long_name


class _Complex:
    """Duck-typed IFsComplexValue: FeatureRA + owned ValueOA feature struct."""

    def __init__(self, feat=None, value=None, long_name=None, class_name=None):
        if class_name is not None:
            self.ClassName = class_name
        if long_name is not None:
            self.LongName = long_name
        if feat is not None:
            self.FeatureRA = _Defn(abbr=feat)
        self.ValueOA = value


class _BaseProxy:
    """Mimics a live base-interface proxy: ClassName + FeatureRA visible, but
    the derived-only LongName / ValueOA are not (cast is a no-op headless)."""

    ClassName = "FsComplexValue"

    def __init__(self, feat):
        self.FeatureRA = _Defn(abbr=feat)


class _Exploding:
    ClassName = "FsComplexValue"

    @property
    def LongName(self):
        raise RuntimeError("boom")

    @property
    def FeatureRA(self):
        raise RuntimeError("boom")

    @property
    def ValueOA(self):
        raise RuntimeError("boom")


class TestComplexValueLabel:
    def test_prefers_longname(self):
        cv = _Complex(long_name="nagr:[BantuSG:3 BantuPl:4]",
                      class_name="FsComplexValue")
        assert _closed_value_label(cv) == "nagr:[BantuSG:3 BantuPl:4]"

    def test_feature_plus_nested_fs_longname(self):
        cv = _Complex(feat="sbj", value=_FeatStruc([], long_name="[pers:1 num:sg]"))
        assert _closed_value_label(cv) == "sbj:[pers:1 num:sg]"

    def test_feature_plus_nested_specs_sorted(self):
        cv = _Complex(feat="nagr", value=_FeatStruc([
            _Closed(feat="BantuSG", val="3"),
            _Closed(long_name="BantuPl:4"),
        ]))
        assert _closed_value_label(cv) == "nagr:[BantuPl:4 BantuSG:3]"

    def test_nested_complex_recurses(self):
        inner = _Complex(feat="sbj", value=_FeatStruc([
            _Closed(feat="pers", val="1"),
        ]))
        cv = _Complex(feat="agr", value=_FeatStruc([inner]),
                      class_name="FsComplexValue")
        assert _closed_value_label(cv) == "agr:[sbj:[pers:1]]"

    def test_empty_nested_fs_gives_feature_name(self):
        cv = _Complex(feat="nagr", value=_FeatStruc([]))
        assert _closed_value_label(cv) == "nagr"

    def test_no_value_gives_feature_name(self):
        assert _closed_value_label(_Complex(feat="nagr", value=None)) == "nagr"

    def test_base_proxy_degrades_to_feature_name(self):
        # Headless, the cast cannot expose ValueOA; never raise, never blank
        # when the feature is readable.
        assert _closed_value_label(_BaseProxy("nagr")) == "nagr"

    def test_never_raises(self):
        assert _closed_value_label(_Exploding()) == ""
        assert _closed_value_label(None) == ""

    def test_depth_guard_terminates(self):
        # Self-referential nesting must not recurse forever.
        fs = _FeatStruc([])
        cv = _Complex(feat="loop", value=fs)
        fs.FeatureSpecsOC = [cv]
        label = _closed_value_label(cv)
        assert label.startswith("loop:[loop:[")

    def test_complex_in_phoneme_and_nc_feature_lists(self):
        class _Holder:
            def __init__(self, specs):
                self.FeaturesOA = _FeatStruc(specs)

        specs = [
            _Closed(long_name="high:+"),
            _Complex(feat="nagr", value=_FeatStruc([_Closed(feat="BantuSG", val="1")])),
        ]
        assert _phoneme_feature_labels(_Holder(specs)) == [
            "high:+", "nagr:[BantuSG:1]"]
        assert _natural_class_features(_Holder(specs)) == [
            "high:+", "nagr:[BantuSG:1]"]


class TestClosedValueUnchanged:
    def test_longname(self):
        assert _closed_value_label(_Closed(long_name="high:+")) == "high:+"

    def test_longname_with_classname(self):
        cv = _Closed(long_name="voice:-", class_name="FsClosedValue")
        assert _closed_value_label(cv) == "voice:-"

    def test_abbreviation_fallback(self):
        assert _closed_value_label(_Closed(feat="ATR", val="+")) == "ATR:+"

    def test_partial_fallbacks(self):
        assert _closed_value_label(_Closed(feat="ATR")) == "ATR"
        assert _closed_value_label(_Closed(val="+")) == "+"

    def test_nothing_readable(self):
        assert _closed_value_label(_Closed()) == ""
