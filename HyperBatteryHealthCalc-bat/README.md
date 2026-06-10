# HyperBatteryHealthCalc-bat (Q-CR Omega v2.1)
**版本**: 1.3.1 - v2.1
**作者**: Q X W / HikiMu慕鱼酱

## 介绍

HyperBatteryHealthCalc-bat 是一款用于分析小米/HyperOS/MIUI Android 设备电池健康状况的开源工具。它能够从 Android 设备的 bugreport 诊断归档文件（ZIP 格式）中自动提取电池相关数据，计算电池健康度百分比，并生成详细的可视化报告。

**v2.1 (Q-CR Omega 三轮审计)** 改进要点：
- 浮点数容量正则统一：`(\d+\.?\d*)` 替代 `(\d+)`，防御 Android 系统输出浮点 mAh 值
- Web 端容量整数化使用 `Math.floor(parseFloat())`，与 Python `int(float())` 行为一致
- Web 端新增系统报告满充容量显示（`fullCapacity`），与 Python 端对齐
- GUI 端 Windows 高分屏 DPI 感知（`SetProcessDpiAwareness`）
- 全端 `designCapacity` 检查统一使用 `!= null && > 0`（falsey-safe），防止零值静默跳过
- `BatteryExtractor._parse_stats_text` 容量值使用 `int(float())` 二层转换防御非整数字符串

**v2 (Q-CR Omega)** 重构要点：
- 提取 `battery_core.py` 共享模块，消除 CLI/GUI 间 175+ 行重复代码
- 三端统一评分逻辑（`_RATING_TABLE` 5档查找表），消除边界不一致
- 网页版单次 ZIP 解析（替代原先的 `extractDeviceInfo` + `processZipFile` 二次解析）
- 三端评分表完全一致：`(100.0001, inf)` / `(90, 100)` / `(80, 90)` / `(70, 80)` / `(0, 70)`

### 核心功能

- **自动检测设计容量** — 从诊断文件的 `android.hardware.health` 数据中提取 `batteryFullChargeDesignCapacityUah`，自动从 μAh ÷1000 转换为 mAh
- **当前容量提取** — 从 `Statistics since last charge:` 统计区块提取 `Min learned battery capacity` 作为当前实际容量
- **健康度计算** — `(当前实际容量 / 设计容量) × 100%`，带五档评级（极佳/良好/正常衰减/建议更换/超出设计容量）
- **设备信息识别** — 提取设备型号（`ro.product.marketname` 优先，`ro.product.model` 备用）
- **电池生命周期追踪** — 提取充电循环次数、估算满充容量、上次/最小/最大学习容量、系统报告满充容量
- **嵌套 ZIP 解析** — 自动穿透外层 ZIP 找到内层诊断 ZIP，支持提前退出
- **本地离线运行** — 所有计算在本地完成，数据不上传

### 四种运行形态

| 形态 | 入口文件 | 技术栈 | 适用场景 |
|------|---------|--------|---------|
| **命令行 (CLI)** | `battery_calc.py` | Python 3.8+, 仅标准库 | 批量处理、脚本自动化 |
| **图形界面 (GUI)** | `battery_gui.py` | Python 3.8+ + tkinter/ttk | 桌面用户，可视化操作 |
| **网页版 (Web)** | `index.html` | 纯静态 HTML + CSS + JS | 浏览器直接使用 |
| **共享核心** | `battery_core.py` | Python 3.8+ (被 CLI/GUI 引用) | 数据模型、提取器、评分逻辑 |

---

## 项目文件结构

```
HyperBatteryHealthCalc-bat/
├── battery_core.py              # **(v2新增)** 共享核心模块 (BatteryInfo/BatteryExtractor/评分函数)
├── battery_calc.py              # 命令行版核心程序（引用 battery_core.py）
├── battery_gui.py               # 图形界面版程序（引用 battery_core.py）
├── index.html                   # 网页版前端（纯浏览器端运行，含内嵌 CSS/JS）
├── run.bat                      # Windows 命令行启动脚本（调用 VBS 无窗口启动）
├── run_gui.vbs                  # Windows GUI 无窗口启动脚本（VBScript 三级降级）
├── js/
│   ├── zip.js                   # zip.js 库（开发版，完整注释，~300KB+）
│   └── zip.min.js               # zip.js 库（压缩版，index.html 实际引用）
├── input/                       # 默认输入目录（用户自行创建或程序自动创建，放置诊断 ZIP 文件）
├── .gitignore                   # Git 忽略规则（Python 生态标准 + 各种常见 IDE/虚拟环境）
├── LICENSE                      # 软件许可协议（GNU GPLv3 全文）
├── .github/
│   └── FUNDING.yml              # GitHub 赞助配置（custom 链接）
├── .gitee/
│   ├── ISSUE_TEMPLATE.zh-CN.md  # Gitee Issue 模板（问题原因/重现步骤/报错信息）
│   └── PULL_REQUEST_TEMPLATE.zh-CN.md  # Gitee Pull Request 模板（关联Issue/原因/描述/测试用例）
├── .claude/
│   └── settings.local.json      # Claude Code 本地设置（仅供开发者本地使用，非项目分发包）
└── README.md                    # 本说明文档
```

---

## 各文件详细说明

### 1. `battery_core.py` — 共享核心模块（211 行）⚠️ v2 新增

**被 `battery_calc.py` 和 `battery_gui.py` 共同引用**。包含三大组件：

#### 1.1 `BatteryInfo` 数据类（第 20-48 行）

电池信息数据容器，11 个字段 + 3 个计算属性。与 v1 的 CLI/GUI 分别定义不同，v2 仅此单一定义——CLI 和 GUI 都 `from battery_core import BatteryInfo`。

| # | 字段 | 类型 | 来源文件 | 说明 |
|----|------|------|---------|------|
| 1 | `design_capacity` | `float \| None` | `android.hardware.health*.txt` | 设计容量（mAh），从 μAh ÷1000 |
| 2 | `design_capacity_auto` | `bool` | 程序标记 | True=自动检测, False=手动输入 |
| 3 | `cycle_count` | `int \| None` | `android.hardware.health*.txt` | 充电循环次数 |
| 4 | `full_capacity` | `float \| None` | `android.hardware.health*.txt` | 满充容量（mAh） |
| 5 | `device_name` | `str \| None` | `bugreport*.txt` | 设备名称，优先 marketname |
| 6 | `report_time` | `str \| None` | `bugreport*.txt` | 诊断报告生成时间 |
| 7 | `estimated_capacity` | `float \| None` | `bugreport*.txt` 统计区块 | 估算满充容量 |
| 8 | `last_learned_capacity` | `int \| None` | `bugreport*.txt` 统计区块 | 上次学习容量 |
| 9 | `min_learned_capacity` | `int \| None` | `bugreport*.txt` 统计区块 | **最小学习容量 → 当前容量** |
| 10 | `max_learned_capacity` | `int \| None` | `bugreport*.txt` 统计区块 | 最大学习容量 |
| 11 | `statistics` | `str \| None` | `bugreport*.txt` 统计区块 | 原始统计文本 |

**三个计算属性**：
- `has_design_capacity` → `bool`: `design_capacity is not None and design_capacity > 0`
- `current_capacity` → `Optional[int]`: 返回 `min_learned_capacity`
- `health_percentage` → `Optional[float]`: `(min_learned / design_capacity) * 100`

#### 1.2 评分逻辑（第 54-76 行）

三端统一的五档评分查找表（不可变 `tuple`），每个元组为 `(下界, 上界, 评级文本, 十六进制色值)`：

```python
_RATING_TABLE: tuple[tuple[float, float, str, str], ...] = (
    (100.0001, float('inf'), '超出设计容量（可能为冗余设计或第三方电池）', '#e67e22'),
    (90,       100,          '极佳状态',                                   '#27ae60'),
    (80,       90,           '良好状态',                                   '#f39c12'),
    (70,       80,           '正常衰减',                                   '#e67e22'),
    (0,        70,           '建议考虑更换电池',                             '#e74c3c'),
)
```

> `100.0001` 下界而非 `100`：浮点 `(cap/design)*100` 恰为 100 时不应归类为"超出"。

导出函数：
- `get_rating_text(percentage: float) -> str`：线性查找返回中文评级
- `get_rating_color(percentage: float) -> str`：线性查找返回十六进制色值

#### 1.3 `BatteryExtractor` 核心提取器类（第 82-211 行）

逐行流式处理 ZIP。10 个预编译正则（类变量，避免重复编译）。关键方法：

```
extract(zip_path) → BatteryInfo
  ├── _find_inner_zips() → 外层中所有 .zip 文件名
  ├── for each inner zip:
  │     ├── _find_file('android.hardware.health', '.txt')
  │     ├── _find_file('bugreport', '.txt')
  │     ├── _parse_health_stream() → 设计容量/循环次数/满充容量
  │     ├── _parse_bugreport_stream() → 设备名/时间/统计区块
  │     │     └── _parse_stats_text() → 4项学习容量
  │     └── [提前退出] has_design_capacity && current_capacity → break
```

> Web 版 JS 的 `parseBugreportText()` / `parseStatsText()` 与 Python 的 `_parse_bugreport_stream()` / `_parse_stats_text()` 逻辑等价，评分表 `RATING_TABLE` 也与 Python 一致。

---

### 2. `battery_calc.py` — 命令行版核心程序（~270 行）

整个工具的**数据引擎**。无第三方依赖，引用 `battery_core.py`。

#### 1.1 导入模块与 Windows GBK 容错（第 1-24 行）

```python
from battery_core import BatteryExtractor, BatteryInfo, get_rating_text, get_rating_color
```

**关键：Windows GBK 控制台 emoji 保护（第 20-24 行）**：
```python
if sys.platform == 'win32' and sys.stdout.isatty():
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding=sys.stdout.encoding,
        errors='replace', line_buffering=sys.stdout.line_buffering
    )
```
Windows 控制台 GBK 编码输出 emoji 会触发 `UnicodeEncodeError`。将 stdout 包装为容错模式（`errors='replace'`）避免崩溃。

#### 1.2 `Colors` 终端颜色控制类（第 32-65 行）

- `_detect_support()`: 先检查 `isatty()`，Windows 平台调用 `_enable_windows_ansi()` 启用 VT100
- `_enable_windows_ansi()`: `ctypes.windll.kernel32.SetConsoleMode(mode | 0x0004)` 启用虚拟终端处理
- `_init_styles()`: 8 个颜色属性，禁用时全部为空字符串
- `rating(percentage)`: **v2 改为调用 `battery_core.get_rating_color()` 判断色值**，消除 v1 独立 `if/elif` 链的维护不一致

#### 1.3 `ReportPrinter` 报告生成类（第 68-130 行）

- `print_report(info, filename)`: 生成 ANSI 彩色终端报告 + 返回 `_strip_ansi()` 纯文本
- `_strip_ansi(text)`: 正则 `\x1b\[[0-9;]*m` 移除 ANSI 序列

#### 1.4 `main()` 主流程（第 156-240 行）

```
main(argv) → int
  ├── build_parser() → parse_args()
  ├── 校验 input 目录
  ├── 扫描 *.zip (忽略大小写)
  ├── for each zip:
  │     ├── extractor.extract() → BatteryInfo
  │     ├── 缺设计容量 → args.capacity 或 prompt_design_capacity()
  │     ├── 缺当前容量 → 跳过
  │     └── printer.print_report() → 终端 + all_reports
  ├── --output → 写入文件
  └── return 0 if failed == 0 else 1

---

### 3. `battery_gui.py` — 图形界面版程序（~265 行）

基于 tkinter + ttk 构建。**v2 通过 `from battery_core import BatteryExtractor, BatteryInfo, get_rating_text, get_rating_color` 消除了约 175 行重复代码**。

#### 2.1 导入模块

```python
from battery_core import BatteryExtractor, BatteryInfo, get_rating_text, get_rating_color
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
```

#### 2.2 `BatteryHealthApp` 主窗口类（第 13-222 行）

**`__init__`**: `tk.Tk()` 初始化 → `BatteryExtractor()` 实例化 → `_build_ui()` 构建全部 UI → `_refresh_file_list()` 启动扫描

**`_build_ui()` 组件树**:
```
root (tk.Tk, bg='#f8f9fa', 720×620)
└── main (ttk.Frame)
    ├── title_frame → ttk.Label("小米电池容量计算器", font=18pt bold)
    ├── note_frame → tk.Label(说明文字, bg='#ebf8ff')
    ├── file_frame (ttk.LabelFrame)
    │   ├── file_combo (ttk.Combobox) + "浏览..." (ttk.Button → filedialog)
    │   └── capacity_entry (ttk.Entry, 手动设计容量)
    ├── btn_frame → analyze_btn (tk.Button, 绿色) + refresh_btn (tk.Button, 蓝色)
    ├── status_lbl (tk.Label, textvariable=self.status_var)
    ├── result_frame (ttk.LabelFrame)
    │   ├── result_text (tk.Text, Consolas 10pt, state='disabled')
    │   └── scrollbar (ttk.Scrollbar)
    └── footer (tk.Label)
```

**`_analyze()`**: 路径解析 → 锁 UI → `extractor.extract()` → 缺设计容量时读 `capacity_entry` → 缺当前容量时报错 → `_build_report()` → `_show_result()` → `_highlight_result()` (tkinter Text tag 高亮健康度行)

**`_build_error_report()`**: 当提取不完整时生成"部分信息已提取"报告。

**评分逻辑**: v2 统一使用 `battery_core.get_rating_text()` 和 `battery_core.get_rating_color()`，不再维护独立评分函数。

---

### 4. `index.html` — 网页版前端（~800 行）⚠️ v2 重写

**v2 核心变更**:
1. **单次 ZIP 解析**: 原 v1 先 `extractDeviceInfo()` 再 `processZipFile()` 两次解析 ZIP，v2 合并为一次 `parseZipAndRender()`
2. **统一评分逻辑**: 使用与 Python `battery_core.py` 完全一致的 `RATING_TABLE`（5 档、相同边界）
3. **评分边界统一**: `[100.0001, Infinity]` 而非 v1 的 `[105, Infinity]` 或 `> 100`
4. **`escHtml()` 防 XSS**: 所有用户数据在插入 HTML 前经过 `textContent` 转义
5. **预编译正则**: 11 个 `const RE_*` 顶层声明替代多劫内联字面量

#### 3.1 核心 JavaScript 调用链 (v2)

```
DOMContentLoaded
  └── addEventListener('change', handleFileSelect) on #zip-file
      addEventListener('click', manualCalculate) on #calculate-btn

handleFileSelect()
  ├── 重置 UI (隐藏输入框/按钮/结果)
  └── parseZipAndRender(file, null)

manualCalculate()
  ├── 校验手动输入 > 0
  └── parseZipAndRender(file, manualCapacity)

parseZipAndRender(file, manualCapacity) [async]
  ├── new zip.ZipReader(new zip.BlobReader(file))
  ├── getEntries() → 遍历外层
  │     └── for each inner .zip:
  │           ├── getData(BlobWriter) → new ZipReader
  │           ├── [health txt]: 正则提取 designCapacity/cycleCount/fullCapacity
  │           ├── [bugreport txt]: parseBugreportText(content, info)
  │           │     └── 单次扫描: 设备名(marketname>model) + 时间 + 统计区块
  │           │           └── parseStatsText(text, info) → 4 项容量
  │           ├── [提前退出] if designCap && minLearned: break
  │           └── innerReader.close()
  │
  ├── designCap = info.designCap || manualCap
  ├── [无设计容量] → 显示 manual-input + calculate-btn + partial report
  ├── [无当前容量] → partial report
  ├── [成功] → buildFullReport(info) → showResult()
  └── [异常] → showError() + 降级到手动模式

buildFullReport(info)
  ├── pct = (current / design) * 100
  ├── rating = getRatingText(pct)  ← RATING_TABLE 查找
  ├── color = getRatingColor(pct)
  ├── 拼装 HTML 报告 (escHtml 防 XSS)
  └── translateStats(statistics) → 翻译对照 (折叠区)
```

#### 3.2 统一评分表

```js
const RATING_TABLE = [
    [100.0001, Infinity, '超出设计容量（可能为冗余设计或第三方电池）', '#e67e22'],
    [90,       100,      '极佳状态',                               '#27ae60'],
    [80,       90,       '良好状态',                               '#f39c12'],
    [70,       80,       '正常衰减',                               '#e67e22'],
    [0,        70,       '建议考虑更换电池',                         '#e74c3c']
];
// 与 Python battery_core._RATING_TABLE 完全一致
```

---

---

### 3. `index.html` — 网页版前端（986 行）

纯静态 HTML + CSS + JavaScript，所有计算在浏览器本地完成，无需服务器。仅依赖同目录 `js/zip.min.js`（zip.js 库压缩版本）。

版本号：`25.11.02`（github 版本 1.3），Copyright HikiMu慕鱼酱。

#### 3.1 HTML 头部（第 1-15 行）

```html
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>电池容量计算器</title>
<meta name="description" content="电池容量计算器是一个工具，用于从导出的ZIP文件中提取电池容量信息...">
<meta name="keywords" content="电池容量计算器, 诊断文件处理, 电池健康度, 电池容量百分比, zip.js库, HyperOS电池容量, MIUI电池容量, 电池容量提取工具, 电池健康度检测">
<script src="js/zip.min.js"></script>
```

`zip.min.js` 以同步 `<script>` 加载，在 `<head>` 中而非 `<body>` 底部。这意味着 `DOMContentLoaded` 事件触发时 zip.js 已可用（脚本阻塞解析），因此 `handleFileSelect` 和 `calculateBatteryCapacity` 可以直接使用 `zip.ZipReader` 等 API。

#### 3.2 完整样式系统 / CSS（第 16-362 行）

以下按 CSS 选择器逐个分析设计意图与样式细节：

| CSS 选择器 | 关键属性 | 设计意图 |
|-----------|---------|---------|
| `body` | `max-width: 800px; margin: 0 auto; padding: 20px; background: #f8f9fa; color: #2d3748; font-family: 'Arial', 'sans-serif', 'Misans'` | 固定宽度居中布局，Misans（小米定制字体）优先但备选系统字体 |
| `.container` | `background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%); border-radius: 12px; box-shadow: 0 6px 16px rgba(0,0,0,0.08); border: 1px solid #e2e8f0` | 白→浅灰渐变卡片，微妙的阴影和边框形成分层效果 |
| `h1` | `color: #2b6cb0; font-size: 28px; text-shadow: 0 1px 2px rgba(0,0,0,0.05)` | 蓝色标题配细微文字阴影（提高对比度但保留柔和感） |
| `.instructions` | `background: linear-gradient(135deg, #ebf8ff 0%, #e6fffa 100%); border-left: 5px solid #4299e1; box-shadow: 0 2px 4px rgba(0,0,0,0.04)` | 蓝→绿渐变背景指示块，左侧5px蓝色竖条（信息层级标记） |
| `.file-upload input` | `border: 2px dashed #cbd5e0; transition: all 0.3s ease`；hover: `border-color: #4299e1; background: #edf2f7` | 虚线边框文件选择区，hover 变蓝增加交互反馈 |
| `button` | `background: linear-gradient(135deg, #48bb78 0%, #38a169 100%); font-weight: 600; box-shadow: 0 2px 4px rgba(72,187,120,0.2); transition: all 0.3s ease`；hover: `translateY(-1px); box-shadow: 0 4px 8px rgba(72,187,120,0.3)` | 绿渐变按钮，hover 上浮1px + 阴影加深 → 3D 效果 |
| `.status` | `display: none; border-left: 5px solid #4299e1; background: linear-gradient(135deg, #edf2f7 0%, #e2e8f0 100%)` | 默认隐藏，显示时有蓝色左边框指示 |
| `.result` | `display: none; box-shadow: 0 2px 8px rgba(0,0,0,0.08)` | 默认隐藏，显示时有阴影卡片效果 |
| `.success` | `background: linear-gradient(135deg, #f0fff4 0%, #e6fffa 100%); border-left: 5px solid #48bb78; color: #22543d` | 成功结果：绿边框 + 浅绿背景 |
| `.error` | `background: linear-gradient(135deg, #fff5f5 0%, #fed7d7 100%); border-left: 5px solid #f56565; color: #742a2a` | 错误结果：红边框 + 浅红背景 |
| `.toggle-btn` | `background: linear-gradient(135deg, #4299e1 0%, #3182ce 100%)` | 蓝渐变折叠按钮，与绿色主按钮区分 |
| `.original-text` | `display: none; max-height: 500px; overflow-y: auto; font-family: 'Cascadia Code', 'Courier New', monospace; font-size: 13px; line-height: 1.6` | 默认折叠的原始数据显示区，500px 最大高度+滚动，等宽字体 |
| `.original-text .battery-key` | `color: #dc2626; font-weight: 600; background: #fef2f2; border-radius: 3px` | 电池字段名用红色高亮（高重要性） |
| `.original-text .capacity-value` | `color: #059669; font-weight: 600; background: #f0fdf4; border-radius: 3px` | 容量数值用绿色高亮（正值/良好） |
| `.original-text .time-value` | `color: #7c3aed; font-weight: 500; background: #faf5ff; border-radius: 3px` | 时间值用紫色高亮（中性信息） |
| `.original-text::-webkit-scrollbar` | 8px 宽度自定义滚动条（Track `#f1f5f9`, Thumb `#cbd5e1`, Hover `#94a3b8`） | WebKit 滚动条美化，与整体配色统一 |
| `#calculate-btn` | `display: none` | 默认隐藏，仅当自动提取失败后显示（手动计算模式） |
| `#manual-input-container` / `.input-group` | `display: none; transition: all 0.3s ease` | 默认隐藏的手动输入区域 |
| `.input-group input:focus` | `border-color: #4299e1; box-shadow: 0 0 0 3px rgba(66,153,225,0.1); outline: none` | focus 状态蓝色外发光（不用浏览器默认 outline） |
| `code, .english-text` | `font-family: 'Cascadia Code', 'Monaco', 'Menlo', 'Ubuntu Mono', monospace` | 代码块多平台等宽字体备选链 |
| `.footer a` | `color: #4299e1; text-decoration: none; transition: color 0.3s ease`；hover: `color: #3182ce; text-decoration: underline` | 页脚链接 hover 下划线（颜色过渡） |
| `.media-alert` | `background: linear-gradient(135deg, #fffaf0 0%, #feebc8 100%); border-left: 5px solid #ed8936` | 橙色边框警吿框（当前未在 HTML 中使用的备选样式） |

#### 3.3 页面结构 / HTML（第 365-431 行）

```
body
├── #watermark-container (全屏覆盖层, pointer-events: none, z-index: 9999)
│     └── 数字水印占位容器，JS 可向其中动态添加水印元素
└── .container (主容器)
    ├── h1 "小米电池容量计算器"
    ├── .instructions[1] — 关于本工具/使用说明/安全声明
    │     ├── <strong>⚠️ 注意: 所有分析过程均在您的浏览器本地完成</strong>
    │     └── <strong>⚠️ 免责声明: 若设备出现异常，请前往小米官方售后</strong>
    ├── .instructions[2] — 抓包步骤说明 + B 站视频嵌入
    │     ├── <iframe> 嵌入 B 站视频播放器 (aid=114260860472968, bvid=BV13YZ4YEE8B)
    ├── .file-upload — <input type="file" id="zip-file" accept=".zip" required>
    ├── #manual-input-container — 手动输入设计容量 (默认隐藏)
    │     └── <input type="number" id="initial-capacity" placeholder="例如: 5000" required>
    ├── <a href="tel:*%23*%23284%23*%23"> — URI 编码的拨号链接 `*#*#284#*#*`
    │     └── <button style="background: #3498db">🔧 一键抓包</button>
    ├── <button id="calculate-btn">计算</button> (默认隐藏)
    ├── #status (默认隐藏)
    ├── #result (默认隐藏)
    └── .footer
          ├── 捐助链接 <a href="http://119.29.227.6/pay">【链接】</a>
          ├── .open-source-links
          │     ├── <a> 开源工具许可 (指向 zip.js GitHub)
          │     └── <a> 此项目开源地址 (指向 HyperBatteryHealthCalc GitHub)
          └── <p> Copyright © HikiMu慕鱼酱 All rights reserved.
```

**一键抓包的工作原理**：`tel:*%23*%23284%23*%23` 中的 `%23` 是 `#` 的 URI 百分号编码。点击后触发系统拨号器拨出 `*#*#284#*#*`，这是小米/HyperOS 的诊断模式工程码，用于触发系统生成 bugreport。

#### 3.4 核心 JavaScript 逻辑（第 433-982 行）

##### 3.4.1 全局状态变量 `autoExtractedInfo`（第 434-445 行）

```js
let autoExtractedInfo = {
    designCapacity: null,    // 设计容量 (mAh)，已从 μAh ÷1000
    deviceModel: null,       // 设备型号代码
    deviceName: null,        // 设备市场名/型号（与 deviceModel 取相同值）
    reportTime: null,        // 诊断报告时间
    cycleCount: null,        // 充电循环次数
    fullCapacity: null,      // 系统报告满充容量 (mAh)
    estimatedCapacity: null, // 估算满充容量 (mAh)
    lastLearnedCapacity: null, // 上次学习容量 (mAh)
    minLearnedCapacity: null,  // 最小学习容量 (mAh)
    maxLearnedCapacity: null   // 最大学习容量 (mAh)
};
```

这是整个 JavaScript 的**全局数据总线**。所有从 ZIP 中提取的信息都存储在此对象中，后续 `processZipFile()` 直接读取其属性生成报告。每次 `handleFileSelect()` 触发时都会**完全重置**为新对象（避免上次文件的信息泄漏到本次分析）。

##### 3.4.2 事件绑定（第 447-450 行）

```js
document.addEventListener('DOMContentLoaded', function () {
    document.getElementById('calculate-btn').addEventListener('click', calculateBatteryCapacity);
    document.getElementById('zip-file').addEventListener('change', handleFileSelect);
});
```

仅绑定两个事件：
- **`#zip-file` → `change`**：用户选择文件后立即触发自动提取流程 `handleFileSelect()`
- **`#calculate-btn` → `click`**：手动计算按钮（仅在自动提取失败后显示），触发 `calculateBatteryCapacity()`

##### 3.4.3 `handleFileSelect()` — 文件选择处理器（第 452-478 行）

```
1. 重置 autoExtractedInfo 为全新对象（全部字段 → null）
2. 隐藏手动输入框和计算按钮: style.display = 'none'
3. 隐藏上次结果和状态: style.display = 'none'
4. 获取 file = input.files[0]
5. 调用 showStatus("正在自动分析电池数据，请稍候...")
6. 调用 extractDeviceInfo(file)  [异步]
```

这是整个流程的**入口守卫**——无论之前的状态如何，选择新文件时一律重置。

##### 3.4.4 `extractDeviceInfo(file)` — 自动提取信息（第 481-558 行）

**async 函数**，串联两次异步 ZIP 解析：

```
1. reader = new zip.ZipReader(new zip.BlobReader(file))
2. entries = await reader.getEntries()   // 获取外层 ZIP 条目

3. for (const entry of entries):
      if (!entry.filename.endsWith('.zip')) continue  // 跳过非 ZIP 文件

      ┌─ 内层 ZIP 解析 ─────────────────────────────┐
      │ innerZipBlob = await entry.getData(          │
      │     new zip.BlobWriter('application/zip'))    │
      │ innerReader = new zip.ZipReader(              │
      │     new zip.BlobReader(innerZipBlob))         │
      │ innerEntries = await innerReader.getEntries() │
      └──────────────────────────────────────────────┘

      4. for (const innerEntry of innerEntries):
           // 匹配 health 文件
           if (filename.includes('android.hardware.health') && endsWith('.txt')):
             content = await innerEntry.getData(new zip.TextWriter())
             // 提取设计容量: /batteryFullChargeDesignCapacityUah\s*[:=]\s*(\d+)/ → ÷1000
             // 提取循环次数: /batteryCycleCount\s*[:=]\s*(\d+)/
             // 提取满充容量: /batteryFullCharge(Uah)?\s*[:=]\s*(\d+)/ → ÷1000

           // 匹配 bugreport 文件
           if (filename.includes('bugreport') && endsWith('.txt')):
             content = await innerEntry.getData(new zip.TextWriter())
             // extractDeviceInfoFromText(content) → deviceName/deviceModel
             // extractDataFromText(content) → reportTime + statistics
             // extractBatteryCapacityFromStatistics(statistics) → 4项学习容量

         await innerReader.close()

5. await reader.close()

6. 结果判断:
     if (autoExtractedInfo.designCapacity):
       processZipFile(file, autoExtractedInfo.designCapacity)  → 自动继续
     else:
       显示手动输入框 + 计算按钮  → 降级到手动模式

7. catch (error):
     显示手动输入框 + 计算按钮  → 解析失败也降级到手动模式
```

**与 CLI 版的差异**：
- 网页版遍历内层 ZIP 条目时**没有**提前退出逻辑（`if has_design_capacity and current_capacity: break`），会遍历完所有内层条目
- 网页版使用正则字面量 `/batteryFullCharge(Uah)?\s*[:=]\s*(\d+)/`——注意捕获组索引是 `[2]` 而非 `[1]`，因为 `(Uah)?` 是第一个捕获组
- 内层 ZIP 解析是一次性的：`BlobWriter('application/zip')` 输出完整 blob，再构建新 `ZipReader`。这比 CLI 版的 `io.BytesIO` 方式对象创建重量更大

##### 3.4.5 `extractDeviceInfoFromText(text)` — 设备信息提取（第 561-600 行）

从 bugreport 文本中提取三项设备标识：

```
for line of text.split('\n'):
  ├── /\[ro\.product\.marketname\]:\s*\[([^\]]+)\]/ → deviceInfo.marketName
  ├── /\[ro\.product\.model\]:\s*\[([^\]]+)\]/       → deviceInfo.model
  └── /\[ro\.product\.device\]:\s*\[([^\]]+)\]/       → deviceInfo.device
  └── 若三项全找到 → break 提前退出
```

**与 CLI 版的差异**：网页版额外提取 `ro.product.device`（设备代号，如 `venus`），但 CLI 版不提取此项——网页版展示更丰富的设备信息。

##### 3.4.6 `extractDataFromText(text)` — 复合数据提取（第 603-679 行）

单次扫描 bugreport 文本，同时完成三项提取。这是复用的核心函数——在 `extractDeviceInfo` 和 `processZipFile` 中都被调用：

```
for line of text.split('\n'):
  ├── [报告时间] /== dumpstate:\s*(.+)/ → reportTime
  ├── [设备信息] 按优先级: marketname → model → device
  │     └── 注意: 若 model 先于 marketname 匹配，device.name = model（预留后续覆盖）
  └── [统计区块] 状态机: "Statistics since last charge:" 开始 → 空行结束
       └── 文件末尾未闭合兜底处理

return { reportTime, device: {name, model, code}, statistics }
```

**注意**：`extractDataFromText` 中的设备信息提取与 `extractDeviceInfoFromText` **有重复**——两个函数都做了设备信息的正则提取。前者用于填充全局 `autoExtractedInfo` 中的 `deviceName`/`deviceModel`；后者返回独立的 `device` 对象（且在 `processZipFile` 中被调用但未实际使用其 `device` 返回值）。这是历史演进中形成的冗余。

##### 3.4.7 `extractBatteryCapacityFromStatistics(statisticsText)` — 容量提取（第 682-713 行）

从统计文本中逐行提取 4 项容量数据。与 CLI/GUI 版的 `_parse_stats_text()` 逻辑等價，但实现为纯 JavaScript：

```js
const result = {};
for (const line of statisticsText.split('\n')):
  /Estimated battery capacity:\s*([\d.]+)\s*mAh/i → result.estimatedCapacity (parseFloat)
  /Last learned battery capacity:\s*(\d+)\s*mAh/i → result.lastLearnedCapacity (parseInt)
  /Min learned battery capacity:\s*(\d+)\s*mAh/i   → result.minLearnedCapacity (parseInt)
  /Max learned battery capacity:\s*(\d+)\s*mAh/i   → result.maxLearnedCapacity (parseInt)
return result;  // 未匹配的字段不出现（undefined）
```

##### 3.4.8 `calculateBatteryCapacity()` — 手动计算入口（第 716-737 行）

仅在自动提取失败后由用户点击触发：

```
1. 校验 fileInput.files[0] 存在
2. 若 autoExtractedInfo.designCapacity 为 null:
     校验 manual input: not (isNaN(val) || val <= 0)
     └── 不通过 → showError + return
3. showStatus("正在解析电池数据，请稍候...")
4. processZipFile(file, initialCapacity)
```

**注意**：如果 `autoExtractedInfo.designCapacity` 已经在 `extractDeviceInfo` 中成功提取（非 null），则用户无需再次输入设计容量——即使手动输入框有值也会被忽略（使用自动提取的值）。

##### 3.4.9 `processZipFile(file, initialCapacity)` — 核心处理与展示（第 740-885 行）

这是 JavaScript 端最重要的函数，约 145 行代码。负责二次 ZIP 解析（与 `extractDeviceInfo` 有重复解析行为）、计算健康度、拼装 HTML 报告：

```
1. reader = new zip.ZipReader(new zip.BlobReader(file))
   └── 再次打开外层 ZIP（即使 extractDeviceInfo 已经解析过一次）

2. for (外层 entries):
      if (filename ends with '.zip'):
        innerZipBlob = entry.getData(new zip.BlobWriter('application/zip'))
        innerReader = new zip.ZipReader(new zip.BlobReader(innerZipBlob))

3.   for (内层 entries):
        if (filename includes 'bugreport' && endsWith '.txt'):
          content = entry.getData(new zip.TextWriter())
          extractedData = extractDataFromText(content)   // 复用 extractDataFromText
          statistics = extractedData.statistics
          stats = extractBatteryCapacityFromStatistics(statistics)  // 4项容量

          currentCapacity = stats.minLearnedCapacity || autoExtractedInfo.minLearnedCapacity
          └── 优先用本次提取的，否则回退到全局 autoExtractedInfo 中的

          if (currentCapacity !== null && currentCapacity !== undefined):
            finalInitialCapacity = autoExtractedInfo.designCapacity || initialCapacity
            └── 自动提取优先；没有才用用户手动输入值

            percentage = (currentCapacity / finalInitialCapacity) * 100
            rating = getBatteryRating(percentage)

            [构建大型 HTML 字符串 resultMessage]
              ├── 📊 基本信息 (设备型号/诊断时间/设计容量/当前容量/健康度)
              ├── 🔧 电池硬件信息 (估算容量/上次/最小/最大学习容量/循环次数)
              ├── 捐助链接
              └── 📖 电池详细信息折叠区
                    ├── 🔍 电池关键信息翻译 (translateBatteryInfoOnly)
                    └── 📄 原始电池数据 (statistics 原文)

            showResult(resultDiv, resultMessage, true)
            await reader.close()
            await innerReader.close()
            return   ← 找到后就退出

        await innerReader.close()  ← 此 close() 可能因提前 return 而跳过

4. [走到这里=未找到有效数据]
   showError + await reader.close()

5. finally:
     setTimeout(() => statusDiv.style.display = 'none', 1000)  → 1秒后隐藏状态栏
```

**潜在的资源泄漏问题**：第 871 行的 `await innerReader.close()` 在 `processZipFile` 正常运行路径中可能被第 866 行的 `return` 跳过。实际分析中这不会产生问题——因为找到数据后两个 reader 在第 865-866 行已被 close，外层循环不再迭代。但如果文件有多个内层 ZIP 且第一个包含有效数据，则第二个内层 ZIP 永远不会被打开。

##### 3.4.10 辅助函数（第 888-981 行）

**`translateBatteryInfoOnly(originalText)`（第 888-928 行）**：
输入原始的英文统计数据文本，返回带 HTML 标注的翻译版本。分三个步骤：
1. 用正则 `.replace(/(\d+\.?\d*\s*mAh)/g, '<span class="capacity-value">$1</span>')` 高亮 mAh 数值为绿色
2. 用正则 `.replace(/(\d+h\s*\d+m\s*\d+s)/g, '<span class="time-value">$1</span>')` 高亮时间值为紫色
3. 用正则 `.replace(/(\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2})/g, '<span class="time-value">$1</span>')` 高亮时间戳为紫色
4. 遍历 `batteryTranslations` 映射表（14 项英→中对照），将英文字段名替换为 `<span class="battery-key">英文\n    (中文)</span>` 红色高亮

**`getRatingColor(percentage)`（第 930-936 行）**：
- `> 100` → `'#ff6b35'`（红橙）
- `≥ 90` → `'#2ecc71'`（绿色）
- `≥ 80` → `'#f39c12'`（黄色）
- `≥ 70` → `'#e67e22'`（橙色）
- else → `'#e74c3c'`（红色）

**`getBatteryRating(percentage)`（第 938-950 行）**：
五档评级文本（含 emoji 前缀，与 CLI/GUI 版不同——网页版是唯一包含 emoji 的评级输出）：
- `> 100` → `"🔋 超出设计容量（可能为冗余设计或第三方电池）"`
- `≥ 90` → `"✅ 极佳状态"`
- `≥ 80` → `"👍 良好状态"`
- `≥ 70` → `"⚠️ 正常衰减"`
- else → `"❌ 建议考虑更换电池"`

**`showResult(element, message, isSuccess)`（第 953-957 行）**：
`element.innerHTML = message` 直接设置 HTML → `element.className = isSuccess ? 'result success' : 'result error'` → `element.style.display = 'block'`

**`showError(element, message)`（第 960-962 行）**：
快捷包装: `showResult(element, message, false)`

**`showStatus(message)`（第 965-969 行）**：
更新 `#status` 元素 textContent（纯文本，不使用 innerHTML 防止注入）并显示。

**`toggleOriginalText(button)`（第 972-981 行）**：
折叠/展开"电池详细信息"区域：
```
button.nextElementSibling 获取折叠区 div
  ├── 当前 display == 'block' → 隐藏, 按钮文字="📖 显示电池详细信息"
  └── 否则 → 显示, 按钮文字="📖 隐藏电池详细信息"
```

---

### 4. `run.bat` — Windows 命令行启动脚本（3 行）

```batch
start "" wscript //nologo "%~dp0run_gui.vbs"
exit /b 0
```

逐行解析：
1. `start ""` — `start` 命令的第一个参数是**窗口标题**（可为空字符串），第二个参数才是要执行的程序/脚本。省略空标题会导致 `start` 把程序路径误解为标题名
2. `wscript //nologo "%~dp0run_gui.vbs"` — `wscript` 是 Windows Script Host 的 GUI 模式宿主（无控制台窗口）；`//nologo` 禁止 wscript 显示版权横幅；`%~dp0` 是批处理参数扩展——`d`=盘符, `p`=路径, `0`=脚本自身 → 得到脚本所在目录的绝对路径（如 `D:\1\...\HyperBatteryHealthCalc-bat\`）
3. `exit /b 0` — 退出当前 CMD 进程并返回 0 退出码，`/b` 表示只退出当前批处理脚本但不关闭 CMD 窗口（如果从外部 CMD 调用的話）

**调用链**：`双击 run.bat` → `start wscript` → `wscript 执行 run_gui.vbs` → `run_gui.vbs 启动 python/pythonw` → `battery_gui.py`

---

### 5. `run_gui.vbs` — Windows 无窗口 GUI 启动脚本（14 行）

```vbscript
Set ws = CreateObject("Wscript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
script_dir = fso.GetParentFolderName(WScript.ScriptFullName)

On Error Resume Next
ws.Run "pythonw """ & script_dir & "\battery_gui.py""", 0, False
If Err.Number <> 0 Then
    ws.Run "python """ & script_dir & "\battery_gui.py""", 1, False
    If Err.Number <> 0 Then
        MsgBox "Python/tkinter not found. Please install Python 3.7+", 48, "Error"
    End If
End If
On Error GoTo 0
```

逐行解析：

1. **第 1-3 行**：创建 `Wscript.Shell`（用于 `Run` 方法启动进程）和 `Scripting.FileSystemObject`（用于获取脚本目录路径）
2. **`script_dir = fso.GetParentFolderName(WScript.ScriptFullName)`** — 获取脚本所在目录的父级路径，不管当前工作目录在哪里，始终能找到 `battery_gui.py`
3. **`On Error Resume Next`** — 启动 VBS 错误容错模式：后续语句即使出错也不中断，继续执行下一行。这是降级链的关键——第一级失败后自动尝试第二级
4. **`ws.Run "pythonw", 0, False`** — **第一级**：使用 `pythonw.exe`（Windows 下无控制台窗口的 Python 解释器）+ 窗口模式 `0`（隐藏窗口）。这是理想路径——GUI 窗口完全由 tkinter 创建，后台无任何 CMD 窗口
5. **`ws.Run "python", 1, False`** — **第二级**：`pythonw` 不可用时（如通过 `python.org` 安装器安装的 Python 可能在 PATH 中只有 `python` 没有 `pythonw`），降级为 `python` + 窗口模式 `1`（正常显示）。此时会短暂出现 CMD 窗口，但 GUI 启动后仍在
6. **`MsgBox "Python/tkinter not found...", 48, "Error"`** — **第三级**：两次尝试都失败 → 弹出错误消息框（`48` = `vbExclamation` 警告图标），提示用户安装 Python 3.7+
7. **`On Error GoTo 0`** — 恢复正常错误处理模式

**双引号转义细节**：`"pythonw """ & script_dir & "\battery_gui.py"""` 的引号逻辑：
- VBS 中 `""` 表示转义后的单引号字符 `"`
- 最终传递给 `ws.Run` 的字符串是 `pythonw "D:\path\battery_gui.py"`（路径用双引号包裹，防止含空格路径断裂）

---

### 6. `js/zip.js` / `js/zip.min.js` — 浏览器端 ZIP 解析库

使用 [@gildas-lormeau/zip.js](https://github.com/gildas-lormeau/zip.js) 开源库（BSD 3-Clause 许可）：
- **`zip.js`** — 开发版本（含完整注释，约 300KB+），供开发者阅读/调试
- **`zip.min.js`** — 生产压缩版本（`index.html` 第 15 行实际引用），通过 `<script src="js/zip.min.js"></script>` 同步加载

**`index.html` 中实际调用的 API**：

| API | 调用位置 | 用途 |
|-----|---------|------|
| `new zip.ZipReader(reader)` | 第 483/489/745/753 行 | ZIP 读取器构造函数，接受 BlobReader 参数 |
| `new zip.BlobReader(blob)` | 第 483/489/745/753 行 | 将浏览器 File/Blob 对象转为 Reader 接口（`getEntries` 等方法的输入） |
| `new zip.BlobWriter(mimeType)` | 第 488/752 行 | 输出 Writer，将 ZIP 条目内容输出为指定 MIME 类型的 Blob（用于嵌套 ZIP） |
| `new zip.TextWriter()` | 第 495/515/760 行 | 输出 Writer，将 ZIP 条目内容输出为 UTF-8 字符串（用于文本解析） |
| `reader.getEntries()` | 第 484/490/747/755 行 | 异步获取 ZIP 内所有文件/目录条目列表 |
| `entry.getData(writer)` | 第 488/495/515/752/760 行 | 异步读取条目数据到指定 Writer，返回 Writer 结果 |
| `reader.close()` | 第 537/540/865/866/871/876 行 | 关闭读取器释放底层资源（FileReader、Blob URL 等） |

**异步模式**：zip.js 的所有 I/O 操作（`getEntries`, `getData`）都是基于 Promise 的异步 API，因此 `extractDeviceInfo`、`processZipFile` 使用 `async/await` 模式。

---

### 7. `input/` — 默认输入目录

CLI 版和 GUI 版均默认从此目录读取诊断 ZIP 文件。目录由程序自动创建（`input_dir.mkdir(parents=True, exist_ok=True)`），用户只需将诊断 ZIP 放入即可。目录在 `.gitignore` 中未显式忽略，但如果目录为空通常不会提交至 Git（Git 不跟踪空目录）。

---

### 8. 其他配置文件

| 文件 | 用途 |
|------|------|
| `.gitignore` | Python 生态标准 gitignore（139 行），覆盖：`__pycache__/`、`*.py[cod]`、虚拟环境（`venv/`, `env/`, `ENV/`）、IDE 文件（`.spyderproject`, `.ropeproject`）、构建产物（`dist/`, `build/`, `*.egg-info/`）、测试（`.pytest_cache/`, `.tox/`）、环境变量（`.env`） |
| `LICENSE` | GNU General Public License v3 全文（674 行），含 Preamble + 17 个条款 + "How to Apply" 指引 |
| `.github/FUNDING.yml` | GitHub 赞助配置：`custom: ['http://119.29.227.6/pay']` |
| `.gitee/ISSUE_TEMPLATE.zh-CN.md` | Gitee Issue 模板（3 个字段：问题原因/重现步骤/报错信息） |
| `.gitee/PULL_REQUEST_TEMPLATE.zh-CN.md` | Gitee PR 模板（4 个字段：关联 Issue/原因/描述/测试用例） |
| `.claude/settings.local.json` | Claude Code 本地设置文件（开发者本地配置文件，非项目分发包） |

---

## 软件架构 — 跨三端统一数据流

以下展示从用户获取诊断 ZIP 到最终报告输出的完整数据流，覆盖 CLI/GUI/Web 三端的共有路径和差异：

```
用户获取诊断 ZIP (小米/HyperOS 设备 → 设置 → 连续点击处理器 → 导出)
      │
      ▼
┌──────────────────────────────────────────────────────────┐
│                    入口层（三选一）                        │
│  CLI: battery_calc.py → main() → argparse 解析参数       │
│  GUI: battery_gui.py → BatteryHealthApp.run() → tk mainloop │
│  Web: index.html → handleFileSelect() → extractDeviceInfo() │
└──────────────────────┬───────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────┐
│          第一层 ZIP 解析 — 穿透外层 ZIP                    │
│                                                          │
│  CLI/GUI: zipfile.ZipFile(zip_path) → namelist()          │
│           → 列表推导式 [n for n in ... if n.endswith('.zip')] │
│  Web:    zip.ZipReader(new zip.BlobReader(file))          │
│           → getEntries() → filter(.zip suffix)            │
│                                                          │
│  ─── 若无内层 .zip → ValueError 中断 ───                 │
└──────────────────────┬───────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────┐
│          第二层 ZIP 解析 — 内层 ZIP 文件匹配              │
│                                                          │
│  CLI/GUI: outer_zip.read(name) → io.BytesIO(data)         │
│           → zipfile.ZipFile(BytesIO) → namelist()         │
│  Web:    entry.getData(new zip.BlobWriter('application/zip')) │
│           → new zip.ZipReader(new zip.BlobReader(blob))   │
│           → getEntries()                                  │
│                                                          │
│  文件名模糊匹配 (三种实现共用同一策略):                     │
│    _find_file(zf, 'android.hardware.health', '.txt')      │
│      → prefix in name AND name.endswith(suffix)           │
│    _find_file(zf, 'bugreport', '.txt')                     │
│      → prefix in name AND name.endswith(suffix)           │
└──────────────────────┬───────────────────────────────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
┌──────────────┐ ┌───────────┐ ┌──────────────────────────┐
│ health 文件   │ │ bugreport  │ │ [可选] 多个内层 ZIP       │
│ 正则提取      │ │ 文件正则    │ │ → 逐个解析直到关键字段齐  │
└──────┬───────┘ └─────┬─────┘ │ (CLI/GUI有提前退出,Web无)│
       │               │        └──────────────────────────┘
       │               │
       ▼               ▼
┌──────────────┐ ┌─────────────────────────────────────────┐
│ 设计容量      │ │ 设备型号: [ro.product.marketname] 优先   │
│ (μAh→mAh)    │ │         [ro.product.model] 备用          │
│ 循环次数      │ │ 报告时间: == dumpstate: ...              │
│ 满充容量      │ │ 统计区块: Statistics since last charge:  │
│ (μAh→mAh)    │ │          ... (空行截止/文件尾兜底)       │
└──────┬───────┘ └─────────────┬───────────────────────────┘
       │                       │
       │   [提前退出条件检查]     │
       │   CLI/GUI: design_capacity != None              │
       │            && current_capacity != None → break  │
       └───────────┬───────────┘
                   │
                   ▼
          [设计容量缺失？]
          ├─ 是 → CLI: --capacity 参数 → prompt_design_capacity()
          │       GUI: capacity_entry 手动输入
          │       Web: 显示手动输入框 + 计算按钮 (降级到手动模式)
          └─ 否 → 继续

                   ▼
          [当前容量缺失？]
          ├─ 是 → 报错 / 部分信息展示
          └─ 否 → 继续

                   ▼
┌──────────────────────────────────────────────────────────┐
│              健康度计算 & 报告生成                         │
│                                                          │
│  current_capacity = min_learned_capacity                 │
│  health_percentage = (current / design_capacity) × 100   │
│  rating = 五档评级表查找 (线性扫描或 if/elif 链)          │
│                                                          │
│  CLI:  ReportPrinter.print_report() → ANSI 彩色终端输出   │
│        + _strip_ansi() → 纯文本 for --output 文件         │
│  GUI:  _build_report() → tk.Text 控件 (tag 高亮健康度行)  │
│  Web:  processZipFile() → resultDiv.innerHTML (HTML 报告) │
└──────────────────────────────────────────────────────────┘
```

### 三端实现差异对照表 (v2)

| 功能点 | CLI (`battery_calc.py`) | GUI (`battery_gui.py`) | Web (`index.html`) |
|--------|------------------------|----------------------|-------------------|
| 核心模块 | `from battery_core import *` | `from battery_core import *` | 独立 JS（逻辑等价） |
| ZIP 解析库 | `zipfile` (标准库) | `zipfile` (标准库) | `zip.js` (第三方) |
| 正则引擎 | `re` 预编译 (battery_core 类变量) | `re` 预编译 (battery_core 类变量) | JS `const RE_*` 顶层声明 |
| 提取器提前退出 | ✓ | ✓ | ✓ (v2 已修复) |
| 评分方式 | 统一 `_RATING_TABLE` 查找 | 统一 `_RATING_TABLE` 查找 | 统一 `RATING_TABLE` 查找 |
| 评分边界 | `(100.0001, inf)` | `(100.0001, inf)` | `[100.0001, Infinity]` |
| 设计容量降级 | `--capacity` → 交互式 | 手动输入框 | 手动输入框 |
| 多文件批量 | ✓ | ✗ | ✗ |
| 报告文件输出 | ✓ (`--output`) | ✗ | ✗ |
| 防 XSS | N/A (终端) | N/A (原生控件) | ✓ `escHtml()` |

---

## 三端完整函数调用链

### CLI 端 (`battery_calc.py`)

```
__name__ == '__main__'
  └── sys.exit(main())
        ├── build_parser() → parse_args()
        ├── Colors().__init__()
        │     ├── _detect_support()
        │     │     ├── sys.stdout.isatty()
        │     │     └── _enable_windows_ansi()
        │     │           └── ctypes.windll.kernel32.SetConsoleMode()
        │     └── _init_styles()
        ├── BatteryExtractor()
        ├── ReportPrinter(colors)
        │
        └── for each .zip file:
              ├── extractor.extract(zip_path) → BatteryInfo
              │     ├── _find_inner_zips(outer_zip)
              │     └── for inner_name:
              │           ├── outer_zip.read(inner_name)
              │           ├── zipfile.ZipFile(BytesIO(inner_data))
              │           ├── _find_file(inner_zip, 'android.hardware.health', '.txt')
              │           ├── _find_file(inner_zip, 'bugreport', '.txt')
              │           ├── [_parse_health_stream]: 逐行正则提取 3 字段
              │           ├── [_parse_bugreport_stream]: 逐行提取设备/时间/统计区块
              │           │     └── _parse_stats_text(text, info)
              │           └── [提前退出]: has_design_capacity && current_capacity
              │
              ├── [设计容量缺失] → args.capacity 或 prompt_design_capacity()
              ├── [当前容量缺失] → 跳过
              └── printer.print_report(info, filename) → 终端 + _strip_ansi() 纯文本
```

### GUI 端 (`battery_gui.py`)

```
__name__ == '__main__'
  └── main()
        └── BatteryHealthApp().__init__()
              ├── BatteryExtractor()
              ├── _build_ui()         # 构建全部 UI 组件 (ttk + tk 混用)
              │     └── 绑定: analyze_btn → _analyze
              │             refresh_btn → _refresh_file_list
              │             file_combo → file_var (StringVar)
              │             browse_btn → _browse_file
              ├── _refresh_file_list() # 启动时扫描 input/
              └── run()                # root.mainloop() 阻塞等待

用户操作触发:
  _browse_file()
    └── filedialog.askopenfilename() → file_var.set()
  _refresh_file_list()
    └── input_dir.mkdir() + 扫描 *.zip → file_combo['values']
  _analyze()
    ├── extractor.extract(zip_path) → BatteryInfo
    │     └── [同 CLI 提取逻辑]
    ├── [设计容量缺失] → capacity_entry 手动输入
    ├── [当前容量缺失] → _build_error_report(info)
    ├── _build_report(info) → 纯文本字符串
    ├── _show_result(text)
    │     └── result_text.insert() → _highlight_result()
    │           └── Text tag_add + tag_config (前景色+加粗)
    └── [异常处理] 四种异常 + 通用 Exception
```

### Web 端 (`index.html`)

```
DOMContentLoaded
  └── addEventListener('change', handleFileSelect) on #zip-file
      addEventListener('click', calculateBatteryCapacity) on #calculate-btn

用户选择文件 → handleFileSelect()
  ├── 重置 autoExtractedInfo (全部 null)
  ├── 隐藏 manual-input / calculate-btn / result / status
  └── extractDeviceInfo(file)  [async]
        ├── new zip.ZipReader(new zip.BlobReader(file))
        ├── getEntries() → 遍历外层
        │     └── entry.getData(new zip.BlobWriter('application/zip'))
        │           → new zip.ZipReader(new zip.BlobReader(innerZipBlob))
        │           → getEntries() → 遍历内层
        │                 ├── [health .txt]: 正则提取 designCapacity/cycleCount/fullCapacity
        │                 └── [bugreport .txt]:
        │                       ├── extractDeviceInfoFromText(content)
        │                       ├── extractDataFromText(content)
        │                       └── extractBatteryCapacityFromStatistics(statistics)
        │
        ├── [成功] processZipFile(file, designCapacity)  → 自动继续
        └── [失败] 显示手动输入框 + 计算按钮

用户点击"计算" → calculateBatteryCapacity()
  └── processZipFile(file, initialCapacity)  [async]
        ├── [再次解析 ZIP，复用 extractDataFromText]
        ├── currentCapacity = minLearnedCapacity
        ├── percentage = (current / finalCapacity) * 100
        ├── rating = getBatteryRating(percentage)
        ├── color = getRatingColor(percentage)
        ├── [构建 HTML 报告字符串]
        │     ├── 📊 基本信息
        │     ├── 🔧 电池硬件信息
        │     ├── translateBatteryInfoOnly(statistics) → 翻译对照
        │     └── 原始统计数据 (折叠区)
        └── showResult(div, html, true) → innerHTML + className
```

---

## 安装与使用

### 环境要求

- **CLI 版**：Python 3.8+，仅标准库（`argparse`, `zipfile`, `io`, `re`, `sys`, `pathlib`, `dataclasses`, `typing`, `ctypes`）
- **GUI 版**：Python 3.8+ + tkinter（Python 标准库自带，但部分 Linux 发行版需单独安装 `python3-tk` 包；Windows/macOS 安装器自带）
- **网页版**：现代浏览器（Chrome/Firefox/Edge/Safari），支持 ES6 (`async/await`, `let/const`, 模板字符串) 和 `Blob` API

### 获取诊断文件

1. 在小米/HyperOS 设备上进入 **设置 → 全部参数与信息 → 连续点击"处理器"**（约 5-7 次）
2. 或在拨号界面输入 `*#*#284#*#*` 一键抓包（网页版提供拨号链接快捷入口）
3. 等待系统生成诊断文件（约 10-30 秒），通过文件管理器导出 ZIP

> 据说先把电量充到 100% 再继续充 30 分钟，诊断数据更准确。

### CLI 命令行方式

```bash
# 分析 input/ 目录下所有 ZIP 文件
python battery_calc.py

# 指定输入目录
python battery_calc.py --input "C:\diagnostics"

# 指定默认设计容量（ZIP 中未检测到时使用此值替代交互式提示）
python battery_calc.py --capacity 5000

# 保存报告到文件（多个文件报告用 --- 分隔）
python battery_calc.py --output report.txt

# 禁用彩色输出（重定向到文件时用）
python battery_calc.py --no-color
```

### GUI 图形界面方式

```bash
# 方式 1：直接运行 Python 脚本
python battery_gui.py

# 方式 2：双击 run.bat（自动调用 VBS 无窗口启动，CMD 一闪而过）
# 方式 3：双击 run_gui.vbs（直接无 CMD 窗口残留）
```

GUI 界面操作：选择诊断文件（下拉列表或"浏览..."）→ 可选手动输入设计容量 → 点击"开始分析" → 查看结果（健康度行彩色高亮）→ "刷新文件列表"重新扫描 input/ 目录。

### 网页版方式

直接用浏览器打开 `index.html`，选择诊断 ZIP 文件即可自动分析。如果自动提取设计容量失败，页面会显示手动输入框和"计算"按钮，手动输入设计容量后点击即可。结果页面包含折叠/展开的"电池详细信息"（翻译对照 + 原始数据）。

---

## 许可证

本项目基于 **GNU General Public License v3 (GPLv3)** 开源。

Copyright © HikiMu慕鱼酱

---

## 开源依赖

| 依赖 | 许可证 | 用途 |
|------|--------|------|
| [zip.js](https://github.com/gildas-lormeau/zip.js) | BSD 3-Clause | 网页版浏览器端 ZIP 解析核心 |
| Python 标准库 (`argparse`, `zipfile`, `tkinter`, `ctypes`, `dataclasses`, `re`, `pathlib`, `io`, `sys`, `typing`) | PSF License | CLI/GUI 版全部运行时依赖 |

项目不依赖任何第三方 Python 包。`pip install` 不是必需的——克隆仓库后 `python battery_calc.py` 或 `python battery_gui.py` 即可运行。
