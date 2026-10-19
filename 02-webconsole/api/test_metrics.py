import metrics
import storage


def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv("FAI_DISCOVERY_METRICS_ENABLED", raising=False)
    assert metrics.enabled() is False


def test_enabled_true(monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_METRICS_ENABLED", "true")
    assert metrics.enabled() is True


def test_enabled_case_insensitive_with_whitespace(monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_METRICS_ENABLED", "  True  ")
    assert metrics.enabled() is True


def test_enabled_other_value_is_false(monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_METRICS_ENABLED", "yes")
    assert metrics.enabled() is False


def test_render_reports_device_counts_by_status(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    storage.init_db()
    storage.register_device("aa:bb:cc:dd:ee:01", "1.1.1.1", "cpu", "1", "1G")
    storage.register_device("aa:bb:cc:dd:ee:02", "1.1.1.2", "cpu", "1", "1G")
    storage.approve_device("aa:bb:cc:dd:ee:02", "host2", "FAIBASE", "admin")

    output = metrics.render().decode()

    assert 'fai_discovery_devices{status="waiting"} 1.0' in output
    assert 'fai_discovery_devices{status="reboot"} 1.0' in output
    assert 'fai_discovery_devices{status="discarded"} 0.0' in output
    assert 'fai_discovery_devices{status="reinstalling"} 0.0' in output


def test_render_content_type():
    assert metrics.CONTENT_TYPE.startswith("text/plain")


def test_render_includes_info_metric(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    storage.init_db()

    output = metrics.render().decode()

    assert "fai_discovery_info{" in output


def test_render_reports_class_usage(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    storage.init_db()
    storage.register_device("aa:bb:cc:dd:ee:01", "1.1.1.1", "cpu", "1", "1G")
    storage.approve_device("aa:bb:cc:dd:ee:01", "host1", "FAIBASE XORG GNOME", "admin")
    storage.register_device("aa:bb:cc:dd:ee:02", "1.1.1.2", "cpu", "1", "1G")
    storage.approve_device("aa:bb:cc:dd:ee:02", "host2", "FAIBASE", "admin")

    output = metrics.render().decode()

    assert 'fai_discovery_class_usage{class="FAIBASE"} 2.0' in output
    assert 'fai_discovery_class_usage{class="XORG"} 1.0' in output
    assert 'fai_discovery_class_usage{class="GNOME"} 1.0' in output


def test_render_omits_class_usage_when_no_classes_recorded(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    storage.init_db()

    output = metrics.render().decode()

    assert "fai_discovery_class_usage" not in output


def test_available_is_true_when_prometheus_client_is_installed():
    assert metrics.AVAILABLE is True


def test_app_imports_and_serves_without_prometheus_client(tmp_path):
    # Ohne python3-prometheus-client darf die Webconsole nicht mehr beim
    # Import abbrechen; nur /metrics faellt aus. sys.modules[...] = None laesst
    # "import prometheus_client" mit ImportError scheitern.
    import subprocess
    import sys
    from pathlib import Path

    api_dir = str(Path(__file__).resolve().parent)
    code = (
        "import sys\n"
        "sys.modules['prometheus_client'] = None\n"
        f"sys.path.insert(0, {api_dir!r})\n"
        "import metrics\n"
        "assert metrics.AVAILABLE is False\n"
        "import app\n"
        "c = app.app.test_client()\n"
        "print(c.get('/metrics').status_code)\n"
    )
    env = {"FAI_DISCOVERY_DB_PATH": str(tmp_path / "devices.db"), "FAI_DISCOVERY_METRICS_ENABLED": "true"}
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines()[-1] == "503"


def test_metrics_endpoint_returns_503_when_enabled_but_library_missing(tmp_path, monkeypatch):
    import app as app_module

    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    monkeypatch.setenv("FAI_DISCOVERY_METRICS_ENABLED", "true")
    monkeypatch.setattr(metrics, "AVAILABLE", False)

    resp = app_module.app.test_client().get("/metrics")

    assert resp.status_code == 503
    assert "python3-prometheus-client" in resp.get_data(as_text=True)


def test_metrics_endpoint_stays_404_when_disabled_and_library_missing(tmp_path, monkeypatch):
    import app as app_module

    monkeypatch.delenv("FAI_DISCOVERY_METRICS_ENABLED", raising=False)
    monkeypatch.setattr(metrics, "AVAILABLE", False)

    assert app_module.app.test_client().get("/metrics").status_code == 404
