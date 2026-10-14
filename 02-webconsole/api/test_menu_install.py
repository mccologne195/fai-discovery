import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
UNITS = REPO / "02-webconsole" / "etc" / "systemd" / "system"
INSTALL = REPO / "install.sh"


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
        assert "self-provisioning" not in text and "selfprov" not in text, path


def test_install_sh_warns_about_the_rollout_order_when_enabling():
    text = INSTALL.read_text()
    enabled_branch = text.split("--is-enabled", 1)[1].split("elif", 1)[0]
    assert "WARNUNG" in enabled_branch
    assert "fai/efi64/syslinux.efi" in enabled_branch
