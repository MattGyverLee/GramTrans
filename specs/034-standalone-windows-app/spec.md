# Feature Specification: Standalone Windows Application (no FlexTools required)

**Feature Branch**: `034-standalone-windows-app`

**Created**: 2026-08-16

**Status**: Draft

**Input**: User description: "Typically, this tool will be run as a FlexTool, but I want to plan a standalone pyinstall version for users without flextools. This will necessarily include the latest version of flexicon, and will expect FLEx and LibLCM to be installed. Windows only." Plus follow-ups: "we will need an explicit Input project selector", "I don't want to configure a default project on this version", and "I want stable sandboxed required packages."

## Overview

GramTrans today is delivered only as a FlexTools module. FlexTools supplies four
things the transfer depends on: the open project, the report sink, the
`modifyAllowed` flag, and a Unit-of-Work wrapper that makes the whole run
undoable with a single `Ctrl+Z` in FLEx.

This feature adds a **second delivery artifact**: a self-contained Windows
application that supplies those four things itself, so a linguist who has
FieldWorks installed but *not* FlexTools can run the same transfer. The
transfer engine is not forked, reimplemented, or behaviourally changed — the
standalone application is a **host shell** wrapped around the existing module.

Two consequences drive most of this specification:

1. **There is no host-provided "currently open project."** The application must
   ask the user for *both* projects — an explicit source picker alongside the
   existing target picker — with nothing pre-selected.
2. **There is no host-provided Unit of Work, therefore no `Ctrl+Z` undo.** A
   Move run in the standalone application is irreversible from the
   application's point of view. That risk is managed by an explicit warning and
   confirmation gate, not by machinery.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run a transfer without FlexTools (Priority: P1)

A field linguist has FieldWorks 9 installed and two FLEx projects on their
machine. They have never installed FlexTools and do not want to. They obtain
the GramTrans application, install it, launch it from the Start Menu, choose
which project to copy grammar *from* and which to copy *into*, review a
preview, and close the application. Nothing in their FLEx projects has
changed.

**Why this priority**: This is the entire point of the feature. Without it the
user cannot run GramTrans at all. A preview-only slice is already valuable —
it lets a user see what a transfer *would* do before deciding whether they
want it — and it exercises every hard part of the delivery (freezing the
runtime, finding FieldWorks, loading the language model, opening two projects,
running the wizard, rendering the report) without risking any data.

**Independent Test**: On a clean Windows machine with FieldWorks 9 and no
FlexTools and no developer Python installed, install the artifact, launch it,
select a source and a target, run a Preview, and confirm the preview matches
the one produced by the same source/target pair under FlexTools. No writes
occur.

**Acceptance Scenarios**:

1. **Given** a machine with FieldWorks 9 installed, at least two local FLEx
   projects, and no FlexTools and no user-installed Python, **When** the user
   launches the application, **Then** the application starts and presents a
   source-project picker listing the local FLEx projects.
2. **Given** the source picker is displayed, **When** the user has not yet
   chosen anything, **Then** no project is pre-selected and the control that
   advances to the next step is disabled.
3. **Given** the user has chosen a source project, **When** they advance,
   **Then** a target-project picker is presented, also with nothing
   pre-selected, and the project already chosen as source is not selectable as
   the target.
4. **Given** both projects are chosen, **When** the user proceeds, **Then** the
   existing GramTrans selection wizard opens with the same categories,
   options, and behaviour it has under FlexTools.
5. **Given** the wizard is set to Preview, **When** the user runs it, **Then**
   the preview result is displayed inside the application (there is no
   FlexTools report window), and the target project is byte-for-byte unchanged.
6. **Given** a Preview run has finished, **When** the user closes the
   application, **Then** both projects are released such that FLEx can
   immediately open either of them without a lock error.
7. **Given** the same source/target pair and the same wizard selections,
   **When** the run is performed under FlexTools and under the standalone
   application, **Then** both produce equivalent preview results.

---

### User Story 2 - Commit a Move, with the irreversibility made unmissable (Priority: P2)

The linguist has reviewed a preview and wants to apply it. Because the
standalone application cannot offer `Ctrl+Z`, it stops them with a warning
that spells out that the write cannot be undone and that they should back up
the target first, and requires them to type the target project's name to
proceed. Once confirmed, the transfer runs and the application reports exactly
what was written.

**Why this priority**: Without this the tool can only look, never act — so it
is required for the feature to be genuinely useful. It is P2 rather than P1
because the preview slice (US1) delivers standalone value and because this
story carries all of the data-loss risk, so it should land on top of a proven
foundation rather than alongside it.

**Independent Test**: With a disposable copy of a target project, run a Move,
verify the confirmation gate cannot be bypassed by clicking through, complete
it, and confirm the expected objects exist in the target with the expected
residue tags.

**Acceptance Scenarios**:

1. **Given** the user selects Move mode, **When** they attempt to start the
   run, **Then** a warning is presented that states plainly that the change
   cannot be undone from within the application and that the target should be
   backed up first.
2. **Given** the warning is displayed, **When** the user has not typed the
   target project's name exactly, **Then** the control that starts the write
   remains disabled.
3. **Given** the warning is displayed, **When** the user cancels, **Then** no
   write occurs and the user is returned to the wizard with their selections
   intact.
4. **Given** the confirmation is completed, **When** the run executes, **Then**
   the objects written to the target are the same objects the immediately
   preceding preview listed, carrying the same residue tags as a FlexTools run
   would produce.
5. **Given** Preview mode is selected, **When** the user starts the run,
   **Then** no warning or confirmation gate is shown.
6. **Given** a Move run fails partway through, **When** the failure is
   reported, **Then** the application states clearly that the target may be
   partially modified, identifies the run so its residue tag can be searched
   in FLEx, and points the user to the log file.

---

### User Story 3 - Produce a reproducible release (Priority: P3)

The maintainer builds the shipped artifacts from a clean checkout. The build
resolves every dependency from a pinned lock, runs in a throwaway environment
that cannot pick anything up from the maintainer's own machine, and produces
the same set of artifacts every time. Both artifacts pass an automated smoke
test before anything is published.

**Why this priority**: The user's requirement for "stable sandboxed required
packages" is a hard constraint on the delivery, and an unreproducible bundle
is the single most likely source of "it works on my machine" failures in the
field. It is P3 only because US1 and US2 must exist before there is anything to
package; it gates the actual release.

**Independent Test**: On a machine that has never built GramTrans, run the
documented build command from a fresh clone, and confirm the artifacts are
produced, are functionally identical to the previous build for the same
commit, and pass the smoke test.

**Acceptance Scenarios**:

1. **Given** a fresh clone and a machine with no GramTrans dependencies
   installed, **When** the maintainer runs the build, **Then** the build
   creates its own isolated environment, installs only the pinned versions
   from the lock file, and completes without using any pre-existing Python
   environment on the machine.
2. **Given** a build has completed, **When** the artifacts are inspected,
   **Then** every runtime dependency is present inside the bundle at the exact
   pinned version, and no FieldWorks or LibLCM assembly is bundled.
3. **Given** the same commit is built twice, **When** the two outputs are
   compared, **Then** they contain the same set of dependencies at the same
   versions and behave identically under the smoke test.
4. **Given** a built artifact, **When** it is launched on a machine that has a
   conflicting Python installation and Python-related environment variables
   set, **Then** the application uses only its own bundled dependencies and is
   unaffected.
5. **Given** either artifact fails the smoke test, **When** the release is
   attempted, **Then** the release is blocked for that artifact.
6. **Given** an installed application, **When** the user views its version,
   **Then** it reports a version identifying the exact source commit it was
   built from.

---

### User Story 4 - Diagnose a machine where it will not start (Priority: P4)

A user reports that the application shows an error or fails to open a project.
They are asked to run the application's self-check and send the result. The
output identifies which prerequisite is missing or mismatched without
requiring the user to install anything or read a stack trace.

**Why this priority**: This is a support-cost feature rather than a
capability. It matters because the failure modes here are unusually opaque —
a missing FieldWorks registry entry, an unsupported FieldWorks version, or a
.NET runtime that will not load all present as the same "nothing happened" to
an end user — but the tool is useful without it.

**Independent Test**: On a machine with FieldWorks deliberately absent or
mis-registered, run the self-check and confirm it names the specific missing
prerequisite and its remedy.

**Acceptance Scenarios**:

1. **Given** any machine, **When** the user runs the application's self-check
   mode, **Then** it reports the detected FieldWorks version and locations, the
   status of the .NET runtime, the versions of the bundled components, the
   application's own version, and a pass/fail verdict per prerequisite.
2. **Given** FieldWorks is not installed, **When** the application is
   launched normally, **Then** it presents a plain-language message naming
   FieldWorks as the missing prerequisite instead of a technical error.
3. **Given** an installed FieldWorks version the application does not support,
   **When** the application is launched, **Then** it names the detected
   version and the versions it supports, and stops.
4. **Given** any run, **When** it finishes or fails, **Then** a log file exists
   at a documented, user-reachable location containing enough detail to
   diagnose the run, and the application tells the user where it is.

---

### Edge Cases

- **Same project chosen twice**: the target picker must make the chosen source
  unselectable, and the run must be refused if the two ever resolve to the
  same project on disk.
- **Target already open in FieldWorks**: the write-enabled open will fail on a
  lock. The user must be told, in plain language, to close the project in FLEx
  and retry — not shown a lock exception.
- **Source already open in FieldWorks**: a read-only open may still succeed;
  behaviour must be deterministic and stated, not incidental.
- **No projects found**: the projects directory exists but is empty, or the
  registry points at a directory that does not exist.
- **Project list contains a project the application cannot open** (corrupt,
  mid-migration, or requiring a FLEx data migration): the picker must not
  crash; the failure must be attributed to that project.
- **Project requires a data-model migration**: FLEx migrates projects on open.
  The application must not silently migrate a user's project as a side effect
  of being pointed at it.
- **Send/Receive (shared) target project**: writing to a project under
  FLExBridge control has consequences beyond the local machine.
- **Move run interrupted** by application crash, power loss, or the user
  killing the process: the target is left partially written with no undo.
- **User closes the application mid-run**: must not leave an LCM lock behind
  that blocks FLEx from opening the project afterwards.
- **Machine has a conflicting Python installation** or `PYTHONPATH` /
  `PYTHONHOME` set: must not affect the bundled application.
- **FieldWorks installed for a different processor architecture** than the
  bundled runtime: the language model cannot be loaded and must produce a clear
  message rather than a load failure.
- **Antivirus or SmartScreen blocks the unsigned artifact**: expected and must
  be documented for users rather than discovered.
- **Non-default projects directory**: the registry's projects location is
  authoritative and must be honoured rather than assuming the default path.
- **Second instance launched** while a run is in progress against the same
  target.

## Requirements *(mandatory)*

### Host-shell responsibilities (replacing FlexTools)

- **FR-001**: The application MUST enumerate the FLEx projects available on the
  machine using the location FieldWorks itself records, not a hard-coded path.
- **FR-002**: The application MUST present an explicit **source** project
  selector. There is no "currently open project" to inherit.
- **FR-003**: The application MUST present an explicit **target** project
  selector, retaining the semantics the existing target picker already has.
- **FR-004**: The application MUST NOT pre-select, default to, or hard-code any
  project in either selector. Both start empty and require a deliberate user
  choice.
- **FR-005**: The application MUST NOT carry any project name baked into the
  shipped artifact — no default source project, and no development or test
  project name reachable by an end user.
- **FR-006**: The application MUST open the chosen source project read-only and
  the chosen target project write-enabled, matching the access levels the
  FlexTools-hosted module receives.
- **FR-007**: The application MUST supply the transfer engine with the same
  reporting interface FlexTools supplies (informational, warning, error, and
  blank-line messages).
- **FR-008**: The application MUST render those report messages in an in-application
  log view, visible during and after the run, since no FlexTools report window
  exists.
- **FR-009**: The application MUST allow the user to save or copy the run
  report out of the application.
- **FR-010**: The application MUST derive the engine's write-permission flag
  from the user's Preview-versus-Move choice, and MUST NOT allow a Move to
  proceed with the flag unset or a Preview to proceed with it set.
- **FR-011**: The application MUST close both projects and release all locks on
  exit, including on error paths and on user-initiated cancellation.
- **FR-012**: The application MUST reuse the existing transfer engine and
  selection wizard without forking, duplicating, or altering their behaviour.
  Any change required to make them host-agnostic MUST leave the
  FlexTools-hosted behaviour identical.
- **FR-013**: The application MUST run identically whether or not FieldWorks
  itself is running, and MUST NOT require FLEx to be open.

### Irreversible-write safeguard

- **FR-014**: Before any Move-mode write, the application MUST display a
  warning that states the operation cannot be undone from within the
  application and that the user should back up the target project first.
- **FR-015**: The application MUST require the user to type the target
  project's name exactly before the write can begin; the confirmation MUST NOT
  be satisfiable by pressing Enter or clicking through a default button.
- **FR-016**: The application MUST NOT show this gate for Preview runs.
- **FR-017**: Cancelling the gate MUST return the user to the wizard with all
  selections intact and MUST leave the target unmodified.
- **FR-018**: If a Move run fails partway, the application MUST state that the
  target may be partially modified, report the run identifier under which
  partial work can be found, and direct the user to the log file.
- **FR-019**: The application MUST NOT claim, imply, or document that a Move
  can be undone from within the application.

### Guard rails and error handling

- **FR-020**: The application MUST refuse to run a transfer where the source
  and target resolve to the same project.
- **FR-021**: When the target cannot be opened write-enabled because it is in
  use, the application MUST tell the user which project is locked and that it
  must be closed in FLEx, without exposing a raw error.
- **FR-022**: When FieldWorks is not installed, the application MUST report
  that FieldWorks is a required prerequisite and stop cleanly.
- **FR-023**: When the installed FieldWorks version is outside the supported
  range, the application MUST report the detected version and the supported
  range, and stop cleanly.
- **FR-024**: When the underlying language-model runtime cannot be loaded, the
  application MUST report which component failed and point to the self-check
  and log file, rather than exiting silently or showing a stack trace.
- **FR-025**: A project that cannot be opened MUST be reported against that
  specific project without preventing the user from choosing a different one.
- **FR-026**: The application MUST NOT trigger a FLEx data-model migration of a
  user's project as an unannounced side effect; if a chosen project requires
  migration, the user MUST be told before anything proceeds.

### Diagnostics

- **FR-027**: The application MUST provide a self-check mode, invocable without
  selecting any project, reporting: detected FieldWorks version and its code
  and projects locations; language-model runtime status; the versions of the
  bundled runtime components; the application version; and a pass/fail verdict
  for each prerequisite.
- **FR-028**: The self-check output MUST be copyable or savable as a single
  block suitable for pasting into a support request.
- **FR-029**: The application MUST write a log file to a documented,
  user-reachable location, retained across runs, and MUST surface that location
  in the interface.
- **FR-030**: Log output MUST NOT contain project content beyond what is
  needed to identify objects involved in the run.

### Packaging, dependencies, and isolation

- **FR-031**: The shipped artifact MUST contain its own runtime and every
  required dependency; it MUST NOT require the user to install Python or any
  Python package.
- **FR-032**: Dependency versions MUST be pinned exactly in a checked-in lock,
  not expressed as minimum floors.
- **FR-033**: The build MUST run in a freshly created, isolated environment and
  MUST NOT resolve any dependency from an environment already present on the
  build machine.
- **FR-034**: At runtime the application MUST ignore host Python environment
  variables and host-installed packages, using only its own bundled
  dependencies.
- **FR-035**: The only external location the application may add to its own
  module search path is the FieldWorks code directory, as recorded by
  FieldWorks itself, because the language-model assemblies must be loaded from
  the user's own FieldWorks installation.
- **FR-036**: The application MUST NOT bundle FieldWorks or its language-model
  assemblies.
- **FR-037**: Two artifacts MUST be produced from a single packaging
  definition: an **installer** (with Start Menu entry and uninstaller), which
  is the supported artifact; and a **single-file portable executable**, which
  is a best-effort artifact.
- **FR-038**: Both artifacts MUST pass the same automated post-build smoke
  test; an artifact that fails MUST NOT be released. Failure of the portable
  artifact MUST NOT block release of the installer.
- **FR-039**: The smoke test MUST verify at minimum that the application
  starts, that the self-check passes on a machine with FieldWorks present, that
  the project list is populated, and that a Preview against a known project
  pair produces the expected result with no modification to the target.
- **FR-040**: Each artifact MUST carry a version identifying the exact source
  commit it was built from, visible both in the interface and in the
  self-check output.
- **FR-041**: The application MUST support Windows only. No macOS or Linux
  artifact is produced.
- **FR-042**: Release documentation MUST state that the artifact is unsigned
  and MUST tell users what the resulting operating-system warning looks like
  and how to proceed, until code signing is arranged.
- **FR-043**: Release documentation MUST state the licence under which the
  distributed binary is made available, given that bundled components impose
  licence terms stricter than the project's own source licence.

### Governance

- **FR-044**: The project constitution MUST be reconciled with the existence of
  a second delivery artifact before this feature is released. The constitution
  currently requires the shipped artifact to be a FlexTools-compatible module
  hosted by a standard FlexTools installation and forbids runtime dependencies
  beyond the language-model wrapper and the UI toolkit. This feature MUST NOT
  be released against an unamended constitution on the basis of an unrecorded
  reading. [NEEDS CLARIFICATION: amend the constitution to admit a standalone
  host artifact, or record an argued finding that the module itself is
  unchanged and the standalone binary merely substitutes for the host? See
  Question 1.]

### Key Entities

- **Project Choice**: a user's selection of one FLEx project for one role
  (source or target). Attributes: role, project name, on-disk location, access
  level required. Constraint: the two choices in a run must not resolve to the
  same project.
- **Host Session**: the standalone application's stand-in for a FlexTools run.
  Holds the open source project, the open target project, the report sink, the
  write-permission flag, and the run's log destination. Responsible for
  releasing both projects on any exit path.
- **Confirmation Gate**: the state guarding a Move run. Attributes: target
  project name expected, text typed by user, satisfied/unsatisfied. Only a
  satisfied gate permits a write.
- **Prerequisite Report**: the result of the self-check. A list of named
  prerequisites, each with a detected value, an expected value, and a verdict.
- **Dependency Lock**: the pinned, exact set of components the artifact is
  built from. Attributes: component name, exact version. Used both to build and
  to verify a built artifact.
- **Release Artifact**: one shipped output. Attributes: kind (installer or
  portable), support status (supported or best-effort), source commit,
  smoke-test verdict.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user with FieldWorks installed and no FlexTools, no Python, and
  no prior GramTrans exposure can get from downloading the artifact to seeing a
  completed preview in under 10 minutes without assistance.
- **SC-002**: 100% of preview results produced by the standalone application
  match those produced by the FlexTools-hosted module for the same project pair
  and the same selections.
- **SC-003**: 100% of Move runs in the standalone application are preceded by a
  completed confirmation gate; zero writes occur without one.
- **SC-004**: Zero preview runs modify the target project, verified by
  comparing the target before and after.
- **SC-005**: After any exit path — normal close, cancellation, error, or a
  failed run — FLEx can open both projects with no lock error, in 100% of
  cases.
- **SC-006**: Every prerequisite failure the application can encounter produces
  a message naming the missing or mismatched prerequisite; zero prerequisite
  failures surface as an unexplained exit or a raw technical error.
- **SC-007**: Given a support report consisting only of the self-check output
  and the log file, the maintainer can identify the cause of a start-up failure
  without further round-trips in at least 90% of cases.
- **SC-008**: Building the same source commit twice yields artifacts containing
  an identical set of dependencies at identical versions, 100% of the time.
- **SC-009**: The application runs correctly on a machine with a conflicting
  Python installation and Python environment variables set, in 100% of test
  cases.
- **SC-010**: No release is published in which any shipped artifact failed the
  smoke test.
- **SC-011**: The transfer engine's behaviour is unchanged: the existing test
  suite passes and the FlexTools-hosted module produces identical results
  before and after this feature.

## Assumptions

- **Prerequisites are the user's responsibility.** FieldWorks 9 (including its
  language-model assemblies) must already be installed. The application detects
  and reports its absence but never installs or bundles it.
- **FieldWorks 9 is the only supported version**, matching what the underlying
  wrapper supports today. Older or newer FieldWorks lines are out of scope.
- **The application is built for the same processor architecture as the
  supported FieldWorks installation** (64-bit, matching observed FieldWorks 9
  installs). Should a supported FieldWorks installation exist for a different
  architecture, a matching build would be a separate scope decision.
- **Local projects only.** Projects are enumerated from the location FieldWorks
  records; projects held outside that location are out of scope for the picker.
- **No persistence between runs in this version.** Nothing is remembered — no
  last-used projects, no saved selections. This follows directly from the "no
  default project" requirement.
- **The installer is the supported artifact**; the single-file portable
  executable is best-effort and may be withheld from a release without blocking
  it, because single-file packaging is the most fragile configuration for the
  runtime this application depends on.
- **The FlexTools-hosted module remains the primary delivery** and is unchanged
  in behaviour. Where shared code must become host-agnostic, the FlexTools path
  keeps identical behaviour.
- **Bundling the real FlexTools support library**, pinned, is the chosen way to
  satisfy the module's existing dependency on it, rather than substituting a
  stand-in. Its own transitive dependencies come along and are inert; their
  size and licence impact are characterised during planning.
- **Distribution is by direct download** of a released artifact. There is no
  auto-update, no update check, and no package manager or app-store channel.
- **Code signing is not solved here.** The need and its user-visible
  consequence are documented; obtaining a certificate is a separate decision.
- **The self-check is a diagnostic, not a transfer interface.** There is no
  headless transfer mode; a transfer always goes through the interface.

## Dependencies

- The existing GramTrans transfer engine and selection wizard.
- An installed FieldWorks 9 on the end user's machine, discoverable through the
  location FieldWorks itself records.
- The language-model wrapper library, at a version supporting everything the
  engine already requires.
- The FlexTools support library, for the metadata names the module imports.
- The UI toolkit already used by the wizard.
- An installer-authoring tool for the supported artifact.
- **Governance dependency**: resolution of FR-044 before release.

## Out of Scope

- macOS and Linux artifacts.
- Bundling, installing, or updating FieldWorks or its language-model assemblies.
- Any change to transfer semantics, merge phases, conflict handling, writing-system
  mapping, or engine behaviour.
- A headless or scriptable transfer interface.
- Automated backup or restore of a target project.
- In-application undo or rollback of a completed Move.
- Auto-update or update notification.
- Obtaining a code-signing certificate.
- Replacing or deprecating the FlexTools module.
- Supporting projects under Send/Receive beyond whatever the resolution to
  Question 2 requires.

## Open Questions

### Question 1: Constitution reconciliation

**Context**: The project constitution states the shipped artifact must be a
FlexTools-compatible module running inside a standard FlexTools host, describes
the runtime as "hosted by a standard FlexTools installation", and forbids
runtime dependencies beyond the language-model wrapper and the UI toolkit. This
feature ships a second artifact that substitutes for that host and bundles
additional components.

**What we need to know**: Which path resolves the conflict?

| Option | Answer | Implications |
|--------|--------|--------------|
| A | Amend the constitution to admit a standalone host artifact as a second sanctioned delivery channel | Honest and durable; requires a constitution version bump and a Sync Impact Report before this feature can be released. Future host shells are pre-authorised. |
| B | Record an argued finding that the module is unchanged and the binary merely supplies a host, so no principle is violated | No constitution churn; relies on a reading that "hosted by a standard FlexTools installation" describes the module's contract rather than the only permitted delivery. Weaker if challenged later. |
| C | Amend narrowly — allow exactly one standalone Windows host artifact, keeping the general prohibition | Preserves the constraint's force while unblocking this feature; any future second channel needs its own amendment. |
| Custom | Provide your own answer | Describe the governance path you want taken. |

**Your choice**: _[Awaiting decision]_

---

### Question 2: Send/Receive (shared) target projects

**Context**: A Move is irreversible from the application's point of view, and
this feature deliberately ships no backup or undo. If the target is under
Send/Receive control, an un-reviewed transfer can propagate to an entire team
on the next send.

**What we need to know**: How should the application treat a target project
that is under Send/Receive control?

| Option | Answer | Implications |
|--------|--------|--------------|
| A | Detect and refuse — Send/Receive projects cannot be targets in the standalone application | Safest; costs some users a legitimate workflow and pushes them to the FlexTools path, where `Ctrl+Z` exists. |
| B | Detect and warn — add a second, sharper warning to the confirmation gate, then allow it | Keeps the workflow available while making the blast radius explicit. Requires reliable detection. |
| C | Ignore — treat all targets identically | Simplest; a user can silently push un-reviewed grammar to a shared repository with no undo. |
| Custom | Provide your own answer | Describe the treatment you want. |

**Your choice**: _[Awaiting decision]_
