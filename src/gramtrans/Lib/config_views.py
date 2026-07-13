"""Part B -- dictionary + reversal `.fwdictconfig` configuration-view file
copy (feature 025-full-reversals).

Copies the source project's dictionary and reversal configuration views --
the `.fwdictconfig` XML files under
`<project>/ConfigurationSettings/Dictionary/` and `.../ReversalIndex/` --
into the target project's corresponding directories. These are sidecar
files, not LCM objects, so this module is a plain file-I/O path (outside the
flexicon surface; Principle II does not apply here -- see plan.md
Constitution Check, Principle II row).

Each config file references writing systems (`writingSystem="en"`, WS option
ids), custom fields (by name), and paragraph/character styles; planning
reports any such reference the target does not hold (a config referencing a
custom field or WS the target lacks) rather than silently importing a
broken view -- see specs/025-full-reversals/contracts/config-view-copy.md.

Plan/apply split (Principle III, Preview-before-mutate):
- `plan_config_views` (decision-only, no file writes, NO DIRECTORY
  CREATION on either project tree -- P0-1, feature-025 cycle-6
  remediation) enumerates source configs via the pure `compute_config_
  dirs` path helper, computes Add/Overwrite/Skip per file (via `filecmp`),
  and scans each file's references against the target, producing
  `ConfigViewRecord`s (see `models.ConfigViewRecord`). A non-existent
  `ConfigurationSettings/` folder on either side (e.g. a brand-new target)
  simply yields an empty file listing for that side -- Preview never
  creates it.
- `apply_config_views` (Move-mode only) performs the actual file copies:
  `shutil.copy2` for ADD/OVERWRITE, backing up any replaced target file
  first; SKIP performs no I/O. This is also the only place any directory
  gets created (per-file `os.makedirs` right before each ADD/OVERWRITE
  copy).

Schema notes (US3 T031/T032, confirmed against the actual FieldWorks source
-- `Src/xWorks/ConfigurableDictionaryNode.cs` -- and live `.fwdictconfig`
files on Ejagham Mini / arz-flex / blx-flex, 2026-07-12, NOT reverse-
engineered from the XML alone):
  - `field="…"` / `style="…"` / `isCustomField="true"` are all plain XML
    attributes on `<ConfigurationItem>` elements (`[XmlAttribute(...)]` on
    `ConfigurableDictionaryNode`); a node only represents a *custom* field
    when `isCustomField="true"` is present (`ShouldSerializeIsCustomField`
    omits the attribute entirely when false) -- the `field` value alone
    does NOT distinguish a custom field from a built-in LCM property name.
  - `<Option id="…">` under a `<WritingSystemOptions>` parent carries either
    a real writing-system tag (e.g. "en") OR one of a small set of "magic"
    default-WS-group tokens (`analysis`, `vernacular`, `pronunciation`,
    `reversal`, `all analysis`, `all vernacular`, `best vernoranal`,
    `best analorvern` -- confirmed via
    `DictionaryConfigurationController.cs`'s WS-type switch). Magic tokens
    are never real WS ids and must never be reported as missing.
  - The `writingSystem="…"` attribute on the ROOT `<DictionaryConfiguration>`
    element (this file's own display-language WS, e.g. "en" for
    `ReversalIndex/en.fwdictconfig`) is a genuine WS id and IS checked.
"""
from __future__ import annotations

import os
import shutil
import filecmp
import xml.etree.ElementTree as ET
from typing import List, Optional, Set

if __package__:
    from .models import ConfigViewAction, ConfigViewRecord, DroppedItemRecord
else:
    from models import ConfigViewAction, ConfigViewRecord, DroppedItemRecord  # type: ignore


# ============================================================================
# Directory resolution (T031)
# ============================================================================

_SUBDIR_NAMES = {
    "Dictionary": "Dictionary",
    "ReversalIndex": "ReversalIndex",
}


def _project_dir(project) -> str:
    """Best-effort extraction of a flexicon project's on-disk directory (the
    folder that contains `ConfigurationSettings/`).

    Tries, in order:
    1. The underlying LCM cache's project path (`project.project.ProjectId
       .Path`, the `.fwdata` file path) -- the same accessor `Lib/api.py`
       already uses for schema-close diagnostics; its directory IS the
       project directory.
    2. Duck-typed attributes mirroring `Lib/ui/main_window.py._safe_path`'s
       convention (`ProjectPath` / `ProjectFilename` / `ProjectFolder`):
       if the value looks like a file (has an extension), its directory is
       used; otherwise the value is assumed to already be the project
       directory (this is the shape unit-test fakes use, and the shape a
       plain wrapper exposing a folder path would use).

    Raises ValueError if no accessor yields a usable path -- callers
    (`resolve_config_dirs`) have nothing sensible to fall back to.
    """
    try:
        cache_path = str(project.project.ProjectId.Path)
        if cache_path:
            return os.path.dirname(cache_path)
    except (AttributeError, TypeError):
        pass
    for attr in ("ProjectPath", "ProjectFilename", "ProjectFolder"):
        try:
            value = getattr(project, attr)
        except AttributeError:
            continue
        value = value() if callable(value) else value
        if not value:
            continue
        value = str(value)
        _, ext = os.path.splitext(value)
        return os.path.dirname(value) if ext else value
    raise ValueError(
        "config_views: could not derive an on-disk project directory from "
        "the given project handle (tried ProjectId.Path, ProjectPath, "
        "ProjectFilename, ProjectFolder)"
    )


def compute_config_dirs(project):
    """Pure path computation -- derive `(dictionary_dir, reversal_dir)`
    absolute paths for a flexicon project handle (R8, contracts/config-
    view-copy.md) WITHOUT creating either directory and WITHOUT any other
    filesystem side effect.

    This is the ONLY directory-path helper `plan_config_views` may call
    (P0-1, feature-025 cycle-6 remediation): Preview's decision pass runs
    this against BOTH the source and target project handles, and creating
    a directory on the SOURCE tree during Preview would violate `Lib/
    preview.py`'s read-only guarantee (Principle III) as well as
    `contracts/config-view-copy.md`:13's "target only" mutation scope.
    """
    project_dir = _project_dir(project)
    dictionary_dir = os.path.join(project_dir, "ConfigurationSettings", "Dictionary")
    reversal_dir = os.path.join(project_dir, "ConfigurationSettings", "ReversalIndex")
    return (os.path.abspath(dictionary_dir), os.path.abspath(reversal_dir))


def resolve_config_dirs(project):
    """Derive `(dictionary_dir, reversal_dir)` absolute paths for a
    flexicon project handle (R8, contracts/config-view-copy.md), creating
    both subdirectories if they do not already exist (a brand-new target
    project may not have a `ConfigurationSettings` folder at all yet).

    Directory-CREATING wrapper around `compute_config_dirs`. This function
    has no call site inside this module as of P0-1 (feature-025 cycle-6
    remediation) -- `plan_config_views` (Preview, read-only) now calls the
    pure `compute_config_dirs` for both src and tgt, and `apply_config_
    views` (Move-only) already does its own per-file `os.makedirs` right
    before each copy, so no plan-time directory creation is needed. Kept
    for any external/future caller that genuinely wants "give me a real,
    already-existing directory" semantics -- but NEVER call this against a
    SOURCE project handle from a read-only code path.
    """
    dictionary_dir, reversal_dir = compute_config_dirs(project)
    os.makedirs(dictionary_dir, exist_ok=True)
    os.makedirs(reversal_dir, exist_ok=True)
    return (dictionary_dir, reversal_dir)


# ============================================================================
# Target introspection helpers for the R9 reference scan
# ============================================================================
#
# Each returns `None` when the target handle can't answer the question at
# all (duck-typing gap) -- callers treat `None` as "unknown, don't report"
# rather than "empty, everything is missing", so a target double that simply
# doesn't expose a given surface never produces false-positive drops.

def _target_ws_ids(project) -> Optional[Set[str]]:
    try:
        return {str(w.Id) for w in project.WritingSystems.GetAll()}
    except (AttributeError, TypeError):
        return None


def _custom_field_label(rec) -> Optional[str]:
    """Best-effort label extraction from one `CustomFields.GetAllFields()`
    row -- tolerates a bare string, a `(cls, field)`-shaped tuple/list (the
    2-tuple shape `Lib/categories.py._enumerate_custom_fields` already
    documents flexicon returning), or a field-record object exposing
    `Label`/`Name`/`name`."""
    if isinstance(rec, str):
        return rec or None
    if isinstance(rec, (tuple, list)):
        rec = rec[-1] if rec else None
    if rec is None:
        return None
    if isinstance(rec, str):
        return rec or None
    return getattr(rec, "Label", None) or getattr(rec, "Name", None) or getattr(rec, "name", None)


def _target_custom_field_names(project) -> Optional[Set[str]]:
    cf_ops = getattr(project, "CustomFields", None)
    if cf_ops is None:
        return None
    try:
        names = set()
        for rec in cf_ops.GetAllFields():
            label = _custom_field_label(rec)
            if label:
                names.add(label)
        return names
    except (AttributeError, TypeError):
        return None


def _target_style_names(project) -> Optional[Set[str]]:
    styles = getattr(project, "Styles", None)
    if styles is None:
        try:
            styles = project.Cache.LangProject.StylesOC
        except (AttributeError, TypeError):
            return None
    try:
        names = set()
        for s in styles:
            name = s if isinstance(s, str) else (getattr(s, "Name", None) or getattr(s, "name", None))
            if name:
                names.add(str(name))
        return names
    except TypeError:
        return None


# WS `Option id` tokens that denote a *default WS group* rather than a real
# writing-system tag (R9) -- confirmed against
# `Src/xWorks/DictionaryConfigurationController.cs`'s WS-type switch, 2026-07-12.
_WS_MAGIC_TOKENS = frozenset({
    "vernacular", "analysis", "reversal", "pronunciation",
    "all vernacular", "all analysis",
    "best vernoranal", "best analorvern",
})


def _local_tag(tag: str) -> str:
    """Strip a `{namespace}` prefix if ElementTree attached one (defensive;
    `.fwdictconfig` files observed so far declare xsi/xsd namespaces for
    attribute use only, so plain element tags are the norm)."""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


# ============================================================================
# Plan (T031)
# ============================================================================

def _list_fwdictconfig(directory: str) -> List[str]:
    if not os.path.isdir(directory):
        return []
    return sorted(f for f in os.listdir(directory) if f.endswith(".fwdictconfig"))


def _plan_action(src_path: str, tgt_path: str) -> ConfigViewAction:
    if not os.path.exists(tgt_path):
        return ConfigViewAction.ADD
    if filecmp.cmp(src_path, tgt_path, shallow=False):
        return ConfigViewAction.SKIP
    return ConfigViewAction.OVERWRITE


def _scan_missing_refs(
    src_path: str,
    filename: str,
    tgt_ws_ids: Optional[Set[str]],
    tgt_field_names: Optional[Set[str]],
    tgt_style_names: Optional[Set[str]],
) -> List[DroppedItemRecord]:
    """R9 -- scan one source `.fwdictconfig` for WS / custom-field / style
    references absent in the target. Never raises: a file that fails to
    parse as XML yields no missing_refs (fail-soft; the file is still
    copied as opaque bytes either way -- see `apply_config_views`)."""
    missing: List[DroppedItemRecord] = []
    try:
        root = ET.parse(src_path).getroot()
    except ET.ParseError:
        return missing

    def _add(field_name: str, item_name: str, reason: str) -> None:
        missing.append(DroppedItemRecord(
            owner_kind="ConfigView",
            owner_guid="",
            owner_label=filename,
            field_name=field_name,
            item_name=item_name,
            item_guid="",
            reason=reason,
        ))

    seen_ws: Set[str] = set()
    seen_styles: Set[str] = set()
    seen_fields: Set[str] = set()

    # Root element's own writing system (e.g. writingSystem="en").
    root_ws = root.attrib.get("writingSystem")
    if root_ws and root_ws not in seen_ws:
        seen_ws.add(root_ws)
        if tgt_ws_ids is not None and root_ws not in tgt_ws_ids:
            _add("writingSystem", root_ws, f"writing system '{root_ws}' absent in target")

    for elem in root.iter():
        tag = _local_tag(elem.tag)
        if tag == "ConfigurationItem":
            style = elem.attrib.get("style")
            if style and style not in seen_styles:
                seen_styles.add(style)
                if tgt_style_names is not None and style not in tgt_style_names:
                    _add("style", style, f"style '{style}' absent in target")
            if elem.attrib.get("isCustomField") == "true":
                fname = elem.attrib.get("field")
                if fname and fname not in seen_fields:
                    seen_fields.add(fname)
                    if tgt_field_names is not None and fname not in tgt_field_names:
                        _add("field", fname, f"custom field '{fname}' absent in target")
        elif tag == "WritingSystemOptions":
            for opt in elem:
                if _local_tag(opt.tag) != "Option":
                    continue
                ws_id = opt.attrib.get("id")
                if not ws_id or ws_id in _WS_MAGIC_TOKENS or ws_id in seen_ws:
                    continue
                seen_ws.add(ws_id)
                if tgt_ws_ids is not None and ws_id not in tgt_ws_ids:
                    _add("writingSystem", ws_id, f"writing system '{ws_id}' absent in target")

    return missing


def plan_config_views(src_project, tgt_project) -> List[ConfigViewRecord]:
    """Decision pass (R8/R9, contracts/config-view-copy.md). No writes --
    and, per P0-1 (feature-025 cycle-6 remediation), NO DIRECTORY CREATION
    on either project tree. This function calls the pure `compute_config_
    dirs` (never `resolve_config_dirs`) for BOTH src and tgt, so a brand-
    new target with no `ConfigurationSettings/` folder yet simply yields
    an empty file listing (`_list_fwdictconfig` returns `[]` for a
    non-existent directory) rather than having Preview create it. Directory
    creation happens exactly once, at Move time, inside `apply_config_
    views`'s own per-file `os.makedirs` right before each ADD/OVERWRITE copy.

    Enumerates every `*.fwdictconfig` under the source's `Dictionary/` and
    `ReversalIndex/` subdirs, computes ADD/SKIP/OVERWRITE against the
    target's matching file (via `filecmp`), and scans each file's WS /
    custom-field / style references against the target, collecting
    `missing_refs`. A file with missing references is still planned for
    ADD/OVERWRITE/SKIP exactly as it would be otherwise -- FLEx degrades a
    dangling reference gracefully; missing_refs is purely reporting.
    """
    src_dict_dir, src_rev_dir = compute_config_dirs(src_project)
    tgt_dict_dir, tgt_rev_dir = compute_config_dirs(tgt_project)

    tgt_ws_ids = _target_ws_ids(tgt_project)
    tgt_field_names = _target_custom_field_names(tgt_project)
    tgt_style_names = _target_style_names(tgt_project)

    records: List[ConfigViewRecord] = []
    for kind, src_dir, tgt_dir in (
        ("Dictionary", src_dict_dir, tgt_dict_dir),
        ("ReversalIndex", src_rev_dir, tgt_rev_dir),
    ):
        for filename in _list_fwdictconfig(src_dir):
            src_path = os.path.join(src_dir, filename)
            tgt_path = os.path.join(tgt_dir, filename)
            action = _plan_action(src_path, tgt_path)
            missing_refs = _scan_missing_refs(
                src_path, filename, tgt_ws_ids, tgt_field_names, tgt_style_names,
            )
            records.append(ConfigViewRecord(
                kind=kind,
                filename=filename,
                src_path=src_path,
                tgt_path=tgt_path,
                action=action,
                missing_refs=missing_refs,
            ))
    return records


# ============================================================================
# Apply (T032) -- Move-mode only
# ============================================================================

def apply_config_views(records, dropped) -> None:
    """Move-mode executor (contracts/config-view-copy.md). For each
    `ConfigViewRecord`:
    - ADD / OVERWRITE: `shutil.copy2(src_path, tgt_path)`. OVERWRITE first
      backs up the existing target file to `<filename>.gtbak` -- the
      previous view is never destroyed without a copy.
    - SKIP: no I/O.

    Every record's `missing_refs` is appended to `dropped` (the run's
    `DroppedItemRecord` collector) regardless of action -- Principle III's
    never-silent guarantee applies even to a SKIPped (byte-identical) file
    that still carries a target-side gap (e.g. the target lost a custom
    field the byte-identical config still references).
    """
    for record in records:
        if record.action is ConfigViewAction.ADD:
            os.makedirs(os.path.dirname(record.tgt_path), exist_ok=True)
            shutil.copy2(record.src_path, record.tgt_path)
        elif record.action is ConfigViewAction.OVERWRITE:
            if os.path.exists(record.tgt_path):
                shutil.copy2(record.tgt_path, record.tgt_path + ".gtbak")
            os.makedirs(os.path.dirname(record.tgt_path), exist_ok=True)
            shutil.copy2(record.src_path, record.tgt_path)
        # ConfigViewAction.SKIP: no I/O.
        if record.missing_refs:
            dropped.extend(record.missing_refs)
