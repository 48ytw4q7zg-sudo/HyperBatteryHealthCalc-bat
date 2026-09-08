"""Synthetic regression tests for native GUI report saving."""

import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'HyperBatteryHealthCalc-bat'))
import battery_gui
from battery_core import BatteryInfo
import report_io


class ReportExportTests(unittest.TestCase):
    def setUp(self):
        build = ROOT / '.build'
        build.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix='gui-export-test-', dir=build)
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.source = self.directory / 'synthetic.zip'
        self.source.write_bytes(b'synthetic diagnostic fixture')
        self.target = self.directory / 'report.txt'
        self.text = 'Battery report\n\u7535\u6c60\u5065\u5eb7\u5ea6: 90.00%'

    def make_app(self):
        app = battery_gui.BatteryHealthApp.__new__(battery_gui.BatteryHealthApp)
        app.root = Mock()
        app.file_var = Mock()
        app.file_var.get.return_value = str(self.source)
        app.capacity_entry = Mock()
        app.capacity_entry.get.return_value = ''
        app.save_btn = Mock()
        app.analyze_btn = Mock()
        app._analysis_pending = False
        app._set_status = Mock()
        app._show_result = Mock()
        app._clear_result = Mock(side_effect=app._invalidate_export)
        app.extractor = Mock()
        app.current_info = None
        app._invalidate_export()
        return app

    def prepared_app(self):
        app = self.make_app()
        app._set_export_report(self.text, self.source, (str(self.source), ''))
        return app

    def run_analysis(self, app, before_collect=None):
        with patch.object(battery_gui, 'Thread') as thread:
            thread.return_value.start.side_effect = lambda: thread.call_args.kwargs['target']()
            app._analyze()
            if before_collect:
                before_collect()
            app.root.after.call_args.args[1]()

    def test_saves_unicode_with_bom_and_windows_newlines(self):
        saved = report_io.save_text_report(self.target, self.text, self.source)
        self.assertEqual(saved, self.target.resolve())
        data = self.target.read_bytes()
        self.assertTrue(data.startswith(b'\xef\xbb\xbf'))
        self.assertIn(b'\r\n', data)
        self.assertNotIn(b'\r\r\n', data)
        self.assertEqual(self.target.read_text(encoding='utf-8-sig'), self.text + '\n')
        self.assertEqual(self.source.read_bytes(), b'synthetic diagnostic fixture')

    def test_existing_report_is_replaced_after_success(self):
        self.target.write_text('previous report', encoding='utf-8')
        report_io.save_text_report(self.target, self.text, self.source)
        self.assertEqual(self.target.read_text(encoding='utf-8-sig'), self.text + '\n')
        self.assertEqual(list(self.directory.glob('.battery-report-*.tmp')), [])

    def test_failed_replace_preserves_existing_report_and_cleans_temporary(self):
        self.target.write_bytes(b'previous report')
        with patch.object(report_io.os, 'replace', side_effect=PermissionError('synthetic write failure')):
            with self.assertRaises(PermissionError):
                report_io.save_text_report(self.target, self.text, self.source)
        self.assertEqual(self.target.read_bytes(), b'previous report')
        self.assertEqual(list(self.directory.glob('.battery-report-*.tmp')), [])

    def test_failed_flush_preserves_existing_report(self):
        self.target.write_bytes(b'previous report')
        with patch.object(report_io.os, 'fsync', side_effect=OSError('synthetic disk failure')):
            with self.assertRaises(OSError):
                report_io.save_text_report(self.target, self.text, self.source)
        self.assertEqual(self.target.read_bytes(), b'previous report')
        self.assertEqual(list(self.directory.glob('.battery-report-*.tmp')), [])

    def test_input_archive_cannot_be_overwritten(self):
        with self.assertRaises(ValueError):
            report_io.save_text_report(self.source, self.text, self.source)
        self.assertEqual(self.source.read_bytes(), b'synthetic diagnostic fixture')

    def test_hardlink_to_input_archive_cannot_be_overwritten(self):
        os.link(self.source, self.target)
        with self.assertRaises(ValueError):
            report_io.save_text_report(self.target, self.text, self.source)
        self.assertEqual(self.source.read_bytes(), b'synthetic diagnostic fixture')

    def test_non_text_destination_is_rejected(self):
        with self.assertRaises(ValueError):
            report_io.save_text_report(self.directory / 'report.zip', self.text, self.source)

    def test_empty_report_is_rejected(self):
        with self.assertRaises(ValueError):
            report_io.save_text_report(self.target, ' \n', self.source)
        self.assertFalse(self.target.exists())

    def test_missing_parent_is_not_created(self):
        with self.assertRaises(FileNotFoundError):
            report_io.save_text_report(self.directory / 'missing' / 'report.txt', self.text, self.source)
        self.assertFalse((self.directory / 'missing').exists())

    def test_cancel_preserves_current_report_without_writing(self):
        app = self.prepared_app()
        with patch.object(battery_gui.filedialog, 'asksaveasfilename', return_value=''), \
                patch.object(battery_gui, 'save_text_report') as writer:
            app._save_report()
        writer.assert_not_called()
        self.assertTrue(app._export_is_current())

    def test_save_action_uses_the_completed_report_snapshot(self):
        app = self.prepared_app()
        with patch.object(battery_gui.filedialog, 'asksaveasfilename', return_value=str(self.target)):
            app._save_report()
        self.assertEqual(self.target.read_text(encoding='utf-8-sig'), self.text + '\n')

    def test_failed_save_reports_error_and_remains_retryable(self):
        app = self.prepared_app()
        with patch.object(battery_gui.filedialog, 'asksaveasfilename', return_value=str(self.target)), \
                patch.object(battery_gui, 'save_text_report', side_effect=PermissionError('synthetic failure')), \
                patch.object(battery_gui.messagebox, 'showerror') as error:
            app._save_report()
        error.assert_called_once()
        self.assertTrue(app._export_is_current())

    def test_no_report_never_opens_save_dialog(self):
        app = self.make_app()
        with patch.object(battery_gui.filedialog, 'asksaveasfilename') as dialog, \
                patch.object(battery_gui.messagebox, 'showinfo'):
            app._save_report()
        dialog.assert_not_called()

    def test_pending_analysis_cannot_save_previous_report(self):
        app = self.prepared_app()
        app._analysis_pending = True
        self.assertFalse(app._export_is_current())

    def test_changed_capacity_invalidates_report(self):
        app = self.prepared_app()
        app.capacity_entry.get.return_value = '5200'
        self.assertFalse(app._export_is_current())
        app._invalidate_export('variable', '', 'write')
        self.assertEqual(app._report_text, '')
        app.save_btn.configure.assert_called_with(state='disabled')

    def test_change_while_save_dialog_is_open_prevents_write(self):
        app = self.prepared_app()
        def choose_after_change(**_options):
            app.file_var.get.return_value = 'different.zip'
            return str(self.target)
        with patch.object(battery_gui.filedialog, 'asksaveasfilename', side_effect=choose_after_change), \
                patch.object(battery_gui, 'save_text_report') as writer, \
                patch.object(battery_gui.messagebox, 'showinfo'):
            app._save_report()
        writer.assert_not_called()
        self.assertEqual(app._report_text, '')

    def test_successful_analysis_enables_report_export(self):
        app = self.make_app()
        info = BatteryInfo()
        info.design_capacity = 5000
        info.min_learned_capacity = 4500
        app.extractor.extract.return_value = info
        self.run_analysis(app)
        self.assertTrue(app._export_is_current())
        self.assertIn('90.00%', app._report_text)
        app.save_btn.configure.assert_called_with(state='normal')

    def test_partial_analysis_can_export_its_notes(self):
        app = self.make_app()
        app.extractor.extract.return_value = BatteryInfo()
        self.run_analysis(app)
        self.assertTrue(app._export_is_current())
        self.assertTrue(app._show_result.call_args.kwargs['error'])

    def test_failed_analysis_does_not_enable_export(self):
        app = self.prepared_app()
        app.extractor.extract.side_effect = ValueError('synthetic parse failure')
        self.run_analysis(app)
        self.assertFalse(app._export_is_current())
        self.assertEqual(app._report_text, '')

    def test_stale_background_result_does_not_enable_export(self):
        app = self.make_app()
        app.extractor.extract.return_value = BatteryInfo()
        self.run_analysis(app, lambda: setattr(app.file_var.get, 'return_value', 'different.zip'))
        self.assertFalse(app._export_is_current())


if __name__ == '__main__':
    unittest.main(verbosity=2)
