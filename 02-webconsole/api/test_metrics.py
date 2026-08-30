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
