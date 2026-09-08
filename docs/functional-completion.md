# Functional completion

Goal: close the existing battery analysis workflows across both web pages, the Python core, CLI and GUI, with consistent capacity semantics and recoverable partial reports.

## Implementation and ownership

| Area | Files | Owner | Verification |
| --- | --- | --- | --- |
| Capacity and archive semantics | `HyperBatteryHealthCalc-bat/battery_core.py` | Codex | `test_battery_core.py`, `test_functional_completion.py` |
| Web parsing, manual overrides, resource cleanup and stale results | Both `index.html` files | Codex | `test_web_logic.cjs`, local browser file selection |
| Desktop and command-line recovery | `battery_gui.py`, `battery_calc.py` | Codex | Targeted controller and CLI tests |
| Independent review | Existing analysis workflows | Claude Code | Concrete findings and follow-up verification |

The initial Claude Code audit completed before the requested model-route change. A later external `codex exec` review completed with `model: gpt-6-astra` and `reasoning effort: max` in its invocation metadata. It reproduced corrupt-entry recovery, stale manual retries, invalid capacity merging, partial-report omission and CLI exit-status defects. Regression tests now cover those cases. This records the requested execution configuration, not a claim about an unverifiable provider-internal model identity.

## Invariants

- Current capacity must be positive and finite. Prefer valid minimum learned capacity; otherwise use positive charge counter only at 95 percent or higher on the reported scale.
- Design capacity must be positive and finite. Current learned capacity is not an original design-capacity source.
- A manually supplied design capacity overrides automatic data in the interactive UI. CLI `--capacity` retains its documented default-for-missing-data meaning.
- Recoverable archive errors must not discard other readable entries. A stale asynchronous request must not publish into a newer selection.
- Report missing values without fabricating a health percentage. Preserve useful snapshot information when health cannot be calculated.

## Risks and acceptance

Real diagnostic files vary across firmware versions. Synthetic archive regressions must be supplemented by the existing real-file regression and actual local-browser operation. The full goal remains open until both projects have review evidence and their relevant user-facing paths have run successfully.

Both pages have been exercised in the local browser with the existing Xiaomi 15 Pro report. Automatic design/current capacities were 6100/4760 mAh (78.03 percent); a manual 6200 mAh design input produced 76.77 percent. Manual recalculation reuses parsed data. GUI controller tests verify worker/main-thread separation and stale-result rejection; native window interaction and close-during-analysis behavior still require a separate check.

CLI exports include partial snapshots, fail with a nonzero exit status when required capacity is absent in noninteractive use, and preserve the previous report if atomic replacement fails. Output may not overwrite an input diagnostic archive.
