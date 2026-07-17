# Bug report — `MediaOperations.CopyToProject` / `Create` throw `NullReferenceException` (cannot add a picture/media file)

**Component**: `pyflexicon` (flexicon) — `flexicon/code/Shared/MediaOperations.py`
**Affected public API**: `LexSenseOperations.AddPicture`, `MediaOperations.CopyToProject`, `MediaOperations.Create`, `ExampleOperations.AddMediaFile`, `PronunciationOperations.AddMediaFile` (everything that funnels into `MediaOperations.Create`)
**Severity**: High — the entire "add an image/media file to the project" surface is unusable; it raises a .NET `NullReferenceException` on every call.
**Reproducibility**: 100% (reproduced on two independent projects).
**Found by**: GramTrans feature 029 (sense-pictures) attended live proof, 2026-07-16.

---

## Summary

Calling `project.Senses.AddPicture(sense, image_path, caption)` — or any path that
reaches `MediaOperations.Create` — throws:

```
System.NullReferenceException: Object reference not set to an instance of an object.
   at SIL.LCModel.DomainImpl.CmFile.set_InternalPath(String value)
```

The immediate cause is that `MediaOperations.Create` sets `ICmFile.InternalPath`
on a **freshly-created, unowned** `CmFile` (never added to a `CmFolder`), and
LibLCM's `CmFile.set_InternalPath` dereferences the owning folder / cache, which
is `null` for an unowned object.

A **second, compounding defect** in `CopyToProject` means it never actually copies
the file: its guard tests `LinkedFilesRootDir` on the wrong object.

---

## Environment

- OS: Windows 11
- Host: FieldWorks / FLEx (LibLCM via pythonnet)
- flexicon build under test: `.../uv/cache/archive-v0/w7360QJI18oGbScq/Lib/site-packages/flexicon`
  (installed as `pyflexicon`; source repo `flexlibs2`)
- Driver: FLExToolsMCP `run_module`, write-enabled
- Writing systems / LinkedFiles: reproduced with and without
  `LangProject.LinkedFilesRootDir` set and with `LinkedFiles/Pictures` pre-created.

## Steps to reproduce

```python
# write-enabled session on any project
entry = project.LexEntry.Create("probe", "stem")
sense = list(project.Senses.GetAll(entry))[0]
# any real, existing image file on disk:
project.Senses.AddPicture(sense, r"C:\tmp\dog.png", "a dog",
                          project.GetDefaultAnalysisWSHandle())
# -> System.NullReferenceException at CmFile.set_InternalPath
```

Reproduced identically on two separate projects (one derived from a lexicon
project with no prior LinkedFiles, one derived from a project that already had a
LinkedFiles tree). Pre-setting `project.Cache.LangProject.LinkedFilesRootDir`
and creating `LinkedFiles/Pictures` did **not** change the outcome.

## Actual call chain / stack

```
LexSenseOperations.AddPicture              LexSenseOperations.py:2358
  -> MediaOperations.CopyToProject         MediaOperations.py:1284
       -> MediaOperations.Create           MediaOperations.py:190
            new_media.InternalPath = file_path.strip()
System.NullReferenceException
   at SIL.LCModel.DomainImpl.CmFile.set_InternalPath(String value)
```

## Root cause

### Defect 1 — `Create` sets `InternalPath` on an unowned `CmFile` (the NRE)

`MediaOperations.Create` (≈ lines 186–190):

```python
factory = self.project.project.ServiceLocator.GetService(ICmFileFactory)
new_media = factory.Create()          # <-- unowned ICmFile (no Owner / not in a CmFolder)
new_media.InternalPath = file_path.strip()   # <-- NRE: setter needs the owning folder/cache
```

`ICmFileFactory.Create()` returns an object that is **not yet owned** by any
`CmFolder`. In LibLCM a `CmFile` must be owned (added to a `CmFolder.FilesOC`)
before `InternalPath` is set, because `CmFile.set_InternalPath` resolves the
path against its owning folder / `LangProject.LinkedFilesRootDir`; with no owner,
that resolution dereferences `null`.

**Fix**: own the `CmFile` in the correct `CmFolder` *before* setting
`InternalPath`. For pictures/media the standard home folders are
`LangProject.PicturesOC` (Local Pictures) and `LangProject.MediaOC`. Prefer the
LibLCM helper that does this correctly rather than hand-wiring:

- Preferred: `ICmFolder.TryFindFile` / the LCM `CmFile` acquisition helpers
  (e.g. `DomainObjectServices`), which find-or-create an owned `CmFile` for a
  path in one step; **or**
- Minimal: add the new file to the owning folder first —
  ```python
  folder = <LangProject.PicturesOC[0] | LangProject.MediaOC>   # ensure it exists
  folder.FilesOC.Add(new_media)     # own it FIRST
  new_media.InternalPath = file_path.strip()   # now safe
  ```

### Defect 2 — `CopyToProject` never copies (guard on the wrong object)

`MediaOperations.CopyToProject` (≈ lines 1281–1284):

```python
if not hasattr(self.project.project, "LinkedFilesRootDir"):
    logger.warning("LinkedFilesRootDir not available, creating reference without copying")
    return self.Create(external_path, label, wsHandle)
```

`self.project.project` is the **`LcmCache`** (it is dereferenced as
`self.project.project.ServiceLocator...` elsewhere in this file).
`LinkedFilesRootDir` is **not** a member of `LcmCache`; it lives on
`ILangProject` (`self.project.project.LangProject.LinkedFilesRootDir`). So the
`hasattr` is **always False**, and `CopyToProject` always takes the
"reference-only, don't copy" fallback — meaning the image is never copied into
`LinkedFiles/…` even on a healthy project. (And because that fallback calls the
broken `Create`, it also raises.)

**Fix**: test/read the attribute on `LangProject`:

```python
lp = self.project.project.LangProject
if not getattr(lp, "LinkedFilesRootDir", None):
    ...
linked_files_dir = lp.LinkedFilesRootDir
```

Note the happy path also ends in `return self.Create(internal_path, …)`
(≈ line 1313), so **Defect 1 must be fixed for either path to work.**

## Expected behaviour

- `AddPicture` / `CopyToProject` create an owned `ICmFile`, set its
  `InternalPath` without error, copy the source file into
  `LinkedFiles/<subdir>/`, and return a picture/media whose `PictureFileRA` /
  `CmFile` resolves via `AbsoluteInternalPath`.

## Impact

- No image or media file can be added to a FLEx project through flexicon.
- Downstream: GramTrans feature 029 (sense-picture reproduction) uses
  `AddPicture` as its Move-leg asset-copy seam. The GramTrans module degrades
  gracefully (it catches the exception and emits a never-silent dropped-item
  report rather than crashing), but **it cannot copy picture assets on a host
  with this flexicon build**. The GramTrans logic itself is fully verified
  offline (unit suite with a faked seam) and imports/runs live; it is blocked
  only by this flexicon defect.

## Suggested test (regression)

```python
def test_add_picture_copies_and_wires_cmfile(tmp_path, writable_project):
    img = tmp_path / "dog.png"; img.write_bytes(MINIMAL_PNG)
    e = writable_project.LexEntry.Create("probe", "stem")
    s = list(writable_project.Senses.GetAll(e))[0]
    pic = writable_project.Senses.AddPicture(s, str(img), "a dog")
    cf = pic.PictureFileRA
    assert cf is not None
    assert cf.InternalPath                       # set, no NRE
    assert os.path.exists(cf.AbsoluteInternalPath)  # file actually copied
```

## Workaround (for callers, until fixed)

Bypass `MediaOperations` and own the `CmFile` before setting `InternalPath`:
create the `CmFile` via `ICmFileFactory`, add it to the appropriate
`CmFolder.FilesOC` (`LangProject.PicturesOC` / `MediaOC`), then set
`InternalPath` and copy the bytes with `shutil` — i.e. the raw-factory path
GramTrans already uses for its missing-binary fallback.
