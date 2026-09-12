# AGENTS.md

Agent instructions for `HyperBatteryHealthCalc-main` (portable battery health calculator).

## Project map
- Core logic: `HyperBatteryHealthCalc-bat/battery_core.py`
- CLI: `HyperBatteryHealthCalc-bat/battery_calc.py`
- GUI: `HyperBatteryHealthCalc-bat/battery_gui.py`
- Report I/O: `HyperBatteryHealthCalc-bat/report_io.py`
- Portable entry: `HyperBatteryHealthCalc-bat/portable_entry.py`
- Packaging: `packaging/verify_portable.py`, `packaging/windows.spec`, `build_windows.ps1`
- Tests: `test_battery_core.py`, `test_functional_completion.py`, `packaging/test_portable.py`, `packaging/test_gui_export.py`
- Optional smoke helpers: `HyperBatteryHealthCalc-bat/battery_smoke.py`, `report_io_smoke.py`

## Hard rules
- **Do not open, parse, or depend on the real diagnostic ZIP** (`HyperBatteryHealthCalc-bat/input/bugreport-*.zip`) in portable acceptance or default tests. Use synthetic archives.
- Local-only changes: do **not** push to GitHub unless the user explicitly asks.
- Prefer smallest production change; keep CLI/GUI/report contracts stable.
- Target platform remains Windows 10/11 x64. Windows 10 physical testing is user-waived (2026-09-08); physical USB remains unverified. Do not invent evidence.
- Reports must stay executable-relative under frozen mode (not cwd-relative).

## Runtime
- Windows x64 Python (project historically used a local build venv under `.build/` when present)
- Node is required for web regression checks in packaging source gates
- Prefer synthetic inputs for all automated tests

## Test commands
```powershell
# Core + functional (skip real-data tests if the diagnostic zip is absent/untouched)
python -m unittest test_battery_core test_functional_completion -v

# Portable behavior + GUI export
python -m unittest packaging.test_portable packaging.test_gui_export -v

# Node web logic (if Node on PATH)
node test_web_logic.cjs
```

Note: packaging source checks intentionally skip:
- `test_real_xiaomi15pro_bugreport_extracts_snapshot_and_health`
- `test_cli_report_contains_chinese_usage_diagnostics`

## Coding standards
- Shared behavior lives in `battery_core.py`; CLI/GUI are thin adapters.
- Atomic report writes and unicode/space path safety are release requirements.
- No credentials or personal device logs in the repo; delete stale diagnostic blobs that are not part of the portable contract.

## Delivery
- Report exact changed files, test results, and remaining unverified items (USB, other Windows builds).
- Do not delete `.build/` acceptance evidence without explicit user request; prefer deleting clearly obsolete `dist/` siblings and unused diagnostic inputs.
