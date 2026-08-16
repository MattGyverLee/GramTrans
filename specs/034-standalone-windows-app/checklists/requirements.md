# Specification Quality Checklist: Standalone Windows Application (no FlexTools required)

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-16
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [ ] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- **Iteration 1 findings and fixes**:
  - *Implementation detail leakage*: the first pass named PyInstaller, Inno Setup,
    PyQt6, pythonnet, flexicon, the registry key path, and `--diagnose` directly in
    the requirements. All were rewritten in capability terms ("a single packaging
    definition", "an installer", "the UI toolkit", "the language-model runtime",
    "the location FieldWorks itself records", "a self-check mode"). The concrete
    tool choices are recorded as user decisions in the Input line and the
    Assumptions section, where they belong, and will be re-stated as technical
    choices in `plan.md`.
  - *Unmeasurable success criteria*: "the build is reproducible" and "errors are
    clear" were replaced with SC-008 (identical dependency set across two builds
    of one commit) and SC-006 (zero prerequisite failures surfacing as raw errors).
  - *Untestable requirement*: an early "the engine must not change" was sharpened
    into FR-012 plus SC-011 (existing suite passes; FlexTools path produces
    identical results before and after).

- **Iteration 2 — non-regression amendment** (after the owner asked "are we clear
  this cannot break FlexTools functionality?"). It was not clear. The spec
  asserted non-regression (then FR-012, SC-011) but supplied no mechanism, and
  two requirements as written actively required touching shared code. Four
  concrete risks were identified against the current source and each is now
  addressed:

  1. **FR-005 collided with the FlexTools fallback.** `DEFAULT_SOURCE_PROJECT`
     (`gramtrans.py:124`) is not dead code — it feeds `_headless_phase0`
     (line 264), the path FlexTools takes when the UI toolkit is unavailable.
     "No project name baked into the artifact" would have deleted it.
     *Resolved* by the owner's ruling that the standalone can never run
     headless: FR-005 is now a **reachability** requirement and FR-006 asserts
     the toolkit at startup, so the fallback and its constant stay untouched.
     Risk eliminated with zero changes to shared code.
  2. **The confirmation gate had no clean home.** The shell cannot own it —
     Preview-versus-Move is chosen inside the wizard. Embedding it there would
     give every FlexTools user a new blocking dialog, redundant where `Ctrl+Z`
     exists. *Resolved* by FR-017: the gate is host-supplied; FlexTools passes
     one satisfied on creation, so its behaviour is byte-identical.
  3. **Packaging pressure toward a 31-file import refactor.** Thirty-one files
     carry `if __package__:` guards depending on the `site.addsitedir` flat
     convention, which static packaging analysis cannot follow. *Resolved* by
     FR-018, which forbids the refactor and puts the burden on packaging; also
     added to Out of Scope.
  4. **Dependency-pin leakage.** Exact pins in the package's declared
     dependencies would constrain every FlexTools install. *Resolved* by FR-019
     (build-only lock) and FR-041.

  Also added: FR-020 (unlisted shared-code changes are a defect), FR-021 (the
  regression gate runs continuously, not once at release), and SC-012/013/014
  to make non-regression measurable rather than asserted.

- **Iteration 2 — write-mode clarification.** The owner ruled that the
  standalone bakes in write permission, dropping the harness's read-only-default
  / `--move` toggle. Captured as FR-011. This required a compensating
  requirement: with the host-level write backstop gone, FR-012 now mandates that
  the wizard open in Preview and expressly forbids defaulting it to Move.
  Verified this does not weaken Principle III's Preview mandate.

- **Iteration 2 — FR-053 (was FR-044) widened.** While checking Principle III's
  Preview mandate, found that the *same* principle also requires "Move Mode MUST
  be undoable through FLEx's standard undo stack wherever LCM permits" — which
  the standalone structurally cannot provide. The governance question is
  therefore Principle II **and** Principle III, not Principle II alone.
  Question 1 now offers four options spanning both.

- **One checklist item is deliberately open**: two `[NEEDS CLARIFICATION]`
  decisions remain, both raised as Open Questions in the spec.
  - **Question 1 (governance, blocking release not planning)**: whether to amend
    the constitution to admit a second delivery artifact and to address
    Principle III's undo clause, or record an argued finding that neither
    principle is violated. Tracked as FR-053. Planning can proceed; release
    cannot.
  - **Question 2 (safety, scope-affecting)**: how the application should treat a
    Send/Receive target, given there is no undo and no backup. Option A (refuse)
    and Option B (warn harder) differ in scope; Option C is the status quo.

  These were retained rather than defaulted because both are genuine decisions
  for the project owner: Question 1 is a governance act only the owner can take,
  and Question 2 trades a user's workflow against a team-wide data-loss risk.

- Items marked incomplete require spec updates before `/speckit-clarify` or `/speckit-plan`
