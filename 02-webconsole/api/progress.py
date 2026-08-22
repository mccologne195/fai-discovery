import os
import re
from pathlib import Path

import logs
import storage

HISTORY_LIMIT_ENV = "FAI_DISCOVERY_PROGRESS_HISTORY_LIMIT"
DEFAULT_HISTORY_LIMIT = 5

_LINE_RE = re.compile(r"^\S+ (TASKBEGIN|TASKEND) (\S+)(?: (-?\d+))?$")


def parse_task_log(text):
    tasks = []
    index_by_name = {}
    for line in text.splitlines():
        match = _LINE_RE.match(line.strip())
        if not match:
            continue
        event, task_name, exit_code = match.groups()
        if event == "TASKBEGIN":
            if task_name not in index_by_name:
                index_by_name[task_name] = len(tasks)
                tasks.append({"task": task_name, "status": "running"})
        elif event == "TASKEND":
            if task_name not in index_by_name:
                continue
            status = "ok" if exit_code == "0" else "failed"
            tasks[index_by_name[task_name]]["status"] = status
    return tasks


def read_task_progress(install_dir):
    log_path = Path(install_dir) / "fai-monitor.log"
    try:
        text = log_path.read_text()
    except OSError:
        return None
    return parse_task_log(text)


def history_limit():
    raw = os.environ.get(HISTORY_LIMIT_ENV, "")
    if raw.strip().isdigit():
        return int(raw)
    return DEFAULT_HISTORY_LIMIT


def list_active_installs():
    running = []
    finished = []
    for device in storage.list_history():
        hostname = device["hostname"]
        if not hostname:
            continue
        install_dir = logs.find_latest_install_dir(logs.log_dir(), hostname)
        if install_dir is None:
            continue
        tasks = read_task_progress(install_dir)
        if tasks is None:
            continue

        task_error_path = Path(install_dir) / "task_error"
        try:
            task_error_raw = task_error_path.read_text().strip()
        except OSError:
            task_error_raw = None

        entry = {
            "hostname": hostname,
            "mac": device["mac"],
            "tasks": tasks,
            "run_id": install_dir.name,
        }

        if task_error_raw is None or not task_error_raw.lstrip("-").isdigit():
            entry["overall"] = "running"
            running.append(entry)
        else:
            entry["overall"] = "ok" if task_error_raw == "0" else "failed"
            finished.append(entry)

    finished.sort(key=lambda entry: entry["run_id"], reverse=True)
    return running + finished[: history_limit()]
