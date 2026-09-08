> 2026-09-08 验收范围更新：用户明确允许省略 Windows 10 实机测试。目标平台仍为 Windows 10/11 x64；Windows 10 实机结果为“未验证，用户已豁免”，不再作为交付阻塞项。下文历史记录中“Windows 10 待验收/待提供环境”等表述仅反映当时状态，以本条更新为准。Windows 11 的已有运行证据不变；本更新不扩大为 Windows 7/8.1、32 位或原生 ARM64 支持，也不声称完成了实体 U 盘实测。

# Save Report and real-data acceptance

Updated: 2026-09-08, Asia/Singapore (UTC+8). Build-directory timestamps use UTC.
Agreed operating-system target: Windows 10/11 x64. The user confirmed that a
Windows 10 computer is currently unavailable; that target remains unverified.

## Current result

The user-requested native Save Report button is implemented, independently
reviewed and exercised in the current frozen executable. Windows 11 native ZIP
extraction, actual save-dialog interaction and clean Sandbox folder-based
execution passed. Two previously skipped real-phone regression cases were also
run separately against the single user-authorized archive and both passed.

This report closes the Save Report feature and the recorded Windows 11 checks.
It does not mark the entire two-project goal complete or certify every Windows
version, physical USB device, managed-device policy or real AI account.

## Current battery deliverable

- [Portable ZIP](D:/1/HyperBatteryHealthCalc-main/dist/HyperBatteryHealthCalc-Windows-x64-20260907-145748-f98fd2/HyperBatteryHealthCalc-Windows-x64.zip): 15,373,606 bytes.
- ZIP SHA256: `9086622D48D4E43920486EA5B24AA7FE4D701A1C541A0CE3C3C4C0269AEE609D`.
- [GUI executable](D:/1/HyperBatteryHealthCalc-main/dist/HyperBatteryHealthCalc-Windows-x64-20260907-145748-f98fd2/HyperBatteryHealthCalc/HyperBatteryHealthCalc.exe): 2,340,258 bytes.
- GUI SHA256: `4B25C630687808B4CB489FA4B884A60A465AFF207992FF1FD4CFE95602B722DA`.
- [CLI executable](D:/1/HyperBatteryHealthCalc-main/dist/HyperBatteryHealthCalc-Windows-x64-20260907-145748-f98fd2/HyperBatteryHealthCalc/HyperBatteryHealthCalc-cli.exe): 2,343,330 bytes.
- CLI SHA256: `1258FD77ABF4F1020BDC496D8336BECEC827372A7A4FDFC5B28DD3C1F42BA007`.
- Expanded payload: 997 files, 31,811,180 bytes.

Extract the ZIP and retain the whole application folder, including `_internal`.
Launch the GUI, select a diagnostic ZIP and run analysis. Enter a design capacity
manually only when needed. Save Report then opens the native TXT save dialog.
Choose a writable destination. Separate Python, Node.js, Docker or programming
software is not needed by the tested portable application.

## Implemented behavior

- Save is disabled before a result, during analysis, after input edits and after
  failed or stale analyses. Complete and partial reports use the analyzed text
  snapshot rather than regenerating a result from changed inputs.
- Cancelling the dialog retains the result and permits another save attempt.
- The dialog result is rechecked against the report snapshot before writing.
- TXT output uses UTF-8 BOM and CRLF for Windows Notepad compatibility.
- A same-directory temporary file is flushed and closed before replacement.
  Precommit failures preserve an existing destination and remain retryable.
- The diagnostic ZIP, its resolved aliases and existing hardlinks are protected
  from replacement. Non-TXT output names and empty reports are rejected.
- Existing report calculations, partial-data explanations and CLI behavior were
  retained. No provider, credential or application security default was changed.

## Verification

| Check | Actual result | Boundary |
| --- | --- | --- |
| New export tests | 20 passed | Synthetic state, cancellation, failure injection, encoding and input protection |
| Related packaging regressions | 31 passed, no skips | Includes those 20 new tests and 11 existing tests; do not add these counts together |
| Existing isolated build suite | 35 passed, two real-data tests skipped | Private phone data was absent from the isolated build source |
| Existing browser logic | 44 assertions passed | No browser source changed for this feature |
| Source no-console self-test | 19 passed, exit 0 | `pythonw.exe`, explicitly not a frozen run |
| Windows native ZIP extraction | Passed with stock PowerShell 5.1, System32-only PATH | 997 files and exact GUI/CLI hashes matched; no Python used for extraction |
| Actual frozen GUI interaction | Passed | Disabled/enabled states, native dialog, cancel/retry, save, input-edit invalidation and normal close |
| Actual exported file | 1,442 bytes; BOM and CRLF verified | Synthetic report, Chinese/space filename; input ZIP unchanged |
| Clean Windows Sandbox GUI | 20 passed, exit 0 | Frozen x64, bundled Tcl/Tk; pre-extracted folder copied into guest-local storage |
| Clean Windows Sandbox CLI | 20 passed, exit 0 | Same exact candidate and guest-local self-test data |
| Authorized real-phone regressions | Two passed, zero skipped | Source-mode execution against the one authorized ZIP; raw output suppressed |

Sandbox guest kernel: `10.0.26100.0`, Windows 11, not Windows 10. The runner
installed no software and limited PATH to `C:\Windows\System32`. The native GUI
test process and the exact completed Sandbox launcher were closed after testing.

## Independent review and source binding

The complete independent Codex CLI invocation requested `gpt-6-astra` with
`model_reasoning_effort=max` and exited 0. All four review categories passed;
no scoped P0/P1/P2 finding was confirmed for ordinary local TXT destinations.
The first review attempt was incomplete due to truncated output and is not
counted as approval. The replacement invocation read each file separately.

| Reviewed source | SHA256 |
| --- | --- |
| [battery_gui.py](D:/1/HyperBatteryHealthCalc-main/HyperBatteryHealthCalc-bat/battery_gui.py) | `058CDCF03E50E2A292FAD84793D35ADFC08DA36718813BE85B69BD446E74F988` |
| [report_io.py](D:/1/HyperBatteryHealthCalc-main/HyperBatteryHealthCalc-bat/report_io.py) | `612C7008779868D3882D550C59A30A91FE58AEA35996316EC6D3A3965466718B` |
| [portable_entry.py](D:/1/HyperBatteryHealthCalc-main/HyperBatteryHealthCalc-bat/portable_entry.py) | `15B073DB2238FEE124FFF57D78EDBD0993126F067AEB05FCF21F7C4737601926` |
| [test_gui_export.py](D:/1/HyperBatteryHealthCalc-main/packaging/test_gui_export.py) | `10E5AD641F24543231675AD931BE36FA788E33710F4AF6E62E7E7F1BB3427073` |

The three runtime source hashes also match the completed build's source
manifest. The new test file was independently reviewed and executed separately.

- [Complete review](D:/1/HyperBatteryHealthCalc-main/.build/gui-save-repair-20260907-145334-c13381/independent-gui-save-audit-complete.txt).
- Review SHA256: `AAB59C65F4068F2DEA16C2699A9F9240B83770950CBFBAD20790EEC1F85B35B3`.
- CLI session: `01a07c6a-74f7-7241-bd1a-135426995011`.
- Official model eligibility was checked at audit time against the [OpenAI model catalog](https://developers.openai.com/api/docs/models) and [GPT-6 Astra documentation](https://developers.openai.com/api/docs/models/gpt-6-astra).

The native receipt identifies the requested/configured model route. It does not
attest an unobservable custom backend or billing identity. Static review and
actual artifact execution are recorded separately above.

## Authorized real-phone result

The user explicitly authorized the existing
`HyperBatteryHealthCalc-bat/input/bugreport-2026-06-23-100941.zip`.
It was read locally, not copied into the portable release or supplied to Claude
Code/pi. The persisted summary excludes raw statistics and full diagnostic logs.

| Field | Parsed value |
| --- | --- |
| Device model | Xiaomi 15 Pro |
| Diagnostic capture time | 2026-06-23 10:09:41 |
| Design/reference capacity | 6100 mAh, from the batterystats estimated capacity |
| Capacity used by the current health calculation | 4760 mAh, from the minimum learned capacity |
| Computed health metric | 78.0327868852459%, displayed as 78.03% |
| Charge counter | 4757 mAh |
| Charge level at capture | 100% |
| Temperature at capture | 34.5 C |
| Voltage at capture | 4377 mV |
| Cycle count | Not identified; no value fabricated |
| Parser warning count | 0 |

The arithmetic `4760 / 6100 * 100` matches the reported metric. These are values
from the June diagnostic snapshot, not today's live state or a laboratory
capacity measurement. The reference capacity was estimated by batterystats;
it was not relabeled as independently verified manufacturer or hardware data.

- Archive size: 195,631,367 bytes.
- Archive SHA256: `1EDEEF2C4DF7091E77C40AC3ADAE8A97E2BE0A7830C3BE5D5FF6A0DC798C9E2C`.
- [Battery-only summary](D:/1/HyperBatteryHealthCalc-main/.build/real-battery-analysis-20260907-154829-b44ed1/battery-summary.json).
- [Two real-data regression results](D:/1/HyperBatteryHealthCalc-main/.build/real-battery-analysis-20260907-154829-b44ed1/real-test-results.json).
- Both real cases passed, with no skips, no exported raw tracebacks and no
  blocked external-action/write events. Input metadata remained unchanged.

## Execution lanes

The user's current allocation is Codex GPT-6 Astra/max for direction, medium and
hard work, and review; simple shares use Claude Code/pi with GPT-5.6 Sol/max.

- Claude Code: explicit `gpt-5.6-sol` / `max` requests completed successfully and
  exited 0, returning the same model identifier. It formatted synthetic evidence
  and located test entry points; it did not read the real phone archive.
- pi: the user authorized `pic --repair`. The repair tool selected and verified
  `@earendil-works/pi-coding-agent@0.85.1`; subsequent `pic --check` passed.
  Its earlier check had reported a `0.84.2` requirement, which was retained as
  failure evidence rather than silently rewritten.
- pi invocation: `cc-claude`, explicit custom model ID `gpt-5.6-sol`, thinking
  `max`, exit 0 and matching response model. The generated catalog did not list
  Sol; the runtime explicitly accepted the custom ID, without selecting a
  different Claude model. Its simple writing share used synthetic evidence only.
- No native pi authentication or second provider route was introduced. Model
  selection was per invocation; global provider/key/default-model settings were
  not manually edited. Generated bridge refresh followed the normal `pic` path.
- Claude's nonfatal hook warnings and the first incomplete GPT-6 review remain
  recorded. Neither is mislabeled as a successful independent review.

## Evidence and retained limitations

- [Build result](D:/1/HyperBatteryHealthCalc-main/.build/windows-20260907-145748-f98fd2/evidence/build-result.json), SHA256 `03D80B7A910D282392A04CF57D05B859DA44950B1CBFDD8FFF3E43A956D371DC`.
- [Native GUI acceptance](D:/1/HyperBatteryHealthCalc-main/.build/gui-save-native-20260907-908662/acceptance.json), SHA256 `4411F75E9881BF5E08525F2CEE00CCF2326CEB089CB4E3D49ED51D0E6B0534C2`.
- [Native ZIP extraction](D:/1/HyperBatteryHealthCalc-main/.build/native-windows-unzip-20260908-908662/native-extraction-result.json).
- [Successful clean Sandbox acceptance](D:/1/HyperBatteryHealthCalc-main/.build/clean-windows-gui-save-local-20260907-908662/acceptance-summary.json).
- Sandbox raw result SHA256: `84C044B6CD2F873B9DE40CF0927761528A64F50B7775277A19FAA38DB9C3586D`.
- [Earlier incomplete Sandbox attempt](D:/1/HyperBatteryHealthCalc-main/.build/clean-windows-gui-save-20260907-908662/incomplete-acceptance.json).

The earlier ZIP-in-guest/shared-output attempt produced only a started marker and
was stopped after 1,948 seconds without an executable or completion report. It
did not prove an application crash. The later folder-based, guest-local-data
case passed. Those changed variables do not establish the earlier failure's
unique cause; the original scenario is not retrospectively declared successful.

The earlier Windows PowerShell 5.1 builder quoting failure (`NameError: win32`)
was subsequently fixed with a one-line quote change. A complete default PS5.1
build passed, as did its source and frozen self-tests; the same probe also passed
under PowerShell 7.6.5. Application sources were unchanged. See the
[PS5.1 repair acceptance](D:/1/HyperBatteryHealthCalc-main/docs/ps51-build-acceptance-20260908.md)
for the reviewed hash and execution evidence. Existing portable users do not need
to replace their program solely for this build-script repair.

Remaining: actual Windows 10 x64 execution, a physical USB run and special
managed/shared-filesystem policies. The Fast-mode UI request was interrupted by
the user's Escape action; Fast was neither confirmed nor switched by the agent.
No further native UI operation is authorized by this report.

The EduBrain service package remains the separately verified
[20260907-141124-4a1515 candidate](D:/1/ocsjs-ai-answer-service/dist/EduBrain-Windows-x64-20260907-141124-4a1515/EduBrain-Windows-x64.zip),
SHA256 `5FA373BAF7C54AC2CA1E76EBE783FB7DFDD3D2819EB77FB97C176F5243D70107`.
This battery feature did not change the service source or its release.
