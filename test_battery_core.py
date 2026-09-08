# -*- coding: utf-8 -*-
"""Regression tests for battery extraction and Web/Python parity."""
from __future__ import annotations

import io
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BAT_DIR = ROOT / "HyperBatteryHealthCalc-bat"
sys.path.insert(0, str(BAT_DIR))

from battery_core import BatteryExtractor, get_rating_color, get_rating_text  # noqa: E402


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
        self.assertEqual(info.last_learned_capacity, 4612)
        self.assertEqual(info.current_capacity, 4599)
        self.assertAlmostEqual(info.health_percentage, 91.98, places=2)
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
        self.assertIn("Math.floor(parseFloat", html)
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


if __name__ == "__main__":
    unittest.main()
