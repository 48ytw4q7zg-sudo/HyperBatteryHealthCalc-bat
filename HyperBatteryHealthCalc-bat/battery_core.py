#!/usr/bin/env python3
"""电池容量计算器 — 共享核心模块 (Q-CR 优化版)

包含 BatteryInfo 数据模型、BatteryExtractor 提取器、评分逻辑。
被 battery_calc.py (CLI) 和 battery_gui.py (GUI) 共同引用。
"""

from __future__ import annotations

import csv
import hashlib
import io
import logging
import math
import tarfile
import tempfile
import time
from copy import deepcopy
from datetime import date, datetime
import re
import sys
import zipfile
from dataclasses import dataclass, field, replace as dataclass_replace
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger("battery_core")

# 解析器版本：写入报告指纹，便于回溯同一 ZIP 在不同版本下的差异。
PARSER_BUILD = "2026.09.26"

DESIGN_SOURCE_HEALTH = "hardware health 设计容量"
DESIGN_SOURCE_BMS = "charge_logger BMS 设计容量"
DESIGN_SOURCE_ESTIMATED = "batterystats 估算容量"
DESIGN_SOURCE_MANUAL = "手动输入"

CYCLE_SOURCE_HEALTH = "hardware health 循环次数"
CYCLE_SOURCE_BMS = "charge_logger BMS 循环次数"

CURRENT_SOURCE_LEARNED = "batterystats 最小学习容量"
CURRENT_SOURCE_COUNTER = "满电状态 Charge counter 估算"

# 低于 70% 但证据不足（估算设计容量/学习值无分化/与 BMS 冲突）时替代“建议考虑更换电池”。
SOFT_REPLACEMENT_RATING = "明显衰减（证据不足，待复核）"

# 设计容量来源 → (置信度, 说明)。报告三端都用这张表解释“这个百分比有多可信”。
_DESIGN_SOURCE_CONFIDENCE = {
    DESIGN_SOURCE_HEALTH: ("高", "来自系统 health 节点的出厂设计容量"),
    DESIGN_SOURCE_BMS: ("高", "来自电池管理芯片（BMS）日志的设计容量"),
    DESIGN_SOURCE_ESTIMATED: ("中", "来自 batterystats 功耗配置的估算容量，不一定等于官方标称容量"),
    DESIGN_SOURCE_MANUAL: ("用户声明", "由用户手动填写，准确性取决于填写值"),
}


class ExtractionCancelled(Exception):
    """用户取消解析（GUI 取消按钮）。"""

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


@dataclass(frozen=True)
class BmsDailyPoint:
    """charge_logger 按日聚合的 BMS 快照（取当天最后一条有效记录）"""
    day: str
    full_mah: Optional[float] = None
    soh: Optional[float] = None
    cycle_count: Optional[int] = None


@dataclass
class BatteryInfo:
    """电池信息数据容器"""
    design_capacity: Optional[float] = None
    design_capacity_auto: bool = True
    design_capacity_source: Optional[str] = None
    cycle_count: Optional[int] = None
    cycle_count_source: Optional[str] = None
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
    device_codename: Optional[str] = None
    build_id: Optional[str] = None
    build_incremental: Optional[str] = None
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
    # charge_logger（BMS 电池管理芯片日志）侧信道；抓包时刻取最后一条有效记录
    bms_full_capacity: Optional[float] = None
    bms_design_capacity: Optional[float] = None
    bms_cycle_count: Optional[int] = None
    bms_soh: Optional[float] = None
    bms_sample_count: int = 0
    bms_history: list[BmsDailyPoint] = field(default_factory=list)
    bms_max_temperature_c: Optional[float] = None
    bms_high_temperature_share: Optional[float] = None
    charge_protocol: Optional[str] = None
    charge_pd_verified: Optional[bool] = None
    stats_truncated: bool = False
    skipped_inner_archives: list[str] = field(default_factory=list)
    parse_stats: dict[str, float] = field(default_factory=dict)
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
            return CURRENT_SOURCE_LEARNED
        if self.current_capacity is not None:
            return CURRENT_SOURCE_COUNTER
        return "未检测到"

    @property
    def health_percentage(self) -> Optional[float]:
        cap = self.current_capacity
        if self.has_design_capacity and cap is not None:
            return (cap / self.design_capacity) * 100
        return None

    @property
    def design_capacity_confidence(self) -> Optional[tuple[str, str]]:
        """设计容量来源对应的 (置信度, 说明)；决定健康度百分比能否被当作结论。"""
        if not self.has_design_capacity:
            return None
        if not self.design_capacity_auto:
            return _DESIGN_SOURCE_CONFIDENCE[DESIGN_SOURCE_MANUAL]
        return _DESIGN_SOURCE_CONFIDENCE.get(self.design_capacity_source, ("中", "来源未标注的自动检测值"))

    @property
    def learned_capacity_note(self) -> Optional[str]:
        values = [
            value for value in (self.last_learned_capacity, self.min_learned_capacity, self.max_learned_capacity)
            if value is not None and math.isfinite(value) and value > 0
        ]
        if len(values) < 3 or (max(values) - min(values)) / max(values) >= 0.01:
            return None
        return (
            "上次/最小/最大学习容量几乎相同（差异不足 1%），学习样本不足或尚未完成完整学习，"
            "健康度可能不稳定，建议完整充放电循环后复测。"
        )

    @property
    def bms_soh_gap(self) -> Optional[float]:
        """BMS SoH 减去容量比健康度（百分点）；两者口径不同，仅用于冲突告警。"""
        pct = self.health_percentage
        if pct is None or self.bms_soh is None:
            return None
        return self.bms_soh - pct

    @property
    def has_soh_conflict(self) -> bool:
        gap = self.bms_soh_gap
        return gap is not None and abs(gap) > 10

    @property
    def health_evidence(self) -> tuple[str, list[str]]:
        """健康度结论的证据强度（强/中/弱）及降级原因。手动填写视为用户声明，不降级。"""
        reasons: list[str] = []
        if self.has_design_capacity and self.design_capacity_auto and self.design_capacity_source == DESIGN_SOURCE_ESTIMATED:
            reasons.append("设计容量为 batterystats 估算值")
        if self.current_capacity is not None and self.current_capacity_source == CURRENT_SOURCE_COUNTER:
            reasons.append("当前容量来自满电 Charge counter 估算")
        if self.learned_capacity_note:
            reasons.append("学习容量三值无分化")
        if self.has_soh_conflict:
            reasons.append("与 BMS SoH 差异超过 10 个百分点")
        level = "强" if not reasons else ("中" if len(reasons) == 1 else "弱")
        return level, reasons

    @property
    def rating_text(self) -> Optional[str]:
        """报告使用的评级：低于 70% 且证据不足时不直接给出“建议更换”。"""
        pct = self.health_percentage
        if pct is None:
            return None
        if pct < 70 and self.health_evidence[0] != "强":
            return SOFT_REPLACEMENT_RATING
        return get_rating_text(pct)

    @property
    def health_percentage_band(self) -> Optional[tuple[float, float]]:
        """满电 Charge counter 与学习容量交叉得到的健康度区间。"""
        if not self.has_design_capacity:
            return None
        learned, counter, level = self.min_learned_capacity, self.charge_counter, self.battery_percentage
        if learned is None or not math.isfinite(learned) or learned <= 0:
            return None
        if counter is None or not math.isfinite(counter) or counter <= 0 or level is None or level < 95:
            return None
        values = (learned / self.design_capacity * 100, counter / self.design_capacity * 100)
        if abs(values[0] - values[1]) > 10:
            return None
        return min(values), max(values)

    @property
    def is_charging_snapshot(self) -> bool:
        powered = (self.ac_powered, self.usb_powered, self.wireless_powered, self.dock_powered)
        return self.status_code in (2, 5) or any(value is True for value in powered)

    @property
    def has_usage_stats(self) -> bool:
        """是否解析到 batterystats 放电/耗电统计；只有容量快照时不输出窗口质量标签。"""
        return any(value is not None for value in (
            self.time_on_battery_seconds, self.total_discharge_mah, self.screen_on_discharge_mah,
            self.screen_off_discharge_mah, self.partial_wakelock_seconds,
        )) or bool(self.power_components or self.top_uid_power)

    @property
    def window_quality(self) -> list[str]:
        """统计窗口质量标签：决定耗电结论能代表多长的真实使用。"""
        labels: list[str] = []
        if not self.has_usage_stats:
            return labels
        if self.is_charging_snapshot:
            labels.append("抓包时正在充电或已充满（耗电统计来自此前的放电窗口）")
        on_battery = self.time_on_battery_seconds
        if on_battery is not None and on_battery > 0:
            if on_battery < 3 * 3600:
                labels.append(f"短会话（放电窗口约 {_format_duration_cn(on_battery)}）")
            if self.screen_on_seconds is not None and self.screen_on_seconds / on_battery >= 0.8:
                labels.append(f"高亮屏占比（亮屏约 {min(self.screen_on_seconds / on_battery * 100, 100):.0f}%）")
        if (
            self.has_design_capacity and self.total_discharge_mah is not None
            and self.total_discharge_mah >= 0.8 * self.design_capacity
        ):
            labels.append("接近完整放电周期")
        return labels

    @property
    def field_sources(self) -> dict[str, str]:
        """关键字段 → 数据来源，供 JSON 导出和三端一致渲染。"""
        sources: dict[str, str] = {}
        if self.has_design_capacity:
            sources["design_capacity"] = (
                DESIGN_SOURCE_MANUAL if not self.design_capacity_auto else (self.design_capacity_source or "自动检测")
            )
        if self.current_capacity is not None:
            sources["current_capacity"] = self.current_capacity_source
        if self.cycle_count is not None:
            sources["cycle_count"] = self.cycle_count_source or CYCLE_SOURCE_HEALTH
        if self.full_capacity is not None:
            sources["full_capacity"] = "hardware health 满充容量"
        if self.estimated_capacity is not None:
            sources["estimated_capacity"] = "batterystats 估算容量"
        if self.charge_counter is not None:
            sources["charge_counter"] = "Current Battery Service state"
        for name in ("bms_soh", "bms_full_capacity", "bms_design_capacity", "bms_cycle_count"):
            if getattr(self, name) is not None:
                sources[name] = "charge_logger BMS"
        return sources

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
            lines.append(self._health_diagnostic_line(pct))
            band = self.health_percentage_band
            if band is not None and band[1] - band[0] >= 0.05:
                lines.append(
                    f"满电 Charge counter 与学习容量交叉估算，健康度约 {band[0]:.1f}%–{band[1]:.1f}%"
                    "（Charge counter 仅在接近满电时可信），不必过度解读小数点后两位。"
                )
        if self.learned_capacity_note:
            lines.append(self.learned_capacity_note)
        confidence = self.design_capacity_confidence
        if confidence is not None and self.design_capacity_auto and self.design_capacity_source == DESIGN_SOURCE_ESTIMATED:
            lines.append(
                f"设计容量来源：{DESIGN_SOURCE_ESTIMATED}（置信度{confidence[0]}），{confidence[1]}；"
                "健康度百分比仅供参考，不是售后官方结论。"
            )
        if self.health_text:
            lines.append(
                f"系统 health 状态为「{self.health_text}」，表示内核上报的电气状态（过热/过压/故障等），"
                "不等于满充容量比例。"
            )
        lines.extend(self._bms_diagnostic_lines())
        if self.cycle_count is not None and self.cycle_count >= 800:
            soh_note = f"，即使 SoH 仍为 {self.bms_soh:.0f}%" if self.bms_soh is not None and self.bms_soh > 85 else ""
            lines.append(f"循环次数约 {self.cycle_count} 次，已偏高{soh_note}，建议关注衰减速度。")
        quality = self.window_quality
        if quality:
            limited = any(label.startswith(("短会话", "高亮屏", "抓包时")) for label in quality)
            note = (
                "本次耗电结论只代表这个统计窗口，不宜直接当作全天续航或电池好坏的依据。"
                if limited else "统计窗口接近完整放电周期，耗电结论代表性较好。"
            )
            lines.append(f"统计窗口：{'、'.join(quality)}。{note}")

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
            if self.screen_off_seconds is not None and self.screen_off_seconds < SHORT_SCREEN_OFF_SAMPLE_SECONDS:
                lines.append(
                    f"息屏平均耗电约 {self.screen_off_drain_ma:.1f} mA，但息屏样本仅 "
                    f"{_format_duration_cn(self.screen_off_seconds)}，样本过短，仅供参考，不能据此判断待机耗电。"
                )
            else:
                note = "偏高，建议检查后台唤醒、定位、同步和常驻应用。" if self.screen_off_drain_ma >= 100 else "处于可接受范围。"
                lines.append(f"息屏平均耗电约 {self.screen_off_drain_ma:.1f} mA，{note}")

        if self.screen_doze_discharge_mah is not None:
            share = self.screen_doze_discharge_share
            if self.screen_doze_discharge_mah <= 0:
                lines.append("本次无有效屏幕 Doze 样本（0 mAh），通常是几乎全程亮屏或未进入息屏显示，不代表 Doze 耗电“正常为零”。")
            elif share is not None:
                lines.append(f"屏幕 Doze 耗电 {self.screen_doze_discharge_mah:.1f} mAh，占总耗电 {share:.1f}%，通常对应息屏显示或低功耗显示阶段。")

        if self.device_deep_doze_discharge_mah is not None:
            share = self.device_deep_doze_discharge_share
            if self.device_deep_doze_discharge_mah <= 0:
                lines.append("本次无有效设备深度 Doze 样本（0 mAh），说明统计窗口内几乎没有长时间静置待机，无法评估待机耗电。")
            elif share is not None:
                lines.append(f"设备深度 Doze 耗电 {self.device_deep_doze_discharge_mah:.1f} mAh，占总耗电 {share:.1f}%，可用于判断长时间待机阶段的系统耗电占比。")

        if self.power_components:
            top = _format_top_mah_items((item.name, item.mah) for item in self.power_components[:3])
            lines.append(f"耗电构成前三：{top}，优先对应排查屏幕、CPU、基带、音频或相机等硬件/系统模块。")

        if self.top_uid_power:
            top = _format_top_uid_mah_items(self.top_uid_power[:3], self.uid_packages, self.total_discharge_mah)
            lines.append(f"最高耗电 UID：{top}，需要结合系统 UID/应用包名映射定位具体应用或系统服务。")
            merged = _multi_user_app_note(self.top_uid_power, self.uid_packages)
            if merged:
                lines.append(merged)

        drain_note = self._drain_consistency_note()
        if drain_note:
            lines.append(drain_note)

        if self.partial_wakelock_seconds is not None:
            share = self.partial_wakelock_share
            share_text = f"，占统计周期 {share:.1f}%" if share is not None else ""
            lines.append(f"部分唤醒锁约 {_format_duration_cn(self.partial_wakelock_seconds)}{share_text}，如果待机耗电高，应优先排查后台常驻和同步任务。")

        if self.kernel_wakelocks:
            item = self.kernel_wakelocks[0]
            lines.append(f"Kernel 唤醒锁最长：{item.name} {_format_duration_cn(item.seconds)}{_format_wakelock_count(item)}，用于判断系统内核或硬件链路是否长期阻止休眠。")

        if self.partial_wakelocks:
            item = self.partial_wakelocks[0]
            name = _format_uid_name(item.name, self.uid_packages)
            lines.append(f"应用部分唤醒锁最长：{name} {_format_duration_cn(item.seconds)}{_format_wakelock_count(item)}，这是后台耗电排查的首要线索。")

        if self.wifi_multicast_wakelock_seconds is not None:
            count = f"{self.wifi_multicast_wakelock_count} 次、" if self.wifi_multicast_wakelock_count is not None else ""
            lines.append(f"WiFi Multicast 唤醒锁 {count}累计约 {_format_duration_cn(self.wifi_multicast_wakelock_seconds)}，投屏、局域网发现或部分应用可能增加后台耗电。")

        connectivity = self._connectivity_note()
        if connectivity:
            lines.append(connectivity)

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

        if not self.has_usage_stats or not lines:
            lines.append(NO_USAGE_STATS_NOTE)
        return lines

    def _health_diagnostic_line(self, pct: float) -> str:
        level, reasons = self.health_evidence
        reason_text = "、".join(reasons)
        if pct < 70:
            if level == "强":
                return f"健康度 {pct:.2f}%，已低于 70%，如果续航明显变差，建议优先考虑售后检测或更换电池。"
            return (
                f"健康度 {pct:.2f}%，按当前数据低于 70%，但证据强度为{level}（{reason_text}），"
                "请结合官方检测、完整充放电循环后复测或 charge_logger 数据再判断，暂不建议仅凭此数字更换电池。"
            )
        if pct < 80:
            line = f"健康度 {pct:.2f}%，处于正常衰减区间，建议继续观察续航；低于 70% 再优先考虑更换。"
        elif pct < 90:
            line = f"健康度 {pct:.2f}%，整体仍可用，属于轻中度衰减。"
        else:
            line = f"健康度 {pct:.2f}%，容量状态较好。"
        if level != "强":
            line += f"（证据强度：{level}，{reason_text}）"
        return line

    def _bms_diagnostic_lines(self) -> list[str]:
        lines: list[str] = []
        parts = []
        if self.bms_soh is not None:
            parts.append(f"SoH {self.bms_soh:.0f}%")
        if self.bms_full_capacity is not None:
            capacity = f"满充 {self.bms_full_capacity:.0f} mAh"
            if self.bms_design_capacity is not None:
                capacity += f" / 设计 {self.bms_design_capacity:.0f} mAh"
            parts.append(capacity)
        if self.bms_cycle_count is not None:
            parts.append(f"循环 {self.bms_cycle_count} 次")
        if parts:
            lines.append(f"BMS 电池管理芯片记录（charge_logger）：{'，'.join(parts)}。")
        gap = self.bms_soh_gap
        if gap is not None and self.has_soh_conflict:
            lines.append(
                f"口径冲突：容量比健康度 {self.health_percentage:.1f}% 与 BMS SoH {self.bms_soh:.0f}% "
                f"相差 {abs(gap):.1f} 个百分点，请勿只看单一数字；建议完整充放电循环后复测，或以官方检测为准。"
            )
        if self.bms_soh is not None:
            lines.append(
                "口径说明：SoH 是电池管理芯片的厂商健康指标（可能综合内阻、电压模型），"
                "容量比是“当前满充容量 ÷ 设计容量”的简单除法，两者定义不同，数值不必一致。"
            )
        lines.extend(self.bms_trend_notes)
        extras = []
        if self.charge_protocol:
            verified = "，PD 已认证" if self.charge_pd_verified else ""
            extras.append(f"充电协议 {self.charge_protocol}{verified}")
        if self.bms_max_temperature_c is not None:
            extras.append(f"记录最高温度 {self.bms_max_temperature_c:.1f} ℃")
        if self.bms_high_temperature_share is not None:
            extras.append(f"高于 40 ℃ 的记录占 {self.bms_high_temperature_share:.1f}%")
        if extras:
            hot = (self.bms_high_temperature_share or 0) >= 10 or (self.bms_max_temperature_c or 0) >= 45
            note = "；高温时段较多，边充边玩会加速电池老化。" if hot else "。"
            lines.append(f"充电记录：{'，'.join(extras)}{note}")
        return lines

    @property
    def bms_trend_notes(self) -> list[str]:
        """BMS 满充容量趋势：近 7/30 日变化（参考点须落在窗口附近）与非线性骤降识别。"""
        points = [point for point in self.bms_history if point.full_mah is not None]
        if len(points) < 2:
            return []
        first, last = points[0], points[-1]
        notes = [f"BMS 满充容量趋势：{first.day} {first.full_mah:.0f} mAh → {last.day} {last.full_mah:.0f} mAh（{len(points)} 天有记录）。"]
        last_day = _parse_day(last.day)
        if last_day is not None:
            windows = []
            for days in (7, 30):
                # 参考点取距最后一条 N 到 N+max(3, N/2) 天之间最近的记录；记录断档时不把半年前的数据当作“近 N 日”。
                limit = days + max(3, days // 2)
                reference, gap = None, None
                for point in points:
                    point_day = _parse_day(point.day)
                    if point_day is not None and days <= (last_day - point_day).days <= limit:
                        reference, gap = point, (last_day - point_day).days
                if reference is not None:
                    windows.append(
                        f"近 {days} 日 {last.full_mah - reference.full_mah:+.0f} mAh（对比 {reference.day}，相隔 {gap} 天）"
                    )
            if windows:
                notes.append(f"满充容量变化：{'，'.join(windows)}，全历史 {last.full_mah - first.full_mah:+.0f} mAh。")
        design = self.design_capacity if self.has_design_capacity else self.bms_design_capacity
        threshold = max(300.0, 0.05 * design) if design else 300.0
        for previous, current in zip(points, points[1:]):
            drop = previous.full_mah - current.full_mah
            previous_day, current_day = _parse_day(previous.day), _parse_day(current.day)
            span = (current_day - previous_day).days if previous_day and current_day else None
            soh_change = (
                abs(previous.soh - current.soh) if previous.soh is not None and current.soh is not None else None
            )
            if drop >= threshold and (span is None or span <= 35) and (soh_change is None or soh_change <= 2):
                if soh_change is not None:
                    cause = f"而 SoH 仅变化 {soh_change:.0f} 点，更像电量计校准事件而非线性老化"
                else:
                    cause = "缺少同期 SoH 记录，无法区分电量计校准事件和真实衰减"
                notes.append(
                    f"{previous.day}→{current.day} 满充容量骤降 {drop:.0f} mAh，{cause}；"
                    "建议完整充放电循环后复测，不宜据此线性推算剩余寿命。"
                )
                break
        return notes

    def _drain_consistency_note(self) -> Optional[str]:
        computed, total = self.computed_drain_mah, self.total_discharge_mah
        if computed is None or total is None or computed <= 0 or total <= 0:
            return None
        difference = abs(computed - total) / total * 100
        if difference <= 30:
            return None
        return (
            f"power profile 估算耗电 {computed:.0f} mAh 与实际放电统计（Discharge）{total:.0f} mAh 相差 {difference:.0f}%，"
            "两者来源不同，勿直接相加或换算；应用/模块排名只作相对参考。"
        )

    def _connectivity_note(self) -> Optional[str]:
        changes = self.connectivity_changes
        if changes is None:
            return None
        window = self.time_on_battery_seconds or self.total_runtime_seconds
        rate = changes / (window / 3600) if window is not None and window >= 1800 else None
        # 窗口已知时只看每小时频率（长窗口累计 200 次也可能正常）；窗口未知才退回总次数阈值。
        if rate is not None:
            if rate < 20 or changes < 50:
                return None
        elif changes < 200:
            return None
        rate_text = f"（约 {rate:.0f} 次/小时）" if rate is not None else ""
        cellular = any(item.name == "mobile_radio" for item in self.power_components[:3])
        extra = "，且 mobile_radio 位列耗电前三，弱网切换可能是基带高耗电的原因" if cellular else ""
        return f"连接切换 {changes} 次{rate_text}，网络环境频繁变化可能增加基带和 Wi-Fi 耗电{extra}。"

    @property
    def root_causes(self) -> list[tuple[str, str]]:
        """按影响排序的本次可行动项：(根因, 建议)，最多 4 条。"""
        scored: list[tuple[float, str, str]] = []
        pct = self.health_percentage
        level, _reasons = self.health_evidence
        if pct is not None:
            if self.has_soh_conflict or (pct < 70 and level != "强"):
                soh = f"，BMS SoH {self.bms_soh:.0f}%" if self.bms_soh is not None else ""
                scored.append((
                    90, f"容量衰减待确认（容量比 {pct:.1f}%{soh}，证据强度{level}）",
                    "先完整充放电一次后重新抓取诊断，或到官方售后检测，再决定是否换电池",
                ))
            elif pct < 70:
                scored.append((95, f"电池容量明显衰减（{pct:.1f}%）", "建议售后检测或更换电池"))
        screen_share = self.screen_on_discharge_share
        if screen_share is not None and screen_share >= 60:
            scored.append((
                min(screen_share, 100), f"亮屏使用是主要耗电（约占 {min(screen_share, 100):.0f}%）",
                "降低亮度/刷新率，减少长时间高负载前台使用",
            ))
        if self.top_uid_power and self.total_discharge_mah:
            top = self.top_uid_power[0]
            share = _percentage(top.mah, self.total_discharge_mah)
            if share is not None and share >= 15:
                label = _format_uid_label(top.uid, self.uid_packages)
                package = _uid_package(top.uid, self.uid_packages) or ""
                if _is_system_uid(top.uid):
                    title, action = (
                        f"系统组件 {label} 耗电突出",
                        "多由系统服务或硬件链路（基带、音频、定位等）引起，无法按应用限制；重启后复测，持续偏高再联系官方售后",
                    )
                elif _looks_like_game(package):
                    title, action = f"游戏 {label} 耗电突出", "游戏时尽量用 Wi-Fi、降低画质和帧率，避免边充边玩"
                else:
                    title, action = f"应用 {label} 耗电突出", "检查该应用的后台与自启动权限，必要时限制后台运行"
                scored.append((min(share, 100) * 0.9, title, action))
        if any(item.name == "mobile_radio" for item in self.power_components[:2]):
            scored.append((70, "蜂窝网络耗电高（mobile_radio 位列耗电前二）", "弱网环境优先使用 Wi-Fi，关闭不必要的后台联网和热点"))
        if self.bluetooth_connected_devices and (self.bluetooth_drain_mah or 0) >= 30:
            devices = "、".join(self.bluetooth_connected_devices[:2])
            scored.append((50, f"蓝牙外设常连（{devices}）", "不用时断开手环/耳机，或降低手环同步频率"))
        wakelock_share = self.partial_wakelock_share
        if wakelock_share is not None and wakelock_share >= 30:
            scored.append((
                min(wakelock_share, 100), f"后台唤醒锁偏多（占统计周期 {min(wakelock_share, 100):.0f}%）",
                "排查常驻、同步类应用的后台权限",
            ))
        if (
            self.screen_off_drain_ma is not None and self.screen_off_drain_ma >= 100
            and (self.screen_off_seconds or 0) >= 1800
        ):
            scored.append((60, f"待机耗电偏高（息屏约 {self.screen_off_drain_ma:.0f} mA）", "检查后台唤醒、定位与同步"))
        if (self.temperature_c is not None and self.temperature_c >= 40) or (self.bms_high_temperature_share or 0) >= 10:
            scored.append((55, "电池温度偏高", "避免边充边玩，高温时暂停高负载应用"))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [(title, action) for _score, title, action in scored[:4]]

    @property
    def summary_lines(self) -> list[str]:
        """报告首屏结论条：三口径并列 → 来源置信度 → 统计窗口 → 可行动项。"""
        lines: list[str] = []
        pct = self.health_percentage
        if pct is not None:
            level, reasons = self.health_evidence
            reason_text = f"；{'、'.join(reasons)}" if reasons else ""
            lines.append(
                f"容量健康度（当前容量 ÷ 设计容量）：{pct:.1f}%，评级：{self.rating_text}，证据强度：{level}{reason_text}"
            )
        else:
            lines.append("容量健康度：无法计算（缺少设计容量或当前容量）")
        if self.bms_soh is not None:
            lines.append(f"BMS 健康度（SoH，厂商口径）：{self.bms_soh:.0f}%")
        if self.health_text:
            lines.append(f"系统 health 状态：{self.health_text}（电气状态，不是容量比）")
        if self.has_soh_conflict:
            lines.append(f"【注意】两种健康度相差 {abs(self.bms_soh_gap):.1f} 个百分点，口径冲突，请勿只看单一数字")
        confidence = self.design_capacity_confidence
        if confidence is not None:
            source = self.field_sources.get("design_capacity", "自动检测")
            lines.append(f"设计容量来源：{source}（置信度：{confidence[0]}）")
        if self.cycle_count is not None:
            lines.append(f"循环次数：{self.cycle_count} 次（来源：{self.cycle_count_source or CYCLE_SOURCE_HEALTH}）")
        quality = self.window_quality
        if quality:
            lines.append(f"统计窗口：{'、'.join(quality)}")
        for index, (title, action) in enumerate(self.root_causes, 1):
            lines.append(f"可行动项 {index}：{title} → {action}")
        return lines


# ── 评分逻辑 (统一, 三端一致) ──────────────────────────────────────────────


_RATING_TABLE: tuple[tuple[float, float, str, str], ...] = (
    (100.0001, float('inf'), '超出设计容量（可能为冗余设计或第三方电池）', '#e67e22'),
    (90,       100.0001,     '极佳状态',                                   '#27ae60'),
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

# 息屏样本短于 5 分钟时，平均电流只是噪声，不做“偏高/正常”判断。
SHORT_SCREEN_OFF_SAMPLE_SECONDS = 300
NO_USAGE_STATS_NOTE = "本次 bugreport 未提供足够的结构化耗电统计，只能显示容量快照。"
_DOWNGRADE_WARNING_PREFIX = "未找到 android.hardware.health 节点，设计容量已降级使用"

# Android 固定系统 UID（android_filesystem_config.h）。注意 1027 才是 nfc，1041 是 audioserver。
_SYSTEM_UID_NAMES = {
    "0": "root/内核",
    "1000": "system/Android 系统",
    "1001": "radio/电话与基带",
    "1002": "bluetooth/蓝牙",
    "1010": "wifi/无线网络",
    "1013": "media/媒体服务",
    "1021": "gps/定位",
    "1027": "nfc/NFC",
    "1041": "audioserver/音频服务",
    "1047": "cameraserver/相机服务",
    "1073": "network_stack/网络栈",
    "2000": "shell",
}
# MIUI/HyperOS 应用双开使用 user 999；同一 appId 在不同用户下是同一个应用。
_DUAL_APP_USER_ID = "999"
_RE_APP_UID = re.compile(r'^u(\d+)a(\d+)$')
_RE_PACKAGE_NAME = re.compile(r'^[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)*$')
_GAME_PACKAGE_HINTS = ('game', '.tmgp.', 'mihoyo', 'hoyoverse', 'netease.', 'supercell', 'tencent.ig')

__all__ = [
    'BatteryInfo',
    'BatteryExtractor',
    'BmsDailyPoint',
    'ExtractionCancelled',
    'PowerComponent',
    'UidPower',
    'WakeLockInfo',
    'CpuProcessUsage',
    'ScreenBrightnessBucket',
    'PARSER_BUILD',
    'apply_manual_design_capacity',
    'build_report_payload',
    'batch_summary_rows',
    'file_fingerprint',
    'format_batch_summary',
    'format_batch_summary_csv',
    'get_rating_text',
    'get_rating_color',
    'redacted_copy',
    'redacted_fingerprint',
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
    if share is not None and share > 100:
        # power profile 估算与 Discharge 统计不是同一本账，超过 100% 的“占比”没有意义。
        return f"{mah:.1f} mAh（高于本次实际放电统计，属 power profile 估算口径，仅用于排名）"
    share_text = f"，占总耗电 {share:.1f}%" if share is not None else ""
    return f"{mah:.1f} mAh{share_text}"


def _format_wakelock_count(item: WakeLockInfo) -> str:
    if item.count is None:
        return ""
    if item.count == 0 and item.seconds > 0:
        return "、次数未记录"
    return f"、{item.count} 次"


def _uid_package(uid: str, uid_packages: dict[str, str]) -> Optional[str]:
    package = uid_packages.get(uid)
    if package:
        return package
    match = _RE_APP_UID.match(uid)
    if match and match.group(1) != "0":
        # 双开/多用户与主用户共享 appId，包名一致。
        return uid_packages.get(f"u0a{match.group(2)}")
    return None


def _is_system_uid(uid: str) -> bool:
    # 纯数字且小于 10000（FIRST_APPLICATION_UID）的是系统固定 UID，不是可限制后台的普通应用。
    return uid.isdigit() and int(uid) < 10000


def _looks_like_game(package: str) -> bool:
    lowered = package.lower()
    return any(hint in lowered for hint in _GAME_PACKAGE_HINTS)


def _multi_user_app_note(items: list[UidPower], uid_packages: dict[str, str]) -> Optional[str]:
    groups: dict[str, list[UidPower]] = {}
    for item in items:
        match = _RE_APP_UID.match(item.uid)
        if match:
            groups.setdefault(match.group(2), []).append(item)
    notes = []
    for app_id, members in groups.items():
        if len(members) < 2:
            continue
        package = next((_uid_package(member.uid, uid_packages) for member in members if _uid_package(member.uid, uid_packages)), None)
        uids = "、".join(member.uid for member in members)
        notes.append(f"{package or 'appId ' + app_id}（{uids}）合计 {sum(member.mah for member in members):.1f} mAh")
    if not notes:
        return None
    return f"同一应用的主用户与双开/分身合并计算：{'；'.join(notes)}。"


def _parse_day(text: str) -> Optional[date]:
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


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
    package = _uid_package(uid, uid_packages)
    match = _RE_APP_UID.match(uid)
    user_note = ""
    if match and match.group(1) != "0":
        user_note = "·应用双开" if match.group(1) == _DUAL_APP_USER_ID else f"·用户{match.group(1)}"
    if package:
        return f"{uid}({package}{user_note})"
    if uid in _SYSTEM_UID_NAMES:
        return f"{uid}({_SYSTEM_UID_NAMES[uid]})"
    if user_note:
        return f"{uid}({user_note[1:]})"
    return uid


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


class _ExtractRun:
    """单次解析的进度、取消与耗时统计（不写入 BatteryInfo 的业务字段）。"""

    def __init__(
        self,
        progress: Optional[Callable[[dict], None]] = None,
        cancel_event=None,
    ) -> None:
        self.progress = progress
        self.cancel_event = cancel_event
        self.started = time.perf_counter()
        self.bytes_read = 0
        self.entries = 0
        self.health_files = 0
        self.current = ""
        self._last_emit = 0.0

    def check(self) -> None:
        if self.cancel_event is not None and self.cancel_event.is_set():
            raise ExtractionCancelled("用户已取消解析")

    def begin(self, entry: str) -> None:
        self.entries += 1
        self.current = entry
        self.advance(0, force=True)

    def advance(self, size: int, *, force: bool = False) -> None:
        self.bytes_read += size
        self.check()
        if self.progress is None:
            return
        now = time.perf_counter()
        if force or now - self._last_emit >= 0.25:
            self._last_emit = now
            try:
                self.progress({"entry": self.current, "bytes_read": self.bytes_read, "elapsed": now - self.started})
            except Exception:
                # 界面回调异常不能打断解析。
                logger.debug("progress callback failed", exc_info=True)

    def summary(self) -> dict[str, float]:
        stats = {
            "entries": self.entries,
            "bytes_read": self.bytes_read,
            "elapsed_seconds": round(time.perf_counter() - self.started, 3),
        }
        peak = _peak_memory_bytes()
        if peak is not None:
            # 进程级峰值（含界面本身），用于大包性能回归对比，不是单次解析的精确增量。
            stats["peak_memory_mb"] = round(peak / (1024 * 1024), 1)
        return stats


def _peak_memory_bytes() -> Optional[int]:
    """进程峰值内存：Windows 取 PeakWorkingSetSize，其它平台取 ru_maxrss；取不到返回 None。"""
    try:
        if sys.platform == 'win32':
            import ctypes
            from ctypes import wintypes

            class _Counters(ctypes.Structure):
                _fields_ = [
                    ('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD),
                    ('PeakWorkingSetSize', ctypes.c_size_t), ('WorkingSetSize', ctypes.c_size_t),
                    ('QuotaPeakPagedPoolUsage', ctypes.c_size_t), ('QuotaPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t), ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                    ('PagefileUsage', ctypes.c_size_t), ('PeakPagefileUsage', ctypes.c_size_t),
                ]

            # 独立的 WinDLL 实例：设置 argtypes 不影响进程里其它模块共用的 ctypes.windll.kernel32。
            kernel32 = ctypes.WinDLL('kernel32')
            kernel32.GetCurrentProcess.restype = wintypes.HANDLE
            kernel32.K32GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(_Counters), wintypes.DWORD]
            kernel32.K32GetProcessMemoryInfo.restype = wintypes.BOOL
            counters = _Counters()
            counters.cb = ctypes.sizeof(counters)
            if kernel32.K32GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
                return int(counters.PeakWorkingSetSize)
            return None
        import resource
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return int(peak if sys.platform == 'darwin' else peak * 1024)
    except Exception:
        logger.debug("peak memory unavailable", exc_info=True)
        return None


class BatteryExtractor:
    """电池数据提取器 — 逐行流式处理，避免大文件内存爆炸

    GUI 可在调用 extract() 前设置 progress_callback / cancel_event；
    同一实例不要并发调用 extract()。
    """

    _RE_DESIGN_CAPACITY = re.compile(r'batteryFullChargeDesignCapacityUah\s*[:=]\s*(\d+)')
    _RE_CYCLE_COUNT = re.compile(r'batteryCycleCount\s*[:=]\s*(\d+)')
    _RE_FULL_CAPACITY = re.compile(r'batteryFullCharge(?:Uah)?\s*[:=]\s*(\d+)')
    _RE_MARKET_NAME = re.compile(r'\[ro\.product\.marketname\]:\s*\[([^\]]+)\]')
    _RE_MODEL = re.compile(r'\[ro\.product\.model\]:\s*\[([^\]]+)\]')
    _RE_DEVICE_CODENAME = re.compile(r'\[ro\.product\.device\]:\s*\[([^\]]+)\]')
    _RE_BUILD_ID = re.compile(r'\[ro\.build\.id\]:\s*\[([^\]]+)\]')
    _RE_BUILD_INCREMENTAL = re.compile(r'\[ro\.(?:build\.version|mi\.os\.version)\.incremental\]:\s*\[([^\]]+)\]')
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
    # profiles=[..] 在部分 ROM 缺失；connected 也可能写成 "connected: true"。
    _RE_BLUETOOTH_DEVICE = re.compile(
        r'^(.+?)\s+(?:profiles=\[[^\]]*\]\s+)?connected\s*[=:]\s*true\b',
        re.I,
    )
    _MAX_BLUETOOTH_DEVICE_NAME = 64
    _MAX_BLUETOOTH_DEVICES = 10
    _RE_CPU_LOAD = re.compile(r'Load:\s*([\d.]+)\s*/\s*([\d.]+)\s*/\s*([\d.]+)', re.I)
    _RE_CPU_PROCESS = re.compile(
        r'^  ([\d.]+)%\s+\d+/(.+?):\s+([\d.]+)%\s+user\s+\+\s+([\d.]+)%\s+kernel',
        re.I,
    )
    _MAX_CPU_SNAPSHOT_LINES = 400
    _RE_POWER_DRAIN = re.compile(
        r'Capacity:\s*[\d.]+,\s*Computed drain:\s*([\d.]+),\s*actual drain:\s*([\d.]+)',
        re.I,
    )
    # 模块名可含数字和连字符（如 wifi_2g、camera-front）。
    _RE_POWER_COMPONENT = re.compile(
        r'^\s{4}([A-Za-z_][A-Za-z0-9_\-]*):\s*([\d.]+)(?:.*?\bduration:\s*(.+?))?\s*.*$',
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

    # Bound nested-archive disk use; real Xiaomi bugreports stay well below this.
    _MAX_INNER_ZIP_BYTES = 512 * 1024 * 1024
    _MAX_CHARGE_LOG_MEMBER_BYTES = 512 * 1024 * 1024
    _MAX_STATS_LINES = 5000
    _PROGRESS_LINE_INTERVAL = 4096
    # 已知与电池诊断无关的内层包（语音唤醒模型、应用日志），按文件名跳过，报告里只汇总提示一次。
    _SKIP_INNER_ZIP_PATTERNS = (
        re.compile(r'encrypt_voice_trigger', re.I),
        re.compile(r'applog\.zip$', re.I),
    )

    def __init__(self) -> None:
        self.progress_callback: Optional[Callable[[dict], None]] = None
        self.cancel_event = None

    def _copy_zip_entry_bounded(self, zf: zipfile.ZipFile, name: str, destination, run: _ExtractRun) -> None:
        """把内层归档流式解压到已打开的临时文件，峰值内存与归档大小无关。"""
        info = zf.getinfo(name)
        declared = int(getattr(info, 'file_size', 0) or 0)
        if declared > self._MAX_INNER_ZIP_BYTES:
            raise ValueError(f'内层归档过大: {declared} bytes')
        run.begin(name)
        copied = 0
        with zf.open(name) as source:
            while True:
                chunk = source.read(1024 * 1024)
                if not chunk:
                    break
                copied += len(chunk)
                if copied > self._MAX_INNER_ZIP_BYTES:
                    raise ValueError(f'内层归档解压后过大: {copied} bytes')
                destination.write(chunk)
                run.advance(len(chunk))
        destination.flush()

    def extract(self, zip_path: Path, progress: Optional[Callable[[dict], None]] = None, cancel_event=None) -> BatteryInfo:
        info = BatteryInfo()
        parse_errors: list[str] = []
        run = _ExtractRun(
            progress if progress is not None else self.progress_callback,
            cancel_event if cancel_event is not None else self.cancel_event,
        )
        run.check()

        with zipfile.ZipFile(zip_path, 'r') as outer_zip:
            inner_names, skipped = self._find_inner_zips(outer_zip)
            info.skipped_inner_archives.extend(skipped)
            parsed = False

            for inner_name in inner_names:
                # TemporaryFile 在 Windows 上以 O_TEMPORARY 打开，句柄关闭（包括进程被结束）时由系统删除；
                # 在 POSIX 上创建后立即 unlink。两者都不会在临时目录留下内层包副本。
                with tempfile.TemporaryFile(prefix='battery-inner-', suffix='.zip') as scratch:
                    try:
                        self._copy_zip_entry_bounded(outer_zip, inner_name, scratch, run)
                    except ExtractionCancelled:
                        raise
                    except Exception as exc:
                        parse_errors.append(f'内层归档读取失败: {inner_name} ({exc})')
                        continue

                    try:
                        scratch.seek(0)
                        with zipfile.ZipFile(scratch, 'r') as inner_zip:
                            parsed = self._parse_bundle_payload(inner_zip, info, run) or parsed
                    except ExtractionCancelled:
                        raise
                    except zipfile.BadZipFile as exc:
                        parse_errors.append(f'内层归档非法: {inner_name} ({exc})')
                    except Exception as exc:
                        parse_errors.append(f'内层归档解析异常: {inner_name} ({exc})')

            try:
                parsed = self._parse_bundle_payload(outer_zip, info, run) or parsed
            except ExtractionCancelled:
                raise
            except Exception as exc:
                parse_errors.append(f'外层归档解析失败 ({exc})')

            if not parsed:
                error_text = "未找到可解析的诊断文本（缺少 android.hardware.health 或 bugreport）"
                if parse_errors:
                    error_text = f"{error_text}；解析失败明细: {' | '.join(parse_errors)}"
                raise ValueError(error_text)

        self._finalize(info, run)
        info.parse_warnings.extend(parse_errors)
        info.parse_stats = run.summary()
        logger.debug("extract finished: %s", info.parse_stats)
        return info

    @staticmethod
    def _finalize(info: BatteryInfo, run: _ExtractRun) -> None:
        """跨文件合并后的来源决策：通过合理性校验的 BMS 设计容量优于 batterystats 估算，循环次数可由 BMS 补齐。"""
        bms_design = info.bms_design_capacity
        if bms_design is not None and bms_design > 0 and (
            info.design_capacity_source == DESIGN_SOURCE_ESTIMATED or not info.has_design_capacity
        ):
            rejection = _bms_design_rejection(bms_design, info.estimated_capacity)
            if rejection is None:
                info.design_capacity = bms_design
                info.design_capacity_source = DESIGN_SOURCE_BMS
            else:
                info.parse_warnings.append(f'charge_logger 记录的设计容量 {bms_design:.0f} mAh {rejection}，未采用')
        if info.cycle_count is None and info.bms_cycle_count is not None:
            info.cycle_count = info.bms_cycle_count
            info.cycle_count_source = CYCLE_SOURCE_BMS
        if run.health_files == 0 and info.has_design_capacity and info.design_capacity_source in (
            DESIGN_SOURCE_ESTIMATED, DESIGN_SOURCE_BMS,
        ):
            info.parse_warnings.append(f'{_DOWNGRADE_WARNING_PREFIX}「{info.design_capacity_source}」')
        if info.stats_truncated:
            info.parse_warnings.append(
                f'Statistics since last charge 段超过 {BatteryExtractor._MAX_STATS_LINES} 行，已截断，部分统计字段可能缺失'
            )
        if info.skipped_inner_archives:
            info.parse_warnings.append(
                f'已跳过 {len(info.skipped_inner_archives)} 个与电池诊断无关的内层包（语音唤醒模型、应用日志）'
            )

    def _parse_bundle_payload(self, zf: zipfile.ZipFile, info: BatteryInfo, run: Optional[_ExtractRun] = None) -> bool:
        run = run or _ExtractRun()
        parsed = False
        for keyword, parser in (
            ('android.hardware.health', self._parse_health_stream),
            ('bugreport', self._parse_bugreport_stream),
        ):
            for entry in zf.infolist():
                name = entry.filename.lower()
                if entry.is_dir() or not name.endswith('.txt') or keyword not in name:
                    continue
                run.begin(entry.filename)
                try:
                    candidate = deepcopy(info)
                    parser(zf, entry.filename, candidate, run)
                    info.__dict__.update(candidate.__dict__)
                    parsed = True
                    if parser == self._parse_health_stream:
                        run.health_files += 1
                except ExtractionCancelled:
                    raise
                except Exception as exc:
                    info.parse_warnings.append(f'日志解析失败: {entry.filename} ({type(exc).__name__})')

        collector = _BmsCollector()
        unrecognized: list[str] = []
        for entry in zf.infolist():
            if entry.is_dir() or _charge_logger_kind(entry.filename) is None:
                continue
            run.begin(entry.filename)
            entry_collector = _BmsCollector()
            try:
                self._parse_charge_logger_entry(zf, entry.filename, entry_collector, run)
            except ExtractionCancelled:
                raise
            except Exception as exc:
                info.parse_warnings.append(f'charge_logger 解析失败: {entry.filename} ({type(exc).__name__})')
                continue
            if entry_collector.sample_count:
                collector.merge(entry_collector)
            else:
                unrecognized.append(entry.filename)
        if unrecognized:
            more = f' 等 {len(unrecognized)} 个文件' if len(unrecognized) > 1 else ''
            info.parse_warnings.append(f'发现 charge_logger 数据但未识别到 BMS 字段（格式可能不同）: {unrecognized[0]}{more}')
        if collector.sample_count:
            collector.apply(info)
            parsed = True
        return parsed

    @classmethod
    def _find_inner_zips(cls, outer_zip: zipfile.ZipFile) -> tuple[list[str], list[str]]:
        """内层包的解析顺序要与合并语义配套：统计字段由后解析的包覆盖。

        其它包先解析、bugreport 包最后解析，组内沿用旧版的文件名字典序，
        因此文件名带日期的多份 bugreport 中日期最新的一份生效；已知无关包直接跳过。
        """
        candidates = []
        skipped = []
        for name in outer_zip.namelist():
            if not name or name.endswith('/') or not name.lower().endswith('.zip'):
                continue
            base = name.replace('\\', '/').rsplit('/', 1)[-1].lower()
            if 'bugreport' not in base and any(pattern.search(base) for pattern in cls._SKIP_INNER_ZIP_PATTERNS):
                skipped.append(name)
                continue
            candidates.append((1 if 'bugreport' in base else 0, name))
        return [name for _group, name in sorted(candidates)], skipped

    def _parse_health_stream(self, zf: zipfile.ZipFile, filename: str, info: BatteryInfo, run: Optional[_ExtractRun] = None) -> None:
        """读完整个 health 节点（文件很小），同一字段多次出现时取最后一次（最新快照）并提示。"""
        run = run or _ExtractRun()
        seen: dict[str, list[int]] = {'design': [], 'cycle': [], 'full': []}
        patterns = (('design', self._RE_DESIGN_CAPACITY), ('cycle', self._RE_CYCLE_COUNT), ('full', self._RE_FULL_CAPACITY))
        with zf.open(filename) as raw:
            text_stream = io.TextIOWrapper(raw, encoding='utf-8-sig', errors='replace')
            for line in text_stream:
                run.advance(len(line))
                for name, pattern in patterns:
                    m = pattern.search(line)
                    if m:
                        seen[name].append(int(m.group(1)))

        designs = [value for value in seen['design'] if value > 0]
        if designs and (not info.has_design_capacity or info.design_capacity_source != DESIGN_SOURCE_HEALTH):
            info.design_capacity = designs[-1] / 1000
            info.design_capacity_source = DESIGN_SOURCE_HEALTH
        if seen['cycle'] and info.cycle_count is None:
            info.cycle_count = seen['cycle'][-1]
            info.cycle_count_source = CYCLE_SOURCE_HEALTH
        if seen['full'] and info.full_capacity is None:
            info.full_capacity = seen['full'][-1] / 1000

        labels = {'design': 'batteryFullChargeDesignCapacityUah', 'cycle': 'batteryCycleCount', 'full': 'batteryFullCharge'}
        for name, values in seen.items():
            if len(set(values)) > 1:
                info.parse_warnings.append(
                    f'health 节点中 {labels[name]} 出现多个不同值（首次 {values[0]}、末次 {values[-1]}），已采用末次'
                )

    def _parse_bugreport_stream(self, zf: zipfile.ZipFile, filename: str, info: BatteryInfo, run: Optional[_ExtractRun] = None) -> None:
        run = run or _ExtractRun()
        with zf.open(filename) as raw:
            text_stream = io.TextIOWrapper(raw, encoding='utf-8-sig', errors='replace')
            in_stats = False
            in_battery_state = False
            in_power_use = False
            in_wakelock_leaders = False
            in_bluetooth_devices = False
            in_cpu_snapshot = False
            cpu_snapshot_done = False
            cpu_snapshot_lines = 0
            stats_lines: list[str] = []
            stats_overflow = False
            longest_stats = ""
            longest_stats_count = 0
            power_lines: list[str] = []
            wakelock_lines: list[str] = []
            pending_chars = 0
            line_count = 0

            def finish_stats_block() -> None:
                nonlocal longest_stats, longest_stats_count, stats_lines, stats_overflow
                block = '\n'.join(stats_lines)
                if len(stats_lines) >= longest_stats_count:
                    longest_stats, longest_stats_count = block, len(stats_lines)
                if stats_overflow:
                    info.stats_truncated = True
                self._parse_stats_text(block, info)
                stats_lines = []
                stats_overflow = False

            for line in text_stream:
                line_count += 1
                pending_chars += len(line)
                if line_count % self._PROGRESS_LINE_INTERVAL == 0:
                    run.advance(pending_chars)
                    pending_chars = 0
                line = line.rstrip('\n\r')
                stripped = line.strip()
                lowered = stripped.lower()
                # 关键字预筛：只有可能命中的行才进入正则，语义与逐行全量匹配一致。
                if '/' in line or ':"' in line:
                    self._parse_uid_package_line(line, info)
                if 'cellular' in lowered or 'wifi' in lowered:
                    self._parse_connectivity_line(stripped, info)
                if 'bluetooth' in lowered:
                    self._parse_bluetooth_stats_line(stripped, info)

                if info.cpu_load_1m is None and 'load:' in lowered:
                    m = self._RE_CPU_LOAD.search(stripped)
                    if m:
                        info.cpu_load_1m = float(m.group(1))
                        info.cpu_load_5m = float(m.group(2))
                        info.cpu_load_15m = float(m.group(3))

                if stripped.startswith('CPU usage from'):
                    if not cpu_snapshot_done:
                        in_cpu_snapshot = True
                        cpu_snapshot_lines = 0
                    continue
                if in_cpu_snapshot:
                    cpu_snapshot_lines += 1
                    if not stripped or 'TOTAL:' in stripped or cpu_snapshot_lines > self._MAX_CPU_SNAPSHOT_LINES:
                        in_cpu_snapshot = False
                        cpu_snapshot_done = True
                    else:
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

                if '[ro.' in line and self._parse_property_line(line, info):
                    continue

                if info.report_time is None and '== dumpstate' in line:
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
                        in_stats = False
                        finish_stats_block()
                    elif len(stats_lines) < self._MAX_STATS_LINES:
                        stats_lines.append(line)
                    else:
                        stats_overflow = True

            run.advance(pending_chars)
            if in_stats and stats_lines:
                finish_stats_block()
            if longest_stats:
                # 原文展示最完整的一段；各段字段按出现顺序合并（后出现的覆盖）。
                info.statistics = longest_stats
            if in_power_use and power_lines:
                self._parse_power_use_text('\n'.join(power_lines), info)
            if in_wakelock_leaders and wakelock_lines:
                self._parse_wakelock_leaders_text('\n'.join(wakelock_lines), info)

    def _parse_property_line(self, line: str, info: BatteryInfo) -> bool:
        if info.device_name is None:
            m = self._RE_MARKET_NAME.search(line) or self._RE_MODEL.search(line)
            if m:
                info.device_name = m.group(1).strip()
                return True
        for pattern, attr in (
            (self._RE_DEVICE_CODENAME, 'device_codename'),
            (self._RE_BUILD_ID, 'build_id'),
            (self._RE_BUILD_INCREMENTAL, 'build_incremental'),
        ):
            if getattr(info, attr) is None:
                m = pattern.search(line)
                if m:
                    setattr(info, attr, m.group(1).strip())
                    return True
        return False

    def _parse_stats_text(self, text: str, info: BatteryInfo) -> None:
        m = self._RE_ESTIMATED.search(text)
        if m:
            info.estimated_capacity = float(m.group(1))
            if not info.has_design_capacity and math.isfinite(info.estimated_capacity) and info.estimated_capacity > 0:
                info.design_capacity = info.estimated_capacity
                info.design_capacity_source = DESIGN_SOURCE_ESTIMATED

        m = self._RE_LAST_LEARNED.search(text)
        if m:
            info.last_learned_capacity = round(float(m.group(1)))

        m = self._RE_MIN_LEARNED.search(text)
        if m:
            info.min_learned_capacity = round(float(m.group(1)))

        m = self._RE_MAX_LEARNED.search(text)
        if m:
            info.max_learned_capacity = round(float(m.group(1)))

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
        if (
            device and len(device) <= self._MAX_BLUETOOTH_DEVICE_NAME
            and device not in info.bluetooth_connected_devices
            and len(info.bluetooth_connected_devices) < self._MAX_BLUETOOTH_DEVICES
        ):
            info.bluetooth_connected_devices.append(device)

    @staticmethod
    def _remember_cpu_process(info: BatteryInfo, item: CpuProcessUsage) -> None:
        """保留瞬时快照中占用最高的 5 个进程（按 percent 排序，而不是出现顺序）。"""
        if any(existing.name == item.name for existing in info.top_cpu_processes):
            return
        info.top_cpu_processes.append(item)
        info.top_cpu_processes.sort(key=lambda process: process.percent, reverse=True)
        del info.top_cpu_processes[5:]

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
        # 过滤 "0.0.0.0/0" 这类路由/IP 行误判出的伪包名。
        if not _RE_PACKAGE_NAME.match(package):
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

    def _parse_charge_logger_entry(self, zf: zipfile.ZipFile, filename: str, collector: "_BmsCollector", run: _ExtractRun) -> None:
        kind = _charge_logger_kind(filename)
        with zf.open(filename) as raw:
            if kind == 'tar':
                # 流式读取：tar 可能有几十 MB，不整包载入内存。
                with tarfile.open(fileobj=raw, mode='r|*') as archive:
                    for member in archive:
                        run.check()
                        if not member.isfile() or not _is_charge_log_text(member.name):
                            continue
                        if member.size > self._MAX_CHARGE_LOG_MEMBER_BYTES:
                            continue
                        stream = archive.extractfile(member)
                        if stream is None:
                            continue
                        # tar 流式成员不可 seek，TextIOWrapper 会报错；按字节行解码即可。
                        collector.feed(_iter_text_lines(stream), run)
            else:
                collector.feed(_iter_text_lines(raw), run)


# ── charge_logger（BMS）解析 ───────────────────────────────────────────────

# 列名/键名 → 规范字段。未用真实多机型样本验证，因此只接受明确的 BMS 字段名。
_BMS_KEY_ALIASES = {
    'bms_chg_full': 'full', 'chg_full': 'full', 'charge_full': 'full', 'bms_charge_full': 'full',
    'bms_chg_full_design': 'design', 'chg_full_design': 'design', 'charge_full_design': 'design',
    'bms_charge_full_design': 'design',
    'bms_cycle_count': 'cycle', 'cycle_count': 'cycle', 'battery_cycle_count': 'cycle',
    'battery_soh': 'soh', 'bms_soh': 'soh', 'soh': 'soh',
    'usb_real_type': 'usb_type', 'real_type': 'usb_type',
    'pd_verified': 'pd_verified', 'pd_verifed': 'pd_verified',
    'batt_temp': 'temp', 'battery_temp': 'temp', 'bat_temp': 'temp', 'tbat': 'temp', 'temp': 'temp',
    'battery_temperature': 'temp',
    'time': 'time', 'timestamp': 'time', 'date': 'time', 'datetime': 'time', 'local_time': 'time',
    'systime': 'time',
}
_BMS_VALUE_FIELDS = ('full', 'design', 'cycle', 'soh')
_RE_KEY_VALUE = re.compile(r'([A-Za-z_][A-Za-z0-9_]*)\s*[=:]\s*([^\s,;]+)')
_RE_DATE = re.compile(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})')
_MAX_BMS_HISTORY_DAYS = 400


def _charge_logger_kind(filename: str) -> Optional[str]:
    lowered = filename.lower().replace('\\', '/')
    if 'charge_logger' not in lowered and 'chargelogger' not in lowered:
        return None
    if lowered.endswith(('.tar', '.tar.gz', '.tgz')):
        return 'tar'
    if lowered.endswith(('.csv', '.txt', '.log')):
        return 'text'
    return None


def _iter_text_lines(stream):
    first = True
    for raw in stream:
        line = raw.decode('utf-8', errors='replace')
        if first:
            line = line.lstrip('﻿')
            first = False
        yield line


def _is_charge_log_text(name: str) -> bool:
    base = name.replace('\\', '/').rsplit('/', 1)[-1].lower()
    return base.endswith(('.csv', '.txt', '.log')) or '.' not in base


def _to_number(text: Optional[str]) -> Optional[float]:
    if text is None:
        return None
    try:
        value = float(text.strip().strip('"'))
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def _capacity_mah(value: Optional[float]) -> Optional[float]:
    if value is None or value <= 0:
        return None
    if value > 100_000:  # µAh
        value /= 1000
    return value if 100 <= value <= 100_000 else None


def _raw_temperature(value: Optional[float]) -> Optional[float]:
    # 原始读数先按 ℃ 或 0.1 ℃ 两种单位都可能的范围收集，单位在 apply() 时按整批数据决定。
    return value if value is not None and -400 <= value <= 1000 else None


# 电池温度的合理范围（℃）；超出的多为传感器占位值（如 -40、999），不参与统计。
_PLAUSIBLE_BATTERY_TEMPERATURE_C = (-30.0, 90.0)


def _temperature_summary(buckets: dict[int, int]) -> Optional[tuple[float, float]]:
    """(最高温度 ℃, 高于 40 ℃ 的占比 %)。整批读数中位数超过 60 视为 0.1 ℃ 单位（常温 25–45 ℃ 记作 250–450）。"""
    total = sum(buckets.values())
    if not total:
        return None
    seen, median = 0, 0
    for bucket in sorted(buckets):
        seen += buckets[bucket]
        if seen * 2 >= total:
            median = bucket
            break
    divisor = 100 if median / 10 > 60 else 10
    low, high = _PLAUSIBLE_BATTERY_TEMPERATURE_C
    valid = {bucket / divisor: count for bucket, count in buckets.items() if low <= bucket / divisor <= high}
    if not valid:
        return None
    hot = sum(count for celsius, count in valid.items() if celsius > 40)
    return max(valid), hot / sum(valid.values()) * 100


def _soh_percent(value: Optional[float]) -> Optional[float]:
    # 部分机型以小数记录（0.95 = 95%）；低于 10% 视为无效占位值。
    if value is None or value <= 0:
        return None
    if value <= 1.5:
        value *= 100
    return value if 10 <= value <= 100 else None


# BMS 设计容量超出常见手机电池范围，或与 batterystats 估算相差 30% 以上时，多半是单位或字段含义不同。
_BMS_DESIGN_RANGE_MAH = (1000.0, 20000.0)
_BMS_DESIGN_MAX_DEVIATION = 0.3


def _bms_design_rejection(design: float, estimate: Optional[float]) -> Optional[str]:
    low, high = _BMS_DESIGN_RANGE_MAH
    if not low <= design <= high:
        return f'不在 {low:.0f}–{high:.0f} mAh 的合理范围内'
    if estimate is not None and estimate > 0 and abs(design - estimate) / estimate > _BMS_DESIGN_MAX_DEVIATION:
        return f'与 batterystats 估算 {estimate:.0f} mAh 相差超过 {_BMS_DESIGN_MAX_DEVIATION:.0%}，可能是单位或字段含义不同'
    return None


def _day_from_text(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    m = _RE_DATE.search(text)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        except ValueError:
            return None
    stripped = text.strip().strip('"')
    if stripped.isdigit() and len(stripped) in (10, 13):
        seconds = int(stripped) / (1000 if len(stripped) == 13 else 1)
        try:
            return datetime.fromtimestamp(seconds).date().isoformat()
        except (OverflowError, OSError, ValueError):
            return None
    return None


class _BmsCollector:
    """把 charge_logger 行（CSV 表头或 key=value）归并为最新快照、按日趋势和温度统计。"""

    def __init__(self) -> None:
        self.sample_count = 0
        self.sequence = 0
        self.latest: dict[str, tuple[tuple, float]] = {}
        self.days: dict[str, dict[str, float]] = {}
        # 温度按 0.1 个原始单位分桶计数：内存有界，apply() 时再按整批中位数判断单位。
        self.temperature_buckets: dict[int, int] = {}
        self.usb_type: Optional[tuple[tuple, str]] = None
        self.pd_verified: Optional[tuple[tuple, bool]] = None

    def feed(self, lines, run: _ExtractRun) -> None:
        header: Optional[list[str]] = None
        delimiter = ','
        pending = 0
        for count, line in enumerate(lines, 1):
            pending += len(line)
            if count % 4096 == 0:
                run.advance(pending)
                pending = 0
            stripped = line.strip()
            if not stripped:
                continue
            detected = self._detect_header(stripped)
            if detected is not None:
                header, delimiter = detected
                continue
            if header is not None and delimiter in stripped:
                values = next(csv.reader([stripped], delimiter=delimiter), [])
                # 表头模式下该行没有任何 BMS 字段（例如混排的 key=value 行）时，再按 key=value 解析一次。
                if len(values) >= min(len(header), 2) and self._consume(dict(zip(header, values)), stripped):
                    continue
            pairs = _RE_KEY_VALUE.findall(stripped)
            if pairs:
                self._consume({key.lower(): value for key, value in pairs}, stripped)
        run.advance(pending)

    @staticmethod
    def _detect_header(line: str) -> Optional[tuple[list[str], str]]:
        for delimiter in (',', '\t', ';'):
            if delimiter not in line:
                continue
            tokens = [token.strip().strip('"').lower() for token in line.split(delimiter)]
            if any(_BMS_KEY_ALIASES.get(token) in _BMS_VALUE_FIELDS for token in tokens) and not any(
                _to_number(token) is not None for token in tokens
            ):
                return tokens, delimiter
        return None

    def _consume(self, row: dict[str, str], raw_line: str) -> bool:
        """记录一行 BMS 数据；该行没有任何 BMS 数值字段时返回 False。"""
        fields: dict[str, str] = {}
        for key, value in row.items():
            canonical = _BMS_KEY_ALIASES.get(str(key).strip().lower())
            if canonical and canonical not in fields and value is not None:
                fields[canonical] = str(value).strip()
        full = _capacity_mah(_to_number(fields.get('full')))
        design = _capacity_mah(_to_number(fields.get('design')))
        cycle_value = _to_number(fields.get('cycle'))
        cycle = int(cycle_value) if cycle_value is not None and 0 <= cycle_value < 100_000 else None
        soh = _soh_percent(_to_number(fields.get('soh')))
        if full is None and design is None and cycle is None and soh is None:
            return False
        self.sequence += 1
        self.sample_count += 1
        day = _day_from_text(fields.get('time')) or _day_from_text(raw_line)
        order = (day or '', self.sequence)
        values = {'full': full, 'design': design, 'cycle': cycle, 'soh': soh}
        for name, value in values.items():
            if value is None:
                continue
            previous = self.latest.get(name)
            if previous is None or order >= previous[0]:
                self.latest[name] = (order, value)
            if day:
                self.days.setdefault(day, {})[name] = value
        temperature = _raw_temperature(_to_number(fields.get('temp')))
        if temperature is not None:
            bucket = round(temperature * 10)
            self.temperature_buckets[bucket] = self.temperature_buckets.get(bucket, 0) + 1
        usb_type = fields.get('usb_type')
        if usb_type and usb_type.upper() not in ('UNKNOWN', '0', 'NONE', 'NULL'):
            if self.usb_type is None or order >= self.usb_type[0]:
                self.usb_type = (order, usb_type)
        verified = fields.get('pd_verified')
        if verified is not None and verified.lower() in ('0', '1', 'true', 'false'):
            if self.pd_verified is None or order >= self.pd_verified[0]:
                self.pd_verified = (order, verified.lower() in ('1', 'true'))
        return True

    def merge(self, other: "_BmsCollector") -> None:
        offset = self.sequence
        for name, (order, value) in other.latest.items():
            shifted = (order[0], order[1] + offset)
            previous = self.latest.get(name)
            if previous is None or shifted >= previous[0]:
                self.latest[name] = (shifted, value)
        for day, values in other.days.items():
            self.days.setdefault(day, {}).update(values)
        self.sequence += other.sequence
        self.sample_count += other.sample_count
        for bucket, count in other.temperature_buckets.items():
            self.temperature_buckets[bucket] = self.temperature_buckets.get(bucket, 0) + count
        for attr in ('usb_type', 'pd_verified'):
            theirs = getattr(other, attr)
            if theirs is None:
                continue
            shifted = ((theirs[0][0], theirs[0][1] + offset), theirs[1])
            mine = getattr(self, attr)
            if mine is None or shifted[0] >= mine[0]:
                setattr(self, attr, shifted)

    def apply(self, info: BatteryInfo) -> None:
        for attr, name in (
            ('bms_full_capacity', 'full'), ('bms_design_capacity', 'design'),
            ('bms_cycle_count', 'cycle'), ('bms_soh', 'soh'),
        ):
            item = self.latest.get(name)
            if item is not None:
                setattr(info, attr, item[1])
        info.bms_sample_count += self.sample_count
        history = [
            BmsDailyPoint(
                day=day,
                full_mah=values.get('full'),
                soh=values.get('soh'),
                cycle_count=int(values['cycle']) if values.get('cycle') is not None else None,
            )
            for day, values in sorted(self.days.items())
        ]
        if history:
            info.bms_history = history[-_MAX_BMS_HISTORY_DAYS:]
        temperature = _temperature_summary(self.temperature_buckets)
        if temperature is not None:
            info.bms_max_temperature_c, info.bms_high_temperature_share = temperature
        if self.usb_type is not None:
            info.charge_protocol = self.usb_type[1]
        if self.pd_verified is not None:
            info.charge_pd_verified = self.pd_verified[1]


# ── 报告导出（JSON / 批量汇总 / 脱敏 / 指纹）────────────────────────────────

_BATCH_COLUMNS = ("文件", "型号", "健康度", "证据强度", "设计容量来源", "循环次数", "BMS SoH", "统计窗口", "状态")


def file_fingerprint(path: Path) -> dict:
    """报告指纹：文件名、字节数、SHA256 前 12 位与解析器版本，便于问题回溯和两份报告对比。"""
    path = Path(path)
    digest = hashlib.sha256()
    size = 0
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
            size += len(chunk)
    return {"name": path.name, "bytes": size, "sha256_12": digest.hexdigest()[:12], "parser_build": PARSER_BUILD}


def format_fingerprint(fingerprint: Optional[dict]) -> Optional[str]:
    if not fingerprint:
        return None
    size_mb = fingerprint["bytes"] / (1024 * 1024)
    return (
        f"{fingerprint['name']} · {size_mb:.1f} MB · SHA256 {fingerprint['sha256_12']} · "
        f"解析器 {fingerprint['parser_build']}"
    )


def _redact_wakelock_name(name: str) -> str:
    parts = name.split(maxsplit=1)
    return f"{parts[0]} [标签已隐藏]" if len(parts) > 1 else name


# 三段及以上的点分标识（com.example.app）视为包名；告警里的路径和归档文件名一并隐藏。
_RE_PACKAGE_TOKEN = re.compile(r'\b[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+){2,}\b')
_RE_WARNING_PATH = re.compile(
    r'[^\s:：()（）|,，]*[\\/][^\s:：()（）|,，]*|[^\s:：()（）|,，]+\.(?:zip|txt|tar|tgz|gz|csv|log)\b', re.I
)


def _redact_package_tokens(text: str) -> str:
    return _RE_PACKAGE_TOKEN.sub('[包名已隐藏]', text)


def _redact_warning(text: str) -> str:
    return _RE_WARNING_PATH.sub('[文件名已隐藏]', text)


def apply_manual_design_capacity(info: BatteryInfo, capacity: float) -> None:
    """用户手填设计容量：覆盖自动检测值；自动来源的“已降级使用估算值”告警随之失效，一并移除。"""
    info.design_capacity = capacity
    info.design_capacity_auto = False
    info.design_capacity_source = DESIGN_SOURCE_MANUAL
    info.parse_warnings = [item for item in info.parse_warnings if not item.startswith(_DOWNGRADE_WARNING_PREFIX)]


def redacted_fingerprint(fingerprint: Optional[dict], label: str = "文件1") -> Optional[dict]:
    """脱敏指纹：文件名可能含姓名或目录名，改为序号；保留大小与 SHA256 前缀供本人核对。"""
    if not fingerprint:
        return fingerprint
    return {**fingerprint, "name": label}


def redacted_copy(info: BatteryInfo) -> BatteryInfo:
    """对外分享用副本：隐藏蓝牙设备名、应用包名、进程名、唤醒锁标签（可能含账号）、告警中的文件名与原始统计段。"""
    copy = deepcopy(info)
    copy.bluetooth_connected_devices = [f"蓝牙设备{index}" for index, _ in enumerate(info.bluetooth_connected_devices, 1)]
    aliases = {package: f"应用#{index}" for index, package in enumerate(sorted(set(info.uid_packages.values())), 1)}
    copy.uid_packages = {uid: aliases[package] for uid, package in info.uid_packages.items()}
    copy.top_cpu_processes = [
        dataclass_replace(item, name=f"进程#{index}") for index, item in enumerate(info.top_cpu_processes, 1)
    ]
    copy.partial_wakelocks = [dataclass_replace(item, name=_redact_wakelock_name(item.name)) for item in info.partial_wakelocks]
    copy.kernel_wakelocks = [
        dataclass_replace(item, name=_redact_package_tokens(item.name)) for item in info.kernel_wakelocks
    ]
    copy.parse_warnings = [_redact_warning(item) for item in info.parse_warnings]
    copy.skipped_inner_archives = [f"内层包{index}" for index, _ in enumerate(info.skipped_inner_archives, 1)]
    copy.statistics = None
    return copy


def _rounded(value: Optional[float], digits: int) -> Optional[float]:
    return round(value, digits) if value is not None else None


def build_report_payload(info: BatteryInfo, fingerprint: Optional[dict] = None) -> dict:
    """机器可读报告：数值 + 来源 + 置信度 + 窗口质量，供批量对比和外部审阅。"""
    level, reasons = info.health_evidence
    confidence = info.design_capacity_confidence
    band = info.health_percentage_band
    sources = info.field_sources
    return {
        "schema": 1,
        "parser_build": PARSER_BUILD,
        "source": fingerprint,
        "device": {
            "name": info.device_name,
            "codename": info.device_codename,
            "build_id": info.build_id,
            "build_incremental": info.build_incremental,
            "report_time": info.report_time,
        },
        "health": {
            "percentage": _rounded(info.health_percentage, 2),
            "band": [round(band[0], 2), round(band[1], 2)] if band else None,
            "rating": info.rating_text,
            "evidence_level": level if info.health_percentage is not None else None,
            "evidence_reasons": reasons,
            "design_capacity_mah": info.design_capacity if info.has_design_capacity else None,
            "design_capacity_source": sources.get("design_capacity"),
            "design_capacity_confidence": confidence[0] if confidence else None,
            "current_capacity_mah": info.current_capacity,
            "current_capacity_source": sources.get("current_capacity"),
            "system_health": info.health_text,
            "learned_capacity_mah": {
                "last": info.last_learned_capacity,
                "min": info.min_learned_capacity,
                "max": info.max_learned_capacity,
            },
            "learned_capacity_note": info.learned_capacity_note,
        },
        "cycle_count": {"value": info.cycle_count, "source": sources.get("cycle_count")},
        "bms": {
            "soh": info.bms_soh,
            "full_capacity_mah": info.bms_full_capacity,
            "design_capacity_mah": info.bms_design_capacity,
            "cycle_count": info.bms_cycle_count,
            "samples": info.bms_sample_count,
            "soh_gap_points": _rounded(info.bms_soh_gap, 1),
            "conflict": info.has_soh_conflict,
            "history": [
                {"day": point.day, "full_mah": point.full_mah, "soh": point.soh, "cycle_count": point.cycle_count}
                for point in info.bms_history
            ],
            "trend_notes": info.bms_trend_notes,
            "charge_protocol": info.charge_protocol,
            "pd_verified": info.charge_pd_verified,
            "max_temperature_c": info.bms_max_temperature_c,
            "high_temperature_share": _rounded(info.bms_high_temperature_share, 1),
        },
        "window_quality": info.window_quality,
        "summary": info.summary_lines,
        "root_causes": [{"cause": cause, "action": action} for cause, action in info.root_causes],
        "diagnostics": info.usage_diagnostics,
        "field_sources": sources,
        "parse_warnings": list(info.parse_warnings),
        "skipped_inner_archives": list(info.skipped_inner_archives),
        "parse_stats": dict(info.parse_stats),
    }


def batch_summary_rows(results) -> list[list[str]]:
    """results: [(文件名, BatteryInfo | None, 错误文本 | None)] → 汇总表行。"""
    rows = []
    for name, info, error in results:
        if info is None:
            rows.append([name, "", "", "", "", "", "", "", f"失败：{error}"])
            continue
        pct = info.health_percentage
        rows.append([
            name,
            info.device_name or "",
            f"{pct:.2f}%" if pct is not None else "无法计算",
            info.health_evidence[0] if pct is not None else "",
            info.field_sources.get("design_capacity", "未检测到"),
            str(info.cycle_count) if info.cycle_count is not None else "",
            f"{info.bms_soh:.0f}%" if info.bms_soh is not None else "",
            "、".join(info.window_quality) or "—",
            "完整" if pct is not None else "部分数据",
        ])
    return rows


def format_batch_summary(results) -> str:
    rows = batch_summary_rows(results)
    lines = [f"批量汇总（共 {len(rows)} 份）", " | ".join(_BATCH_COLUMNS)]
    lines.extend(" | ".join(value or "—" for value in row) for row in rows)
    return "\n".join(lines)


_CSV_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _csv_safe(value: str) -> str:
    # 以公式字符开头的单元格（例如文件名）加前导单引号，防止 Excel 当作公式执行。
    return f"'{value}" if value.startswith(_CSV_FORMULA_PREFIXES) else value


def format_batch_summary_csv(results) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(_BATCH_COLUMNS)
    writer.writerows([_csv_safe(cell) for cell in row] for row in batch_summary_rows(results))
    return buffer.getvalue()
