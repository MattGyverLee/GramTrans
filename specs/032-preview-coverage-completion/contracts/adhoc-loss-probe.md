# Contract: Ad hoc Rule Transfer-Loss Probe (read-only)

**Feature**: 032 (US5) | Surface: `debug/probe_adhoc_loss.py` (read-only) + `Lib/report.py`
(never-silent reporting if in-scope loss confirmed)

## Scope

Investigation + characterization only. Reproduction of ad hoc/compound rules is **out of
scope** (FR-016). The probe writes nothing to either project (read-only DoD, SC-008).

## Inputs

- A source project with ad hoc/compound rules, and a target that already received all
  stems and affixes (so loss cannot be blamed on missing morphemes).

## Outputs (evidence artifact)

1. **What reproduced vs what was lost**: per ad hoc rule, which portion is present on the
   target and which is absent (FR-016 acceptance 1).
2. **Root cause**: written characterization. Leading hypothesis to confirm/refute — the
   `to_ws_map_dict` silent-drop of source WSs whose mapped target Id is absent
   (`ws_mapping.py` ~66-85) as it applies to the ad-hoc transfer path.
3. **Scope decision**: either (a) reproduction is warranted → recorded as a
   recommendation for a **separate follow-up feature** (not built here), or (b) loss is
   unavoidable in this scope → recorded as a **known limitation**.

## Never-silent requirement (FR-017)

If any ad hoc/compound content is lost during Move within the chosen scope, that loss MUST
surface to the user explicitly via the post-run statistics/report surface — consistent
with the project's no-silent-skips contract. The probe's job is to determine *whether*
this reporting path is needed and *what* it must say.

## Acceptance

- Read-only probe produces the evidence artifact + written root cause + scope decision
  (SC-006).
- No destructive Move is performed (SC-008); no `needs_human` write gate is triggered.
