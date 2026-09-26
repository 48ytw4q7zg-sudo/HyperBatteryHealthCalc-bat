#!/usr/bin/env python3
"""电池容量计算器 - 可视化桌面版 (Q-CR Omega 优化版)
使用 tkinter 构建 GUI，完全绕过 Windows CMD 终端编码问题。
"""

from __future__ import annotations

import json
import sys
import math
import zipfile
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from typing import Optional
from queue import Empty, Queue
from threading import Event, Thread

from battery_core import (
    BatteryExtractor,
    BatteryInfo,
    ExtractionCancelled,
    apply_manual_design_capacity,
    build_report_payload,
    file_fingerprint,
    format_batch_summary,
    format_batch_summary_csv,
    format_fingerprint,
    get_rating_color,
    redacted_copy,
    redacted_fingerprint,
)
from report_io import application_dir, resolve_app_path, save_csv_report, save_json_report, save_text_report

PRIVACY_NOTE = '报告含应用包名、蓝牙设备名等使用痕迹；公开分享前建议勾选“导出时脱敏”。'


def _safe_fingerprint(path) -> Optional[dict]:
    try:
        return file_fingerprint(path)
    except (OSError, TypeError, ValueError):
        return None


def _progress_text(event: dict) -> str:
    entry = str(event.get('entry') or '').replace('\\', '/').rsplit('/', 1)[-1]
    size_mb = float(event.get('bytes_read') or 0) / (1024 * 1024)
    elapsed = float(event.get('elapsed') or 0)
    target = f' {entry}' if entry else ''
    return f'正在解析{target}（已读 {size_mb:.1f} MB，{elapsed:.0f} 秒），可点击“取消”中止'

if sys.platform == 'win32':
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


class BatteryHealthApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title('小米电池容量计算器')
        self.root.geometry('720x620')
        self.root.resizable(True, True)
        self.root.minsize(560, 500)
        self.root.configure(bg='#f8f9fa')

        self.extractor = BatteryExtractor()
        self.current_info: Optional[BatteryInfo] = None
        self._report_text = ''
        self._report_source: Optional[Path] = None
        self._report_inputs: Optional[tuple[str, str]] = None
        self._cancel_event: Optional[Event] = None
        self._worker: Optional[Thread] = None
        self.file_path_index: dict[str, Path] = {}
        self.recursive_scan = tk.BooleanVar(value=False)
        self.redact_export = tk.BooleanVar(value=False)
        # 结果区默认折叠原始统计段（先结论后原文）；保存的报告始终是全文。
        self.show_raw = tk.BooleanVar(value=False)
        self._display_texts: Optional[tuple[str, str, bool]] = None

        self._build_ui()
        self._refresh_file_list()
        self.root.protocol('WM_DELETE_WINDOW', self._on_close)

    def _build_ui(self) -> None:
        main = ttk.Frame(self.root, padding='15')
        main.pack(fill='both', expand=True)

        title_frame = ttk.Frame(main)
        title_frame.pack(fill='x', pady=(0, 12))
        ttk.Label(
            title_frame, text='小米电池容量计算器',
            font=('Microsoft YaHei', 18, 'bold'),
            foreground='#2b6cb0'
        ).pack()

        note_frame = tk.Frame(main, bg='#ebf8ff',
                              padx=12, pady=10)
        note_frame.pack(fill='x', pady=(0, 12))
        tk.Label(
            note_frame, bg='#ebf8ff', fg='#2d3748',
            font=('Microsoft YaHei', 9),
            text='从诊断 ZIP 文件中提取电池数据并计算健康度。\n'
                 '所有分析在本地完成，数据不会上传；报告含应用包名/蓝牙设备名，分享前可勾选脱敏导出。',
            justify='left'
        ).pack(anchor='w')

        file_frame = ttk.LabelFrame(main, text='诊断文件', padding='10')
        file_frame.pack(fill='x', pady=(0, 10))

        top_row = ttk.Frame(file_frame)
        top_row.pack(fill='x', pady=(0, 6))

        self.file_var = tk.StringVar()
        self.file_combo = ttk.Combobox(top_row, textvariable=self.file_var,
                                       font=('Consolas', 10))
        self.file_combo.pack(side='left', fill='x', expand=True, padx=(0, 8))

        ttk.Button(top_row, text='浏览...', command=self._browse_file).pack(side='right')

        scan_row = ttk.Frame(file_frame)
        scan_row.pack(fill='x', pady=(0, 6))
        ttk.Checkbutton(
            scan_row,
            text='递归扫描 input 子目录',
            variable=self.recursive_scan,
            command=self._refresh_file_list
        ).pack(side='left')
        ttk.Checkbutton(
            scan_row,
            text='导出时脱敏（隐藏蓝牙/包名/文件名/原始统计等）',
            variable=self.redact_export,
        ).pack(side='left', padx=(12, 0))

        self.capacity_frame = ttk.Frame(file_frame)
        self.capacity_frame.pack(fill='x')

        ttk.Label(self.capacity_frame, text='设计容量 (mAh):',
                  font=('Microsoft YaHei', 9)).pack(side='left', padx=(0, 8))
        self.capacity_var = tk.StringVar()
        self.capacity_entry = ttk.Entry(self.capacity_frame, width=18,
                                        textvariable=self.capacity_var,
                                        font=('Consolas', 10))
        self.capacity_entry.pack(side='left')
        ttk.Checkbutton(
            self.capacity_frame,
            text='显示原始统计数据',
            variable=self.show_raw,
            command=self._toggle_raw_statistics,
        ).pack(side='left', padx=(12, 0))

        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill='x', pady=(0, 10))

        self.analyze_btn = tk.Button(
            btn_frame, text=' 开始分析 ', font=('Microsoft YaHei', 11, 'bold'),
            bg='#48bb78', fg='white', activebackground='#38a169',
            activeforeground='white', relief='flat', padx=20, pady=8,
            cursor='hand2', command=self._analyze)
        self.analyze_btn.pack(side='left', padx=(0, 10))

        self.refresh_btn = tk.Button(
            btn_frame, text='刷新文件列表', font=('Microsoft YaHei', 9),
            bg='#4299e1', fg='white', activebackground='#3182ce',
            activeforeground='white', relief='flat', padx=14, pady=6,
            cursor='hand2', command=self._refresh_file_list)
        self.refresh_btn.pack(side='left')

        self.save_btn = tk.Button(
            btn_frame, text='保存报告', font=('Microsoft YaHei', 9),
            bg='#2b6cb0', fg='white', activebackground='#2c5282',
            activeforeground='white', relief='flat', padx=14, pady=6,
            cursor='hand2', state='disabled', command=self._save_report)
        self.save_btn.pack(side='left', padx=(10, 0))

        self.batch_btn = tk.Button(
            btn_frame, text='批量汇总', font=('Microsoft YaHei', 9),
            bg='#4a5568', fg='white', activebackground='#2d3748',
            activeforeground='white', relief='flat', padx=14, pady=6,
            cursor='hand2', command=self._batch_summary)
        self.batch_btn.pack(side='left', padx=(10, 0))

        self.cancel_btn = tk.Button(
            btn_frame, text='取消', font=('Microsoft YaHei', 9),
            bg='#e53e3e', fg='white', activebackground='#c53030',
            activeforeground='white', relief='flat', padx=14, pady=6,
            cursor='hand2', state='disabled', command=self._cancel_analysis)
        self.cancel_btn.pack(side='left', padx=(10, 0))

        self.status_var = tk.StringVar(value='请选择诊断文件或点击"浏览..."')
        tk.Label(
            main, textvariable=self.status_var,
            font=('Microsoft YaHei', 9), fg='#718096',
            bg='#f8f9fa', anchor='w'
        ).pack(fill='x', pady=(0, 8))

        result_frame = ttk.LabelFrame(main, text='分析结果', padding='8')
        result_frame.pack(fill='both', expand=True)

        self.result_text = tk.Text(
            result_frame, font=('Consolas', 10), wrap='word',
            bg='#ffffff', fg='#2d3748', relief='flat',
            padx=10, pady=10, state='disabled'
        )
        scrollbar = ttk.Scrollbar(result_frame, orient='vertical',
                                  command=self.result_text.yview)
        scrollbar.pack(side='right', fill='y')
        self.result_text.pack(fill='both', expand=True)
        self.result_text.configure(yscrollcommand=scrollbar.set)

        tk.Label(
            main, text='Copyright  HikiMu慕鱼酱  |  v2 Q-CR Omega',
            font=('Microsoft YaHei', 8), fg='#a0aec0', bg='#f8f9fa'
        ).pack(pady=(8, 0))

        self.file_var.trace_add('write', self._invalidate_export)
        self.capacity_var.trace_add('write', self._invalidate_export)

    def _input_dir(self) -> Path:
        return application_dir() / 'input'

    def _collect_zip_files(self) -> list[Path]:
        input_dir = self._input_dir()
        iterator = input_dir.rglob('*.zip') if self.recursive_scan.get() else input_dir.glob('*.zip')
        return sorted(
            (path for path in iterator if path.is_file()),
            key=lambda item: str(item).lower(),
        )

    def _resolve_selected_zip(self, selected: str) -> Optional[Path]:
        selected = selected.strip()
        if not selected:
            return None

        path = Path(selected)
        if path.is_absolute():
            return path if path.is_file() and path.suffix.lower() == '.zip' else None

        # List labels are input-relative; a stale choice must not use another ZIP.
        if selected in self.file_path_index:
            mapped = self.file_path_index[selected]
            return mapped if mapped.is_file() and mapped.suffix.lower() == '.zip' else None

        direct = resolve_app_path(path)
        if direct.is_file() and direct.suffix.lower() == '.zip':
            return direct

        candidate = self._input_dir() / selected
        if candidate.is_file() and candidate.suffix.lower() == '.zip':
            return candidate

        for item in self._collect_zip_files():
            if item.name == selected:
                return item
        return None

    def _apply_manual_capacity(self, info: BatteryInfo) -> None:
        raw_value = self.capacity_entry.get().strip()
        if not raw_value:
            return

        try:
            value = float(raw_value)
        except ValueError as exc:
            raise ValueError('设计容量必须是数字') from exc

        if not math.isfinite(value) or value <= 0:
            raise ValueError('设计容量必须是大于 0 的有限数值')

        apply_manual_design_capacity(info, value)

    def _refresh_file_list(self) -> None:
        input_dir = self._input_dir()
        try:
            input_dir.mkdir(parents=True, exist_ok=True)
            zip_files = self._collect_zip_files()
        except OSError as exc:
            self.file_path_index = {}
            self.file_combo['values'] = []
            self._set_status(f'读取 input 目录失败：{exc}；可点击“浏览...”选择其他文件')
            return
        display_items: list[str] = []
        self.file_path_index = {}
        for item in zip_files:
            try:
                display_name = str(item.relative_to(input_dir))
            except ValueError:
                display_name = str(item)
            self.file_path_index[display_name] = item
            display_items.append(display_name)

        self.file_combo['values'] = display_items
        if display_items:
            self.file_var.set(display_items[0])
            self._set_status(f'已发现 {len(zip_files)} 个诊断文件，选择后点击"开始分析"')
        else:
            self.file_var.set('')
            self._set_status('input 目录下暂无 ZIP 文件，请点击"浏览..."选择')

    def _browse_file(self) -> None:
        path = filedialog.askopenfilename(
            title='选择诊断文件',
            filetypes=[('ZIP 文件', '*.zip'), ('所有文件', '*.*')]
        )
        if path:
            self.file_var.set(path)
            self._set_status(f'已选择: {Path(path).name}')

    def _set_status(self, text: str) -> None:
        self.status_var.set(text)
        self.root.update_idletasks()

    def _analyze(self) -> None:
        if getattr(self, '_analysis_pending', False):
            return
        self._invalidate_export()
        file_name = self.file_var.get().strip()
        if not file_name:
            messagebox.showwarning('提示', '请先选择一个诊断文件')
            return

        zip_path = self._resolve_selected_zip(file_name)
        if zip_path is None:
            messagebox.showerror('错误', f'未找到文件:\n{file_name}')
            return

        if not zip_path.is_file():
            messagebox.showerror('错误', f'文件不存在:\n{zip_path}')
            return
        try:
            manual = BatteryInfo()
            self._apply_manual_capacity(manual)
        except ValueError as exc:
            self._show_result(f'错误: {exc}', error=True)
            self._set_status(str(exc))
            return

        self._analysis_pending = True
        self.analyze_btn.configure(state='disabled', text='分析中...')
        self._set_status('正在解析诊断文件，请稍候...')
        self._clear_result()
        capacity_text = self.capacity_entry.get()
        result_queue = Queue()
        progress_queue = Queue()
        cancel_event = Event()
        self._cancel_event = cancel_event
        # 通过属性传递进度/取消，extract() 调用签名保持不变。
        self.extractor.progress_callback = progress_queue.put
        self.extractor.cancel_event = cancel_event
        self._set_busy_controls(True)

        def extract_in_background():
            try:
                info = self.extractor.extract(zip_path)
                result_queue.put((info, None, _safe_fingerprint(zip_path)))
            except Exception as exc:
                result_queue.put((None, exc, None))

        def collect_result():
            latest_progress = None
            while True:
                try:
                    latest_progress = progress_queue.get_nowait()
                except Empty:
                    break
            if latest_progress is not None and not cancel_event.is_set():
                self._set_status(_progress_text(latest_progress))
            try:
                info, error, fingerprint = result_queue.get_nowait()
            except Empty:
                self.root.after(50, collect_result)
                return
            self._analysis_pending = False
            self._cancel_event = None
            self._set_busy_controls(False)
            self.analyze_btn.configure(state='normal', text=' 开始分析 ')
            if self.file_var.get().strip() != file_name or self.capacity_entry.get() != capacity_text:
                self._set_status('文件或容量已改变，请点击“开始分析”更新结果')
                return
            if isinstance(error, ExtractionCancelled):
                self._show_result('已取消本次解析，可重新点击“开始分析”。', error=True)
                self._set_status('已取消解析')
                return
            if error is not None:
                message = 'ZIP 文件损坏或格式不正确' if isinstance(error, zipfile.BadZipFile) else str(error)
                self._show_result(f'解析失败: {message}', error=True)
                self._set_status('解析失败，可重新选择文件后重试')
                return
            if manual.has_design_capacity:
                apply_manual_design_capacity(info, manual.design_capacity)
            self.current_info = info
            complete = info.has_design_capacity and info.current_capacity is not None
            build = self._build_report if complete else self._build_error_report
            report = build(info, fingerprint)
            redacted_info = redacted_copy(info)
            hidden_fingerprint = redacted_fingerprint(fingerprint)
            self._show_report_text(build(info, fingerprint, include_raw=False), report, error=not complete)
            self._set_export_report(
                report, zip_path, (file_name, capacity_text),
                redacted_text=build(redacted_info, hidden_fingerprint),
                payload=build_report_payload(info, fingerprint),
                redacted_payload=build_report_payload(redacted_info, hidden_fingerprint),
            )
            self._set_status('分析完成' if complete else '分析完成：数据不完整，已保留本次电池快照')

        self._worker = Thread(target=extract_in_background, daemon=True)
        self._worker.start()
        self.root.after(50, collect_result)

    def _set_busy_controls(self, busy: bool) -> None:
        cancel_btn = getattr(self, 'cancel_btn', None)
        if cancel_btn is not None:
            cancel_btn.configure(state='normal' if busy else 'disabled')
        batch_btn = getattr(self, 'batch_btn', None)
        if batch_btn is not None:
            batch_btn.configure(state='disabled' if busy else 'normal')

    def _cancel_analysis(self) -> None:
        event = getattr(self, '_cancel_event', None)
        if event is not None and not event.is_set():
            event.set()
            self._set_status('正在取消，请稍候...')

    def _on_close(self) -> None:
        """关窗时先取消后台解析并短暂等待，让内层包临时文件随句柄关闭而删除。"""
        event = getattr(self, '_cancel_event', None)
        if event is not None:
            event.set()
        worker = getattr(self, '_worker', None)
        if worker is not None and worker.is_alive():
            worker.join(timeout=5)
        self.root.destroy()

    def _batch_summary(self) -> None:
        """一次分析 input 目录全部 ZIP，输出横向对比表（可保存为 TXT/CSV）。"""
        if getattr(self, '_analysis_pending', False):
            return
        try:
            zip_files = self._collect_zip_files()
        except OSError as exc:
            messagebox.showerror('错误', f'读取 input 目录失败：{exc}')
            return
        if not zip_files:
            messagebox.showinfo('提示', 'input 目录下暂无 ZIP 文件，无法批量汇总')
            return
        try:
            manual = BatteryInfo()
            self._apply_manual_capacity(manual)
        except ValueError as exc:
            self._set_status(str(exc))
            return
        self._invalidate_export()
        self._analysis_pending = True
        self.analyze_btn.configure(state='disabled', text='汇总中...')
        self._clear_result()
        file_name, capacity_text = self.file_var.get().strip(), self.capacity_entry.get()
        input_dir = self._input_dir()
        result_queue = Queue()
        progress_queue = Queue()
        cancel_event = Event()
        self._cancel_event = cancel_event
        self._set_busy_controls(True)

        def run_batch():
            extractor = BatteryExtractor()
            extractor.progress_callback = progress_queue.put
            extractor.cancel_event = cancel_event
            results = []
            try:
                for path in zip_files:
                    try:
                        label = str(path.relative_to(input_dir))
                    except ValueError:
                        label = path.name
                    try:
                        info = extractor.extract(path)
                    except ExtractionCancelled:
                        raise
                    except zipfile.BadZipFile:
                        results.append((label, None, 'ZIP 文件损坏或格式不正确'))
                        continue
                    except Exception as exc:
                        results.append((label, None, type(exc).__name__))
                        continue
                    # 与单文件分析一致：填写了设计容量就覆盖自动检测值。
                    if manual.has_design_capacity:
                        apply_manual_design_capacity(info, manual.design_capacity)
                    results.append((label, info, None))
                result_queue.put((results, None))
            except Exception as exc:
                result_queue.put((None, exc))

        def collect_batch():
            latest_progress = None
            while True:
                try:
                    latest_progress = progress_queue.get_nowait()
                except Empty:
                    break
            if latest_progress is not None and not cancel_event.is_set():
                self._set_status(_progress_text(latest_progress))
            try:
                results, error = result_queue.get_nowait()
            except Empty:
                self.root.after(100, collect_batch)
                return
            self._analysis_pending = False
            self._cancel_event = None
            self._set_busy_controls(False)
            self.analyze_btn.configure(state='normal', text=' 开始分析 ')
            if error is not None:
                cancelled = isinstance(error, ExtractionCancelled)
                self._show_result('已取消批量汇总。' if cancelled else f'批量汇总失败: {error}', error=True)
                self._set_status('已取消批量汇总' if cancelled else '批量汇总失败')
                return
            if self.file_var.get().strip() != file_name or self.capacity_entry.get() != capacity_text:
                self._set_status('文件或容量已改变，请重新点击“批量汇总”')
                return
            # 脱敏版用序号代替文件名（可能带姓名或目录名）。
            redacted_results = [
                (f'文件{index}', redacted_copy(info) if info is not None else None, message)
                for index, (_label, info, message) in enumerate(results, 1)
            ]
            text = format_batch_summary(results)
            self._show_result(text, error=True)
            self._set_export_report(
                text, input_dir, (file_name, capacity_text),
                redacted_text=format_batch_summary(redacted_results),
                csv_text=format_batch_summary_csv(results),
                redacted_csv_text=format_batch_summary_csv(redacted_results),
            )
            self._set_status(f'批量汇总完成：{len(results)} 个文件，可保存为 TXT 或 CSV')

        self._worker = Thread(target=run_batch, daemon=True)
        self._worker.start()
        self.root.after(100, collect_batch)

    def _build_report(self, info: BatteryInfo, fingerprint: Optional[dict] = None, include_raw: bool = True) -> str:
        lines = []
        sep = '=' * 54
        lines.append(sep)
        lines.append('  电池容量详细报告')
        lines.append(sep)
        fingerprint_text = format_fingerprint(fingerprint)
        if fingerprint_text:
            lines.append(f'  文件指纹: {fingerprint_text}')

        lines.append('')
        lines.append('  --- 结论摘要 ---')
        for item in info.summary_lines:
            lines.append(f'  - {item}')
        lines.append('')
        lines.append('  --- 基本信息 ---')

        if info.device_name:
            lines.append(f'  设备型号: {info.device_name}')
        firmware = ' / '.join(value for value in (info.device_codename, info.build_id, info.build_incremental) if value)
        if firmware:
            lines.append(f'  设备代号/固件: {firmware}')
        if info.report_time:
            lines.append(f'  诊断时间: {info.report_time}')

        if info.has_design_capacity:
            source = info.field_sources.get('design_capacity', '自动检测')
            confidence = info.design_capacity_confidence
            source = f'({source}，置信度：{confidence[0]})' if confidence else f'({source})'
            lines.append(f'  原始设计容量: {info.design_capacity:.0f} mAh  {source}')
        else:
            lines.append('  原始设计容量: 未检测到（填入设计容量后可计算健康度）')

        current = info.current_capacity
        pct = info.health_percentage
        if current is not None:
            lines.append(f'  当前实际容量: {current} mAh（来源：{info.current_capacity_source}）')
        else:
            lines.append('  当前实际容量: 未检测到可用容量')

        if pct is not None:
            rating = info.rating_text
            lines.append(f'  电池健康度: {pct:.2f}%  ({rating})')
            level, reasons = info.health_evidence
            reason_text = f"（{'、'.join(reasons)}）" if reasons else ''
            lines.append(f'  结论证据强度: {level}{reason_text}')
        else:
            lines.append(f'  电池健康度: 无法计算')

        lines.append('')
        lines.append('  --- 电池硬件信息 ---')
        if info.estimated_capacity is not None:
            lines.append(f'  估算满充容量: {info.estimated_capacity} mAh')
        if info.last_learned_capacity is not None:
            lines.append(f'  上次学习容量: {info.last_learned_capacity} mAh')
        if info.min_learned_capacity is not None:
            lines.append(f'  最小学习容量: {info.min_learned_capacity} mAh')
        if info.max_learned_capacity is not None:
            lines.append(f'  最大学习容量: {info.max_learned_capacity} mAh')
        if info.full_capacity is not None:
            lines.append(f'  系统报告满充容量: {info.full_capacity:.0f} mAh')
        if info.charge_counter is not None:
            lines.append(f'  当前电量计数: {info.charge_counter} mAh')
        if info.battery_level is not None:
            scale = f'/{info.battery_scale}' if info.battery_scale is not None else '%'
            lines.append(f'  当前电量: {info.battery_level}{scale}')
        if info.status_text:
            lines.append(f'  充电状态: {info.status_text}')
        if info.health_text:
            lines.append(f'  系统健康状态: {info.health_text}')
        if info.capacity_level_text:
            lines.append(f'  容量等级: {info.capacity_level_text}')
        if info.voltage_mv is not None:
            lines.append(f'  当前电压: {info.voltage_mv} mV')
        if info.temperature_c is not None:
            temp_note = f'（{info.temperature_text}）' if info.temperature_text else ''
            lines.append(f'  当前温度: {info.temperature_c:.1f} ℃ {temp_note}')
        if info.technology:
            lines.append(f'  电池技术: {info.technology}')
        if info.ac_powered is not None or info.usb_powered is not None or info.wireless_powered is not None:
            lines.append(f'  供电来源: {info.power_source_text}')
        if info.max_charging_current_ma is not None:
            lines.append(f'  最大充电电流: {info.max_charging_current_ma} mA')
        if info.max_charging_voltage_mv is not None:
            lines.append(f'  最大充电电压: {info.max_charging_voltage_mv} mV')
        if info.max_charging_power_w is not None:
            lines.append(f'  估算当前充电功率上限: {info.max_charging_power_w:.2f} W')
        if info.bms_soh is not None:
            lines.append(f'  BMS 健康度 (SoH): {info.bms_soh:.0f}%（电池管理芯片厂商口径）')
        if info.bms_full_capacity is not None:
            lines.append(f'  BMS 满充容量: {info.bms_full_capacity:.0f} mAh')
        if info.bms_design_capacity is not None:
            lines.append(f'  BMS 设计容量: {info.bms_design_capacity:.0f} mAh')
        if info.cycle_count is not None:
            source = f'（来源：{info.cycle_count_source}）' if info.cycle_count_source else ''
            lines.append(f'  充电循环次数: {info.cycle_count} 次{source}')
            lines.append(f'  提示: 满充容量会随着循环次数的增加而逐渐减少')
        else:
            lines.append(f'  充电循环次数: 未检测到 (不同机型数据有差异)')

        diagnostics = info.usage_diagnostics
        if diagnostics:
            lines.append('')
            lines.append('  --- 中文诊断结论 ---')
            for item in diagnostics:
                lines.append(f'  - {item}')

        if info.statistics:
            lines.append('')
            if include_raw:
                lines.append('  --- 原始电池统计数据 ---')
                lines.append('-' * 54)
                lines.append(info.statistics)
                lines.append('-' * 54)
            else:
                lines.append('  --- 原始电池统计数据（已折叠：勾选“显示原始统计数据”查看；保存的报告包含全文）---')

        for warning in info.parse_warnings:
            lines.append(f'  [注意] {warning}')
        lines.append('')
        lines.append(sep)
        return '\n'.join(lines)

    def _build_error_report(self, info: BatteryInfo, fingerprint: Optional[dict] = None, include_raw: bool = True) -> str:
        lines = [self._build_report(info, fingerprint, include_raw), '', '  部分信息已提取（以下说明缺失的数据）']
        if not info.has_design_capacity:
            lines.append('  [注意] 未检测到设计容量，请在上方手动输入后重试。')
        if info.current_capacity is None:
            lines.append('  [注意] 未检测到有效的最小学习容量。')
            if info.charge_counter is None or info.charge_counter <= 0:
                lines.append('  [注意] 未检测到有效的 Charge counter。')
            if info.battery_percentage is None:
                lines.append('  [注意] 电量或电量刻度缺失或无效。')
            elif info.battery_percentage < 95:
                lines.append(f'  [注意] 当前电量 {info.battery_percentage:.1f}%，请充满后重新抓取诊断文件。')
        return '\n'.join(lines)

    def _show_result(self, text: str, error: bool = False) -> None:
        self._display_texts = None
        self._invalidate_export()
        self._render_result(text, error)

    def _render_result(self, text: str, error: bool) -> None:
        self.result_text.configure(state='normal')
        self.result_text.delete('1.0', 'end')
        self.result_text.insert('1.0', text)
        if not error:
            self._highlight_result()
        self.result_text.configure(state='disabled')

    def _show_report_text(self, collapsed: str, full: str, *, error: bool) -> None:
        """单份报告：按“显示原始统计数据”开关选择折叠版或全文显示。"""
        show_raw = getattr(self, 'show_raw', None)
        self._show_result(full if show_raw is not None and show_raw.get() else collapsed, error=error)
        self._display_texts = (collapsed, full, error)

    def _toggle_raw_statistics(self) -> None:
        # 只切换显示，不改变已分析的结果和导出内容。
        texts = getattr(self, '_display_texts', None)
        if not texts:
            return
        collapsed, full, error = texts
        self._render_result(full if self.show_raw.get() else collapsed, error)

    def _highlight_result(self) -> None:
        info = self.current_info
        if info is None:
            return

        pct = info.health_percentage
        if pct is None:
            return

        color = get_rating_color(pct)
        rating = info.rating_text

        content = self.result_text.get('1.0', 'end')
        search_str = f'{pct:.2f}%  ({rating})'

        start = content.find(search_str)
        if start >= 0:
            line = content[:start].count('\n') + 1
            line_start = content.rfind('\n', 0, start) + 1
            col_start = start - line_start
            self.result_text.tag_add('highlight', f'{line}.{col_start}',
                                     f'{line}.{col_start + len(search_str)}')
            self.result_text.tag_config('highlight', foreground=color,
                                        font=('Consolas', 11, 'bold'))

    def _clear_result(self) -> None:
        self._invalidate_export()
        self._display_texts = None
        self.current_info = None
        self.result_text.configure(state='normal')
        self.result_text.delete('1.0', 'end')
        self.result_text.configure(state='disabled')

    def _invalidate_export(self, *_args: object) -> None:
        self._report_text = ''
        self._report_source = None
        self._report_inputs = None
        self._report_variants: dict[str, str] = {}
        button = getattr(self, 'save_btn', None)
        if button is not None:
            button.configure(state='disabled')

    def _set_export_report(
        self,
        text: str,
        source: Path,
        inputs: tuple[str, str],
        *,
        redacted_text: str = '',
        payload: Optional[dict] = None,
        redacted_payload: Optional[dict] = None,
        csv_text: str = '',
        redacted_csv_text: str = '',
    ) -> None:
        self._report_text = text
        self._report_source = source.resolve()
        self._report_inputs = inputs
        # 同一分析快照的其它导出形态；保存时按后缀与“脱敏”开关选择。
        variants = {'.txt': text, 'redacted.txt': redacted_text}
        if payload is not None:
            variants['.json'] = json.dumps(payload, ensure_ascii=False, indent=2)
        if redacted_payload is not None:
            variants['redacted.json'] = json.dumps(redacted_payload, ensure_ascii=False, indent=2)
        if csv_text:
            variants['.csv'] = csv_text
        if redacted_csv_text:
            variants['redacted.csv'] = redacted_csv_text
        self._report_variants = variants
        self.save_btn.configure(state='normal')

    def _export_content(self, suffix: str) -> str:
        variants = getattr(self, '_report_variants', {}) or {}
        redact_var = getattr(self, 'redact_export', None)
        redact = bool(redact_var.get()) if redact_var is not None else False
        if suffix == '.txt' and not redact:
            return self._report_text
        key = f'redacted{suffix}' if redact else suffix
        content = variants.get(key, '')
        if not content:
            raise ValueError('当前分析结果不支持该导出格式' if not redact else '当前结果没有可用的脱敏版本')
        return content

    def _export_is_current(self) -> bool:
        return (
            bool(self._report_text) and self._report_source is not None
            and not getattr(self, '_analysis_pending', False)
            and self._report_inputs == (self.file_var.get().strip(), self.capacity_entry.get())
        )

    def _save_report(self) -> None:
        if not self._export_is_current():
            self._invalidate_export()
            messagebox.showinfo('提示', '请先完成当前文件的分析，再保存报告。', parent=self.root)
            return
        text, source, inputs = self._report_text, self._report_source, self._report_inputs
        variants = getattr(self, '_report_variants', {}) or {}
        filetypes = [('文本报告', '*.txt')]
        if '.json' in variants:
            filetypes.append(('JSON 数据', '*.json'))
        if '.csv' in variants:
            filetypes.append(('CSV 表格', '*.csv'))
        try:
            selected = filedialog.asksaveasfilename(
                parent=self.root, title='保存电池报告',
                initialdir=str(application_dir()), initialfile='battery_report.txt',
                defaultextension='.txt', filetypes=filetypes,
                confirmoverwrite=True,
            )
        except tk.TclError as exc:
            messagebox.showerror('保存失败', f'无法打开保存窗口：{exc}', parent=self.root)
            return
        if not selected:
            self._set_status('已取消保存，分析结果仍保留')
            return
        # A native save dialog runs a nested event loop. Recheck the exact
        # analyzed snapshot before committing a destination selected there.
        if (not self._export_is_current() or self._report_inputs != inputs
                or self._report_text != text or self._report_source != source):
            self._invalidate_export()
            messagebox.showinfo('提示', '分析结果已改变，请重新分析后保存。', parent=self.root)
            return
        suffix = Path(selected).suffix.lower()
        writer = {'.json': save_json_report, '.csv': save_csv_report}.get(suffix, save_text_report)
        try:
            content = self._export_content(suffix if suffix in ('.json', '.csv') else '.txt')
            destination = writer(Path(selected), content, source)
        except (OSError, ValueError) as exc:
            self._set_status('保存失败，分析结果仍可再次保存')
            messagebox.showerror('保存失败', f'未能保存报告：{exc}', parent=self.root)
            return
        redact_var = getattr(self, 'redact_export', None)
        privacy = '' if redact_var is not None and redact_var.get() else f'；{PRIVACY_NOTE}'
        self._set_status(f'报告已保存：{destination}{privacy}')

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    app = BatteryHealthApp()
    app.run()


if __name__ == '__main__':
    main()
