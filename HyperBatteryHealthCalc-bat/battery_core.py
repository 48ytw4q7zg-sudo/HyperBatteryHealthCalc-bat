#!/usr/bin/env python3
"""电池容量计算器 — 共享核心模块 (Q-CR 优化版)

包含 BatteryInfo 数据模型、BatteryExtractor 提取器、评分逻辑。
被 battery_calc.py (CLI) 和 battery_gui.py (GUI) 共同引用。
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# ── 数据模型 ──────────────────────────────────────────────────────────────


@dataclass
class BatteryInfo:
    """电池信息数据容器 — 11 字段 + 3 计算属性"""
    design_capacity: Optional[float] = None
    design_capacity_auto: bool = True
    cycle_count: Optional[int] = None
    full_capacity: Optional[float] = None
    device_name: Optional[str] = None
    report_time: Optional[str] = None
    estimated_capacity: Optional[float] = None
    last_learned_capacity: Optional[int] = None
    min_learned_capacity: Optional[int] = None
    max_learned_capacity: Optional[int] = None
    statistics: Optional[str] = None

    @property
    def has_design_capacity(self) -> bool:
        return self.design_capacity is not None and self.design_capacity > 0

    @property
    def current_capacity(self) -> Optional[int]:
        return self.min_learned_capacity

    @property
    def health_percentage(self) -> Optional[float]:
        cap = self.current_capacity
        if self.has_design_capacity and cap is not None:
            return (cap / self.design_capacity) * 100
        return None


# ── 评分逻辑 (统一, 三端一致) ──────────────────────────────────────────────


_RATING_TABLE: tuple[tuple[float, float, str, str], ...] = (
    (100.0001, float('inf'), '超出设计容量（可能为冗余设计或第三方电池）', '#e67e22'),
    (90,       100,          '极佳状态',                                   '#27ae60'),
    (80,       90,           '良好状态',                                   '#f39c12'),
    (70,       80,           '正常衰减',                                   '#e67e22'),
    (0,        70,           '建议考虑更换电池',                             '#e74c3c'),
)

__all__ = ['BatteryInfo', 'BatteryExtractor', 'get_rating_text', 'get_rating_color']


def get_rating_text(percentage: float) -> str:
    """根据健康百分比返回中文评级文本"""
    for low, high, text, _ in _RATING_TABLE:
        if low <= percentage <= high:
            return text
    return '未知状态'


def get_rating_color(percentage: float) -> str:
    """根据健康百分比返回十六进制颜色值"""
    for low, high, _, color in _RATING_TABLE:
        if low <= percentage <= high:
            return color
    return '#718096'


# ── 核心提取器 ─────────────────────────────────────────────────────────────


class BatteryExtractor:
    """电池数据提取器 — 逐行流式处理，避免大文件内存爆炸"""

    _RE_DESIGN_CAPACITY = re.compile(r'batteryFullChargeDesignCapacityUah\s*[:=]\s*(\d+)')
    _RE_CYCLE_COUNT = re.compile(r'batteryCycleCount\s*[:=]\s*(\d+)')
    _RE_FULL_CAPACITY = re.compile(r'batteryFullCharge(?:Uah)?\s*[:=]\s*(\d+)')
    _RE_MARKET_NAME = re.compile(r'\[ro\.product\.marketname\]:\s*\[([^\]]+)\]')
    _RE_MODEL = re.compile(r'\[ro\.product\.model\]:\s*\[([^\]]+)\]')
    _RE_REPORT_TIME = re.compile(r'== dumpstate:\s*(.+)')
    _RE_ESTIMATED = re.compile(r'Estimated battery capacity:\s*([\d.]+)\s*mAh', re.I)
    _RE_LAST_LEARNED = re.compile(r'Last learned battery capacity:\s*([\d.]+)\s*mAh', re.I)
    _RE_MIN_LEARNED = re.compile(r'Min learned battery capacity:\s*([\d.]+)\s*mAh', re.I)
    _RE_MAX_LEARNED = re.compile(r'Max learned battery capacity:\s*([\d.]+)\s*mAh', re.I)

    def extract(self, zip_path: Path) -> BatteryInfo:
        info = BatteryInfo()

        with zipfile.ZipFile(zip_path, 'r') as outer_zip:
            inner_names = self._find_inner_zips(outer_zip)
            if not inner_names:
                raise ValueError('未找到内层 ZIP 文件（诊断文件应包含嵌套 ZIP）')

            for inner_name in inner_names:
                inner_data = outer_zip.read(inner_name)
                with zipfile.ZipFile(io.BytesIO(inner_data), 'r') as inner_zip:
                    health_file = self._find_file(inner_zip, 'android.hardware.health', '.txt')
                    bugreport_file = self._find_file(inner_zip, 'bugreport', '.txt')

                    if health_file:
                        self._parse_health_stream(inner_zip, health_file, info)
                    if bugreport_file:
                        self._parse_bugreport_stream(inner_zip, bugreport_file, info)

                    if info.has_design_capacity and info.current_capacity is not None:
                        break

        return info

    @staticmethod
    def _find_inner_zips(outer_zip: zipfile.ZipFile) -> list[str]:
        return [name for name in outer_zip.namelist() if name.endswith('.zip')]

    @staticmethod
    def _find_file(zf: zipfile.ZipFile, prefix: str, suffix: str) -> Optional[str]:
        for name in zf.namelist():
            if prefix in name and name.endswith(suffix):
                return name
        return None

    def _parse_health_stream(self, zf: zipfile.ZipFile, filename: str, info: BatteryInfo) -> None:
        with zf.open(filename) as raw:
            text_stream = io.TextIOWrapper(raw, encoding='utf-8-sig', errors='replace')
            for line in text_stream:
                line = line.rstrip('\n\r')

                if info.design_capacity is None:
                    m = self._RE_DESIGN_CAPACITY.search(line)
                    if m:
                        info.design_capacity = int(m.group(1)) / 1000

                if info.cycle_count is None:
                    m = self._RE_CYCLE_COUNT.search(line)
                    if m:
                        info.cycle_count = int(m.group(1))

                if info.full_capacity is None:
                    m = self._RE_FULL_CAPACITY.search(line)
                    if m:
                        info.full_capacity = int(m.group(1)) / 1000

                if info.design_capacity is not None and info.cycle_count is not None:
                    break

    def _parse_bugreport_stream(self, zf: zipfile.ZipFile, filename: str, info: BatteryInfo) -> None:
        with zf.open(filename) as raw:
            text_stream = io.TextIOWrapper(raw, encoding='utf-8-sig', errors='replace')
            in_stats = False
            stats_lines: list[str] = []

            for line in text_stream:
                line = line.rstrip('\n\r')
                stripped = line.strip()

                if info.device_name is None:
                    m = self._RE_MARKET_NAME.search(line)
                    if m:
                        info.device_name = m.group(1).strip()
                        continue
                    m = self._RE_MODEL.search(line)
                    if m:
                        info.device_name = m.group(1).strip()
                        continue

                if info.report_time is None:
                    m = self._RE_REPORT_TIME.search(line)
                    if m:
                        info.report_time = m.group(1).strip()

                if stripped.startswith('Statistics since last charge:'):
                    in_stats = True
                    stats_lines.append(line)
                elif in_stats:
                    if stripped == '':
                        info.statistics = '\n'.join(stats_lines)
                        in_stats = False
                        self._parse_stats_text(info.statistics, info)
                        stats_lines = []
                    else:
                        stats_lines.append(line)

            if in_stats and stats_lines:
                info.statistics = '\n'.join(stats_lines)
                self._parse_stats_text(info.statistics, info)

    def _parse_stats_text(self, text: str, info: BatteryInfo) -> None:
        m = self._RE_ESTIMATED.search(text)
        if m:
            info.estimated_capacity = float(m.group(1))

        m = self._RE_LAST_LEARNED.search(text)
        if m:
            info.last_learned_capacity = int(float(m.group(1)))

        m = self._RE_MIN_LEARNED.search(text)
        if m:
            info.min_learned_capacity = int(float(m.group(1)))

        m = self._RE_MAX_LEARNED.search(text)
        if m:
            info.max_learned_capacity = int(float(m.group(1)))
