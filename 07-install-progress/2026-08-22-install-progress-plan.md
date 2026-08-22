# Live-Installationsfortschritt Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eine neue Seite `/admin/progress` in der bestehenden Flask-Webkonsole zeigt den Task-für-Task-Fortschritt laufender FAI-Installationen live an und ersetzt damit die manuelle `fai-monitor-gui`-Session per SSH-X11-Forwarding.

**Architecture:** Neues, zustandsloses Modul `progress.py` liest bei jedem Request die pro-Host-Kopie von `fai-monitor.log` aus `/var/log/fai/remote-logs/<hostname>/install-<timestamp>/` (wiederverwendet `logs.find_latest_install_dir()`), parst Task-Ereignisse zeilenweise und liefert eine geordnete Task-Liste pro Host. Eine neue `@require_auth`-Route in `admin.py` rendert das Ergebnis serverseitig; das Frontend pollt dieselbe URL im bestehenden `dashboard.html`-Muster (`fetch` + `DOMParser`, kein neuer JSON-Endpoint, kein Websocket).

**Tech Stack:** Python 3.13 + Flask (wie der Rest von `02-webconsole/`), `pytest` (venv unter `/Users/Thomas/Repo/fai-discovery/venv`), Jinja2, kein neues Paket.

**Spec:** `07-install-progress/2026-08-22-install-progress-design.md`

## Global Constraints

- Kein neuer Hintergrund-Thread, kein persistenter In-Memory-State, keine neue JSON-API — jede Anfrage liest die Log-Dateien frisch (siehe Design-Doc, Abschnitt "Architektur").
- Task-Spalten ergeben sich dynamisch aus beobachteten `TASKBEGIN`-Zeilen, kein hartcodierter Task-Katalog.
- Gesamtstatus eines Hosts kommt ausschließlich aus der `task_error`-Datei (wie in `logs.py:read_install_log()`), nicht aus Task-Namen geraten.
- Anzahl abgeschlossener Installationen in der Übersicht: Default `5`, überschreibbar per Env-Var `FAI_DISCOVERY_PROGRESS_HISTORY_LIMIT`.
- Laufende Installationen werden immer angezeigt, unabhängig vom Limit.
- Fehlerbehandlung defensiv: fehlende/unlesbare Log-Datei oder kaputte Zeile darf die restliche Seite nicht zum Absturz bringen (Zeile/Host überspringen).
- Bestehende CSS-Variablen (`--accent`, `--danger`) und Klassenmuster (`log-status-ok`/`log-status-failed`) wiederverwenden, keine neuen hartcodierten Farben.
- Referenz-Spec: `2026-08-22-install-progress-design.md` (dieser Ordner).

---

### Task 1: Parser- und Auswahl-Logik (`progress.py`)

**Files:**
- Create: `02-webconsole/api/progress.py`
- Test: `02-webconsole/api/test_progress.py`
- Referenz (nur lesen, nicht ändern): `02-webconsole/api/logs.py` (liefert `find_latest_install_dir(base_dir, hostname)`, `log_dir()`)

**Interfaces:**
- Produziert: `parse_task_log(text: str) -> list[dict]` — reine Parsing-Funktion, nimmt den Dateiinhalt als String, gibt `[{"task": str, "status": "running"|"ok"|"failed"}]` in Auftrittsreihenfolge zurück.
- Produziert: `read_task_progress(install_dir: Path) -> list[dict]` — liest `install_dir / "fai-monitor.log"`, liefert `None` falls die Datei fehlt/unlesbar ist, sonst das Ergebnis von `parse_task_log`.
- Produziert: `history_limit() -> int` — liest `FAI_DISCOVERY_PROGRESS_HISTORY_LIMIT` aus der Umgebung, Default `5`.
- Produziert: `list_active_installs() -> list[dict]` — `[{"hostname": str, "mac": str, "tasks": list[dict], "overall": "running"|"ok"|"failed"}]`. Nutzt `storage.list_history()` und `logs.find_latest_install_dir(logs.log_dir(), hostname)`.

- [ ] **Step 1: Test für `parse_task_log` schreiben**

```python
# 02-webconsole/api/test_progress.py
import progress


REAL_LOG_EXCERPT = """\
vmrepro TASKBEGIN setup
vmrepro TASKEND setup 0
vmrepro TASKBEGIN defclass
vmrepro TASKEND defclass 0
vmrepro TASKBEGIN action
vmrepro TASKBEGIN install
vmrepro TASKBEGIN partition
vmrepro TASKEND partition 0
vmrepro HOOK updatebase.DEBIAN
vmrepro TASKBEGIN updatebase
vmrepro TASKEND updatebase 0
vmrepro TASKBEGIN configure
vmrepro TASKEND configure 1
vmrepro TASKBEGIN tests
"""


def test_parse_task_log_orders_tasks_by_first_appearance():
    tasks = progress.parse_task_log(REAL_LOG_EXCERPT)
    names = [t["task"] for t in tasks]
    assert names == [
        "setup",
        "defclass",
        "action",
        "install",
        "partition",
        "updatebase",
        "configure",
        "tests",
    ]


def test_parse_task_log_marks_completed_tasks_ok():
    tasks = progress.parse_task_log(REAL_LOG_EXCERPT)
    by_name = {t["task"]: t["status"] for t in tasks}
    assert by_name["setup"] == "ok"
    assert by_name["partition"] == "ok"
    assert by_name["updatebase"] == "ok"


def test_parse_task_log_marks_nonzero_exit_as_failed():
    tasks = progress.parse_task_log(REAL_LOG_EXCERPT)
    by_name = {t["task"]: t["status"] for t in tasks}
    assert by_name["configure"] == "failed"


def test_parse_task_log_marks_open_tasks_running():
    tasks = progress.parse_task_log(REAL_LOG_EXCERPT)
    by_name = {t["task"]: t["status"] for t in tasks}
    assert by_name["action"] == "running"
    assert by_name["install"] == "running"
    assert by_name["tests"] == "running"


def test_parse_task_log_ignores_hook_lines():
    tasks = progress.parse_task_log(REAL_LOG_EXCERPT)
    names = [t["task"] for t in tasks]
    assert "updatebase.DEBIAN" not in names


def test_parse_task_log_ignores_malformed_lines():
    text = "vmrepro TASKBEGIN setup\nnot a valid line\nvmrepro TASKEND setup 0\n"
    tasks = progress.parse_task_log(text)
    assert [t["task"] for t in tasks] == ["setup"]
    assert tasks[0]["status"] == "ok"


def test_parse_task_log_empty_text_returns_empty_list():
    assert progress.parse_task_log("") == []
```

- [ ] **Step 2: Tests ausführen, sicherstellen dass sie fehlschlagen**

Run: `cd 02-webconsole/api && ../../venv/bin/pytest test_progress.py -v`
Expected: FAIL mit `ModuleNotFoundError: No module named 'progress'`

- [ ] **Step 3: `parse_task_log` implementieren**

```python
# 02-webconsole/api/progress.py (Anfang der Datei)
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
```

- [ ] **Step 4: Tests ausführen, sicherstellen dass sie bestehen**

Run: `cd 02-webconsole/api && ../../venv/bin/pytest test_progress.py -v`
Expected: PASS (7 Tests)

- [ ] **Step 5: Commit**

```bash
git add 02-webconsole/api/progress.py 02-webconsole/api/test_progress.py
git commit -m "feat: Task-Log-Parser fuer Live-Installationsfortschritt"
```

- [ ] **Step 6: Test für `read_task_progress` schreiben**

```python
# an test_progress.py anhaengen

def test_read_task_progress_reads_fai_monitor_log(tmp_path):
    install_dir = tmp_path / "install-20260822120000"
    install_dir.mkdir()
    (install_dir / "fai-monitor.log").write_text(REAL_LOG_EXCERPT)

    tasks = progress.read_task_progress(install_dir)

    assert tasks is not None
    assert tasks[0]["task"] == "setup"


def test_read_task_progress_returns_none_if_log_missing(tmp_path):
    install_dir = tmp_path / "install-20260822120000"
    install_dir.mkdir()

    assert progress.read_task_progress(install_dir) is None
```

- [ ] **Step 7: Tests ausführen, sicherstellen dass sie fehlschlagen**

Run: `cd 02-webconsole/api && ../../venv/bin/pytest test_progress.py -v -k read_task_progress`
Expected: FAIL mit `AttributeError: module 'progress' has no attribute 'read_task_progress'`

- [ ] **Step 8: `read_task_progress` implementieren**

```python
# an progress.py anhaengen

def read_task_progress(install_dir):
    log_path = Path(install_dir) / "fai-monitor.log"
    try:
        text = log_path.read_text()
    except OSError:
        return None
    return parse_task_log(text)
```

- [ ] **Step 9: Tests ausführen, sicherstellen dass sie bestehen**

Run: `cd 02-webconsole/api && ../../venv/bin/pytest test_progress.py -v`
Expected: PASS (9 Tests)

- [ ] **Step 10: Commit**

```bash
git add 02-webconsole/api/progress.py 02-webconsole/api/test_progress.py
git commit -m "feat: fai-monitor.log pro Installationsverzeichnis einlesen"
```

- [ ] **Step 11: Tests für `history_limit` und `list_active_installs` schreiben**

```python
# an test_progress.py anhaengen
from datetime import datetime, timezone

import storage


def _make_install_dir(base_dir, hostname, run_id, log_text, task_error=None):
    install_dir = base_dir / hostname / f"install-{run_id}"
    install_dir.mkdir(parents=True)
    (install_dir / "fai-monitor.log").write_text(log_text)
    if task_error is not None:
        (install_dir / "task_error").write_text(str(task_error))
    return install_dir


def _register_and_approve(mac, hostname):
    storage.register_device(mac, "192.168.10.99", "CPU", "8", "100G")
    storage.approve_device(mac, hostname, "SALT STEP", "thomas")


def test_history_limit_defaults_to_five(monkeypatch):
    monkeypatch.delenv(progress.HISTORY_LIMIT_ENV, raising=False)
    assert progress.history_limit() == 5


def test_history_limit_reads_env_override(monkeypatch):
    monkeypatch.setenv(progress.HISTORY_LIMIT_ENV, "2")
    assert progress.history_limit() == 2


def test_list_active_installs_includes_running_host(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    monkeypatch.setenv("FAI_DISCOVERY_LOG_DIR", str(tmp_path / "remote-logs"))
    storage.init_db()
    _register_and_approve("aa:bb:cc:dd:ee:01", "hostA")
    _make_install_dir(tmp_path / "remote-logs", "hostA", "20260822120000", REAL_LOG_EXCERPT)

    result = progress.list_active_installs()

    assert len(result) == 1
    assert result[0]["hostname"] == "hostA"
    assert result[0]["overall"] == "running"


def test_list_active_installs_marks_finished_ok(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    monkeypatch.setenv("FAI_DISCOVERY_LOG_DIR", str(tmp_path / "remote-logs"))
    storage.init_db()
    _register_and_approve("aa:bb:cc:dd:ee:02", "hostB")
    _make_install_dir(
        tmp_path / "remote-logs", "hostB", "20260822120000", REAL_LOG_EXCERPT, task_error=0
    )

    result = progress.list_active_installs()

    assert result[0]["overall"] == "ok"


def test_list_active_installs_marks_finished_failed(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    monkeypatch.setenv("FAI_DISCOVERY_LOG_DIR", str(tmp_path / "remote-logs"))
    storage.init_db()
    _register_and_approve("aa:bb:cc:dd:ee:03", "hostC")
    _make_install_dir(
        tmp_path / "remote-logs", "hostC", "20260822120000", REAL_LOG_EXCERPT, task_error=1
    )

    result = progress.list_active_installs()

    assert result[0]["overall"] == "failed"


def test_list_active_installs_limits_finished_entries(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    monkeypatch.setenv("FAI_DISCOVERY_LOG_DIR", str(tmp_path / "remote-logs"))
    monkeypatch.setenv(progress.HISTORY_LIMIT_ENV, "2")
    storage.init_db()
    for i in range(4):
        mac = f"aa:bb:cc:dd:ee:{i:02x}"
        hostname = f"host{i}"
        _register_and_approve(mac, hostname)
        _make_install_dir(
            tmp_path / "remote-logs",
            hostname,
            f"2026082212000{i}",
            REAL_LOG_EXCERPT,
            task_error=0,
        )

    result = progress.list_active_installs()

    assert len(result) == 2
    assert [entry["hostname"] for entry in result] == ["host3", "host2"]


def test_list_active_installs_keeps_all_running_regardless_of_limit(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    monkeypatch.setenv("FAI_DISCOVERY_LOG_DIR", str(tmp_path / "remote-logs"))
    monkeypatch.setenv(progress.HISTORY_LIMIT_ENV, "1")
    storage.init_db()
    for i in range(3):
        mac = f"aa:bb:cc:dd:ee:{i:02x}"
        hostname = f"running{i}"
        _register_and_approve(mac, hostname)
        _make_install_dir(
            tmp_path / "remote-logs", hostname, f"2026082212000{i}", REAL_LOG_EXCERPT
        )

    result = progress.list_active_installs()

    assert len(result) == 3
    assert all(entry["overall"] == "running" for entry in result)


def test_list_active_installs_skips_host_without_install_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    monkeypatch.setenv("FAI_DISCOVERY_LOG_DIR", str(tmp_path / "remote-logs"))
    storage.init_db()
    _register_and_approve("aa:bb:cc:dd:ee:04", "hostNoLogs")

    result = progress.list_active_installs()

    assert result == []
```

- [ ] **Step 12: Tests ausführen, sicherstellen dass sie fehlschlagen**

Run: `cd 02-webconsole/api && ../../venv/bin/pytest test_progress.py -v -k "history_limit or list_active_installs"`
Expected: FAIL mit `AttributeError: module 'progress' has no attribute 'history_limit'`

- [ ] **Step 13: `history_limit` und `list_active_installs` implementieren**

```python
# an progress.py anhaengen

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
```

- [ ] **Step 14: Tests ausführen, sicherstellen dass sie bestehen**

Run: `cd 02-webconsole/api && ../../venv/bin/pytest test_progress.py -v`
Expected: PASS (alle Tests in der Datei)

- [ ] **Step 15: Vollständige Testsuite laufen lassen (keine Regression)**

Run: `cd 02-webconsole/api && ../../venv/bin/pytest -v`
Expected: PASS (alle bestehenden + neuen Tests)

- [ ] **Step 16: Commit**

```bash
git add 02-webconsole/api/progress.py 02-webconsole/api/test_progress.py
git commit -m "feat: aktive und letzte Installationen fuer Live-Fortschritt auswaehlen"
```

---

### Task 2: Route, Template, i18n, Navigation

**Files:**
- Modify: `02-webconsole/api/admin.py`
- Modify: `02-webconsole/api/i18n.py`
- Modify: `02-webconsole/api/templates/base.html`
- Create: `02-webconsole/api/templates/progress.html`
- Modify: `02-webconsole/api/static/style.css`
- Test: `02-webconsole/api/test_admin.py`

**Interfaces:**
- Konsumiert: `progress.list_active_installs() -> list[dict]` aus Task 1 (Felder: `hostname`, `mac`, `tasks`, `overall`, `run_id`).
- Produziert: Route `GET /admin/progress` (Blueprint `admin`, Endpoint-Name `admin.progress`).

- [ ] **Step 1: Test für die neue Route schreiben**

```python
# an 02-webconsole/api/test_admin.py anhaengen
import progress


def test_progress_requires_auth(client):
    resp = client.get("/admin/progress")
    assert resp.status_code == 401


def test_progress_shows_empty_state(client, auth_headers, monkeypatch):
    monkeypatch.setattr(progress, "list_active_installs", lambda: [])
    resp = client.get("/admin/progress", headers=auth_headers)
    assert resp.status_code == 200
    assert "hostA" not in resp.get_data(as_text=True)


def test_progress_renders_running_host_with_tasks(client, auth_headers, monkeypatch):
    monkeypatch.setattr(
        progress,
        "list_active_installs",
        lambda: [
            {
                "hostname": "hostA",
                "mac": "aa:bb:cc:dd:ee:ff",
                "overall": "running",
                "run_id": "install-20260822120000",
                "tasks": [
                    {"task": "partition", "status": "ok"},
                    {"task": "extrbase", "status": "running"},
                ],
            }
        ],
    )
    resp = client.get("/admin/progress", headers=auth_headers)
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "hostA" in body
    assert "partition" in body
    assert "extrbase" in body
```

Hinweis: prüfe zuerst mit `grep -n "def client\|def auth_headers" 02-webconsole/api/test_admin.py`, ob diese Fixtures bereits existieren (z. B. in `conftest.py`) und übernimm exakt deren Namen/Signatur statt sie neu zu erfinden — die bestehenden Tests in `test_admin.py` nutzen mit hoher Wahrscheinlichkeit dasselbe Muster.

- [ ] **Step 2: Tests ausführen, sicherstellen dass sie fehlschlagen**

Run: `cd 02-webconsole/api && ../../venv/bin/pytest test_admin.py -v -k progress`
Expected: FAIL mit 404 (Route existiert noch nicht)

- [ ] **Step 3: i18n-Keys ergänzen**

In `02-webconsole/api/i18n.py`, im `TRANSLATIONS`-Dict nach dem `"logs.*"`-Block einfügen:

```python
    "nav.progress": {"de": "Fortschritt", "en": "Progress"},

    "progress.title": {"de": "Installationsfortschritt – fai-discovery", "en": "Installation progress – fai-discovery"},
    "progress.heading": {"de": "Live-Installationsfortschritt", "en": "Live installation progress"},
    "progress.empty": {
        "de": "Aktuell läuft keine Installation, keine kürzlich abgeschlossene vorhanden.",
        "en": "No installation is currently running, and none finished recently.",
    },
    "progress.status_running": {"de": "läuft", "en": "running"},
    "progress.status_ok": {"de": "fertig", "en": "done"},
    "progress.status_failed": {"de": "fehlgeschlagen", "en": "failed"},
    "progress.run_label": {"de": "Lauf", "en": "Run"},
```

- [ ] **Step 4: Route in `admin.py` ergänzen**

Am Ende von `02-webconsole/api/admin.py` (nach der letzten bestehenden Route, vor evtl. Hilfsfunktionen) einfügen, und `import progress` oben bei den anderen Imports ergänzen:

```python
@bp.route("/progress", methods=["GET"])
@require_auth
def progress_view(username):
    installs = progress.list_active_installs()
    return render_template("progress.html", installs=installs, username=username)
```

- [ ] **Step 5: Template erstellen**

`02-webconsole/api/templates/progress.html`:

```html
{% extends "base.html" %}
{% block title %}{{ t("progress.title") }}{% endblock %}
{% block content %}
  <h1>{{ t("progress.heading") }}</h1>

  <div id="progress-grid">
    {% for install in installs %}
    <table class="history-table progress-table">
      <thead>
        <tr>
          <th>{{ install.hostname }}</th>
          {% for entry in install.tasks %}
          <th>{{ entry.task }}</th>
          {% endfor %}
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>
            <span class="log-status {% if install.overall == 'ok' %}log-status-ok{% elif install.overall == 'failed' %}log-status-failed{% endif %}">
              {{ t("progress.status_" + install.overall) }}
            </span>
            <div class="device-meta">{{ t("progress.run_label") }}: {{ install.run_id }}</div>
          </td>
          {% for entry in install.tasks %}
          <td class="progress-task progress-task-{{ entry.status }}"></td>
          {% endfor %}
        </tr>
      </tbody>
    </table>
    {% else %}
    <p class="empty">{{ t("progress.empty") }}</p>
    {% endfor %}
  </div>

  <script>
    function refreshProgress() {
      fetch(window.location.href)
        .then(function (resp) { return resp.text(); })
        .then(function (html) {
          var doc = new DOMParser().parseFromString(html, 'text/html');
          var fresh = doc.getElementById('progress-grid');
          if (fresh) {
            document.getElementById('progress-grid').innerHTML = fresh.innerHTML;
          }
        })
        .catch(function () { /* stiller Retry beim naechsten Intervall */ });
    }

    setInterval(refreshProgress, 3000);
  </script>
{% endblock %}
```

- [ ] **Step 6: Nav-Link in `base.html` ergänzen**

In `02-webconsole/api/templates/base.html`, nach der Zeile mit `admin.discovery_form` einfügen:

```html
        <a href="{{ url_for('admin.progress_view') }}">{{ t("nav.progress") }}</a>
```

- [ ] **Step 7: CSS für Task-Zellen ergänzen**

An `02-webconsole/api/static/style.css` anhängen:

```css
.progress-table {
  margin-bottom: 24px;
}

.progress-task {
  text-align: center;
  min-width: 90px;
}

.progress-task-running {
  color: var(--text);
  opacity: .6;
}

.progress-task-ok::after {
  content: "\2713";
  color: var(--accent);
  font-weight: 600;
}

.progress-task-failed::after {
  content: "\2717";
  color: var(--danger);
  font-weight: 600;
}
```

- [ ] **Step 8: Tests ausführen, sicherstellen dass sie bestehen**

Run: `cd 02-webconsole/api && ../../venv/bin/pytest test_admin.py -v -k progress`
Expected: PASS (3 Tests)

- [ ] **Step 9: Vollständige Testsuite laufen lassen (keine Regression)**

Run: `cd 02-webconsole/api && ../../venv/bin/pytest -v`
Expected: PASS (alle Tests)

- [ ] **Step 10: Commit**

```bash
git add 02-webconsole/api/admin.py 02-webconsole/api/i18n.py \
        02-webconsole/api/templates/base.html 02-webconsole/api/templates/progress.html \
        02-webconsole/api/static/style.css 02-webconsole/api/test_admin.py
git commit -m "feat: Live-Fortschrittsseite /admin/progress in der Webkonsole"
```

---

### Task 3: Deployment auf faiserver2

**Files:** keine (reines Ops-Task, kein Code)

- [ ] **Step 1: Push nach `origin main`**

```bash
git push origin main
```

- [ ] **Step 2: App-Code auf faiserver2 aktualisieren**

```bash
ssh thomas@faiserver2.mein.lan "sudo -n git -C /opt/fai-discovery-repo pull"
```

- [ ] **Step 3: Service neu starten**

```bash
ssh thomas@faiserver2.mein.lan "sudo -n systemctl restart fai-discovery-webconsole.service"
```

- [ ] **Step 4: Service-Status und Logs prüfen**

```bash
ssh thomas@faiserver2.mein.lan "systemctl is-active fai-discovery-webconsole.service"
ssh thomas@faiserver2.mein.lan "journalctl -u fai-discovery-webconsole.service -n 30 --no-pager"
```

Expected: `active`, keine Traceback-Zeilen im Log.

- [ ] **Step 5: Route-Smoke-Test**

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://faiserver2.mein.lan:8080/admin/progress
```

Expected: `401` (Route existiert, Auth greift, kein 500/Connection-Fehler). Bei `500`: `journalctl`-Output analysieren und Fix nachcommitten, dann Schritte 1-5 wiederholen.
