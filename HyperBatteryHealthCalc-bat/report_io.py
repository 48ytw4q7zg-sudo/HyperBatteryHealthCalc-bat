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


def _write_text_atomic(
    destination: Path,
    text: str,
    *,
    encoding: str = "utf-8",
    newline: str = "\n",
    add_final_newline: bool = True,
    normalize_for_notepad: bool = False,
) -> Path:
    """Atomically write text content to destination path."""
    if not text.strip():
        raise ValueError("The report is empty")

    target = resolve_app_path(Path(destination))
    target.parent.mkdir(parents=True, exist_ok=True)
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")
    if normalize_for_notepad:
        normalized = normalized.replace("\n", "\r\n")
    if add_final_newline:
        normalized = normalized + newline

    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding=encoding,
            newline=newline,
            prefix=".battery-report-",
            suffix=".tmp",
            dir=target.parent,
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


def write_text_atomic(destination: Path, text: str, *, encoding: str = "utf-8", newline: str = "\n") -> Path:
    """Public helper for generic atomic text writing."""
    return _write_text_atomic(
        destination,
        text,
        encoding=encoding,
        newline=newline,
        add_final_newline=True,
        normalize_for_notepad=False,
    )


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
    return _write_text_atomic(target, text, encoding="utf-8-sig", newline="\r\n", normalize_for_notepad=True, add_final_newline=True)
