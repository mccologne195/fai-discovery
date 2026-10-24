import json
import os
from functools import wraps
from pathlib import Path
from urllib.parse import urlsplit

from flask import request
from werkzeug.security import check_password_hash

ADMINS_FILE_ENV = "FAI_DISCOVERY_ADMINS_FILE"
DEFAULT_ADMINS_FILE = "/etc/fai-discovery/admins.json"


def admins_path():
    return os.environ.get(ADMINS_FILE_ENV, DEFAULT_ADMINS_FILE)


def load_admins(path):
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def verify_credentials(username, password, admins):
    if not username or not password:
        return False
    stored_hash = admins.get(username)
    if not stored_hash:
        return False
    return check_password_hash(stored_hash, password)


def current_admin():
    auth_header = request.authorization
    if auth_header is None:
        return None
    admins = load_admins(admins_path())
    if verify_credentials(auth_header.username, auth_header.password, admins):
        return auth_header.username
    return None


def foreign_origin():
    # Schutz vor fremden Formularen (CSRF): der Browser schickt gespeicherte
    # Basic-Auth-Zugangsdaten auch bei Formularen fremder Webseiten mit, setzt
    # bei jedem POST aber einen Origin-Header. Passt dessen Host nicht zum
    # Host-Header der Anfrage, kommt sie von einer anderen Seite. Ohne Origin
    # ist der Aufrufer kein Browser (curl, fai-discovery-approve.sh) und kann
    # nicht fremdgesteuert sein. Nur der Host zaehlt, nicht das Schema: hinter
    # einem TLS-Proxy (Caddy) ist Origin https://, die Anfrage hier aber http.
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return False
    origin = request.headers.get("Origin")
    if origin is None:
        return False
    return urlsplit(origin).netloc.lower() != request.host.lower()


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if foreign_origin():
            return "Anfrage von fremder Seite abgelehnt", 403
        username = current_admin()
        if username is None:
            return (
                "Login erforderlich",
                401,
                {"WWW-Authenticate": 'Basic realm="fai-discovery"'},
            )
        return view(username, *args, **kwargs)

    return wrapped
