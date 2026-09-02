import os
import re
import subprocess

MAC_RE = re.compile(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$")
CLASSES_RE = re.compile(r"^[A-Za-z0-9_ -]+$")
HOSTNAME_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")
_HOSTNAME_FRAGMENT_PLACEHOLDERS = {
    "not specified",
    "not settable",
    "to be filled by o.e.m.",
    "none",
    "n/a",
    "unknown",
    "default string",
}

_HOSTNAME_FRAGMENT_INVALID_RE = re.compile(r"[^a-z0-9]+")
_DEGENERATE_UUID_SEGMENT_RE = re.compile(r"^(0+|[fF]+)$")

CHBOOT_WRAPPER = "/usr/local/bin/fai-discovery-chboot"
NFS_ROOT_ENV = "FAI_DISCOVERY_NFS_ROOT"
BOOT_URL_ENV = "FAI_DISCOVERY_BOOT_URL"


def nfs_root():
    return os.environ.get(NFS_ROOT_ENV)


def boot_url():
    return os.environ.get(BOOT_URL_ENV, "")


def normalize_mac(raw):
    if not isinstance(raw, str) or not raw:
        return None
    candidate = raw.strip().lower()
    if MAC_RE.fullmatch(candidate):
        return candidate
    return None


def run_fai_chboot(mac, classes, reboot=False, verbose=True, runner=subprocess.run):
    if not MAC_RE.fullmatch(mac):
        return False, f"invalid mac: {mac}"
    if not CLASSES_RE.fullmatch(classes):
        return False, f"invalid classes: {classes}"
    root = nfs_root()
    if not root:
        return False, "FAI_DISCOVERY_NFS_ROOT ist nicht gesetzt (siehe site.conf.example)"

    reboot_flag = "1" if reboot else "0"
    verbose_flag = "1" if verbose else "0"
    result = runner(
        ["sudo", CHBOOT_WRAPPER, "approve", mac, classes, root, reboot_flag, verbose_flag, boot_url()],
        capture_output=True,
        text=True,
    )
    output = (result.stdout or "") + (result.stderr or "")
    return result.returncode == 0, output


def run_fai_chboot_discovery(mac, runner=subprocess.run):
    if not MAC_RE.fullmatch(mac):
        return False, f"invalid mac: {mac}"
    root = nfs_root()
    if not root:
        return False, "FAI_DISCOVERY_NFS_ROOT ist nicht gesetzt (siehe site.conf.example)"

    result = runner(
        ["sudo", CHBOOT_WRAPPER, "discovery", mac, root, boot_url()], capture_output=True, text=True
    )
    output = (result.stdout or "") + (result.stderr or "")
    return result.returncode == 0, output


def run_fai_chboot_disable(mac, runner=subprocess.run):
    if not MAC_RE.fullmatch(mac):
        return False, f"invalid mac: {mac}"

    result = runner(["sudo", CHBOOT_WRAPPER, "disable", mac], capture_output=True, text=True)
    output = (result.stdout or "") + (result.stderr or "")
    return result.returncode == 0, output


def suggest_hostname_fragment(raw):
    if not isinstance(raw, str):
        return None
    candidate = raw.strip()
    if not candidate or candidate.lower() in _HOSTNAME_FRAGMENT_PLACEHOLDERS:
        return None
    normalized = _HOSTNAME_FRAGMENT_INVALID_RE.sub("-", candidate.lower()).strip("-")
    return normalized or None


def suggest_hostname_fragment_from_uuid(raw):
    if not isinstance(raw, str):
        return None
    segment = raw.strip().split("-")[0]
    if _DEGENERATE_UUID_SEGMENT_RE.match(segment):
        return None
    return suggest_hostname_fragment(segment)
