> 2026-09-08 验收范围更新：用户明确允许省略 Windows 10 实机测试。目标平台仍为 Windows 10/11 x64；Windows 10 实机结果为“未验证，用户已豁免”，不再作为交付阻塞项。下文历史记录中“Windows 10 待验收/待提供环境”等表述仅反映当时状态，以本条更新为准。Windows 11 的已有运行证据不变；本更新不扩大为 Windows 7/8.1、32 位或原生 ARM64 支持，也不声称完成了实体 U 盘实测。

# Windows PowerShell 5.1 build repair acceptance

Date: 2026-09-08, Asia/Singapore. The user explicitly approved this build-only
repair. No application, model/provider, credential or host security setting was
changed.

## Result

PASS for the approved quoting repair and complete stock Windows PowerShell 5.1
build. The changed probe also passed under PowerShell 7.6.5. Independent Codex
GPT-6 Astra/max review passed with no scoped P0/P1/P2 finding.

The change is at [build_windows.ps1:37](D:/1/HyperBatteryHealthCalc-main/build_windows.ps1:37):

```powershell
Invoke-Checked $Python @('-c', "import struct,sys,tkinter; assert sys.platform == 'win32' and struct.calcsize('P') == 8; print(sys.version)")
```

Python string literals now use single quotes inside the PowerShell double-quoted
argument, so legacy native argument passing preserves them. The Windows check,
64-bit pointer check and Tk import are retained. There are no character-code
workarounds or weakened checks.

Reviewed script SHA256:
`82C63274B6F164AA5E01DC9A4354393273AA411429315E9B206A159F88E47D83`.
This exact value also matches the completed build's source manifest.

## Verification

| Check | Result |
| --- | --- |
| Prior PS5.1 reproduction | Failed with `NameError: win32`; original literal quotes were lost |
| Patched PS5.1 default build | Exit 0, no Python-path override |
| Existing isolated regression suite | 35 passed, two private real-archive cases skipped in the isolated build |
| Browser logic | 44 assertions passed |
| Source windowed self-test | 19 checks passed |
| Frozen GUI self-test | 20 checks passed, including report save and input protection |
| Frozen CLI self-test | 20 checks passed, including report save and input protection |
| PS7 exact repaired probe | Passed on PowerShell 7.6.5; no second full PS7 build claimed |
| Application/source-test preservation | GUI, report I/O, portable entry and export test hashes unchanged |
| Independent review | PASS, CLI exit 0, exact script hash matched |

The earlier two real-archive tests remain separately passed against the
user-authorized phone ZIP; they were not rerun or copied into this build.

## Execution lanes

Claude Code was explicitly invoked with `gpt-5.6-sol`, effort `max`, and made the
single-file mechanical edit. It returned success/exit 0. The Codex owner ran the
full build; a separate `gpt-6-astra` / `max` invocation performed read-only review.

Review session: `01a07cc7-cbbc-7e52-ba80-a48a724eca36`.
Review report SHA256:
`2662BEC006839E99D529E24A76438DECA1590629B11B02EFB01999A94542C30F`.
Requested/configured model identity is recorded, not invisible backend or
billing identity. No desktop interaction or Fast-mode switch was performed.

## Build validation artifact

[PS5.1-built ZIP](D:/1/HyperBatteryHealthCalc-main/dist/HyperBatteryHealthCalc-Windows-x64-20260907-164957-a00d0d/HyperBatteryHealthCalc-Windows-x64.zip):
15,373,258 bytes; 997 payload files totaling 31,811,180 bytes.

- ZIP SHA256: `40A474E80EB2A9DC16A51D3EEB99D6E643422F5CCB65E3AAB7C056A9F7A06ACC`.
- GUI SHA256: `98209453171C74A3CE3EB65745C80D9FA0D1B83D91AA7DEF9139F26A01C79C7F`.
- CLI SHA256: `19181CD3E459E223A64373826C9E94794CA0EC5D8B5BD3CDE9C2BB0514120C7E`.

This is a build-validation output. The application source is unchanged, but the
binary hashes differ from the earlier release. Its fresh local frozen self-tests
passed; the earlier native-dialog and clean-Sandbox observations are not relabeled
as fresh runs of these new hashes. The existing user delivery remains available,
and this script-only repair does not require portable users to download again.

## Evidence

- [Edit receipt](D:/1/HyperBatteryHealthCalc-main/.build/ps51-quoting-repair-20260908/claude-sol-edit-receipt.json).
- [Full build receipt](D:/1/HyperBatteryHealthCalc-main/.build/ps51-quoting-repair-20260908/build-receipt.json).
- [Runtime acceptance](D:/1/HyperBatteryHealthCalc-main/.build/ps51-quoting-repair-20260908/acceptance.json).
- [Independent review](D:/1/HyperBatteryHealthCalc-main/.build/ps51-quoting-repair-20260908/gpt6-independent-review.txt).
- [Build result](D:/1/HyperBatteryHealthCalc-main/.build/windows-20260907-164957-a00d0d/evidence/build-result.json), SHA256 `E1A7291F2497C32B6C61514F7CEB585956F43E64D6BDD59BA9732913D2D622CE`.

Windows 10 actual execution and physical USB testing remain unverified. Passing
PowerShell 5.1 on Windows 11 is not Windows 10 runtime acceptance. This scoped
repair does not mark the full two-project goal complete.
