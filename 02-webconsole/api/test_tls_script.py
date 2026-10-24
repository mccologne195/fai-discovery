import hashlib
import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "bin" / "fai-discovery-tls"
MARKER = "# fai-discovery-tls: managed file, do not edit"
DEBIAN_DEFAULT = ":80 {\n\troot * /usr/share/caddy\n\tfile_server\n}\n"

# Stub fuer caddy: "validate" schlaegt fehl, wenn FAKE_CADDY_FAIL=1.
FAKE_CADDY = """#!/bin/bash
echo "caddy $*" >> "$FAKE_CALLS_LOG"
if [ "$1" = validate ] && [ "${FAKE_CADDY_FAIL:-0}" = 1 ]; then echo "Error: adapting config" >&2; exit 1; fi
exit 0
"""
FAKE_SYSTEMCTL = """#!/bin/bash
echo "systemctl $*" >> "$FAKE_CALLS_LOG"
exit 0
"""
# dpkg-query liefert die Conffile-Pruefsumme des Debian-Default-Caddyfile.
FAKE_DPKG_QUERY = """#!/bin/bash
printf ' /etc/caddy/Caddyfile %s\\n' "$FAKE_DEFAULT_MD5"
"""


class Env:
    def __init__(self, root: Path):
        self.root = root
        self.site_conf = root / "site.conf"
        self.caddyfile = root / "caddy" / "Caddyfile"
        self.caddyfile.parent.mkdir()
        self.calls = root / "calls.log"
        self.bin = root / "bin"
        self.bin.mkdir()
        for name, body in {"caddy": FAKE_CADDY, "systemctl": FAKE_SYSTEMCTL, "dpkg-query": FAKE_DPKG_QUERY}.items():
            (self.bin / name).write_text(body)
            (self.bin / name).chmod(0o755)
        self.root_ca = root / "root_ca.crt"
        self.root_ca.write_text("-----BEGIN CERTIFICATE-----\n")

    def write_site(self, text: str) -> None:
        self.site_conf.write_text(text)

    def run(self, caddy=None, **extra) -> subprocess.CompletedProcess:
        env = {
            "PATH": os.environ["PATH"],
            "FAI_DISCOVERY_SITE_CONF": str(self.site_conf),
            "FAI_DISCOVERY_CADDYFILE": str(self.caddyfile),
            "FAI_DISCOVERY_CADDY": caddy or str(self.bin / "caddy"),
            "FAI_DISCOVERY_SYSTEMCTL": str(self.bin / "systemctl"),
            "FAI_DISCOVERY_DPKG_QUERY": str(self.bin / "dpkg-query"),
            "FAI_DISCOVERY_CADDY_OWNER": "",
            "FAKE_CALLS_LOG": str(self.calls),
            "FAKE_DEFAULT_MD5": hashlib.md5(DEBIAN_DEFAULT.encode()).hexdigest(),
        }
        env.update(extra)
        return subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True)

    def calls_list(self):
        return self.calls.read_text().splitlines() if self.calls.exists() else []


@pytest.fixture
def env(tmp_path):
    return Env(tmp_path)


def acme_site(env, extra=""):
    return (
        "FAI_DISCOVERY_TLS_MODE=acme\n"
        "FAI_DISCOVERY_TLS_HOST=fai.example.org\n"
        "FAI_DISCOVERY_TLS_ACME_CA=https://ca.example.org:9000/acme/acme/directory\n"
        f"FAI_DISCOVERY_TLS_ACME_CA_ROOT={env.root_ca}\n" + extra
    )


def test_acme_mode_writes_caddyfile_and_reloads(env):
    env.write_site(acme_site(env))

    result = env.run()

    assert result.returncode == 0, result.stderr
    text = env.caddyfile.read_text()
    assert text.splitlines()[0] == MARKER
    assert "auto_https disable_redirects" in text
    assert "https://fai.example.org {" in text
    assert "dir https://ca.example.org:9000/acme/acme/directory" in text
    assert f"trusted_roots {env.root_ca}" in text
    assert "disable_http_challenge" in text
    assert "reverse_proxy 127.0.0.1:8080" in text
    calls = env.calls_list()
    assert any(c.startswith("caddy validate") for c in calls)
    assert "systemctl enable caddy" in calls
    assert "systemctl reload-or-restart caddy" in calls


def test_acme_mode_can_use_http01_instead_of_tls_alpn(env):
    # Manche ACME-CAs (z.B. step-ca mit eingeschraenkter challenges-Liste)
    # bieten kein tls-alpn-01 an - dann http-01, wofuer Port 80 frei sein muss.
    env.write_site(acme_site(env, "FAI_DISCOVERY_TLS_ACME_CHALLENGE=http-01\n"))

    result = env.run()

    assert result.returncode == 0, result.stderr
    text = env.caddyfile.read_text()
    assert "disable_tlsalpn_challenge" in text
    assert "disable_http_challenge" not in text


def test_acme_mode_without_ca_root_uses_system_trust(env):
    env.write_site(
        "FAI_DISCOVERY_TLS_MODE=acme\n"
        "FAI_DISCOVERY_TLS_HOST=fai.example.org\n"
        "FAI_DISCOVERY_TLS_ACME_CA=https://ca.example.org/acme/acme/directory\n"
    )

    result = env.run()

    assert result.returncode == 0, result.stderr
    assert "trusted_roots" not in env.caddyfile.read_text()


def test_internal_mode_with_extra_names(env):
    env.write_site(
        "FAI_DISCOVERY_TLS_MODE=internal\n"
        "FAI_DISCOVERY_TLS_HOST=fai.example.org\n"
        'FAI_DISCOVERY_TLS_EXTRA_NAMES="192.168.77.2, fai"\n'
    )

    result = env.run()

    assert result.returncode == 0, result.stderr
    text = env.caddyfile.read_text()
    assert "https://fai.example.org, https://192.168.77.2, https://fai {" in text
    assert "tls internal" in text
    assert "skip_install_trust" in text
    assert "issuer acme" not in text


def test_files_mode_uses_given_certificate(env):
    cert = env.root / "fai.crt"
    key = env.root / "fai.key"
    cert.write_text("cert")
    key.write_text("key")
    env.write_site(
        "FAI_DISCOVERY_TLS_MODE=files\n"
        "FAI_DISCOVERY_TLS_HOST=fai.example.org\n"
        f"FAI_DISCOVERY_TLS_CERT_FILE={cert}\n"
        f"FAI_DISCOVERY_TLS_KEY_FILE={key}\n"
    )

    result = env.run()

    assert result.returncode == 0, result.stderr
    assert f"tls {cert} {key}" in env.caddyfile.read_text()


def test_files_mode_missing_key_changes_nothing(env):
    cert = env.root / "fai.crt"
    cert.write_text("cert")
    env.write_site(
        "FAI_DISCOVERY_TLS_MODE=files\n"
        "FAI_DISCOVERY_TLS_HOST=fai.example.org\n"
        f"FAI_DISCOVERY_TLS_CERT_FILE={cert}\n"
        f"FAI_DISCOVERY_TLS_KEY_FILE={env.root / 'missing.key'}\n"
    )

    result = env.run()

    assert result.returncode != 0
    assert "missing.key" in result.stderr
    assert not env.caddyfile.exists()
    assert env.calls_list() == []


def test_custom_port(env):
    env.write_site(acme_site(env, "FAI_DISCOVERY_TLS_PORT=8443\n"))

    result = env.run()

    assert result.returncode == 0, result.stderr
    assert "https://fai.example.org:8443 {" in env.caddyfile.read_text()


@pytest.mark.parametrize(
    "line",
    [
        "FAI_DISCOVERY_TLS_HOST=fai.example.org {",
        "FAI_DISCOVERY_TLS_HOST=fai",
        "FAI_DISCOVERY_TLS_EXTRA_NAMES=ok.example.org,bad name",
        "FAI_DISCOVERY_TLS_ACME_CA=http://ca.example.org/acme/acme/directory",
        "FAI_DISCOVERY_TLS_ACME_CA=https://ca.example.org/dir}\n import x",
        "FAI_DISCOVERY_TLS_PORT=80",
        "FAI_DISCOVERY_TLS_PORT=8080",
        "FAI_DISCOVERY_TLS_PORT=70000",
        "FAI_DISCOVERY_TLS_ACME_CHALLENGE=dns-01",
    ],
)
def test_invalid_values_change_nothing(env, line):
    env.write_site(acme_site(env) + line + "\n")

    result = env.run()

    assert result.returncode != 0
    assert not env.caddyfile.exists()
    assert env.calls_list() == []


def test_unknown_mode_is_rejected(env):
    env.write_site("FAI_DISCOVERY_TLS_MODE=letsencrypt\nFAI_DISCOVERY_TLS_HOST=fai.example.org\n")

    result = env.run()

    assert result.returncode != 0
    assert not env.caddyfile.exists()


def test_failed_validation_keeps_previous_caddyfile(env):
    env.write_site(acme_site(env))
    assert env.run().returncode == 0
    before = env.caddyfile.read_text()
    env.write_site(acme_site(env).replace("fai.example.org", "other.example.org"))

    result = env.run(FAKE_CADDY_FAIL="1")

    assert result.returncode != 0
    assert env.caddyfile.read_text() == before
    assert not list(env.caddyfile.parent.glob("*.new*"))


def test_foreign_caddyfile_is_not_touched(env):
    foreign = "proxy.example.org {\n\treverse_proxy 10.0.0.1:80\n}\n"
    env.caddyfile.write_text(foreign)
    env.write_site(acme_site(env))

    result = env.run()

    assert result.returncode != 0
    assert "Caddyfile" in result.stderr
    assert env.caddyfile.read_text() == foreign
    assert not any(c.startswith("systemctl") for c in env.calls_list())


def test_debian_default_caddyfile_is_backed_up_and_replaced(env):
    env.caddyfile.write_text(DEBIAN_DEFAULT)
    env.write_site(acme_site(env))

    result = env.run()

    assert result.returncode == 0, result.stderr
    assert env.caddyfile.read_text().startswith(MARKER)
    assert (env.caddyfile.parent / "Caddyfile.pre-fai-discovery").read_text() == DEBIAN_DEFAULT


def test_off_removes_managed_caddyfile_and_restores_backup(env):
    env.caddyfile.write_text(DEBIAN_DEFAULT)
    env.write_site(acme_site(env))
    assert env.run().returncode == 0
    env.write_site("FAI_DISCOVERY_TLS_MODE=off\n")

    result = env.run()

    assert result.returncode == 0, result.stderr
    assert env.caddyfile.read_text() == DEBIAN_DEFAULT
    assert "systemctl disable --now caddy" in env.calls_list()


def test_off_without_managed_caddyfile_does_nothing(env):
    foreign = "proxy.example.org {\n}\n"
    env.caddyfile.write_text(foreign)
    env.write_site("# kein TLS\n")

    result = env.run()

    assert result.returncode == 0, result.stderr
    assert env.caddyfile.read_text() == foreign
    assert env.calls_list() == []


def test_generated_caddyfiles_pass_real_caddy_validation(env):
    # Nur wenn ein echtes caddy im PATH liegt (Server, oder lokal fuer die
    # Entwicklung): prueft die erzeugte Syntax gegen Caddy selbst.
    real = shutil.which("caddy")
    if real is None:
        pytest.skip("kein caddy im PATH")
    env.write_site(
        "FAI_DISCOVERY_TLS_MODE=acme\nFAI_DISCOVERY_TLS_HOST=fai.example.org\n"
        "FAI_DISCOVERY_TLS_ACME_CA=https://ca.example.org:9000/acme/acme/directory\n"
    )
    result = env.run(caddy=real)
    assert result.returncode == 0, result.stderr
    env.write_site(
        "FAI_DISCOVERY_TLS_MODE=acme\nFAI_DISCOVERY_TLS_HOST=fai.example.org\n"
        "FAI_DISCOVERY_TLS_ACME_CA=https://ca.example.org:9000/acme/acme/directory\n"
        "FAI_DISCOVERY_TLS_ACME_CHALLENGE=http-01\n"
    )
    result = env.run(caddy=real)
    assert result.returncode == 0, result.stderr
    env.write_site(
        "FAI_DISCOVERY_TLS_MODE=internal\nFAI_DISCOVERY_TLS_HOST=fai.example.org\n"
        "FAI_DISCOVERY_TLS_EXTRA_NAMES=192.168.77.2\n"
    )
    result = env.run(caddy=real)
    assert result.returncode == 0, result.stderr
