# 小米电池健康容量计算器

解析小米 / HyperOS / MIUI 设备的 Android 诊断 ZIP，计算当前电池容量百分比，并输出中文耗电诊断。数据全部在本地处理，不上传服务器。

| 项目 | 地址 |
|------|------|
| GitHub 源码仓库 | [48ytw4q7zg-sudo/HyperBatteryHealthCalc-bat](https://github.com/48ytw4q7zg-sudo/HyperBatteryHealthCalc-bat) |
| Gitee 源码仓库 | [qinxinwei123/hyper-battery-health-calc-bat](https://gitee.com/qinxinwei123/hyper-battery-health-calc-bat) |
| 最新 Windows x64 便携包 | [Release portable-20260913](https://github.com/48ytw4q7zg-sudo/HyperBatteryHealthCalc-bat/releases/tag/portable-20260913) |
| 上游网页版 | [Hikimucheno/HyperBatteryHealthCalc](https://hikimucheno.github.io/HyperBatteryHealthCalc/) |
| 相关第三方 | 微信搜索「电池健康报告」（可检测小米、vivo、荣耀、红魔、三星） |

**当前交付状态**：源码 `master` 分支 + Windows 11 x64 便携发行 `portable-20260913`（`release-verified`）。构建源码提交 `da69b92`；ZIP SHA256 `e7630bef8a9d7665c9ba2ba856d33768aa6605be1dfcc437178149e7ddd228ea`。验收边界见 [docs/portable-delivery-20260912.md](docs/portable-delivery-20260912.md)。

---

## 系统介绍（最新版）

本项目是一套**三端共享同一套语义**的小米电池诊断分析工具：

- **网页版**：打开 `index.html` 即用，浏览器内解析嵌套诊断 ZIP，无需安装。
- **Python 桌面端（CLI / GUI）**：共享 `battery_core.py`，支持批量分析、报告导出、中文耗电诊断。
- **Windows x64 便携包**：双击 EXE 即用，自带 Python / Tcl-Tk 运行库，目标机器无需安装 Python 或 Node。

健康度核心公式为 `(最小学习容量 / 设计容量) × 100%`，并统一五档评级。三端评分边界一致；证据不足（估算设计容量、学习容量无分化等）且低于 70% 时，三端同样把评级降为「明显衰减（证据不足，待复核）」。

**电脑新手**看「新手教程」；**会终端**看「快速教程（大学生版）」。教程按**刚重装的干净 Windows x64** 编写，并写明官方验收边界（Win10 未实机、非签名包等）。

---

## 项目结构

```
HyperBatteryHealthCalc-main/                 # 本仓库根目录（GitHub master）
├── index.html                               # 根网页版（纯浏览器端）
├── js/zip.min.js                            # zip.js 压缩版（index.html 引用）
├── HyperBatteryHealthCalc-bat/              # Python 桌面子项目
│   ├── battery_core.py                      # ★ 共享核心（数据模型 / 提取器 / 评分）
│   ├── battery_calc.py                      # 命令行 CLI
│   ├── battery_gui.py                       # 图形界面 GUI (tkinter)
│   ├── report_io.py                         # 报告原子写入
│   ├── portable_entry.py                    # 便携冻结入口
│   ├── index.html                           # 网页版副本
│   ├── run.bat / run_gui.vbs                # Windows 启动脚本
│   ├── input/ reports/                      # 默认输入 / 报告目录
│   └── README.md                            # 子项目详细文档
├── packaging/                               # Windows 便携打包与门禁
│   ├── BUILD_WINDOWS.md                     # 构建说明
│   ├── PORTABLE_README.txt                  # 便携包使用说明
│   ├── windows.spec                         # PyInstaller 规格
│   ├── verify_portable.py                   # 便携验收
│   └── test_portable.py / test_gui_export.py
├── docs/                                    # 验收 / 功能完整性 / 发行记录
│   ├── functional-completion.md
│   └── portable-delivery-20260912.md        # 最新便携交付记录
├── build_windows.ps1                        # 一键 Windows 便携构建脚本
├── test_battery_core.py                     # 核心回归
├── test_functional_completion.py            # 功能完整性回归
├── test_web_logic.cjs                       # 网页逻辑回归（需 Node）
├── AGENTS.md                                # 代理协作约定
├── LICENSE                                  # Apache 2.0（根项目）
└── README.md                                # 本文件
```

---

## 运行形态总览

| 形态 | 入口 | 技术栈 | 适用场景 |
|------|------|--------|---------|
| **Windows 便携版** | Release 中 `HyperBatteryHealthCalc.exe` | 冻结 Python + Tcl/Tk | 普通用户，双击即用 |
| **网页版** | `index.html` | 纯静态 HTML + CSS + JS (zip.js) | 浏览器直接使用 |
| **命令行 (CLI)** | `HyperBatteryHealthCalc-bat/battery_calc.py` | Python 3.8+，仅标准库 | 批量处理、脚本自动化 |
| **图形界面 (GUI)** | `HyperBatteryHealthCalc-bat/battery_gui.py` | Python 3.8+ + tkinter/ttk | 源码运行，可视化操作 |
| **共享核心** | `HyperBatteryHealthCalc-bat/battery_core.py` | Python 3.8+ | 被 CLI / GUI 共同引用 |

---


## 选你的教程（按干净 Windows 写）

| 你是谁 | 看哪一段 |
|--------|----------|
| 电脑新手（约初中），要一步一步点鼠标 | **新手教程** |
| 会用终端、嫌啰嗦 | **快速教程（大学生版）** |

> **重要前提（官方验收边界，别跳过）**  
> - 便携包实测环境：**Windows 11 Pro x64**（build 26200）。  
> - **仅支持 Windows 10/11 的 64 位（x64）**。32 位 Windows、Windows 7/8.1、**原生 ARM64** 不在支持范围。  
> - **Windows 10 x64 未做实机测试**（用户已豁免，非阻塞）——不是“官方已通过 Win10”。  
> - 便携包**未做代码签名**；干净系统弹 SmartScreen 属预期，见下文。  
> - 便携包**已内置** Python、Tcl/Tk，以及 `VCRUNTIME140.dll` / `VCRUNTIME140_1.dll` 等运行库；**目标机不必再装 Python、Node、VC++ 运行库**。  
> - 包内运行库 ≠ 在任意干净虚拟机/任意 Win10 构建上都保证成功；失败请先按「干净系统排错表」自查。

### 干净系统 30 秒自检（两条路线都建议做）

1. **确认是 64 位**：设置 → 系统 → 系统信息 →「系统类型」应含 **64 位操作系统，x64**。  
   若显示 ARM64 或 32 位 → **不要继续**，本便携包跑不了。  
2. **确认可写目录**：准备例如 `D:\Tools` 或桌面文件夹；**不要**放 `C:\Program Files`。  
3. **网络**：GitHub 可能连不上；连不上就用 Gitee 或请人代下 ZIP。  
4. **手机诊断 ZIP**：没有它，工具装好也算不出健康度（导出方法见后文）。

---

## 快速教程（大学生版 · 干净系统）

> 假设：已确认 Win10/11 **x64**、会用 PowerShell、会解压。新手细节见后文。

### A. 便携包（推荐，干净机首选）

```powershell
# 1) 确认 64 位
(Get-CimInstance Win32_ComputerSystem).SystemType   # 应含 x64-based

# 2) 下载 Release 资产 HyperBatteryHealthCalc-Windows-x64.zip
#    https://github.com/48ytw4q7zg-sudo/HyperBatteryHealthCalc-bat/releases/tag/portable-20260913
#    ZIP SHA256: e7630bef8a9d7665c9ba2ba856d33768aa6605be1dfcc437178149e7ddd228ea

# 3) 解压到可写目录（示例）
New-Item -ItemType Directory -Force D:\Tools | Out-Null
Expand-Archive .\HyperBatteryHealthCalc-Windows-x64.zip -DestinationPath D:\Tools -Force

# 4) 目录结构必须是 ...\HyperBatteryHealthCalc\HyperBatteryHealthCalc.exe 且旁边有 _internal
Get-ChildItem D:\Tools\HyperBatteryHealthCalc | Select-Object Name

# 5) 先跑内置合成自检（不读真实诊断）
Set-Location D:\Tools\HyperBatteryHealthCalc
.\HyperBatteryHealthCalc-cli.exe --self-test --self-test-output "D:\Tools\cli-self-test.json"
# 打开 json 确认 ok 字段；再双击 HyperBatteryHealthCalc.exe
```

**不要：** 在 ZIP 内直接双击 EXE；只拷 EXE；删掉 `_internal`；拷到 Program Files。

**SmartScreen：** 更多信息 → 仍要运行（未签名）。

**CLI：**

```powershell
.\HyperBatteryHealthCalc-cli.exe --help
.\HyperBatteryHealthCalc-cli.exe --input "D:\diag" --no-pause --output reports\out.txt
```

退出码：0 成功 / 1 数据或导出失败 / 2 参数错误。

### B. 网页版

解压**整个仓库 ZIP**后打开根目录 `index.html`（必须保留同级 `js/zip.min.js`）。勿把单个 html 拷到桌面。

### C. 源码 CLI/GUI（干净机需要自备 Python）

- **依赖：** 仅 Python 标准库；**不需要** `pip install`。  
- **版本：** 核心逻辑 **3.8+** 即可；GUI 的 `run_gui.vbs` 在找不到解释器时提示 **请安装 Python 3.12+**——干净机**建议直接装 3.12.x 64 位**，少踩坑。  
- **必须用 python.org 官方安装器**，不要 Microsoft Store 版 Python（会话应用假 `python.exe`，命令会弹商店）。  
- 安装第一页勾选 **Add python.exe to PATH**；勾选 **tcl/tk and IDLE**（GUI 需要）。

```powershell
# 验证（必须是 64 位官方解释器，不是 WindowsApps）
Get-Command python, pythonw | Format-List Name, Source
py -3.12 -c "import sys,tkinter; print(sys.version); print(sys.maxsize>2**32)"

git clone https://github.com/48ytw4q7zg-sudo/HyperBatteryHealthCalc-bat.git
cd HyperBatteryHealthCalc-bat\HyperBatteryHealthCalc-bat
# 诊断 ZIP 放 .\input\
python .\battery_calc.py
python .\battery_gui.py
```

回归（仓库根目录）：`python -m unittest test_battery_core test_functional_completion -v`

### 环境表（已按干净系统核对）

| 路径 | 干净系统还需要装什么 |
|------|----------------------|
| 便携 GUI/CLI | **无**（无 Python/Node/VC++ 要求；包内已含 VCRUNTIME140*、python314） |
| 网页 | 仅浏览器；完整解压仓库 |
| 源码 CLI/GUI | python.org **64 位 Python**（建议 3.12，含 tcl/tk） |
| Node | 仅开发者跑 `test_web_logic.cjs` |
| 构建新便携包 | 仓库 `build_windows.ps1` + 门禁环境，见 packaging/BUILD_WINDOWS.md |

---

## 新手教程（初中水平 · 假设电脑刚重装）

下面按**一台刚重装完、什么都没装**的 Windows 电脑写。

### 第 0 步：确认电脑能不能用

1. 点 **开始菜单** → **设置** → **系统** → **系统信息**（或「关于」）。  
2. 看 **系统类型**：  
   - 写着 **64 位操作系统，基于 x64 的处理器** → 可以继续。  
   - 写着 ARM64 或 32 位 → **停止**，这个安装包不支持。  
3. 准备一个以后能随便改的文件夹，例如在 D 盘新建 `D:\Tools`。  
   **不要**放进 `C:\Program Files`。

### 第 1 步：下载安装包（不用装 Python）

1. 打开 **Microsoft Edge**（开始菜单里有）。  
2. 地址栏粘贴：  
   `https://github.com/48ytw4q7zg-sudo/HyperBatteryHealthCalc-bat/releases/latest`  
3. 回车，打开后往下找 **Assets**（资源），可能要点箭头展开。  
4. 点 **`HyperBatteryHealthCalc-Windows-x64.zip`** 开始下载。  
5. 下载完按 `Ctrl+J`，点文件夹图标，进入「下载」目录。

> GitHub 打不开：用 Gitee 仓库找同样的 Release，或让能上网的人下好后用 U 盘拷给你。  
> 当前发行 `portable-20260913`，ZIP 约 14 MB，SHA256 见发行页（可选校验）。

### 第 2 步：解压（最容易错的一步）

1. `Win+E` 打开文件资源管理器 → **下载**。  
2. 找到 `HyperBatteryHealthCalc-Windows-x64.zip`。  
3. **右键** → **全部解压缩…** → 目标改成 `D:\Tools` → 解压缩。  
4. 打开 `D:\Tools\HyperBatteryHealthCalc`，你应该**同时**看到：  
   - `HyperBatteryHealthCalc.exe`  
   - `HyperBatteryHealthCalc-cli.exe`  
   - `_internal` 文件夹  
   - `LICENSE.txt`、`README.txt`  
   - 可能还有 `input`、`reports`  

**检查清单（少一条都容易失败）：**

- [ ] 不是在压缩包里双击  
- [ ] `_internal` 还在，没有被删  
- [ ] 整个文件夹一起拷贝，不是只拷 exe  
- [ ] 不在 Program Files  
- [ ] 盘符可写（U 盘要先别拔）

### 第 3 步：第一次打开

1. **双击** `HyperBatteryHealthCalc.exe`。  
2. 若出现蓝色提示「Windows 已保护你的电脑」：  
   - 点 **更多信息**（小字）  
   - 点 **仍要运行**  
   - 原因：本包**未做代码签名**，不是病毒结论。  
3. 若杀毒软件拦截：添加信任，或换文件夹再解压一次。  
4. **出现「小米电池容量计算器」窗口 = 成功。** 没有任何窗口 → 见排错表。

### 第 4 步：（可选）自检，不连手机也能测安装

1. 进入 `D:\Tools\HyperBatteryHealthCalc`。  
2. 在地址栏输入 `powershell` 回车（会在该目录打开 PowerShell）。  
3. 粘贴：

```powershell
.\HyperBatteryHealthCalc-cli.exe --self-test --self-test-output "$env:USERPROFILE\Desktop\hbhc-self-test.json"
```

4. 到桌面用记事本打开 `hbhc-self-test.json`，找 `"ok"`，为 `true` 表示安装正常。

### 第 5 步：手机导出诊断 ZIP（没有这个算不了）

1. （推荐）手机充到 100% 再多充约 30 分钟。  
2. **方法一：** 拨号盘输入 `*#*#284#*#*`。  
3. **方法二：** 设置 → 我的设备 / 全部参数与信息 → 连续点 **「处理器」** 约 5–7 次。  
4. 等 10–30 秒。  
5. 文件管理里搜 `bugreport` 或 `诊断`，找 **ZIP**（体积较大的那个）。  
6. 用数据线 / 微信文件助手 / 小米互传拷到电脑，放到例如 `D:\Tools\HyperBatteryHealthCalc\input\`。

### 第 6 步：开始分析

**图形界面：**

1. 双击 `HyperBatteryHealthCalc.exe`。  
2. 点 **浏览…** 选诊断 ZIP，或把 ZIP 放进 `input` 后点 **刷新文件列表**。  
3. 点 **开始分析**。  
4. 看健康度和五档评级；需要保存就点 **保存报告**。

**网页版（不用装 Python）：**

1. 下载仓库 ZIP 并**完整解压**。  
2. 双击根目录 `index.html`。  
3. 选择诊断 ZIP。  
4. 若缺 `js` 文件夹导致空白页 → 说明只解压/只拷了 html，重新完整解压。

**命令行：**

```powershell
cd D:\Tools\HyperBatteryHealthCalc
.\HyperBatteryHealthCalc-cli.exe --no-pause
```

### 第 7 步：想用源码？干净机必须先装 Python（小白最容易死在这）

**一定要从官网装，不要点开始菜单里那个会弹商店的「Python」。**

1. 打开 `https://www.python.org/downloads/`  
2. 下载 **Windows installer (64-bit)**（当前建议 3.12.x）。  
3. 双击安装器 → **第一步务必勾选最下面的 Add python.exe to PATH**。  
4. 点 **Install Now**（不要选 Store 版快捷方式）。  
5. **重新打开**一个 cmd（旧窗口 PATH 不会更新）：

```bat
python --version
python -c "import sys; print(sys.maxsize>2**32)"
```

- 第二行应打印 `True`（64 位）。  
- 若 `python` 打开的是 Microsoft Store → 设置里关掉「应用执行别名」里的 python.exe，或改用 `py -3.12`。  
6. 验证 GUI 组件：

```bat
python -c "import tkinter; print('tk ok')"
```

7. 下载源码（ZIP 解压或 Git 克隆），进入 `HyperBatteryHealthCalc-bat\HyperBatteryHealthCalc-bat`：

```bat
python battery_calc.py
python battery_gui.py
```

或双击 `run.bat`。  
电池项目**不需要**安装第三方包。

### 出错了怎么办（干净系统排错表）

| 现象 | 最可能原因 | 怎么修 |
|------|------------|--------|
| 系统类型是 ARM64 | 不支持 | 换 x64 电脑；或自行找社区非官方构建（无保证） |
| 双击 exe 完全没窗口 | 只拷了 exe / `_internal` 缺失 | 重新完整解压 |
| 闪退 / 应用程序错误 | 解压损坏、盘符异常 | 重新下载 ZIP 再解压；换 `D:\Tools` |
| SmartScreen 拦截 | 未签名 | 更多信息 → 仍要运行 |
| 杀软拦截 | 误报或目录无权限 | 信任该目录；换用户可写目录 |
| 放进 Program Files 后异常 | 无写权限（报告/input） | 挪到 `D:\Tools` |
| `python` 弹出 Microsoft Store | 装了应用执行别名/Store 孪生版 | 改用官网 64 位安装器；关 alias；或 `py -3.12` |
| `python` 不是内部命令 | 没勾 Add to PATH | 重装官网 Python 并勾选；或用完整路径 |
| `tkinter` 缺失 | 装 Python 时去掉了 Tcl/Tk | 重装官方安装器并保留默认组件 |
| 网页空白/报错 zip 未定义 | 只打开单个 html，缺 `js/zip.min.js` | 完整解压仓库再打开 |
| 有窗口但读不出健康度 | 诊断包不对/损坏/太旧 | 重新用手机导出 bugreport ZIP |
| GitHub 下不动 | 网络 | Gitee 或代下 |
| Win10 上行为异常 | **未实机验证的边界** | 可尝试；不能当作官方支持声明 |

更完整边界见 [docs/portable-delivery-20260912.md](docs/portable-delivery-20260912.md)、[docs/functional-completion.md](docs/functional-completion.md)、[packaging/PORTABLE_README.txt](packaging/PORTABLE_README.txt)。

---
## 功能特点

- **本地处理**: 所有数据解析和计算在本地完成 (浏览器端/桌面端)，数据不会上传至任何服务器
- **自动检测设计容量**: 从 `android.hardware.health*.txt` 中提取 `batteryFullChargeDesignCapacityUah`，自动从 μAh ÷ 1000 转换为 mAh；health 节点读到文件尾，同一字段出现多个不同值时取最后一次并在报告中提示
- **当前容量提取**: 从 `Statistics since last charge:` 统计区块提取 `Min learned battery capacity` 作为当前实际容量
- **健康度计算**: `(当前实际容量 / 设计容量) × 100%`，五档评级
- **设备信息识别**: 提取设备型号 (`ro.product.marketname` 优先，`ro.product.model` 备用)
- **电池生命周期追踪**: 充电循环次数、估算满充容量、上次/最小/最大学习容量、系统报告满充容量、当前电量计数和充电状态
- **中文耗电诊断**: 不只计算健康度，还解析亮屏/息屏耗电、屏幕亮度分布、Doze、唤醒锁、WiFi Multicast、连接切换、UID 前台/后台耗电拆分、蓝牙耗电/扫描/连接设备、移动网络流量、Wi-Fi 流量、CPU 负载和高占用进程，生成中文建议
- **嵌套 ZIP 解析**: 自动穿透外层 ZIP 找到内层诊断 ZIP
- **结论可信度**: 报告首屏为「结论摘要」——容量比健康度、BMS SoH（如有）、系统 health 状态三口径并列；标注设计容量来源与置信度（health 节点=高、charge_logger BMS=高、batterystats 估算=中、手动填写=用户声明）和证据强度（强/中/弱），并给出满电 Charge counter 与学习容量的交叉区间
- **charge_logger（BMS）侧信道（仅桌面版）**: 自动识别诊断包内 `charge_logger*.tar/.csv/.log`，读取 `bms_chg_full / bms_chg_full_design / bms_cycle_count / battery_soh` 等字段，输出 SoH、循环次数、满充趋势（近 7/30 日变化，参考点须在 N～N×1.5 天内并标注对比日期；满充骤降时有 SoH 对照才判断“疑似校准”）、充电协议与温度（按整批中位数判断 ℃ / 0.1 ℃ 单位，剔除超出 -30～90 ℃ 的占位值）；与容量比相差超过 10 个百分点时告警“口径冲突”。BMS 设计容量不在 1000～20000 mAh、或与 batterystats 估算相差超过 30% 时不采用并提示。该格式尚未用多机型真实样本验证，识别不到字段时只提示、不猜测
- **统计窗口质量与可行动项**: 有耗电统计时标注“抓包时在充电 / 短会话 / 高亮屏占比 / 接近完整放电周期”（只有容量快照时不标注，并提示“未提供足够的结构化耗电统计”），并按影响排序给出最多 4 条本次可行动项；系统 UID（如 1041 audioserver）给系统组件建议，游戏才给画质/帧率建议
- **口径修正**: 应用耗电高于实际放电统计时不再显示“占总耗电 >100%”；power profile 与 Discharge 相差 >30% 时提示；息屏样本不足 5 分钟不下结论；Doze 为 0 标注“无样本”；连接切换在窗口已知时按每小时频率判断（≥20 次/小时且 ≥50 次），窗口未知才看总次数 ≥200；唤醒锁 0 次显示“次数未记录”；过滤 `0.0.0.0` 等伪包名，内置系统 UID 名称（1027=nfc、1041=audioserver），应用双开 `u999aNNN` 与主用户合并计算
- **导出与隐私**: TXT（默认）、JSON（机器可读，含来源/置信度/窗口质量/BMS）、批量汇总 CSV（以 `= + - @` 开头的单元格加前导单引号，防止 Excel 当作公式）；可选脱敏导出（隐藏蓝牙设备名、应用包名、进程名、唤醒锁标签、Kernel 唤醒锁中的包名、告警里的文件路径和原始统计段，文件名改为“文件1/文件2…”）；报告带文件指纹（文件名、大小、SHA256 前 12 位、解析器版本）
- **大文件**: 内层 ZIP 流式写入临时文件后解析（不再整包读入内存；Windows 上句柄关闭即由系统删除，进程被结束也不残留副本），跳过 `encrypt_voice_trigger.zip`、`*appLog.zip` 等无关包并在报告里汇总提示一次跳过数量，逐行关键字预筛；GUI 与两个网页都显示当前文件和已读 MB 并可随时取消，关窗时先取消后台解析；解析统计记录字节、耗时与进程峰值内存。54 MB 合成日志实测解析由约 24 秒降到约 4 秒
- **多个内层包的顺序**: 统计字段由后解析的包覆盖；其它内层包先解析，bugreport 包最后解析（组内按文件名排序，与旧版一致），所以文件名带日期的多份 bugreport 中日期最新的一份生效

### 五档评级标准

| 健康度 | 评级 | 色值 |
|--------|------|------|
| > 100% | 超出设计容量（可能为冗余设计或第三方电池） | `#e67e22` |
| 90% ~ 100% | 极佳状态 | `#27ae60` |
| 80% ~ 90% | 良好状态 | `#f39c12` |
| 70% ~ 80% | 正常衰减 | `#e67e22` |
| < 70% | 建议考虑更换电池 | `#e74c3c` |

> 三端 (Web/CLI/GUI) 评分边界完全一致，使用 `100.0001` 下界区分"超出"与"极佳"，避免浮点 `100.0` 的边界歧义。
>
> 低于 70% 但证据强度不是「强」（设计容量为 batterystats 估算、学习容量三值无分化、当前容量来自满电 Charge counter，或与 BMS SoH 冲突）时，评级显示为「明显衰减（证据不足，待复核）」，颜色不变；健康度百分比本身不是售后官方结论。

---

## 使用方法

当前功能收口说明与验证边界见 [功能完整性记录](docs/functional-completion.md)。网页和桌面版的手动容量会覆盖自动值；命令行 `--capacity` 保持「缺少设计容量时使用默认值」的含义。部分数据可以保留为报告，但不会据此伪造健康度。

### 获取诊断文件

1. 在小米/HyperOS 设备上进入 **设置 → 全部参数与信息 → 连续点击「处理器」**（约 5–7 次）
2. 或在拨号界面输入 `*#*#284#*#*` 一键抓包
3. 等待系统生成诊断文件（约 10–30 秒），通过文件管理器导出 ZIP

> 建议先把电量充到 100% 再继续充 30 分钟，诊断数据更准确。

### 网页版

直接用浏览器打开 `index.html`，选择诊断 ZIP 文件即可自动分析。如果自动提取设计容量失败，页面会显示手动输入框和「计算」按钮。

网页版与桌面版共用证据强度、来源置信度和各项口径修正规则（`test_web_logic.cjs` 对两个网页做一致性回归，并要求两个网页里同名的解析/诊断函数逐字相同，只放行少数界面函数）；解析大包时显示进度，可点“取消解析”；charge_logger（BMS）分析、批量汇总、JSON/CSV 与脱敏导出目前只在桌面版提供。

### 命令行版 (CLI)

```powershell
cd HyperBatteryHealthCalc-bat

# 分析 input/ 目录下所有 ZIP 文件
python battery_calc.py

# 指定输入目录
python battery_calc.py --input "C:\diagnostics"

# 指定默认设计容量（ZIP 中未检测到时使用）
python battery_calc.py --capacity 5000

# 保存报告到文件
python battery_calc.py --output report.txt

# 禁用彩色输出（重定向时）
python battery_calc.py --no-color

# 另存机器可读 JSON（含来源、置信度、窗口质量、BMS SoH；多个文件时为 {schema, reports, failures}）
python battery_calc.py --json report.json

# 生成可分享的脱敏报告，且不附原始统计段
python battery_calc.py --redact --no-raw --output share.txt

# 脚本/CI：细分退出码（0 全部完整，3 仅有部分数据或跳过，1 存在失败，2 参数错误）
python battery_calc.py --detailed-exit-codes --no-pause
```

一次分析多个 ZIP 时，终端和 `--output` 报告末尾会附「批量汇总」表（型号、健康度、证据强度、设计容量来源、循环次数、BMS SoH、统计窗口）；全部文件都失败时不写报告文件。`--json` 路径在分析前校验，不能与 `--output` 相同。`--redact` 时报告、JSON 和汇总表里的文件名都改为“文件N”。

### 图形界面版 (GUI)

```powershell
cd HyperBatteryHealthCalc-bat

# 直接运行 Python 脚本
python battery_gui.py

# 或双击 run.bat（自动调用 VBS 无窗口启动）
```

GUI 解析大包时状态栏显示已读 MB 与耗时，可点「取消」中止；「批量汇总」一次分析 input 目录全部 ZIP 并可另存 CSV，填写的设计容量与单文件分析一样覆盖自动值；「保存报告」可选 TXT 或 JSON，勾选「导出时脱敏」后保存的是脱敏版本。结果区默认折叠原始统计段（勾选「显示原始统计数据」展开），保存的报告仍包含全文。

### Windows 便携版 CLI

```powershell
.\HyperBatteryHealthCalc-cli.exe --help
.\HyperBatteryHealthCalc-cli.exe --no-color --no-pause
.\HyperBatteryHealthCalc-cli.exe --input "D:\我的诊断" --no-pause
.\HyperBatteryHealthCalc-cli.exe --capacity 5000 --recursive --no-pause
.\HyperBatteryHealthCalc-cli.exe --output "reports\本次报告.txt" --no-pause
.\HyperBatteryHealthCalc-cli.exe --json "reports\本次报告.json" --redact --no-pause
```

相对输入/输出路径相对于 EXE 所在目录。退出码：`0` 成功；`1` 缺数据/坏 ZIP/无输入/导出失败；`2` 参数错误；加 `--detailed-exit-codes` 后，只有部分数据或跳过时返回 `3`。

---

## 各文件详细说明

### 1. `index.html` — 网页版前端

纯静态 HTML + CSS + JavaScript。所有计算在浏览器本地完成，无需服务器。依赖同目录 `js/zip.min.js`。

#### 1.1 加载流程

```
浏览器打开 index.html
  └── <script src="js/zip.min.js"> 同步加载（阻塞解析）
        └── DOMContentLoaded 事件触发
              ├── addEventListener('change', handleFileSelect) on #zip-file
              └── addEventListener('click', manualCalculate) on #calculate-btn
```

#### 1.2 核心 JavaScript 调用链

```
handleFileSelect()
  ├── 重置 autoExtractedInfo (全部 null)
  ├── 隐藏 manual-input / calculate-btn / result / status
  └── parseZipAndRender(file, null)

manualCalculate()
  ├── 校验手动输入 > 0
  └── parseZipAndRender(file, manualCapacity)

parseZipAndRender(file, manualCapacity) [async]
  ├── new zip.ZipReader(new zip.BlobReader(file))
  ├── getEntries() → 遍历外层
  │     └── for each inner .zip:
  │           ├── entry.getData(new zip.BlobWriter('application/zip'))
  │           ├── new zip.ZipReader(new zip.BlobReader(innerBlob))
  │           ├── getEntries() → 遍历内层
  │           │     ├── [health .txt]:
  │           │     │     RE_DESIGN → designCapacity (μAh÷1000)
  │           │     │     RE_CYCLE  → cycleCount
  │           │     │     RE_FULL   → fullCapacity (μAh÷1000)
  │           │     └── [bugreport .txt]:
  │           │           parseBugreportText(content, info)
  │           │             ├── RE_MARKET / RE_MODEL → deviceName
  │           │             ├── RE_DUMPSTATE → reportTime
  │           │             └── [统计区块状态机]
  │           │                   └── parseStatsText(text, info)
  │           │                         ├── RE_ESTIMATED → estimatedCapacity
  │           │                         ├── RE_LAST → lastLearnedCapacity
  │           │                         ├── RE_MIN → minLearnedCapacity
  │           │                         └── RE_MAX → maxLearnedCapacity
  │           ├── [提前退出] if designCap && minLearned
  │           └── innerReader.close()
  ├── buildFullReport(info) → HTML 报告
  │     ├── getRatingText(pct) / getRatingColor(pct) ← 统一 RATING_TABLE
  │     ├── escHtml() 防 XSS
  │     └── translateStats() 翻译对照
  └── showResult(div, html, true) → innerHTML + className
```

#### 1.3 关键 CSS 选择器

| 选择器 | 设计意图 |
|--------|---------|
| `body` | 固定宽度 800px 居中，Misans 小米定制字体 |
| `.container` | 白→浅灰渐变卡片，12px 圆角，多层阴影 |
| `.instructions` | 蓝→绿渐变信息块，左侧 5px 蓝色竖条 |
| `.file-upload input` | 2px 虚线边框，hover 变蓝 |
| `button` | 绿渐变按钮，hover 上浮 1px + 阴影加深 |
| `.success` | 成功结果：绿边框 + 浅绿背景 |
| `.error` | 错误结果：红边框 + 浅红背景 |
| `.toggle-btn` | 蓝渐变折叠按钮（与绿色主按钮区分） |
| `.original-text` | 500px 最大高度滚动区，WebKit 自定义滚动条 |

#### 1.4 安全性

- **XSS 防护**: `escHtml()` 通过 `textContent` → `innerHTML` 转义所有用户数据
- **本地处理**: 所有解析在浏览器本地完成，数据不上传
- **无 `eval()`**: 不使用任何动态代码执行

---

### 2. `HyperBatteryHealthCalc-bat/battery_core.py` — 共享核心模块

被 `battery_calc.py` (CLI) 和 `battery_gui.py` (GUI) 共同引用。包含三大组件：

#### 2.1 `BatteryInfo` 数据类

当前数据模型已经从“容量快照”扩展为“容量 + 硬件状态 + 耗电诊断”三层。基础容量字段如下：

| 字段 | 类型 | 来源 | 说明 |
|------|------|------|------|
| `design_capacity` | `float\|None` | `android.hardware.health*.txt` | 设计容量 (mAh)，μAh÷1000 |
| `design_capacity_auto` | `bool` | 程序标记 | True=自动, False=手动 |
| `cycle_count` | `int\|None` | `android.hardware.health*.txt` | 充电循环次数 |
| `full_capacity` | `float\|None` | `android.hardware.health*.txt` | 满充容量 (mAh) |
| `device_name` | `str\|None` | `bugreport*.txt` | 设备名称 (marketname 优先) |
| `report_time` | `str\|None` | `bugreport*.txt` | 诊断报告时间 |
| `estimated_capacity` | `float\|None` | 统计区块 | 估算满充容量 |
| `last_learned_capacity` | `int\|None` | 统计区块 | 上次学习容量 |
| `min_learned_capacity` | `int\|None` | 统计区块 | **最小学习容量 → 当前容量** |
| `max_learned_capacity` | `int\|None` | 统计区块 | 最大学习容量 |
| `statistics` | `str\|None` | 统计区块 | 原始统计文本 |

扩展诊断字段按来源分组：

| 分组 | 代表字段 | 用途 |
|---|---|---|
| 当前硬件快照 | `charge_counter`, `battery_level`, `voltage_mv`, `temperature_c`, `status_code`, `health_code`, `max_charging_current_ma`, `max_charging_voltage_mv` | 解释当前电量、温度、充电状态和满电低功率补电 |
| 屏幕/待机耗电 | `screen_on_seconds`, `screen_off_seconds`, `screen_on_discharge_mah`, `screen_off_discharge_mah`, `screen_doze_discharge_mah`, `device_deep_doze_discharge_mah`, `screen_brightnesses` | 判断亮屏、息屏、屏幕亮度分布、屏幕 Doze 和深度 Doze 的耗电占比 |
| 唤醒锁与连接 | `partial_wakelock_seconds`, `kernel_wakelocks`, `partial_wakelocks`, `wifi_multicast_wakelock_seconds`, `connectivity_changes` | 判断后台常驻、投屏/局域网发现、弱网或频繁切换导致的耗电 |
| UID 应用耗电 | `top_uid_power`, `uid_packages`, `foreground_mah`, `background_mah`, `foreground_service_mah` | 找出高耗电应用/系统 UID，并区分前台、后台、前台服务耗电 |
| 网络/蓝牙 | `cellular_received_bytes`, `cellular_sent_bytes`, `cellular_kernel_active_seconds`, `wifi_received_bytes`, `wifi_sent_bytes`, `bluetooth_drain_mah`, `bluetooth_connected_devices` | 区分移动网络、Wi-Fi、蓝牙设备和扫描造成的耗电 |
| CPU 快照 | `cpu_load_1m`, `cpu_load_5m`, `cpu_load_15m`, `top_cpu_processes` | 输出当前 CPU 负载和瞬时高占用进程 |

计算属性:
- `has_design_capacity` → `design_capacity is not None and design_capacity > 0`
- `current_capacity` → 优先返回 `min_learned_capacity`；满电且缺少学习容量时可用 `charge_counter` 兜底
- `current_capacity_source` → 说明当前容量来自最小学习容量还是满电电量计数
- `health_percentage` → `(min_learned / design_capacity) * 100`
- `usage_diagnostics` → 返回面向用户的中文诊断结论列表

#### 2.2 评分逻辑（第 54-76 行）

五档查找表（不可变 `tuple`），每项 `(下界, 上界, 评级文本, 色值)`：

```python
_RATING_TABLE = (
    (100.0001, float('inf'), '超出设计容量...', '#e67e22'),
    (90,       100,          '极佳状态',        '#27ae60'),
    (80,       90,           '良好状态',        '#f39c12'),
    (70,       80,           '正常衰减',        '#e67e22'),
    (0,        70,           '建议考虑更换电池',  '#e74c3c'),
)
```

导出函数：
- `get_rating_text(percentage) -> str`
- `get_rating_color(percentage) -> str`

#### 2.3 `BatteryExtractor` 提取器类

逐行流式处理 ZIP，使用预编译正则提取容量、硬件快照和耗电诊断。调用链：

```
extract(zip_path) → BatteryInfo
  ├── _find_inner_zips(outer_zip) → 所有 .zip 文件名
  ├── for each inner zip:
  │     ├── outer_zip.read(name) → BytesIO
  │     ├── zipfile.ZipFile(BytesIO)
  │     ├── _find_file('android.hardware.health', '.txt')
  │     ├── _find_file('bugreport', '.txt')
  │     ├── _parse_health_stream() → 设计容量/循环次数/满充容量
  │     │     └── 逐行正则: RE_DESIGN_CAPACITY / RE_CYCLE_COUNT / RE_FULL_CAPACITY
  │     ├── _parse_bugreport_stream() → 设备名/时间/统计区块
  │     │     ├── RE_MARKET_NAME / RE_MODEL → device_name
  │     │     ├── RE_REPORT_TIME → report_time
  │     │     └── 统计区块状态机 → _parse_stats_text()
  │     │           ├── RE_ESTIMATED → estimated_capacity
  │     │           ├── RE_LAST_LEARNED → last_learned_capacity
  │     │           ├── RE_MIN_LEARNED → min_learned_capacity
  │     │           └── RE_MAX_LEARNED → max_learned_capacity
  │     │           ├── 屏幕亮度/Doze/耗电构成/唤醒锁
  │     │           ├── 移动网络/Wi-Fi 流量和活跃时间
  │     │           ├── 蓝牙耗电/扫描/连接设备
  │     │           └── CPU 负载和高占用进程
  │     └── [提前退出] has_design_capacity && current_capacity → break
```

---

### 3. `HyperBatteryHealthCalc-bat/battery_calc.py` — 命令行版（314 行）

无第三方依赖，引用 `battery_core.py`。

**关键模块**:

| 类/函数 | 行号 | 功能 |
|---------|------|------|
| Windows GBK 容错 | 19-24 | `TextIOWrapper(errors='replace')` 避免 emoji 崩溃 |
| `Colors` | 30-64 | 终端颜色控制 (VT100/Windows ANSI)，自动检测 TTY |
| `ReportPrinter` | 68-128 | 格式化输出 + ANSI 剥离 |
| `prompt_design_capacity()` | 142-164 | 交互式设计容量输入（仅 TTY 模式） |
| `build_parser()` | 168-192 | argparse 参数定义 |
| `main()` | 194-290 | 主循环：扫描 → 提取 → 报告 → 写入文件 |

**命令行参数**:

```
-i, --input PATH    输入目录（默认: ./input）
-c, --capacity NUM  默认设计容量 (mAh)
-o, --output PATH   报告输出文件
--no-color          禁用彩色输出
```

**main() 流程**:

```
main(argv) → int
  ├── parse_args()
  ├── 扫描 input_dir/*.zip
  ├── for each zip:
  │     ├── extractor.extract() → BatteryInfo
  │     ├── 缺设计容量 → args.capacity 或 prompt_design_capacity()
  │     ├── 缺当前容量 → 跳过
  │     └── printer.print_report() → 终端 + all_reports
  ├── --output → 写入文件 (UTF-8, --- 分隔多个报告)
  └── return 0 if failed == 0 else 1
```

---

### 4. `HyperBatteryHealthCalc-bat/battery_gui.py` — 图形界面版（362 行）

基于 tkinter + ttk，引用 `battery_core.py`。

**DPI 感知**: Windows 平台自动调用 `SetProcessDpiAwareness(1)` 解决高分屏模糊。

**UI 组件树**:

```
root (tk.Tk, bg='#f8f9fa', 720×620)
└── main (ttk.Frame)
    ├── title_frame → ttk.Label("小米电池容量计算器", 18pt bold)
    ├── note_frame → tk.Label(说明, bg='#ebf8ff')
    ├── file_frame (ttk.LabelFrame)
    │   ├── file_combo (ttk.Combobox) + "浏览..." (ttk.Button)
    │   └── capacity_entry (ttk.Entry, 手动设计容量)
    ├── btn_frame
    │   ├── analyze_btn (tk.Button, 绿色)
    │   └── refresh_btn (tk.Button, 蓝色)
    ├── status_lbl (tk.Label, 状态提示)
    ├── result_frame (ttk.LabelFrame)
    │   ├── result_text (tk.Text, Consolas 10pt)
    │   └── scrollbar (ttk.Scrollbar)
    └── footer (tk.Label, 版权信息)
```

**核心方法**:

| 方法 | 功能 |
|------|------|
| `_build_ui()` | 构建全部 UI 组件 |
| `_refresh_file_list()` | 扫描 input/ 目录，刷新下拉列表 |
| `_browse_file()` | 文件选择对话框 |
| `_analyze()` | 核心分析流程：提取 → 校验 → 报告 |
| `_build_report(info)` | 生成纯文本报告 |
| `_build_error_report(info)` | 部分信息展示（提取不完整时） |
| `_highlight_result()` | tkinter Text tag 高亮健康度行（按评级着色） |

---

### 5. `HyperBatteryHealthCalc-bat/run.bat` — Windows 启动脚本（3 行）

```batch
start "" wscript //nologo "%~dp0run_gui.vbs"
exit /b 0
```

- `start ""` — 空窗口标题，避免路径被误解为标题
- `wscript //nologo` — GUI 模式 Windows Script Host (无 CMD 窗口)
- `%~dp0` — 批处理参数扩展，得到脚本所在目录绝对路径
- `exit /b 0` — 退出批处理，不关闭父 CMD

**调用链**: 双击 `run.bat` → `start wscript` → `run_gui.vbs` → `pythonw/python` → `battery_gui.py`

---

### 6. `HyperBatteryHealthCalc-bat/run_gui.vbs` — VBS 无窗口启动（14 行）

三级降级策略：

```
第一级: ws.Run "pythonw ...battery_gui.py", 0, False
  └── pythonw.exe (无控制台窗口, 隐藏模式)
       ↓ 失败 (Err.Number <> 0)
第二级: ws.Run "python ...battery_gui.py", 1, False
  └── python.exe (正常窗口, 短暂 CMD)
       ↓ 失败
第三级: MsgBox "Python/tkinter not found. Please install Python 3.7+", 48, "Error"
  └── 弹出错误消息框 (vbExclamation 警告图标)
```

---

### 7. `js/zip.min.js` / `js/zip.min.js` — 浏览器 ZIP 解析库

使用 [@gildas-lormeau/zip.js](https://github.com/gildas-lormeau/zip.js) (BSD 3-Clause 许可)。

**index.html 中实际调用的 API**:

| API | 调用位置 | 用途 |
|-----|---------|------|
| `new zip.ZipReader(reader)` | handleFileSelect / parseZipAndRender | ZIP 读取器 |
| `new zip.BlobReader(blob)` | handleFileSelect / parseZipAndRender | 将 File/Blob 转为 Reader |
| `new zip.BlobWriter(mimeType)` | 内层 ZIP 读取 | 输出为 Blob (嵌套 ZIP) |
| `new zip.TextWriter()` | 文本文件读取 | 输出为 UTF-8 字符串 |
| `reader.getEntries()` | 外层 + 内层遍历 | 异步获取条目列表 |
| `entry.getData(writer)` | 读取条目内容 | 异步读取到 Writer |
| `reader.close()` | 清理 | 释放底层资源 |

---

### 8. 其他配置文件

| 文件 | 用途 |
|------|------|
| `.gitignore` | Python 生态标准 (139行)，覆盖 `__pycache__/`, `*.py[cod]`, `venv/`, `dist/`, 各种 IDE |
| `LICENSE` | 根项目 Apache 2.0；bat 子项目 GPLv3 |
| `.github/FUNDING.yml` | `custom: ['http://119.29.227.6/pay']` |
| `.gitee/ISSUE_TEMPLATE.zh-CN.md` | 问题原因 / 重现步骤 / 报错信息 |
| `.gitee/PULL_REQUEST_TEMPLATE.zh-CN.md` | 关联 Issue / 原因 / 描述 / 测试用例 |

---

## 统一数据流（三端）

```
用户获取诊断 ZIP
      │
      ▼
┌─────────────────────────────────────────────────────────┐
│                    入口层（三选一）                       │
│  Web: handleFileSelect() → parseZipAndRender()          │
│  CLI: main() → extractor.extract()                      │
│  GUI: _analyze() → extractor.extract()                  │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│          第一层 ZIP 解析 — 穿透外层 ZIP                   │
│  Web: zip.ZipReader + BlobReader                         │
│  CLI/GUI: zipfile.ZipFile + namelist()                   │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│          第二层 ZIP 解析 — 内层诊断 ZIP                    │
│  文件名匹配: 'android.hardware.health' + '.txt'          │
│             'bugreport' + '.txt'                         │
└──────────────────────┬──────────────────────────────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
┌──────────────┐ ┌───────────┐ ┌─────────────────────────┐
│ health 文件   │ │ bugreport  │ │ [提前退出]               │
│ 设计容量      │ │ 设备名     │ │ has_design_capacity     │
│ 循环次数      │ │ 时间戳     │ │ && current_capacity     │
│ 满充容量      │ │ 统计区块   │ │ → break                 │
└──────┬───────┘ └─────┬─────┘ └─────────────────────────┘
       │               │
       └───────┬───────┘
               ▼
      [设计容量缺失?]
      ├─ 是 → CLI: --capacity / 交互输入
      │       GUI: 手动输入框
      │       Web: 显示手动模式
      └─ 否 → 继续
               ▼
┌─────────────────────────────────────────────────────────┐
│              健康度计算 & 报告生成                        │
│  current = min_learned_capacity                         │
│  health% = (current / design) × 100                     │
│  rating = RATING_TABLE 五档查找                          │
│  Web: innerHTML (escHtml 防 XSS)                        │
│  CLI: ANSI 彩色终端 + --output 文件                      │
│  GUI: tk.Text (tag 高亮)                                │
└─────────────────────────────────────────────────────────┘
```

---

## 三端实现差异对照表

| 功能点 | Web (`index.html`) | CLI (`battery_calc.py`) | GUI (`battery_gui.py`) |
|--------|-------------------|------------------------|----------------------|
| 核心逻辑 | 独立 JS（等价实现） | `from battery_core import *` | `from battery_core import *` |
| ZIP 解析库 | zip.js (第三方) | `zipfile` (标准库) | `zipfile` (标准库) |
| 正则引擎 | JS `const RE_*` 顶层声明 | `battery_core` 类变量预编译 | `battery_core` 类变量预编译 |
| 评分表 | 统一 `RATING_TABLE` | 统一 `_RATING_TABLE` | 统一 `_RATING_TABLE` |
| 评分边界 | `[100.0001, Infinity]` | `(100.0001, inf)` | `(100.0001, inf)` |
| 浮点容量处理 | `Math.round(parseFloat())` | `round(float())` | `round(float())` |
| 提取器提前退出 | ✓ | ✓ | ✓ |
| 设计容量降级 | 手动输入框 | `--capacity` / 交互输入 | 手动输入框 |
| fullCapacity 显示 | ✓ | ✓ | ✓ |
| 多文件批量 | ✗ | ✓ | ✗ |
| 防 XSS | `escHtml()` | N/A (终端输出) | N/A (原生控件) |
| DPI 感知 | N/A | N/A | ✓ `SetProcessDpiAwareness` |

---

## 环境要求

| 组件 | 要求 |
|------|------|
| **Windows 便携包** | Windows 10/11 x64；无需本机 Python/Node；需可写目录 |
| **网页版** | 现代浏览器 (Chrome/Firefox/Edge/Safari)，支持 ES6 + Blob API |
| **CLI 版（源码）** | Python 3.8+，仅标准库 |
| **GUI 版（源码）** | Python 3.8+ + tkinter（Windows 安装器通常自带） |
| **构建便携包** | Windows x64 CPython（含 Tk）+ Node（仅源码门禁测试）+ PowerShell 5.1+ |

---

## 注意事项

- 本工具仅通过解析系统诊断文件估算电池容量，结果仅供参考，不具备官方检测效力
- 若设备出现异常，请前往小米官方售后处理
- 不同版本的 HyperOS/MIUI 系统可能导致诊断文件格式略有差异
- 如果电池不是小米官方正品配件，计算结果可能不准确

> 锂电池因充放电循环、使用环境和习惯出现容量衰减是通用物理特性，并非小米设备独有。建议理性看待正常损耗，有疑问可通过官方售后检测。

---

## 常见问题

**Q: 为什么上传文件后没有反应？**
- 诊断文件可能损坏，请重新导出
- 浏览器兼容性问题，建议使用 Chrome、Edge 等主流浏览器

**Q: 初始电池容量在哪里查询？**
- 可在设备的官方参数页面、产品说明书中查询

**Q: 计算结果与实际感受差距较大怎么办？**
- 建议在不同电量状态下多次测试，取平均值
- 检查操作是否有误
- 尝试更新设备系统后重新导出

---

## 开源依赖

| 依赖 | 许可证 | 用途 |
|------|--------|------|
| [zip.js](https://github.com/gildas-lormeau/zip.js) | BSD 3-Clause | 网页版浏览器端 ZIP 解析 |
| Python 标准库 | PSF License | CLI/GUI 版全部运行时依赖 |
| PyInstaller（仅构建） | GPL/exception | Windows 便携包打包，见 `packaging/requirements-build.txt` |

源码运行不依赖任何第三方 Python 包。克隆仓库后直接运行即可。

---

## 许可证

- 根项目 (`index.html`): Apache License 2.0
- 子项目 (`HyperBatteryHealthCalc-bat/`): GNU General Public License v3 (GPLv3)

Copyright © HikiMu慕鱼酱

---

## 贡献

欢迎参与项目改进。可在 GitHub 仓库提交 Issue / Pull Request：

1. Fork 本仓库
2. 创建分支：`git checkout -b fix/short-desc`
3. 提交改动（保持 CLI/GUI/报告契约稳定；勿提交真实诊断 ZIP 或个人日志）
4. 推送分支并在 GitHub 打开 PR
5. 在 PR 中说明改动、验证命令与结果

本地变更请勿直接强推他人的 `master`。

## 免责声明

本工具仅为估算电池容量提供参考，不具备官方检测效力。若设备出现电池异常、续航锐减等问题，请前往小米官方线下售后网点进行专业检测和处理，本工具计算结果不作为售后依据。
