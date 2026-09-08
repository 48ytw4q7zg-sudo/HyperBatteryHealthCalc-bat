审计完成。**当前候选存在 1 项 P2 文件选择错误；便携路径正确性判为 FAIL。** 已有 Windows 11 构建与运行记录相互一致，但 Windows 10、干净 Windows 10/11 环境、字节级可复现构建以及本次审计模型资格仍为 **PENDING／未验证**。在限定的 7 个源文件中未发现 P0/P1 问题。

本次仅进行了文件读取、证据统计和 SHA256 计算；未修改文件，未运行被审程序、构建脚本或测试，未使用 git、其他代理或 harness，未读取凭据或真实诊断归档。

发现按严重程度排列：

- **P2 — GUI 可能分析与下拉列表选择不符的同名 ZIP。**  
  位置：[HyperBatteryHealthCalc-bat/battery_gui.py:160](D:/1/HyperBatteryHealthCalc-main/HyperBatteryHealthCalc-bat/battery_gui.py:160)，涉及第 160–166 行。  
  下拉列表为 `input/sample.zip` 保存的显示值是 `sample.zip`。如果程序旁同时存在另一个 `sample.zip`，`_resolve_selected_zip()` 会先将该显示值解析为程序目录下的路径并直接返回，随后才检查 `file_path_index`。因此，用户选择列表中的文件时，可能得到另一个归档的电池结果。递归列表中的同名相对路径也存在这一问题。  
  应让列表项优先使用已保存的路径映射，并单独处理浏览器返回的绝对路径。此结论来自当前代码的分支顺序；遵照任务约束，未执行复现。

- **P3 — ZIP 构建没有消除时间戳差异，当前 SHA256 不能证明同源构建可产生相同字节。**  
  位置：[packaging/verify_portable.py:136](D:/1/HyperBatteryHealthCalc-main/packaging/verify_portable.py:136)，涉及第 136–139 行。  
  打包直接使用 `archive.write()` 写入新建目录和文件，保留其文件系统时间戳。即使载荷内容相同，不同构建时间也可能改变 ZIP 字节及散列。源文件散列、依赖版本和产物清单提供了追溯依据；若验收要求包含字节级可复现，应固定 ZIP 元数据并另行比较独立重建结果。

各项判定如下。表中的“已有记录 PASS”表示我核对了本次构建留下的证据，未重新执行相应检查。

| 审计项 | 判定 | 依据及范围 |
|---|---|---|
| 便携路径正确性 | **FAIL** | GUI 存在上述同名 ZIP 遮蔽问题。CLI 默认及相对路径按程序目录解析的实现与已有记录一致。 |
| GUI 无控制台行为 | **PASS，静态＋已有记录** | `windows.spec` 设置 `console=False`；流配置、颜色检测、交互判断均处理 `None`。GUI 打包记录显示 `stdout_is_none=true`、`stderr_is_none=true`，PE subsystem 为 `2`。 |
| CLI 控制台行为 | **PASS，静态＋已有记录** | CLI 设置 `console=True`，PE subsystem 为 `3`；已有帮助输出、正常处理和失败退出检查记录。 |
| 包内并列运行时 | **PASS，清单＋已有记录** | GUI/CLI 共享 `_internal`；清单包含 `python314.dll`、Tcl/Tk、`VCRUNTIME140.dll`、`VCRUNTIME140_1.dll`、`ucrtbase.dll`。67 个 PE 记录均为 AMD64；自测记录确认 Tcl/Tk 资源位于包内。 |
| 中文、空格、迁移及不同工作目录 | **PASS，已有记录** | 记录显示从 ZIP 解压后重命名目录，以 `C:\WINDOWS\System32` 为最小 PATH，并从其他工作目录运行。 |
| 清理范围 | **PASS，静态审查** | Python `owned()` 检查 `.build`／`dist` 子路径、解析后的范围和 symlink/junction；两处递归删除前再次检查。PowerShell 发布移动前检查绝对路径和重解析点。未发现所审代码中的直接越界清理路径。 |
| 报告 I/O 与既有报告保护 | **PASS，静态＋已有记录** | 同目录临时文件写完后使用 `os.replace()`；失败时清理临时文件；无可导出报告时不替换旧报告；拒绝覆盖本次扫描到的输入 ZIP。原始测试记录包含导出失败保留旧报告、部分报告保留及导出失败返回非零状态。 |
| 防止夹带用户数据 | **PASS，打包规则／清单级；内容级保证 PENDING** | spec 未收集项目树、`input` 或 `reports`；自测归档为代码生成的合成数据。997 项清单没有命中所设私密文件规则，记录中的 `input`／`reports` 为空。未独立解包检查 EXE 内嵌内容，且 `battery_core.py` 不在本次源码阅读范围内。 |
| 构建证据及源文件关联 | **PASS** | 当前 7 个源文件的 SHA256 均与 `source-hashes.json` 一致；清单实际记录数 997、字节合计 31,802,254，均与构建摘要一致。 |
| 字节级可复现构建 | **PENDING／未验证** | 存在上述时间戳问题，且没有第二次独立重建比较证据。 |
| Windows 10、干净 Windows 10/11、实体 USB | **PENDING／未验证** | 证据仅支持记录中的 Windows 11 主机；验证文件明确列出了这些未执行环境。 |

关键证据为：

- [source/source-verification.json](D:/1/HyperBatteryHealthCalc-main/.build/windows-20260907-084446-574cd0/evidence/source/source-verification.json:2)：33 项 Python 测试中 **31 通过、2 跳过**，并记录 **44 项 JS 断言通过**。JS 原始日志还包含一条 `Error: initial failure` 调用栈；验证器对 Node 的退出码有零值检查，当前成功记录与该错误路径日志并存。
- [bundle/bundle-verification.json](D:/1/HyperBatteryHealthCalc-main/.build/windows-20260907-084446-574cd0/evidence/bundle/bundle-verification.json:16)：GUI、CLI 各 **14 项合成打包检查通过**；运行时记录为 Python `3.14.4`、Tcl/Tk `8.6.15`。
- [host-details.json](D:/1/HyperBatteryHealthCalc-main/.build/windows-20260907-084446-574cd0/evidence/host-details.json:1)：记录主机为 Windows 11 Pro 25H2、OS build `26200.9168`、x64。
- [build-result.json](D:/1/HyperBatteryHealthCalc-main/.build/windows-20260907-084446-574cd0/evidence/build-result.json:6) 与包验证记录中的 ZIP SHA256 均为  
  `2e03579b6f3473998e26216e3b794a2ff2ec1abd1f1967bbe4deed05bdb331c9`。  
  **这与任务提供值一致；本次未直接读取 ZIP 重算其散列。**

以下是本次实算的源文件 SHA256。路径相对于 `D:\1\HyperBatteryHealthCalc-main`，7 项均匹配构建记录：

```text
F58231AD772512B6D695106AEBF5DDF520342A666EB2A1D94F81DEC53D4E29EA  HyperBatteryHealthCalc-bat\battery_gui.py
1F6F2F9DDA9CF0AFFB05FFE61E0C4B173C80AF6E3F2174AE8D2FA6105F32176A  HyperBatteryHealthCalc-bat\battery_calc.py
0468694158DA7E74905C8D859D7852F34B5337F8B5E235B7534014EAF0A0F2C4  HyperBatteryHealthCalc-bat\report_io.py
241874B7D1BF1F86E65FDC73BB00A26F7B1478CB74A2AF11CC8946C98892E97A  HyperBatteryHealthCalc-bat\portable_entry.py
C3DFDBD76F16D4C28FC5162F0BB5B1E4DC0339E0D8ADCA1D17BDF1862A681190  packaging\windows.spec
9CCE5DF62DD18FD5E842D61E793C8D26006F0DBDA816B95B52240544792E8C5A  packaging\verify_portable.py
77FC07FE00C6E54CDFC872A633CCF87FE3BDC2A5C10CB8BC6CFFF1EEC17525B6  build_windows.ps1
```

已读取证据文件的实算 SHA256 如下；路径相对于 `.build\windows-20260907-084446-574cd0\evidence`：

```text
98677FD3755A007CC3486105E37252738F1D0C6B56B7DD3C977C79E1C2ECB9CA  build-result.json
EE3BEC820C6A38C2D93523BFD0ED20FE4D4F45CD51317A460EE1443A7693CBDD  source-hashes.json
7DFB57FBD70C4EDEB2FC5608ED8150A1B2FBE41A0553B5E8A1735B05C0ED67D7  host-details.json
05AE3FCC084B2D85DFDB728149778128C52AB3DDB991F1CEA740082DB903E214  requirements-resolved.txt
DF8A352F1D3B64287853EEF696BB072F6541A194FB2D4F6431A16A351BBDB8AF  source\source-verification.json
5E1A4599B7C7E9F450BDE2FFE95917F7E7CAABC36218D41862322F82B145F271  source\python-tests.txt
6AFE9DB37ADBB1DE49BF7ACDD1A71D5FF5F776A1F81A017ADD2E080A2610E64F  source\node-tests.txt
A86F4BAD638E4E09FD29DA4BB875C2058E900ABED054F04606A5F3800651E818  bundle\bundle-verification.json
98A5234C6D34934AA798B2B2F1C634AF73E0ABFD53E211C8F90B80683A1082CA  bundle\HyperBatteryHealthCalc-self-test.json
B6A45DC017F27E1EC43D6B8FE664E5D57C57C92A594884FFA5524B6AF5E1AA3D  bundle\HyperBatteryHealthCalc-cli-self-test.json
AA8B279B181C1D924534A5C98287741BAB784A7516E7670FA26421565562CFAE  bundle\cli-help.txt
A6D6C27C27C0829654A04A0BD6695322689E0009474A550911C17FC9388A2C1F  bundle\cli-default.txt
CE1E71B87CCBAA72A4DCC07D8E79D5680BDC2A5DF7D6E6418ED5BDE9791EE402  bundle\cli-relative.txt
191C7DD103E748067149FEF8CCEBA363C32ED22A475F6934DF617F623F756BE0  bundle\cli-missing-input.txt
4B6CACC4E9AC1374C8A2CC0F07C6AADEE29D12A78EB53FB8988F4E6A997214DF  bundle\cli-corrupt-input.txt
```

模型核验状态：**请求为 `gpt-6-astra`，effort 为 `max`**；宿主提供的可用模型目录列有该 ID 及该 effort。当前会话没有提供实际已配置模型／effort 的可核验回执，后端具体模型身份及“审计时最新 GA 旗舰”资格均为 **未验证**。因此，本报告不能作为 AGENTS.md §D 所要求的模型资格已核验凭据。

工具异常已纠正：首次错误地将证据路径置于 `HyperBatteryHealthCalc-bat` 下，读取返回以下两条错误；随后读取项目根目录下的正确路径成功，后续读取和散列计算均以退出码 `0` 完成。

```text
Cannot find path 'D:\1\HyperBatteryHealthCalc-main\HyperBatteryHealthCalc-bat\.build\windows-20260907-084446-574cd0\evidence\build-result.json' because it does not exist.
Cannot find path 'D:\1\HyperBatteryHealthCalc-main\HyperBatteryHealthCalc-bat\.build\windows-20260907-084446-574cd0\evidence\source-hashes.json' because it does not exist.
```
