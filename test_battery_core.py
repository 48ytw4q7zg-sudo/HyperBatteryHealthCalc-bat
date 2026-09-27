# -*- coding: utf-8 -*-
"""Regression tests for battery extraction and Web/Python parity."""
from __future__ import annotations

import contextlib
import io
import json
import re
import sys
import tarfile
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
BAT_DIR = ROOT / "HyperBatteryHealthCalc-bat"
sys.path.insert(0, str(BAT_DIR))

import battery_core  # noqa: E402
from battery_core import (  # noqa: E402
    CYCLE_SOURCE_BMS,
    DESIGN_SOURCE_BMS,
    DESIGN_SOURCE_ESTIMATED,
    DESIGN_SOURCE_HEALTH,
    SOFT_REPLACEMENT_RATING,
    BatteryExtractor,
    BatteryInfo,
    ExtractionCancelled,
    batch_summary_rows,
    build_report_payload,
    format_batch_summary_csv,
    get_rating_color,
    get_rating_text,
    redacted_copy,
)


class BatteryCoreTests(unittest.TestCase):
    def _build_nested_report(self, path: Path) -> None:
        inner_buffer = io.BytesIO()
        with zipfile.ZipFile(inner_buffer, "w") as inner:
            inner.writestr(
                "dump/android.hardware.health-service.txt",
                "\n".join([
                    "batteryFullChargeDesignCapacityUah: 5000000",
                    "batteryCycleCount: 123",
                    "batteryFullChargeUah: 4625000",
                ]),
            )
            inner.writestr(
                "dump/bugreport-demo.txt",
                "\n".join([
                    "[ro.product.marketname]: [Xiaomi Test Phone]",
                    "== dumpstate: 2026-06-26 12:34:56",
                    "Statistics since last charge:",
                    "  Estimated battery capacity: 4680.5 mAh",
                    "  Last learned battery capacity: 4612.9 mAh",
                    "  Min learned battery capacity: 4599.8 mAh",
                    "  Max learned battery capacity: 4701.2 mAh",
                    "  Screen brightnesses:",
                    "    dark 10m 0s (20.0%)",
                    "    bright 40m 0s (80.0%)",
                    "Estimated power use (mAh):",
                    "  Capacity: 5000, Computed drain: 123.4, actual drain: 120.0",
                    "  Global",
                    "    screen: 10.0 apps: 10.0 duration: 30m 0s",
                    "    cpu: 30.0 apps: 29.0 duration: 1h 0m 0s",
                    "    mobile_radio: 40.0 apps: 39.0",
                    "    wakelock: 5.0 apps: 5.0 duration: 30m 0s",
                    "  UID u0a123: 50.5 fg: 20 (10m) bg: 30 (20m)",
                    "  UID 1000: 25 bg: 25",
                    "    * com.example.music/u0a123 exemption=DENIED",
                    "    * android/1000 exemption=ALLOWLISTED_PACKAGE",
                    "All kernel wake locks:",
                    "  Kernel Wake lock PowerManagerService.WakeLocks: 1h 2m 3s 4ms (5 times) realtime",
                    "  Kernel Wake lock rmnet_ctl: 12m 28s 960ms (5304 times) realtime",
                    "All partial wake locks:",
                    "  Wake lock u0a288 AudioIn: 3h 48m 4s 662ms (2 times) realtime",
                    "BluetoothController state:",
                    "  mConnectionState=CONNECTED",
                    "  Bluetooth Devices:",
                    "    Xiaomi Smart Band 10 profiles=[4] connected=true active[A2DP]=false active[HEADSET]=false",
                    "    HUAWEI FreeClip profiles=[1,2,6] connected=true active[A2DP]=true active[HEADSET]=true",
                    "CONNECTIVITY POWER SUMMARY START",
                    "  Cellular Statistics:",
                    "     Cellular kernel active time: 1h 2m 3s 4ms (65.5%)",
                    "     Cellular Rx time:     40m 0s (65.0%)",
                    "     Cellular data received: 1.25GB",
                    "     Cellular data sent: 42.5MB",
                    "  Wifi Statistics:",
                    "     WiFi Scan time:  12s 500ms (0.0%)",
                    "     Wifi data received: 2048B",
                    "     Wifi data sent: 1.5KB",
                    "CONNECTIVITY POWER SUMMARY END",
                    "Bluetooth total received: 221.39KB, sent: 170.95KB",
                    "Bluetooth scan time: 2h 19m 28s 818ms",
                    "   Bluetooth Rx time:     29m 19s 483ms (5.1%)",
                    "   Bluetooth Tx time:     6m 33s 839ms (1.2%)",
                    "   Bluetooth Battery drain: 69.9mAh",
                    "Load: 15.79 / 15.85 / 16.28",
                    "CPU usage from 54711ms to 26109ms ago:",
                    "  9.9% 19856/com.kaoshibaodian.app: 6.5% user + 3.4% kernel / faults: 6491 minor",
                    "    2.7% 17920/RenderThread: 2.2% user + 0.4% kernel",
                    "  4.2% 2045/surfaceflinger: 3.1% user + 1.1% kernel",
                    "",
                ]),
            )

        with zipfile.ZipFile(path, "w") as outer:
            outer.writestr("nested-diagnostic.zip", inner_buffer.getvalue())

    def test_extractor_handles_nested_zip_and_float_learned_capacity(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "report.zip"
            self._build_nested_report(report_path)

            info = BatteryExtractor().extract(report_path)

        self.assertEqual(info.device_name, "Xiaomi Test Phone")
        self.assertEqual(info.report_time, "2026-06-26 12:34:56")
        self.assertEqual(info.design_capacity, 5000)
        self.assertEqual(info.design_capacity_source, "hardware health 设计容量")
        self.assertEqual(info.cycle_count, 123)
        self.assertEqual(info.full_capacity, 4625)
        self.assertEqual(info.estimated_capacity, 4680.5)
        self.assertEqual(info.last_learned_capacity, 4613)
        self.assertEqual(info.current_capacity, 4600)
        self.assertAlmostEqual(info.health_percentage, 92.0, places=2)
        self.assertAlmostEqual(info.computed_drain_mah, 123.4, places=2)
        self.assertAlmostEqual(info.actual_drain_mah, 120.0, places=2)
        self.assertEqual(
            [(item.name, item.mah) for item in info.power_components[:3]],
            [("mobile_radio", 40.0), ("cpu", 30.0), ("screen", 10.0)],
        )
        self.assertEqual(info.top_uid_power[0].uid, "u0a123")
        self.assertAlmostEqual(info.top_uid_power[0].mah, 50.5, places=2)
        self.assertEqual(info.uid_packages["u0a123"], "com.example.music")
        self.assertEqual(info.uid_packages["1000"], "android")
        self.assertEqual(info.kernel_wakelocks[0].name, "PowerManagerService.WakeLocks")
        self.assertAlmostEqual(info.kernel_wakelocks[0].seconds, 3723.004, places=3)
        self.assertEqual(info.partial_wakelocks[0].name, "u0a288 AudioIn")
        self.assertAlmostEqual(info.partial_wakelocks[0].seconds, 13684.662, places=3)
        self.assertEqual(info.bluetooth_connected_devices, ["Xiaomi Smart Band 10", "HUAWEI FreeClip"])
        self.assertAlmostEqual(info.bluetooth_drain_mah, 69.9, places=2)
        self.assertAlmostEqual(info.bluetooth_scan_seconds, 8368.818, places=3)
        self.assertEqual(info.cellular_received_bytes, 1342177280)
        self.assertEqual(info.cellular_sent_bytes, 44564480)
        self.assertEqual(info.wifi_received_bytes, 2048)
        self.assertEqual(info.wifi_sent_bytes, 1536)
        self.assertAlmostEqual(info.cellular_kernel_active_seconds, 3723.004, places=3)
        self.assertAlmostEqual(info.wifi_scan_seconds, 12.5, places=3)
        self.assertAlmostEqual(info.cpu_load_1m, 15.79, places=2)
        self.assertEqual(info.top_cpu_processes[0].name, "com.kaoshibaodian.app")
        self.assertAlmostEqual(info.top_cpu_processes[0].percent, 9.9, places=2)
        self.assertEqual(info.screen_brightnesses[0].name, "bright")
        self.assertAlmostEqual(info.screen_brightnesses[0].seconds, 2400.0, places=2)
        self.assertAlmostEqual(info.screen_brightnesses[0].percent, 80.0, places=2)
        diagnostics = "\n".join(info.usage_diagnostics)
        self.assertIn("耗电构成前三", diagnostics)
        self.assertIn("最高耗电 UID", diagnostics)
        self.assertIn("前台 20.0 mAh / 后台 30.0 mAh", diagnostics)
        self.assertIn("亮度分布：高亮(bright) 80.0%", diagnostics)
        self.assertIn("应用部分唤醒锁最长", diagnostics)
        self.assertIn("蓝牙耗电 69.9 mAh", diagnostics)
        self.assertIn("移动网络流量 1.25 GB 下行 / 42.50 MB 上行", diagnostics)
        self.assertIn("当前 CPU 负载 15.79/15.85/16.28", diagnostics)

    def test_real_xiaomi15pro_bugreport_extracts_snapshot_and_health(self):
        report_path = (
            BAT_DIR / "input" / "bugreport-2026-06-23-100941.zip"
        )
        if not report_path.exists():
            self.skipTest("real Xiaomi bugreport fixture not present")

        info = BatteryExtractor().extract(report_path)

        self.assertEqual(info.device_name, "Xiaomi 15 Pro")
        self.assertEqual(info.report_time, "2026-06-23 10:09:41")
        self.assertEqual(info.design_capacity, 6100)
        self.assertEqual(info.design_capacity_source, "batterystats 估算容量")
        self.assertEqual(info.current_capacity, 4760)
        self.assertEqual(info.current_capacity_source, "batterystats 最小学习容量")
        self.assertEqual(info.charge_counter, 4757)
        self.assertEqual(info.battery_level, 100)
        self.assertEqual(info.battery_scale, 100)
        self.assertEqual(info.status_text, "已充满")
        self.assertEqual(info.health_text, "良好")
        self.assertEqual(info.voltage_mv, 4377)
        self.assertEqual(info.temperature_c, 34.5)
        self.assertEqual(info.temperature_text, "正常")
        self.assertEqual(info.technology, "Li-poly")
        self.assertEqual(info.power_source_text, "AC 电源")
        self.assertEqual(info.max_charging_current_ma, 1600)
        self.assertEqual(info.max_charging_voltage_mv, 5000)
        self.assertAlmostEqual(info.max_charging_power_w, 8.0, places=2)
        self.assertAlmostEqual(info.health_percentage, 78.03, places=2)
        self.assertAlmostEqual(info.time_on_battery_seconds, 34208.182, places=3)
        self.assertAlmostEqual(info.screen_on_seconds, 8462.718, places=3)
        self.assertAlmostEqual(info.screen_off_seconds, 25745.464, places=3)
        self.assertEqual(info.total_discharge_mah, 3102)
        self.assertEqual(info.screen_on_discharge_mah, 2123)
        self.assertEqual(info.screen_off_discharge_mah, 979)
        self.assertAlmostEqual(info.computed_drain_mah, 2829, places=2)
        self.assertAlmostEqual(info.actual_drain_mah, 2829, places=2)
        self.assertEqual(info.power_components[0].name, "cpu")
        self.assertAlmostEqual(info.power_components[0].mah, 1897, places=2)
        self.assertEqual(info.power_components[1].name, "mobile_radio")
        self.assertAlmostEqual(info.power_components[1].mah, 1713, places=2)
        self.assertEqual(info.top_uid_power[0].uid, "u0a290")
        self.assertAlmostEqual(info.top_uid_power[0].mah, 554, places=2)
        self.assertEqual(info.uid_packages["u0a290"], "com.tencent.qqmusic")
        self.assertEqual(info.uid_packages["u0a377"], "com.tencent.tmgp.supercell.clashofclans")
        self.assertEqual(info.uid_packages["u0a288"], "com.mi.health")
        self.assertEqual(info.bluetooth_connected_devices[:2], ["Xiaomi Smart Band 10 00DA", "HUAWEI FreeClip"])
        self.assertAlmostEqual(info.bluetooth_drain_mah, 69.9, places=2)
        self.assertAlmostEqual(info.bluetooth_scan_seconds, 8368.818, places=3)
        self.assertEqual(info.cellular_received_bytes, 1256277934)
        self.assertEqual(info.cellular_sent_bytes, 62662902)
        self.assertEqual(info.wifi_received_bytes, 0)
        self.assertEqual(info.wifi_sent_bytes, 0)
        self.assertAlmostEqual(info.cellular_kernel_active_seconds, 22419.266, places=3)
        self.assertAlmostEqual(info.cellular_rx_seconds, 22243.863, places=3)
        self.assertAlmostEqual(info.cpu_load_1m, 15.79, places=2)
        self.assertEqual(info.top_cpu_processes[0].name, "com.kaoshibaodian.app")
        self.assertAlmostEqual(info.top_cpu_processes[0].percent, 9.9, places=2)
        self.assertEqual(info.kernel_wakelocks[0].name, "PowerManagerService.WakeLocks")
        self.assertEqual(info.partial_wakelocks[0].name, "u0a288 AudioIn")
        self.assertAlmostEqual(info.screen_on_discharge_share, 68.44, places=2)
        self.assertAlmostEqual(info.screen_on_drain_ma, 903.11, places=2)
        self.assertAlmostEqual(info.screen_off_drain_ma, 136.89, places=2)
        self.assertEqual(info.connectivity_changes, 259)
        self.assertAlmostEqual(info.partial_wakelock_seconds, 16269.485, places=3)
        self.assertEqual(info.screen_brightnesses[0].name, "dark")
        self.assertAlmostEqual(info.screen_brightnesses[0].seconds, 6952.787, places=3)
        self.assertAlmostEqual(info.screen_brightnesses[0].percent, 82.2, places=1)
        diagnostics = "\n".join(info.usage_diagnostics)
        self.assertIn("健康度 78.03%", diagnostics)
        self.assertIn("亮屏耗电占比 68.4%", diagnostics)
        self.assertIn("亮度分布：低亮度(dark) 82.2%", diagnostics)
        self.assertIn("本次亮屏主要处于低亮度", diagnostics)
        self.assertIn("息屏平均耗电约 136.9 mA", diagnostics)
        self.assertIn("屏幕 Doze 耗电 24.0 mAh，占总耗电 0.8%", diagnostics)
        self.assertIn("设备深度 Doze 耗电 686.0 mAh，占总耗电 22.1%", diagnostics)
        self.assertIn("部分唤醒锁约 4小时31分钟", diagnostics)
        self.assertIn("耗电构成前三：cpu 1897.0 mAh、mobile_radio 1713.0 mAh、audio 207.0 mAh", diagnostics)
        self.assertIn("最高耗电 UID：u0a290(com.tencent.qqmusic) 554.0 mAh，占总耗电 17.9%", diagnostics)
        self.assertIn("前台服务 468.0 mAh", diagnostics)
        self.assertIn("u0a377(com.tencent.tmgp.supercell.clashofclans) 377.0 mAh，占总耗电 12.2%", diagnostics)
        self.assertIn("Kernel 唤醒锁最长：PowerManagerService.WakeLocks", diagnostics)
        self.assertIn("应用部分唤醒锁最长：u0a288(com.mi.health) AudioIn", diagnostics)
        self.assertIn("蓝牙耗电 69.9 mAh", diagnostics)
        self.assertIn("已连接蓝牙设备：Xiaomi Smart Band 10 00DA、HUAWEI FreeClip", diagnostics)
        self.assertIn("移动网络流量 1.17 GB 下行 / 59.76 MB 上行", diagnostics)
        self.assertIn("当前 CPU 负载 15.79/15.85/16.28", diagnostics)

    def test_charge_counter_can_be_capacity_fallback_when_full(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "report.zip"
            inner_buffer = io.BytesIO()
            with zipfile.ZipFile(inner_buffer, "w") as inner:
                inner.writestr(
                    "dump/bugreport-demo.txt",
                    "\n".join([
                        "== dumpstate: 2026-06-26 12:34:56",
                        "Statistics since last charge:",
                        "  Estimated battery capacity: 5000 mAh",
                        "",
                        "Current Battery Service state:",
                        "  Charge counter: 4550000",
                        "  level: 100",
                        "  status: 5",
                    ]),
                )
            with zipfile.ZipFile(report_path, "w") as outer:
                outer.writestr("nested-diagnostic.zip", inner_buffer.getvalue())

            info = BatteryExtractor().extract(report_path)

        self.assertEqual(info.design_capacity, 5000)
        self.assertEqual(info.current_capacity, 4550)
        self.assertEqual(info.current_capacity_source, "满电状态 Charge counter 估算")
        self.assertAlmostEqual(info.health_percentage, 91.0, places=2)

    def test_extract_falls_back_to_outer_zip_when_inner_zip_corrupt(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "report-corrupt.zip"
            with zipfile.ZipFile(report_path, "w") as outer:
                outer.writestr("nested-corrupt.zip", b"\x00\x00\x00this-is-not-a-valid-zip")
                outer.writestr(
                    "dump/android.hardware.health-service.txt",
                    "\n".join([
                        "batteryFullChargeDesignCapacityUah: 5000000",
                        "batteryCycleCount: 77",
                        "batteryFullChargeUah: 4800000",
                    ]),
                )

            info = BatteryExtractor().extract(report_path)

        self.assertEqual(info.design_capacity, 5000)
        self.assertEqual(info.design_capacity_source, "hardware health 设计容量")
        self.assertEqual(info.cycle_count, 77)
        self.assertEqual(info.full_capacity, 4800)
        self.assertIsNone(info.current_capacity)

    def test_extract_matches_case_insensitive_inner_file_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "report-case.zip"
            inner_buffer = io.BytesIO()
            with zipfile.ZipFile(inner_buffer, "w") as inner:
                inner.writestr(
                    "DUMP/ANDROID.HARDWARE.HEALTH-SERVICE.TXT",
                    "\n".join([
                        "batteryFullChargeDesignCapacityUah: 4200000",
                        "batteryCycleCount: 9",
                        "batteryFullChargeUah: 3900000",
                    ]),
                )
                inner.writestr(
                    "DUMP/BUGREPORT-DEMO.TXT",
                    "\n".join([
                        "== dumpstate: 2026-06-26 12:00:00",
                    ]),
                )
            with zipfile.ZipFile(report_path, "w") as outer:
                outer.writestr("NESTED-DIAGNOSTIC.ZIP", inner_buffer.getvalue())

            info = BatteryExtractor().extract(report_path)

        self.assertEqual(info.design_capacity, 4200)
        self.assertEqual(info.design_capacity_source, "hardware health 设计容量")
        self.assertEqual(info.cycle_count, 9)
        self.assertEqual(info.full_capacity, 3900)
        self.assertEqual(info.report_time, "2026-06-26 12:00:00")

    def test_rating_boundaries_match_documented_table(self):
        self.assertEqual(get_rating_text(100), "极佳状态")
        self.assertEqual(get_rating_color(100), "#27ae60")
        self.assertEqual(
            get_rating_text(100.0002),
            "超出设计容量（可能为冗余设计或第三方电池）",
        )
        self.assertEqual(get_rating_color(69.99), "#e74c3c")

    def test_root_web_page_keeps_security_and_parity_guards(self):
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        bat_html = (BAT_DIR / "index.html").read_text(encoding="utf-8")

        self.assertIn("const RATING_TABLE", html)
        self.assertIn("[100.0001, Infinity", html)
        self.assertIn("Math.round(parseFloat", html)
        self.assertNotIn("Math.floor(parseFloat", html)
        self.assertIn("当前电池快照", html)
        self.assertIn("batterystats 估算容量", html)
        self.assertIn("Charge counter", html)
        self.assertIn("系统健康状态", html)
        self.assertIn("当前温度", html)
        self.assertIn("escHtml(deviceName)", html)
        self.assertIn("escHtml(autoExtractedInfo.reportTime)", html)
        self.assertIn("escHtml(statistics)", html)
        self.assertIn("escHtml(originalText)", html)
        self.assertIn("系统报告满充容量", html)
        self.assertIn("buildUsageDiagnosticsHtml", html)
        self.assertIn("parseUsageStats", html)
        self.assertIn("中文诊断结论", html)
        self.assertIn("屏幕 Doze 耗电", html)
        self.assertIn("设备深度 Doze 耗电", html)
        self.assertIn("耗电构成前三", html)
        self.assertIn("最高耗电 UID", html)
        self.assertIn("formatTopUidPower", html)
        self.assertIn("formatUidPowerDetail", html)
        self.assertIn("前台服务", html)
        self.assertIn("formatMahWithShare(item.mah, stats.totalDischargeMah)", html)
        self.assertIn("Kernel 唤醒锁最长", html)
        self.assertIn("应用部分唤醒锁最长", html)
        self.assertIn("parsePowerUseStats", html)
        self.assertIn("parseWakelockLeaders", html)
        self.assertIn("parseConnectivityPowerStats", html)
        self.assertIn("parseBluetoothStats", html)
        self.assertIn("parseCpuSnapshot", html)
        self.assertIn("parseScreenBrightnessStats", html)
        self.assertIn("Screen brightnesses", html)
        self.assertIn("亮度分布", html)
        self.assertIn("蓝牙耗电", html)
        self.assertIn("移动网络流量", html)
        self.assertIn("当前 CPU 负载", html)
        self.assertIn("当前满电附近充电功率上限约", html)
        self.assertIn("Time on battery:\\s*([\\ddhms .]+)", html)
        self.assertIn("Screen on discharge:\\s*([\\d.]+)\\s*mAh", html)
        self.assertIn("Total partial wakelock time", html)
        self.assertIn("Connectivity changes:", html)
        self.assertNotIn("Min learned battery capacity:\\s*(\\d+)\\s*mAh", html)
        self.assertIn("当前电池快照", bat_html)
        self.assertIn("batterystats 估算容量", bat_html)
        self.assertIn("Charge counter", bat_html)
        self.assertIn("系统健康状态", bat_html)
        self.assertIn("当前温度", bat_html)
        self.assertIn("buildUsageDiagnosticsHtml", bat_html)
        self.assertIn("parseUsageStats", bat_html)
        self.assertIn("中文诊断结论", bat_html)
        self.assertIn("屏幕 Doze 耗电", bat_html)
        self.assertIn("设备深度 Doze 耗电", bat_html)
        self.assertIn("耗电构成前三", bat_html)
        self.assertIn("最高耗电 UID", bat_html)
        self.assertIn("formatTopUidPower", bat_html)
        self.assertIn("formatUidPowerDetail", bat_html)
        self.assertIn("前台服务", bat_html)
        self.assertIn("formatMahWithShare(item.mah, stats.totalDischargeMah)", bat_html)
        self.assertIn("Kernel 唤醒锁最长", bat_html)
        self.assertIn("应用部分唤醒锁最长", bat_html)
        self.assertIn("parsePowerUseStats", bat_html)
        self.assertIn("parseWakelockLeaders", bat_html)
        self.assertIn("parseConnectivityPowerStats", bat_html)
        self.assertIn("parseBluetoothStats", bat_html)
        self.assertIn("parseCpuSnapshot", bat_html)
        self.assertIn("parseScreenBrightnessStats", bat_html)
        self.assertIn("Screen brightnesses", bat_html)
        self.assertIn("亮度分布", bat_html)
        self.assertIn("蓝牙耗电", bat_html)
        self.assertIn("移动网络流量", bat_html)
        self.assertIn("当前 CPU 负载", bat_html)
        self.assertIn("当前满电附近充电功率上限约", bat_html)
        self.assertIn("Time on battery:\\s*([\\ddhms .]+)", bat_html)
        self.assertIn("Screen on discharge:\\s*([\\d.]+)\\s*mAh", bat_html)
        self.assertIn("Total partial wakelock time", bat_html)
        self.assertIn("Connectivity changes:", bat_html)

    def test_cli_report_contains_chinese_usage_diagnostics(self):
        from battery_calc import Colors, ReportPrinter  # noqa: E402

        report_path = (
            BAT_DIR / "input" / "bugreport-2026-06-23-100941.zip"
        )
        if not report_path.exists():
            self.skipTest("real Xiaomi bugreport fixture not present")

        info = BatteryExtractor().extract(report_path)
        colors = Colors()
        colors.enabled = False
        colors._init_styles()
        text = ReportPrinter(colors).print_report(info, report_path.name)

        self.assertIn("中文诊断结论", text)
        self.assertIn("健康度 78.03%", text)
        self.assertIn("亮屏耗电占比 68.4%", text)
        self.assertIn("亮度分布：低亮度(dark) 82.2%", text)
        self.assertIn("本次亮屏主要处于低亮度", text)
        self.assertIn("屏幕 Doze 耗电 24.0 mAh，占总耗电 0.8%", text)
        self.assertIn("设备深度 Doze 耗电 686.0 mAh，占总耗电 22.1%", text)
        self.assertIn("部分唤醒锁约 4小时31分钟", text)
        self.assertIn("耗电构成前三：cpu 1897.0 mAh、mobile_radio 1713.0 mAh、audio 207.0 mAh", text)
        self.assertIn("最高耗电 UID：u0a290(com.tencent.qqmusic) 554.0 mAh，占总耗电 17.9%", text)
        self.assertIn("前台服务 468.0 mAh", text)
        self.assertIn("u0a377(com.tencent.tmgp.supercell.clashofclans) 377.0 mAh，占总耗电 12.2%", text)
        self.assertIn("Kernel 唤醒锁最长：PowerManagerService.WakeLocks", text)
        self.assertIn("应用部分唤醒锁最长：u0a288(com.mi.health) AudioIn", text)
        self.assertIn("蓝牙耗电 69.9 mAh", text)
        self.assertIn("移动网络流量 1.17 GB 下行 / 59.76 MB 上行", text)
        self.assertIn("当前 CPU 负载 15.79/15.85/16.28", text)



def _nested_zip(path: Path, inner_files: dict, outer_files: dict | None = None, inner_name: str = "bugreport-synthetic.zip") -> Path:
    inner_buffer = io.BytesIO()
    with zipfile.ZipFile(inner_buffer, "w", zipfile.ZIP_DEFLATED) as inner:
        for name, content in inner_files.items():
            inner.writestr(name, content)
    with zipfile.ZipFile(path, "w") as outer:
        for name, content in (outer_files or {}).items():
            outer.writestr(name, content)
        outer.writestr(inner_name, inner_buffer.getvalue())
    return path


def _charge_logger_tar(rows: list[str], member: str = "charge_logger/charge_log_0.csv") -> bytes:
    buffer = io.BytesIO()
    data = "\n".join(rows).encode("utf-8")
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        info = tarfile.TarInfo(member)
        info.size = len(data)
        archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


_WEAK_EVIDENCE_BUGREPORT = "\n".join([
    "[ro.product.marketname]: [Synthetic Phone Pro]",
    "[ro.product.device]: [synthphone]",
    "[ro.build.id]: [BP2A.250605.031.A3]",
    "[ro.build.version.incremental]: [OS2.0.206.0.SYNTH]",
    "== dumpstate: 2026-09-01 10:00:00",
    "    * 0.0.0.0/0 via rmnet_data0",
    "    * com.tencent.mm/u0a289 exemption=DENIED",
    "    * com.example.osgame/u0a300 exemption=DENIED",
    "Current Battery Service state:",
    "  AC powered: true",
    "  status: 2",
    "  health: 2",
    "  level: 100",
    "  scale: 100",
    "  Charge counter: 4019000",
    "  temperature: 362",
    "---------",
    "Statistics since last charge:",
    "  Estimated battery capacity: 6100 mAh",
    "  Last learned battery capacity: 4077 mAh",
    "  Min learned battery capacity: 4077 mAh",
    "  Max learned battery capacity: 4077 mAh",
    "  Time on battery: 1h 27m 4s 0ms (54.6%) realtime, 1h 27m 4s 0ms uptime",
    "  Time on battery screen off: 1m 52s 0ms (2.1%) realtime",
    "  Screen on: 1h 25m 12s 0ms (97.9%) 10x, Interactive: 1h 25m",
    "  Discharge: 909 mAh",
    "  Screen off discharge: 7 mAh",
    "  Screen doze discharge: 0 mAh",
    "  Screen on discharge: 902 mAh",
    "  Device deep doze discharge: 0 mAh",
    "  Connectivity changes: 167",
    "",
    "Estimated power use (mAh):",
    "  Capacity: 6100, Computed drain: 487, actual drain: 909",
    "  Global",
    "    screen: 150.0 apps: 150.0 duration: 1h 25m 0s",
    "    wifi_2g: 12.0 apps: 12.0",
    "    camera-front: 3.0 apps: 3.0",
    "    mobile_radio: 200.0 apps: 190.0",
    "  UID u0a300: 960 fg: 900 bg: 60",
    "  UID u0a289: 40",
    "  UID u999a289: 30",
    "  UID 1041: 25",
    "  UID 0: 20",
    "",
    "All kernel wake locks:",
    "  Kernel Wake lock game_popup: 19s 0ms (0 times) realtime",
    "",
    "Bluetooth Devices:",
    "    Xiaomi Smart Band 10 connected: true",
    "",
    "Load: 1.00 / 2.00 / 3.00",
    "CPU usage from 1000ms to 0ms ago:",
    "  2.0% 100/com.low.app: 1.0% user + 1.0% kernel",
    "  9.0% 101/com.high.app: 5.0% user + 4.0% kernel",
    "  5.0% 102/com.mid.app: 3.0% user + 2.0% kernel",
    "16% TOTAL: 9% user + 7% kernel",
    "",
])

_BMS_ROWS = [
    "time,bms_chg_full,bms_chg_full_design,bms_cycle_count,battery_soh,batt_temp,usb_real_type,pd_verified",
    "2026-02-01 08:00:00,5100000,6100000,700,95,300,USB_PD,1",
    "2026-07-20 08:00:00,4931000,6100000,900,90,420,USB_PD,1",
    "2026-08-20 08:00:00,4077000,6100000,928,89,362,USB_PD,1",
    "2026-09-01 09:00:00,4077000,6100000,928,89,455,USB_PD,1",
]


class EvidenceAndChargeLoggerTests(unittest.TestCase):
    def extract(self, inner_files, outer_files=None, **kwargs):
        with tempfile.TemporaryDirectory() as tmp:
            path = _nested_zip(Path(tmp) / "report.zip", inner_files, outer_files)
            return BatteryExtractor().extract(path, **kwargs)

    def test_estimated_design_and_flat_learning_soften_replacement_advice(self):
        info = self.extract({"bugreport-synth.txt": _WEAK_EVIDENCE_BUGREPORT})

        self.assertEqual(info.design_capacity_source, DESIGN_SOURCE_ESTIMATED)
        self.assertEqual(info.design_capacity_confidence[0], "中")
        self.assertIsNotNone(info.learned_capacity_note)
        self.assertEqual(info.health_evidence[0], "弱")
        self.assertEqual(info.rating_text, SOFT_REPLACEMENT_RATING)
        self.assertEqual(get_rating_text(info.health_percentage), "建议考虑更换电池")
        diagnostics = "\n".join(info.usage_diagnostics)
        self.assertIn("健康度 66.84%，按当前数据低于 70%，但证据强度为弱", diagnostics)
        self.assertIn("暂不建议仅凭此数字更换电池", diagnostics)
        self.assertIn("健康度约 65.9%–66.8%", diagnostics)
        self.assertIn("系统 health 状态为「良好」", diagnostics)
        self.assertTrue(any("未找到 android.hardware.health 节点" in item for item in info.parse_warnings))
        self.assertEqual(
            (info.device_codename, info.build_id, info.build_incremental),
            ("synthphone", "BP2A.250605.031.A3", "OS2.0.206.0.SYNTH"),
        )

    def test_strong_evidence_keeps_replacement_rating(self):
        info = BatteryInfo(
            design_capacity=5000, design_capacity_source=DESIGN_SOURCE_HEALTH,
            last_learned_capacity=3100, min_learned_capacity=3000, max_learned_capacity=3300,
        )
        self.assertEqual(info.health_evidence, ("强", []))
        self.assertEqual(info.rating_text, "建议考虑更换电池")
        self.assertIn("建议优先考虑售后检测或更换电池", info.usage_diagnostics[0])

    def test_manual_design_capacity_is_user_declared_not_downgraded(self):
        info = BatteryInfo(design_capacity=5000, design_capacity_auto=False, design_capacity_source="手动输入",
                           min_learned_capacity=3000)
        self.assertEqual(info.design_capacity_confidence[0], "用户声明")
        self.assertEqual(info.health_evidence[0], "强")

    def test_window_quality_and_sample_size_guards(self):
        info = self.extract({"bugreport-synth.txt": _WEAK_EVIDENCE_BUGREPORT})
        labels = "、".join(info.window_quality)
        self.assertIn("抓包时正在充电或已充满", labels)
        self.assertIn("短会话", labels)
        self.assertIn("高亮屏占比", labels)
        diagnostics = "\n".join(info.usage_diagnostics)
        self.assertIn("样本过短，仅供参考", diagnostics)
        self.assertNotIn("偏高，建议检查后台唤醒", diagnostics)
        self.assertIn("本次无有效屏幕 Doze 样本", diagnostics)
        self.assertIn("本次无有效设备深度 Doze 样本", diagnostics)
        self.assertIn("连接切换 167 次（约 115 次/小时）", diagnostics)
        self.assertIn("game_popup 19秒、次数未记录", diagnostics)

    def test_connectivity_threshold_is_normalized_by_window(self):
        long_window = BatteryInfo(connectivity_changes=150, time_on_battery_seconds=10 * 3600)
        self.assertFalse(any("连接切换" in line for line in long_window.usage_diagnostics))
        legacy = BatteryInfo(connectivity_changes=259)
        self.assertTrue(any("连接切换 259 次" in line for line in legacy.usage_diagnostics))

    def test_uid_labels_shares_and_dual_app_merge(self):
        info = self.extract({"bugreport-synth.txt": _WEAK_EVIDENCE_BUGREPORT})
        self.assertNotIn("0", info.uid_packages)
        diagnostics = "\n".join(info.usage_diagnostics)
        self.assertIn("u0a300(com.example.osgame) 960.0 mAh（高于本次实际放电统计", diagnostics)
        self.assertNotIn("占总耗电 105", diagnostics)
        self.assertIn("u999a289(com.tencent.mm·应用双开)", diagnostics)
        self.assertIn("com.tencent.mm（u0a289、u999a289）合计 70.0 mAh", diagnostics)
        self.assertIn("相差 46%，两者来源不同", diagnostics)
        self.assertEqual(battery_core._format_uid_label("1041", {}), "1041(audioserver/音频服务)")
        self.assertEqual(battery_core._format_uid_label("1027", {}), "1027(nfc/NFC)")
        self.assertEqual(battery_core._format_uid_label("0", {}), "0(root/内核)")

    def test_parser_details_cpu_components_and_bluetooth(self):
        info = self.extract({"bugreport-synth.txt": _WEAK_EVIDENCE_BUGREPORT})
        self.assertEqual([item.name for item in info.top_cpu_processes], ["com.high.app", "com.mid.app", "com.low.app"])
        names = [item.name for item in info.power_components]
        self.assertIn("wifi_2g", names)
        self.assertIn("camera-front", names)
        self.assertEqual(info.bluetooth_connected_devices, ["Xiaomi Smart Band 10"])

    def test_charge_logger_tar_supplies_bms_design_cycles_and_conflict(self):
        info = self.extract({
            "bugreport-synth.txt": _WEAK_EVIDENCE_BUGREPORT,
            "FS/data/vendor/charge_logger.tar": _charge_logger_tar(_BMS_ROWS),
        })
        self.assertEqual((info.bms_soh, info.bms_full_capacity, info.bms_design_capacity, info.bms_cycle_count),
                         (89.0, 4077.0, 6100.0, 928))
        self.assertEqual(info.design_capacity_source, DESIGN_SOURCE_BMS)
        self.assertEqual(info.design_capacity_confidence[0], "高")
        self.assertEqual((info.cycle_count, info.cycle_count_source), (928, CYCLE_SOURCE_BMS))
        self.assertTrue(info.has_soh_conflict)
        self.assertAlmostEqual(info.bms_soh_gap, 22.16, places=1)
        self.assertEqual(info.charge_protocol, "USB_PD")
        self.assertTrue(info.charge_pd_verified)
        self.assertEqual(info.bms_max_temperature_c, 45.5)
        self.assertAlmostEqual(info.bms_high_temperature_share, 50.0)
        self.assertEqual([point.day for point in info.bms_history], ["2026-02-01", "2026-07-20", "2026-08-20", "2026-09-01"])
        text = "\n".join(info.usage_diagnostics + info.summary_lines)
        self.assertIn("口径冲突", text)
        self.assertIn("BMS 健康度（SoH，厂商口径）：89%", text)
        self.assertIn("2026-07-20→2026-08-20 满充容量骤降 854 mAh", text)
        self.assertIn("近 30 日 -854 mAh", text)
        self.assertIn("循环次数约 928 次，已偏高，即使 SoH 仍为 89%", text)
        self.assertIn("充电协议 USB_PD，PD 已认证", text)

    def test_charge_logger_key_value_text_entry(self):
        rows = [
            "2026-09-01 09:00:00 bms_chg_full=4077 bms_chg_full_design=6100 battery_soh=89 bms_cycle_count=928",
            "garbage line without fields",
        ]
        info = self.extract({"bugreport-synth.txt": _WEAK_EVIDENCE_BUGREPORT, "logs/charge_logger_1.log": "\n".join(rows)})
        self.assertEqual((info.bms_soh, info.bms_full_capacity, info.bms_cycle_count), (89.0, 4077.0, 928))

    def test_charge_logger_temperature_unit_is_inferred_per_batch(self):
        rows = ["time,battery_soh,batt_temp"] + [
            f"2026-09-0{day} 08:00:00,90,{raw}" for day, raw in ((1, 95), (2, 120), (3, 180))
        ]
        info = self.extract({"bugreport-synth.txt": _WEAK_EVIDENCE_BUGREPORT, "charge_logger.tar": _charge_logger_tar(rows)})
        self.assertEqual(info.bms_max_temperature_c, 18.0)
        self.assertEqual(info.bms_high_temperature_share, 0.0)
        celsius = ["time,battery_soh,batt_temp", "2026-09-01 08:00:00,90,36.5", "2026-09-02 08:00:00,90,42"]
        info = self.extract({"bugreport-synth.txt": _WEAK_EVIDENCE_BUGREPORT, "charge_logger.tar": _charge_logger_tar(celsius)})
        self.assertEqual(info.bms_max_temperature_c, 42.0)
        self.assertEqual(info.bms_high_temperature_share, 50.0)

    def test_weak_evidence_between_70_and_80_is_not_an_action_item(self):
        info = BatteryInfo(design_capacity=5000, design_capacity_source=DESIGN_SOURCE_ESTIMATED, min_learned_capacity=3800)
        self.assertEqual(info.health_evidence[0], "中")
        self.assertFalse(any("容量衰减待确认" in title for title, _action in info.root_causes))

    def test_unrecognized_charge_logger_is_reported_not_guessed(self):
        info = self.extract({
            "bugreport-synth.txt": _WEAK_EVIDENCE_BUGREPORT,
            "charge_logger.tar": _charge_logger_tar(["col_a,col_b", "1,2"]),
        })
        self.assertIsNone(info.bms_soh)
        self.assertTrue(any("未识别到 BMS 字段" in item for item in info.parse_warnings))
        self.assertEqual(info.design_capacity_source, DESIGN_SOURCE_ESTIMATED)

    def test_inner_zip_priority_skip_list_and_streaming(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _nested_zip(
                Path(tmp) / "report.zip",
                {"bugreport-synth.txt": _WEAK_EVIDENCE_BUGREPORT},
                {"encrypt_voice_trigger.zip": b"not a zip", "com.demo-appLog.zip": b"not a zip either"},
            )
            with patch.object(zipfile.ZipFile, "read", side_effect=AssertionError("inner zip must be streamed")):
                info = BatteryExtractor().extract(path)
        self.assertEqual(sorted(info.skipped_inner_archives), ["com.demo-appLog.zip", "encrypt_voice_trigger.zip"])
        self.assertFalse(any("encrypt_voice_trigger" in item for item in info.parse_warnings))
        self.assertTrue(any("已跳过 2 个与电池诊断无关的内层包" in item for item in info.parse_warnings))
        self.assertIsNotNone(info.health_percentage)

    def test_progress_callback_and_cancellation(self):
        events = []
        info = self.extract({"bugreport-synth.txt": _WEAK_EVIDENCE_BUGREPORT}, progress=events.append)
        self.assertTrue(events)
        self.assertIn("bytes_read", events[-1])
        self.assertGreater(info.parse_stats["bytes_read"], 0)
        cancelled = threading.Event()
        cancelled.set()
        with self.assertRaises(ExtractionCancelled):
            self.extract({"bugreport-synth.txt": _WEAK_EVIDENCE_BUGREPORT}, cancel_event=cancelled)

    def test_truncated_statistics_block_is_warned(self):
        text = "Statistics since last charge:\n  Min learned battery capacity: 4500 mAh\n" + (
            "  filler line\n" * 5100) + "\n"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("bugreport.txt", text)
            info = BatteryExtractor().extract(path)
        self.assertTrue(info.stats_truncated)
        self.assertTrue(any("已截断" in item for item in info.parse_warnings))

    def test_payload_redaction_and_batch_summary(self):
        info = self.extract({
            "bugreport-synth.txt": _WEAK_EVIDENCE_BUGREPORT,
            "charge_logger.tar": _charge_logger_tar(_BMS_ROWS),
        })
        payload = build_report_payload(info, {"name": "report.zip", "bytes": 1, "sha256_12": "0" * 12,
                                              "parser_build": battery_core.PARSER_BUILD})
        encoded = json.dumps(payload, ensure_ascii=False)
        self.assertEqual(payload["health"]["design_capacity_source"], DESIGN_SOURCE_BMS)
        self.assertEqual(payload["bms"]["soh"], 89.0)
        self.assertTrue(payload["bms"]["conflict"])
        self.assertEqual(payload["cycle_count"], {"value": 928, "source": CYCLE_SOURCE_BMS})
        self.assertIn("window_quality", payload)
        self.assertIn("com.tencent.mm", encoded)
        redacted = redacted_copy(info)
        redacted_text = json.dumps(build_report_payload(redacted), ensure_ascii=False) + "\n".join(redacted.usage_diagnostics)
        for secret in ("com.tencent.mm", "com.example.osgame", "Xiaomi Smart Band", "com.high.app"):
            self.assertNotIn(secret, redacted_text)
        self.assertIsNone(redacted.statistics)
        self.assertIn("com.tencent.mm", "\n".join(info.usage_diagnostics))
        rows = batch_summary_rows([("a.zip", info, None), ("b.zip", None, "ZIP 文件损坏或格式不正确")])
        self.assertEqual(rows[0][2], "66.84%")
        self.assertEqual(rows[0][5], "928")
        self.assertEqual(rows[1][-1], "失败：ZIP 文件损坏或格式不正确")
        self.assertTrue(format_batch_summary_csv([("a.zip", info, None)]).startswith("文件,型号,健康度"))

    def test_inner_zip_order_lets_newest_bugreport_win(self):
        def inner(min_learned, filler=0):
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("bugreport-dump.txt", "Statistics since last charge:\n"
                                 "  Estimated battery capacity: 5000 mAh\n"
                                 f"  Min learned battery capacity: {min_learned} mAh\n" + "  filler\n" * filler + "\n")
            return buffer.getvalue()

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.zip"
            with zipfile.ZipFile(path, "w") as outer:
                outer.writestr("zz-extra-logs.zip", inner(3000))
                outer.writestr("bugreport-2026-01-01.zip", inner(4200, filler=2000))
                outer.writestr("bugreport-2026-09-01.zip", inner(4000))
            with zipfile.ZipFile(path) as outer:
                order, _skipped = BatteryExtractor._find_inner_zips(outer)
            info = BatteryExtractor().extract(path)
        # 后解析的包覆盖统计字段：其它包在前，bugreport 包按文件名排在最后，日期最新的一份生效（与体积无关）。
        self.assertEqual(order, ["zz-extra-logs.zip", "bugreport-2026-01-01.zip", "bugreport-2026-09-01.zip"])
        self.assertEqual(info.min_learned_capacity, 4000)
        self.assertAlmostEqual(info.health_percentage, 80.0)

    def test_skip_list_matches_only_known_irrelevant_archives(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "outer.zip"
            with zipfile.ZipFile(path, "w") as outer:
                for name in ("encrypt_voice_trigger.zip", "com.demo-appLog.zip", "applog-parser-notes.zip",
                             "bugreport-applog.zip"):
                    outer.writestr(name, b"x")
            with zipfile.ZipFile(path) as outer:
                order, skipped = BatteryExtractor._find_inner_zips(outer)
        self.assertEqual(sorted(skipped), ["com.demo-appLog.zip", "encrypt_voice_trigger.zip"])
        self.assertEqual(order, ["applog-parser-notes.zip", "bugreport-applog.zip"])

    def test_inner_archive_temp_files_do_not_outlive_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            scratch = Path(tmp) / "scratch"
            scratch.mkdir()
            path = _nested_zip(Path(tmp) / "report.zip", {"bugreport-synth.txt": _WEAK_EVIDENCE_BUGREPORT},
                               {"bugreport-broken.zip": b"not a zip"})
            cancelled = threading.Event()
            with patch.object(tempfile, "tempdir", str(scratch)):
                info = BatteryExtractor().extract(path)
                self.assertEqual(list(scratch.iterdir()), [])
                with self.assertRaises(ExtractionCancelled):
                    BatteryExtractor().extract(path, progress=lambda _event: cancelled.set(), cancel_event=cancelled)
                self.assertEqual(list(scratch.iterdir()), [])
        self.assertTrue(any("内层归档非法: bugreport-broken.zip" in item for item in info.parse_warnings))
        self.assertIsNotNone(info.health_percentage)

    def test_bms_trend_windows_are_bounded_and_step_drop_wording(self):
        info = BatteryInfo(bms_history=[
            battery_core.BmsDailyPoint("2026-01-01", 5000.0),
            battery_core.BmsDailyPoint("2026-08-25", 4900.0),
            battery_core.BmsDailyPoint("2026-09-01", 4500.0),
        ])
        text = "\n".join(info.bms_trend_notes)
        self.assertIn("近 7 日 -400 mAh（对比 2026-08-25，相隔 7 天）", text)
        # 243 天前的记录不能当作“近 30 日”的参考点。
        self.assertNotIn("近 30 日", text)
        self.assertIn("缺少同期 SoH 记录，无法区分电量计校准事件和真实衰减", text)
        self.assertNotIn("更像电量计校准事件", text)

    def test_charge_logger_temperature_median_soh_fraction_and_sentinels(self):
        rows = ["time,battery_soh,batt_temp",
                "2026-09-01 08:00:00,0.95,31", "2026-09-02 08:00:00,0.95,36",
                "2026-09-03 08:00:00,0.95,999", "2026-09-04 08:00:00,0.94,-400"]
        info = self.extract({"bugreport-synth.txt": _WEAK_EVIDENCE_BUGREPORT, "charge_logger.tar": _charge_logger_tar(rows)})
        self.assertAlmostEqual(info.bms_soh, 94.0)
        self.assertEqual(info.bms_max_temperature_c, 36.0)
        self.assertEqual(info.bms_high_temperature_share, 0.0)
        # 0.1 ℃ 单位的低温占位值（-400）按中位数识别单位后被剔除。
        self.assertEqual(battery_core._temperature_summary({2500: 1, 3000: 1, -4000: 1}), (30.0, 0.0))
        self.assertIsNone(battery_core._soh_percent(5))
        self.assertIsNone(battery_core._soh_percent(101))
        self.assertAlmostEqual(battery_core._soh_percent(0.9), 90.0)

    def test_charge_logger_mixed_header_and_key_value_rows(self):
        rows = [
            "time,battery_soh,batt_temp",
            "2026-09-01 08:00:00,90,300",
            "2026-09-02 08:00:00 bms_chg_full=4077, bms_cycle_count=928, battery_soh=89",
        ]
        info = self.extract({"bugreport-synth.txt": _WEAK_EVIDENCE_BUGREPORT, "charge_logger.tar": _charge_logger_tar(rows)})
        self.assertEqual((info.bms_soh, info.bms_full_capacity, info.bms_cycle_count), (89.0, 4077.0, 928))

    def test_unrecognized_charge_logger_files_are_reported_once(self):
        info = self.extract({
            "bugreport-synth.txt": _WEAK_EVIDENCE_BUGREPORT,
            "a/charge_logger_1.log": "col_a,col_b\n1,2\n",
            "b/charge_logger_2.log": "nothing useful here\n",
        })
        warnings = [item for item in info.parse_warnings if "未识别到 BMS 字段" in item]
        self.assertEqual(len(warnings), 1)
        self.assertIn("等 2 个文件", warnings[0])

    def test_bms_design_capacity_sanity_check(self):
        rows = ["time,bms_chg_full,bms_chg_full_design,battery_soh", "2026-09-01 08:00:00,4000,3000,90"]
        info = self.extract({"bugreport-synth.txt": _WEAK_EVIDENCE_BUGREPORT, "charge_logger.tar": _charge_logger_tar(rows)})
        self.assertEqual(info.bms_design_capacity, 3000.0)
        self.assertEqual((info.design_capacity, info.design_capacity_source), (6100, DESIGN_SOURCE_ESTIMATED))
        self.assertTrue(any("设计容量 3000 mAh 与 batterystats 估算 6100 mAh 相差超过 30%" in item
                            for item in info.parse_warnings))
        self.assertIn("不在 1000–20000 mAh", battery_core._bms_design_rejection(60000, None))

    def test_snapshot_without_usage_stats_keeps_fallback_and_no_window_labels(self):
        info = BatteryInfo(design_capacity=5000, design_capacity_source=DESIGN_SOURCE_HEALTH,
                           min_learned_capacity=4500, status_code=2, ac_powered=True, temperature_c=30.0)
        self.assertFalse(info.has_usage_stats)
        self.assertEqual(info.window_quality, [])
        self.assertEqual(info.usage_diagnostics[-1], battery_core.NO_USAGE_STATS_NOTE)
        self.assertFalse(any(line.startswith("统计窗口") for line in info.summary_lines))

    def test_root_cause_advice_matches_uid_kind(self):
        def cause(uid, packages=None):
            info = BatteryInfo(total_discharge_mah=1000, top_uid_power=[battery_core.UidPower(uid, 400)],
                               uid_packages=packages or {})
            return next((title, action) for title, action in info.root_causes if "耗电突出" in title)

        title, action = cause("1041")
        self.assertTrue(title.startswith("系统组件 1041(audioserver/音频服务)"))
        self.assertNotIn("自启动", action)
        title, action = cause("u0a300", {"u0a300": "com.example.osgame"})
        self.assertTrue(title.startswith("游戏 "))
        self.assertIn("降低画质", action)
        title, action = cause("u0a301", {"u0a301": "com.example.notes"})
        self.assertTrue(title.startswith("应用 "))
        self.assertNotIn("画质", action)

    def test_connectivity_uses_rate_when_window_is_known(self):
        day = BatteryInfo(connectivity_changes=300, time_on_battery_seconds=24 * 3600)
        self.assertFalse(any("连接切换" in line for line in day.usage_diagnostics))
        busy = BatteryInfo(connectivity_changes=120, time_on_battery_seconds=3 * 3600)
        self.assertTrue(any("连接切换 120 次（约 40 次/小时）" in line for line in busy.usage_diagnostics))

    def test_redaction_hides_paths_kernel_package_tokens_and_file_names(self):
        info = BatteryInfo(
            total_discharge_mah=500,
            kernel_wakelocks=[battery_core.WakeLockInfo("com.example.secret.sync_alarm", 30.0, 2),
                              battery_core.WakeLockInfo("PowerManagerService.WakeLocks", 20.0, 1)],
            parse_warnings=["日志解析失败: FS/data/user/张三/bugreport-a.txt (UnicodeError)", "内层归档非法: 张三的手机.zip (bad)"],
            skipped_inner_archives=["张三-appLog.zip"],
        )
        redacted = redacted_copy(info)
        text = json.dumps(build_report_payload(redacted), ensure_ascii=False)
        for secret in ("com.example.secret", "张三", "bugreport-a.txt"):
            self.assertNotIn(secret, text)
        self.assertIn("com.example.secret", json.dumps(build_report_payload(info), ensure_ascii=False))
        self.assertEqual(redacted.kernel_wakelocks[1].name, "PowerManagerService.WakeLocks")
        self.assertEqual(battery_core.redacted_fingerprint({"name": "张三.zip", "bytes": 1}, "文件3")["name"], "文件3")

    def test_batch_csv_neutralizes_formula_cells(self):
        csv_text = format_batch_summary_csv([("=HYPERLINK(1).zip", None, "ZIP 文件损坏或格式不正确")])
        self.assertIn("'=HYPERLINK(1).zip", csv_text)

    def test_manual_design_capacity_overrides_and_clears_downgrade_warning(self):
        info = self.extract({"bugreport-synth.txt": _WEAK_EVIDENCE_BUGREPORT})
        self.assertTrue(any("已降级使用" in item for item in info.parse_warnings))
        battery_core.apply_manual_design_capacity(info, 5000)
        self.assertEqual((info.design_capacity, info.design_capacity_source, info.design_capacity_auto),
                         (5000, "手动输入", False))
        self.assertFalse(any("已降级使用" in item for item in info.parse_warnings))

    def test_health_node_uses_last_snapshot_and_reports_changes(self):
        health = "\n".join([
            "batteryFullChargeDesignCapacityUah: 0",
            "batteryFullChargeDesignCapacityUah: 5000000", "batteryCycleCount: 120", "batteryFullChargeUah: 4600000",
            "--- later snapshot ---",
            "batteryFullChargeDesignCapacityUah: 5000000", "batteryCycleCount: 123", "batteryFullChargeUah: 4550000",
        ])
        info = self.extract({"android.hardware.health-service.txt": health,
                             "bugreport-synth.txt": "Statistics since last charge:\n  Min learned battery capacity: 4500 mAh\n\n"})
        self.assertEqual((info.design_capacity, info.cycle_count, info.full_capacity), (5000, 123, 4550))
        warnings = "\n".join(info.parse_warnings)
        self.assertIn("batteryCycleCount 出现多个不同值（首次 120、末次 123）", warnings)
        self.assertNotIn("batteryFullChargeDesignCapacityUah 出现多个不同值", warnings)

    def test_parse_stats_include_peak_memory_when_available(self):
        info = self.extract({"bugreport-synth.txt": _WEAK_EVIDENCE_BUGREPORT})
        if battery_core._peak_memory_bytes() is None:
            self.skipTest("platform does not expose peak memory")
        self.assertGreater(info.parse_stats["peak_memory_mb"], 0)

    def test_rating_table_matches_both_web_pages(self):
        for page in (ROOT / "index.html", BAT_DIR / "index.html"):
            with self.subTest(page=page.name):
                html = page.read_text(encoding="utf-8")
                block = re.search(r"const RATING_TABLE = \[(.*?)\];", html, re.S).group(1)
                rows = re.findall(
                    r"\[\s*([\d.]+|Infinity)\s*,\s*([\d.]+|Infinity)\s*,\s*'([^']+)'\s*,\s*'(#[0-9a-f]{6})'\s*\]", block)
                parsed = tuple((float(low), float("inf") if high == "Infinity" else float(high), text, color)
                               for low, high, text, color in rows)
                self.assertEqual(parsed, battery_core._RATING_TABLE)


class CliExportTests(unittest.TestCase):
    def test_cli_json_redact_no_raw_batch_and_detailed_exit_codes(self):
        from battery_calc import main as cli_main

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            _nested_zip(folder / "a.zip", {"bugreport-synth.txt": _WEAK_EVIDENCE_BUGREPORT,
                                           "charge_logger.tar": _charge_logger_tar(_BMS_ROWS)})
            with zipfile.ZipFile(folder / "b.zip", "w") as archive:
                archive.writestr("bugreport.txt", "[ro.product.model]: [Snapshot Device]\nCurrent Battery Service state:\nlevel: 20\n")
            report, data = folder / "out.txt", folder / "out.json"
            args = ["--input", str(folder), "--output", str(report), "--json", str(data),
                    "--redact", "--no-raw", "--no-pause", "--no-color"]
            with patch("battery_calc.is_interactive", return_value=False), contextlib.redirect_stdout(io.StringIO()):
                legacy = cli_main(args)
                detailed = cli_main(args + ["--detailed-exit-codes"])
            text = report.read_text(encoding="utf-8")
            document = json.loads(data.read_text(encoding="utf-8"))
        self.assertEqual(legacy, 1)
        self.assertEqual(detailed, 3)
        self.assertIn("结论摘要", text)
        self.assertIn("文件指纹: 文件1", text)
        self.assertNotIn("a.zip", text)
        self.assertIn("批量汇总（共 2 份）", text)
        self.assertNotIn("com.tencent.mm", text)
        self.assertNotIn("原始电池统计数据", text)
        self.assertEqual(len(document["reports"]), 2)
        self.assertEqual(document["failures"], [])
        self.assertEqual(document["reports"][0]["bms"]["soh"], 89.0)
        self.assertEqual(document["reports"][0]["source"]["name"], "文件1")

    def test_cli_all_failures_write_no_report_and_json_lists_failures(self):
        from battery_calc import main as cli_main

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "a.zip").write_bytes(b"broken")
            (folder / "b.zip").write_bytes(b"broken too")
            report = folder / "out.txt"
            with patch("battery_calc.is_interactive", return_value=False), contextlib.redirect_stdout(io.StringIO()):
                all_failed = cli_main(["--input", str(folder), "--output", str(report), "--no-pause", "--no-color"])
            report_written = report.exists()
            _nested_zip(folder / "c.zip", {"bugreport-synth.txt": _WEAK_EVIDENCE_BUGREPORT})
            data = folder / "out.json"
            with patch("battery_calc.is_interactive", return_value=False), contextlib.redirect_stdout(io.StringIO()):
                mixed = cli_main(["--input", str(folder), "--json", str(data), "--no-pause", "--no-color"])
            document = json.loads(data.read_text(encoding="utf-8"))
        self.assertEqual(all_failed, 1)
        self.assertFalse(report_written, "all-failed run must not write a summary-only report")
        self.assertEqual(mixed, 1)
        self.assertEqual(len(document["reports"]), 1)
        self.assertEqual([item["file"] for item in document["failures"]], ["a.zip", "b.zip"])

    def test_cli_json_path_is_validated_before_analysis(self):
        from battery_calc import main as cli_main

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            _nested_zip(folder / "a.zip", {"bugreport-synth.txt": _WEAK_EVIDENCE_BUGREPORT})
            same = folder / "same.json"
            with patch("battery_calc.is_interactive", return_value=False), \
                    patch("battery_calc.BatteryExtractor.extract", side_effect=AssertionError("analysis must not start")), \
                    contextlib.redirect_stdout(io.StringIO()):
                result = cli_main(["--input", str(folder), "--output", str(same), "--json", str(same),
                                   "--no-pause", "--no-color"])
            self.assertFalse(same.exists())
        self.assertEqual(result, 1)

    def test_cli_rejects_non_json_side_output(self):
        from battery_calc import main as cli_main

        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            _nested_zip(folder / "a.zip", {"bugreport-synth.txt": _WEAK_EVIDENCE_BUGREPORT})
            with patch("battery_calc.is_interactive", return_value=False), contextlib.redirect_stdout(io.StringIO()):
                result = cli_main(["--input", str(folder), "--json", str(folder / "out.txt"), "--no-pause", "--no-color"])
        self.assertEqual(result, 1)


if __name__ == "__main__":
    unittest.main()
