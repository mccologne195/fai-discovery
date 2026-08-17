import socket
import subprocess
from pathlib import Path

_DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[2]


def current_version(repo_root=None, runner=subprocess.run):
    if repo_root is None:
        repo_root = _DEFAULT_REPO_ROOT

    try:
        result = runner(
            ["git", "describe", "--tags", "--always", "--dirty"],
            capture_output=True,
            text=True,
            cwd=repo_root,
        )
    except OSError:
        return None

    if result.returncode != 0:
        return None

    return result.stdout.strip()


def current_hostname(resolver=socket.getfqdn):
    return resolver()
