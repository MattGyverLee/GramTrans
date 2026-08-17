# GramTrans for Windows — release notes

Feature 034 · `contracts/build-and-release.md` §6 (FR-030, FR-027, FR-045,
FR-051, FR-052, FR-054).

This file is the source for what ships with every release. Everything in it is
required to be stated; none of it is optional detail.

---

## Before you install

**You need FieldWorks 9.** GramTrans reads and writes FieldWorks Language
Explorer projects through FieldWorks' own language-model libraries, and it does
**not** include them. Install FieldWorks 9 first, from
[software.sil.org/fieldworks](https://software.sil.org/fieldworks/). If you
already use FLEx, you already have it.

GramTrans does not need FlexTools. If you do have FlexTools, the GramTrans
module you run inside it is unchanged and unaffected by this application —
they can both be installed and neither knows about the other.

## What you download

| File | What it is | Support |
|---|---|---|
| `GramTrans-Setup-<version>.exe` | Installer: Start Menu entry, uninstaller | **Supported** — use this one |
| `GramTrans-<version>.exe` | Single-file portable executable | Best effort |

The portable build unpacks itself to a temporary folder every time it starts,
which interacts badly with both antivirus software and the FieldWorks
libraries. It is provided for people who cannot install software, and problems
with it may not be fixable.

## The download warning you will see

**GramTrans is not code-signed.** Code signing certificates have not been
arranged for this project yet, so Windows does not recognise the publisher.

What you will see, and what to do:

* **Microsoft Defender SmartScreen** — a blue box reading *"Windows protected
  your PC"* with only a **Don't run** button visible. Click **More info**, then
  **Run anyway**.
* **Your browser** may warn that the file *"isn't commonly downloaded"* and
  offer to discard it. Choose **Keep** (in Edge, via the **...** menu next to
  the download).
* **Your antivirus** may quarantine it. Any program packaged this way looks
  unusual to heuristic scanners; if this happens, restore the file from
  quarantine and, if your antivirus offers it, add an exclusion.

None of these mean anything is wrong with the file. They mean Windows has never
seen it signed. If you would rather not proceed on that basis, that is a
reasonable position — use the FlexTools module instead.

## Licence of the downloaded program

**GramTrans's own source code is MIT licensed. The downloadable program is
not, and is distributed under stricter terms**, because of what it has to
include to run:

| Bundled component | Licence |
|---|---|
| PyQt6 | **GPL v3** or a commercial Riverbank licence |
| pythonnet, clr_loader | MIT |
| pyflexicon | LGPL (see the project) |
| flextoolslib | LGPL |
| flexlibs (stock, "flexlibs1") | LGPL |
| cdfutils | LGPL |

Because PyQt6 is included and is GPL-or-commercial, **the combined binary is
distributed under the GPL v3**. You may use, copy and redistribute it under
those terms. The GramTrans source remains available under MIT, and a build made
against a commercial Qt licence would not carry the GPL obligation — that is a
choice for whoever makes such a build.

`flexlibs` and `cdfutils` arrive as dependencies of `flextoolslib` and nothing
in GramTrans imports them at runtime. They are shipped nonetheless, and are
listed here because being inert does not make them absent.

The exact pinned version of every component is in `build/requirements.lock` and
in the manifest published beside each release artifact.

## Two things to know before you run a transfer

**1. The target project must be closed in FieldWorks — even for a Preview.**

GramTrans opens the project you are copying *into* with write access as soon as
you choose it, regardless of whether you go on to run a Preview or a Move. If
it is open in FLEx you will get a "something else is using it" message naming
the project. Close it in FLEx and try again.

The source project — the one you copy *from* — is opened read-only and is never
modified.

**2. A Move cannot be undone from within GramTrans.**

Inside FlexTools, a GramTrans run is wrapped in a FLEx editing session and
`Ctrl+Z` undoes it. **This application has no such thing.** Once a Move starts
writing, GramTrans cannot take it back, and closing the application will not
put the project back the way it was.

So, before any Move:

* **Back up the target project.** In FLEx: *File > Back up this Project*. This
  is the reliable way back, and it takes seconds.
* **If the project uses Send/Receive, do a Send/Receive first.** Then, if the
  run goes wrong, you can delete your local copy of the project and receive it
  again — which returns you to exactly where you started. A Send/Receive user
  arguably has a *better* recovery story than a local-only user.

GramTrans asks you to type the target project's name before it will write. That
is deliberate friction, and it is there because the write cannot be reversed.

**If a Move stops partway**, the target may be partially modified. GramTrans
will tell you the run's tag (`GT-<date>-<time>`); search for it in FLEx — it
appears in the **Import Residue** field and in the Description of objects that
have one — to see exactly what was added. There is no rollback; restoring your
backup, or re-receiving, is the way back.

## Where the log is

`%LOCALAPPDATA%\GramTrans\logs\gramtrans-<run-id>.log` — one file per run, kept
between runs. The path is shown in the application's status bar, at the top of
the report pane, and in the self-check.

Uninstalling GramTrans does **not** delete the logs.

## If it will not start

Run **Help > Self-check...** inside the application, or `GramTrans.exe
--self-check` from a command prompt. Both produce the same block: one line per
prerequisite, and a concrete next step under anything that failed. Copy the
whole block and include it when you ask for help, along with the log file.
