import json

import pytest
from werkzeug.security import generate_password_hash

import app as app_module
import chboot
import profiles
import storage

AUTH_HEADERS = {"Authorization": "Basic " + __import__("base64").b64encode(b"admin:s3cret").decode()}

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


def test_base_html_lang_attribute_follows_language_env(client, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_LANGUAGE", "en")
    resp = client.get("/admin/", headers=AUTH_HEADERS)
    assert b'<html lang="en">' in resp.data

    monkeypatch.delenv("FAI_DISCOVERY_LANGUAGE", raising=False)
    resp = client.get("/admin/", headers=AUTH_HEADERS)
    assert b'<html lang="de">' in resp.data


def test_nav_labels_translated_to_english(client, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_LANGUAGE", "en")
    resp = client.get("/admin/", headers=AUTH_HEADERS)
    assert b">History<" in resp.data
    assert b">Help<" in resp.data


def test_dashboard_translated_to_english(client, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_LANGUAGE", "en")
    resp = client.get("/admin/", headers=AUTH_HEADERS)
    assert b"Waiting devices" in resp.data
    assert b"No device is currently waiting for approval." in resp.data


def test_dashboard_discard_confirm_translated_and_interpolated(client, monkeypatch):
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")
    monkeypatch.setenv("FAI_DISCOVERY_LANGUAGE", "en")

    resp = client.get("/admin/", headers=AUTH_HEADERS)

    assert b"Really stop/delete device aa:bb:cc:dd:ee:ff?" in resp.data


def test_history_translated_to_english(client, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_LANGUAGE", "en")
    resp = client.get("/admin/history", headers=AUTH_HEADERS)
    assert b"Approval history" in resp.data
    assert b"No approvals yet." in resp.data


def test_discovery_form_translated_to_english(client, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_LANGUAGE", "en")
    resp = client.get("/admin/discovery", headers=AUTH_HEADERS)
    assert b"Trigger discovery mode" in resp.data
    assert b"Start discovery" in resp.data


def test_discovery_submit_error_translated_to_english(client, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_LANGUAGE", "en")
    resp = client.post("/admin/discovery", data={"macs": "   ,  ,  "}, headers=AUTH_HEADERS)
    assert resp.status_code == 400
    assert b"Please enter at least one MAC address." in resp.data


def test_approve_form_translated_to_english(client, monkeypatch):
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")
    monkeypatch.setenv("FAI_DISCOVERY_LANGUAGE", "en")

    resp = client.get("/admin/approve/aa:bb:cc:dd:ee:ff", headers=AUTH_HEADERS)

    assert resp.status_code == 200
    assert b"Approve device: aa:bb:cc:dd:ee:ff" in resp.data
    assert b"Target profile" in resp.data
    assert b"Reboot automatically after installation" in resp.data
    assert b"Verbose installation output" in resp.data
    assert b"Only affects the FAI installer" in resp.data


def test_approve_submit_invalid_form_error_translated_to_english(client, monkeypatch):
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")
    monkeypatch.setenv("FAI_DISCOVERY_LANGUAGE", "en")

    resp = client.post(
        "/admin/approve/aa:bb:cc:dd:ee:ff",
        data={"hostname": "-invalid", "profile": "Debian 13 + EXT4 System"},
        headers=AUTH_HEADERS,
    )

    assert resp.status_code == 400
    assert b"Please enter a valid hostname" in resp.data


def test_approve_form_profile_error_translated_to_english(client, monkeypatch):
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")
    monkeypatch.setenv("FAI_DISCOVERY_LANGUAGE", "en")

    def raise_oserror(path):
        raise OSError("nope")

    monkeypatch.setattr(profiles, "load_profiles", raise_oserror)

    resp = client.get("/admin/approve/aa:bb:cc:dd:ee:ff", headers=AUTH_HEADERS)

    assert resp.status_code == 200
    assert b"Profile file not readable" in resp.data


def test_help_page_translated_to_english(client, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_LANGUAGE", "en")
    resp = client.get("/admin/help", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    assert b"Automatic UEFI detection" in resp.data
    assert b'<a href="/admin/">dashboard</a>' in resp.data


def test_help_page_documents_language_variable(client, monkeypatch):
    resp = client.get("/admin/help", headers=AUTH_HEADERS)
    assert resp.status_code == 200
    assert b"FAI_DISCOVERY_LANGUAGE" in resp.data


def test_history_delete_invalid_mac_error_translated_to_english(client, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_LANGUAGE", "en")
    resp = client.post("/admin/history/not-a-mac/delete", headers=AUTH_HEADERS)
    assert resp.status_code == 400
    assert b"Invalid MAC address" in resp.data


def test_discard_unknown_device_error_translated_to_english(client, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_LANGUAGE", "en")
    resp = client.post("/admin/discard/11:22:33:44:55:66", headers=AUTH_HEADERS)
    assert resp.status_code == 404
    assert b"Unknown or non-discardable device" in resp.data


def test_invalid_language_value_falls_back_to_german(client, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_LANGUAGE", "fr")
    resp = client.get("/admin/", headers=AUTH_HEADERS)
    assert b"Wartende Ger\xc3\xa4te" in resp.data
