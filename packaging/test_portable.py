"""Focused portable behavior tests; all fixtures are synthetic."""

import contextlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "HyperBatteryHealthCalc-bat"
sys.path.insert(0, str(APP))

from battery_calc import Colors, is_interactive, main as cli_main
from battery_gui import BatteryHealthApp
from portable_entry import create_synthetic_archive
from report_io import application_dir, configure_standard_streams, resolve_app_path


class PortableTests(unittest.TestCase):
    def test_source_directory_stays_next_to_modules(self):
        self.assertEqual(application_dir(), APP)

    def test_frozen_paths_follow_executable_with_unicode_and_spaces(self):
        executable = ROOT / ".build" / "USB \u4e2d\u6587" / "Battery Tool.exe"
        with patch.object(sys, "frozen", True, create=True), patch.object(sys, "executable", str(executable)):
            self.assertEqual(application_dir(), executable.parent)
            self.assertEqual(resolve_app_path(Path("reports/result.txt")), executable.parent / "reports/result.txt")
            self.assertEqual(BatteryHealthApp._input_dir(None), executable.parent / "input")

    def test_explicit_absolute_paths_stay_absolute(self):
        path = ROOT / ".build" / "chosen" / "report.txt"
        with patch.object(sys, "frozen", True, create=True):
            self.assertEqual(resolve_app_path(path), path)

    def test_windowed_import_has_no_stdio_dependency(self):
        code = "import sys; sys.stdin = sys.stdout = sys.stderr = None; import battery_calc; assert not battery_calc.Colors().enabled; assert not battery_calc.is_interactive()"
        result = subprocess.run([sys.executable, "-c", code], cwd=APP, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))

    def test_none_and_redirected_streams_are_safe(self):
        with patch.object(sys, "stdin", None), patch.object(sys, "stdout", None), patch.object(sys, "stderr", None):
            configure_standard_streams()
            self.assertFalse(Colors().enabled)
            self.assertFalse(is_interactive())
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
            configure_standard_streams()
            print("redirected")
        self.assertEqual(stream.getvalue(), "redirected\n")

    def test_frozen_cli_uses_default_input_and_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            create_synthetic_archive(folder / "input" / "synthetic.zip")
            with patch.object(sys, "frozen", True, create=True), patch.object(sys, "executable", str(folder / "Battery-cli.exe")), contextlib.redirect_stdout(io.StringIO()):
                result = cli_main(["--no-color", "--no-pause"])
            self.assertEqual(result, 0)
            self.assertIn("90.00%", (folder / "reports" / "battery-report.txt").read_text(encoding="utf-8"))

    def test_frozen_cli_relative_overrides_are_executable_relative(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            create_synthetic_archive(folder / "chosen input" / "synthetic.zip")
            with patch.object(sys, "frozen", True, create=True), patch.object(sys, "executable", str(folder / "Battery-cli.exe")), contextlib.redirect_stdout(io.StringIO()):
                result = cli_main(["--input", "chosen input", "--output", "chosen output/report.txt", "--no-color", "--no-pause"])
            self.assertEqual(result, 0)
            self.assertIn("90.00%", (folder / "chosen output" / "report.txt").read_text(encoding="utf-8"))


class GuiZipSelectionTests(unittest.TestCase):
    @contextlib.contextmanager
    def portable_app(self, folder, recursive=False):
        with patch.object(sys, "frozen", True, create=True), patch.object(sys, "executable", str(folder / "Battery Tool.exe")):
            app = BatteryHealthApp.__new__(BatteryHealthApp)
            app.file_path_index = {}
            app.file_combo = {}
            app.file_var = Mock()
            app.recursive_scan = Mock()
            app.recursive_scan.get.return_value = recursive
            app._set_status = Mock()
            app._refresh_file_list()
            yield app

    def test_gui_zip_selection_prefers_input_mapping_over_root_collision(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            expected = folder / "input" / "sample.zip"
            create_synthetic_archive(folder / "sample.zip")
            create_synthetic_archive(expected)
            with self.portable_app(folder) as app:
                self.assertEqual(app.file_combo["values"], ["sample.zip"])
                selected = app.file_var.set.call_args.args[0]
                self.assertEqual(app._resolve_selected_zip(selected), expected)

    def test_gui_zip_selection_prefers_nested_mapping_over_relative_collision(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            relative = Path("nested") / "sample.zip"
            expected = folder / "input" / relative
            create_synthetic_archive(folder / relative)
            create_synthetic_archive(expected)
            with self.portable_app(folder, recursive=True) as app:
                self.assertEqual(app.file_combo["values"], [str(relative)])
                selected = app.file_var.set.call_args.args[0]
                self.assertEqual(app._resolve_selected_zip(selected), expected)

    def test_gui_zip_selection_preserves_absolute_browsed_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / "portable"
            browsed = Path(temporary) / "chosen location" / "sample.zip"
            create_synthetic_archive(folder / "sample.zip")
            create_synthetic_archive(folder / "input" / "sample.zip")
            create_synthetic_archive(browsed)
            with self.portable_app(folder) as app, patch("battery_gui.filedialog.askopenfilename", return_value=str(browsed)):
                app._browse_file()
                selected = app.file_var.set.call_args.args[0]
                self.assertEqual(selected, str(browsed))
                self.assertEqual(app._resolve_selected_zip(selected), browsed)

    def test_gui_zip_selection_rejects_missing_mapping_without_fallback(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            mapped = folder / "input" / "sample.zip"
            create_synthetic_archive(folder / "sample.zip")
            create_synthetic_archive(mapped)
            create_synthetic_archive(folder / "input" / "other" / "sample.zip")
            with self.portable_app(folder, recursive=True) as app:
                self.assertEqual(app.file_path_index["sample.zip"], mapped)
                mapped.unlink()
                # A stale list choice must not search for a substitute archive.
                with patch("battery_gui.resolve_app_path") as resolve, patch.object(app, "_collect_zip_files") as collect:
                    self.assertIsNone(app._resolve_selected_zip("sample.zip"))
                    resolve.assert_not_called()
                    collect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
