import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
UNITS = REPO / "02-webconsole" / "etc" / "systemd" / "system"
INSTALL = REPO / "install.sh"
# Built from pieces on purpose: the product must not use this phrase anywhere,
# not even as a literal in its own tests.
FORBIDDEN_TERMS = ("self" + "-provisioning", "self" + "prov")


def test_service_unit_runs_the_script_once_with_debounce():
    text = (UNITS / "fai-discovery-menu.service").read_text()
    assert "Type=oneshot" in text
    assert "ExecStartPre=/bin/sleep 5" in text
    assert "ExecStart=/usr/local/bin/fai-discovery-menu\n" in text


def test_path_unit_watches_the_tftp_root():
    text = (UNITS / "fai-discovery-menu.path").read_text()
    assert "PathChanged=/srv/tftp/fai\n" in text
    assert "WantedBy=multi-user.target" in text


def test_install_sh_is_valid_bash():
    r = subprocess.run(["bash", "-n", str(INSTALL)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_install_sh_deploys_menu_script_and_gates_units_on_site_conf():
    text = INSTALL.read_text()
    assert '02-webconsole/bin/fai-discovery-menu" /usr/local/bin/fai-discovery-menu' in text
    assert "/usr/local/bin/fai-discovery-menu --is-enabled" in text
    assert "FAI_DISCOVERY_MENU_ENABLED=true' \"$SITE_CONF\"" not in text  # no second parser
    assert "systemctl enable --now fai-discovery-menu.path" in text
    assert "systemctl disable --now fai-discovery-menu.path" in text
    assert text.index("Schritt 5b") < text.index("Schritt 6: Firewall")


def test_no_forbidden_term_in_new_files():
    for path in (
        UNITS / "fai-discovery-menu.service",
        UNITS / "fai-discovery-menu.path",
        REPO / "02-webconsole" / "bin" / "fai-discovery-menu",
    ):
        text = path.read_text().lower()
        assert not any(term in text for term in FORBIDDEN_TERMS), path


def test_install_sh_warns_about_the_rollout_order_when_enabling():
    text = INSTALL.read_text()
    enabled_branch = text.split("--is-enabled", 1)[1].split("elif", 1)[0]
    assert "WARNUNG" in enabled_branch
    assert "fai/efi64/syslinux.efi" in enabled_branch


def test_install_sh_disable_branch_reports_script_failure_clearly():
    text = INSTALL.read_text()
    disable_branch = text.split("systemctl disable --now fai-discovery-menu.path", 1)[1].split("else", 1)[0]
    assert "/usr/local/bin/fai-discovery-menu || die" in disable_branch


def test_known_service_unit_runs_the_script_once():
    text = (UNITS / "fai-discovery-known.service").read_text()
    assert "Type=oneshot" in text
    assert "ExecStart=/usr/local/bin/fai-discovery-known\n" in text


def test_known_path_unit_watches_the_per_mac_config_directory():
    text = (UNITS / "fai-discovery-known.path").read_text()
    assert "PathChanged=/srv/tftp/fai/pxelinux.cfg\n" in text
    assert "WantedBy=multi-user.target" in text


def test_known_timer_unit_catches_database_changes():
    text = (UNITS / "fai-discovery-known.timer").read_text()
    assert "OnUnitActiveSec=" in text
    assert "OnBootSec=" in text
    assert "WantedBy=timers.target" in text


def test_install_sh_deploys_known_script_and_gates_units_on_the_menu_switch():
    text = INSTALL.read_text()
    assert '02-webconsole/bin/fai-discovery-known" /usr/local/bin/fai-discovery-known' in text
    assert "for unit in service path timer; do" in text
    assert "etc/systemd/system/fai-discovery-known.$unit" in text
    assert "systemctl enable --now fai-discovery-known.path fai-discovery-known.timer" in text
    assert "systemctl disable --now fai-discovery-known.path fai-discovery-known.timer" in text
    assert text.index("Schritt 5b") < text.index("fai-discovery-known.path") < text.index("Schritt 6: Firewall")


def test_install_sh_disable_branch_cleans_up_known_files_after_stopping_the_units():
    text = INSTALL.read_text()
    disable_branch = text.split("systemctl disable --now fai-discovery-known.path", 1)[1]
    disable_branch = disable_branch.split("else", 1)[0]
    assert "/usr/local/bin/fai-discovery-known || die" in disable_branch


def test_no_forbidden_term_in_known_units():
    for name in ("service", "path", "timer"):
        text = (UNITS / f"fai-discovery-known.{name}").read_text().lower()
        assert not any(term in text for term in FORBIDDEN_TERMS), name
