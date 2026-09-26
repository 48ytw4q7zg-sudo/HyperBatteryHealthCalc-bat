#!/usr/bin/env python3
"""电池容量计算器 - 命令行版本 (Q-CR Omega 优化版)
从小米/Redmi 诊断 ZIP 文件中提取电池健康数据并计算容量百分比
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import math
import zipfile
from pathlib import Path
from typing import Optional

from battery_core import (
    BatteryExtractor,
    BatteryInfo,
    apply_manual_design_capacity,
    build_report_payload,
    file_fingerprint,
    format_batch_summary,
    format_fingerprint,
    get_rating_color,
    redacted_copy,
    redacted_fingerprint,
)
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

    def print_report(
        self,
        info: BatteryInfo,
        filename: str,
        fingerprint: Optional[dict] = None,
        include_raw: bool = True,
    ) -> str:
        c = self.c
        w = 60

        lines = [f"\n{'=' * w}",
                 f"{c.bold}电池容量详细报告{c.reset}",
                 f"{'=' * w}",
                 f"{c.gray}文件: {filename}{c.reset}"]
        fingerprint_text = format_fingerprint(fingerprint)
        if fingerprint_text:
            lines.append(f"{c.gray}文件指纹: {fingerprint_text}{c.reset}")
        lines.append("")

        lines.append(f"{c.cyan}🧾 结论摘要{c.reset}")
        for item in info.summary_lines:
            lines.append(f"  - {item}")

        lines.append(f"\n{c.cyan}📊 基本信息{c.reset}")
        if info.device_name:
            lines.append(f"  设备型号: {c.bold}{info.device_name}{c.reset}")
        firmware = " / ".join(value for value in (info.device_codename, info.build_id, info.build_incremental) if value)
        if firmware:
            lines.append(f"  设备代号/固件: {firmware}")
        if info.report_time:
            lines.append(f"  诊断时间: {info.report_time}")
        if info.has_design_capacity:
            source = info.field_sources.get("design_capacity", "自动检测")
            confidence = info.design_capacity_confidence
            source_tag = f" ({source}，置信度：{confidence[0]})" if confidence else f" ({source})"
            lines.append(f"  原始设计容量: {c.bold}{info.design_capacity:.0f} mAh{c.reset}{source_tag}")
        else:
            lines.append(f"  原始设计容量: {c.bold}未检测到{c.reset}（仍可显示本次快照；填入 --capacity 后可计算健康度）")

        current = info.current_capacity
        if current is not None:
            lines.append(f"  当前实际容量: {c.bold}{current} mAh{c.reset}（来源：{info.current_capacity_source}）")
            pct = info.health_percentage
            if pct is not None:
                rating = info.rating_text
                color = c.rating(pct)
                lines.append(f"  电池健康度: {color}{c.bold}{pct:.2f}%{c.reset} ({color}{rating}{c.reset})")
                level, reasons = info.health_evidence
                reason_text = f"（{'、'.join(reasons)}）" if reasons else ""
                lines.append(f"  结论证据强度: {level}{reason_text}")
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
        if info.bms_soh is not None:
            lines.append(f"  BMS 健康度 (SoH): {info.bms_soh:.0f}%（电池管理芯片厂商口径）")
        if info.bms_full_capacity is not None:
            lines.append(f"  BMS 满充容量: {info.bms_full_capacity:.0f} mAh")
        if info.bms_design_capacity is not None:
            lines.append(f"  BMS 设计容量: {info.bms_design_capacity:.0f} mAh")
        if info.cycle_count is not None:
            source = f"（来源：{info.cycle_count_source}）" if info.cycle_count_source else ""
            lines.append(f"  充电循环次数: {c.bold}{info.cycle_count} 次{c.reset}{source}")
            lines.append(f"  {c.gray}💡 满充容量会随着循环次数的增加而逐渐减少{c.reset}")
        else:
            lines.append(f"  充电循环次数: 未检测到 (不同机型数据有差异)")

        diagnostics = info.usage_diagnostics
        if diagnostics:
            lines.append(f"\n{c.cyan}🧭 中文诊断结论{c.reset}")
            for item in diagnostics:
                lines.append(f"  - {item}")

        if info.statistics and include_raw:
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
  %(prog)s --json report.json       # 另存机器可读 JSON（来源/置信度/窗口质量）
  %(prog)s --redact -o share.txt    # 生成可分享的脱敏报告
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
    parser.add_argument(
        '--json', type=Path, default=None, metavar='PATH',
        help='额外导出机器可读 JSON（含来源、置信度、窗口质量、BMS SoH、循环次数）'
    )
    parser.add_argument(
        '--redact', action='store_true',
        help='脱敏：隐藏蓝牙设备名、应用包名、进程名、唤醒锁标签和原始统计段，便于分享'
    )
    parser.add_argument(
        '--no-raw', action='store_true',
        help='报告不附原始 batterystats 统计段（结论与诊断仍完整输出）'
    )
    parser.add_argument(
        '--detailed-exit-codes', action='store_true',
        help='退出码细分：0=全部完整，3=无失败但有部分数据/跳过，1=存在解析失败（2 仍表示参数错误）'
    )
    return parser


def _safe_fingerprint(path: Path) -> Optional[dict]:
    try:
        return file_fingerprint(path)
    except (OSError, TypeError, ValueError):
        return None


def _validate_side_output(path: Path, zip_files: list[Path], suffix: str) -> Path:
    output_path = resolve_app_path(path)
    if output_path.suffix.lower() != suffix:
        raise ValueError(f'输出文件必须使用 {suffix} 后缀')
    if any(output_path == item.resolve() for item in zip_files):
        raise ValueError('输出路径不能覆盖输入诊断包')
    return output_path


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

    # JSON 路径在分析前校验，避免分析完大包后才发现路径不可用或会覆盖文本报告。
    json_path: Optional[Path] = None
    if args.json is not None:
        try:
            json_path = _validate_side_output(args.json, zip_files, '.json')
            if args.output is not None and json_path == resolve_app_path(args.output):
                raise ValueError('JSON 路径不能与 --output 报告相同')
        except (OSError, ValueError) as e:
            print(f"错误: 无法使用 JSON 输出路径: {e}")
            return 1

    colors = Colors()
    if args.no_color:
        colors.enabled = False
        colors._init_styles()

    extractor = BatteryExtractor()
    printer = ReportPrinter(colors)

    print(f"发现 {len(zip_files)} 个诊断文件，开始分析...")
    success = failed = skipped = partial = 0
    all_reports: list[str] = []
    payloads: list[dict] = []
    batch_results: list[tuple[str, Optional[BatteryInfo], Optional[str]]] = []

    for i, zip_path in enumerate(zip_files, 1):
        display_name = zip_path.name
        try:
            display_name = str(zip_path.relative_to(input_dir))
        except ValueError:
            pass
        print(f"\n[{i}/{len(zip_files)}] 正在分析: {display_name} ...", end='', flush=True)
        # 脱敏报告不含文件名（可能带姓名或目录名），用序号代替。
        label = f"文件{i}" if args.redact else display_name

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
                    apply_manual_design_capacity(info, design)

            fingerprint = _safe_fingerprint(zip_path)
            report_info = info
            report_name = zip_path.name
            if args.redact:
                report_info = redacted_copy(info)
                fingerprint = redacted_fingerprint(fingerprint, label)
                report_name = label
            report = printer.print_report(report_info, report_name, fingerprint, include_raw=not args.no_raw)
            all_reports.append(report)
            payloads.append(build_report_payload(report_info, fingerprint))
            batch_results.append((label, report_info, None))

            if info.current_capacity is None or not info.has_design_capacity:
                if user_skipped:
                    skipped += 1
                    print("  跳过")
                    print("  [提示] 用户跳过了手动输入设计容量")
                else:
                    print("  [提示] 已保留部分报告；缺少有效的设计容量或当前容量，暂时无法计算健康度")
                    failed += 1
                    partial += 1
                continue

            success += 1

        except zipfile.BadZipFile as e:
            print(f" 失败\n  [错误] ZIP 文件损坏或格式不正确: {e}")
            failed += 1
            batch_results.append((label, None, "ZIP 文件损坏或格式不正确"))
        except PermissionError as e:
            print(f" 失败\n  [错误] 文件访问被拒绝: {e}")
            failed += 1
            batch_results.append((label, None, "文件访问被拒绝"))
        except OSError as e:
            print(f" 失败\n  [错误] 文件系统错误: {e}")
            failed += 1
            batch_results.append((label, None, "文件系统错误"))
        except ValueError as e:
            print(f" 失败\n  [错误] {e}")
            failed += 1
            batch_results.append((label, None, "未找到可解析的诊断数据"))
        except Exception as e:
            print(f" 失败\n  [错误] 未知错误: {type(e).__name__}: {e}")
            failed += 1
            batch_results.append((label, None, type(e).__name__))

    print(f"\n{'=' * 42}")
    print(f"处理完成: {success} 成功, {failed} 失败, {skipped} 跳过")
    print(f"{'=' * 42}")

    if len(zip_files) > 1:
        summary = format_batch_summary(batch_results)
        print(f"\n{summary}")
        # 全部失败时不写只有汇总表的报告文件，与单文件失败时的行为一致。
        if all_reports:
            all_reports.append(summary)

    if args.output and all_reports:
        try:
            output_path = resolve_app_path(args.output)
            if output_path.suffix.lower() == '.zip':
                raise ValueError('输出路径不能使用 .zip 后缀，以免覆盖诊断包')
            if any(output_path == path.resolve() for path in zip_files):
                raise ValueError('输出路径不能覆盖输入诊断包')
            write_report_atomic(output_path, '\n---\n'.join(all_reports))
            print(f"\n报告已保存至: {output_path}")
            if not args.redact:
                print("[提示] 报告含应用包名、蓝牙设备名等使用痕迹，公开分享前可加 --redact 生成脱敏版。")
        except (OSError, ValueError) as e:
            print(f"\n[警告] 无法保存报告文件: {e}")
            return 1

    if json_path is not None and payloads:
        try:
            if len(zip_files) == 1:
                document = payloads[0]
            else:
                # 多文件时结构固定，失败的文件也列出来，脚本不必再猜 reports 与输入的对应关系。
                failures = [{"file": name, "error": error} for name, item, error in batch_results if item is None]
                document = {"schema": 1, "reports": payloads, "failures": failures}
            write_report_atomic(json_path, json.dumps(document, ensure_ascii=False, indent=2))
            print(f"JSON 已保存至: {json_path}")
        except (OSError, ValueError) as e:
            print(f"\n[警告] 无法保存 JSON 文件: {e}")
            return 1

    if sys.platform == 'win32' and is_interactive() and not args.no_pause:
        input("\n按回车键退出...")

    if args.detailed_exit_codes:
        hard_failures = failed - partial
        if hard_failures:
            return 1
        # 2 已被 argparse 用于参数错误，部分数据使用 3 以免脚本误判。
        return 3 if (partial or skipped) else 0
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
