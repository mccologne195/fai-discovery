import progress
import storage


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


UNPREFIXED_LOG_EXCERPT = """\
TASKBEGIN confdir
check
TASKBEGIN confdir
TASKEND confdir 0
HOOK setup.DEFAULT.sh
TASKBEGIN setup
TASKEND setup 0
TASKBEGIN partition
TASKEND partition 0
TASKBEGIN configure
"""


def test_parse_task_log_handles_lines_without_hostname_prefix():
    # remote-logs/<host>/install-*/fai-monitor.log hat kein Hostname-Praefix
    # mehr (anders als das globale Log) - der Host steht schon im
    # Verzeichnisnamen.
    tasks = progress.parse_task_log(UNPREFIXED_LOG_EXCERPT)
    by_name = {t["task"]: t["status"] for t in tasks}
    assert by_name["confdir"] == "ok"
    assert by_name["setup"] == "ok"
    assert by_name["partition"] == "ok"
    assert by_name["configure"] == "running"
    assert "check" not in by_name


def test_read_task_progress_handles_unprefixed_remote_log_copy(tmp_path):
    install_dir = tmp_path / "install-20260821_104033"
    install_dir.mkdir()
    (install_dir / "fai-monitor.log").write_text(UNPREFIXED_LOG_EXCERPT)

    tasks = progress.read_task_progress(install_dir)

    assert tasks is not None
    assert tasks != []
    by_name = {t["task"]: t["status"] for t in tasks}
    assert by_name["partition"] == "ok"


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


def _make_install_dir(base_dir, hostname, run_id, log_text, task_error=None):
    install_dir = base_dir / hostname / f"install-{run_id}"
    install_dir.mkdir(parents=True)
    (install_dir / "fai-monitor.log").write_text(log_text)
    if task_error is not None:
        (install_dir / "task_error").write_text(str(task_error))
    return install_dir


def _register_and_approve(mac, hostname):
    storage.register_device(mac, "192.168.10.99", "CPU", "8", "100G")
    storage.approve_device(mac, hostname, "SALT STEP", "admin")


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


def test_running_macs_includes_running_host(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    monkeypatch.setenv("FAI_DISCOVERY_LOG_DIR", str(tmp_path / "remote-logs"))
    storage.init_db()
    _register_and_approve("aa:bb:cc:dd:ee:01", "hostA")
    _make_install_dir(tmp_path / "remote-logs", "hostA", "20260822120000", REAL_LOG_EXCERPT)

    assert progress.running_macs() == {"aa:bb:cc:dd:ee:01"}


def test_running_macs_excludes_finished_host(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    monkeypatch.setenv("FAI_DISCOVERY_LOG_DIR", str(tmp_path / "remote-logs"))
    storage.init_db()
    _register_and_approve("aa:bb:cc:dd:ee:02", "hostB")
    _make_install_dir(tmp_path / "remote-logs", "hostB", "20260822120000", REAL_LOG_EXCERPT, task_error=0)

    assert progress.running_macs() == set()


def test_running_macs_empty_when_no_history(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    monkeypatch.setenv("FAI_DISCOVERY_LOG_DIR", str(tmp_path / "remote-logs"))
    storage.init_db()

    assert progress.running_macs() == set()


def test_mark_unclosed_as_implicit_relabels_only_running_tasks():
    tasks = [
        {"task": "action", "status": "running"},
        {"task": "install", "status": "ok"},
        {"task": "configure", "status": "failed"},
    ]

    result = progress._mark_unclosed_as_implicit(tasks)

    by_name = {t["task"]: t["status"] for t in result}
    assert by_name["action"] == "implicit"
    assert by_name["install"] == "ok"
    assert by_name["configure"] == "failed"


def test_list_active_installs_finished_run_marks_never_closed_task_as_implicit(tmp_path, monkeypatch):
    # "action" bekommt in FAI nie ein eigenes TASKEND (nur sein Kind
    # "install"), siehe REAL_LOG_EXCERPT. Auf einem fertigen Lauf soll das
    # nicht wie "laeuft noch" aussehen, sondern als eigener "implicit"-Status.
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    monkeypatch.setenv("FAI_DISCOVERY_LOG_DIR", str(tmp_path / "remote-logs"))
    storage.init_db()
    _register_and_approve("aa:bb:cc:dd:ee:20", "hostD")
    _make_install_dir(
        tmp_path / "remote-logs", "hostD", "20260822120000", REAL_LOG_EXCERPT, task_error=0
    )

    result = progress.list_active_installs()

    by_name = {t["task"]: t["status"] for t in result[0]["tasks"]}
    assert by_name["action"] == "implicit"
    assert by_name["partition"] == "ok"
    assert by_name["configure"] == "failed"


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


def _write_monitor_log(tmp_path, text):
    path = tmp_path / "fai-monitor.log"
    path.write_text(text)
    return path


def test_list_active_installs_uses_global_monitor_log_when_remote_logs_stale(tmp_path, monkeypatch):
    # remote-logs/ enthaelt nur einen alten, laengst abgeschlossenen Lauf -
    # savelog befuellt das Verzeichnis erst spaet im naechsten Lauf, daher
    # muss der aktuell laufende Fortschritt aus dem globalen Log kommen.
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    monkeypatch.setenv("FAI_DISCOVERY_LOG_DIR", str(tmp_path / "remote-logs"))
    storage.init_db()
    _register_and_approve("aa:bb:cc:dd:ee:10", "testhost200")
    _make_install_dir(
        tmp_path / "remote-logs", "testhost200", "20260819170849", REAL_LOG_EXCERPT, task_error=0
    )

    monitor_log = (
        "aa:bb:cc:dd:ee:10 TASKBEGIN setup\n"
        "aa:bb:cc:dd:ee:10 TASKEND setup 0\n"
        "aa:bb:cc:dd:ee:10 TASKBEGIN defclass\n"
        "aa:bb:cc:dd:ee:10 TASKEND defclass 0\n"
        "aa:bb:cc:dd:ee:10 TASKBEGIN action\n"
        "aa:bb:cc:dd:ee:10 TASKBEGIN install\n"
        "aa:bb:cc:dd:ee:10 TASKBEGIN partition\n"
        "aa:bb:cc:dd:ee:10 TASKEND partition 0\n"
        "aa:bb:cc:dd:ee:10 TASKBEGIN instsoft\n"
    )
    monkeypatch.setenv(progress.MONITOR_LOG_ENV, str(_write_monitor_log(tmp_path, monitor_log)))

    result = progress.list_active_installs()

    assert len(result) == 1
    assert result[0]["hostname"] == "testhost200"
    assert result[0]["overall"] == "running"
    by_name = {t["task"]: t["status"] for t in result[0]["tasks"]}
    assert by_name["partition"] == "ok"
    assert by_name["instsoft"] == "running"


def test_list_active_installs_falls_back_to_remote_logs_once_reboot_task_ended(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    monkeypatch.setenv("FAI_DISCOVERY_LOG_DIR", str(tmp_path / "remote-logs"))
    storage.init_db()
    _register_and_approve("aa:bb:cc:dd:ee:11", "testhost201")
    _make_install_dir(
        tmp_path / "remote-logs", "testhost201", "20260822120000", REAL_LOG_EXCERPT, task_error=0
    )

    monitor_log = (
        "aa:bb:cc:dd:ee:11 TASKBEGIN setup\n"
        "aa:bb:cc:dd:ee:11 TASKEND setup 0\n"
        "aa:bb:cc:dd:ee:11 TASKBEGIN faiend\n"
        "aa:bb:cc:dd:ee:11 TASKEND faiend 0\n"
        "aa:bb:cc:dd:ee:11 TASKEND reboot 0\n"
    )
    monkeypatch.setenv(progress.MONITOR_LOG_ENV, str(_write_monitor_log(tmp_path, monitor_log)))

    result = progress.list_active_installs()

    assert len(result) == 1
    assert result[0]["overall"] == "ok"
    assert result[0]["run_id"] == "install-20260822120000"


def test_list_active_installs_uses_only_latest_run_segment_from_monitor_log(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    monkeypatch.setenv("FAI_DISCOVERY_LOG_DIR", str(tmp_path / "remote-logs"))
    storage.init_db()
    _register_and_approve("aa:bb:cc:dd:ee:12", "testhost202")

    monitor_log = (
        # Alter, abgeschlossener Lauf
        "aa:bb:cc:dd:ee:12 TASKBEGIN setup\n"
        "aa:bb:cc:dd:ee:12 TASKEND setup 0\n"
        "aa:bb:cc:dd:ee:12 TASKEND reboot 0\n"
        # Neuer, laufender Lauf
        "aa:bb:cc:dd:ee:12 TASKBEGIN setup\n"
        "aa:bb:cc:dd:ee:12 TASKEND setup 0\n"
        "aa:bb:cc:dd:ee:12 TASKBEGIN partition\n"
    )
    monkeypatch.setenv(progress.MONITOR_LOG_ENV, str(_write_monitor_log(tmp_path, monitor_log)))

    result = progress.list_active_installs()

    assert len(result) == 1
    assert result[0]["overall"] == "running"
    by_name = {t["task"]: t["status"] for t in result[0]["tasks"]}
    assert by_name["partition"] == "running"


def test_list_active_installs_matches_by_mac_not_hostname(tmp_path, monkeypatch):
    # Kernbug, den FAI_SENDID=mac beheben soll: FAI fixiert $HOSTNAME im
    # allerersten Task (confdir), lange bevor 02-set-hostname.sh den von der
    # Webkonsole zugewiesenen Hostnamen setzt - Monitor-Zeilen tragen daher
    # ueber den ganzen Lauf noch den alten DHCP-Hostnamen. Zeilen unter dem
    # (falschen) zugewiesenen Hostnamen duerfen NICHT matchen, nur die MAC.
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    monkeypatch.setenv("FAI_DISCOVERY_LOG_DIR", str(tmp_path / "remote-logs"))
    storage.init_db()
    _register_and_approve("aa:bb:cc:c4:29:99", "vm-bbe17a46")

    monitor_log = (
        # Alter DHCP-Hostname, wie ihn FAI tatsaechlich sendet - darf nicht matchen
        "test001 TASKBEGIN setup\n"
        "test001 TASKEND setup 0\n"
        "test001 TASKBEGIN partition\n"
        # Echte Monitor-Zeilen unter der MAC (FAI_SENDID=mac)
        "aa:bb:cc:c4:29:99 TASKBEGIN setup\n"
        "aa:bb:cc:c4:29:99 TASKEND setup 0\n"
        "aa:bb:cc:c4:29:99 TASKBEGIN instsoft\n"
    )
    monkeypatch.setenv(progress.MONITOR_LOG_ENV, str(_write_monitor_log(tmp_path, monitor_log)))

    result = progress.list_active_installs()

    assert len(result) == 1
    assert result[0]["hostname"] == "vm-bbe17a46"
    by_name = {t["task"]: t["status"] for t in result[0]["tasks"]}
    assert by_name["instsoft"] == "running"
    assert "partition" not in by_name  # das waere die (falsche) test001-Zeile


def test_list_active_installs_ignores_other_hosts_in_monitor_log(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    monkeypatch.setenv("FAI_DISCOVERY_LOG_DIR", str(tmp_path / "remote-logs"))
    storage.init_db()
    _register_and_approve("aa:bb:cc:dd:ee:13", "testhost203")

    monitor_log = (
        "aa:bb:cc:dd:ee:99 TASKBEGIN setup\n"
        "aa:bb:cc:dd:ee:99 TASKEND setup 0\n"
        "aa:bb:cc:dd:ee:99 TASKBEGIN partition\n"
        "aa:bb:cc:dd:ee:13 TASKBEGIN setup\n"
        "aa:bb:cc:dd:ee:13 TASKEND setup 0\n"
        "aa:bb:cc:dd:ee:13 TASKBEGIN partition\n"
    )
    monkeypatch.setenv(progress.MONITOR_LOG_ENV, str(_write_monitor_log(tmp_path, monitor_log)))

    result = progress.list_active_installs()

    assert len(result) == 1
    assert result[0]["hostname"] == "testhost203"
    by_name = {t["task"]: t["status"] for t in result[0]["tasks"]}
    assert by_name["partition"] == "running"


def test_monitor_log_path_defaults_when_env_unset(monkeypatch):
    monkeypatch.delenv(progress.MONITOR_LOG_ENV, raising=False)
    assert progress.monitor_log_path() == progress.DEFAULT_MONITOR_LOG_PATH


def test_monitor_log_path_reads_env_override(monkeypatch, tmp_path):
    custom = str(tmp_path / "custom.log")
    monkeypatch.setenv(progress.MONITOR_LOG_ENV, custom)
    assert progress.monitor_log_path() == custom


TRUNCATED_REMOTE_LOG_COPY = (
    "TASKBEGIN chboot\n"
    "TASKEND chboot 0\n"
    "HOOK savelog.LAST.sh\n"
    "TASKBEGIN savelog\n"
)


def test_list_active_installs_finished_run_uses_full_task_list_from_monitor_log(tmp_path, monkeypatch):
    # remote-logs/-Kopie bricht strukturell bei "TASKBEGIN savelog" ab (der
    # savelog-Task kann seine eigene TASKEND-Zeile nicht mehr in die Kopie
    # schreiben, die er selbst gerade erzeugt) - das globale Log hat aber
    # die vollstaendige Sequenz inkl. savelog/faiend/reboot.
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    monkeypatch.setenv("FAI_DISCOVERY_LOG_DIR", str(tmp_path / "remote-logs"))
    storage.init_db()
    _register_and_approve("aa:bb:cc:dd:ee:14", "testhost204")
    _make_install_dir(
        tmp_path / "remote-logs",
        "testhost204",
        "20260822135944",
        TRUNCATED_REMOTE_LOG_COPY,
        task_error=0,
    )

    monitor_log = (
        "aa:bb:cc:dd:ee:14 TASKBEGIN setup\n"
        "aa:bb:cc:dd:ee:14 TASKEND setup 0\n"
        "aa:bb:cc:dd:ee:14 TASKBEGIN chboot\n"
        "aa:bb:cc:dd:ee:14 TASKEND chboot 0\n"
        "aa:bb:cc:dd:ee:14 HOOK savelog.LAST.sh\n"
        "aa:bb:cc:dd:ee:14 TASKBEGIN savelog\n"
        "aa:bb:cc:dd:ee:14 TASKEND savelog 0\n"
        "aa:bb:cc:dd:ee:14 TASKBEGIN faiend\n"
        "aa:bb:cc:dd:ee:14 TASKEND faiend 0\n"
        "aa:bb:cc:dd:ee:14 TASKEND reboot 0\n"
    )
    monkeypatch.setenv(progress.MONITOR_LOG_ENV, str(_write_monitor_log(tmp_path, monitor_log)))

    result = progress.list_active_installs()

    assert len(result) == 1
    assert result[0]["overall"] == "ok"
    by_name = {t["task"]: t["status"] for t in result[0]["tasks"]}
    assert by_name["savelog"] == "ok"
    assert by_name["faiend"] == "ok"
    assert "reboot" not in by_name  # reboot ist der Abschluss-Marker selbst, kein eigener Task-Balken


def test_list_active_installs_finished_run_falls_back_when_host_missing_from_monitor_log(tmp_path, monkeypatch):
    # Host taucht im (begrenzten) Fenster des globalen Logs gar nicht mehr
    # auf (z.B. sehr alte Installation) - dann lieber die unvollstaendige
    # remote-logs/-Liste zeigen als gar keine Tasks.
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    monkeypatch.setenv("FAI_DISCOVERY_LOG_DIR", str(tmp_path / "remote-logs"))
    storage.init_db()
    _register_and_approve("aa:bb:cc:dd:ee:15", "testhost205old")
    _make_install_dir(
        tmp_path / "remote-logs",
        "testhost205old",
        "20260101120000",
        TRUNCATED_REMOTE_LOG_COPY,
        task_error=0,
    )

    monitor_log = "otherhost TASKBEGIN setup\notherhost TASKEND setup 0\notherhost TASKEND reboot 0\n"
    monkeypatch.setenv(progress.MONITOR_LOG_ENV, str(_write_monitor_log(tmp_path, monitor_log)))

    result = progress.list_active_installs()

    assert len(result) == 1
    assert result[0]["overall"] == "ok"
    by_name = {t["task"]: t["status"] for t in result[0]["tasks"]}
    assert by_name["chboot"] == "ok"
    assert by_name["savelog"] == "implicit"  # remote-logs-Fallback bricht bei savelog ab (TASKBEGIN ohne TASKEND), Lauf ist aber fertig -> implicit statt running
