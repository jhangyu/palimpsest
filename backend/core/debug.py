# backend/core/debug.py
from pathlib import Path
from datetime import datetime
from hashlib import md5
import os


class DebugWriter:
    def __init__(self, operation: str, site_name: str = "unknown"):
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H%M%S")
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in site_name)
        dir_name = f"{operation}_{safe_name}_{time_str}"
        default_log_dir = Path(__file__).resolve().parents[2] / "log"
        log_dir = Path(os.getenv("PALIMPSEST_LOG_DIR", default_log_dir))
        self._debug_dir = log_dir / "debug" / date_str / dir_name
        self._debug_dir.mkdir(parents=True, exist_ok=True)

    def save(self, stage: str, filename: str, content: str):
        file_path = self._debug_dir / f"{stage}_{filename}"
        file_path.write_text(content, encoding="utf-8")
        print(f"[Debug] Saved: {file_path}")

    @property
    def debug_dir(self) -> str:
        return str(self._debug_dir)


class NullDebugWriter:
    def save(self, stage: str, filename: str, content: str):
        pass

    @property
    def debug_dir(self) -> None:
        return None


def create_debug_writer(debug: bool, operation: str, site_name: str = "unknown"):
    if debug:
        return DebugWriter(operation, site_name)
    return NullDebugWriter()


def url_hash(url: str) -> str:
    return md5(url.encode()).hexdigest()[:8]
