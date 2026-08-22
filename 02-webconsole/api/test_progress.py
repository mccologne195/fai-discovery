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
