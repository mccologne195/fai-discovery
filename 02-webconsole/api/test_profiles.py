import pytest

import profiles

SAMPLE = """Default: Debian 13 + EXT4 System

Name: Debian 13 + EXT4 System
Description: Base install trixie by FAI installation
Short: A linux-host, no xorg, an account called admin
Long: This is a small installation with security feature
fail2ban and ufw firewall. Additional account called admin
All needed packages are already on the CD or USB stick.
Classes: INSTALL FAIBASE DEBIAN STEP SALT SECURE TRIXIE64

Name: Debian 13 + BTRFS System
Description: Base install trixie by FAI installation
Classes: INSTALL FAIBASE BTRFS DEBIAN STEP SECURE TRIXIE64

Name: Inventory
Description: Show hardware info
Classes: INVENTORY
"""


def test_parse_profiles_extracts_name_and_classes():
    result = profiles.parse_profiles(SAMPLE)
    assert result == [
        {"name": "Debian 13 + EXT4 System", "classes": "INSTALL FAIBASE DEBIAN STEP SALT SECURE TRIXIE64"},
        {"name": "Debian 13 + BTRFS System", "classes": "INSTALL FAIBASE BTRFS DEBIAN STEP SECURE TRIXIE64"},
        {"name": "Inventory", "classes": "INVENTORY"},
    ]


def test_parse_profiles_skips_leading_default_line():
    result = profiles.parse_profiles(SAMPLE)
    names = [p["name"] for p in result]
    assert "Debian 13 + EXT4 System" in names
    assert not any("Default" in n for n in names)


def test_parse_profiles_empty_text_returns_empty_list():
    assert profiles.parse_profiles("") == []


def test_load_profiles_reads_file(tmp_path):
    profile_file = tmp_path / "example.profile"
    profile_file.write_text(SAMPLE)

    result = profiles.load_profiles(profile_file)

    assert len(result) == 3


def test_load_profiles_missing_file_raises_oserror(tmp_path):
    missing = tmp_path / "does-not-exist.profile"
    with pytest.raises(OSError):
        profiles.load_profiles(missing)


def test_profile_path_uses_env_var(monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_PROFILE_FILE", "/tmp/custom.profile")
    assert profiles.profile_path() == "/tmp/custom.profile"


def test_profile_path_default(monkeypatch):
    monkeypatch.delenv("FAI_DISCOVERY_PROFILE_FILE", raising=False)
    assert profiles.profile_path() == "/srv/fai/config/class/example.profile"


def test_parse_default_returns_name_from_default_line():
    assert profiles.parse_default(SAMPLE) == "Debian 13 + EXT4 System"


def test_parse_default_strips_whitespace():
    assert profiles.parse_default("Default:   Inventory  \n\nName: Inventory\nClasses: INVENTORY\n") == "Inventory"


def test_parse_default_without_default_line_returns_none():
    assert profiles.parse_default("Name: Inventory\nClasses: INVENTORY\n") is None


def test_parse_default_empty_value_returns_none():
    assert profiles.parse_default("Default:\n\nName: Inventory\nClasses: INVENTORY\n") is None


def test_load_default_profile_returns_name_only_if_profile_exists(tmp_path):
    profile_file = tmp_path / "x.profile"
    profile_file.write_text(SAMPLE)
    assert profiles.load_default_profile(profile_file) == "Debian 13 + EXT4 System"

    profile_file.write_text(SAMPLE.replace("Default: Debian 13 + EXT4 System", "Default: Gibt es nicht"))
    assert profiles.load_default_profile(profile_file) is None


def test_load_default_profile_missing_file_returns_none(tmp_path):
    assert profiles.load_default_profile(tmp_path / "does-not-exist.profile") is None
