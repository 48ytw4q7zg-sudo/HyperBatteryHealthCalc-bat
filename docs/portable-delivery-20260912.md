# 便携交付索引（2026-09-12）

追加源码优化和源码层复核已完成；构建启动被宿主执行策略拒绝，尚未重新打包或推送 GitHub。状态：`source-verified-build-blocked`（更新：2026-09-13）。

用户已撤销“9 月 16 日前不推送”的限制，授权在本次整体优化和验收完成后上传。下表保留追加修改前候选包的路径和哈希，不能将其作为本次追加优化后的最新版发布。

## 追加优化与回归结果

- 两份网页都将导出报告绑定到所选文件和容量输入，输入变化后旧报告失效；清空手动容量后恢复检测值，继续复用已解析数据。
- TXT 导出保留段落、列表、表格和原始日志换行，移除按钮等界面内容，使用 UTF-8 BOM 和 CRLF；文件名限制长度并清理非法字符，下载失败后释放临时链接和对象 URL。
- 便携网页支持保存部分数据报告。单个文本日志超过 256 MiB 时在读取前拒绝；超大内层 ZIP 和手动重试中的解析遗漏进入报告警告。
- Node 原有 46 项业务断言及新增导出、输入和 ZIP 场景通过。Python 核心和功能回归共 26 项，其中 24 项通过、2 项因原真实手机诊断样本已不在当前路径而跳过。
- 两份页面均已用真实浏览器和 zip.js 解压合成诊断包：自动 5000 mAh 对应 94.00%，手动 6000 mAh 对应 78.33%，清空后恢复 5000 mAh 和 94.00%；修改输入时导出按钮隐藏。
- 浏览器已显示下载请求已发出的提示，但下载事件接口超时，未据此声称磁盘下载落地已验证。TXT 字节和下载失败清理由自动化夹具覆盖；真实手机样本复验仍未完成。

## 2026-09-13 源码层收尾

- 两份网页均可保存有实际诊断数据的部分报告；空日志、不可读日志或仅有手动容量时继续禁止导出。
- 网页文本及内层 ZIP 读取明确启用 CRC 校验；Python health 解析在提交候选前分块读至 EOF，避免采信尾部损坏的数据。
- 电池自检拒绝输出与任一输入同路径或互为别名，并要求 JSON 后缀；原子写入不覆盖原诊断或有效旧报告，错误原因和机器可读输出保持一致。
- GUI 导出测试及 smoke 依赖已纳入构建源码门禁和哈希清单，便携说明已改为使用 GUI“保存报告”。
- 解压后的诊断日志、默认 smoke 结果、环境配置和临时验收目录已从 Git 排除。
- 本机专用的 `.claude/settings.local.json` 不再纳入后续提交；本地文件保留，未读取内容，未改写历史。

| 验证组 | 最终有效结果 |
|---|---|
| Python 核心 | 6 通过，2 项真实样本测试因样本缺失而跳过 |
| 功能及输出保护 | 31 通过 |
| 便携基础与 GUI 导出 | 11 + 20 通过 |
| 网页业务及真实 zip.js CRC | 945 项显式断言通过，包含 25 个真实 CRC 场景 |
| 独立 Python 完整性复核 | 17 项通过，CRC 组合覆盖 8 个子场景 |
| 修复后 pythonw 源码自检 | 19 项通过，`frozen=false`，Python 3.14.4 x64 / Tcl-Tk 8.6.15 |

关键源码、测试、资源和构建配置的哈希已与独立复核结果逐项比对，记录在 [源码验证记录](source-verification-20260913.json)。这不代表新 EXE 或便携 ZIP 已验收。

宿主在创建进程前拒绝了本轮隔离构建启动，返回仅为 `blocked by policy`，没有更具体原因；未通过其他方式重试。浏览器合成验收目录的清理也被拒绝，该目录保留并已从 Git 排除。仍需完成新便携包构建及运行验收、更新交付路径和哈希、清理过时候选及临时目录，再同步 GitHub；下面的历史候选不能替代这些步骤。

## HyperBatteryHealthCalc

| 项 | 值 |
|---|---|
| 发行目录 | `D:\1\HyperBatteryHealthCalc-main\dist\HyperBatteryHealthCalc-Windows-x64-20260912-064031-f7e2b9` |
| ZIP | `HyperBatteryHealthCalc-Windows-x64.zip`（15,333,816 bytes） |
| ZIP SHA256 | `D0A9124C40C56E4D26CAA025AB92663BD2FE5709FD22899885D0DF1F0A2D3313` |
| 构建证据 | `.build\windows-20260912-064031-f7e2b9\evidence\` |
| 验收主机 | Windows 11 Pro 25H2，AMD64 |

解压 ZIP 后保留整个 `HyperBatteryHealthCalc` 文件夹，双击 `HyperBatteryHealthCalc.exe`；命令行用 `HyperBatteryHealthCalc-cli.exe`。

**兼容性说明**（`packaging/verify_portable.py` → `release_status`）：

- Windows 10 x64：未实机测试；用户已豁免（2026-09-08），非阻塞
- 实体 U 盘：未验证，未豁免

## EduBrain（ocsjs-ai-answer-service）

| 项 | 值 |
|---|---|
| 发行目录 | `D:\1\ocsjs-ai-answer-service\dist\EduBrain-Windows-x64-20260912-064325-306783` |
| ZIP | `EduBrain-Windows-x64.zip`（38,104,343 bytes） |
| ZIP SHA256 | `EE0F6825D4DB526FA6C21433201A14C56211B2B2ADF5116837F081AF2A4DA01C` |

完整说明与豁免字段见
`D:\1\ocsjs-ai-answer-service\docs\portable-delivery-20260912.md`。

## 仍有限制

1. Windows 10 实机启动/功能未测（已豁免）
2. 实体 USB / 受管设备策略未测
3. HyperBattery 不依赖真实模型账号；EduBrain 的真实账号/额度/计费未验证
4. Windows 7/8.1、32 位、原生 ARM64 不在范围

此前历史 ZIP / 旧 dist 清理记录保持不变；下一次构建验收后再更新交付路径与哈希，并据此清理过时候选。
