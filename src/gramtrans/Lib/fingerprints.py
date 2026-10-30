"""Content-half child fingerprint tokens for preview pairing (spec-023, SC-006).

Qt-free, py38-compatible module shared by ``merge_preview.py`` (nested
gather) and the Move path (``matcher.py`` / ``preview.py``).

Each helper returns a hashable tuple used to build the machine join key
``f"{kind}\x1f{token_hash}\x1f{field}"``.  The *content half* intentionally
drops the ``owner_entry_guid`` component present in the full
``matcher.fingerprint_for_*`` tuples so that source and target children with
the same content land on the same join key regardless of their owning
entry's GUID (FR-011, data-model.md §2).

Fingerprint definitions (constitution I: "fingerprint definition per object
class MUST be documented"):

Allomorph token
    ``("allomorph", lexeme_form_text: str, morph_type_id: str)``
    where ``morph_type_id`` is the MorphTypeRA GUID string if present else
    the morph-type Name string else "".  Content derived from form text and
    morph-type identity; stable across projects.

Sense token
    ``("sense", gloss_text: str)``
    where ``gloss_text`` is the best analysis-WS gloss.  Ordinal suffix
    ``#N`` appended by ``make_sense_token`` only when the caller detects a
    collision (two senses share the same raw gloss).

MSA token
    ``("msa", label_text: str)``
    where ``label_text`` is the concatenated POS abbreviation plus slot names
    (e.g. ``"n:NC"``); content half of ``preview._msa_fingerprint`` (drops
    raw ``pos_guid``).
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any, Tuple

# ---------------------------------------------------------------------------
# Canonical token constructors
# ---------------------------------------------------------------------------


def allomorph_token(
    lexeme_form_text: str,
    morph_type_id: str,
) -> Tuple[str, str, str]:
    """Content-only allomorph join token.

    Parameters
    ----------
    lexeme_form_text:
        String form of the allomorph in the default vernacular WS; "" if
        unavailable.
    morph_type_id:
        MorphTypeRA GUID string (preferred) or morph-type Name string or "".
    """
    return ("allomorph", lexeme_form_text, morph_type_id)


def sense_token(gloss_text: str, ordinal_suffix: str = "") -> Tuple[str, str]:
    """Content-only sense join token.

    Parameters
    ----------
    gloss_text:
        Best analysis-WS gloss; "" if none.
    ordinal_suffix:
        Collision disambiguator; supply ``"#2"``, ``"#3"`` etc. when the
        caller has detected that two senses share the same raw gloss.  Leave
        empty for the first (or only) occurrence.
    """
    return ("sense", gloss_text + ordinal_suffix)


def msa_token(label_text: str) -> Tuple[str, str]:
    """Content-only MSA join token.

    Parameters
    ----------
    label_text:
        POS abbreviation + slot names as shown in FLEx (e.g. ``"n:NC"``).
        "" if the label cannot be determined.
    """
    return ("msa", label_text)


# ---------------------------------------------------------------------------
# Machine join-key construction
# ---------------------------------------------------------------------------


def token_hash(token: tuple) -> str:
    """Stable 8-char hex digest of a canonical token.

    Uses SHA-256 over the repr of the token so the hash is consistent
    across Python sessions (no PYTHONHASHSEED dependence).
    """
    raw = repr(token).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:8]


def machine_key(kind: str, tok: tuple, field_name: str) -> str:
    """Build the fingerprint-based join key for a child field.

    Format: ``"{kind}\\x1f{token_hash}\\x1f{field_name}"``

    The unit-separator ``\\x1f`` guarantees no collision with human text in
    any component.

    Parameters
    ----------
    kind:
        Child kind string: ``"sense"``, ``"allomorph"``, or ``"msa"``.
    tok:
        One of the canonical token tuples from this module.
    field_name:
        Child field label, e.g. ``"Gloss"``, ``"Form"``, ``"Comment"``.
    """
    return f"{kind}\x1f{token_hash(tok)}\x1f{field_name}"


# ---------------------------------------------------------------------------
# LCM object helpers (called by merge_preview._gather_entry_nested)
# These take raw LCM objects; no Qt dependency.
# ---------------------------------------------------------------------------


def allomorph_token_from_obj(allo: Any, ws_handle: Any = None) -> Tuple[str, str, str]:
    """Extract allomorph content token from a live LCM allomorph object.

    Mirrors the content half of ``matcher.fingerprint_for_allomorph``.
    Never raises; falls back to "" on any read failure.
    """
    lexeme_form_text = ""
    morph_type_id = ""
    try:
        form_prop = getattr(allo, "Form", None)
        if form_prop is not None and ws_handle is not None:
            try:
                ts = form_prop.get_String(ws_handle)
                if ts is not None:
                    lexeme_form_text = (ts.Text or "") if hasattr(ts, "Text") else str(ts)
            except Exception:
                pass
        # MorphTypeRA: prefer GUID, fall back to Name
        mt = getattr(allo, "MorphTypeRA", None)
        if mt is not None:
            try:
                morph_type_id = str(mt.Guid)
            except Exception:
                try:
                    name_prop = getattr(mt, "Name", None)
                    if name_prop is not None:
                        if hasattr(name_prop, "BestAnalysisAlternative"):
                            best = name_prop.BestAnalysisAlternative
                            morph_type_id = (getattr(best, "Text", None) or "") if best else ""
                        elif hasattr(name_prop, "Text"):
                            morph_type_id = name_prop.Text or ""
                        else:
                            morph_type_id = str(name_prop)
                except Exception:
                    morph_type_id = ""
    except Exception:
        pass
    return allomorph_token(lexeme_form_text, morph_type_id)


def sense_token_from_gloss(gloss_text: str, ordinal_suffix: str = "") -> Tuple[str, str]:
    """Thin wrapper kept for symmetry; prefer ``sense_token`` directly."""
    return sense_token(gloss_text, ordinal_suffix)


_CAST_IMPORT_WARNED = False


def _cast_msa_to_concrete(msa: Any) -> Any:
    """``categories._cast_to_concrete`` (ClassName-driven interface cast), or
    ``msa`` unchanged if categories cannot be imported. Lazy import:
    categories is heavy and imports this package's siblings.

    Only ``ImportError`` is swallowed, and it is logged ONCE (module flag) so a
    broken import is visible rather than silently reverting every label to "".
    ``_cast_to_concrete`` itself is fail-soft for duck-typed objects (missing
    ClassName / absent interface / refused cast all return the object), so no
    broad guard is kept around the call.
    """
    global _CAST_IMPORT_WARNED
    try:
        if __package__:
            from .categories import _cast_to_concrete
        else:
            from categories import _cast_to_concrete  # type: ignore
    except ImportError as exc:
        if not _CAST_IMPORT_WARNED:
            _CAST_IMPORT_WARNED = True
            logging.getLogger(__name__).warning(
                "msa_label_from_obj: cannot import categories._cast_to_concrete "
                "(%s); MSA labels will be read uncast and may be empty", exc)
        return msa
    return _cast_to_concrete(msa)


def msa_label_from_obj(msa: Any) -> str:
    """Best-effort MSA label string (e.g. ``"n:NC"``) from a live LCM MSA.

    Stem/infl MSAs: POS abbreviation + sorted slot names joined by ``":"``
    (the content portion of ``preview._msa_fingerprint``). Derivational MSAs
    (``MoDerivAffMsa``) do NOT mirror that: they are labelled ``"From>To"``
    from From-/ToPartOfSpeechRA, with an unset side left blank (``">v"``,
    ``"Root>"``); both unset yields no POS part. Never raises; returns "" on
    any failure.
    """
    parts: list[str] = []
    # Cast before reading (same trap as categories._cast_to_concrete / T088):
    # a sense's MorphoSyntaxAnalysisRA is statically typed
    # IMoMorphSynAnalysis, on which PartOfSpeechRA / SlotsRC /
    # From-/ToPartOfSpeechRA are NOT declared, so an uncast read yields None
    # for every MSA subclass.
    msa = _cast_msa_to_concrete(msa)

    def _abbr_text(pos: Any) -> str:
        abbr_prop = getattr(pos, "Abbreviation", None)
        if abbr_prop is None:
            return ""
        try:
            best = getattr(abbr_prop, "BestAnalysisAlternative", None)
            if best is not None:
                return getattr(best, "Text", None) or ""
            if hasattr(abbr_prop, "Text"):
                return abbr_prop.Text or ""
        except Exception:
            pass
        return ""

    try:
        pos = getattr(msa, "PartOfSpeechRA", None)
        if pos is not None:
            text = _abbr_text(pos)
            if text:
                parts.append(text)
        else:
            # Derivational affix: label as "From>To" (either side may be unset).
            frm = getattr(msa, "FromPartOfSpeechRA", None)
            to = getattr(msa, "ToPartOfSpeechRA", None)
            if frm is not None or to is not None:
                f_txt = _abbr_text(frm) if frm is not None else ""
                t_txt = _abbr_text(to) if to is not None else ""
                if f_txt or t_txt:
                    parts.append("%s>%s" % (f_txt, t_txt))
    except Exception:
        pass
    try:
        slots = getattr(msa, "SlotsRC", None)
        slot_names: list[str] = []
        if slots is not None:
            for sl in slots:
                try:
                    nm = getattr(sl, "Name", None)
                    if nm is not None:
                        best = getattr(nm, "BestAnalysisAlternative", None)
                        if best is not None:
                            t = getattr(best, "Text", None)
                            if t:
                                slot_names.append(t)
                        elif hasattr(nm, "Text"):
                            t = nm.Text
                            if t:
                                slot_names.append(t)
                except Exception:
                    continue
        if slot_names:
            parts.append(":".join(sorted(slot_names)))
    except Exception:
        pass
    return ":".join(parts) if parts else ""
