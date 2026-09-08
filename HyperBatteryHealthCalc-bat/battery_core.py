#!/usr/bin/env python3
"""电池容量计算器 — 共享核心模块 (Q-CR 优化版)

包含 BatteryInfo 数据模型、BatteryExtractor 提取器、评分逻辑。
被 battery_calc.py (CLI) 和 battery_gui.py (GUI) 共同引用。
"""

from __future__ import annotations

import io
import math
from copy import deepcopy
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ── 数据模型 ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PowerComponent:
    """单项耗电构成"""
    name: str
    mah: float
    duration_seconds: Optional[float] = None


@dataclass(frozen=True)
class UidPower:
    """UID 级耗电记录"""
    uid: str
    mah: float
    foreground_mah: Optional[float] = None
    background_mah: Optional[float] = None
    foreground_service_mah: Optional[float] = None


@dataclass(frozen=True)
class WakeLockInfo:
    """唤醒锁排行记录"""
    name: str
    seconds: float
    count: Optional[int] = None


@dataclass(frozen=True)
class CpuProcessUsage:
    """CPU 快照中的进程耗时记录"""
    name: str
    percent: float
    user_percent: Optional[float] = None
    kernel_percent: Optional[float] = None


@dataclass(frozen=True)
class ScreenBrightnessBucket:
    """屏幕亮度分布记录"""
    name: str
    seconds: float
    percent: float


@dataclass
class BatteryInfo:
    """电池信息数据容器"""
    design_capacity: Optional[float] = None
    design_capacity_auto: bool = True
    design_capacity_source: Optional[str] = None
    cycle_count: Optional[int] = None
    full_capacity: Optional[float] = None
    charge_counter: Optional[int] = None
    battery_level: Optional[int] = None
    battery_scale: Optional[int] = None
    voltage_mv: Optional[int] = None
    temperature_c: Optional[float] = None
    technology: Optional[str] = None
    status_code: Optional[int] = None
    health_code: Optional[int] = None
    capacity_level: Optional[int] = None
    ac_powered: Optional[bool] = None
    usb_powered: Optional[bool] = None
    wireless_powered: Optional[bool] = None
    dock_powered: Optional[bool] = None
    max_charging_current_ma: Optional[int] = None
    max_charging_voltage_mv: Optional[int] = None
    device_name: Optional[str] = None
    report_time: Optional[str] = None
    estimated_capacity: Optional[float] = None
    last_learned_capacity: Optional[int] = None
    min_learned_capacity: Optional[int] = None
    max_learned_capacity: Optional[int] = None
    statistics: Optional[str] = None
    time_on_battery_seconds: Optional[float] = None
    screen_off_seconds: Optional[float] = None
    screen_on_seconds: Optional[float] = None
    total_runtime_seconds: Optional[float] = None
    total_discharge_mah: Optional[float] = None
    screen_on_discharge_mah: Optional[float] = None
    screen_off_discharge_mah: Optional[float] = None
    screen_doze_discharge_mah: Optional[float] = None
    device_deep_doze_discharge_mah: Optional[float] = None
    full_wakelock_seconds: Optional[float] = None
    partial_wakelock_seconds: Optional[float] = None
    wifi_multicast_wakelock_count: Optional[int] = None
    wifi_multicast_wakelock_seconds: Optional[float] = None
    connectivity_changes: Optional[int] = None
    computed_drain_mah: Optional[float] = None
    actual_drain_mah: Optional[float] = None
    cellular_received_bytes: Optional[int] = None
    cellular_sent_bytes: Optional[int] = None
    cellular_kernel_active_seconds: Optional[float] = None
    cellular_rx_seconds: Optional[float] = None
    wifi_received_bytes: Optional[int] = None
    wifi_sent_bytes: Optional[int] = None
    wifi_scan_seconds: Optional[float] = None
    bluetooth_received_bytes: Optional[int] = None
    bluetooth_sent_bytes: Optional[int] = None
    bluetooth_scan_seconds: Optional[float] = None
    bluetooth_rx_seconds: Optional[float] = None
    bluetooth_tx_seconds: Optional[float] = None
    bluetooth_drain_mah: Optional[float] = None
    bluetooth_connected_devices: list[str] = field(default_factory=list)
    cpu_load_1m: Optional[float] = None
    cpu_load_5m: Optional[float] = None
    cpu_load_15m: Optional[float] = None
    power_components: list[PowerComponent] = field(default_factory=list)
    top_uid_power: list[UidPower] = field(default_factory=list)
    kernel_wakelocks: list[WakeLockInfo] = field(default_factory=list)
    partial_wakelocks: list[WakeLockInfo] = field(default_factory=list)
    top_cpu_processes: list[CpuProcessUsage] = field(default_factory=list)
    screen_brightnesses: list[ScreenBrightnessBucket] = field(default_factory=list)
    uid_packages: dict[str, str] = field(default_factory=dict)
    parse_warnings: list[str] = field(default_factory=list)

    @property
    def has_design_capacity(self) -> bool:
        return self.design_capacity is not None and math.isfinite(self.design_capacity) and self.design_capacity > 0

    @property
    def battery_percentage(self) -> Optional[float]:
        scale = self.battery_scale if self.battery_scale is not None else 100
        level = self.battery_level
        if level is None or not math.isfinite(level) or not math.isfinite(scale) or scale <= 0 or not 0 <= level <= scale:
            return None
        return level / scale * 100

    @property
    def current_capacity(self) -> Optional[int]:
        if self.min_learned_capacity is not None and math.isfinite(self.min_learned_capacity) and self.min_learned_capacity > 0:
            return self.min_learned_capacity
        if (
            self.charge_counter is not None
            and math.isfinite(self.charge_counter)
            and self.charge_counter > 0
            and self.battery_percentage is not None
            and self.battery_percentage >= 95
        ):
            return self.charge_counter
        return None

    @property
    def current_capacity_source(self) -> str:
        if self.min_learned_capacity is not None and math.isfinite(self.min_learned_capacity) and self.min_learned_capacity > 0:
            return "batterystats 最小学习容量"
        if self.current_capacity is not None:
            return "满电状态 Charge counter 估算"
        return "未检测到"

    @property
    def health_percentage(self) -> Optional[float]:
        cap = self.current_capacity
        if self.has_design_capacity and cap is not None:
            return (cap / self.design_capacity) * 100
        return None

    @property
    def status_text(self) -> Optional[str]:
        return _BATTERY_STATUS_TEXT.get(self.status_code) if self.status_code is not None else None

    @property
    def health_text(self) -> Optional[str]:
        return _BATTERY_HEALTH_TEXT.get(self.health_code) if self.health_code is not None else None

    @property
    def capacity_level_text(self) -> Optional[str]:
        return _CAPACITY_LEVEL_TEXT.get(self.capacity_level) if self.capacity_level is not None else None

    @property
    def power_source_text(self) -> str:
        sources = []
        if self.ac_powered:
            sources.append("AC 电源")
        if self.usb_powered:
            sources.append("USB")
        if self.wireless_powered:
            sources.append("无线充电")
        if self.dock_powered:
            sources.append("底座")
        return "、".join(sources) if sources else "电池供电或未检测到外接电源"

    @property
    def max_charging_power_w(self) -> Optional[float]:
        if self.max_charging_current_ma is None or self.max_charging_voltage_mv is None:
            return None
        return (self.max_charging_current_ma * self.max_charging_voltage_mv) / 1_000_000

    @property
    def temperature_text(self) -> Optional[str]:
        if self.temperature_c is None:
            return None
        if self.temperature_c >= 45:
            return "过高，建议停止高负载并降温"
        if self.temperature_c >= 40:
            return "偏高，建议减少边充边用"
        if self.temperature_c < 0:
            return "过低，低温会影响续航和充电"
        return "正常"

    @property
    def screen_on_discharge_share(self) -> Optional[float]:
        return _percentage(self.screen_on_discharge_mah, self.total_discharge_mah)

    @property
    def screen_off_discharge_share(self) -> Optional[float]:
        return _percentage(self.screen_off_discharge_mah, self.total_discharge_mah)

    @property
    def screen_doze_discharge_share(self) -> Optional[float]:
        return _percentage(self.screen_doze_discharge_mah, self.total_discharge_mah)

    @property
    def device_deep_doze_discharge_share(self) -> Optional[float]:
        return _percentage(self.device_deep_doze_discharge_mah, self.total_discharge_mah)

    @property
    def screen_on_drain_ma(self) -> Optional[float]:
        return _drain_rate_ma(self.screen_on_discharge_mah, self.screen_on_seconds)

    @property
    def screen_off_drain_ma(self) -> Optional[float]:
        return _drain_rate_ma(self.screen_off_discharge_mah, self.screen_off_seconds)

    @property
    def partial_wakelock_share(self) -> Optional[float]:
        return _percentage(self.partial_wakelock_seconds, self.time_on_battery_seconds)

    @property
    def usage_diagnostics(self) -> list[str]:
        lines: list[str] = []
        pct = self.health_percentage
        if pct is not None:
            if pct < 70:
                lines.append(f"健康度 {pct:.2f}%，已低于 70%，如果续航明显变差，建议优先考虑售后检测或更换电池。")
            elif pct < 80:
                lines.append(f"健康度 {pct:.2f}%，处于正常衰减区间，建议继续观察续航；低于 70% 再优先考虑更换。")
            elif pct < 90:
                lines.append(f"健康度 {pct:.2f}%，整体仍可用，属于轻中度衰减。")
            else:
                lines.append(f"健康度 {pct:.2f}%，容量状态较好。")

        if self.screen_on_discharge_share is not None:
            drain = self.screen_on_drain_ma
            drain_text = f"，亮屏平均耗电约 {drain:.1f} mA" if drain is not None else ""
            lines.append(f"亮屏耗电占比 {self.screen_on_discharge_share:.1f}%{drain_text}，屏幕与前台使用是本次主要耗电来源。")

        if self.screen_brightnesses:
            summary = "、".join(_format_screen_brightness_item(item) for item in self.screen_brightnesses[:5])
            top = self.screen_brightnesses[0]
            if top.name in {"dark", "dim"} and top.percent >= 60:
                note = "本次亮屏主要处于低亮度，不像是高亮度本身导致耗电；可结合刷新率、前台应用、网络和 CPU 负载继续判断。"
            elif top.name in {"light", "bright"} and top.percent >= 50:
                note = "本次亮屏主要处于高亮度，屏幕亮度可能是亮屏耗电的重要因素。"
            else:
                note = "本次亮屏亮度分布较分散，可结合亮屏耗电和前台应用继续判断。"
            lines.append(f"亮度分布：{summary}，{note}")

        if self.screen_off_drain_ma is not None:
            note = "偏高，建议检查后台唤醒、定位、同步和常驻应用。" if self.screen_off_drain_ma >= 100 else "处于可接受范围。"
            lines.append(f"息屏平均耗电约 {self.screen_off_drain_ma:.1f} mA，{note}")

        if self.screen_doze_discharge_mah is not None:
            share = self.screen_doze_discharge_share
            if share is not None:
                lines.append(f"屏幕 Doze 耗电 {self.screen_doze_discharge_mah:.1f} mAh，占总耗电 {share:.1f}%，通常对应息屏显示或低功耗显示阶段。")

        if self.device_deep_doze_discharge_mah is not None:
            share = self.device_deep_doze_discharge_share
            if share is not None:
                lines.append(f"设备深度 Doze 耗电 {self.device_deep_doze_discharge_mah:.1f} mAh，占总耗电 {share:.1f}%，可用于判断长时间待机阶段的系统耗电占比。")

        if self.power_components:
            top = _format_top_mah_items((item.name, item.mah) for item in self.power_components[:3])
            lines.append(f"耗电构成前三：{top}，优先对应排查屏幕、CPU、基带、音频或相机等硬件/系统模块。")

        if self.top_uid_power:
            top = _format_top_uid_mah_items(self.top_uid_power[:3], self.uid_packages, self.total_discharge_mah)
            lines.append(f"最高耗电 UID：{top}，需要结合系统 UID/应用包名映射定位具体应用或系统服务。")

        if self.partial_wakelock_seconds is not None:
            share = self.partial_wakelock_share
            share_text = f"，占统计周期 {share:.1f}%" if share is not None else ""
            lines.append(f"部分唤醒锁约 {_format_duration_cn(self.partial_wakelock_seconds)}{share_text}，如果待机耗电高，应优先排查后台常驻和同步任务。")

        if self.kernel_wakelocks:
            item = self.kernel_wakelocks[0]
            count = f"、{item.count} 次" if item.count is not None else ""
            lines.append(f"Kernel 唤醒锁最长：{item.name} {_format_duration_cn(item.seconds)}{count}，用于判断系统内核或硬件链路是否长期阻止休眠。")

        if self.partial_wakelocks:
            item = self.partial_wakelocks[0]
            count = f"、{item.count} 次" if item.count is not None else ""
            name = _format_uid_name(item.name, self.uid_packages)
            lines.append(f"应用部分唤醒锁最长：{name} {_format_duration_cn(item.seconds)}{count}，这是后台耗电排查的首要线索。")

        if self.wifi_multicast_wakelock_seconds is not None:
            count = f"{self.wifi_multicast_wakelock_count} 次、" if self.wifi_multicast_wakelock_count is not None else ""
            lines.append(f"WiFi Multicast 唤醒锁 {count}累计约 {_format_duration_cn(self.wifi_multicast_wakelock_seconds)}，投屏、局域网发现或部分应用可能增加后台耗电。")

        if self.connectivity_changes is not None and self.connectivity_changes >= 200:
            lines.append(f"连接切换 {self.connectivity_changes} 次，网络环境频繁变化可能增加基带和 Wi-Fi 耗电。")

        if self.bluetooth_drain_mah is not None:
            parts = [f"蓝牙耗电 {self.bluetooth_drain_mah:.1f} mAh"]
            if self.bluetooth_scan_seconds is not None:
                parts.append(f"扫描约 {_format_duration_cn(self.bluetooth_scan_seconds)}")
            if self.bluetooth_received_bytes is not None and self.bluetooth_sent_bytes is not None:
                parts.append(
                    f"收发 {_format_bytes(self.bluetooth_received_bytes)}/{_format_bytes(self.bluetooth_sent_bytes)}"
                )
            message = "，".join(parts) + "，耳机、手环、车机或持续扫描都可能增加后台耗电。"
            if self.bluetooth_connected_devices:
                message += f"已连接蓝牙设备：{'、'.join(self.bluetooth_connected_devices[:3])}。"
            lines.append(message)

        if self.cellular_received_bytes is not None and self.cellular_sent_bytes is not None:
            details = [
                f"移动网络流量 {_format_bytes(self.cellular_received_bytes)} 下行 / {_format_bytes(self.cellular_sent_bytes)} 上行"
            ]
            if self.cellular_kernel_active_seconds is not None:
                details.append(f"蜂窝内核活跃约 {_format_duration_cn(self.cellular_kernel_active_seconds)}")
            if self.cellular_rx_seconds is not None:
                details.append(f"蜂窝接收约 {_format_duration_cn(self.cellular_rx_seconds)}")
            lines.append("，".join(details) + "，mobile_radio 高耗电时优先检查弱网、热点、后台联网和长时间移动数据传输。")

        if self.wifi_received_bytes is not None and self.wifi_sent_bytes is not None:
            scan_text = ""
            if self.wifi_scan_seconds is not None and self.wifi_scan_seconds > 0:
                scan_text = f"，Wi-Fi 扫描约 {_format_duration_cn(self.wifi_scan_seconds)}"
            lines.append(
                f"Wi-Fi 流量 {_format_bytes(self.wifi_received_bytes)} 下行 / {_format_bytes(self.wifi_sent_bytes)} 上行{scan_text}，用于判断本次网络耗电主要来自 Wi-Fi 还是移动网络。"
            )

        if self.cpu_load_1m is not None and self.cpu_load_5m is not None and self.cpu_load_15m is not None:
            load = f"{self.cpu_load_1m:.2f}/{self.cpu_load_5m:.2f}/{self.cpu_load_15m:.2f}"
            if self.top_cpu_processes:
                top = "、".join(f"{item.name} {item.percent:.1f}%" for item in self.top_cpu_processes[:3])
                lines.append(f"当前 CPU 负载 {load}，瞬时最高进程：{top}；需要和 cpu 模块耗电一起判断是否有高计算负载。")
            else:
                lines.append(f"当前 CPU 负载 {load}，需要结合 cpu 模块耗电判断是否存在高计算负载。")

        if self.temperature_c is not None:
            lines.append(f"抓包温度 {self.temperature_c:.1f} ℃（{self.temperature_text}）。")

        if self.max_charging_power_w is not None:
            if self.status_text == "已充满" and self.max_charging_power_w <= 10:
                lines.append(f"当前满电附近充电功率上限约 {self.max_charging_power_w:.2f} W，符合满电维护或低功率补电状态。")
            else:
                lines.append(f"当前系统报告充电功率上限约 {self.max_charging_power_w:.2f} W。")

        return lines or ["本次 bugreport 未提供足够的结构化耗电统计，只能显示容量快照。"]


# ── 评分逻辑 (统一, 三端一致) ──────────────────────────────────────────────


_RATING_TABLE: tuple[tuple[float, float, str, str], ...] = (
    (100.0001, float('inf'), '超出设计容量（可能为冗余设计或第三方电池）', '#e67e22'),
    (90,       100,          '极佳状态',                                   '#27ae60'),
    (80,       90,           '良好状态',                                   '#f39c12'),
    (70,       80,           '正常衰减',                                   '#e67e22'),
    (0,        70,           '建议考虑更换电池',                             '#e74c3c'),
)

_BATTERY_STATUS_TEXT = {
    1: "未知",
    2: "充电中",
    3: "放电中",
    4: "未充电",
    5: "已充满",
}

_BATTERY_HEALTH_TEXT = {
    1: "未知",
    2: "良好",
    3: "过热",
    4: "电池故障",
    5: "过压",
    6: "未知错误",
    7: "过冷",
}

_CAPACITY_LEVEL_TEXT = {
    1: "严重低电",
    2: "低电",
    3: "正常",
    4: "高电",
    5: "满电",
}

_SCREEN_BRIGHTNESS_TEXT = {
    "dark": "低亮度",
    "dim": "较低亮度",
    "medium": "中等亮度",
    "light": "较高亮度",
    "bright": "高亮",
}

__all__ = [
    'BatteryInfo',
    'BatteryExtractor',
    'PowerComponent',
    'UidPower',
    'WakeLockInfo',
    'CpuProcessUsage',
    'ScreenBrightnessBucket',
    'get_rating_text',
    'get_rating_color',
]


def _percentage(part: Optional[float], total: Optional[float]) -> Optional[float]:
    if part is None or total is None or total <= 0:
        return None
    return (part / total) * 100


def _drain_rate_ma(discharge_mah: Optional[float], seconds: Optional[float]) -> Optional[float]:
    if discharge_mah is None or seconds is None or seconds <= 0:
        return None
    return discharge_mah / (seconds / 3600)


def _format_duration_cn(seconds: float) -> str:
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    if hours:
        return f"{hours}小时{minutes}分钟"
    if minutes:
        return f"{minutes}分钟"
    return f"{total_seconds}秒"


def _format_top_mah_items(items) -> str:
    return "、".join(f"{name} {mah:.1f} mAh" for name, mah in items)


def _format_mah_with_share(mah: float, total_mah: Optional[float]) -> str:
    share = _percentage(mah, total_mah)
    share_text = f"，占总耗电 {share:.1f}%" if share is not None else ""
    return f"{mah:.1f} mAh{share_text}"


def _format_top_uid_mah_items(
    items: list[UidPower],
    uid_packages: dict[str, str],
    total_mah: Optional[float] = None,
) -> str:
    return "、".join(
        f"{_format_uid_label(item.uid, uid_packages)} "
        f"{_format_mah_with_share(item.mah, total_mah)}"
        f"{_format_uid_power_detail(item)}"
        for item in items
    )


def _format_uid_power_detail(item: UidPower) -> str:
    parts = []
    if item.foreground_mah is not None:
        parts.append(f"前台 {item.foreground_mah:.1f} mAh")
    if item.background_mah is not None:
        parts.append(f"后台 {item.background_mah:.1f} mAh")
    if item.foreground_service_mah is not None:
        parts.append(f"前台服务 {item.foreground_service_mah:.1f} mAh")
    return f"（{' / '.join(parts)}）" if parts else ""


def _format_screen_brightness_item(item: ScreenBrightnessBucket) -> str:
    label = _SCREEN_BRIGHTNESS_TEXT.get(item.name, item.name)
    return f"{label}({item.name}) {item.percent:.1f}%"


def _format_bytes(value: int) -> str:
    units = (("GB", 1024 ** 3), ("MB", 1024 ** 2), ("KB", 1024), ("B", 1))
    for unit, size in units:
        if value >= size or unit == "B":
            amount = value / size
            return f"{amount:.2f} {unit}" if unit != "B" else f"{int(amount)} B"
    return f"{value} B"


def _format_uid_label(uid: str, uid_packages: dict[str, str]) -> str:
    package = uid_packages.get(uid)
    return f"{uid}({package})" if package else uid


def _format_uid_name(name: str, uid_packages: dict[str, str]) -> str:
    parts = name.split(maxsplit=1)
    if not parts:
        return name
    uid = parts[0]
    label = _format_uid_label(uid, uid_packages)
    return f"{label} {parts[1]}" if len(parts) > 1 else label


def _parse_duration_seconds(text: str) -> float:
    total = 0.0
    for value, unit in re.findall(r'(\d+(?:\.\d+)?)\s*(ms|d|h|m|s)(?![a-zA-Z])', text):
        number = float(value)
        if unit == 'd':
            total += number * 86400
        elif unit == 'h':
            total += number * 3600
        elif unit == 'm':
            total += number * 60
        elif unit == 's':
            total += number
        elif unit == 'ms':
            total += number / 1000
    return total


def _parse_data_size_bytes(text: str) -> Optional[int]:
    m = re.search(r'([\d.]+)\s*(B|KB|MB|GB)\b', text, re.I)
    if not m:
        return None
    unit = m.group(2).upper()
    multiplier = {
        "B": 1,
        "KB": 1024,
        "MB": 1024 ** 2,
        "GB": 1024 ** 3,
    }[unit]
    return int(round(float(m.group(1)) * multiplier))


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
    _RE_TIME_ON_BATTERY = re.compile(r'Time on battery:\s*(.+?)\s*\(', re.I)
    _RE_SCREEN_OFF_TIME = re.compile(r'Time on battery screen off:\s*(.+?)\s*\(', re.I)
    _RE_TOTAL_RUNTIME = re.compile(r'Total run time:\s*(.+?)\s+realtime', re.I)
    _RE_SCREEN_ON_TIME = re.compile(r'Screen on:\s*(.+?)\s*\(', re.I)
    _RE_TOTAL_DISCHARGE = re.compile(r'^\s*Discharge:\s*([\d.]+)\s*mAh', re.I | re.M)
    _RE_SCREEN_OFF_DISCHARGE = re.compile(r'Screen off discharge:\s*([\d.]+)\s*mAh', re.I)
    _RE_SCREEN_DOZE_DISCHARGE = re.compile(r'Screen doze discharge:\s*([\d.]+)\s*mAh', re.I)
    _RE_SCREEN_ON_DISCHARGE = re.compile(r'Screen on discharge:\s*([\d.]+)\s*mAh', re.I)
    _RE_DEEP_DOZE_DISCHARGE = re.compile(r'Device deep doze discharge:\s*([\d.]+)\s*mAh', re.I)
    _RE_SCREEN_BRIGHTNESS_ITEM = re.compile(
        r'^\s*(dark|dim|medium|light|bright)\s+(.+?)\s+\(([\d.]+)%\)',
        re.I,
    )
    _RE_FULL_WAKELOCK = re.compile(r'Total full wakelock time:\s*(.+)', re.I)
    _RE_PARTIAL_WAKELOCK = re.compile(r'Total partial wakelock time:\s*(.+)', re.I)
    _RE_WIFI_MULTICAST_COUNT = re.compile(r'Total WiFi Multicast wakelock Count:\s*(\d+)', re.I)
    _RE_WIFI_MULTICAST_TIME = re.compile(r'Total WiFi Multicast wakelock time:\s*(.+)', re.I)
    _RE_CONNECTIVITY_CHANGES = re.compile(r'Connectivity changes:\s*(\d+)', re.I)
    _RE_CELLULAR_KERNEL_ACTIVE = re.compile(r'Cellular kernel active time:\s*(.+?)(?:\s*\(|$)', re.I)
    _RE_CELLULAR_RX_TIME = re.compile(r'Cellular Rx time:\s*(.+?)(?:\s*\(|$)', re.I)
    _RE_CELLULAR_DATA_RECEIVED = re.compile(r'Cellular data received:\s*(\S+)', re.I)
    _RE_CELLULAR_DATA_SENT = re.compile(r'Cellular data sent:\s*(\S+)', re.I)
    _RE_WIFI_SCAN_TIME = re.compile(r'WiFi Scan time:\s*(.+?)(?:\s*\(|$)', re.I)
    _RE_WIFI_DATA_RECEIVED = re.compile(r'Wifi data received:\s*(\S+)', re.I)
    _RE_WIFI_DATA_SENT = re.compile(r'Wifi data sent:\s*(\S+)', re.I)
    _RE_BLUETOOTH_TOTAL = re.compile(r'Bluetooth total received:\s*([^,]+),\s*sent:\s*(\S+)', re.I)
    _RE_BLUETOOTH_SCAN = re.compile(r'Bluetooth scan time:\s*(.+)', re.I)
    _RE_BLUETOOTH_RX = re.compile(r'Bluetooth Rx time:\s*(.+?)(?:\s*\(|$)', re.I)
    _RE_BLUETOOTH_TX = re.compile(r'Bluetooth Tx time:\s*(.+?)(?:\s*\(|$)', re.I)
    _RE_BLUETOOTH_DRAIN = re.compile(r'Bluetooth Battery drain:\s*([\d.]+)\s*mAh', re.I)
    _RE_BLUETOOTH_DEVICE = re.compile(r'^(.+?)\s+profiles=\[[^\]]*\]\s+connected=true\b', re.I)
    _RE_CPU_LOAD = re.compile(r'Load:\s*([\d.]+)\s*/\s*([\d.]+)\s*/\s*([\d.]+)', re.I)
    _RE_CPU_PROCESS = re.compile(
        r'^  ([\d.]+)%\s+\d+/(.+?):\s+([\d.]+)%\s+user\s+\+\s+([\d.]+)%\s+kernel',
        re.I,
    )
    _RE_POWER_DRAIN = re.compile(
        r'Capacity:\s*[\d.]+,\s*Computed drain:\s*([\d.]+),\s*actual drain:\s*([\d.]+)',
        re.I,
    )
    _RE_POWER_COMPONENT = re.compile(
        r'^\s{4}([A-Za-z_]+):\s*([\d.]+)(?:.*?\bduration:\s*(.+?))?\s*.*$',
        re.I,
    )
    _RE_UID_POWER = re.compile(
        r'^\s*UID\s+([^:]+):\s*([\d.]+)(?:\s+fg:\s*([\d.]+))?(?:.*?\s+bg:\s*([\d.]+))?(?:.*?\s+fgs:\s*([\d.]+))?',
        re.I,
    )
    _RE_KERNEL_WAKELOCK_LEADER = re.compile(
        r'^\s*Kernel Wake lock\s+(.+?):\s*(.+?)\s+\((\d+)\s+times\)',
        re.I,
    )
    _RE_PARTIAL_WAKELOCK_LEADER = re.compile(
        r'^\s*Wake lock\s+(.+?):\s*(.+?)\s+\((\d+)\s+times\)',
        re.I,
    )
    _RE_UID_PACKAGE_STAR = re.compile(
        r'\*\s+([A-Za-z0-9_.:]+)\s*/\s*(u\d+a\d+|\d+)\b'
    )
    _RE_UID_PACKAGE_APP = re.compile(
        r'\bapp=\d+:([A-Za-z0-9_.:]+)/(u\d+a\d+)\b'
    )
    _RE_UID_PACKAGE_HISTORY = re.compile(
        r'\b(?:top|fg|longwake)=(u\d+a\d+):"([^"]+)"'
    )

    def extract(self, zip_path: Path) -> BatteryInfo:
        info = BatteryInfo()
        parse_errors: list[str] = []

        with zipfile.ZipFile(zip_path, 'r') as outer_zip:
            inner_names = self._find_inner_zips(outer_zip)
            parsed = False

            if inner_names:
                for inner_name in inner_names:
                    try:
                        inner_data = outer_zip.read(inner_name)
                    except Exception as exc:
                        parse_errors.append(f'内层归档读取失败: {inner_name} ({exc})')
                        continue

                    try:
                        with zipfile.ZipFile(io.BytesIO(inner_data), 'r') as inner_zip:
                            parsed = self._parse_bundle_payload(inner_zip, info) or parsed
                    except zipfile.BadZipFile as exc:
                        parse_errors.append(f'内层归档非法: {inner_name} ({exc})')
                        continue
                    except Exception as exc:
                        parse_errors.append(f'内层归档解析异常: {inner_name} ({exc})')
                        continue

            try:
                parsed = self._parse_bundle_payload(outer_zip, info) or parsed
            except Exception as exc:
                parse_errors.append(f'外层归档解析失败 ({exc})')

            if not parsed:
                error_text = "未找到可解析的诊断文本（缺少 android.hardware.health 或 bugreport）"
                if parse_errors:
                    error_text = f"{error_text}；解析失败明细: {' | '.join(parse_errors)}"
                raise ValueError(error_text)

        info.parse_warnings.extend(parse_errors)
        return info

    def _parse_bundle_payload(self, zf: zipfile.ZipFile, info: BatteryInfo) -> bool:
        parsed = False
        for keyword, parser in (
            ('android.hardware.health', self._parse_health_stream),
            ('bugreport', self._parse_bugreport_stream),
        ):
            for entry in zf.infolist():
                name = entry.filename.lower()
                if entry.is_dir() or not name.endswith('.txt') or keyword not in name:
                    continue
                try:
                    candidate = deepcopy(info)
                    parser(zf, entry.filename, candidate)
                    info.__dict__.update(candidate.__dict__)
                    parsed = True
                except Exception as exc:
                    info.parse_warnings.append(f'日志解析失败: {entry.filename} ({type(exc).__name__})')
        return parsed

    @staticmethod
    def _find_inner_zips(outer_zip: zipfile.ZipFile) -> list[str]:
        return sorted(
            [
                name
                for name in outer_zip.namelist()
                if name and not name.endswith('/') and name.lower().endswith('.zip')
            ]
        )

    @staticmethod
    def _find_file(zf: zipfile.ZipFile, prefix: str, suffix: str) -> Optional[str]:
        lower_prefix = prefix.lower()
        lower_suffix = suffix.lower()
        for name in zf.namelist():
            lower_name = name.lower()
            if lower_prefix in lower_name and lower_name.endswith(lower_suffix):
                return name
        return None

    def _parse_health_stream(self, zf: zipfile.ZipFile, filename: str, info: BatteryInfo) -> None:
        with zf.open(filename) as raw:
            text_stream = io.TextIOWrapper(raw, encoding='utf-8-sig', errors='replace')
            for line in text_stream:
                line = line.rstrip('\n\r')

                if not info.has_design_capacity or info.design_capacity_source != 'hardware health 设计容量':
                    m = self._RE_DESIGN_CAPACITY.search(line)
                    if m and int(m.group(1)) > 0:
                        info.design_capacity = int(m.group(1)) / 1000
                        info.design_capacity_source = "hardware health 设计容量"

                if info.cycle_count is None:
                    m = self._RE_CYCLE_COUNT.search(line)
                    if m:
                        info.cycle_count = int(m.group(1))

                if info.full_capacity is None:
                    m = self._RE_FULL_CAPACITY.search(line)
                    if m:
                        info.full_capacity = int(m.group(1)) / 1000

                if (
                    info.design_capacity is not None
                    and info.cycle_count is not None
                    and info.full_capacity is not None
                ):
                    break

    def _parse_bugreport_stream(self, zf: zipfile.ZipFile, filename: str, info: BatteryInfo) -> None:
        with zf.open(filename) as raw:
            text_stream = io.TextIOWrapper(raw, encoding='utf-8-sig', errors='replace')
            in_stats = False
            in_battery_state = False
            in_power_use = False
            in_wakelock_leaders = False
            in_bluetooth_devices = False
            in_cpu_snapshot = False
            stats_lines: list[str] = []
            power_lines: list[str] = []
            wakelock_lines: list[str] = []

            for line in text_stream:
                line = line.rstrip('\n\r')
                stripped = line.strip()
                self._parse_uid_package_line(line, info)
                self._parse_connectivity_line(stripped, info)
                self._parse_bluetooth_stats_line(stripped, info)

                m = self._RE_CPU_LOAD.search(stripped)
                if m and info.cpu_load_1m is None:
                    info.cpu_load_1m = float(m.group(1))
                    info.cpu_load_5m = float(m.group(2))
                    info.cpu_load_15m = float(m.group(3))

                if stripped.startswith('CPU usage from'):
                    in_cpu_snapshot = True
                    continue
                if in_cpu_snapshot:
                    m = self._RE_CPU_PROCESS.match(line)
                    if m:
                        self._remember_cpu_process(
                            info,
                            CpuProcessUsage(
                                name=m.group(2).strip(),
                                percent=float(m.group(1)),
                                user_percent=float(m.group(3)),
                                kernel_percent=float(m.group(4)),
                            ),
                        )
                        if len(info.top_cpu_processes) >= 5:
                            in_cpu_snapshot = False

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

                if stripped == 'Current Battery Service state:':
                    in_battery_state = True
                    continue

                if stripped == 'Bluetooth Devices:':
                    in_bluetooth_devices = True
                    continue

                if in_bluetooth_devices:
                    if not stripped or stripped.startswith('CRITICAL dump') or stripped.endswith('Controller:'):
                        in_bluetooth_devices = False
                    else:
                        self._parse_bluetooth_device_line(stripped, info)

                if in_battery_state:
                    if (
                        stripped.startswith('MiuiBatteryService')
                        or stripped.startswith('---------')
                        or stripped.startswith('DUMP OF SERVICE')
                    ):
                        in_battery_state = False
                    else:
                        self._parse_battery_state_line(stripped, info)

                if stripped.startswith('Estimated power use (mAh):'):
                    in_power_use = True
                    power_lines = [line]
                elif in_power_use:
                    if stripped == '':
                        in_power_use = False
                        self._parse_power_use_text('\n'.join(power_lines), info)
                        power_lines = []
                    elif len(power_lines) < 1500:
                        power_lines.append(line)

                if stripped == 'All kernel wake locks:':
                    in_wakelock_leaders = True
                    wakelock_lines = [line]
                elif stripped == 'All partial wake locks:':
                    in_wakelock_leaders = True
                    wakelock_lines = [line]
                elif in_wakelock_leaders:
                    if stripped == '':
                        in_wakelock_leaders = False
                        self._parse_wakelock_leaders_text('\n'.join(wakelock_lines), info)
                        wakelock_lines = []
                    elif len(wakelock_lines) < 1500:
                        wakelock_lines.append(line)

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
            if in_power_use and power_lines:
                self._parse_power_use_text('\n'.join(power_lines), info)
            if in_wakelock_leaders and wakelock_lines:
                self._parse_wakelock_leaders_text('\n'.join(wakelock_lines), info)

    def _parse_stats_text(self, text: str, info: BatteryInfo) -> None:
        m = self._RE_ESTIMATED.search(text)
        if m:
            info.estimated_capacity = float(m.group(1))
            if not info.has_design_capacity and math.isfinite(info.estimated_capacity) and info.estimated_capacity > 0:
                info.design_capacity = info.estimated_capacity
                info.design_capacity_source = "batterystats 估算容量"

        m = self._RE_LAST_LEARNED.search(text)
        if m:
            info.last_learned_capacity = int(float(m.group(1)))

        m = self._RE_MIN_LEARNED.search(text)
        if m:
            info.min_learned_capacity = int(float(m.group(1)))

        m = self._RE_MAX_LEARNED.search(text)
        if m:
            info.max_learned_capacity = int(float(m.group(1)))

        self._parse_usage_stats_text(text, info)
        self._parse_power_use_text(text, info)
        self._parse_wakelock_leaders_text(text, info)

    def _parse_usage_stats_text(self, text: str, info: BatteryInfo) -> None:
        duration_fields = (
            (self._RE_TIME_ON_BATTERY, "time_on_battery_seconds"),
            (self._RE_SCREEN_OFF_TIME, "screen_off_seconds"),
            (self._RE_TOTAL_RUNTIME, "total_runtime_seconds"),
            (self._RE_SCREEN_ON_TIME, "screen_on_seconds"),
            (self._RE_FULL_WAKELOCK, "full_wakelock_seconds"),
            (self._RE_PARTIAL_WAKELOCK, "partial_wakelock_seconds"),
            (self._RE_WIFI_MULTICAST_TIME, "wifi_multicast_wakelock_seconds"),
        )
        for pattern, attr in duration_fields:
            m = pattern.search(text)
            if m:
                setattr(info, attr, _parse_duration_seconds(m.group(1)))

        value_fields = (
            (self._RE_TOTAL_DISCHARGE, "total_discharge_mah"),
            (self._RE_SCREEN_OFF_DISCHARGE, "screen_off_discharge_mah"),
            (self._RE_SCREEN_DOZE_DISCHARGE, "screen_doze_discharge_mah"),
            (self._RE_SCREEN_ON_DISCHARGE, "screen_on_discharge_mah"),
            (self._RE_DEEP_DOZE_DISCHARGE, "device_deep_doze_discharge_mah"),
        )
        for pattern, attr in value_fields:
            m = pattern.search(text)
            if m:
                setattr(info, attr, float(m.group(1)))

        m = self._RE_WIFI_MULTICAST_COUNT.search(text)
        if m:
            info.wifi_multicast_wakelock_count = int(m.group(1))

        m = self._RE_CONNECTIVITY_CHANGES.search(text)
        if m:
            info.connectivity_changes = int(m.group(1))

        self._parse_screen_brightness_stats_text(text, info)

    def _parse_screen_brightness_stats_text(self, text: str, info: BatteryInfo) -> None:
        items: list[ScreenBrightnessBucket] = []
        in_section = False

        for line in text.splitlines():
            stripped = line.strip()
            if stripped.lower() == "screen brightnesses:":
                in_section = True
                continue
            if not in_section:
                continue
            if not stripped:
                break

            m = self._RE_SCREEN_BRIGHTNESS_ITEM.match(line)
            if not m:
                if not line.startswith((" ", "\t")) or stripped.endswith(":"):
                    break
                continue
            items.append(
                ScreenBrightnessBucket(
                    name=m.group(1).lower(),
                    seconds=_parse_duration_seconds(m.group(2)),
                    percent=float(m.group(3)),
                )
            )

        if items:
            info.screen_brightnesses = sorted(items, key=lambda item: item.seconds, reverse=True)

    def _parse_connectivity_line(self, line: str, info: BatteryInfo) -> None:
        duration_patterns = (
            (self._RE_CELLULAR_KERNEL_ACTIVE, "cellular_kernel_active_seconds"),
            (self._RE_CELLULAR_RX_TIME, "cellular_rx_seconds"),
            (self._RE_WIFI_SCAN_TIME, "wifi_scan_seconds"),
        )
        for pattern, attr in duration_patterns:
            m = pattern.search(line)
            if m:
                if getattr(info, attr) is None:
                    setattr(info, attr, _parse_duration_seconds(m.group(1)))
                return

        size_patterns = (
            (self._RE_CELLULAR_DATA_RECEIVED, "cellular_received_bytes"),
            (self._RE_CELLULAR_DATA_SENT, "cellular_sent_bytes"),
            (self._RE_WIFI_DATA_RECEIVED, "wifi_received_bytes"),
            (self._RE_WIFI_DATA_SENT, "wifi_sent_bytes"),
        )
        for pattern, attr in size_patterns:
            m = pattern.search(line)
            if m:
                value = _parse_data_size_bytes(m.group(1))
                if value is not None and getattr(info, attr) is None:
                    setattr(info, attr, value)
                return

    def _parse_bluetooth_stats_line(self, line: str, info: BatteryInfo) -> None:
        m = self._RE_BLUETOOTH_TOTAL.search(line)
        if m:
            received = _parse_data_size_bytes(m.group(1))
            sent = _parse_data_size_bytes(m.group(2))
            if received is not None:
                info.bluetooth_received_bytes = received
            if sent is not None:
                info.bluetooth_sent_bytes = sent
            return

        duration_patterns = (
            (self._RE_BLUETOOTH_SCAN, "bluetooth_scan_seconds"),
            (self._RE_BLUETOOTH_RX, "bluetooth_rx_seconds"),
            (self._RE_BLUETOOTH_TX, "bluetooth_tx_seconds"),
        )
        for pattern, attr in duration_patterns:
            m = pattern.search(line)
            if m:
                setattr(info, attr, _parse_duration_seconds(m.group(1)))
                return

        m = self._RE_BLUETOOTH_DRAIN.search(line)
        if m:
            info.bluetooth_drain_mah = float(m.group(1))

    def _parse_bluetooth_device_line(self, line: str, info: BatteryInfo) -> None:
        m = self._RE_BLUETOOTH_DEVICE.match(line)
        if not m:
            return
        device = m.group(1).strip()
        if device and device not in info.bluetooth_connected_devices:
            info.bluetooth_connected_devices.append(device)

    @staticmethod
    def _remember_cpu_process(info: BatteryInfo, item: CpuProcessUsage) -> None:
        if len(info.top_cpu_processes) >= 5:
            return
        if any(existing.name == item.name for existing in info.top_cpu_processes):
            return
        info.top_cpu_processes.append(item)

    def _parse_power_use_text(self, text: str, info: BatteryInfo) -> None:
        m = self._RE_POWER_DRAIN.search(text)
        if m:
            info.computed_drain_mah = float(m.group(1))
            info.actual_drain_mah = float(m.group(2))

        components: list[PowerComponent] = []
        uids: list[UidPower] = []
        in_global = False

        for line in text.splitlines():
            stripped = line.strip()
            if stripped == 'Global':
                in_global = True
                continue
            if in_global:
                m = self._RE_POWER_COMPONENT.match(line)
                if m:
                    duration = _parse_duration_seconds(m.group(3)) if m.group(3) else None
                    components.append(PowerComponent(m.group(1), float(m.group(2)), duration))
                    continue
                if stripped.startswith('UID '):
                    in_global = False
                elif stripped and not stripped.startswith('('):
                    in_global = False

            m = self._RE_UID_POWER.match(line)
            if m:
                uids.append(
                    UidPower(
                        uid=m.group(1).strip(),
                        mah=float(m.group(2)),
                        foreground_mah=float(m.group(3)) if m.group(3) else None,
                        background_mah=float(m.group(4)) if m.group(4) else None,
                        foreground_service_mah=float(m.group(5)) if m.group(5) else None,
                    )
                )

        if components:
            info.power_components = sorted(components, key=lambda item: item.mah, reverse=True)[:10]
        if uids:
            info.top_uid_power = sorted(uids, key=lambda item: item.mah, reverse=True)[:10]

    def _parse_wakelock_leaders_text(self, text: str, info: BatteryInfo) -> None:
        kernel_items: list[WakeLockInfo] = []
        partial_items: list[WakeLockInfo] = []
        in_partial = False

        for line in text.splitlines():
            stripped = line.strip()
            if stripped == 'All partial wake locks:':
                in_partial = True
                continue
            if not in_partial:
                m = self._RE_KERNEL_WAKELOCK_LEADER.match(line)
                if m:
                    kernel_items.append(
                        WakeLockInfo(
                            name=m.group(1).strip(),
                            seconds=_parse_duration_seconds(m.group(2)),
                            count=int(m.group(3)),
                        )
                    )
                continue

            m = self._RE_PARTIAL_WAKELOCK_LEADER.match(line)
            if m:
                partial_items.append(
                    WakeLockInfo(
                        name=m.group(1).strip(),
                        seconds=_parse_duration_seconds(m.group(2)),
                        count=int(m.group(3)),
                    )
                )

        if kernel_items:
            info.kernel_wakelocks = sorted(kernel_items, key=lambda item: item.seconds, reverse=True)[:10]
        if partial_items:
            info.partial_wakelocks = sorted(partial_items, key=lambda item: item.seconds, reverse=True)[:10]

    def _parse_uid_package_line(self, line: str, info: BatteryInfo) -> None:
        for pattern in (self._RE_UID_PACKAGE_STAR, self._RE_UID_PACKAGE_APP):
            m = pattern.search(line)
            if m:
                self._remember_uid_package(info, m.group(2), m.group(1))
                return
        m = self._RE_UID_PACKAGE_HISTORY.search(line)
        if m:
            self._remember_uid_package(info, m.group(1), m.group(2))

    @staticmethod
    def _remember_uid_package(info: BatteryInfo, uid: str, package: str) -> None:
        package = package.strip().split(':', 1)[0]
        if not uid or not package:
            return
        existing = info.uid_packages.get(uid)
        if existing is None or (':' in existing and ':' not in package):
            info.uid_packages[uid] = package

    def _parse_battery_state_line(self, line: str, info: BatteryInfo) -> None:
        if ':' not in line:
            return
        key, raw_value = line.split(':', 1)
        key = key.strip()
        value = raw_value.strip()
        if not value:
            return

        def as_bool(text: str) -> Optional[bool]:
            if text.lower() == 'true':
                return True
            if text.lower() == 'false':
                return False
            return None

        def as_int(text: str) -> Optional[int]:
            try:
                return int(text)
            except ValueError:
                return None

        int_value = as_int(value)

        if key == 'AC powered':
            info.ac_powered = as_bool(value)
        elif key == 'USB powered':
            info.usb_powered = as_bool(value)
        elif key == 'Wireless powered':
            info.wireless_powered = as_bool(value)
        elif key == 'Dock powered':
            info.dock_powered = as_bool(value)
        elif key == 'Max charging current' and int_value is not None:
            info.max_charging_current_ma = int_value // 1000
        elif key == 'Max charging voltage' and int_value is not None:
            info.max_charging_voltage_mv = int_value // 1000
        elif key == 'Charge counter' and int_value is not None:
            info.charge_counter = int_value // 1000
        elif key == 'status' and int_value is not None:
            info.status_code = int_value
        elif key == 'health' and int_value is not None:
            info.health_code = int_value
        elif key == 'level' and int_value is not None:
            info.battery_level = int_value
        elif key == 'scale' and int_value is not None:
            info.battery_scale = int_value
        elif key == 'voltage' and int_value is not None:
            info.voltage_mv = int_value
        elif key == 'temperature' and int_value is not None:
            info.temperature_c = int_value / 10
        elif key == 'technology':
            info.technology = value
        elif key == 'Capacity level' and int_value is not None:
            info.capacity_level = int_value
