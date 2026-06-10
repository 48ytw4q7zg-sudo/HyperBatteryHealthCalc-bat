#!/usr/bin/env python3
"""电池容量计算器 - 命令行版本 (Q-CR Omega 优化版)
从小米/Redmi 诊断 ZIP 文件中提取电池健康数据并计算容量百分比
"""

from __future__ import annotations

import argparse
import io
import re
import sys
import zipfile
from pathlib import Path
from typing import Optional

from battery_core import BatteryExtractor, BatteryInfo, get_rating_text, get_rating_color

# Windows GBK 控制台打印 emoji 会触发 UnicodeEncodeError
if sys.platform == 'win32' and sys.stdout.isatty():
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding=sys.stdout.encoding,
        errors='replace', line_buffering=sys.stdout.line_buffering
    )


class Colors:
    """安全的终端颜色输出 — 不支持颜色时静默回退为空字符串"""

    def __init__(self) -> None:
        self.enabled = self._detect_support()
        self._init_styles()

    def _detect_support(self) -> bool:
        if not sys.stdout.isatty():
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
            source_tag = " (自动检测)" if info.design_capacity_auto else " (手动输入)"
            lines.append(f"  原始设计容量: {c.bold}{info.design_capacity:.0f} mAh{c.reset}{source_tag}")
        else:
            lines.append(f"  原始设计容量: {c.bold}未检测到{c.reset}")

        current = info.current_capacity
        if current is not None:
            lines.append(f"  当前实际容量: {c.bold}{current} mAh{c.reset}")
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
        if info.cycle_count is not None:
            lines.append(f"  充电循环次数: {c.bold}{info.cycle_count} 次{c.reset}")
            lines.append(f"  {c.gray}💡 满充容量会随着循环次数的增加而逐渐减少{c.reset}")
        else:
            lines.append(f"  充电循环次数: 未检测到 (不同机型数据有差异)")

        if info.statistics:
            lines.append(f"\n{c.cyan}📄 原始电池统计数据{c.reset}")
            lines.append(f"{'-' * w}")
            lines.append(info.statistics)
            lines.append(f"{'-' * w}")

        lines.append(f"\n{'=' * w}\n")
        report_text = '\n'.join(lines)
        print(report_text)
        return self._strip_ansi(report_text)

    @staticmethod
    def _strip_ansi(text: str) -> str:
        return re.sub(r'\x1b\[[0-9;]*m', '', text)


def is_interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


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
            if value <= 0:
                print("  容量必须大于 0，请重新输入。")
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
        help='输入目录路径（默认: 脚本所在目录下的 input/）'
    )
    parser.add_argument(
        '-c', '--capacity', type=float, default=None,
        help='默认设计容量(mAh)，当 ZIP 中未检测到设计容量时使用'
    )
    parser.add_argument(
        '-o', '--output', type=Path, default=None,
        help='报告输出文件路径'
    )
    parser.add_argument(
        '--no-color', action='store_true',
        help='禁用彩色输出'
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    script_dir = Path(__file__).parent.resolve()
    input_dir = args.input or (script_dir / 'input')

    if not input_dir.exists():
        print(f"错误: 输入目录不存在: {input_dir}")
        print("请将诊断 ZIP 文件放入 input/ 目录，或使用 --input 指定")
        return 1
    if not input_dir.is_dir():
        print(f"错误: 输入路径不是目录: {input_dir}")
        return 1

    zip_files = sorted(
        p for p in input_dir.iterdir()
        if p.is_file() and p.suffix.lower() == '.zip'
    )
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
        print(f"\n[{i}/{len(zip_files)}] 正在分析: {zip_path.name} ...", end='', flush=True)

        try:
            info = extractor.extract(zip_path)
            print(" 完成")

            if not info.has_design_capacity:
                design = args.capacity
                if design is None:
                    design = prompt_design_capacity()
                if design is not None:
                    info.design_capacity = design
                    info.design_capacity_auto = False
                else:
                    print(f"  [跳过] 缺少设计容量，无法计算健康度")
                    skipped += 1
                    continue

            if info.current_capacity is None:
                print(f"  [错误] 无法从文件中提取电池容量（缺少 Min learned battery capacity）")
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
            output_path = args.output.resolve()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text('\n---\n'.join(all_reports), encoding='utf-8')
            print(f"\n报告已保存至: {output_path}")
        except OSError as e:
            print(f"\n[警告] 无法保存报告文件: {e}")

    if sys.platform == 'win32' and is_interactive():
        input("\n按回车键退出...")

    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
