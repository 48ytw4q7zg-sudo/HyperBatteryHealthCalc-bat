# Windows portable acceptance checkpoint (historical)

Current delivery and acceptance: [Save Report and real-data acceptance, 2026-09-08](D:/1/HyperBatteryHealthCalc-main/docs/gui-save-and-real-data-acceptance-20260908.md).

The content below records the earlier candidate only. Its artifact hashes and
statements about the missing GUI export action are historical, not the current
application state. The newer report above supersedes this checkpoint.

Date: 2026-09-07. Target agreed with the user: Windows 10/11, x64.

## Decision

The current battery candidate has passed the recorded automated application,
packaging, relocation and clean Windows 11 Sandbox checks. A subsequent native
walkthrough passed file selection, analysis and normal close using a synthetic
archive. The current GUI exposes no save/export action; separately verified CLI
exports must not be counted as a GUI export pass. Windows 10 execution remains
unverified. This checkpoint is not a claim that the full two-project goal is
complete or that every Windows version and hardware configuration is supported.

## Current deliverable

- Release directory: `D:\1\HyperBatteryHealthCalc-main\dist\HyperBatteryHealthCalc-Windows-x64-20260907-102223-3d31e0`
- ZIP: `HyperBatteryHealthCalc-Windows-x64.zip`
- ZIP size: 15,363,378 bytes.
- ZIP SHA256: `E90954AB3459F7DD1EC1988DD6886A5CA07B5C51F8F226070798AF09ED0E4F00`
- GUI: `HyperBatteryHealthCalc\HyperBatteryHealthCalc.exe`, 2,335,944 bytes.
- GUI SHA256: `532A72A67986086B31EEA64EE5F5D7B60156DDB6883E5BC8C080439CBD6B64D1`
- CLI: `HyperBatteryHealthCalc\HyperBatteryHealthCalc-cli.exe`, 2,339,016 bytes.
- CLI SHA256: `B47078F8FFDECE9C31DC7E0CC0A2B1738F01242FE8B302A737DDC02BABADE5DA`

Extract the ZIP and keep the entire application folder together. Launch the GUI
executable inside that folder. Do not separate the executable from `_internal`
or try to run it inside the compressed ZIP. The target computer does not need a
separate Python, Node.js, Docker or programming-software installation. A portable
folder used for application data and exports must be writable.

## Application work covered by the existing evidence

- Capacity parsing rejects non-finite and non-positive values; charge-counter
  fallback requires a sufficiently complete charge reading and a valid scale.
- Recognized outer and nested diagnostic logs are combined with explicit
  hardware-design-capacity priority.
- Archive-entry failures are isolated; unsuccessful or corrupt input does not
  commit partially parsed state over valid results.
- Partial reports and manual capacity correction remain available.
- Power-usage parsing is restricted to its intended report sections.
- Browser results reject stale asynchronous responses and escape error text.
- CLI exports are atomic, cannot overwrite the input archive, and use nonzero
  exit codes for noninteractive failures.
- Native GUI work is queued back to the main thread; obsolete selections are
  discarded.
- The latest GUI file-selection repair preserves the selected mapped path,
  including when a same-named root file exists, and rejects stale mappings.

## Verification matrix

| Requirement | Evidence and result | Limit |
| --- | --- | --- |
| Latest selected-path defect | Four targeted reproductions: before repair one passed and three failed; after repair all four passed | Synthetic paths, not the interrupted live file picker |
| Python regression suite | 35 passed, two real-archive cases skipped in the portable repair run | Skips are not passes |
| Browser behavior assertions | 44 assertions passed | Does not replace all manual browser use |
| Source windowed startup | 13 self-test checks passed | Source test uses the build runtime |
| Frozen GUI and CLI | 14 checks each passed | Synthetic test data |
| CLI failures and exports | Help, default and relative export paths passed; missing/corrupt input returned the expected exit 1 | Expected failures are recorded separately |
| Native binaries | 67 native PE files were AMD64; GUI subsystem 2, CLI subsystem 3 | No x86 or native ARM64 claim |
| Relocation | Chinese/space-containing paths and unrelated working directory passed with PATH limited to System32 | No physical USB device was used |
| Clean target environment | Both executables passed 14 checks each in an actual Windows Sandbox without Python/Node/Docker on PATH | Guest kernel 10.0.26100 is Windows 11, not Windows 10 |
| Native interface | Fresh synthetic file selection, analysis and normal close passed; 5000 mAh design, 4500 mAh current, 90.00% health | Earlier manual closure remains historical, not a crash; the current GUI has no save/export action |
| Source review | Separate successful GPT-6 Astra/max invocation reviewed the repaired source hashes | Static scoped review, not backend/billing attestation or OS execution |

## Evidence locations

- Build result: `D:\1\HyperBatteryHealthCalc-main\.build\windows-20260907-102223-3d31e0\evidence\build-result.json`
- Build-result SHA256: `87476364D9B130E290D9823FFA639778CA959B9AEAF88C2EDD67D39317D0CD5B`
- Repair handoff: `D:\1\HyperBatteryHealthCalc-main\.build\zip-selection-repair-20260907-101953-74089f\repair-summary.json`
- Clean Sandbox result: `D:\1\HyperBatteryHealthCalc-main\.build\clean-windows-20260907-e90954\out\result.json`
- Sandbox-result SHA256: `036751DC22AE46CF0822C36F1B7AA39C460278BEE1637AB126F15C209B081E2D`
- Independent repaired-source review: `D:\1\ocsjs-ai-answer-service\.build\repaired-source-audit-20260907.txt`
- Native interaction record: `D:\1\ocsjs-ai-answer-service\.build\native-ui-acceptance-20260907.json`
- Subsequent native flow evidence: `D:\1\HyperBatteryHealthCalc-main\.build\native-ui-completion-20260907-e90954\acceptance.json`; zero test windows and processes remained after normal close.

The repaired `battery_gui.py` hash is
`88C546E6A80689EDA68B05ADD96E28A3E325053F8133A469ECD96C4500D78AC3`.
The repaired `packaging/test_portable.py` hash is
`A104D66ADD27B300996C4D67FB21EFF9C81AC9BD7A49F557B8BE24328E808A0B`.
Older release directories and earlier failed audit reports remain historical
evidence and must not be substituted for this candidate.

## Remaining acceptance

1. Run the exact candidate on an actual Windows 10 x64 computer, record the OS
   version and executable/ZIP hashes, and exercise startup, analysis and export.
2. GUI report export is a confirmed interface gap. File selection and analysis
   now have live evidence, but there is no GUI save/export control and no automatic
   report in the task-owned expected output directories. A GUI export decision
   remains separate from the already-verified CLI export path.
3. A physical removable-drive run remains unverified; relocation checks support
   portability but do not prove every drive, permission policy or managed device.

No Windows 7/8.1, 32-bit Windows, real-account integration, code-signing trust,
managed-device exemption or universal hardware claim is made. No security setting
or provider credential was changed for this checkpoint.
