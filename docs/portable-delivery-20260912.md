# HyperBatteryHealthCalc 便携交付记录

更新：2026-09-13。状态：`release-verified`。

本次源码优化、Windows 11 x64 便携包构建及独立发行复核已完成。旧的通用进程包装命令曾被拒绝；之后通过同一执行工具提交项目原生构建入口并成功执行，没有修改审批或安全规则。

## 本次交付

| 项目 | 值 |
|---|---|
| GitHub 仓库 | [48ytw4q7zg-sudo/HyperBatteryHealthCalc-bat](https://github.com/48ytw4q7zg-sudo/HyperBatteryHealthCalc-bat) |
| 源码分支 | `master` |
| 本次发行位置 | [portable-20260913](https://github.com/48ytw4q7zg-sudo/HyperBatteryHealthCalc-bat/releases/tag/portable-20260913) |
| 本地发行目录 | `D:\1\HyperBatteryHealthCalc-main\dist\HyperBatteryHealthCalc-Windows-x64-20260913-002531-54e50a` |
| ZIP | `HyperBatteryHealthCalc-Windows-x64.zip` |
| ZIP 大小 | 14,302,765 bytes |
| ZIP SHA256 | `e7630bef8a9d7665c9ba2ba856d33768aa6605be1dfcc437178149e7ddd228ea` |
| 实际构建源码提交 | `da69b92fcca4c7cbadf7d8de70ab947ee3c7fecd` |
| 构建证据 | `.build\windows-20260913-002531-54e50a\evidence\` |
| bundle 验收记录 SHA256 | `093C8BAAC553B64B17443407E78E3FA6BBBABD44880B46E0B249786C084A911D` |

解压后保留完整的 `HyperBatteryHealthCalc` 文件夹和 `_internal`，不要直接在 ZIP 内运行，也不要只复制 EXE。Windows 便携包自带运行库，不需要安装本机 Python。

双击 `HyperBatteryHealthCalc.exe`；命令行程序为 `HyperBatteryHealthCalc-cli.exe`。分析后可通过 GUI“保存报告”，也可使用 CLI 导出。

两份电池 HTML 和答题服务 `health_smoke.py` 属于源码交付，不作为独立文件放入 EXE 包。最终源码提交可以包含本记录等文档更新；实际构建代码版本以上表为准。

## 验收与主要改进

- 网页和 Python 解析均校验日志完整性，损坏候选不覆盖有效结果。
- 两份网页及原生 GUI 支持保存有效的部分快照，输入变化会使旧报告失效。
- 自检输出不得覆盖输入 ZIP，原子保存和机器可读失败报告均已验证。
- GUI 导出测试和 smoke 依赖纳入构建源码门禁及哈希清单。

| 检查 | 结果 |
|---|---|
| 源码测试 | 68 通过，2 项真实诊断样本测试按验收范围跳过 |
| 网页逻辑与 CRC | 945 项显式断言通过，含 25 个真实 zip.js CRC 场景 |
| 独立 Python 完整性复核 | 17 项通过，CRC 组合含 8 个子场景 |
| 无控制台源码自检 | 19 项通过 |
| 新冻结 GUI / CLI | 各 20 项检查通过，退出码均为 0 |
| 冻结 CLI 补充检查 | 5 项通过 |
| 构建源码绑定 | 20 项输入与构建源码提交匹配 |

新包的 954 个文件已逐项核对 ZIP、展开文件、校验清单及 bundle 清单。中文空格路径迁移、不同工作目录、最小 PATH 和包内运行库均有通过记录。

独立审核使用 Codex `gpt-6-astra / max`，运行 ID 为 `01a09670-b319-7e60-9ccb-7c1a648289e4`，批准范围为上述精确源码与产物。详细源码哈希和检查记录见 [source-verification-20260913.json](source-verification-20260913.json)。

## 清理记录

- 已移除被本次新包替代的旧发行目录 `dist/HyperBatteryHealthCalc-Windows-x64-20260912-064031-f7e2b9`。
- 删除前确认旧归档哈希及展开文件一致，没有额外文件、重解析点或用户数据。
- 保留新发行包及全部必要构建证据。
- 已移除本轮合成浏览器验收 ZIP 及空目录。
- 本机 `.claude/settings.local.json` 仅停止 Git 跟踪，原文件保留，未读取内容或改写历史。
- 真实诊断输入、默认 smoke 结果及本地配置不进入源码提交。

## 验收边界

- 实测主机为 Windows 11 Pro x64，build 26200；其他 Windows 构建及无预装运行库的干净系统未实测。
- Windows 10 x64 未进行实机测试，用户于 2026-09-08 豁免，非阻塞；这不是实机通过声明。
- 实体 USB 文件系统及受管设备策略未验证、未豁免。
- 原真实手机诊断样本当前不在指定路径，两项相关测试跳过。
- 浏览器下载事件接口曾超时，浏览器实际落盘未单独确认；真实 Blob 字节和新冻结 GUI 的报告保存已验证。
- Windows 7/8.1、32 位系统和原生 ARM64 不在本次支持范围。
