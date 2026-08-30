import json

import pytest
from werkzeug.security import generate_password_hash

import app as app_module
import chboot
import diskconfig
import storage


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    admins_file = tmp_path / "admins.json"
    admins_file.write_text(json.dumps({"admin": generate_password_hash("s3cret")}))
    monkeypatch.setenv("FAI_DISCOVERY_ADMINS_FILE", str(admins_file))
    storage.init_db()
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


AUTH_HEADERS = {"Authorization": "Basic " + __import__("base64").b64encode(b"admin:s3cret").decode()}


def test_register_creates_waiting_device(client):
    resp = client.post("/register", json={
        "mac": "AA:BB:CC:DD:EE:FF", "ip": "192.168.10.55", "cpu": "Intel i5", "ram": "16", "disk": "500G",
    })
    assert resp.status_code == 200
    device = storage.get_device("aa:bb:cc:dd:ee:ff")
    assert device["status"] == "waiting"
    assert device["ip"] == "192.168.10.55"


def test_register_stores_uuid_and_serial(client):
    resp = client.post("/register", json={
        "mac": "AA:BB:CC:DD:EE:FF", "ip": "192.168.10.55", "cpu": "Intel i5", "ram": "16", "disk": "500G",
        "uuid": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "serial": "ABC123",
    })
    assert resp.status_code == 200
    device = storage.get_device("aa:bb:cc:dd:ee:ff")
    assert device["uuid"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert device["serial"] == "ABC123"


def test_register_rejects_invalid_mac(client):
    resp = client.post("/register", json={"mac": "not-a-mac"})
    assert resp.status_code == 400


def test_status_unknown_mac_returns_waiting(client):
    resp = client.get("/status/aa:bb:cc:dd:ee:ff")
    assert resp.status_code == 200
    assert resp.data == b"waiting"


def test_status_invalid_mac_returns_waiting_not_error(client):
    resp = client.get("/status/../../etc/passwd")
    assert resp.status_code == 200
    assert resp.data == b"waiting"


def test_approve_requires_auth(client):
    resp = client.post("/approve", json={"mac": "aa:bb:cc:dd:ee:ff", "hostname": "h", "classes": "FAIBASE"})
    assert resp.status_code == 401


def test_approve_with_valid_auth_calls_chboot_and_updates_status(client, monkeypatch):
    client.post("/register", json={"mac": "aa:bb:cc:dd:ee:ff", "ip": "", "cpu": "", "ram": "", "disk": ""})

    monkeypatch.setattr(chboot, "run_fai_chboot", lambda mac, classes: (True, "ok"))

    resp = client.post(
        "/approve",
        json={"mac": "aa:bb:cc:dd:ee:ff", "hostname": "vmtest01", "classes": "FAIBASE DEBIAN"},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200

    status_resp = client.get("/status/aa:bb:cc:dd:ee:ff")
    assert status_resp.data == b"reboot"
    device = storage.get_device("aa:bb:cc:dd:ee:ff")
    assert device["approved_by"] == "admin"


def test_approve_returns_502_when_chboot_fails(client, monkeypatch):
    client.post("/register", json={"mac": "aa:bb:cc:dd:ee:ff", "ip": "", "cpu": "", "ram": "", "disk": ""})
    monkeypatch.setattr(chboot, "run_fai_chboot", lambda mac, classes: (False, "boom"))

    resp = client.post(
        "/approve",
        json={"mac": "aa:bb:cc:dd:ee:ff", "hostname": "h", "classes": "FAIBASE"},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 502
    device = storage.get_device("aa:bb:cc:dd:ee:ff")
    assert device["status"] == "waiting"


def test_approve_unknown_mac_returns_404(client):
    resp = client.post(
        "/approve",
        json={"mac": "11:22:33:44:55:66", "hostname": "h", "classes": "c"},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 404


def _forbid_chboot_call(mac, classes):
    raise AssertionError("chboot.run_fai_chboot must not be called for invalid input")


def test_approve_rejects_empty_hostname(client, monkeypatch):
    client.post("/register", json={"mac": "aa:bb:cc:dd:ee:ff", "ip": "", "cpu": "", "ram": "", "disk": ""})
    monkeypatch.setattr(chboot, "run_fai_chboot", _forbid_chboot_call)

    resp = client.post(
        "/approve",
        json={"mac": "aa:bb:cc:dd:ee:ff", "hostname": "", "classes": "FAIBASE"},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 400
    device = storage.get_device("aa:bb:cc:dd:ee:ff")
    assert device["status"] == "waiting"


def test_approve_rejects_non_string_hostname(client, monkeypatch):
    client.post("/register", json={"mac": "aa:bb:cc:dd:ee:ff", "ip": "", "cpu": "", "ram": "", "disk": ""})
    monkeypatch.setattr(chboot, "run_fai_chboot", _forbid_chboot_call)

    resp = client.post(
        "/approve",
        json={"mac": "aa:bb:cc:dd:ee:ff", "hostname": {"a": 1}, "classes": "FAIBASE"},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 400
    device = storage.get_device("aa:bb:cc:dd:ee:ff")
    assert device["status"] == "waiting"


def test_approve_rejects_hostname_with_shell_metacharacters(client, monkeypatch):
    client.post("/register", json={"mac": "aa:bb:cc:dd:ee:ff", "ip": "", "cpu": "", "ram": "", "disk": ""})
    monkeypatch.setattr(chboot, "run_fai_chboot", _forbid_chboot_call)

    resp = client.post(
        "/approve",
        json={"mac": "aa:bb:cc:dd:ee:ff", "hostname": "foo; touch /tmp/x", "classes": "FAIBASE"},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 400
    device = storage.get_device("aa:bb:cc:dd:ee:ff")
    assert device["status"] == "waiting"


def test_approve_rejects_hostname_with_space(client, monkeypatch):
    client.post("/register", json={"mac": "aa:bb:cc:dd:ee:ff", "ip": "", "cpu": "", "ram": "", "disk": ""})
    monkeypatch.setattr(chboot, "run_fai_chboot", _forbid_chboot_call)

    resp = client.post(
        "/approve",
        json={"mac": "aa:bb:cc:dd:ee:ff", "hostname": "foo bar", "classes": "FAIBASE"},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 400
    device = storage.get_device("aa:bb:cc:dd:ee:ff")
    assert device["status"] == "waiting"


def test_approve_accepts_valid_hostnames(client, monkeypatch):
    client.post("/register", json={"mac": "aa:bb:cc:dd:ee:ff", "ip": "", "cpu": "", "ram": "", "disk": ""})
    monkeypatch.setattr(chboot, "run_fai_chboot", lambda mac, classes: (True, "ok"))

    for hostname in ("vmtest01", "vm-test-01"):
        resp = client.post(
            "/approve",
            json={"mac": "aa:bb:cc:dd:ee:ff", "hostname": hostname, "classes": "FAIBASE"},
            headers=AUTH_HEADERS,
        )
        assert resp.status_code == 200
        device = storage.get_device("aa:bb:cc:dd:ee:ff")
        assert device["hostname"] == hostname


def test_approve_rejects_invalid_classes_with_400_not_502(client, monkeypatch):
    client.post("/register", json={"mac": "aa:bb:cc:dd:ee:ff", "ip": "", "cpu": "", "ram": "", "disk": ""})
    monkeypatch.setattr(chboot, "run_fai_chboot", _forbid_chboot_call)

    resp_empty = client.post(
        "/approve",
        json={"mac": "aa:bb:cc:dd:ee:ff", "hostname": "vmtest01", "classes": ""},
        headers=AUTH_HEADERS,
    )
    assert resp_empty.status_code == 400

    resp_wrong_type = client.post(
        "/approve",
        json={"mac": "aa:bb:cc:dd:ee:ff", "hostname": "vmtest01", "classes": ["FAIBASE"]},
        headers=AUTH_HEADERS,
    )
    assert resp_wrong_type.status_code == 400

    device = storage.get_device("aa:bb:cc:dd:ee:ff")
    assert device["status"] == "waiting"


def test_register_coerces_non_string_fields(client):
    resp = client.post("/register", json={
        "mac": "aa:bb:cc:dd:ee:ff", "ip": {"x": 1}, "cpu": 4, "ram": 16, "disk": ["500G"],
    })
    assert resp.status_code == 200
    device = storage.get_device("aa:bb:cc:dd:ee:ff")
    assert device["ip"] == str({"x": 1})
    assert device["cpu"] == "4"
    assert device["ram"] == "16"
    assert device["disk"] == str(["500G"])


def test_device_unknown_mac_returns_null_fields(client):
    resp = client.get("/device/aa:bb:cc:dd:ee:ff")
    assert resp.status_code == 200
    assert resp.get_json() == {"hostname": None, "classes": None}


def test_device_invalid_mac_returns_null_fields_not_error(client):
    resp = client.get("/device/not-a-mac")
    assert resp.status_code == 200
    assert resp.get_json() == {"hostname": None, "classes": None}


def test_device_waiting_device_returns_null_fields(client):
    client.post("/register", json={
        "mac": "aa:bb:cc:dd:ee:ff", "ip": "", "cpu": "", "ram": "", "disk": "",
    })

    resp = client.get("/device/aa:bb:cc:dd:ee:ff")

    assert resp.status_code == 200
    assert resp.get_json() == {"hostname": None, "classes": None}


def test_device_approved_device_returns_hostname_and_classes(client):
    client.post("/register", json={
        "mac": "aa:bb:cc:dd:ee:ff", "ip": "", "cpu": "", "ram": "", "disk": "",
    })
    storage.approve_device("aa:bb:cc:dd:ee:ff", "vmtest01", "FAIBASE DEBIAN SALT", "admin")

    resp = client.get("/device/aa:bb:cc:dd:ee:ff")

    assert resp.status_code == 200
    assert resp.get_json() == {"hostname": "vmtest01", "classes": "FAIBASE DEBIAN SALT"}


def test_register_stores_firmware(client):
    resp = client.post("/register", json={
        "mac": "AA:BB:CC:DD:EE:FF", "ip": "1.1.1.1", "cpu": "cpu", "ram": "1", "disk": "1G",
        "firmware": "uefi",
    })
    assert resp.status_code == 200
    device = storage.get_device("aa:bb:cc:dd:ee:ff")
    assert device["firmware"] == "uefi"


def test_approve_appends_efi_classes_when_firmware_uefi(client, monkeypatch, tmp_path):
    monkeypatch.setenv("FAI_DISCOVERY_DISK_CONFIG_DIR", str(tmp_path))
    (tmp_path / "FAIBASE_EFI").write_text("dummy")
    client.post("/register", json={
        "mac": "aa:bb:cc:dd:ee:ff", "ip": "", "cpu": "", "ram": "", "disk": "", "firmware": "uefi",
    })

    calls = []
    monkeypatch.setattr(
        chboot, "run_fai_chboot",
        lambda mac, classes: (calls.append(classes) or True, "ok"),
    )

    resp = client.post(
        "/approve",
        json={"mac": "aa:bb:cc:dd:ee:ff", "hostname": "vmtest01", "classes": "INSTALL FAIBASE DEBIAN"},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200
    assert calls == ["INSTALL FAIBASE DEBIAN FAIBASE_EFI"]
    device = storage.get_device("aa:bb:cc:dd:ee:ff")
    assert device["classes"] == "INSTALL FAIBASE DEBIAN FAIBASE_EFI"


def test_approve_does_not_append_efi_classes_when_firmware_bios(client, monkeypatch, tmp_path):
    monkeypatch.setenv("FAI_DISCOVERY_DISK_CONFIG_DIR", str(tmp_path))
    (tmp_path / "FAIBASE_EFI").write_text("dummy")
    client.post("/register", json={
        "mac": "aa:bb:cc:dd:ee:ff", "ip": "", "cpu": "", "ram": "", "disk": "", "firmware": "bios",
    })

    calls = []
    monkeypatch.setattr(
        chboot, "run_fai_chboot",
        lambda mac, classes: (calls.append(classes) or True, "ok"),
    )

    resp = client.post(
        "/approve",
        json={"mac": "aa:bb:cc:dd:ee:ff", "hostname": "vmtest01", "classes": "INSTALL FAIBASE DEBIAN"},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200
    assert calls == ["INSTALL FAIBASE DEBIAN"]


def test_approve_rejects_classes_with_path_traversal_characters(client, monkeypatch):
    client.post("/register", json={"mac": "aa:bb:cc:dd:ee:ff", "ip": "", "cpu": "", "ram": "", "disk": ""})

    def _forbid_diskconfig_call(classes_str, firmware):
        raise AssertionError("diskconfig.classes_with_efi_variants must not be called for invalid classes")

    monkeypatch.setattr(diskconfig, "classes_with_efi_variants", _forbid_diskconfig_call)

    resp = client.post(
        "/approve",
        json={"mac": "aa:bb:cc:dd:ee:ff", "hostname": "vmtest01", "classes": "../../../../etc/passwd"},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 400


def test_approve_handles_null_firmware_from_pre_migration_device(client, monkeypatch):
    conn = storage.get_connection()
    conn.execute("ALTER TABLE devices RENAME TO devices_old")
    conn.execute(
        """
        CREATE TABLE devices (
            mac TEXT PRIMARY KEY, ip TEXT, cpu TEXT, ram TEXT, disk TEXT,
            registered_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'waiting',
            hostname TEXT, classes TEXT, approved_by TEXT, approved_at TEXT,
            uuid TEXT, serial TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO devices (mac, ip, cpu, ram, disk, registered_at, status) VALUES (?, ?, ?, ?, ?, ?, 'waiting')",
        ("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G", "2026-01-01T00:00:00+00:00"),
    )
    conn.execute("DROP TABLE devices_old")
    conn.commit()
    conn.close()
    storage.get_connection().close()  # triggers the ALTER TABLE ADD COLUMN firmware migration

    monkeypatch.setattr(chboot, "run_fai_chboot", lambda mac, classes: (True, "ok"))

    resp = client.post(
        "/approve",
        json={"mac": "aa:bb:cc:dd:ee:ff", "hostname": "vmtest01", "classes": "FAIBASE"},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200


def test_metrics_returns_404_when_disabled(client, monkeypatch):
    monkeypatch.delenv("FAI_DISCOVERY_METRICS_ENABLED", raising=False)

    resp = client.get("/metrics")

    assert resp.status_code == 404


def test_metrics_returns_prometheus_text_when_enabled(client, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_METRICS_ENABLED", "true")

    resp = client.get("/metrics")

    assert resp.status_code == 200
    assert resp.content_type.startswith("text/plain")
    assert "fai_discovery_devices" in resp.get_data(as_text=True)


def test_metrics_requires_no_auth(client, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_METRICS_ENABLED", "true")

    resp = client.get("/metrics")

    assert resp.status_code != 401
