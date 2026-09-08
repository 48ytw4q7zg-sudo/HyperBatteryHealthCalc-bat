# 两个项目的便携交付索引

更新日期：2026-09-08。

## 交付范围与使用方式

本次目标平台为 Windows 10/11 x64。用户已明确允许省略 Windows 10 实机测试，因此该项为“未验证，用户已豁免”，不是已测试通过。Windows 7/8.1、32 位及原生 ARM64 不在本次范围内。

两个程序均以完整文件夹交付。将 ZIP 完整解压后，把整个程序文件夹复制到 U 盘或另一台电脑，保留内部运行库和资源，不能只复制单个 EXE。启动不要求额外安装 Python、Node.js、Docker 或编程工具。报告和设置需要可写的目标目录。已验证中文/空格路径、换目录运行和 Windows 11 隔离环境；未声称完成实体 U 盘实测。

电池分析可以离线处理本地日志。EduBrain 的界面和本地服务可独立启动，但调用远程 AI 仍需要可用网络和用户自己的服务配置；“无需编程环境”不等于“远程 AI 无需账号或网络”。

## 最终用户交付

| 项目 | 交付版本 | ZIP 字节数 | 入口 |
| --- | --- | ---: | --- |
| HyperBatteryHealthCalc | 20260907-145748-f98fd2 | 15,373,606 | HyperBatteryHealthCalc.exe |
| EduBrain | 20260907-141124-4a1515 | 38,100,164 | EduBrain.exe |

电池包：[HyperBatteryHealthCalc-Windows-x64.zip](D:/1/HyperBatteryHealthCalc-main/dist/HyperBatteryHealthCalc-Windows-x64-20260907-145748-f98fd2/HyperBatteryHealthCalc-Windows-x64.zip)

电池 ZIP SHA256：`9086622D48D4E43920486EA5B24AA7FE4D701A1C541A0CE3C3C4C0269AEE609D`。

服务包：[EduBrain-Windows-x64.zip](D:/1/ocsjs-ai-answer-service/dist/EduBrain-Windows-x64-20260907-141124-4a1515/EduBrain-Windows-x64.zip)

服务 ZIP SHA256：`5FA373BAF7C54AC2CA1E76EBE783FB7DFDD3D2819EB77FB97C176F5243D70107`。

另一个电池包 `20260907-164957-a00d0d` 用于证明修复后的 Windows PowerShell 5.1 打包流程可用。本索引没有把原交付版本的手工界面或隔离环境结果冒用到新二进制上，因此仍选用完整运行证据绑定的 `145748-f98fd2` 作为用户交付。

## 关键成果与证据

| 项目 | 已记录的成果 | 验收证据 |
| --- | --- | --- |
| 电池分析 | 日志解析、健康/容量统计、诊断输出、GUI/CLI/浏览器相关逻辑 | 35 项构建测试通过；44 项浏览器逻辑断言通过；私有真实日志测试另行运行 |
| 保存报告 | 保存、取消、重试、输入变更失效、原 ZIP 保护、UTF-8 BOM/CRLF | 20 项新导出测试；31 项相关回归通过；实际原生保存对话框通过 |
| 真实手机文件 | 2026-06-23 的 Xiaomi 15 Pro 日志快照 | 两项真实数据测试通过；6100 mAh 为日志估算参考，4760 mAh 为学习容量，健康比例约 78.03%，不是当前实测健康 |
| 电池便携运行 | 自带运行库与 Tk 资源，无开发环境启动 | Windows 11 隔离环境 GUI/CLI 各 20 项检查通过 |
| EduBrain | 配置回滚、重试边界、接口兼容、会话保护、便携设置、资源完整性 | 源码/接口/浏览器/SDK 与打包报告分别列出范围，不以单一测试替代全部功能 |
| EduBrain 便携运行 | 自带运行库、离线界面资源和 API 文档 | Windows 11 隔离环境 GUI/console 各 21 项检查通过 |
| 打包完整性 | 冻结前后快照与受审输入哈希绑定；PS5.1 引号修复 | 两组独立审核及实际构建证据 |

## 详细验收记录

- [电池保存与真实数据验收](D:/1/HyperBatteryHealthCalc-main/docs/gui-save-and-real-data-acceptance-20260908.md)
- [Windows PowerShell 5.1 打包验收](D:/1/HyperBatteryHealthCalc-main/docs/ps51-build-acceptance-20260908.md)
- [EduBrain 便携验收](D:/1/ocsjs-ai-answer-service/docs/windows-portable-acceptance-20260907-current.md)
- [当前文件一致性证据](D:/1/HyperBatteryHealthCalc-main/.build/final-closeout-20260908-win10-waived/current-state-evidence.json)
- [逐项验收要求](D:/1/HyperBatteryHealthCalc-main/.build/final-closeout-20260908-win10-waived/requirements.json)

## 审核与执行边界

最终独立审核的目标配置为 `gpt-6-astra / max`，新启动的审核请求使用一次性 `service_tier=fast`，不修改全局默认。Fast 是执行设置，不是改用较低能力模型。桌面当前任务的 Fast 按钮此前因 Escape 中止而未确认，不能以命令行配置声称桌面也已切换。实际后端处理档位及计费身份以服务返回为准，不能从自定义路由名推断。

正式结论请结合 [独立审核](D:/1/HyperBatteryHealthCalc-main/.build/final-closeout-20260908-win10-waived/gpt6-final-review.md) 与 [执行回执](D:/1/HyperBatteryHealthCalc-main/.build/final-closeout-20260908-win10-waived/gpt6-final-review-receipt.json)。单独存在本交付索引，不代表尚未结束的审核已经通过。

Claude Code 与 pi 的 Sol/max 小任务成功结果保留；pi 程序包修复通过用户批准的入口完成。未修改应用提供商默认值、密钥、主机安全设置或原始手机日志。

历史失败与跳过均保留在详细报告：首个电池隔离用例未完成、首次短路径环境回归失败、旧打包引号错误及一次审核输出截断，均未伪装为通过。新增成功证据只支持其实际检查过的范围。

