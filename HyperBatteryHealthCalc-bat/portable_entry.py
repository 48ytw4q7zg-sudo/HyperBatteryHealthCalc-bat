"""GUI/CLI frozen entry point and a private-data-free executable self-test."""

from __future__ import annotations

import argparse
import contextlib
import io
import json
from pathlib import Path
import platform
import struct
import sys
import tempfile
import time
import traceback
import zipfile

from report_io import application_dir, resolve_app_path, save_text_report


def create_synthetic_archive(path: Path) -> None:
    """Create only invented diagnostics, never copy a user's input archive."""
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "dump/android.hardware.health-service.txt",
            "batteryFullChargeDesignCapacityUah: 5000000\n"
            "batteryCycleCount: 42\nbatteryFullChargeUah: 4500000\n",
        )
        archive.writestr(
            "dump/bugreport-synthetic.txt",
            "[ro.product.model]: [Portable Synthetic Device]\n"
            "Statistics since last charge:\n"
            "  Estimated battery capacity: 5000 mAh\n"
            "  Min learned battery capacity: 4500 mAh\n"
            "Estimated power use (mAh):\n"
            "  Capacity: 5000, Computed drain: 100, actual drain: 100\n"
            "  Global\n    cpu: 60\n    screen: 30\n"
            "  UID u0a123: 60\n  UID 1000: 30\n\n",
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("synthetic-inner.zip", inner.getvalue())


def run_self_test(output_path: Path) -> int:
    output_path = resolve_app_path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "schema": 1,
        "ok": False,
        "frozen": bool(getattr(sys, "frozen", False)),
        "pointer_bits": struct.calcsize("P") * 8,
        "machine": platform.machine(),
        "windows_version": platform.version(),
        "python_version": platform.python_version(),
        "executable": str(sys.executable),
        "application_dir": str(application_dir()),
        "stdout_is_none": sys.stdout is None,
        "stderr_is_none": sys.stderr is None,
        "checks": [],
    }

    def check(name: str, condition: bool) -> None:
        if not condition:
            raise AssertionError(name)
        result["checks"].append(name)

    try:
        import codecs
        import encodings.gbk
        import encodings.utf_8
        import zlib
        from battery_calc import Colors, is_interactive, main as cli_main
        from battery_core import BatteryExtractor
        from battery_gui import BatteryHealthApp, filedialog

        check("compressed_zip_and_encodings", bool(zlib.ZLIB_VERSION) and codecs.lookup("cp936").name == "gbk")
        check("no_console_import", sys.stdout is not None or not Colors().enabled)
        check("no_console_interactive_guard", sys.stdin is not None or not is_interactive())
        # All temporary synthetic data is under the explicitly requested output
        # directory. Never instantiate the normal GUI against real input/.
        with tempfile.TemporaryDirectory(prefix="battery-self-test-", dir=output_path.parent) as temporary:
            temporary_dir = Path(temporary).resolve()
            check("synthetic_workspace_contained", temporary_dir.is_relative_to(output_path.parent.resolve()))
            input_dir = temporary_dir / "input"
            synthetic = input_dir / "synthetic.zip"
            create_synthetic_archive(synthetic)
            info = BatteryExtractor().extract(synthetic)
            check("nested_synthetic_zip", info.design_capacity == 5000 and info.current_capacity == 4500)
            check("synthetic_health", info.health_percentage == 90)
            check("synthetic_power_ranking", [(x.uid, x.mah) for x in info.top_uid_power[:2]] == [("u0a123", 60), ("1000", 30)])

            class SyntheticApp(BatteryHealthApp):
                def _input_dir(self) -> Path:
                    return input_dir

            app = SyntheticApp()
            app.root.withdraw()
            try:
                check("gui_default_input_path", BatteryHealthApp._input_dir(app) == application_dir() / "input")
                tcl_dir = Path(app.root.tk.eval("info library")).resolve()
                tk_dir = Path(app.root.tk.eval("set tk_library")).resolve()
                check("tk_resources_loaded", (tcl_dir / "init.tcl").is_file() and (tk_dir / "tk.tcl").is_file())
                if result["frozen"]:
                    resource_dir = Path(sys._MEIPASS).resolve()
                    check("tk_resources_bundled", tcl_dir.is_relative_to(resource_dir) and tk_dir.is_relative_to(resource_dir))
                result["tcl_version"] = app.root.tk.eval("info patchlevel")
                result["tk_version"] = app.root.tk.eval("package require Tk")
                check("gui_save_disabled_before_analysis", app.save_btn.cget("state") == "disabled")
                app._analyze()
                deadline = time.monotonic() + 15
                while getattr(app, "_analysis_pending", False) and time.monotonic() < deadline:
                    app.root.update()
                    time.sleep(0.01)
                check("gui_background_analysis", not app._analysis_pending and app.current_info is not None)
                check("gui_report_rendered", "90.00%" in app.result_text.get("1.0", "end"))
                check("gui_save_enabled_after_analysis", app.save_btn.cget("state") == "normal")
                gui_report = temporary_dir / "gui-report.txt"
                original_dialog = filedialog.asksaveasfilename
                try:
                    filedialog.asksaveasfilename = lambda **_options: str(gui_report)
                    app._save_report()
                finally:
                    filedialog.asksaveasfilename = original_dialog
                check("gui_report_export", gui_report.read_text(encoding="utf-8-sig") == app._report_text + "\n")
                check("gui_report_export_utf8", gui_report.read_bytes().startswith(b"\xef\xbb\xbf"))
                original_archive = synthetic.read_bytes()
                input_protected = False
                try:
                    save_text_report(synthetic, app._report_text, synthetic)
                except ValueError:
                    input_protected = True
                check("gui_source_archive_protected", input_protected and synthetic.read_bytes() == original_archive)
                app.capacity_var.set("5200")
                check("gui_save_invalidated_on_edit", app.save_btn.cget("state") == "disabled" and not app._report_text)
            finally:
                app.root.destroy()

            report = temporary_dir / "reports" / "synthetic.txt"
            with contextlib.redirect_stdout(io.StringIO()):
                status = cli_main(["--input", str(input_dir), "--output", str(report), "--no-color", "--no-pause"])
            check("cli_synthetic_export", status == 0 and "90.00%" in report.read_text(encoding="utf-8"))
            check("atomic_report_cleanup", not list(report.parent.glob(".battery-report-*.tmp")))
        result["ok"] = True
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["traceback"] = traceback.format_exc()
    # A windowed executable cannot communicate success through stdout.
    output_path.write_text(json.dumps(result, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    return 0 if result["ok"] else 1


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--self-test" in args:
        parser = argparse.ArgumentParser(description="Portable executable self-test (synthetic data only)")
        parser.add_argument("--self-test", action="store_true", required=True)
        parser.add_argument("--self-test-output", type=Path, required=True)
        options = parser.parse_args(args)
        if options.self_test_output.suffix.lower() != ".json":
            parser.error("--self-test-output must name a .json file")
        return run_self_test(options.self_test_output)

    cli_mode = Path(sys.executable).stem.lower().endswith("-cli") and getattr(sys, "frozen", False)
    if "--cli" in args:
        args.remove("--cli")
        cli_mode = True
    if cli_mode:
        from battery_calc import main as cli_main
        return cli_main(args)
    if args:
        return 2
    from battery_gui import main as gui_main
    gui_main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
