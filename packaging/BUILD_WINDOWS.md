# Windows portable build

The target is Windows 10/11 x64. Build on Windows with an x64 CPython installation
that includes Tk and LICENSE.txt. The initial build uses CPython 3.14.4 and
PyInstaller 6.22.2. Node is a build-host-only requirement for existing web tests.
Target machines need neither Python nor Node.

Run from PowerShell 5.1 or later:

```powershell
& .\build_windows.ps1 -Python 'C:\Python314\python.exe' -Node 'C:\Program Files\nodejs\node.exe'
```

The script creates a unique isolated venv, temporary directory, PyInstaller cache,
work directory, and release candidate under `.build/windows-<timestamp>-<id>`.
It installs wheel-only build dependencies from official PyPI with pip isolated
mode and records resolved versions. No global packages or settings are changed.
The spec disables UPX and shares one `_internal` runtime between the windowed GUI
and console CLI. Only explicit application imports and Python's license are
collected. Browser pages, source folders, diagnostics, input ZIPs and reports are
not collected. The final folder contains empty `input/` and `reports/` directories.

Source acceptance runs existing Python tests plus `packaging/test_portable.py`,
the existing Node assertions, and a real pythonw self-test. The two existing tests
that open the real diagnostic archive are explicitly skipped without touching it.
All temporary test data is redirected below the project build directory.

Binary acceptance verifies AMD64 PE headers, GUI/CLI subsystems, all payload hashes,
the filename privacy inventory, and the standard-library ZIP members. It creates
the deliverable ZIP, checks CRCs, extracts it, and moves the resulting folder to a
path containing Chinese characters and spaces. Both EXEs run with a different cwd,
only System32 on PATH, no Python/Node on PATH, and no inherited Python/Tk paths.
Self-tests load real Tcl/Tk resources, create/withdraw/destroy the application's own
Tk window, parse a compressed synthetic nested ZIP, exercise the GUI worker/report,
and export a CLI report. CLI help, default and relative paths, Unicode output paths,
missing input, and corrupt synthetic ZIP failures are also exercised.

Acceptance artifacts are retained in each build's `evidence/`: source and binary
JSON results, test outputs, source hashes, resolved build dependencies, and final
`build-result.json`. Temporary relocated program copies are removed after recording
evidence. Every recursive removal/move checks resolved containment under `.build`
or `dist` and rejects reparse points. Failures preserve the candidate for diagnosis.
Sources are hashed before and after the build; concurrent changes prevent publishing
that candidate. The existing release is never deleted or overwritten.

After checks pass, a unique directory under `dist/` contains the one-folder bundle,
`HyperBatteryHealthCalc-Windows-x64.zip`, and `SHA256SUMS.txt`. This is a prepared,
locally verified artifact pending the parent's independent review. It is unsigned.
Running on the build host with minimal PATH establishes bundled-runtime operation,
but does not substitute for a clean Windows 10/11 machine or physical USB test.

Official packaging references:
- https://pyinstaller.org/en/stable/usage.html
- https://pyinstaller.org/en/stable/runtime-information.html
- https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html
- https://pypi.org/project/pyinstaller/6.22.2/
