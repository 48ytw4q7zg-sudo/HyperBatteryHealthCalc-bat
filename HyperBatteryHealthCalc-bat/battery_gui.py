#!/usr/bin/env python3
"""电池容量计算器 - 可视化桌面版 (Q-CR Omega 优化版)
使用 tkinter 构建 GUI，完全绕过 Windows CMD 终端编码问题。
"""

from __future__ import annotations

import sys
import zipfile
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from typing import Optional

from battery_core import BatteryExtractor, BatteryInfo, get_rating_text, get_rating_color

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

        self._build_ui()
        self._refresh_file_list()

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
                 '所有分析在本地完成，数据不会上传。',
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

        self.capacity_frame = ttk.Frame(file_frame)
        self.capacity_frame.pack(fill='x')

        ttk.Label(self.capacity_frame, text='设计容量 (mAh):',
                  font=('Microsoft YaHei', 9)).pack(side='left', padx=(0, 8))
        self.capacity_entry = ttk.Entry(self.capacity_frame, width=18,
                                        font=('Consolas', 10))
        self.capacity_entry.pack(side='left')

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
        self.result_text.pack(fill='both', expand=True)

        scrollbar = ttk.Scrollbar(result_frame, orient='vertical',
                                  command=self.result_text.yview)
        scrollbar.pack(side='right', fill='y')
        self.result_text.configure(yscrollcommand=scrollbar.set)

        tk.Label(
            main, text='Copyright  HikiMu慕鱼酱  |  v2 Q-CR Omega',
            font=('Microsoft YaHei', 8), fg='#a0aec0', bg='#f8f9fa'
        ).pack(pady=(8, 0))

    def _input_dir(self) -> Path:
        return Path(__file__).parent / 'input'

    def _refresh_file_list(self) -> None:
        input_dir = self._input_dir()
        input_dir.mkdir(parents=True, exist_ok=True)

        zip_files = sorted(
            p.name for p in input_dir.iterdir()
            if p.is_file() and p.suffix.lower() == '.zip'
        )

        self.file_combo['values'] = zip_files
        if zip_files:
            self.file_var.set(zip_files[0])
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
            self.file_combo.set('')
            self._set_status(f'已选择: {Path(path).name}')

    def _set_status(self, text: str) -> None:
        self.status_var.set(text)
        self.root.update_idletasks()

    def _analyze(self) -> None:
        file_name = self.file_var.get().strip()
        if not file_name:
            messagebox.showwarning('提示', '请先选择一个诊断文件')
            return

        zip_path = Path(file_name)
        if not zip_path.is_absolute():
            zip_path = self._input_dir() / file_name

        if not zip_path.exists():
            messagebox.showerror('错误', f'文件不存在:\n{zip_path}')
            return

        self.analyze_btn.configure(state='disabled', text='分析中...')
        self._set_status('正在解析诊断文件，请稍候...')
        self._clear_result()
        self.root.update()

        try:
            info = self.extractor.extract(zip_path)
            self._set_status('分析完成')

            if not info.has_design_capacity:
                manual = self.capacity_entry.get().strip()
                if manual:
                    try:
                        val = float(manual)
                        if val > 0:
                            info.design_capacity = val
                            info.design_capacity_auto = False
                    except ValueError:
                        pass

            if not info.has_design_capacity:
                self._show_result(self._build_error_report(info), error=True)
                self._set_status('未检测到设计容量，请在下方手动输入后重试')
                return

            if info.current_capacity is None:
                self._show_result(self._build_error_report(info), error=True)
                self._set_status('无法提取电池容量数据（缺少 Min learned 字段）')
                return

            self.current_info = info
            self._show_result(self._build_report(info))

        except zipfile.BadZipFile:
            self._show_result('错误: ZIP 文件损坏或格式不正确', error=True)
            self._set_status('文件格式错误')
        except ValueError as e:
            self._show_result(f'错误: {e}', error=True)
            self._set_status('解析失败')
        except PermissionError:
            self._show_result('错误: 文件访问被拒绝，请关闭其他正在使用此文件的程序', error=True)
            self._set_status('文件访问被拒绝')
        except OSError as e:
            self._show_result(f'文件系统错误: {e}', error=True)
            self._set_status('文件读取失败')
        except Exception as e:
            self._show_result(f'未知错误: {type(e).__name__}: {e}', error=True)
            self._set_status('分析失败')
        finally:
            self.analyze_btn.configure(state='normal', text=' 开始分析 ')

    def _build_report(self, info: BatteryInfo) -> str:
        lines = []
        sep = '=' * 54
        lines.append(sep)
        lines.append('  电池容量详细报告')
        lines.append(sep)

        if info.device_name:
            lines.append(f'  设备型号: {info.device_name}')
        if info.report_time:
            lines.append(f'  诊断时间: {info.report_time}')

        source = '(自动检测)' if info.design_capacity_auto else '(手动输入)'
        lines.append(f'  原始设计容量: {info.design_capacity:.0f} mAh  {source}')

        current = info.current_capacity
        pct = info.health_percentage
        lines.append(f'  当前实际容量: {current} mAh')

        if pct is not None:
            rating = get_rating_text(pct)
            lines.append(f'  电池健康度: {pct:.2f}%  ({rating})')
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
        if info.cycle_count is not None:
            lines.append(f'  充电循环次数: {info.cycle_count} 次')
            lines.append(f'  提示: 满充容量会随着循环次数的增加而逐渐减少')
        else:
            lines.append(f'  充电循环次数: 未检测到 (不同机型数据有差异)')

        if info.statistics:
            lines.append('')
            lines.append('  --- 原始电池统计数据 ---')
            lines.append('-' * 54)
            lines.append(info.statistics)
            lines.append('-' * 54)

        lines.append('')
        lines.append(sep)
        return '\n'.join(lines)

    def _build_error_report(self, info: BatteryInfo) -> str:
        lines = ['=' * 54,
                 '  部分信息已提取（以下为已获取的数据）',
                 '=' * 54]

        if info.device_name:
            lines.append(f'  设备型号: {info.device_name}')
        if info.report_time:
            lines.append(f'  诊断时间: {info.report_time}')
        if info.has_design_capacity:
            lines.append(f'  设计容量: {info.design_capacity:.0f} mAh')
        if info.cycle_count is not None:
            lines.append(f'  循环次数: {info.cycle_count} 次')
        if info.statistics:
            lines.append('')
            lines.append('  --- 原始统计数据 ---')
            lines.append(info.statistics)

        if not info.has_design_capacity:
            lines.append('')
            lines.append('  [注意] 未检测到设计容量，请在下方手动输入后重试。')

        if info.current_capacity is None:
            lines.append('')
            lines.append('  [注意] 未检测到 Min learned battery capacity。')
            lines.append('        建议将电量充满后重新抓取诊断文件。')

        lines.append('=' * 54)
        return '\n'.join(lines)

    def _show_result(self, text: str, error: bool = False) -> None:
        self.result_text.configure(state='normal')
        self.result_text.delete('1.0', 'end')
        self.result_text.insert('1.0', text)
        if not error:
            self._highlight_result()
        self.result_text.configure(state='disabled')

    def _highlight_result(self) -> None:
        info = self.current_info
        if info is None:
            return

        pct = info.health_percentage
        if pct is None:
            return

        color = get_rating_color(pct)
        rating = get_rating_text(pct)

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
        self.current_info = None
        self.result_text.configure(state='normal')
        self.result_text.delete('1.0', 'end')
        self.result_text.configure(state='disabled')

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    app = BatteryHealthApp()
    app.run()


if __name__ == '__main__':
    main()
