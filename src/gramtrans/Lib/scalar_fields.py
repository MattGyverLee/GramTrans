"""Issue #135 (fidelity epic): scalar/text fields flexicon's
``GetSyncableProperties`` never carries, copied GramTrans-side on create.

flexicon's per-class ``GetSyncableProperties`` omits a handful of text fields
(``LexSense.AnthroNote``/``UsageNote``, ``LexEntry.SummaryDefinition``/
``Restrictions``, ``LexEtymology.Note``/``PrecComment``, ``IText.Source``;
``LexPronunciation.CVPattern``/``Tone`` are single ``ITsString`` values). So a
transfer created the object and silently left the field empty.

This module owns the one table + the one copy routine. It is called from the
create paths (`categories._walk_lex_entry_closure` for the entry and each
top-level sense, `owned._copy_one_owned_child` for sub-senses, pronunciations
and etymologies, `texts.apply_texts` for IText.Source). Rules:

* WS-mapped: every alternative is written at the TARGET handle of its
  (``ws_map``-translated) writing system, runs/styles preserved
  (`categories._tss_remap_ws_runs`); never a raw source handle.
* An empty source value never writes anything.
* Never silent: no target WS, a raising write, or a read-back mismatch is a
  `DroppedItemRecord` on the owning object.
"""
from __future__ import annotations

if __package__:
    from .models import DroppedItemRecord
else:  # pragma: no cover - script-mode import shim
    from models import DroppedItemRecord  # type: ignore

#: owner class -> (LCM interface used to cast, IMultiString field names)
MULTISTRING_FIELDS: dict = {
    "LexEntry": ("ILexEntry", ("SummaryDefinition", "Restrictions")),
    "LexSense": ("ILexSense", ("AnthroNote", "UsageNote")),
    "LexEtymology": ("ILexEtymology", ("Note", "PrecComment")),
    "Text": ("IText", ("Source",)),
    # Slice 2: lexical-relation Name/Comment, inflectional-variant-type glosses.
    "LexReference": ("ILexReference", ("Name", "Comment")),
    "LexEntryInflType": ("ILexEntryInflType", ("GlossPrepend", "GlossAppend")),
    # Slice 3: feature-definition / symbolic-value gloss fields (IMultiUnicode).
    "FsFeatDefn": ("IFsFeatDefn", ("GlossAbbreviation", "RightGlossSep")),
    "FsSymFeatVal": ("IFsSymFeatVal", ("GlossAbbreviation", "RightGlossSep")),
}

#: owner class -> (LCM interface, single-ITsString field names)
TSSTRING_FIELDS: dict = {
    "LexPronunciation": ("ILexPronunciation", ("CVPattern", "Tone")),
}

#: owner class -> (LCM interface, int/bool field names). Copied only when the
#: source value differs from the freshly created target's value.
VALUE_FIELDS: dict = {
    "MoAlloAdhocProhib": ("IMoAdhocProhib", ("Adjacency", "Disabled")),
    "MoMorphAdhocProhib": ("IMoAdhocProhib", ("Adjacency", "Disabled")),
    "FsFeatDefn": ("IFsFeatDefn", ("ShowInGloss", "DisplayToRightOfValues")),
    "FsSymFeatVal": ("IFsSymFeatVal", ("ShowInGloss",)),
}


def _cats():
    if __package__:
        from . import categories as c
    else:  # pragma: no cover
        import categories as c  # type: ignore
    return c


def _typed(c, obj, iface):
    try:
        return c._cast_lcm(obj, iface)
    except Exception:  # noqa: BLE001 -- offline fake / no pythonnet
        return obj


def copy_supplemental_fields(owner_class, src_obj, new_obj, *, source, target,
                             ws_map, dropped, owner_guid="", owner_label=""):
    """Copy the issue #135 fields for `owner_class` from `src_obj` onto the
    freshly created `new_obj`. Returns the list of field labels written.
    Never raises; failures become DroppedItemRecords."""
    ms_spec = MULTISTRING_FIELDS.get(owner_class)
    ts_spec = TSSTRING_FIELDS.get(owner_class)
    val_spec = VALUE_FIELDS.get(owner_class)
    if (ms_spec is None and ts_spec is None and val_spec is None) or src_obj is None or new_obj is None:
        return []
    c = _cats()
    written = []
    ws_map = ws_map or {}
    src_ids = c._ws_id_by_handle(source)
    tgt_ids = c._ws_id_by_handle(target)
    tgt_handle_by_id = {i: h for h, i in tgt_ids.items()}

    def _drop(field, item, reason):
        c._append_dropped_once(dropped, DroppedItemRecord(
            owner_kind=owner_class, owner_guid=owner_guid,
            owner_label=owner_label, field_name=field, item_name=item,
            item_guid="", reason=reason))

    if ms_spec is not None:
        iface, names = ms_spec
        s, n = _typed(c, src_obj, iface), _typed(c, new_obj, iface)
        for name in names:
            try:
                src_ms = getattr(s, name, None)
                tgt_ms = getattr(n, name, None)
                if src_ms is None:
                    continue
                src_tss = c._multistring_tss_by_ws_id(src_ms, src_ids)
                src_alts = c._multistring_alts_by_ws_id(src_ms, src_ids)
            except Exception as exc:  # noqa: BLE001
                _drop(name, name, "%s unreadable on the source (%s: %s)"
                      % (name, type(exc).__name__, exc))
                continue
            if not src_alts:
                continue
            if tgt_ms is None:
                _drop(name, ", ".join(sorted(src_alts)),
                      "%s unavailable on the target %s" % (name, owner_class))
                continue
            mk = c._tss_make_string if c._is_dotnet(tgt_ms) else c._plain_make_string
            src_id_by_handle = {h: i for h, i in src_ids.items()}
            for src_ws, text in src_alts.items():
                tgt_ws = ws_map.get(src_ws, src_ws)
                handle = tgt_handle_by_id.get(tgt_ws)
                if handle is None:
                    _drop(name, tgt_ws, "no target writing system for %s "
                          "alternative %r (mapped from source %r)"
                          % (name, tgt_ws, src_ws))
                    continue
                try:
                    new_tss = None
                    st = src_tss.get(src_ws)
                    if st is not None and c._is_dotnet(tgt_ms):
                        new_tss = c._tss_remap_ws_runs(
                            st, handle, src_id_by_handle, tgt_handle_by_id,
                            ws_map)
                    tgt_ms.set_String(
                        handle, new_tss if new_tss is not None else mk(text, handle))
                    back = c._tss_read_text(tgt_ms.get_String(handle))
                except Exception as exc:  # noqa: BLE001 -- recorded
                    _drop(name, tgt_ws, "%s alternative not written (%s: %s)"
                          % (name, type(exc).__name__, exc))
                    continue
                if back is None or str(back) != text:
                    _drop(name, tgt_ws,
                          "%s alternative not present on read-back" % name)
                else:
                    written.append("%s@%s" % (name, tgt_ws))

    if ts_spec is not None:
        iface, names = ts_spec
        s, n = _typed(c, src_obj, iface), _typed(c, new_obj, iface)
        for name in names:
            try:
                src_tss = getattr(s, name, None)
                text = c._tss_read_text(src_tss) if src_tss is not None else None
            except Exception as exc:  # noqa: BLE001
                _drop(name, name, "%s unreadable on the source (%s: %s)"
                      % (name, type(exc).__name__, exc))
                continue
            if not text:
                continue
            try:
                fallback = getattr(getattr(target, "Cache", None),
                                   "DefaultVernWs", None)
                if c._is_dotnet(src_tss):
                    new_val = c._tss_remap_ws_runs(
                        src_tss, fallback, {h: i for h, i in src_ids.items()},
                        tgt_handle_by_id, ws_map)
                else:
                    new_val = text
                setattr(n, name, new_val)
                back = c._tss_read_text(getattr(n, name, None))
            except Exception as exc:  # noqa: BLE001 -- recorded
                _drop(name, name, "%s not written (%s: %s)"
                      % (name, type(exc).__name__, exc))
                continue
            if back is None or str(back) != str(text):
                _drop(name, name, "%s not present on read-back" % name)
            else:
                written.append(name)

    if val_spec is not None:
        iface, names = val_spec
        s, n = _typed(c, src_obj, iface), _typed(c, new_obj, iface)
        for name in names:
            try:
                want = getattr(s, name, None)
                if want is None or want == getattr(n, name, None):
                    continue
                setattr(n, name, want)
                back = getattr(n, name, None)
            except Exception as exc:  # noqa: BLE001 -- recorded
                _drop(name, name, "%s not written (%s: %s)"
                      % (name, type(exc).__name__, exc))
                continue
            if back != want:
                _drop(name, name, "%s not present on read-back" % name)
            else:
                written.append(name)
    return written
