import os
import shutil
import subprocess
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[2] / "01-discovery-client" / "fai-config" / "hooks" / "discovery"
MAC = "aa:bb:cc:dd:ee:ff"
API_URL = "http://webconsole.test:8080"

# Stub fuer curl: /register scheitert, solange register-failures > 0 ist
# (Webkonsole kurz nicht erreichbar), /status liefert den Inhalt von "status".
CURL_STUB = """#!/bin/bash
state="$STUB_STATE"
url="${@: -1}"
echo "$url" >> "$state/curl.log"
case "$url" in
  */register)
    n=$(cat "$state/register-failures")
    if [ "$n" -gt 0 ]; then
        echo $((n - 1)) > "$state/register-failures"
        exit 7
    fi
    ;;
  */status/*)
    cat "$state/status"
    ;;
esac
exit 0
"""

IP_STUB = """#!/bin/bash
if [ "$1" = "route" ]; then echo "default via 10.0.0.1 dev eth0"; fi
if [ "$1" = "-4" ]; then echo "eth0 UP 10.0.0.50/24"; fi
"""


@pytest.fixture
def hook_env(tmp_path):
    bash = shutil.which("bash")
    version = subprocess.run([bash, "-c", "echo ${BASH_VERSINFO[0]}"], capture_output=True, text=True).stdout
    if int(version.strip() or 0) < 4:
        pytest.skip("Hook braucht bash >= 4 (${var,,})")

    stubs = tmp_path / "stubs"
    stubs.mkdir()
    for name, body in {
        "curl": CURL_STUB,
        "ip": IP_STUB,
        "sleep": "#!/bin/bash\nexit 0\n",
        "reboot": '#!/bin/bash\ntouch "$STUB_STATE/rebooted"\n',
    }.items():
        (stubs / name).write_text(body)
        (stubs / name).chmod(0o755)

    net = tmp_path / "net" / "eth0"
    net.mkdir(parents=True)
    (net / "address").write_text(MAC.upper() + "\n")

    state = tmp_path / "state"
    state.mkdir()
    (state / "status").write_text("reboot")
    (state / "register-failures").write_text("0")

    hook = tmp_path / "discovery"
    hook.write_text(HOOK.read_text().replace("__FAI_DISCOVERY_INTERNAL_URL__", API_URL))

    def run():
        env = {
            "PATH": f"{stubs}:{os.environ['PATH']}",
            "STUB_STATE": str(state),
            "FAI": str(tmp_path / "no-config"),
            "FAI_DISCOVERY_SYS_CLASS_NET": str(tmp_path / "net"),
        }
        return subprocess.run([bash, str(hook)], env=env, capture_output=True, text=True, timeout=30)

    return run, state


def register_calls(state):
    return [line for line in (state / "curl.log").read_text().splitlines() if line.endswith("/register")]


def test_hook_registers_once_and_reboots_after_approval(hook_env):
    run, state = hook_env

    result = run()

    assert result.returncode == 0, result.stderr
    assert register_calls(state) == [f"{API_URL}/register"]
    assert f"{API_URL}/status/{MAC}" in (state / "curl.log").read_text()
    assert (state / "rebooted").exists()


def test_hook_retries_registration_until_webconsole_answers(hook_env):
    # Review 2026-10-24: ein einziger fehlgeschlagener /register-Aufruf (z.B.
    # Webkonsole startet gerade neu) liess das Geraet ewig warten - /status
    # meldet fuer unbekannte MACs "waiting", das Geraet tauchte nie im
    # Dashboard auf.
    run, state = hook_env
    (state / "register-failures").write_text("2")

    result = run()

    assert result.returncode == 0, result.stderr
    assert len(register_calls(state)) == 3
    log = (state / "curl.log").read_text().splitlines()
    first_status = next(i for i, line in enumerate(log) if "/status/" in line)
    assert first_status > max(i for i, line in enumerate(log) if line.endswith("/register"))
    assert (state / "rebooted").exists()
