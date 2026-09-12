小米电池容量计算器：Windows x64 便携版

使用方法
1. 将整个 ZIP 解压到可写文件夹，再双击 HyperBatteryHealthCalc.exe。
2. 可以把整个 HyperBatteryHealthCalc 文件夹复制到 U 盘或其他电脑。
   必须保留 _internal 文件夹，不能只复制 EXE，也不要直接在 ZIP 内运行。
3. 把自己的诊断 ZIP 放入程序旁的 input 文件夹，点击“刷新文件列表”；
   或点击“浏览...”选择电脑上的诊断 ZIP，然后点击“开始分析”。
4. 如未能检测到设计容量，可手动填入设计容量后重新分析。
5. 分析完成后点击“保存报告”导出 TXT 并选择保存位置；数据不完整时也可保存本次快照。
   命令行批量分析与导出见下面的 CLI 入口。

适用范围
- 目标系统：Windows 10/11 64 位（x64）；32 位 Windows 和 ARM64 原生运行不在范围内。
- 已随包包含 Python 和 Tcl/Tk，目标电脑不需要安装 Python、Node、开发工具。
- 原生程序及文本说明可离线使用。这个发行包不包含网页或在线视频教程。
- 支持带空格和中文的文件夹。默认 input 和 reports 均相对于 EXE 所在位置。
- 文件夹需要可写权限；不要放在 Program Files 等受保护位置。
- 本次发行未携带真实诊断文件或个人报告。分析均在本地完成。

命令行入口（在 PowerShell 中运行）
  .\HyperBatteryHealthCalc-cli.exe --help
  .\HyperBatteryHealthCalc-cli.exe --no-color --no-pause
  .\HyperBatteryHealthCalc-cli.exe --input "D:\我的诊断" --no-pause
  .\HyperBatteryHealthCalc-cli.exe --capacity 5000 --recursive --no-pause
  .\HyperBatteryHealthCalc-cli.exe --output "reports\本次报告.txt" --no-pause

CLI 默认扫描 EXE 旁的 input，并将可提取的完整/部分快照保存为
reports\battery-report.txt。再次运行会原子替换同名报告；需要保留旧报告时，
用 --output 指定新的文件名。CLI 的相对输入/输出路径相对于 EXE 文件夹。
退出码 0 表示全部分析成功，1 表示缺失数据、坏 ZIP、无输入或导出失败；
2 表示命令参数错误。缺少容量时仍尽可能保留本次快照。

内置自检（只生成合成数据，不读取 input 里的真实文件）
  .\HyperBatteryHealthCalc.exe --self-test --self-test-output "gui-self-test.json"
  .\HyperBatteryHealthCalc-cli.exe --self-test --self-test-output "cli-self-test.json"
GUI 没有控制台；请等待进程结束后查看显式指定的 JSON 文件中的 ok 字段。
自检会临时初始化并关闭程序自己的隐藏 Tk 窗口。

验证范围与许可
- 构建主机的实际 Windows 版本和验收记录位于构建者保留的 evidence 中。
- Windows 10 x64 实机测试已由用户豁免（非阻塞）；其他 Windows 构建、无 Python 的干净虚拟机及实体 U 盘仍需单独验证。
- 此包未做代码签名。不要把“打包成功”解释为所有 Windows 版本兼容。
- 项目许可证见 LICENSE.txt，Python 许可证见 _internal\licenses\python。
  其余运行库保留随包的许可证。原项目：
  https://github.com/Hikimucheno/HyperBatteryHealthCalc
- 本便携版修改了运行路径和无控制台处理，添加了打包入口及合成自检。
