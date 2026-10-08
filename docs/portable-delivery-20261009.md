# HyperBatteryHealthCalc 便携交付记录

更新：2026-10-09。状态：`release-verified`。

本轮完成 52 条优化建议对应的源码优化，并用 Claude Code `claude-opus-5-5`（effort max）做了多轮独立复查，复查结论全部修复后重新构建 Windows 11 x64 便携包。

## 本次交付

| 项目 | 值 |
|---|---|
| GitHub 仓库 | [48ytw4q7zg-sudo/HyperBatteryHealthCalc-bat](https://github.com/48ytw4q7zg-sudo/HyperBatteryHealthCalc-bat) |
| 源码分支 | `master`（同步推送 `optimize-2026-09-review`） |
| 本次发行位置 | [portable-20261009](https://github.com/48ytw4q7zg-sudo/HyperBatteryHealthCalc-bat/releases/tag/portable-20261009) |
| 本地发行目录 | `D:\1\HyperBatteryHealthCalc-main\dist\HyperBatteryHealthCalc-Windows-x64-20261008-221824-f0de01` |
| ZIP | `HyperBatteryHealthCalc-Windows-x64.zip` |
| ZIP 大小 | 15,455,049 bytes |
| ZIP SHA256 | `9d891326cc21c90317c41c677800fa49bafea5f74240ed2c9f895795724a5551` |
| 实际构建源码提交 | `2a1a62542041c198b6a547389ec083a20cd45868` |
| 构建证据 | `.build\windows-20261008-221824-f0de01\evidence\` |
| bundle 验收记录 SHA256 | `FEEC55B0A2C6FD663DD0D307B1F935FC4035FB288360A9A33CE9236E770C7248` |

解压后保留完整的 `HyperBatteryHealthCalc` 文件夹和 `_internal`，不要直接在 ZIP 内运行，也不要只复制 EXE。便携包自带运行库，不需要安装本机 Python。双击 `HyperBatteryHealthCalc.exe`；命令行程序为 `HyperBatteryHealthCalc-cli.exe`。

两份电池网页属于源码交付，不放入 EXE 包。最终源码提交只追加本记录等文档更新；实际构建代码版本以上表为准（构建时 20 项源码输入与该提交逐字节一致）。

## 本轮主要改进

- 报告带证据强度、设计容量来源与置信度；charge_logger（BMS）侧信道；脱敏导出（文件名、包名、蓝牙名等）且建议类别不变。
- 三端（命令行、桌面版、两个网页）统一取值规则：内层包解析顺序、health 节点同一文件取最后一次、诊断时间跟随统计段、流量与蓝牙每份文件取首次值并由后解析的文件覆盖、多个统计段逐段合并。
- 网页：解析进度与取消；取消或首次解析失败后点“计算”会完整重新解析；重新选文件会中止进行中的解析；两页同名函数（含 async）逐字一致的回归门禁。
- 桌面版：批量汇总与 CSV、原始统计默认折叠、与命令行共用中文失败原因。

## 检查结果

| 检查 | 结果 |
|---|---|
| 构建门禁源码测试 | 115 个：113 通过，2 个真实诊断样本测试按验收范围跳过 |
| 网页逻辑回归 | 6 组全部 PASS（含 431 项真实 zip.js CRC 断言），两页 67 个同名函数逐字一致 |
| 无控制台源码自检 | 20 项通过 |
| 冻结 GUI / CLI 自检 | 各 21 项通过，退出码均为 0 |
| 冻结 CLI 补充检查 | 5 项通过（帮助、默认输入导出、中文空格相对路径输出、缺失输入、损坏 ZIP） |
| 包内文件核对 | 997 个文件逐项核对 ZIP、展开文件、SHA256SUMS 与 bundle 清单 |
| 迁移与运行环境 | 中文空格路径迁移、不同工作目录、最小 PATH、包内运行库均通过 |

## 独立复查

复查使用 Claude Code CLI，模型 `claude-opus-5-5`，effort `max`（用户指定）。2026-09-27 查询 Anthropic 官方模型页时，Opus 5.5 在当前可用模型列表中；页面另列有定位更高的 Fable 5.1，本账号调用时提示额度用尽，因此按用户指定使用 Opus 5.5。

| 轮次 | 会话 ID | 范围 | 结论 | 处理 |
|---|---|---|---|---|
| 全量复查 | `68d8e60a-0a19-41e2-b5c1-c20ff7c33d42` | `659d448..6663ac8` | 无阻塞；3 个 P2、7 个 P3 | `aec105d` 全部修复 |
| 修复复查 | `8ae30588-3b40-4167-aaac-fe8b7fd7b3f7` | `6663ac8..aec105d` | 无阻塞；1 个 P2 回退、6 个 P3 | `5462b62`、`393e3f6` 修复 |
| 终审 | `e128e3a7-9203-41f0-976c-ed9e9442bebe` | `aec105d..393e3f6` | 无 P1/P2；4 个 P3 | `2a1a625` 修复 |
| 收尾确认 | `1df97e47-d68e-45b9-95c2-a5724d6c5ebe` | `393e3f6..2a1a625` | 无阻塞，FINDINGS 为空；3 条可选建议 | 子目录 README 残留的一句已改；另两条记为后续可选项 |

另有几次复查因账号额度上限在出结论前中断，结果未采用（会话 `00dc9f25…`、`a2bc493a…` 等）。

## 清理记录

- 已移除被本次新包取代的发行目录：`dist/HyperBatteryHealthCalc-Windows-x64-20260913-002531-54e50a`（上一版，其 ZIP 仍保存在 GitHub 草稿发行 portable-20260913）以及本轮中间构建 `20260927-111644-582c01`、`20261002-181224-1564c9`、`20261008-121403-15458a`、`20261008-172652-843d4a`。
- 删除前确认要保留的新包 ZIP 哈希与上表一致，旧目录中没有链接或重解析点，也没有用户数据。
- `.build/` 下全部构建证据（含中间构建与一次失败的构建）按项目规则保留。
- 真实诊断输入、本机配置和与本项目无关的 `Microsoft/` 目录不进入源码提交。

## 后续可选项（复查提出、暂未实施）

- 为“诊断时间标记在整份文件解析成功后才设置”补一个解析中途抛错的回归测试。
- 网页用整段文本匹配 `Wifi data received:\s*(\S+)`，遇到值为空的行会把下一行的第一个词当作值（随后因无法解析而跳过）；Python 逐行解析会继续往后找。真实数据中几乎不会出现。

## 验收边界

- 实测主机为 Windows 11 Pro x64（build 26300）；其他 Windows 构建及无预装运行库的干净系统未实测。
- Windows 10 x64 未进行实机测试，用户于 2026-09-08 豁免，非阻塞；这不是实机通过声明。
- 实体 USB 文件系统及受管设备策略未验证、未豁免。
- 真实手机诊断样本不在验收范围内，两项相关测试跳过；charge_logger 解析尚未用多机型真实样本验证。
- 网页在真实浏览器中的下载落盘未单独验证；网页逻辑由 Node 回归测试覆盖。
- HawkScan 动态安全扫描未运行（本机未配置 `HAWK_API_KEY`）。
- Windows 7/8.1、32 位系统和原生 ARM64 不在本次支持范围。
