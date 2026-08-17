import os
from pathlib import Path

LOG_DIR_ENV = "FAI_DISCOVERY_LOG_DIR"
DEFAULT_LOG_DIR = "/var/log/fai/remote-logs"


def log_dir():
    return os.environ.get(LOG_DIR_ENV, DEFAULT_LOG_DIR)


def find_latest_install_dir(base_dir, hostname):
    host_dir = Path(base_dir) / hostname
    if not host_dir.is_dir():
        return None

    install_dirs = sorted(
        (entry for entry in host_dir.iterdir() if entry.is_dir() and entry.name.startswith("install-")),
        key=lambda entry: entry.name,
    )
    return install_dirs[-1] if install_dirs else None


def _read_text(path):
    try:
        return path.read_text()
    except OSError:
        return None


def read_install_log(install_dir):
    install_dir = Path(install_dir)

    task_error_raw = _read_text(install_dir / "task_error")
    task_error = int(task_error_raw.strip()) if task_error_raw and task_error_raw.strip().isdigit() else None

    status = _read_text(install_dir / "status.log")

    error = _read_text(install_dir / "error.log")
    if error is not None and error.strip() == "":
        error = None

    ok = None if task_error is None else task_error == 0

    return {
        "task_error": task_error,
        "ok": ok,
        "status": status,
        "error": error,
    }
