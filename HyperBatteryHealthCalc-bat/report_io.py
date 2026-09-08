"""Portable paths and console handling shared by the existing entry points."""

from pathlib import Path
import os
import sys
import tempfile


def application_dir() -> Path:
    # PyInstaller's __file__ lives in _internal, which is not the user data root.
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def resolve_app_path(path: Path) -> Path:
    if getattr(sys, "frozen", False) and not path.is_absolute():
        path = application_dir() / path
    return path.resolve()


def configure_standard_streams() -> None:
    if sys.platform != "win32":
        return
    for stream in (sys.stdout, sys.stderr):
        # Windowed executables have None streams; test/host streams may lack
        # buffer/reconfigure. Reconfiguring also avoids taking buffer ownership.
        if stream is None or not hasattr(stream, "reconfigure"):
            continue
        encoding = stream.encoding if stream.isatty() else "utf-8"
        stream.reconfigure(encoding=encoding or "utf-8", errors="replace")


def save_text_report(destination: Path, text: str, source: Path) -> Path:
    """Atomically save a Notepad-compatible report without replacing its input."""
    if not text.strip():
        raise ValueError("The report is empty")
    target = resolve_app_path(Path(destination))
    source = Path(source).resolve()
    if target == source or (target.exists() and source.exists() and target.samefile(source)):
        raise ValueError("The report cannot replace its diagnostic ZIP")
    if target.suffix.lower() != ".txt":
        raise ValueError("Choose a .txt report filename")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n") + "\n"
    temporary = None
    try:
        # Keep the temporary on the same filesystem. The existing report stays
        # intact until the entire replacement has been flushed successfully.
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8-sig", newline="\r\n",
            prefix=".battery-report-", suffix=".tmp", dir=target.parent,
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(normalized)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        return target
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
