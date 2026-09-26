# 真实诊断包人工验收清单（不进入自动化测试）

用途：拿到一份真实的小米/HyperOS 诊断 ZIP 后，由人工逐项核对新版解析结果。
自动化测试只使用合成样本（见 `AGENTS.md` 硬性规则）；本清单不改变这一点，也不要把真实 ZIP 放进仓库。

## 操作步骤

1. 把真实 ZIP 放到本机任意目录（不要放进仓库的 `input/` 再提交）。
2. 运行（只读，报告写到仓库外）：

   ```powershell
   python HyperBatteryHealthCalc-bat\battery_calc.py --input "D:\诊断包目录" --output "D:\验收\report.txt" --json "D:\验收\report.json" --no-pause --no-color
   ```

3. 用 GUI 打开同一个 ZIP，确认状态栏有进度、可以取消、保存 TXT/JSON 正常；勾选“导出时脱敏”再保存一次。
4. 按下表核对 `report.json` 与报告正文。

## 核对表

“参考值”列来自优化建议报告中引用的真实样本（Xiaomi 15 Pro / haotian / BP2A.250605.031.A3，约 162 MB）。
**本机未找到该样本，参考值未经本次复核**；请以你手上样本的实际内容为准，把实际值填入最后一列。

| # | 字段（JSON 路径） | 参考值 | 核对要点 | 实际值 |
|---|---|---|---|---|
| 1 | `health.design_capacity_mah` | 6100 | 有 charge_logger 时来源应为 `charge_logger BMS 设计容量`；否则为 `batterystats 估算容量` | |
| 2 | `health.design_capacity_confidence` | 高 / 中 | 与第 1 项来源对应 | |
| 3 | `health.current_capacity_mah` | 4077 | 来源 `batterystats 最小学习容量` | |
| 4 | `health.percentage` | 66.84 | 容量比，不是官方 SoH | |
| 5 | `health.learned_capacity_note` | 非空 | 上次/最小/最大学习容量三值相同时应提示“学习样本不足” | |
| 6 | `health.rating` | 明显衰减（证据不足，待复核） | 证据不足时不应直接显示“建议考虑更换电池” | |
| 7 | `bms.soh` | 89 | 仅当识别到 charge_logger 字段时存在 | |
| 8 | `bms.conflict` | true | 容量比与 SoH 相差超过 10 个百分点 | |
| 9 | `cycle_count.value` / `.source` | 928 / charge_logger BMS 循环次数 | health 节点缺失时由 BMS 补齐 | |
| 10 | `bms.trend_notes` | 含 4931→4077 骤降提示 | 满充骤降但 SoH 几乎不变时应提示“疑似校准事件” | |
| 11 | `window_quality` | 充电中、短会话、高亮屏占比 | 与抓包时状态一致 | |
| 12 | `diagnostics` 中的 UID 行 | 无“占总耗电 105.6%” | 高于实际放电时改为“仅用于排名” | |
| 13 | `parse_warnings` | 含“未找到 android.hardware.health 节点” | 样本缺少 health 节点时应降级提示 | |
| 14 | `skipped_inner_archives` | 含 `encrypt_voice_trigger.zip` | 无关内层包被跳过，报告只汇总提示一次跳过数量，不逐个告警 | |
| 15 | `parse_stats.elapsed_seconds` | — | 记录耗时，便于版本间对比 | |
| 16 | 脱敏报告 | — | 不出现应用包名、蓝牙设备名、唤醒锁标签、原始统计段 | |

## 已知限制

- charge_logger 的列名/单位按常见字段名做了容错（CSV 表头或 `key=value`，µAh/mAh 与 0.1 ℃ 自动换算），
  但尚未在多机型、多固件的真实样本上验证；识别不到时报告只提示“未识别到 BMS 字段”。
- 设计容量的“官方标称值”没有内置机型表，避免引用未经核实的数据。
