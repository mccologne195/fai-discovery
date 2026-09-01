import base64
import json
import re

import pytest
from werkzeug.security import generate_password_hash

import app as app_module
import chboot
import logs
import profiles
import progress
import storage

AUTH_HEADERS = {"Authorization": "Basic " + base64.b64encode(b"admin:s3cret").decode()}

SAMPLE_PROFILE = """Name: Debian 13 + EXT4 System
Classes: INSTALL FAIBASE DEBIAN STEP SALT SECURE TRIXIE64
"""


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    admins_file = tmp_path / "admins.json"
    admins_file.write_text(json.dumps({"admin": generate_password_hash("s3cret")}))
    monkeypatch.setenv("FAI_DISCOVERY_ADMINS_FILE", str(admins_file))
    profile_file = tmp_path / "example.profile"
    profile_file.write_text(SAMPLE_PROFILE)
    monkeypatch.setenv("FAI_DISCOVERY_PROFILE_FILE", str(profile_file))
    storage.init_db()
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


def test_dashboard_requires_auth(client):
    resp = client.get("/admin/")
    assert resp.status_code == 401


def test_footer_shows_version_and_hostname(client, monkeypatch):
    monkeypatch.setattr(app_module.version, "current_version", lambda: "v1.0.5-2-gabc1234")
    monkeypatch.setattr(app_module.version, "current_hostname", lambda: "fai.example.com")

    resp = client.get("/admin/help", headers=AUTH_HEADERS)

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "v1.0.5-2-gabc1234" in body
    assert "fai.example.com" in body


def test_footer_falls_back_when_version_unknown(client, monkeypatch):
    monkeypatch.setattr(app_module.version, "current_version", lambda: None)

    resp = client.get("/admin/help", headers=AUTH_HEADERS)

    assert resp.status_code == 200
    assert "None" not in resp.get_data(as_text=True)


def test_dashboard_lists_waiting_devices(client):
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")

    resp = client.get("/admin/", headers=AUTH_HEADERS)

    assert resp.status_code == 200
    assert b"aa:bb:cc:dd:ee:ff" in resp.data


def test_approve_form_shows_profiles_from_file(client):
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")

    resp = client.get("/admin/approve/aa:bb:cc:dd:ee:ff", headers=AUTH_HEADERS)

    assert resp.status_code == 200
    assert b"Debian 13 + EXT4 System" in resp.data


def test_approve_form_unknown_mac_returns_404(client):
    resp = client.get("/admin/approve/11:22:33:44:55:66", headers=AUTH_HEADERS)
    assert resp.status_code == 404


def test_approve_submit_calls_chboot_and_redirects(client, monkeypatch):
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")
    monkeypatch.setattr(chboot, "run_fai_chboot", lambda mac, classes, reboot=False, verbose=True: (True, "ok"))

    resp = client.post(
        "/admin/approve/aa:bb:cc:dd:ee:ff",
        data={"hostname": "vmtest01", "profile": "Debian 13 + EXT4 System"},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 302
    device = storage.get_device("aa:bb:cc:dd:ee:ff")
    assert device["status"] == "reboot"
    assert device["hostname"] == "vmtest01"
    assert device["classes"] == "INSTALL FAIBASE DEBIAN STEP SALT SECURE TRIXIE64"
    assert device["approved_by"] == "admin"


def test_approve_submit_default_form_submission_is_verbose_on_reboot_off(client, monkeypatch):
    # Die verbose-Checkbox ist im Template per "checked" vorbelegt, daher
    # schickt eine unveraenderte Formularabsendung "verbose=on" mit, aber
    # kein "reboot"-Feld (dessen Checkbox ist standardmaessig nicht angehakt).
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")
    calls = []
    monkeypatch.setattr(
        chboot, "run_fai_chboot",
        lambda mac, classes, reboot=False, verbose=True: (calls.append((reboot, verbose)) or True, "ok"),
    )

    resp = client.post(
        "/admin/approve/aa:bb:cc:dd:ee:ff",
        data={"hostname": "vmtest01", "profile": "Debian 13 + EXT4 System", "verbose": "on"},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 302
    assert calls == [(False, True)]


def test_approve_submit_with_no_checkbox_fields_at_all_defaults_both_off(client, monkeypatch):
    # Absicherung fuer Nicht-Browser-Clients bzw. fehlende Felder: fehlt ein
    # Checkbox-Feld komplett, gilt es als nicht angehakt (Standard-HTML-
    # Semantik) - "verbose on" ist ausschliesslich ueber das vorbelegte
    # Template-Attribut abgesichert, nicht serverseitig.
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")
    calls = []
    monkeypatch.setattr(
        chboot, "run_fai_chboot",
        lambda mac, classes, reboot=False, verbose=True: (calls.append((reboot, verbose)) or True, "ok"),
    )

    resp = client.post(
        "/admin/approve/aa:bb:cc:dd:ee:ff",
        data={"hostname": "vmtest01", "profile": "Debian 13 + EXT4 System"},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 302
    assert calls == [(False, False)]


def test_approve_submit_passes_reboot_and_verbose_checkboxes_to_chboot(client, monkeypatch):
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")
    calls = []
    monkeypatch.setattr(
        chboot, "run_fai_chboot",
        lambda mac, classes, reboot=False, verbose=True: (calls.append((reboot, verbose)) or True, "ok"),
    )

    resp = client.post(
        "/admin/approve/aa:bb:cc:dd:ee:ff",
        data={"hostname": "vmtest01", "profile": "Debian 13 + EXT4 System", "reboot": "on"},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 302
    assert calls == [(True, False)]


def test_approve_submit_missing_hostname_shows_error(client):
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")

    resp = client.post(
        "/admin/approve/aa:bb:cc:dd:ee:ff",
        data={"hostname": "", "profile": "Debian 13 + EXT4 System"},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 400
    device = storage.get_device("aa:bb:cc:dd:ee:ff")
    assert device["status"] == "waiting"


def test_approve_submit_rejects_hostname_with_shell_metacharacters(client, monkeypatch):
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")

    def _forbid_chboot_call(mac, classes):
        raise AssertionError("chboot.run_fai_chboot must not be called for invalid input")

    monkeypatch.setattr(chboot, "run_fai_chboot", _forbid_chboot_call)

    resp = client.post(
        "/admin/approve/aa:bb:cc:dd:ee:ff",
        data={"hostname": "foo; touch /tmp/x", "profile": "Debian 13 + EXT4 System"},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 400
    device = storage.get_device("aa:bb:cc:dd:ee:ff")
    assert device["status"] == "waiting"


def test_history_shows_approved_devices(client, monkeypatch):
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")
    storage.approve_device("aa:bb:cc:dd:ee:ff", "vmtest01", "FAIBASE", "admin")

    resp = client.get("/admin/history", headers=AUTH_HEADERS)

    assert resp.status_code == 200
    assert b"vmtest01" in resp.data


def test_history_shows_approved_at_in_local_time(client):
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")
    storage.approve_device("aa:bb:cc:dd:ee:ff", "vmtest01", "FAIBASE", "admin")

    resp = client.get("/admin/history", headers=AUTH_HEADERS)
    body = resp.get_data(as_text=True)

    assert "+00:00" not in body
    assert not re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", body)


def test_dashboard_shows_registered_at_in_local_time(client):
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")

    resp = client.get("/admin/", headers=AUTH_HEADERS)
    body = resp.get_data(as_text=True)

    assert "+00:00" not in body


def test_approve_submit_returns_502_when_chboot_fails(client, monkeypatch):
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")
    monkeypatch.setattr(chboot, "run_fai_chboot", lambda mac, classes, reboot=False, verbose=True: (False, "boom"))

    resp = client.post(
        "/admin/approve/aa:bb:cc:dd:ee:ff",
        data={"hostname": "vmtest01", "profile": "Debian 13 + EXT4 System"},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 502
    device = storage.get_device("aa:bb:cc:dd:ee:ff")
    assert device["status"] == "waiting"


def test_approve_form_shows_error_when_profile_file_unreadable(client, monkeypatch):
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")

    def raise_oserror(path):
        raise OSError("nope")

    monkeypatch.setattr(profiles, "load_profiles", raise_oserror)

    resp = client.get("/admin/approve/aa:bb:cc:dd:ee:ff", headers=AUTH_HEADERS)

    assert resp.status_code == 200
    assert b"nicht lesbar" in resp.data


def test_approve_submit_shows_error_when_profile_file_unreadable(client, monkeypatch):
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")

    def raise_oserror(path):
        raise OSError("nope")

    monkeypatch.setattr(profiles, "load_profiles", raise_oserror)

    resp = client.post(
        "/admin/approve/aa:bb:cc:dd:ee:ff",
        data={"hostname": "vmtest01", "profile": "Debian 13 + EXT4 System"},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 500
    assert b"nicht lesbar" in resp.data
    device = storage.get_device("aa:bb:cc:dd:ee:ff")
    assert device["status"] == "waiting"


def test_approve_form_requires_auth(client):
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")

    resp = client.get("/admin/approve/aa:bb:cc:dd:ee:ff")

    assert resp.status_code == 401


def test_approve_submit_requires_auth(client):
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")

    resp = client.post(
        "/admin/approve/aa:bb:cc:dd:ee:ff",
        data={"hostname": "vmtest01", "profile": "Debian 13 + EXT4 System"},
    )

    assert resp.status_code == 401


def test_history_requires_auth(client):
    resp = client.get("/admin/history")
    assert resp.status_code == 401


def test_history_delete_removes_entry_and_redirects(client):
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")
    storage.approve_device("aa:bb:cc:dd:ee:ff", "vmtest01", "FAIBASE", "admin")

    resp = client.post("/admin/history/aa:bb:cc:dd:ee:ff/delete", headers=AUTH_HEADERS)

    assert resp.status_code == 302
    assert storage.get_device("aa:bb:cc:dd:ee:ff") is None


def test_history_delete_invalid_mac_returns_400(client):
    resp = client.post("/admin/history/not-a-mac/delete", headers=AUTH_HEADERS)
    assert resp.status_code == 400


def test_history_delete_unknown_mac_returns_404(client):
    resp = client.post("/admin/history/11:22:33:44:55:66/delete", headers=AUTH_HEADERS)
    assert resp.status_code == 404


def test_history_delete_waiting_entry_returns_404(client):
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")

    resp = client.post("/admin/history/aa:bb:cc:dd:ee:ff/delete", headers=AUTH_HEADERS)

    assert resp.status_code == 404
    assert storage.get_device("aa:bb:cc:dd:ee:ff") is not None


def test_history_delete_requires_auth(client):
    resp = client.post("/admin/history/aa:bb:cc:dd:ee:ff/delete")
    assert resp.status_code == 401


def test_history_logs_shows_status_and_error(client, monkeypatch, tmp_path):
    monkeypatch.setenv(logs.LOG_DIR_ENV, str(tmp_path))
    install_dir = tmp_path / "vmtest01" / "install-20260817_174532"
    install_dir.mkdir(parents=True)
    (install_dir / "task_error").write_text("0\n")
    (install_dir / "status.log").write_text("instsoft.DEBIAN      OK.\n")
    (install_dir / "error.log").write_text("")

    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")
    storage.approve_device("aa:bb:cc:dd:ee:ff", "vmtest01", "FAIBASE", "admin")

    resp = client.get("/admin/history/aa:bb:cc:dd:ee:ff/logs", headers=AUTH_HEADERS)

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "instsoft.DEBIAN" in body
    assert "install-20260817_174532" in body


def test_history_logs_no_log_directory_returns_404(client, monkeypatch, tmp_path):
    monkeypatch.setenv(logs.LOG_DIR_ENV, str(tmp_path))
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")
    storage.approve_device("aa:bb:cc:dd:ee:ff", "vmtest01", "FAIBASE", "admin")

    resp = client.get("/admin/history/aa:bb:cc:dd:ee:ff/logs", headers=AUTH_HEADERS)

    assert resp.status_code == 404


def test_history_logs_available_while_reinstalling(client, monkeypatch, tmp_path):
    monkeypatch.setenv(logs.LOG_DIR_ENV, str(tmp_path))
    install_dir = tmp_path / "vmtest01" / "install-20260817_174532"
    install_dir.mkdir(parents=True)
    (install_dir / "status.log").write_text("instsoft.DEBIAN      OK.\n")

    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")
    storage.approve_device("aa:bb:cc:dd:ee:ff", "vmtest01", "FAIBASE", "admin")
    storage.mark_reinstalling("aa:bb:cc:dd:ee:ff")

    resp = client.get("/admin/history/aa:bb:cc:dd:ee:ff/logs", headers=AUTH_HEADERS)

    assert resp.status_code == 200
    assert "instsoft.DEBIAN" in resp.get_data(as_text=True)


def test_history_logs_invalid_mac_returns_400(client):
    resp = client.get("/admin/history/not-a-mac/logs", headers=AUTH_HEADERS)
    assert resp.status_code == 400


def test_history_logs_requires_auth(client):
    resp = client.get("/admin/history/aa:bb:cc:dd:ee:ff/logs")
    assert resp.status_code == 401


def test_history_logs_full_returns_raw_fai_log(client, monkeypatch, tmp_path):
    monkeypatch.setenv(logs.LOG_DIR_ENV, str(tmp_path))
    install_dir = tmp_path / "vmtest01" / "install-20260817_174532"
    install_dir.mkdir(parents=True)
    (install_dir / "fai.log").write_text("very long verbose log content\n")

    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")
    storage.approve_device("aa:bb:cc:dd:ee:ff", "vmtest01", "FAIBASE", "admin")

    resp = client.get("/admin/history/aa:bb:cc:dd:ee:ff/logs/full", headers=AUTH_HEADERS)

    assert resp.status_code == 200
    assert resp.mimetype == "text/plain"
    assert "very long verbose log content" in resp.get_data(as_text=True)


def test_history_shows_delete_button(client):
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")
    storage.approve_device("aa:bb:cc:dd:ee:ff", "vmtest01", "FAIBASE", "admin")

    resp = client.get("/admin/history", headers=AUTH_HEADERS)

    assert b"/admin/history/aa:bb:cc:dd:ee:ff/delete" in resp.data


def test_history_reinstall_triggers_discovery_and_redirects(client, monkeypatch):
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")
    storage.approve_device("aa:bb:cc:dd:ee:ff", "vmtest01", "FAIBASE", "admin")

    calls = []
    monkeypatch.setattr(
        chboot,
        "run_fai_chboot_discovery",
        lambda mac, runner=None: calls.append(mac) or (True, "discovery mode set"),
    )

    resp = client.post("/admin/history/aa:bb:cc:dd:ee:ff/reinstall", headers=AUTH_HEADERS)

    assert resp.status_code == 302
    assert calls == ["aa:bb:cc:dd:ee:ff"]
    device = storage.get_device("aa:bb:cc:dd:ee:ff")
    assert device["status"] == "reinstalling"
    assert device["hostname"] == "vmtest01"


def test_history_reinstall_invalid_mac_returns_400(client):
    resp = client.post("/admin/history/not-a-mac/reinstall", headers=AUTH_HEADERS)
    assert resp.status_code == 400


def test_history_reinstall_unknown_mac_returns_404(client):
    resp = client.post("/admin/history/11:22:33:44:55:66/reinstall", headers=AUTH_HEADERS)
    assert resp.status_code == 404


def test_history_reinstall_waiting_entry_returns_404(client, monkeypatch):
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")

    def fail_if_called(mac, runner=None):
        raise AssertionError("run_fai_chboot_discovery must not be called for a waiting device")

    monkeypatch.setattr(chboot, "run_fai_chboot_discovery", fail_if_called)

    resp = client.post("/admin/history/aa:bb:cc:dd:ee:ff/reinstall", headers=AUTH_HEADERS)

    assert resp.status_code == 404


def test_history_reinstall_chboot_failure_keeps_entry_and_returns_502(client, monkeypatch):
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")
    storage.approve_device("aa:bb:cc:dd:ee:ff", "vmtest01", "FAIBASE", "admin")
    monkeypatch.setattr(chboot, "run_fai_chboot_discovery", lambda mac, runner=None: (False, "fai-chboot: boom"))

    resp = client.post("/admin/history/aa:bb:cc:dd:ee:ff/reinstall", headers=AUTH_HEADERS)

    assert resp.status_code == 502
    device = storage.get_device("aa:bb:cc:dd:ee:ff")
    assert device["status"] == "reboot"


def test_history_reinstall_requires_auth(client):
    resp = client.post("/admin/history/aa:bb:cc:dd:ee:ff/reinstall")
    assert resp.status_code == 401


def test_history_shows_reinstall_button(client):
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")
    storage.approve_device("aa:bb:cc:dd:ee:ff", "vmtest01", "FAIBASE", "admin")

    resp = client.get("/admin/history", headers=AUTH_HEADERS)

    assert b"/admin/history/aa:bb:cc:dd:ee:ff/reinstall" in resp.data


def test_history_shows_pending_badge_instead_of_buttons_while_reinstalling(client):
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")
    storage.approve_device("aa:bb:cc:dd:ee:ff", "vmtest01", "FAIBASE", "admin")
    storage.mark_reinstalling("aa:bb:cc:dd:ee:ff")

    resp = client.get("/admin/history", headers=AUTH_HEADERS)
    body = resp.get_data(as_text=True)

    assert "Wartet auf Neuinstallation" in body
    assert "/admin/history/aa:bb:cc:dd:ee:ff/reinstall" not in body
    assert "/admin/history/aa:bb:cc:dd:ee:ff/delete" not in body


def test_approve_form_shows_previous_hostname_suggestion(client):
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")
    storage.approve_device("aa:bb:cc:dd:ee:ff", "vmtest01", "FAIBASE", "admin")
    storage.register_device("aa:bb:cc:dd:ee:ff", "2.2.2.2", "cpu2", "2", "2G")

    resp = client.get("/admin/approve/aa:bb:cc:dd:ee:ff", headers=AUTH_HEADERS)

    assert resp.status_code == 200
    assert b"vmtest01" in resp.data


def test_approve_form_hides_previous_hostname_suggestion_when_never_approved(client):
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")

    resp = client.get("/admin/approve/aa:bb:cc:dd:ee:ff", headers=AUTH_HEADERS)

    assert resp.status_code == 200
    assert "Zuvor installiert als".encode() not in resp.data


def test_approve_form_shows_hostname_hint(client):
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")

    resp = client.get("/admin/approve/aa:bb:cc:dd:ee:ff", headers=AUTH_HEADERS)

    assert b"Kleinbuchstaben, Ziffern, Bindestriche" in resp.data


def test_dashboard_has_autorefresh_script(client):
    resp = client.get("/admin/", headers=AUTH_HEADERS)

    assert b"setInterval" in resp.data
    assert b"12000" in resp.data


def test_help_page_requires_auth(client):
    resp = client.get("/admin/help")
    assert resp.status_code == 401


def test_help_page_shows_workflow_and_hostname_rule(client):
    resp = client.get("/admin/help", headers=AUTH_HEADERS)

    assert resp.status_code == 200
    assert b"Discovery-Modus" in resp.data
    assert b"Kleinbuchstaben, Ziffern, Bindestriche" in resp.data


def test_dashboard_shows_help_nav_link(client):
    resp = client.get("/admin/", headers=AUTH_HEADERS)

    assert b"/admin/help" in resp.data


def test_approve_submit_hostname_error_includes_full_rule(client):
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")

    resp = client.post(
        "/admin/approve/aa:bb:cc:dd:ee:ff",
        data={"hostname": "-invalid", "profile": "Debian 13 + EXT4 System"},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 400
    assert b"max. 63 Zeichen) und ein Profil ausw\xc3\xa4hlen." in resp.data


def test_dashboard_shows_theme_and_fontsize_controls(client):
    resp = client.get("/admin/", headers=AUTH_HEADERS)

    assert resp.status_code == 200
    assert b'id="theme-toggle"' in resp.data
    assert b'class="fontsize-group"' in resp.data
    assert b'data-scale="125"' in resp.data
    assert b"fai-discovery-theme" in resp.data


def test_discovery_form_requires_auth(client):
    resp = client.get("/admin/discovery")
    assert resp.status_code == 401


def test_discovery_submit_requires_auth(client):
    resp = client.post("/admin/discovery", data={"macs": "aa:bb:cc:dd:ee:ff"})
    assert resp.status_code == 401


def test_discovery_form_shows_input(client):
    resp = client.get("/admin/discovery", headers=AUTH_HEADERS)

    assert resp.status_code == 200
    assert b'name="macs"' in resp.data


def test_discovery_submit_empty_input_shows_form_error(client, monkeypatch):
    def fail_if_called(mac, runner=None):
        raise AssertionError("run_fai_chboot_discovery must not be called for empty input")

    monkeypatch.setattr(chboot, "run_fai_chboot_discovery", fail_if_called)

    resp = client.post("/admin/discovery", data={"macs": "   ,  ,  "}, headers=AUTH_HEADERS)

    assert resp.status_code == 400
    assert b"mindestens eine MAC-Adresse" in resp.data


def test_discovery_submit_calls_discovery_for_each_valid_mac(client, monkeypatch):
    calls = []

    def fake_discovery(mac, runner=None):
        calls.append(mac)
        return True, "discovery mode set"

    monkeypatch.setattr(chboot, "run_fai_chboot_discovery", fake_discovery)

    resp = client.post(
        "/admin/discovery",
        data={"macs": "AA:BB:CC:DD:EE:FF, aa:bb:cc:c4:29:99"},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200
    assert calls == ["aa:bb:cc:dd:ee:ff", "aa:bb:cc:c4:29:99"]
    assert b"aa:bb:cc:dd:ee:ff" in resp.data
    assert b"aa:bb:cc:c4:29:99" in resp.data


def test_discovery_submit_mixed_valid_and_invalid_mac(client, monkeypatch):
    calls = []

    def fake_discovery(mac, runner=None):
        calls.append(mac)
        return True, "discovery mode set"

    monkeypatch.setattr(chboot, "run_fai_chboot_discovery", fake_discovery)

    resp = client.post(
        "/admin/discovery",
        data={"macs": "aa:bb:cc:dd:ee:ff, not-a-mac"},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200
    assert calls == ["aa:bb:cc:dd:ee:ff"]
    assert b"ung\xc3\xbcltiges MAC-Format" in resp.data


def test_discovery_submit_deduplicates_repeated_mac(client, monkeypatch):
    calls = []

    def fake_discovery(mac, runner=None):
        calls.append(mac)
        return True, "discovery mode set"

    monkeypatch.setattr(chboot, "run_fai_chboot_discovery", fake_discovery)

    resp = client.post(
        "/admin/discovery",
        data={"macs": "aa:bb:cc:dd:ee:ff, AA:BB:CC:DD:EE:FF"},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200
    assert calls == ["aa:bb:cc:dd:ee:ff"]


def test_discovery_submit_reports_failure_without_blocking_others(client, monkeypatch):
    def fake_discovery(mac, runner=None):
        if mac == "aa:bb:cc:dd:ee:ff":
            return False, "fai-chboot: unknown host"
        return True, "discovery mode set"

    monkeypatch.setattr(chboot, "run_fai_chboot_discovery", fake_discovery)

    resp = client.post(
        "/admin/discovery",
        data={"macs": "aa:bb:cc:dd:ee:ff, aa:bb:cc:c4:29:99"},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200
    assert b"unknown host" in resp.data
    assert b"aa:bb:cc:c4:29:99" in resp.data


def test_discovery_submit_rejects_already_registered_mac(client, monkeypatch):
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")

    def fail_if_called(mac, runner=None):
        raise AssertionError("run_fai_chboot_discovery must not be called for an already-registered MAC")

    monkeypatch.setattr(chboot, "run_fai_chboot_discovery", fail_if_called)

    resp = client.post(
        "/admin/discovery",
        data={"macs": "aa:bb:cc:dd:ee:ff"},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200
    assert b"bereits registriert" in resp.data


def test_discovery_submit_allows_discarded_mac(client, monkeypatch):
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")
    storage.discard_waiting_device("aa:bb:cc:dd:ee:ff")

    calls = []
    monkeypatch.setattr(
        chboot,
        "run_fai_chboot_discovery",
        lambda mac, runner=None: calls.append(mac) or (True, "discovery mode set"),
    )

    resp = client.post(
        "/admin/discovery",
        data={"macs": "aa:bb:cc:dd:ee:ff"},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 200
    assert calls == ["aa:bb:cc:dd:ee:ff"]
    assert b"bereits registriert" not in resp.data


def test_dashboard_shows_discovery_nav_link(client):
    resp = client.get("/admin/", headers=AUTH_HEADERS)

    assert b"/admin/discovery" in resp.data


def test_history_filters_by_query_param(client):
    storage.register_device("aa:aa:aa:aa:aa:aa", "1.1.1.1", "cpu", "1", "1G")
    storage.register_device("bb:bb:bb:bb:bb:bb", "2.2.2.2", "cpu", "1", "1G")
    storage.approve_device("aa:aa:aa:aa:aa:aa", "vmtest01", "FAIBASE", "admin")
    storage.approve_device("bb:bb:bb:bb:bb:bb", "vmweb02", "FAIBASE", "alice")

    resp = client.get("/admin/history?q=test01", headers=AUTH_HEADERS)

    assert resp.status_code == 200
    assert b"vmtest01" in resp.data
    assert b"vmweb02" not in resp.data


def test_history_without_query_shows_all(client):
    storage.register_device("aa:aa:aa:aa:aa:aa", "1.1.1.1", "cpu", "1", "1G")
    storage.approve_device("aa:aa:aa:aa:aa:aa", "vmtest01", "FAIBASE", "admin")

    resp = client.get("/admin/history", headers=AUTH_HEADERS)

    assert resp.status_code == 200
    assert b"vmtest01" in resp.data


def test_history_shows_search_form_with_value_prefilled(client):
    resp = client.get("/admin/history?q=test01", headers=AUTH_HEADERS)

    assert resp.status_code == 200
    assert b'name="q"' in resp.data
    assert b'value="test01"' in resp.data


def test_history_no_match_shows_specific_empty_message(client):
    storage.register_device("aa:aa:aa:aa:aa:aa", "1.1.1.1", "cpu", "1", "1G")
    storage.approve_device("aa:aa:aa:aa:aa:aa", "vmtest01", "FAIBASE", "admin")

    resp = client.get("/admin/history?q=does-not-exist", headers=AUTH_HEADERS)

    assert resp.status_code == 200
    assert "Keine Treffer für".encode() in resp.data
    assert b"does-not-exist" in resp.data


def test_history_escapes_query_in_output(client):
    resp = client.get(
        '/admin/history?q=%22%3E%3Cscript%3Ealert(1)%3C/script%3E',
        headers=AUTH_HEADERS,
    )

    assert b"<script>alert(1)</script>" not in resp.data


def test_history_empty_db_without_query_shows_generic_empty_message(client):
    resp = client.get("/admin/history", headers=AUTH_HEADERS)

    assert resp.status_code == 200
    assert b"Noch keine Freigaben." in resp.data


def test_discard_removes_waiting_entry_and_redirects(client, monkeypatch):
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")
    monkeypatch.setattr(chboot, "run_fai_chboot_disable", lambda mac, runner=None: (True, "disabled"))

    resp = client.post("/admin/discard/aa:bb:cc:dd:ee:ff", headers=AUTH_HEADERS)

    assert resp.status_code == 302
    device = storage.get_device("aa:bb:cc:dd:ee:ff")
    assert device is not None
    assert device["status"] == "discarded"
    assert storage.list_waiting_devices() == []


def test_discard_chboot_failure_keeps_entry_and_returns_502(client, monkeypatch):
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")
    monkeypatch.setattr(chboot, "run_fai_chboot_disable", lambda mac, runner=None: (False, "fai-chboot: boom"))

    resp = client.post("/admin/discard/aa:bb:cc:dd:ee:ff", headers=AUTH_HEADERS)

    assert resp.status_code == 502
    assert storage.get_device("aa:bb:cc:dd:ee:ff") is not None


def test_discard_invalid_mac_returns_400(client):
    resp = client.post("/admin/discard/not-a-mac", headers=AUTH_HEADERS)
    assert resp.status_code == 400


def test_discard_unknown_mac_returns_404(client):
    resp = client.post("/admin/discard/11:22:33:44:55:66", headers=AUTH_HEADERS)
    assert resp.status_code == 404


def test_discard_reboot_entry_returns_404(client):
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")
    storage.approve_device("aa:bb:cc:dd:ee:ff", "vmtest01", "FAIBASE", "admin")

    resp = client.post("/admin/discard/aa:bb:cc:dd:ee:ff", headers=AUTH_HEADERS)

    assert resp.status_code == 404
    assert storage.get_device("aa:bb:cc:dd:ee:ff") is not None


def test_discard_requires_auth(client):
    resp = client.post("/admin/discard/aa:bb:cc:dd:ee:ff")
    assert resp.status_code == 401


def test_dashboard_shows_discard_button(client):
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")

    resp = client.get("/admin/", headers=AUTH_HEADERS)

    assert resp.status_code == 200
    assert "Stop/Löschen".encode() in resp.data
    assert b'action="/admin/discard/aa:bb:cc:dd:ee:ff"' in resp.data


def test_approve_form_shows_type_and_location_prefixes(client, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_TYPE_PREFIXES", "NB:Notebook,DT:Desktop")
    monkeypatch.setenv("FAI_DISCOVERY_LOCATION_PREFIXES", "K:Köln,B:Berlin")
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")

    resp = client.get("/admin/approve/aa:bb:cc:dd:ee:ff", headers=AUTH_HEADERS)

    assert resp.status_code == 200
    assert "NB – Notebook".encode() in resp.data
    assert "K – Köln".encode() in resp.data
    assert b'value="nb"' in resp.data
    assert b'value="k"' in resp.data


def test_approve_form_hides_prefix_block_when_not_configured(client, monkeypatch):
    monkeypatch.delenv("FAI_DISCOVERY_TYPE_PREFIXES", raising=False)
    monkeypatch.delenv("FAI_DISCOVERY_LOCATION_PREFIXES", raising=False)
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")

    resp = client.get("/admin/approve/aa:bb:cc:dd:ee:ff", headers=AUTH_HEADERS)

    assert resp.status_code == 200
    assert "Hilfen für den Hostnamen".encode() not in resp.data


def test_approve_form_shows_serial_and_uuid_suggestion_buttons(client, monkeypatch):
    monkeypatch.delenv("FAI_DISCOVERY_TYPE_PREFIXES", raising=False)
    monkeypatch.delenv("FAI_DISCOVERY_LOCATION_PREFIXES", raising=False)
    storage.register_device(
        "aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G",
        uuid="a1b2c3d4-e5f6-7890-abcd-ef1234567890", serial="SN 4471 XK",
    )

    resp = client.get("/admin/approve/aa:bb:cc:dd:ee:ff", headers=AUTH_HEADERS)

    assert resp.status_code == 200
    assert "Serial übernehmen: sn-4471-xk".encode() in resp.data
    assert "UUID übernehmen: a1b2c3d4".encode() in resp.data


def test_approve_form_hides_serial_suggestion_for_placeholder_value(client, monkeypatch):
    monkeypatch.delenv("FAI_DISCOVERY_TYPE_PREFIXES", raising=False)
    monkeypatch.delenv("FAI_DISCOVERY_LOCATION_PREFIXES", raising=False)
    storage.register_device(
        "aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G",
        uuid="", serial="Not Specified",
    )

    resp = client.get("/admin/approve/aa:bb:cc:dd:ee:ff", headers=AUTH_HEADERS)

    assert resp.status_code == 200
    assert "Serial übernehmen".encode() not in resp.data
    assert "UUID übernehmen".encode() not in resp.data


def test_approve_form_shows_raw_serial_and_uuid_in_device_meta(client):
    storage.register_device(
        "aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G",
        uuid="a1b2c3d4-e5f6-7890-abcd-ef1234567890", serial="SN 4471 XK",
    )

    resp = client.get("/admin/approve/aa:bb:cc:dd:ee:ff", headers=AUTH_HEADERS)

    assert resp.status_code == 200
    assert b"SN 4471 XK" in resp.data
    assert b"a1b2c3d4-e5f6-7890-abcd-ef1234567890" in resp.data


def test_help_page_shows_hostname_assist_section(client):
    resp = client.get("/admin/help", headers=AUTH_HEADERS)

    assert resp.status_code == 200
    assert "Hilfen für den Hostnamen".encode() in resp.data
    assert b"FAI_DISCOVERY_TYPE_PREFIXES" in resp.data
    assert b"FAI_DISCOVERY_LOCATION_PREFIXES" in resp.data


def test_approve_submit_appends_efi_classes_when_firmware_uefi(client, monkeypatch, tmp_path):
    monkeypatch.setenv("FAI_DISCOVERY_DISK_CONFIG_DIR", str(tmp_path))
    (tmp_path / "FAIBASE_EFI").write_text("dummy")
    storage.register_device(
        "aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G", firmware="uefi",
    )

    calls = []
    monkeypatch.setattr(
        chboot, "run_fai_chboot",
        lambda mac, classes, reboot=False, verbose=True: (calls.append(classes) or True, "ok"),
    )

    resp = client.post(
        "/admin/approve/aa:bb:cc:dd:ee:ff",
        data={"hostname": "vmtest01", "profile": "Debian 13 + EXT4 System"},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 302
    assert calls == ["INSTALL FAIBASE DEBIAN STEP SALT SECURE TRIXIE64 FAIBASE_EFI"]
    device = storage.get_device("aa:bb:cc:dd:ee:ff")
    assert device["classes"] == "INSTALL FAIBASE DEBIAN STEP SALT SECURE TRIXIE64 FAIBASE_EFI"


def test_approve_submit_does_not_append_efi_classes_when_firmware_bios(client, monkeypatch, tmp_path):
    monkeypatch.setenv("FAI_DISCOVERY_DISK_CONFIG_DIR", str(tmp_path))
    (tmp_path / "FAIBASE_EFI").write_text("dummy")
    storage.register_device(
        "aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G", firmware="bios",
    )

    calls = []
    monkeypatch.setattr(
        chboot, "run_fai_chboot",
        lambda mac, classes, reboot=False, verbose=True: (calls.append(classes) or True, "ok"),
    )

    resp = client.post(
        "/admin/approve/aa:bb:cc:dd:ee:ff",
        data={"hostname": "vmtest01", "profile": "Debian 13 + EXT4 System"},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 302
    assert calls == ["INSTALL FAIBASE DEBIAN STEP SALT SECURE TRIXIE64"]


def test_approve_form_shows_firmware_in_device_meta(client):
    storage.register_device(
        "aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G", firmware="uefi",
    )

    resp = client.get("/admin/approve/aa:bb:cc:dd:ee:ff", headers=AUTH_HEADERS)

    assert resp.status_code == 200
    assert b"Firmware UEFI" in resp.data


def test_approve_form_hides_firmware_when_not_set(client):
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")

    resp = client.get("/admin/approve/aa:bb:cc:dd:ee:ff", headers=AUTH_HEADERS)

    assert resp.status_code == 200
    assert "· Firmware".encode() not in resp.data


def test_help_page_shows_uefi_section(client):
    resp = client.get("/admin/help", headers=AUTH_HEADERS)

    assert resp.status_code == 200
    assert "UEFI".encode() in resp.data
    assert b"FAI_DISCOVERY_DISK_CONFIG_DIR" in resp.data


def test_help_page_shows_history_reinstall_section(client):
    resp = client.get("/admin/help", headers=AUTH_HEADERS)

    assert resp.status_code == 200
    assert "Neuinstallation".encode() in resp.data


def test_progress_requires_auth(client):
    resp = client.get("/admin/progress")
    assert resp.status_code == 401


def test_progress_shows_empty_state(client, monkeypatch):
    monkeypatch.setattr(progress, "list_active_installs", lambda: [])
    resp = client.get("/admin/progress", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    assert "hostA" not in resp.get_data(as_text=True)


def test_progress_renders_running_host_with_tasks(client, monkeypatch):
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
    resp = client.get("/admin/progress", headers=AUTH_HEADERS)
    body = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "hostA" in body
    assert "partition" in body
    assert "extrbase" in body
