# Deploying Care Manager to the office PCs

The exe is distributed through the shared network folder; each PC launches a
local copy that self-updates from the share. GitHub Releases carry the build
from the dev machine (not on the office network) to the office.

```
dev machine                    GitHub                office
deploy\deploy.ps1  ──release──▶  ⬡  ──update-share.ps1──▶ \\SERVER\Share\CareManagerApp\
                                                              │ Care Manager.exe
                                                              │ version.txt
                                              every PC's launcher.bat copies when
                                              newer, then starts the local copy
```

## One-time setup

**Shared folder:** create `\\SERVER\Share\CareManagerApp\` (any name works —
use the same path everywhere below).

**Each office PC:**
1. Copy `deploy\launcher.bat` somewhere local (e.g. `C:\CareManager\`), edit
   the `SHARE=` line to the folder above.
2. Right-click → New shortcut to the .bat on the Desktop; in shortcut
   Properties set *Run: Minimized* and *Change Icon…* to `bowery-emblem.ico`.
   Staff use this shortcut; it updates-then-launches every time.

**One office PC (the "updater"):** install GitHub CLI
(`winget install GitHub.cli`), run `gh auth login` with an account that can
read this repo, and keep a copy of `deploy\update-share.ps1`. Optional:
schedule it (Task Scheduler, daily) for fully automatic updates.

## Releasing an update

On the dev machine:

```powershell
.\deploy\deploy.ps1          # builds + publishes a GitHub release
```

On the updater office PC:

```powershell
.\update-share.ps1 -ShareDir "\\SERVER\Share\CareManagerApp"
```

Done — every PC gets the new build the next time someone starts the app.
A PC that's already running the app keeps the old build until it's restarted.

The build version (date + git commit, e.g. `2026.07.09-1350-11b8503`) shows in
the app's title bar, so you can always check what a PC is running. Running
from source shows `dev`.

## Notes

- If the dev machine can ever see the share directly, skip GitHub:
  `.\deploy\deploy.ps1 -ShareDir "\\SERVER\Share\CareManagerApp"`.
- The launcher never fails on a flaky network: if the share is unreachable it
  just starts the existing local copy.
- Replacing the exe **in the share** is always safe while people are using
  the app — they run local copies, nothing locks the shared file.
- If antivirus/SmartScreen ever flags a new build, set `upx=False` in
  CareManager.spec first (known false-positive trigger for PyInstaller exes).
