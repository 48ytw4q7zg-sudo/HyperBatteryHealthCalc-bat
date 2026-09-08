"""Build acceptance checks, ZIP creation, and privacy inventory (no real input)."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "packaging"), str(ROOT / "HyperBatteryHealthCalc-bat")]


def owned(path: Path) -> Path:
    path = path.absolute()
    allowed = (ROOT / ".build", ROOT / "dist")
    if not any(path.is_relative_to(base) and path != base for base in allowed):
        raise ValueError(f"Not a task-owned build path: {path}")
    for item in (path, *path.parents):
        if item == ROOT:
            break
        if item.is_symlink() or item.is_junction():
            raise ValueError(f"Reparse points are not allowed: {item}")
    resolved = path.resolve()
    if not any(resolved.is_relative_to(base.resolve()) and resolved != base.resolve() for base in allowed):
        raise ValueError(f"Resolved path escapes the build roots: {resolved}")
    return resolved


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save_json(path: Path, value) -> None:
    owned(path).write_text(json.dumps(value, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run_process(command: list[str], cwd: Path, env: dict[str, str], log: Path, expected: int = 0, windowed: bool = False) -> dict:
    # Redirected pipes give pythonw real standard streams. A detached process
    # with no inherited handles exercises the actual double-click environment.
    completed = subprocess.run(command, cwd=cwd, env=env, capture_output=not windowed, timeout=60,
                               close_fds=True, creationflags=subprocess.DETACHED_PROCESS if windowed else subprocess.CREATE_NO_WINDOW)
    output = (completed.stdout or b"").decode("utf-8", "replace")
    error = (completed.stderr or b"").decode("utf-8", "replace")
    owned(log).write_text(output + error, encoding="utf-8")
    require(completed.returncode == expected, f"{Path(command[0]).name}: exit {completed.returncode}, expected {expected}; see {log}")
    return {"exit_code": completed.returncode, "stdout": output, "stderr": error}


def source_checks(work: Path, node: str) -> dict:
    import test_battery_core

    # Do not execute, open, rename, or temporarily hide the real diagnostic ZIP.
    skipped = ["test_real_xiaomi15pro_bugreport_extracts_snapshot_and_health",
               "test_cli_report_contains_chinese_usage_diagnostics"]
    for name in skipped:
        method = getattr(test_battery_core.BatteryCoreTests, name)
        setattr(test_battery_core.BatteryCoreTests, name, unittest.skip("Real diagnostic data is outside portable acceptance scope")(method))
    suite = unittest.defaultTestLoader.loadTestsFromNames(
        ["test_battery_core", "test_functional_completion", "test_portable"])
    with (work / "python-tests.txt").open("w", encoding="utf-8") as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    require(result.wasSuccessful(), f"Source tests failed; see {work / 'python-tests.txt'}")
    node_path = shutil.which(node)
    require(node_path is not None, "Node is required on the build host for existing web regression checks")
    node_result = run_process([node_path, str(ROOT / "test_web_logic.cjs")], ROOT, dict(os.environ), work / "node-tests.txt")
    source_json = work / "pythonw-self-test.json"
    run_process([str(Path(sys.executable).with_name("pythonw.exe")), str(ROOT / "HyperBatteryHealthCalc-bat" / "portable_entry.py"),
                 "--self-test", "--self-test-output", str(source_json)], work, dict(os.environ), work / "pythonw-process.txt", windowed=True)
    no_console = json.loads(source_json.read_text(encoding="utf-8"))
    require(no_console["ok"] and no_console["stdout_is_none"] and no_console["stderr_is_none"], "pythonw self-test did not exercise absent streams")
    return {"ok": True, "tests_run": result.testsRun, "tests_passed": result.testsRun - len(result.skipped),
            "tests_skipped": len(result.skipped), "skip_names": skipped,
            "node_result": node_result["stdout"].strip(), "pythonw_self_test": no_console}


def pe_info(path: Path) -> dict:
    with path.open("rb") as stream:
        require(stream.read(2) == b"MZ", f"Missing PE header: {path.name}")
        stream.seek(0x3C)
        offset = struct.unpack("<I", stream.read(4))[0]
        stream.seek(offset)
        header = stream.read(96)
    require(header[:4] == b"PE\0\0", f"Invalid PE header: {path.name}")
    machine = struct.unpack_from("<H", header, 4)[0]
    require(machine == 0x8664, f"Not an AMD64 binary: {path.name}: {machine:#x}")
    return {"machine": "AMD64", "subsystem": struct.unpack_from("<H", header, 24 + 68)[0]}


def inventory(bundle: Path) -> dict:
    expected_top = {"HyperBatteryHealthCalc.exe", "HyperBatteryHealthCalc-cli.exe", "README.txt", "LICENSE.txt", "_internal", "input", "reports"}
    require({p.name for p in bundle.iterdir()} == expected_top, "Unexpected distribution root content")
    require(not any((bundle / "input").iterdir()) and not any((bundle / "reports").iterdir()), "Release input/reports must be empty")
    records, binaries = [], []
    for path in sorted(bundle.rglob("*")):
        owned(path)
        if not path.is_file():
            continue
        relative = path.relative_to(bundle).as_posix()
        lower = relative.lower()
        require(not any(x in lower for x in ("bugreport", "diagnostic", ".env", "credentials", "battery-report", ".build/", "site-packages/")), f"Forbidden release file: {relative}")
        require(path.suffix.lower() not in {".log", ".key", ".pem", ".pfx", ".py", ".pyc", ".ps1", ".bat"}, f"Unexpected source/private file: {relative}")
        if path.suffix.lower() == ".zip":
            require(relative == "_internal/base_library.zip", f"Unexpected ZIP: {relative}")
            with zipfile.ZipFile(path) as archive:
                require(all(x.endswith(".pyc") for x in archive.namelist()), "Non-stdlib payload in base_library.zip")
        if path.suffix.lower() in {".exe", ".dll", ".pyd"}:
            binaries.append({"path": relative, **pe_info(path)})
        records.append({"path": relative, "bytes": path.stat().st_size, "sha256": digest(path)})
    require(pe_info(bundle / "HyperBatteryHealthCalc.exe")["subsystem"] == 2, "GUI must be windowed")
    require(pe_info(bundle / "HyperBatteryHealthCalc-cli.exe")["subsystem"] == 3, "CLI must retain its console")
    return {"files": records, "file_count": len(records), "total_bytes": sum(x["bytes"] for x in records),
            "pe_binaries": binaries, "input_empty": True, "reports_empty": True,
            "privacy_check": "Allowlisted build inputs, filename inventory, empty user directories, and stdlib ZIP member check"}


def bundle_checks(bundle: Path, work: Path, archive_path: Path) -> dict:
    from portable_entry import create_synthetic_archive

    before = inventory(bundle)
    with zipfile.ZipFile(owned(archive_path), "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        archive.write(bundle, bundle.name + "/")
        for path in sorted(bundle.rglob("*")):
            archive.write(path, (Path(bundle.name) / path.relative_to(bundle)).as_posix())
    relocation = owned(work / "USB \u4e2d\u6587 \u8def\u5f84")
    relocation.mkdir()
    with zipfile.ZipFile(archive_path) as archive:
        require(archive.testzip() is None, "ZIP CRC failure")
        for member in archive.namelist():
            name = PurePosixPath(member)
            require(not name.is_absolute() and ".." not in name.parts and "\\" not in member, "Unsafe ZIP member")
        archive.extractall(relocation)
    extracted = owned(relocation / bundle.name)
    moved = owned(relocation / "\u79fb\u52a8\u540e\u7684 Battery Tool")
    extracted.rename(moved)
    require(inventory(moved) == before, "ZIP extraction changed the payload")
    other_cwd = owned(work / "unrelated working directory")
    other_cwd.mkdir()
    minimal = {key: value for key, value in os.environ.items() if key.upper() in {"SYSTEMROOT", "WINDIR", "SYSTEMDRIVE", "COMSPEC"}}
    minimal["PATH"] = str(Path(os.environ["SystemRoot"]) / "System32")
    minimal["TEMP"] = minimal["TMP"] = str(owned(work / "temp"))
    require(shutil.which("python", path=minimal["PATH"]) is None and shutil.which("node", path=minimal["PATH"]) is None, "Minimal PATH exposes development tools")
    self_tests = {}
    for name in ("HyperBatteryHealthCalc", "HyperBatteryHealthCalc-cli"):
        output = work / (name + "-self-test.json")
        run_process([str(moved / (name + ".exe")), "--self-test", "--self-test-output", str(output)], other_cwd, minimal, work / (name + "-process.txt"), windowed=name == "HyperBatteryHealthCalc")
        data = json.loads(output.read_text(encoding="utf-8"))
        require(data["ok"] and data["frozen"] and data["pointer_bits"] == 64, f"Self-test failed: {name}")
        require(Path(data["application_dir"]) == moved, "Self-test used an old application path")
        if name == "HyperBatteryHealthCalc":
            require(data["stdout_is_none"] and data["stderr_is_none"], "GUI did not run windowed")
        self_tests[name] = data
    cli = str(moved / "HyperBatteryHealthCalc-cli.exe")
    help_result = run_process([cli, "--help"], other_cwd, minimal, work / "cli-help.txt")
    require("--input" in help_result["stdout"], "CLI help is missing")
    create_synthetic_archive(moved / "input" / "synthetic.zip")
    run_process([cli, "--no-color", "--no-pause"], other_cwd, minimal, work / "cli-default.txt")
    default_report = moved / "reports" / "battery-report.txt"
    require("90.00%" in default_report.read_text(encoding="utf-8"), "Default report missing")
    require(not (other_cwd / "reports").exists(), "Report was written relative to cwd")
    run_process([cli, "--input", "input", "--output", "reports/\u4e2d\u6587 report.txt", "--no-color", "--no-pause"], other_cwd, minimal, work / "cli-relative.txt")
    require("90.00%" in (moved / "reports" / "\u4e2d\u6587 report.txt").read_text(encoding="utf-8"), "Relative unicode report failed")
    run_process([cli, "--input", "missing input", "--no-pause"], other_cwd, minimal, work / "cli-missing-input.txt", expected=1)
    broken_dir = moved / "broken input"
    broken_dir.mkdir()
    (broken_dir / "synthetic-broken.zip").write_bytes(b"invalid synthetic zip")
    run_process([cli, "--input", "broken input", "--no-pause"], other_cwd, minimal, work / "cli-corrupt-input.txt", expected=1)
    require(inventory(bundle) == before, "Acceptance tests modified the clean release payload")
    result = {"ok": True, "host": {"system": platform.system(), "release": platform.release(),
              "version": platform.version(), "edition": platform.win32_edition(), "machine": platform.machine(),
              "pointer_bits": struct.calcsize("P") * 8}, "minimal_path": minimal["PATH"],
              "python_on_path": False, "relocated_from_zip": True, "unicode_and_space_paths": True,
              "different_working_directory": True, "self_tests": self_tests,
              "cli_checks": ["help", "default_input_and_export", "relative_unicode_output", "missing_input_exit_1", "corrupt_zip_exit_1"],
              "inventory": before, "zip": {"name": archive_path.name, "bytes": archive_path.stat().st_size, "sha256": digest(archive_path)},
              "compatibility_limits": ["Only the recorded host Windows build was executed", "No clean Windows 10/11 VM or physical USB filesystem was tested"]}
    save_json(work / "bundle-verification.json", result)
    # Validate absolute containment immediately before each recursive cleanup.
    shutil.rmtree(owned(relocation))
    shutil.rmtree(owned(other_cwd))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--source-only", action="store_true")
    parser.add_argument("--node", default="node")
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    require(sys.platform == "win32" and struct.calcsize("P") == 8, "Build verification requires Windows x64 Python")
    work = owned(args.work_dir)
    work.mkdir(parents=True, exist_ok=True)
    temp = owned(work / "temp")
    temp.mkdir(exist_ok=True)
    os.environ["TEMP"] = os.environ["TMP"] = str(temp)
    tempfile.tempdir = str(temp)
    if args.source_only:
        result = source_checks(work, args.node)
        save_json(work / "source-verification.json", result)
        print(json.dumps({key: result[key] for key in ("ok", "tests_run", "tests_passed", "tests_skipped", "node_result")}))
    else:
        require(args.bundle is not None and args.archive is not None, "--bundle and --archive are required")
        result = bundle_checks(owned(args.bundle), work, owned(args.archive))
        print(json.dumps({"ok": result["ok"], "host": result["host"], "file_count": result["inventory"]["file_count"],
                          "bundle_bytes": result["inventory"]["total_bytes"], "zip": result["zip"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
