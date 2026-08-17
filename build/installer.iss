; Inno Setup script for the SUPPORTED artifact (FR-046, T044).
;
; Wraps the PyInstaller onedir tree (dist\GramTrans\) into
; GramTrans-Setup-<version>.exe with a Start Menu entry and an uninstaller.
;
; Driven by build\build.py, which passes:
;     /DAppVersion=<git describe>   /DRepoRoot=<repo root>
; Do not run ISCC by hand for a release: build.py is what creates the throwaway
; venv, installs from the hash-pinned lock and stamps _buildinfo.py.
;
; The onefile portable executable is deliberately NOT wrapped. It is
; best-effort (it unpacks to a temp directory on every launch, which interacts
; badly with both pythonnet assembly loading and antivirus), and shipping an
; installer for it would imply a support commitment we are not making.
;
; The artifact is UNSIGNED. FR-051 requires the release notes to say so and to
; describe the SmartScreen warning a user will see; there is deliberately no
; SignTool directive here pretending otherwise.

#ifndef AppVersion
  #define AppVersion "0.0.0-unknown"
#endif
#ifndef RepoRoot
  #define RepoRoot ".."
#endif

#define AppName "GramTrans"
#define AppPublisher "SIL"
#define AppExeName "GramTrans.exe"

[Setup]
; Fixed for the lifetime of the product: Inno Setup keys upgrades and
; uninstalls off this, so changing it would strand every existing install.
AppId={{7E6C3B21-4E6A-4E1F-9E2A-034ABCDEF012}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
; Per-user by default: a linguist on a managed laptop usually cannot elevate,
; and GramTrans needs no machine-wide state -- its log lives in %LOCALAPPDATA%
; and FieldWorks is a separate, user-installed prerequisite (FR-045).
PrivilegesRequiredOverridesAllowed=dialog
PrivilegesRequired=lowest
OutputDir={#RepoRoot}\build\dist
OutputBaseFilename={#AppName}-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
DisableProgramGroupPage=yes
UninstallDisplayName={#AppName} {#AppVersion}
UninstallDisplayIcon={app}\{#AppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; \
    GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
; The whole onedir tree, verbatim. `recursesubdirs` matters: PyInstaller puts
; almost everything under _internal\, including clr_loader's native
; ClrLoader.dll and pythonnet's Python.Runtime.dll.
Source: "{#RepoRoot}\build\dist\{#AppName}\*"; DestDir: "{app}"; \
    Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; \
    Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; \
    Description: "Start {#AppName}"; \
    Flags: nowait postinstall skipifsilent

[UninstallDelete]
; PyInstaller and Python leave __pycache__ directories behind that the file
; list does not know about; without this the uninstaller leaves an app folder
; the user has to delete by hand.
Type: filesandordirs; Name: "{app}\_internal\__pycache__"

; NOT removed on uninstall: %LOCALAPPDATA%\GramTrans\logs. FR-038 requires the
; logs be retained, and a user uninstalling after a bad run is exactly the
; person who still needs them.
