import logs


def test_find_latest_install_dir_picks_most_recent(tmp_path):
    host_dir = tmp_path / "vmtest01"
    host_dir.mkdir()
    (host_dir / "install-20260810_120000").mkdir()
    newest = host_dir / "install-20260817_174532"
    newest.mkdir()
    (host_dir / "install-20260815_090000").mkdir()

    result = logs.find_latest_install_dir(tmp_path, "vmtest01")

    assert result == newest


def test_find_latest_install_dir_returns_none_for_unknown_hostname(tmp_path):
    result = logs.find_latest_install_dir(tmp_path, "unknown-host")

    assert result is None


def test_find_latest_install_dir_returns_none_when_no_install_runs_exist(tmp_path):
    (tmp_path / "vmtest01").mkdir()

    result = logs.find_latest_install_dir(tmp_path, "vmtest01")

    assert result is None


def test_read_install_log_parses_success(tmp_path):
    install_dir = tmp_path / "install-20260817_174532"
    install_dir.mkdir()
    (install_dir / "task_error").write_text("0\n")
    (install_dir / "status.log").write_text("setup.DEFAULT.sh     OK.\ninstsoft.DEBIAN      OK.\n")
    (install_dir / "error.log").write_text("")

    result = logs.read_install_log(install_dir)

    assert result["task_error"] == 0
    assert result["ok"] is True
    assert "instsoft.DEBIAN" in result["status"]
    assert result["error"] is None


def test_read_install_log_parses_failure_with_errors(tmp_path):
    install_dir = tmp_path / "install-20260817_174532"
    install_dir.mkdir()
    (install_dir / "task_error").write_text("701\n")
    (install_dir / "status.log").write_text("instsoft.DEBIAN      FAILED.\n")
    (install_dir / "error.log").write_text("scripts.log:some error happened\n")

    result = logs.read_install_log(install_dir)

    assert result["task_error"] == 701
    assert result["ok"] is False
    assert result["error"] == "scripts.log:some error happened\n"


def test_read_install_log_handles_missing_files_gracefully(tmp_path):
    install_dir = tmp_path / "install-20260817_174532"
    install_dir.mkdir()

    result = logs.read_install_log(install_dir)

    assert result["task_error"] is None
    assert result["ok"] is None
    assert result["status"] is None
    assert result["error"] is None
