"""Smoke test for atomic report I/O helpers.

Focuses on idempotence, encoding policy, newline normalization and source-file
protection without touching any user data.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from report_io import _write_text_atomic, write_text_atomic, save_text_report


def run_report_io_smoke(output: Path) -> int:
    checks = []

    def check(name: str, condition: bool) -> None:
        if not condition:
            raise AssertionError(name)
        checks.append(name)

    report = {"ok": False, "checks": checks, "tmp_glob": []}
    try:
        with tempfile.TemporaryDirectory(prefix="hb-report-io-smoke-") as directory:
            workspace = Path(directory).resolve()

            target = workspace / "report.txt"
            write_text_atomic(target, "a\nb", encoding="utf-8", newline="\n")
            content = target.read_text(encoding="utf-8")
            check("atomic_write_created", target.is_file())
            check("atomic_write_final_newline", content.endswith("\n"))
            check("atomic_write_line_norm", content == "a\nb\n")

            # Internal atomic helper should keep the destination path and remove temp
            # artifacts even after replacement succeeds.
            nested = workspace / "nested" / "out" / "safe.txt"
            _write_text_atomic(nested, "x")
            check("internal_atomic_single_file", nested.is_file())
            check("internal_atomic_nested_parent_created", nested.parent.is_dir())
            check("internal_atomic_tmp_cleaned", len(list(workspace.glob(".battery-report-*.tmp"))) == 0)

            archive = workspace / "input.zip"
            archive.write_bytes(b"zip-bytes")
            destination = workspace / "output.txt"
            saved = save_text_report(destination, "notepad-ready", source=archive)
            payload = destination.read_bytes()
            check("save_text_report_destination", saved == destination)
            check("save_text_report_utf8_bom", payload.startswith(b"\xef\xbb\xbf"))
            check("save_text_report_notepad_newline", b"\r\n" in payload)

            protected = False
            try:
                save_text_report(destination, "blocked", source=destination)
            except ValueError:
                protected = True
            check("save_text_report_reject_self", protected)

            wrong_suffix = workspace / "not_txt.bin"
            wrong_suffix_rejected = False
            try:
                save_text_report(wrong_suffix, "wrong-ext", source=archive)
            except ValueError:
                wrong_suffix_rejected = True
            check("save_text_report_suffix_guard", wrong_suffix_rejected)

            report["checks"] = checks
            report["tmp_files_after"] = [path.name for path in workspace.glob(".battery-report-*.tmp")]
            report["ok"] = True
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        return 0
    except Exception as exc:
        report["ok"] = False
        report["error_type"] = type(exc).__name__
        report["error"] = str(exc)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 1


def main(argv: list[str] | None = None) -> int:
    output = Path("report_io_smoke.json")
    if argv is not None and len(argv) > 0:
        output = Path(argv[0])
    return run_report_io_smoke(output)


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv[1:]))
