import json
import base64

from flask import Flask
from werkzeug.security import generate_password_hash

import auth


def test_load_admins_reads_json(tmp_path):
    admins_file = tmp_path / "admins.json"
    admins_file.write_text(json.dumps({"admin": "hash1"}))

    assert auth.load_admins(admins_file) == {"admin": "hash1"}


def test_load_admins_missing_file_returns_empty_dict(tmp_path):
    missing = tmp_path / "does-not-exist.json"
    assert auth.load_admins(missing) == {}


def test_load_admins_malformed_json_returns_empty_dict(tmp_path):
    admins_file = tmp_path / "admins.json"
    admins_file.write_text("{not valid json,,,")

    assert auth.load_admins(admins_file) == {}


def test_current_admin_malformed_admins_file_returns_none_not_500(tmp_path, monkeypatch):
    # A broken admins.json must fail closed (None -> 401 via require_auth),
    # not raise json.JSONDecodeError up into the request handler (500).
    admins_file = tmp_path / "admins.json"
    admins_file.write_text("{not valid json,,,")
    monkeypatch.setenv("FAI_DISCOVERY_ADMINS_FILE", str(admins_file))

    app = Flask(__name__)
    credentials = base64.b64encode(b"admin:s3cret").decode("utf-8")
    with app.test_request_context(
        headers={"Authorization": f"Basic {credentials}"}
    ):
        assert auth.current_admin() is None


def test_verify_credentials_correct_password():
    admins = {"admin": generate_password_hash("s3cret")}
    assert auth.verify_credentials("admin", "s3cret", admins) is True


def test_verify_credentials_wrong_password():
    admins = {"admin": generate_password_hash("s3cret")}
    assert auth.verify_credentials("admin", "wrong", admins) is False


def test_verify_credentials_unknown_user():
    admins = {"admin": generate_password_hash("s3cret")}
    assert auth.verify_credentials("alice", "s3cret", admins) is False


def test_verify_credentials_empty_username_or_password():
    admins = {"admin": generate_password_hash("s3cret")}
    assert auth.verify_credentials("", "s3cret", admins) is False
    assert auth.verify_credentials("admin", "", admins) is False


def test_admins_path_uses_env_var(monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_ADMINS_FILE", "/tmp/custom-admins.json")
    assert auth.admins_path() == "/tmp/custom-admins.json"


def test_admins_path_default(monkeypatch):
    monkeypatch.delenv("FAI_DISCOVERY_ADMINS_FILE", raising=False)
    assert auth.admins_path() == "/etc/fai-discovery/admins.json"


# Tests for current_admin() and require_auth (require Flask request context)

def test_current_admin_no_auth_header():
    app = Flask(__name__)
    with app.test_request_context():
        assert auth.current_admin() is None


def test_current_admin_with_valid_credentials(tmp_path, monkeypatch):
    # Setup: Create a temp admins file
    admins_file = tmp_path / "admins.json"
    admins_file.write_text(json.dumps({"admin": generate_password_hash("s3cret")}))
    monkeypatch.setenv("FAI_DISCOVERY_ADMINS_FILE", str(admins_file))

    # Create a Flask app and test with valid credentials
    app = Flask(__name__)
    credentials = base64.b64encode(b"admin:s3cret").decode("utf-8")
    with app.test_request_context(
        headers={"Authorization": f"Basic {credentials}"}
    ):
        assert auth.current_admin() == "admin"


def test_current_admin_with_invalid_credentials(tmp_path, monkeypatch):
    # Setup: Create a temp admins file
    admins_file = tmp_path / "admins.json"
    admins_file.write_text(json.dumps({"admin": generate_password_hash("s3cret")}))
    monkeypatch.setenv("FAI_DISCOVERY_ADMINS_FILE", str(admins_file))

    # Create a Flask app and test with invalid credentials
    app = Flask(__name__)
    credentials = base64.b64encode(b"admin:wrong").decode("utf-8")
    with app.test_request_context(
        headers={"Authorization": f"Basic {credentials}"}
    ):
        assert auth.current_admin() is None


def test_require_auth_no_credentials():
    app = Flask(__name__)

    @auth.require_auth
    def protected_view(username):
        return f"Hello {username}"

    with app.test_request_context():
        result = protected_view()
        assert result[1] == 401  # Status code
        assert "WWW-Authenticate" in result[2]  # Headers dict
        assert 'Basic realm="fai-discovery"' in result[2]["WWW-Authenticate"]


def test_require_auth_valid_credentials_passes_username(tmp_path, monkeypatch):
    # Setup: Create a temp admins file
    admins_file = tmp_path / "admins.json"
    admins_file.write_text(json.dumps({"admin": generate_password_hash("s3cret")}))
    monkeypatch.setenv("FAI_DISCOVERY_ADMINS_FILE", str(admins_file))

    # Create a Flask app with a protected route
    app = Flask(__name__)

    @auth.require_auth
    def protected_view(username):
        return f"Hello {username}", 200

    credentials = base64.b64encode(b"admin:s3cret").decode("utf-8")
    with app.test_request_context(
        headers={"Authorization": f"Basic {credentials}"}
    ):
        result = protected_view()
        assert result[0] == "Hello admin"
        assert result[1] == 200
