import ipaddress
import json
import os
from functools import wraps
from pathlib import Path
from urllib.parse import urlsplit

from flask import redirect, request
from werkzeug.security import check_password_hash

ADMINS_FILE_ENV = "FAI_DISCOVERY_ADMINS_FILE"
DEFAULT_ADMINS_FILE = "/etc/fai-discovery/admins.json"
HTTPS_ONLY_ENV = "FAI_DISCOVERY_ADMIN_HTTPS_ONLY"
TLS_HOST_ENV = "FAI_DISCOVERY_TLS_HOST"
TLS_PORT_ENV = "FAI_DISCOVERY_TLS_PORT"


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


def https_only_redirect():
    # FAI_DISCOVERY_ADMIN_HTTPS_ONLY=true: Caddy (fai-discovery-tls) laeuft auf
    # demselben Host und spricht die Webkonsole ueber Loopback an. Alles andere
    # kam unverschluesselt direkt auf 8080 - umleiten bzw. ablehnen, BEVOR
    # Basic Auth abgefragt wird, damit der Browser das Passwort nie im Klartext
    # schickt. X-Forwarded-For wird bewusst nicht ausgewertet (kein ProxyFix),
    # remote_addr laesst sich von aussen also nicht faelschen.
    if os.environ.get(HTTPS_ONLY_ENV, "").strip().lower() != "true":
        return None
    try:
        if ipaddress.ip_address(request.remote_addr or "").is_loopback:
            return None
    except ValueError:
        pass
    if request.method not in ("GET", "HEAD"):
        return "Nur ueber HTTPS erreichbar", 403
    host = os.environ.get(TLS_HOST_ENV, "").strip() or request.host.split(":")[0]
    port = os.environ.get(TLS_PORT_ENV, "").strip()
    suffix = f":{port}" if port and port != "443" else ""
    return redirect(f"https://{host}{suffix}{request.full_path.rstrip('?')}", code=308)


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        response = https_only_redirect()
        if response is not None:
            return response
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
