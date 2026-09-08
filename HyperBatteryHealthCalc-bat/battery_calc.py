#!/usr/bin/env python3
"""电池容量计算器 - 命令行版本 (Q-CR Omega 优化版)
从小米/Redmi 诊断 ZIP 文件中提取电池健康数据并计算容量百分比
"""

from __future__ import annotations

import argparse
import io
import re
import sys
import math
import zipfile
from pathlib import Path
from typing import Optional

from battery_core import BatteryExtractor, BatteryInfo, get_rating_text, get_rating_color
from report_io import application_dir, configure_standard_streams, resolve_app_path, write_text_atomic

# Windows GBK 控制台或管道打印 emoji 会触发 UnicodeEncodeError。
configure_standard_streams()


class Colors:
    """安全的终端颜色输出 — 不支持颜色时静默回退为空字符串"""

    def __init__(self) -> None:
        self.enabled = self._detect_support()
        self._init_styles()

    def _detect_support(self) -> bool:
        if sys.stdout is None or not sys.stdout.isatty():
            return False
        if sys.platform == 'win32':
            return self._enable_windows_ansi()
        return True

    def _enable_windows_ansi(self) -> bool:
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.GetStdHandle(-11)
            mode = ctypes.c_ulong()
            if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                return False
            if not kernel32.SetConsoleMode(handle, mode.value | 0x0004):
                return False
            return True
        except Exception:
            return False

    def _init_styles(self) -> None:
        if self.enabled:
            self.reset = '\033[0m'
            self.bold = '\033[1m'
            self.cyan = '\033[36m'
            self.gray = '\033[90m'
            self.red = '\033[31m'
            self.green = '\033[32m'
            self.yellow = '\033[33m'
            self.orange = '\033[38;5;208m'
        else:
            self.reset = self.bold = self.cyan = self.gray = ''
            self.red = self.green = self.yellow = self.orange = ''

    def rating(self, percentage: float) -> str:
        color = get_rating_color(percentage)
        if color == '#27ae60':
            return self.green
        elif color == '#f39c12':
            return self.yellow
        elif color == '#e74c3c':
            return self.red
        else:
            return self.orange


class ReportPrinter:
    """电池报告格式化输出"""

    def __init__(self, colors: Colors) -> None:
        self.c = colors

    def print_report(self, info: BatteryInfo, filename: str) -> str:
        c = self.c
        w = 60

        lines = [f"\n{'=' * w}",
                 f"{c.bold}电池容量详细报告{c.reset}",
                 f"{'=' * w}",
                 f"{c.gray}文件: {filename}{c.reset}\n",
                 f"{c.cyan}📊 基本信息{c.reset}"]

        if info.device_name:
            lines.append(f"  设备型号: {c.bold}{info.device_name}{c.reset}")
        if info.report_time:
            lines.append(f"  诊断时间: {info.report_time}")
        if info.has_design_capacity:
            source = info.design_capacity_source or ("自动检测" if info.design_capacity_auto else "手动输入")
            source_tag = f" ({source})"
            lines.append(f"  原始设计容量: {c.bold}{info.design_capacity:.0f} mAh{c.reset}{source_tag}")
        else:
            lines.append(f"  原始设计容量: {c.bold}未检测到{c.reset}（仍可显示本次快照；填入 --capacity 后可计算健康度）")

        current = info.current_capacity
        if current is not None:
            lines.append(f"  当前实际容量: {c.bold}{current} mAh{c.reset}（来源：{info.current_capacity_source}）")
            pct = info.health_percentage
            if pct is not None:
                rating = get_rating_text(pct)
                color = c.rating(pct)
                lines.append(f"  电池健康度: {color}{c.bold}{pct:.2f}%{c.reset} ({color}{rating}{c.reset})")
            else:
                lines.append(f"  电池健康度: 无法计算（缺少设计容量）")
        else:
            lines.append(f"  当前实际容量: {c.bold}未检测到{c.reset}")

        lines.append(f"\n{c.cyan}🔧 电池硬件信息{c.reset}")
        if info.estimated_capacity is not None:
            lines.append(f"  估算满充容量: {info.estimated_capacity} mAh")
        if info.last_learned_capacity is not None:
            lines.append(f"  上次学习容量: {info.last_learned_capacity} mAh")
        if info.min_learned_capacity is not None:
            lines.append(f"  最小学习容量: {info.min_learned_capacity} mAh")
        if info.max_learned_capacity is not None:
            lines.append(f"  最大学习容量: {info.max_learned_capacity} mAh")
        if info.full_capacity is not None:
            lines.append(f"  系统报告满充容量: {info.full_capacity:.0f} mAh")
        if info.charge_counter is not None:
            lines.append(f"  当前电量计数: {info.charge_counter} mAh")
        if info.battery_level is not None:
            scale = f"/{info.battery_scale}" if info.battery_scale is not None else "%"
            lines.append(f"  当前电量: {info.battery_level}{scale}")
        if info.status_text:
            lines.append(f"  充电状态: {info.status_text}")
        if info.health_text:
            lines.append(f"  系统健康状态: {info.health_text}")
        if info.capacity_level_text:
            lines.append(f"  容量等级: {info.capacity_level_text}")
        if info.voltage_mv is not None:
            lines.append(f"  当前电压: {info.voltage_mv} mV")
        if info.temperature_c is not None:
            temp_note = f"（{info.temperature_text}）" if info.temperature_text else ""
            lines.append(f"  当前温度: {info.temperature_c:.1f} ℃ {temp_note}")
        if info.technology:
            lines.append(f"  电池技术: {info.technology}")
        if info.ac_powered is not None or info.usb_powered is not None or info.wireless_powered is not None:
            lines.append(f"  供电来源: {info.power_source_text}")
        if info.max_charging_current_ma is not None:
            lines.append(f"  最大充电电流: {info.max_charging_current_ma} mA")
        if info.max_charging_voltage_mv is not None:
            lines.append(f"  最大充电电压: {info.max_charging_voltage_mv} mV")
        if info.max_charging_power_w is not None:
            lines.append(f"  估算当前充电功率上限: {info.max_charging_power_w:.2f} W")
        if info.cycle_count is not None:
            lines.append(f"  充电循环次数: {c.bold}{info.cycle_count} 次{c.reset}")
            lines.append(f"  {c.gray}💡 满充容量会随着循环次数的增加而逐渐减少{c.reset}")
        else:
            lines.append(f"  充电循环次数: 未检测到 (不同机型数据有差异)")

        diagnostics = info.usage_diagnostics
        if diagnostics:
            lines.append(f"\n{c.cyan}🧭 中文诊断结论{c.reset}")
            for item in diagnostics:
                lines.append(f"  - {item}")

        if info.statistics:
            lines.append(f"\n{c.cyan}📄 原始电池统计数据{c.reset}")
            lines.append(f"{'-' * w}")
            lines.append(info.statistics)
            lines.append(f"{'-' * w}")

        for warning in info.parse_warnings:
            lines.append(f'  [注意] {warning}')
        lines.append(f"\n{'=' * w}\n")
        report_text = '\n'.join(lines)
        print(report_text)
        return self._strip_ansi(report_text)

    @staticmethod
    def _strip_ansi(text: str) -> str:
        return re.sub(r'\x1b\[[0-9;]*m', '', text)


def is_interactive() -> bool:
    return bool(sys.stdin is not None and sys.stdout is not None
                and sys.stdin.isatty() and sys.stdout.isatty())


def collect_zip_files(input_dir: Path, recursive: bool = False) -> list[Path]:
    """收集输入目录中的诊断 ZIP 文件。

    - recursive=False: 仅扫描 input_dir 直接子文件。
    - recursive=True: 递归扫描 input_dir 下所有子目录。
    """
    pattern = '**/*.zip' if recursive else '*.zip'
    iterator = input_dir.rglob(pattern) if recursive else input_dir.glob(pattern)
    return sorted(
        (path for path in iterator if path.is_file()),
        key=lambda item: str(item).lower(),
    )


def positive_capacity(raw_value: str) -> float:
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError('设计容量必须是数字') from exc
    if not math.isfinite(value) or value <= 0:
        raise argparse.ArgumentTypeError('设计容量必须是大于 0 的有限数值')
    return value


def prompt_design_capacity() -> Optional[float]:
    if not is_interactive():
        print("\n[提示] 非交互式环境，无法提示输入设计容量。")
        print("       请使用 --capacity <数值> 参数指定设计容量。")
        return None

    print("\n[提示] 无法从诊断文件中自动检测设计容量。")
    print("       请手动输入设备的初始电池容量（单位: mAh）")
    print("       或按 Enter 跳过此文件。")

    while True:
        try:
            user_input = input("初始电池容量: ").strip()
        except EOFError:
            print("  检测到输入结束，跳过此文件。")
            return None
        if not user_input:
            return None
        try:
            value = float(user_input)
            if not math.isfinite(value) or value <= 0:
                print("  容量必须是大于 0 的有限数值，请重新输入。")
                continue
            return value
        except ValueError:
            print("  无效的数值，请重新输入或按 Enter 跳过。")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='小米电池容量计算器 - 从诊断 ZIP 中提取电池健康数据',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''示例:
  %(prog)s                          # 自动分析 input/ 目录下的所有 ZIP
  %(prog)s --capacity 5000          # 自动分析，缺失设计容量时默认使用 5000 mAh
  %(prog)s --input "C:\\diag"       # 指定输入目录
  %(prog)s -o report.txt            # 保存报告到文件
        '''.strip()
    )
    parser.add_argument(
        '-i', '--input', type=Path, default=None,
        help='输入目录路径（默认: 程序所在目录下的 input/）'
    )
    parser.add_argument(
        '-r', '--recursive', action='store_true',
        help='递归扫描输入目录中的 ZIP 文件（包含子目录）'
    )
    parser.add_argument(
        '-c', '--capacity', type=positive_capacity, default=None,
        help='默认设计容量(mAh)，当 ZIP 中未检测到设计容量时使用'
    )
    parser.add_argument(
        '-o', '--output', type=Path, default=None,
        help='报告输出文件路径（便携版默认: 程序旁 reports/battery-report.txt）'
    )
    parser.add_argument(
        '--no-color', action='store_true',
        help='禁用彩色输出'
    )
    parser.add_argument(
        '--no-pause', action='store_true',
        help='在处理结束后不等待回车退出（适合脚本/CI）'
    )
    return parser


def write_report_atomic(output_path: Path, content: str) -> None:
    output_path = resolve_app_path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(output_path, content, encoding="utf-8", newline="\n")


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    script_dir = application_dir()
    input_dir = resolve_app_path(args.input) if args.input is not None else script_dir / 'input'
    if args.output is None and getattr(sys, 'frozen', False):
        args.output = script_dir / 'reports' / 'battery-report.txt'

    if not input_dir.exists():
        print(f"错误: 输入目录不存在: {input_dir}")
        print("请将诊断 ZIP 文件放入 input/ 目录，或使用 --input 指定")
        return 1
    if not input_dir.is_dir():
        print(f"错误: 输入路径不是目录: {input_dir}")
        return 1

    zip_files = collect_zip_files(input_dir, args.recursive)
    if not zip_files:
        print(f"错误: 在 {input_dir} 中未找到 .zip 文件")
        return 1

    colors = Colors()
    if args.no_color:
        colors.enabled = False
        colors._init_styles()

    extractor = BatteryExtractor()
    printer = ReportPrinter(colors)

    print(f"发现 {len(zip_files)} 个诊断文件，开始分析...")
    success = failed = skipped = 0
    all_reports: list[str] = []

    for i, zip_path in enumerate(zip_files, 1):
        display_name = zip_path.name
        try:
            display_name = str(zip_path.relative_to(input_dir))
        except ValueError:
            pass
        print(f"\n[{i}/{len(zip_files)}] 正在分析: {display_name} ...", end='', flush=True)

        try:
            info = extractor.extract(zip_path)
            print(" 完成")
            user_skipped = False

            if not info.has_design_capacity:
                design = args.capacity
                if design is None:
                    design = prompt_design_capacity()
                    user_skipped = design is None and is_interactive()
                if design is not None:
                    info.design_capacity = design
                    info.design_capacity_auto = False
                    info.design_capacity_source = "手动输入"

            if info.current_capacity is None or not info.has_design_capacity:
                report = printer.print_report(info, zip_path.name)
                all_reports.append(report)
                if user_skipped:
                    skipped += 1
                    print("  跳过")
                    print("  [提示] 用户跳过了手动输入设计容量")
                else:
                    print("  [提示] 已保留部分报告；缺少有效的设计容量或当前容量，暂时无法计算健康度")
                    failed += 1
                continue

            report = printer.print_report(info, zip_path.name)
            all_reports.append(report)
            success += 1

        except zipfile.BadZipFile as e:
            print(f" 失败\n  [错误] ZIP 文件损坏或格式不正确: {e}")
            failed += 1
        except PermissionError as e:
            print(f" 失败\n  [错误] 文件访问被拒绝: {e}")
            failed += 1
        except OSError as e:
            print(f" 失败\n  [错误] 文件系统错误: {e}")
            failed += 1
        except ValueError as e:
            print(f" 失败\n  [错误] {e}")
            failed += 1
        except Exception as e:
            print(f" 失败\n  [错误] 未知错误: {type(e).__name__}: {e}")
            failed += 1

    print(f"\n{'=' * 42}")
    print(f"处理完成: {success} 成功, {failed} 失败, {skipped} 跳过")
    print(f"{'=' * 42}")

    if args.output and all_reports:
        try:
            output_path = resolve_app_path(args.output)
            if any(output_path == path.resolve() for path in zip_files):
                raise ValueError('输出路径不能覆盖输入诊断包')
            write_report_atomic(output_path, '\n---\n'.join(all_reports))
            print(f"\n报告已保存至: {output_path}")
        except (OSError, ValueError) as e:
            print(f"\n[警告] 无法保存报告文件: {e}")
            return 1

    if sys.platform == 'win32' and is_interactive() and not args.no_pause:
        input("\n按回车键退出...")

    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
