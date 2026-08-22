import os
import re
from collections import deque
from pathlib import Path

import logs
import storage

HISTORY_LIMIT_ENV = "FAI_DISCOVERY_PROGRESS_HISTORY_LIMIT"
DEFAULT_HISTORY_LIMIT = 5

MONITOR_LOG_ENV = "FAI_DISCOVERY_MONITOR_LOG_PATH"
DEFAULT_MONITOR_LOG_PATH = "/var/log/fai/fai-monitor.log"
MONITOR_LOG_TAIL_LINES = 5000

# Hostname-Praefix ist optional: das globale fai-monitor.log hat "<host>
# TASKBEGIN x", die per-Host-Kopien in remote-logs/<host>/install-*/ haben
# dagegen kein Praefix mehr ("TASKBEGIN x") - der Host steht dort schon im
# Verzeichnisnamen.
_LINE_RE = re.compile(r"^(?:\S+ )?(TASKBEGIN|TASKEND) (\S+)(?: (-?\d+))?$")


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


def _mark_unclosed_as_implicit(tasks):
    # Manche FAI-Tasks (z.B. "action", das nur "install" umschliesst)
    # bekommen nie ein eigenes TASKEND - nur ihr Kind-Task wird
    # abgeschlossen. Auf einem bereits fertigen Lauf (overall ok/failed)
    # ist so ein Task damit implizit erledigt, auch ohne eigenes
    # TASKEND. Nur fuer abgeschlossene Laeufe aufrufen, nicht fuer
    # echte laufende Installationen - dort bedeutet "running" tatsaechlich
    # noch aktiv.
    for entry in tasks:
        if entry["status"] == "running":
            entry["status"] = "implicit"
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


def monitor_log_path():
    return os.environ.get(MONITOR_LOG_ENV, DEFAULT_MONITOR_LOG_PATH)


def _read_monitor_log_tail(path):
    # Das globale fai-monitor.log ist append-only ueber die Lebenszeit des
    # Servers und kann ueber Monate/Jahre gross werden. Fuer "letzter Lauf
    # pro Host" reichen die letzten paar tausend Zeilen bei weitem, ein
    # deque(maxlen=...) vermeidet das Einlesen der kompletten Datei.
    try:
        with open(path, "r") as f:
            return list(deque(f, maxlen=MONITOR_LOG_TAIL_LINES))
    except OSError:
        return []


def _sendid_lines(lines, sendid):
    # "sendid" ist die Kennung, die FAI den Monitor-Meldungen voranstellt
    # (chain=forward FAI_SENDID, siehe fai-discovery-chboot: "FAI_SENDID=mac").
    # Bewusst nicht mehr der Hostname: FAI fixiert $HOSTNAME bereits im
    # allerersten Task (confdir), lange bevor 02-set-hostname.sh den von der
    # Webkonsole zugewiesenen Hostnamen setzt - jede Installation waere sonst
    # fuer den gesamten Lauf unter ihrem alten DHCP-Hostnamen sichtbar (oder
    # gar nicht, weil die Webkonsole nur den neuen Hostnamen kennt). Die MAC
    # ist dagegen von Anfang an bekannt und aendert sich nie.
    prefix = sendid + " "
    return [line for line in lines if line.startswith(prefix)]


def _last_run_lines(host_lines, sendid):
    # Das globale Log enthaelt alle historischen Laeufe hintereinander.
    # "TASKBEGIN setup" ist der allererste Task jedes FAI-Laufs (siehe
    # Task-Reihenfolge in ARCHITEKTUR.md/Beobachtung) - ab der letzten
    # solchen Zeile beginnt der aktuellste Lauf.
    start_marker = sendid + " TASKBEGIN setup"
    last_start = None
    for i, line in enumerate(host_lines):
        if line.strip() == start_marker:
            last_start = i
    if last_start is None:
        return None
    return host_lines[last_start:]


def _run_finished(run_lines, sendid):
    # "reboot" ist der letzte Task in der FAI-Sequenz (nach savelog/faiend).
    # Solange TASKEND dafuer nicht aufgetaucht ist, laeuft die Installation
    # noch - unabhaengig davon, ob remote-logs/ (erst von savelog befuellt,
    # also spaet im Lauf) schon etwas Aktuelles enthaelt.
    prefix = sendid + " TASKEND reboot "
    return any(line.strip().startswith(prefix) for line in run_lines)


def _live_progress_from_monitor_log(monitor_lines, sendid):
    host_lines = _sendid_lines(monitor_lines, sendid)
    run_lines = _last_run_lines(host_lines, sendid)
    if run_lines is None or _run_finished(run_lines, sendid):
        return None
    return parse_task_log("".join(run_lines))


def _finished_progress_from_monitor_log(monitor_lines, sendid):
    # Gegenstueck zu _live_progress_from_monitor_log: liefert die
    # vollstaendige Task-Liste eines bereits abgeschlossenen Laufs. Noetig,
    # weil die remote-logs/-Kopie der Logdatei vom savelog-Task selbst
    # erzeugt wird und daher ihre eigene TASKEND-Zeile (und alles danach:
    # faiend, reboot) strukturell nie enthalten kann - das globale Log hat
    # dagegen die vollstaendigen Daten, sofern der Lauf noch im
    # MONITOR_LOG_TAIL_LINES-Fenster liegt.
    host_lines = _sendid_lines(monitor_lines, sendid)
    run_lines = _last_run_lines(host_lines, sendid)
    if run_lines is None or not _run_finished(run_lines, sendid):
        return None
    return parse_task_log("".join(run_lines))


def list_active_installs():
    running = []
    finished = []
    monitor_lines = _read_monitor_log_tail(monitor_log_path())

    for device in storage.list_history():
        hostname = device["hostname"]
        mac = device["mac"]
        if not hostname:
            continue

        live_tasks = _live_progress_from_monitor_log(monitor_lines, mac)
        if live_tasks is not None:
            running.append(
                {
                    "hostname": hostname,
                    "mac": device["mac"],
                    "tasks": live_tasks,
                    "run_id": "live",
                    "overall": "running",
                }
            )
            continue

        # Kein offener Lauf im globalen Log gefunden (entweder noch nie
        # installiert, oder der letzte Lauf ist bereits mit TASKEND reboot
        # abgeschlossen) - abgeschlossene Laeufe kommen weiterhin aus
        # remote-logs/, wo savelog den finalen Stand inkl. task_error
        # ablegt.
        install_dir = logs.find_latest_install_dir(logs.log_dir(), hostname)
        if install_dir is None:
            continue
        tasks = _finished_progress_from_monitor_log(monitor_lines, mac)
        if tasks is None:
            # Fallback: Lauf ist nicht (mehr) im Fenster des globalen Logs
            # zu finden (aeltere Installation) - dann lieber die
            # unvollstaendige remote-logs/-Liste zeigen als gar keine.
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
            entry["tasks"] = _mark_unclosed_as_implicit(entry["tasks"])
            finished.append(entry)

    finished.sort(key=lambda entry: entry["run_id"], reverse=True)
    return running + finished[: history_limit()]
