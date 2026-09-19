# Cycle 8 — the `'*???'` / `'***'` placeholder-name flag (optional read)

**Finding: the strings transferred correctly. `'*???'` is a RENDERING artifact of
writing-system configuration in the destination, not a lost value.**

Optional read requested by the lead; it did not block the cycle. Read-only:
`write_enabled: false`, `is_certified_readonly: true`, `mutating_calls_detected: []`.
Ops `op-104607946-016` (destination), `op-104634383-017` (source).

Scope: ngoreme's `omoona` only. Mbugwe's `Periphrastic Form` was **not** examined.

## The comparison

Entry `e2cd79ef-2ee5-4d56-ae54-9210060bcdae`, per writing system:

| field | WS | source `Ngoreme FLEx` | destination `GT038 T124 Ngoreme` |
|---|---|---|---|
| `LexemeFormOA.Form` | `ngq` | `'Xna'` | `'Xna'` |
| `CitationForm` | `ngq` | `'omoona'` | `'omoona'` |
| `LexemeFormOA.Form` | en / swh | None | None |
| `CitationForm` | en / swh | None | None |
| rendered `HeadWord.Text` | — | **`'omoona'`** | **`'*???'`** |

**Both stored multistrings round-tripped exactly.** Nothing was lost.

Note `'Xna'` is the *source's own* `LexemeForm` — it is not corruption introduced
by the transfer. (It occurs on 2 source entries; whether it is good lexicography
is the project's business, not ours.) The headword differs from the lexeme form
in the source too, which is ordinary: `CitationForm` overrides `LexemeForm` for
display.

## Why the rendering differs — writing-system inventory

```
source      writing systems: 3   en, swh, ngq   (ngq named "Ngoreme")
destination writing systems: 4   en, swh, etu, ngq   (ngq named "Ngurimi")
```

The destination carries an extra vernacular WS, `etu` (Ejagham), that the source
does not have, and its `ngq` is named *Ngurimi* rather than *Ngoreme*. `HeadWord`
is a computed property resolved against the project's **default vernacular
writing system**; `'*???'` is FLEx's rendering when that WS holds no value (`***`
plus the homograph marker).

**Leading hypothesis, NOT yet confirmed:** the destination's default vernacular WS
is `etu`, inherited from the starter/baseline project the target was built from,
rather than `ngq`. Every headword would then render empty while the underlying
data is intact.

**The one read that would confirm it** (cheap, read-only, for whoever takes the
spurt-4 row): compare `LangProject.CurrentVernacularWritingSystems` /
`DefaultVernacularWritingSystem` between the two projects. If the destination's
default is `etu`, this is closed as a target-provisioning defect.

## Why it matters, and why it is not a T123 row

A class-count census cannot see this **by construction**: the object is present
and counted; only its rendered string is empty. It is the same shape as cycle 5's
observation that mbugwe's `Periphrastic Form` arrived named `"***"` while
ngoreme's `Perfective` arrived correctly named — two different pairs, two
different code paths, both showing a placeholder where a multistring should be.

But on this evidence the ngoreme case is **not a fidelity loss**: the values are
in the destination. Before treating the mbugwe case as the same thing, it needs
the same per-WS read — it may be a genuine loss rather than a rendering artifact,
and assuming they share a cause would be exactly the kind of unexamined inference
that has already cost this feature three cycles.

**Recommendation:** spurt-4 candidate row, framed as *"destination writing-system
provisioning / default-vernacular WS"*, not as a name-transfer defect. Nothing
here changes T123(a) or T123(b), and nothing here should block the cycle-8 commit.
