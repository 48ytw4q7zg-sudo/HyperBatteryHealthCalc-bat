# 小米电池健康容量计算器

一款用于解析 Android 诊断 ZIP 文件中的电池数据，计算小米/HyperOS/MIUI 设备当前电池容量百分比的工具。

本项目链接 >>>
- [Github Page](https://hikimucheno.github.io/HyperBatteryHealthCalc/)
- 第三方 >>> 微信搜索 "电池健康报告" (可检测小米、vivo、荣耀、红魔、三星)

---

## 项目结构

```
HyperBatteryHealthCalc-main/
├── index.html                              # 网页版（纯浏览器端运行）
├── js/
│   ├── zip.js                              # zip.js 开发版（完整注释）
│   └── zip.min.js                          # zip.js 压缩版（index.html 实际引用）
├── HyperBatteryHealthCalc-bat/             # Python 桌面版子项目
│   ├── battery_core.py                     # ★ 共享核心模块（数据模型/提取器/评分）
│   ├── battery_calc.py                     # 命令行版（CLI）
│   ├── battery_gui.py                      # 图形界面版（GUI, tkinter）
│   ├── index.html                          # 网页版副本（Q-CR 优化版）
│   ├── run.bat                             # Windows 启动脚本（→ run_gui.vbs）
│   ├── run_gui.vbs                         # VBS 无窗口启动（三级降级）
│   ├── input/                              # 默认输入目录（放置诊断 ZIP）
│   ├── js/                                 # zip.js 副本
│   ├── .gitignore                          # Python 生态标准 gitignore
│   ├── LICENSE                             # GPLv3 许可证
│   ├── .github/FUNDING.yml                 # GitHub 赞助配置
│   ├── .gitee/                             # Gitee Issue/PR 模板
│   └── README.md                           # 子项目详细文档
├── .github/FUNDING.yml                     # GitHub 赞助配置
├── LICENSE                                 # Apache 2.0 许可证
└── README.md                               # 本文件
```

---

## 运行形态总览

| 形态 | 入口文件 | 技术栈 | 适用场景 |
|------|---------|--------|---------|
| **网页版** | `index.html` | 纯静态 HTML + CSS + JS (zip.js) | 浏览器直接使用，无需安装 |
| **命令行 (CLI)** | `HyperBatteryHealthCalc-bat/battery_calc.py` | Python 3.8+，仅标准库 | 批量处理、脚本自动化 |
| **图形界面 (GUI)** | `HyperBatteryHealthCalc-bat/battery_gui.py` | Python 3.8+ + tkinter/ttk | 桌面用户，可视化操作 |
| **共享核心** | `HyperBatteryHealthCalc-bat/battery_core.py` | Python 3.8+ | 被 CLI 和 GUI 共同引用 |

---

## 功能特点

- **本地处理**: 所有数据解析和计算在本地完成 (浏览器端/桌面端)，数据不会上传至任何服务器
- **自动检测设计容量**: 从 `android.hardware.health*.txt` 中提取 `batteryFullChargeDesignCapacityUah`，自动从 μAh ÷ 1000 转换为 mAh
- **当前容量提取**: 从 `Statistics since last charge:` 统计区块提取 `Min learned battery capacity` 作为当前实际容量
- **健康度计算**: `(当前实际容量 / 设计容量) × 100%`，五档评级
- **设备信息识别**: 提取设备型号 (`ro.product.marketname` 优先，`ro.product.model` 备用)
- **电池生命周期追踪**: 充电循环次数、估算满充容量、上次/最小/最大学习容量、系统报告满充容量
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

### 获取诊断文件

1. 在小米/HyperOS 设备上进入 **设置 → 全部参数与信息 → 连续点击"处理器"** (约 5-7 次)
2. 或在拨号界面输入 `*#*#284#*#*` 一键抓包
3. 等待系统生成诊断文件 (约 10-30 秒)，通过文件管理器导出 ZIP

> 据说先把电量充到 100% 再继续充 30 分钟，诊断数据更准确。

### 网页版

直接用浏览器打开 `index.html`，选择诊断 ZIP 文件即可自动分析。如果自动提取设计容量失败，页面会显示手动输入框和"计算"按钮。

### 命令行版 (CLI)

```bash
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

```bash
cd HyperBatteryHealthCalc-bat

# 直接运行 Python 脚本
python battery_gui.py

# 或双击 run.bat（自动调用 VBS 无窗口启动）
```

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

### 2. `HyperBatteryHealthCalc-bat/battery_core.py` — 共享核心模块（214 行）

被 `battery_calc.py` (CLI) 和 `battery_gui.py` (GUI) 共同引用。包含三大组件：

#### 2.1 `BatteryInfo` 数据类（第 20-48 行）

11 个字段 + 3 个计算属性：

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

计算属性:
- `has_design_capacity` → `design_capacity is not None and design_capacity > 0`
- `current_capacity` → 返回 `min_learned_capacity`
- `health_percentage` → `(min_learned / design_capacity) * 100`

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

#### 2.3 `BatteryExtractor` 提取器类（第 84-214 行）

逐行流式处理 ZIP，10 个预编译正则。调用链：

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

### 7. `js/zip.js` / `js/zip.min.js` — 浏览器 ZIP 解析库

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
| 浮点容量处理 | `Math.floor(parseFloat())` | `int(float())` | `int(float())` |
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
| **网页版** | 现代浏览器 (Chrome/Firefox/Edge/Safari)，支持 ES6 + Blob API |
| **CLI 版** | Python 3.8+，仅标准库 |
| **GUI 版** | Python 3.8+ + tkinter (Windows/macOS 安装器自带) |

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

项目不依赖任何第三方 Python 包。克隆仓库后直接运行即可。

---

## 许可证

- 根项目 (`index.html`): Apache License 2.0
- 子项目 (`HyperBatteryHealthCalc-bat/`): GNU General Public License v3 (GPLv3)

Copyright © HikiMu慕鱼酱

---

## 贡献

欢迎参与项目改进！如有 bug 反馈或功能建议，可提交 issue 或 pull request。

## 免责声明

本工具仅为估算电池容量提供参考，不具备官方检测效力。若设备出现电池异常、续航锐减等问题，请前往小米官方线下售后网点进行专业检测和处理，本工具计算结果不作为售后依据。
