import os
import sqlite3
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "bin" / "fai-discovery-known"
MARKER = "# fai-discovery-known: managed file, do not edit"
# Built from pieces on purpose: the product must not use this phrase anywhere,
# not even as a literal in its own tests.
FORBIDDEN_TERMS = ("self" + "-provisioning", "self" + "prov")

MAC_FLEET = "aa:bb:cc:00:00:01"
MAC_REINSTALL = "aa:bb:cc:00:00:02"
MAC_WAITING = "aa:bb:cc:00:00:03"
MAC_DISCARDED = "aa:bb:cc:00:00:04"
INSTALL_CONFIG = "default fai-generated\n\nlabel fai-generated\nlinux vmlinuz-x\nappend FAI_ACTION=install\n"


def cfg_name(mac: str) -> str:
    return "01-" + mac.replace(":", "-")


class Env:
    def __init__(self, root: Path):
        self.root = root
        self.tftp = root / "tftp"
        self.cfg = self.tftp / "pxelinux.cfg"
        self.db = root / "devices.db"
        self.site_conf = root / "site.conf"

    def write_db(self, rows):
        conn = sqlite3.connect(self.db)
        conn.execute("CREATE TABLE devices (mac TEXT PRIMARY KEY, status TEXT NOT NULL)")
        conn.executemany("INSERT INTO devices (mac, status) VALUES (?, ?)", rows)
        conn.commit()
        conn.close()

    def env(self, **extra) -> dict:
        base = {
            "PATH": os.environ["PATH"],
            "FAI_DISCOVERY_SITE_CONF": str(self.site_conf),
            "FAI_DISCOVERY_TFTP_DIR": str(self.tftp),
            "FAI_DISCOVERY_DB_PATH": str(self.db),
            "FAI_DISCOVERY_TFTP_OWNER": "",
            "FAI_DISCOVERY_LOCK_FILE": str(self.root / "known.lock"),
        }
        base.update(extra)
        return base

    def run(self, **extra_env) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["/bin/bash", str(SCRIPT)],
            env=self.env(**extra_env),
            capture_output=True,
            text=True,
        )

    def file(self, mac: str) -> Path:
        return self.cfg / cfg_name(mac)


@pytest.fixture
def known_env(tmp_path):
    e = Env(tmp_path)
    e.cfg.mkdir(parents=True)
    e.site_conf.write_text("FAI_DISCOVERY_MENU_ENABLED=true\n")
    e.write_db(
        [
            (MAC_FLEET, "reboot"),
            (MAC_REINSTALL, "reinstalling"),
            (MAC_WAITING, "waiting"),
            (MAC_DISCARDED, "discarded"),
        ]
    )
    return e


def test_known_devices_get_a_localboot_config(known_env):
    r = known_env.run()
    assert r.returncode == 0, r.stderr

    for mac in (MAC_FLEET, MAC_REINSTALL):
        lines = known_env.file(mac).read_text().splitlines()
        assert lines[0] == MARKER
        assert "localboot -1" in lines


def test_waiting_and_discarded_devices_stay_unknown(known_env):
    assert known_env.run().returncode == 0
    assert not known_env.file(MAC_WAITING).exists()
    assert not known_env.file(MAC_DISCARDED).exists()


def test_active_unmarked_config_is_never_touched(known_env):
    known_env.file(MAC_FLEET).write_text(INSTALL_CONFIG)
    assert known_env.run().returncode == 0
    assert known_env.file(MAC_FLEET).read_text() == INSTALL_CONFIG


def test_finished_install_gets_localboot_after_fai_disables_its_config(known_env):
    # FAI renames the install config to 01-<mac>.disable at the end of a run.
    disabled = known_env.cfg / (cfg_name(MAC_FLEET) + ".disable")
    disabled.write_text(INSTALL_CONFIG)
    assert known_env.run().returncode == 0
    assert known_env.file(MAC_FLEET).read_text().splitlines()[0] == MARKER
    assert disabled.read_text() == INSTALL_CONFIG


def test_marker_file_of_a_deleted_device_is_removed(known_env):
    assert known_env.run().returncode == 0
    conn = sqlite3.connect(known_env.db)
    conn.execute("DELETE FROM devices WHERE mac = ?", (MAC_FLEET,))
    conn.commit()
    conn.close()

    assert known_env.run().returncode == 0
    assert not known_env.file(MAC_FLEET).exists()
    assert known_env.file(MAC_REINSTALL).exists()


def test_marker_file_of_a_device_that_is_waiting_again_is_removed(known_env):
    assert known_env.run().returncode == 0
    conn = sqlite3.connect(known_env.db)
    conn.execute("UPDATE devices SET status = 'waiting' WHERE mac = ?", (MAC_FLEET,))
    conn.commit()
    conn.close()

    assert known_env.run().returncode == 0
    assert not known_env.file(MAC_FLEET).exists()


def test_unmarked_config_of_an_unknown_mac_is_never_removed(known_env):
    stranger = "aa:bb:cc:00:00:99"
    known_env.file(stranger).write_text(INSTALL_CONFIG)
    assert known_env.run().returncode == 0
    assert known_env.file(stranger).read_text() == INSTALL_CONFIG


def test_second_run_changes_nothing(known_env):
    assert known_env.run().returncode == 0
    before = {p.name: p.stat().st_mtime_ns for p in known_env.cfg.iterdir()}
    r = known_env.run()
    assert r.returncode == 0, r.stderr
    after = {p.name: p.stat().st_mtime_ns for p in known_env.cfg.iterdir()}
    assert before == after


def test_disabled_menu_removes_all_marker_files_but_keeps_others(known_env):
    assert known_env.run().returncode == 0
    other = known_env.file(MAC_WAITING)
    other.write_text(INSTALL_CONFIG)
    known_env.site_conf.write_text("FAI_DISCOVERY_MENU_ENABLED=false\n")

    assert known_env.run().returncode == 0
    assert not known_env.file(MAC_FLEET).exists()
    assert not known_env.file(MAC_REINSTALL).exists()
    assert other.read_text() == INSTALL_CONFIG


def test_missing_database_changes_nothing(known_env):
    assert known_env.run().returncode == 0
    known_env.db.unlink()
    r = known_env.run()
    assert r.returncode == 0, r.stderr
    assert known_env.file(MAC_FLEET).exists()


def test_unreadable_database_fails_and_keeps_existing_files(known_env):
    assert known_env.run().returncode == 0
    known_env.db.write_text("this is not a sqlite database")
    r = known_env.run()
    assert r.returncode != 0
    assert known_env.file(MAC_FLEET).exists()


def test_invalid_mac_in_database_is_skipped(known_env):
    conn = sqlite3.connect(known_env.db)
    conn.execute("INSERT INTO devices (mac, status) VALUES ('../../etc/x', 'reboot')")
    conn.commit()
    conn.close()

    r = known_env.run()
    assert r.returncode == 0, r.stderr
    assert known_env.file(MAC_FLEET).exists()
    assert sorted(p.name for p in known_env.cfg.iterdir()) == sorted(
        [cfg_name(MAC_FLEET), cfg_name(MAC_REINSTALL)]
    )


def test_uppercase_mac_in_database_is_normalised(known_env):
    conn = sqlite3.connect(known_env.db)
    conn.execute("INSERT INTO devices (mac, status) VALUES ('AA:BB:CC:00:00:05', 'reboot')")
    conn.commit()
    conn.close()

    assert known_env.run().returncode == 0
    assert known_env.file("aa:bb:cc:00:00:05").exists()


def test_script_does_not_use_the_forbidden_term():
    text = SCRIPT.read_text().lower()
    assert not any(term in text for term in FORBIDDEN_TERMS)
