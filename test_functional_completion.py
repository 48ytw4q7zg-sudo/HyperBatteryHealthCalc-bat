import contextlib
import io
import sys
import tempfile
import unittest
import threading
import struct
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent / 'HyperBatteryHealthCalc-bat'))
from battery_core import BatteryExtractor, BatteryInfo
from battery_calc import build_parser, main as cli_main, write_report_atomic
from battery_gui import BatteryHealthApp


class FunctionalCompletionTests(unittest.TestCase):
    def test_invalid_learned_capacity_uses_valid_fallback(self):
        for value in (0, -1, float('nan'), float('inf')):
            with self.subTest(value=value):
                info = BatteryInfo(min_learned_capacity=value, charge_counter=4500, battery_level=100)
                self.assertEqual(info.current_capacity, 4500)
                self.assertIn('Charge counter', info.current_capacity_source)

    def test_charge_counter_respects_scale_and_validity(self):
        for level, scale, expected in ((100, 200, None), (10, 10, 4500), (190, 200, 4500), (101, 100, None), (100, 0, None)):
            with self.subTest(level=level, scale=scale):
                info = BatteryInfo(charge_counter=4500, battery_level=level, battery_scale=scale)
                self.assertEqual(info.current_capacity, expected)
        self.assertIsNone(BatteryInfo(charge_counter=-1, battery_level=100).current_capacity)

    def test_invalid_design_capacity_cannot_produce_health(self):
        for value in (0, -1, float('nan'), float('inf')):
            info = BatteryInfo(design_capacity=value, min_learned_capacity=4500)
            self.assertFalse(info.has_design_capacity)
            self.assertIsNone(info.health_percentage)

    def test_cli_rejects_nonfinite_and_nonpositive_capacity(self):
        for value in ('nan', 'inf', '-inf', '0', '-1'):
            with self.subTest(value=value), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                build_parser().parse_args(['--capacity=' + value])
        self.assertEqual(build_parser().parse_args(['--capacity', '5000']).capacity, 5000)

    def test_gui_selection_keeps_browsed_path(self):
        app = BatteryHealthApp.__new__(BatteryHealthApp)
        app.file_var = MagicMock()
        app.file_combo = MagicMock()
        app._set_status = MagicMock()
        with patch('battery_gui.filedialog.askopenfilename', return_value='D:/diagnostic.zip'):
            app._browse_file()
        app.file_var.set.assert_called_once_with('D:/diagnostic.zip')
        app.file_combo.set.assert_not_called()

    def test_gui_manual_capacity_is_validated(self):
        app = BatteryHealthApp.__new__(BatteryHealthApp)
        app.capacity_entry = MagicMock()
        for value in ('nan', 'inf', '-1', '0'):
            app.capacity_entry.get.return_value = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                app._apply_manual_capacity(BatteryInfo())
        app.capacity_entry.get.return_value = '5100'
        info = BatteryInfo(design_capacity=5000)
        app._apply_manual_capacity(info)
        self.assertEqual(info.design_capacity, 5100)

    def test_mixed_archive_preserves_outer_bugreport(self):
        nested = io.BytesIO()
        with zipfile.ZipFile(nested, 'w') as archive:
            archive.writestr('android.hardware.health.txt', 'batteryFullChargeDesignCapacityUah: 5000000\nbatteryCycleCount: 123\n')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'report.zip'
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('bugreport-inner.zip', nested.getvalue())
                archive.writestr('bugreport.txt', 'Statistics since last charge:\nMin learned battery capacity: 4500 mAh\n\n')
            info = BatteryExtractor().extract(path)
        self.assertEqual(info.design_capacity, 5000)
        self.assertEqual(info.current_capacity, 4500)
        self.assertEqual(info.cycle_count, 123)

    def test_statistics_include_days_and_compact_duration(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'report.zip'
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('bugreport.txt', 'Statistics since last charge:\nTime on battery: 1d2h3m4s (100.0%) realtime\nMin learned battery capacity: 4500 mAh\n\n')
            info = BatteryExtractor().extract(path)
        self.assertEqual(info.time_on_battery_seconds, 93784)

    def test_cli_exports_partial_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'report.zip'
            output = Path(directory) / 'snapshot.txt'
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('bugreport.txt', '[ro.product.model]: [Snapshot Device]\nCurrent Battery Service state:\nlevel: 20\nscale: 100\nCharge counter: 1000000\ntemperature: 345\n')
            with patch('battery_calc.is_interactive', return_value=False), contextlib.redirect_stdout(io.StringIO()):
                result = cli_main(['--input', directory, '--capacity', '5000', '--output', str(output), '--no-pause', '--no-color'])
            self.assertEqual(result, 1)
            self.assertTrue(output.exists(), 'partial report was discarded')
            text = output.read_text(encoding='utf8')
            self.assertIn('Snapshot Device', text)
            self.assertIn('34.5', text)
            self.assertNotIn('None mAh', text)

    def test_cli_export_failure_sets_failure_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'report.zip'
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('bugreport.txt', 'Statistics since last charge:\nEstimated battery capacity: 5000 mAh\nMin learned battery capacity: 4500 mAh\n\n')
            with patch('battery_calc.is_interactive', return_value=False), contextlib.redirect_stdout(io.StringIO()):
                result = cli_main(['--input', directory, '--output', directory, '--no-pause', '--no-color'])
            self.assertEqual(result, 1, 'failed report export must not report success')

    def test_gui_partial_report_keeps_snapshot(self):
        app = BatteryHealthApp.__new__(BatteryHealthApp)
        report = app._build_error_report(BatteryInfo(battery_level=20, battery_scale=100, charge_counter=1000, temperature_c=34.5))
        self.assertIn('34.5', report)
        self.assertIn('20.0%', report)
        self.assertNotIn('None mAh', report)

    def test_gui_directory_failure_is_recoverable(self):
        app = BatteryHealthApp.__new__(BatteryHealthApp)
        app.file_combo = MagicMock()
        app._set_status = MagicMock()
        with patch.object(Path, 'mkdir', side_effect=PermissionError('test directory unavailable')):
            app._refresh_file_list()
        self.assertEqual(app.file_path_index, {})
        self.assertIn('test directory unavailable', app._set_status.call_args.args[0])

    def test_failed_atomic_export_preserves_previous_report(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'report.txt'
            path.write_text('previous report', encoding='utf8')
            with patch('battery_calc.os.replace', side_effect=OSError('export unavailable')), self.assertRaises(OSError):
                write_report_atomic(path, 'new report')
            self.assertEqual(path.read_text(encoding='utf8'), 'previous report')
            self.assertEqual(list(Path(directory).glob('.battery-report-*.tmp')), [])

    def test_gui_worker_keeps_ui_free_and_discards_stale_result(self):
        app = BatteryHealthApp.__new__(BatteryHealthApp)
        app.file_var = MagicMock()
        app.file_var.get.return_value = 'report.zip'
        app.capacity_entry = MagicMock()
        app.capacity_entry.get.return_value = ''
        app._resolve_selected_zip = MagicMock(return_value=MagicMock(is_file=lambda: True))
        app.analyze_btn = MagicMock()
        app._set_status = MagicMock()
        app._clear_result = MagicMock()
        app._show_result = MagicMock()
        app.root = MagicMock()
        app.extractor = MagicMock()
        started, release = threading.Event(), threading.Event()
        def extract(_):
            started.set()
            release.wait(2)
            return BatteryInfo(design_capacity=5000, min_learned_capacity=4500)
        app.extractor.extract.side_effect = extract
        workers = []
        def make_thread(*args, **kwargs):
            thread = threading.Thread(*args, **kwargs)
            workers.append(thread)
            return thread
        with patch('battery_gui.Thread', side_effect=make_thread):
            app._analyze()
        self.assertTrue(started.wait(1))
        self.assertTrue(app._analysis_pending)
        app.root.update.assert_not_called()
        app.file_var.get.return_value = 'new-report.zip'
        release.set()
        workers[0].join(2)
        self.assertFalse(workers[0].is_alive())
        app.root.after.call_args.args[1]()
        self.assertFalse(app._analysis_pending)
        app._show_result.assert_not_called()

    def test_corrupt_compressed_entry_does_not_hide_next_candidate(self):
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('bugreport-a.txt', 'Statistics since last charge:\nMin learned battery capacity: 4000 mAh\n\n')
            archive.writestr('bugreport-b.txt', 'Statistics since last charge:\nEstimated battery capacity: 5000 mAh\nMin learned battery capacity: 4500 mAh\n\n')
        corrupt = bytearray(data.getvalue())
        name_length, extra_length = struct.unpack_from('<HH', corrupt, 26)
        corrupt[30 + name_length + extra_length] = 7
        info = BatteryExtractor().extract(io.BytesIO(corrupt))
        self.assertEqual(info.health_percentage, 90)
        self.assertTrue(info.parse_warnings)

    def test_invalid_estimate_does_not_block_later_valid_value(self):
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w') as archive:
            for name, capacity in [('bugreport-a.txt', 0), ('bugreport-b.txt', 5000)]:
                archive.writestr(name, f'Statistics since last charge:\nEstimated battery capacity: {capacity} mAh\nMin learned battery capacity: 4500 mAh\n\n')
        data.seek(0)
        self.assertEqual(BatteryExtractor().extract(data).health_percentage, 90)

    def test_cli_missing_capacity_in_noninteractive_mode_is_incomplete(self):
        output = io.StringIO()
        with patch('battery_calc.collect_zip_files', return_value=[Path('synthetic.zip')]), patch('battery_calc.BatteryExtractor.extract', return_value=BatteryInfo(min_learned_capacity=4500)), patch('battery_calc.is_interactive', return_value=False), contextlib.redirect_stdout(output):
            result = cli_main(['--input', str(Path(__file__).parent), '--no-color', '--no-pause'])
        self.assertEqual(result, 1)
        self.assertNotIn('用户跳过', output.getvalue())

    def test_corrupt_candidate_cannot_publish_partially_parsed_values(self):
        data = io.BytesIO()
        first = 'Statistics since last charge:\nEstimated battery capacity: 9999 mAh\nMin learned battery capacity: 4000 mAh\n\n' + ('padding\n' * 8000)
        with zipfile.ZipFile(data, 'w', zipfile.ZIP_STORED) as archive:
            archive.writestr('bugreport-a.txt', first)
            archive.writestr('bugreport-b.txt', 'Statistics since last charge:\nEstimated battery capacity: 5000 mAh\nMin learned battery capacity: 4500 mAh\n\n')
        corrupt = bytearray(data.getvalue())
        name_length, extra_length = struct.unpack_from('<HH', corrupt, 26)
        corrupt[30 + name_length + extra_length + len(first.encode('utf8')) - 1] ^= 1
        info = BatteryExtractor().extract(io.BytesIO(corrupt))
        self.assertEqual(info.design_capacity, 5000)
        self.assertEqual(info.health_percentage, 90)


if __name__ == '__main__':
    unittest.main()
