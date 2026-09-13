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

健康度核心公式为 `(最小学习容量 / 设计容量) × 100%`，并统一五档评级。三端评分边界一致。

**电脑新手请直接往下看「新手教程：一步一步装好并用起来」**（按初中生电脑水平写，含下载、解压、双击运行、手机导出诊断包、排错表）。

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

## 新手教程：一步一步装好并用起来

> 下面按「电脑新手 / 初中生也能跟着点」写。每一步都写清楚：打开哪个网页、点哪个按钮、文件放哪里、看到什么算成功。  
> 如果你只想**马上看电池健康度**，走 **路线一** 或 **路线二**，大约 5–10 分钟，**不用装 Python**。

### 先认识几个词（会了就不怕）

| 词 | 白话解释 |
|----|----------|
| **浏览器** | 上网的软件，Windows 自带 **Microsoft Edge**（蓝色 e 图标），也可以用 Chrome |
| **ZIP 压缩包** | 把很多文件打包成一个文件，像书包。需要先「解压」才能用里面的东西 |
| **解压** | 把书包里的东西拿出来。Windows 自带解压功能 |
| **双击** | 鼠标左键快速点两下 |
| **文件夹路径** | 文件住在哪一层，例如 `C:\Users\你\Desktop` 表示桌面 |
| **GitHub** | 存放本项目源码和安装包的网站。本仓库地址见文首表格 |
| **Release / 发行版** | 作者打包好的「安装包」，下载 ZIP 即可，一般不用自己编译 |
| **诊断 ZIP** | 小米手机导出的系统日志压缩包，本工具要分析的就是它 |

### 路线怎么选（只选一条）

| 你的情况 | 走哪条 | 大概要什么 |
|----------|--------|------------|
| 只想看自己手机电池健康，会下载解压就行 | **路线一：下载 Windows 便携版** | 一台 Windows 10/11 电脑 |
| 电脑暂时不便解压，或想先在浏览器里试试 | **路线二：网页版** | 浏览器 |
| 想自己改代码、批量处理、或学习源码 | **路线三：从 GitHub 跑源码** | 再装 Git + Python |

**普通用户请优先走路线一。** 路线三步骤多，但每一步都写了。

---

### 路线一：下载 Windows 便携版（推荐新手）

#### 1.1 打开下载页面

1. 打开 **Microsoft Edge**（或 Chrome）。  
2. 在顶部地址栏粘贴下面网址，按 **回车**：  
   `https://github.com/48ytw4q7zg-sudo/HyperBatteryHealthCalc-bat/releases/latest`  
3. 你会看到标题类似 **HyperBatteryHealthCalc Windows x64 portable 2026-09-13** 的页面。  
4. 往下滚，找到 **Assets（资源）** 一栏，可能要点一下箭头展开。

#### 1.2 下载哪几个文件

1. 点 **`HyperBatteryHealthCalc-Windows-x64.zip`**，浏览器开始下载。  
2. （可选但建议）再点一下 **`SHA256SUMS.txt`**，这是校验文件，新手可先跳过。  
3. 下载完成后，点浏览器右上角 **下载图标**，或按 `Ctrl+J` 打开下载列表。  
4. 记住文件在哪个文件夹（通常是 **下载** 文件夹）。

> 若 GitHub 打不开：可改用 Gitee 仓库页找 Release，或请网络好的人代下 ZIP 后用 U 盘拷给你。

#### 1.3 解压（不要只解压一半）

1. 打开 **文件资源管理器**（任务栏文件夹图标，或按 `Win+E`）。  
2. 进入 **下载** 文件夹。  
3. 找到 `HyperBatteryHealthCalc-Windows-x64.zip`。  
4. **右键单击** 该文件 → 选 **全部解压缩…**（Windows 11）或 **解压到 HyperBatteryHealthCalc-Windows-x64\**（若装了其他解压软件）。  
5. 解压目标建议改成例如：  
   `D:\电池工具`  
   或直接解压到 **桌面** 也可以。  
6. 点 **解压缩**，等待完成。

**非常重要（新手最容易错）：**

- 要进入解压出来的**文件夹**里运行程序，**不要**在 ZIP 里直接双击 EXE。  
- 要把**整个文件夹**一起拷走，**不能**只拷 `HyperBatteryHealthCalc.exe` 一个文件。  
- 文件夹里必须一直带着 **`_internal`**，删了就打不开。  
- 不要把程序放进 `C:\Program Files` 这种系统目录，会没权限。

#### 1.4 打开程序

1. 打开解压后的文件夹，直到能看到：  
   `HyperBatteryHealthCalc.exe`  
   `HyperBatteryHealthCalc-cli.exe`  
   `_internal` 文件夹  
   `input` 文件夹（没有的话程序可能会自动建）  
2. **双击 `HyperBatteryHealthCalc.exe`**。  
3. 若弹出「Windows 已保护你的电脑」：  
   - 点 **更多信息**  
   - 再点 **仍要运行**  
   - （因本包未做代码签名，属正常现象）  
4. 成功时会出现图形窗口，标题类似「小米电池容量计算器」。  
   **看到窗口 = 安装成功。**

#### 1.5 命令行版（可选）

想批量分析时，可在**该文件夹空白处**按住 `Shift` + **右键** → **在此处打开 PowerShell 窗口**，然后输入：

```powershell
.\HyperBatteryHealthCalc-cli.exe --help
```

看到帮助文字即成功。详细参数见后文「使用方法」。

---

### 路线二：只用网页版（不用装 Python）

#### 2.1 拿到 index.html

任选一种：

**方法 A（推荐）：直接下载仓库 ZIP**

1. 浏览器打开：  
   `https://github.com/48ytw4q7zg-sudo/HyperBatteryHealthCalc-bat`  
2. 点绿色 **Code** 按钮 → **Download ZIP**。  
3. 解压到例如 `D:\电池网页版`。  
4. 在解压后的文件夹里找到 **`index.html`**。

**方法 B：已有完整源码仓库**  
进入仓库根目录，那里也有 `index.html`。

#### 2.2 打开网页并选择诊断文件

1. **双击 `index.html`**，会用默认浏览器打开。  
2. 页面上找到 **选择文件 / 上传** 的按钮，点击它。  
3. 在弹出窗口中选中手机导出的 **诊断 ZIP**。  
4. 等待几秒到十几秒，页面出现绿色结果区 = 成功。  
5. 若自动识别失败，页面会提示手动输入「设计容量」（例如手机标称 5000 mAh），填入后点 **计算**。

> 注意：网页版依赖同目录下的 `js/zip.min.js`。请解压**整个文件夹**，不要只把 `index.html` 单独拷到桌面。

---

### 路线三：从 GitHub 跑源码（想折腾的人）

下面仍按「完全没配过环境」写。

#### 3.1 先装 Git（用来下载代码）

1. 打开：`https://git-scm.com/download/win`  
2. 下载 **64-bit Git for Windows Setup**。  
3. 双击安装。安装向导里一路 **Next / Install** 即可；若问「Adjust PATH」，保持默认。  
4. 装完后：按 `Win+R`，输入 `cmd`，回车，在黑窗口里输入：  
   `git --version`  
5. 看到类似 `git version 2.x` = 装好了。

#### 3.2 再装 Python（用来运行程序）

1. 打开：`https://www.python.org/downloads/`  
2. 点黄色按钮下载最新 **Windows installer (64-bit)**。  
3. 双击安装。**第一个画面务必勾选底部的：**  
   **Add python.exe to PATH**  
   （这一步漏了，后面会提示「不是内部或外部命令」）  
4. 再点 **Install Now**。  
5. 安装完，新开一个 `cmd` 窗口，输入：  
   `python --version`  
6. 看到 `Python 3.x` = 成功。

**验证图形界面组件（GUI 需要）：**

```text
python -c "import tkinter; print('tk ok')"
```

看到 `tk ok` 即可。若报错，请重装 Python 并确保勾选 Tcl/Tk；或先用命令行版/网页版。

> 本电池项目**不需要** `pip install` 任何第三方库，装好 Python 就能跑。

#### 3.3 下载代码（二选一）

**方式 1：命令行克隆**

按 `Win+R` → 输入 `cmd` → 回车，然后：

```bat
cd /d D:\
git clone https://github.com/48ytw4q7zg-sudo/HyperBatteryHealthCalc-bat.git
cd HyperBatteryHealthCalc-bat
```

国内网络慢可改用 Gitee：

```bat
git clone https://gitee.com/qinxinwei123/hyper-battery-health-calc-bat.git
cd hyper-battery-health-calc-bat
```

**方式 2：下载 ZIP 再解压**（和路线二方法 A 一样）  
解压后进入文件夹即可，不需要 Git 也能运行。

#### 3.4 放入手机诊断 ZIP

1. 先按后文「手机怎么导出诊断文件」拿到 ZIP。  
2. 把 ZIP **复制**到：  
   `...\HyperBatteryHealthCalc-bat\HyperBatteryHealthCalc-bat\input\`  
   （即子目录 `HyperBatteryHealthCalc-bat` 里的 `input` 文件夹；没有就新建一个叫 `input` 的文件夹）

#### 3.5 运行

**图形界面（推荐先试这个）：**

```bat
cd HyperBatteryHealthCalc-bat\HyperBatteryHealthCalc-bat
python battery_gui.py
```

或在资源管理器里双击 `run.bat`。

**命令行：**

```bat
cd HyperBatteryHealthCalc-bat\HyperBatteryHealthCalc-bat
python battery_calc.py
```

**网页版：** 回到仓库根目录，双击 `index.html`。

#### 3.6 想把代码推到自己的 GitHub（可选）

1. 先注册 GitHub 账号并登录。  
2. 在本项目页面点右上角 **Fork**。  
3. 在 cmd 中：

```bat
git remote add mine https://github.com/你的用户名/HyperBatteryHealthCalc-bat.git
git push -u mine master
```

#### 3.7 网页挂到 GitHub Pages（可选）

1. 打开你自己 Fork 的仓库 → **Settings** → 左侧 **Pages**。  
2. Source 选 **Deploy from a branch**，Branch 选 **master**，文件夹选 **/(root)**，保存。  
3. 等 1–2 分钟，刷新页面顶部会出现网址，类似：  
   `https://你的用户名.github.io/HyperBatteryHealthCalc-bat/`  
4. 用手机/电脑打开该网址，应能看到计算器页面。

#### 3.8 给维护者：重新打包 Windows 便携版（可选）

```powershell
# 在仓库根目录，PowerShell 5.1+，需要已装好 x64 Python（含 Tk）和 Node
& .\build_windows.ps1 -Python 'C:\Python314\python.exe' -Node 'C:\Program Files\nodejs\node.exe'
```

产物在 `dist\HyperBatteryHealthCalc-Windows-x64-<时间戳>\`。详见 [packaging/BUILD_WINDOWS.md](packaging/BUILD_WINDOWS.md)。

---

### 手机上怎么导出诊断文件（电池工具必需）

没有诊断 ZIP，任何路线都算不出健康度。

1. **先充电（更准）：** 把手机充到 100%，再多充约 30 分钟（可选，但推荐）。  
2. **方法 A（拨号）：** 打开拨号盘，输入：  
   `*#*#284#*#*`  
   有的机型会自动开始抓取日志。  
3. **方法 B（设置）：**  
   设置 → **我的设备 / 全部参数与信息** → 连续点击 **「处理器」** 约 5–7 次。  
4. 等待约 10–30 秒，系统提示生成诊断/日志文件。  
5. 打开手机 **文件管理**，搜索关键词：`bugreport` 或 `诊断` 或 `284`，找到体积较大的 **ZIP** 文件。  
6. 用 QQ/微信文件传输助手、数据线、或小米互传，把 ZIP **传到电脑**。  
7. 放到你能找到的地方，例如桌面或 `D:\电池工具\input\`。

> 不同 HyperOS/MIUI 版本菜单位置略有差别。若连续点「处理器」没反应，尝试「内核版本」「MIUI 版本」等参数项，或用拨号方法。

---

### 装好以后怎么用（通用）

1. 打开 **便携版 GUI**，或 **网页版**，或 `python battery_gui.py`。  
2. 点 **浏览…** 选择电脑上的诊断 ZIP；便携版也可把 ZIP 放进程序旁 `input` 后点 **刷新文件列表**。  
3. 点 **开始分析**。  
4. 等待结果，看 **健康度百分比** 和五档评级：  
   - \>100%：超出设计容量（可能是冗余设计/第三方电池）  
   - 90–100%：极佳  
   - 80–90%：良好  
   - 70–80%：正常衰减  
   - <70%：建议考虑更换电池  
5. 若自动识别不到设计容量：按手机官方参数页面/说明书填 **设计容量 mAh**，再点计算。  
6. 需要保存时：便携版点 **保存报告**；CLI 用 `--output "reports\报告.txt"`。

---

### 出错了怎么办（新手 FAQ）

| 现象 | 可能原因 | 你可以这样做 |
|------|----------|--------------|
| 双击 EXE 没反应 / 闪退 | 只拷了 EXE，缺 `_internal`；或解压不完整 | 解压**完整文件夹**再运行 |
| 提示「Windows 已保护你的电脑」 | 未代码签名 | 更多信息 → 仍要运行 |
| 选择 ZIP 后没有任何结果 | 文件损坏、不是诊断包、或格式很旧 | 重新用手机导出；确认是 ZIP |
| `python` 不是内部或外部命令 | 装 Python 时没勾 Add to PATH | 重装 Python 并勾选；或用绝对路径 |
| `tkinter` 报错 | Python 没装 Tcl/Tk | 重装官方安装器；或用 CLI/网页版 |
| 打开网页一片空白 | 只拷了 index.html，缺 `js/zip.min.js` | 解压整个仓库文件夹 |
| 健康度和体感差很多 | 学习容量/充放状态差异 | 多测几次取平均；充满电后再导出 |
| GitHub 打不开或很慢 | 网络问题 | 用 Gitee 镜像，或让别人代下 ZIP |

更完整的验证边界见 [docs/functional-completion.md](docs/functional-completion.md) 与 [docs/portable-delivery-20260912.md](docs/portable-delivery-20260912.md)。

---
## 功能特点

- **本地处理**: 所有数据解析和计算在本地完成 (浏览器端/桌面端)，数据不会上传至任何服务器
- **自动检测设计容量**: 从 `android.hardware.health*.txt` 中提取 `batteryFullChargeDesignCapacityUah`，自动从 μAh ÷ 1000 转换为 mAh
- **当前容量提取**: 从 `Statistics since last charge:` 统计区块提取 `Min learned battery capacity` 作为当前实际容量
- **健康度计算**: `(当前实际容量 / 设计容量) × 100%`，五档评级
- **设备信息识别**: 提取设备型号 (`ro.product.marketname` 优先，`ro.product.model` 备用)
- **电池生命周期追踪**: 充电循环次数、估算满充容量、上次/最小/最大学习容量、系统报告满充容量、当前电量计数和充电状态
- **中文耗电诊断**: 不只计算健康度，还解析亮屏/息屏耗电、屏幕亮度分布、Doze、唤醒锁、WiFi Multicast、连接切换、UID 前台/后台耗电拆分、蓝牙耗电/扫描/连接设备、移动网络流量、Wi-Fi 流量、CPU 负载和高占用进程，生成中文建议
- **嵌套 ZIP 解析**: 自动穿透外层 ZIP 找到内层诊断 ZIP

### 五档评级标准

| 健康度 | 评级 | 色值 |
|--------|------|------|
| > 100% | 超出设计容量（可能为冗余设计或第三方电池） | `#e67e22` |
| 90% ~ 100% | 极佳状态 | `#27ae60` |
| 80% ~ 90% | 良好状态 | `#f39c12` |
| 70% ~ 80% | 正常衰减 | `#e67e22` |
| < 70% | 建议考虑更换电池 | `#e74c3c` |

> 三端 (Web/CLI/GUI) 评分边界完全一致，使用 `100.0001` 下界区分"超出"与"极佳"，避免浮点 `100.0` 的边界歧义。

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
```

### 图形界面版 (GUI)

```powershell
cd HyperBatteryHealthCalc-bat

# 直接运行 Python 脚本
python battery_gui.py

# 或双击 run.bat（自动调用 VBS 无窗口启动）
```

### Windows 便携版 CLI

```powershell
.\HyperBatteryHealthCalc-cli.exe --help
.\HyperBatteryHealthCalc-cli.exe --no-color --no-pause
.\HyperBatteryHealthCalc-cli.exe --input "D:\我的诊断" --no-pause
.\HyperBatteryHealthCalc-cli.exe --capacity 5000 --recursive --no-pause
.\HyperBatteryHealthCalc-cli.exe --output "reports\本次报告.txt" --no-pause
```

相对输入/输出路径相对于 EXE 所在目录。退出码：`0` 成功；`1` 缺数据/坏 ZIP/无输入/导出失败；`2` 参数错误。

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
