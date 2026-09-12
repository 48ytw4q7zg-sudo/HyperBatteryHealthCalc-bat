"""End-to-end smoke test for battery parsing on real bugreport samples."""

from __future__ import annotations

import argparse
import json
import math
import sys
import traceback
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from battery_core import BatteryExtractor
from report_io import write_text_atomic


_DEFAULT_SAMPLE_NAME = "bugreport-2026-06-23-100941.zip"
_SCRIPT_DIR = Path(__file__).resolve().parent
_SCRIPT_VERSION = "2.2.1"
_SCHEMA_VERSION = "battery-smoke/v1"


def _default_sample_path() -> Path:
    candidates = [
        _SCRIPT_DIR / "input" / _DEFAULT_SAMPLE_NAME,
        Path.cwd() / "input" / _DEFAULT_SAMPLE_NAME,
    ]
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_file():
            return resolved
    return candidates[0].resolve()


def _safe_output_path(raw_output: str) -> Path:
    output = Path(raw_output).expanduser()
    if not output.is_absolute():
        output = _SCRIPT_DIR / output
    return output


def _resolve_sample(path: str) -> Path:
    return Path(path).expanduser().resolve()


def _resolve_samples(cli_samples: Optional[List[str]]) -> List[Path]:
    samples: List[Path] = []
    if cli_samples:
        samples.extend(_resolve_sample(item) for item in cli_samples)
    else:
        default_sample = _default_sample_path()
        if default_sample.is_file():
            samples.append(default_sample)
        else:
            samples.extend(sorted((_SCRIPT_DIR / "input").glob("*.zip")))

    seen = set()
    resolved: List[Path] = []
    for sample in samples:
        path = sample.resolve()
        if path in seen:
            continue
        seen.add(path)
        resolved.append(path)
    return resolved


def _positive_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value > 0
    )


def _ratio_reasonable(value: Any) -> bool:
    return _positive_number(value) and value <= 1000


def _append_issue(checks: List[str], sample_name: str, issue: str) -> None:
    checks.append(f"{sample_name}: {issue}")


def _write_report(output: Path, report: Dict[str, Any], checks: List[str]) -> bool:
    try:
        report["checks_count"] = len(checks)
        report["checks"] = checks
        payload = json.dumps(report, ensure_ascii=True, indent=2) + "\n"
        write_text_atomic(output, payload, encoding="utf-8", newline="\n")
        return True
    except OSError as exc:
        report["ok"] = False
        report["error"] = "output_write_failed"
        report["error_detail"] = str(exc)
        report["exit_code"] = 1
        report["failure_reasons"] = sorted(set(report.get("failure_reasons", [])) | {"output_write_failed"})
        checks.append("output_write_failed")
        report["checks"] = checks
        report["checks_count"] = len(checks)
        print(f"battery_smoke: output write failed: {exc}", file=sys.stderr)
        return False


def run_battery_smoke(
    samples: List[Path],
    output: Path,
    min_diagnostics: int = 1,
    fail_fast: bool = False,
    print_json: bool = False,
) -> int:
    checks: List[str] = []
    report: Dict[str, Any] = {
        "script": "battery_smoke.py",
        "schema_version": _SCHEMA_VERSION,
        "version": _SCRIPT_VERSION,
        "ok": False,
        "samples": {},
        "checks": [],
        "failure_reasons": [],
        "sample_order": [],
        "fail_fast": fail_fast,
        "min_diagnostics": min_diagnostics,
    }

    extractor = BatteryExtractor()
    start_time = time.perf_counter()
    sample_count = len(samples)

    destination_error: Optional[str] = None
    try:
        output = Path(output).expanduser().resolve()
        samples = [Path(sample).expanduser().resolve() for sample in samples]
        if any(
            output == sample
            or (output.exists() and sample.exists() and output.samefile(sample))
            for sample in samples
        ):
            destination_error = "output_matches_input"
        elif output.is_dir():
            destination_error = "output_is_directory"
        elif output.suffix.lower() != ".json":
            destination_error = "output_not_json"
    except (OSError, RuntimeError, ValueError) as exc:
        destination_error = "output_path_invalid"
        report["error_detail"] = str(exc)

    if destination_error is not None:
        report["error"] = destination_error
        report["failure_reasons"] = [destination_error]
        checks.append(destination_error)
        report["checks"] = checks
        report["checks_count"] = len(checks)
        report["exit_code"] = 1
        report["output"] = str(output)
        # Invalid destinations must never receive even an error report.
        if print_json:
            print(json.dumps(report, ensure_ascii=True, indent=2))
        else:
            print(f"battery_smoke: invalid output: {destination_error}", file=sys.stderr)
        return 1

    if not samples:
        report["error"] = "no_bugreport_samples"
        report["failure_reasons"] = ["no_bugreport_samples"]
        checks.append("no_bugreport_samples")
        report["exit_code"] = 1
        if not _write_report(output, report, checks):
            if print_json:
                print(json.dumps(report, ensure_ascii=True, indent=2))
            return 1
        if print_json:
            print(json.dumps(report, ensure_ascii=True, indent=2))
        return 1

    all_ok = True
    for sample in samples:
        sample_key = str(sample)
        sample_name = sample.name
        report["sample_order"].append(sample_key)
        info: Dict[str, Any] = {}
        report["samples"][sample_key] = info
        sample_started = time.perf_counter()
        sample_issues: List[str] = []

        if not sample.is_file():
            issue = "sample_not_found"
            info["status"] = "fail"
            info["error"] = issue
            sample_issues.append(issue)
            info["issues"] = sample_issues
            info["duration_ms"] = round((time.perf_counter() - sample_started) * 1000, 2)
            for item in sample_issues:
                _append_issue(checks, sample_name, item)
            all_ok = False
            if fail_fast:
                break
            continue

        try:
            parsed = extractor.extract(sample)
        except Exception as exc:
            issue = "parse_failed"
            info["status"] = "fail"
            info["error"] = issue
            sample_issues.append(issue)
            info["issues"] = sample_issues
            info["duration_ms"] = round((time.perf_counter() - sample_started) * 1000, 2)
            info["exception_type"] = type(exc).__name__
            info["exception_message"] = str(exc)
            stack_tail = traceback.format_exc().splitlines()[-8:]
            info["trace_tail"] = [line for line in stack_tail if line.strip()]
            for item in sample_issues:
                _append_issue(checks, sample_name, item)
            all_ok = False
            if fail_fast:
                break
            continue

        info["status"] = "ok"
        info["duration_ms"] = round((time.perf_counter() - sample_started) * 1000, 2)
        info["design_capacity"] = parsed.design_capacity
        info["design_capacity_source"] = parsed.design_capacity_source
        info["design_capacity_is_valid"] = parsed.has_design_capacity
        info["current_capacity"] = parsed.current_capacity
        info["current_capacity_source"] = parsed.current_capacity_source
        info["health_percentage"] = parsed.health_percentage
        info["diagnostics_count"] = len(parsed.usage_diagnostics)
        info["diagnostics_preview"] = list(parsed.usage_diagnostics)[:3]
        info["parse_warnings_count"] = len(parsed.parse_warnings)
        info["parse_warnings_preview"] = parsed.parse_warnings[:3]
        info["source"] = str(sample)

        if not parsed.has_design_capacity:
            sample_issues.append("design_capacity_invalid_or_missing")
        if not _positive_number(parsed.current_capacity):
            sample_issues.append("current_capacity_invalid_or_missing")
        if not _ratio_reasonable(parsed.health_percentage):
            sample_issues.append("health_percentage_out_of_range")
        if len(parsed.usage_diagnostics) < max(min_diagnostics, 0):
            sample_issues.append("diagnostics_missing")
        if not parsed.design_capacity_source:
            sample_issues.append("design_capacity_source_missing")
        if not parsed.current_capacity_source:
            sample_issues.append("current_capacity_source_missing")

        if sample_issues:
            info["issues"] = sample_issues
            info["error"] = sample_issues[0]
            info["status"] = "fail"
            all_ok = False
            for item in sample_issues:
                _append_issue(checks, sample_name, item)
        else:
            info["status"] = "ok"
            _append_issue(checks, sample_name, "parsed")

        if not all_ok and fail_fast:
            break

    total_entries = len(report["samples"])
    failed_count = sum(1 for sample in report["samples"].values() if sample.get("status") == "fail")
    success_count = total_entries - failed_count
    failure_reasons = set()
    for sample in report["samples"].values():
        issues = sample.get("issues")
        if isinstance(issues, list):
            for issue in issues:
                if isinstance(issue, str):
                    failure_reasons.add(issue)

    report["elapsed_ms"] = round((time.perf_counter() - start_time) * 1000, 2)
    report["failure_reasons"] = sorted(failure_reasons)
    report["ok"] = all_ok
    report["sample_count"] = sample_count
    report["total_samples"] = total_entries
    report["failed_samples"] = failed_count
    report["ok_samples"] = success_count
    report["failure_rate"] = 0 if total_entries == 0 else round((failed_count * 100) / total_entries, 2)
    report["output"] = str(output)
    report["exit_code"] = 1 if not all_ok else 0

    if not _write_report(output, report, checks):
        report["ok"] = False
        report["error"] = "output_write_failed"
        report["exit_code"] = 1
    if print_json:
        print(json.dumps(report, ensure_ascii=True, indent=2))

    return 0 if report["exit_code"] == 0 else 1


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke test battery extractor with real bugreport input")
    parser.add_argument("--zip", action="append", help="Path to a bugreport zip file (repeatable)")
    parser.add_argument(
        "--output",
        default=str(_SCRIPT_DIR / "battery_smoke.json"),
        help="Smoke result output path (default: battery_smoke.json under script directory)",
    )
    parser.add_argument("--min-diagnostics", type=int, default=1, help="Minimum required usage_diagnostics count (default: 1)")
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop at the first failed sample and return non-zero",
    )
    parser.add_argument("--print-summary", action="store_true", help="Print final summary to stdout")
    parser.add_argument("--json", action="store_true", help="Print JSON report to stdout")
    args = parser.parse_args(argv)

    if args.min_diagnostics < 0:
        parser.error("--min-diagnostics must be >= 0")

    output = _safe_output_path(args.output)
    code = run_battery_smoke(
        samples=_resolve_samples(args.zip),
        output=output,
        min_diagnostics=args.min_diagnostics,
        fail_fast=args.fail_fast,
        print_json=args.json,
    )

    if args.print_summary and not args.json:
        if code == 0:
            print(f"battery_smoke: OK output={output}")
        else:
            print(f"battery_smoke: FAILED output={output}")

    return code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
