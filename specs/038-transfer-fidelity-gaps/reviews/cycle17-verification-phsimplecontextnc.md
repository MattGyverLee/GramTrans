# Verification -- PhSimpleContextNC -1 shortfall (mbugwe t135)

**Method:** read-only XML parse of both `.fwdata` files (no live LCM opened, no writes).

## Hash precondition

Both files matched the artifact's recorded digests exactly:

| File | sha256 | Result |
|---|---|---|
| source (Mbugwe LizzieHC practice.fwdata) | `3fb29a294434f85301e2f2f75d704489cdf4495325252cfb0f8797137cd5436d` | MATCH |
| dest (GT038 T124 Mbugwe.fwdata) | `dd97c8c821caeb48050b4c2e9f2e89685d7f2847d343d3e44bcd3bf336814b1a` | MATCH |

No drift. Proceeded to diff.

## Element shape (inspected before assuming)

`<rt class="PhSimpleContextNC" guid="..." ownerguid="...">` carries a `<FeatureStructure><objsur t="r"/></FeatureStructure>` (a *reference* to a `PhNCFeatures` natural class) and, in ~40% of instances, an optional `<PlusConstr>` list of reference-`objsur` children (feature-value constraints). No `INC`/`MinOccurs`/`MaxOccurs` children exist on this class.

## Counts

- Source: **104** `PhSimpleContextNC` elements.
- Dest: **103** `PhSimpleContextNC` elements.

Both match the census exactly (104/103, diff -1).

## Diff by GUID (both directions)

- Source-only GUIDs: **1** -- `e6a93fd6-ecfc-45a5-81df-497fba40766e`
- Destination-only GUIDs: **0**

103 of 104 GUIDs intersect exactly. GUID preservation holds cleanly for this class -- the by-GUID route was valid and sufficient; no fallback to a structural diff was needed.

## The named object

- **Missing GUID:** `e6a93fd6-ecfc-45a5-81df-497fba40766e`
- **Owner (`ownerguid`):** `be765e3e-ea5e-11de-9d42-0013722f8dec`, class **`PhPhonData`** -- the project's single phonological-data singleton, which owns *all* `PhPhonContext`-family objects (of every context subtype) in one flat `Contexts` collection, not per-rule.
- **Referenced natural class (`FeatureStructure` target):** `3ab6ae6a-5cc3-40ee-9319-18e5ffb393a9`, class `PhNCFeatures`, Name="Short vowels", Abbreviation="Vs". This natural class object itself **is present in the destination**, under the same owner GUID, with the same GUID.

Confirmed independently via the owner's `<Contexts>` collection contents (not just rt-element presence):
- Source `PhPhonData.Contexts`: 128 objsur entries, includes the missing GUID.
- Dest `PhPhonData.Contexts`: 127 objsur entries, does **not** include the missing GUID.

So the loss is consistent at both levels: the `<rt>` element for the context is absent AND its objsur was never added to the owner's collection in the destination -- a clean single-object omission, not a dangling reference or an orphaned rt-element.

## Owner present?

**Yes.** `PhPhonData` (guid `be765e3e-...`) exists in the destination with the identical GUID (its own `ownerguid`, pointing up to the project's LangProject-equivalent container, legitimately differs between source and dest project instances, as expected for a singleton). The referenced `PhNCFeatures` "Short vowels" natural class it would have pointed to is also present in the destination, unchanged.

Because both the owner and the referenced natural class transferred correctly, and only the context object itself (and its single collection membership) is missing, this is a create-time omission of one child object under an otherwise fully-transferred owner -- not a consequence of a missing or renamed sibling/owner row.

## Verdict

**NAMED-AND-ISOLATED**
