# Build only the explicit application entry and the modules it imports.
# Never collect a project tree, input/, reports/, browser files, or user data.
from pathlib import Path
import sys

ROOT = Path(SPECPATH).parent
APP = ROOT / "HyperBatteryHealthCalc-bat"
python_license = Path(sys.base_prefix) / "LICENSE.txt"
if not python_license.is_file():
    raise RuntimeError("The build Python installation must include LICENSE.txt")

a = Analysis(
    [str(APP / "portable_entry.py")],
    pathex=[str(APP)],
    binaries=[],
    datas=[(str(python_license), "licenses/python")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["unittest", "pytest", "pip", "setuptools", "PyInstaller"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
gui = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="HyperBatteryHealthCalc",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    uac_admin=False,
    contents_directory="_internal",
)
cli = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="HyperBatteryHealthCalc-cli",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    uac_admin=False,
    contents_directory="_internal",
)
COLLECT(
    gui, cli, a.binaries, a.datas,
    strip=False,
    upx=False,
    name="HyperBatteryHealthCalc",
)
