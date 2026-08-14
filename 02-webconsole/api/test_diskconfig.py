import diskconfig


def test_disk_config_dir_uses_env_var(monkeypatch):
    monkeypatch.setenv(diskconfig.DISK_CONFIG_DIR_ENV, "/custom/path")
    assert diskconfig.disk_config_dir() == "/custom/path"


def test_disk_config_dir_default(monkeypatch):
    monkeypatch.delenv(diskconfig.DISK_CONFIG_DIR_ENV, raising=False)
    assert diskconfig.disk_config_dir() == "/srv/fai/config/disk_config"


def test_efi_classes_for_finds_matching_file(tmp_path, monkeypatch):
    monkeypatch.setenv(diskconfig.DISK_CONFIG_DIR_ENV, str(tmp_path))
    (tmp_path / "FAIBASE_EFI").write_text("dummy")

    result = diskconfig.efi_classes_for("INSTALL FAIBASE DEBIAN STEP")

    assert result == ["FAIBASE_EFI"]


def test_efi_classes_for_no_matches_returns_empty_list(tmp_path, monkeypatch):
    monkeypatch.setenv(diskconfig.DISK_CONFIG_DIR_ENV, str(tmp_path))

    result = diskconfig.efi_classes_for("INSTALL FAIBASE DEBIAN")

    assert result == []


def test_efi_classes_for_multiple_matches_preserve_input_order(tmp_path, monkeypatch):
    monkeypatch.setenv(diskconfig.DISK_CONFIG_DIR_ENV, str(tmp_path))
    (tmp_path / "DEBIAN_EFI").write_text("dummy")
    (tmp_path / "FAIBASE_EFI").write_text("dummy")

    result = diskconfig.efi_classes_for("INSTALL FAIBASE DEBIAN STEP")

    assert result == ["FAIBASE_EFI", "DEBIAN_EFI"]


def test_efi_classes_for_unreadable_directory_returns_empty_list(monkeypatch):
    monkeypatch.setenv(diskconfig.DISK_CONFIG_DIR_ENV, "/nonexistent/path/xyz-does-not-exist")

    result = diskconfig.efi_classes_for("INSTALL FAIBASE")

    assert result == []


def test_efi_classes_for_ignores_directory_named_like_a_class(tmp_path, monkeypatch):
    monkeypatch.setenv(diskconfig.DISK_CONFIG_DIR_ENV, str(tmp_path))
    (tmp_path / "FAIBASE_EFI").mkdir()

    result = diskconfig.efi_classes_for("INSTALL FAIBASE")

    assert result == []


def test_classes_with_efi_variants_appends_matches_when_uefi(tmp_path, monkeypatch):
    monkeypatch.setenv(diskconfig.DISK_CONFIG_DIR_ENV, str(tmp_path))
    (tmp_path / "FAIBASE_EFI").write_text("dummy")

    result = diskconfig.classes_with_efi_variants("INSTALL FAIBASE DEBIAN", "uefi")

    assert result == "INSTALL FAIBASE DEBIAN FAIBASE_EFI"


def test_classes_with_efi_variants_unchanged_when_bios(tmp_path, monkeypatch):
    monkeypatch.setenv(diskconfig.DISK_CONFIG_DIR_ENV, str(tmp_path))
    (tmp_path / "FAIBASE_EFI").write_text("dummy")

    result = diskconfig.classes_with_efi_variants("INSTALL FAIBASE DEBIAN", "bios")

    assert result == "INSTALL FAIBASE DEBIAN"


def test_classes_with_efi_variants_unchanged_when_firmware_empty(tmp_path, monkeypatch):
    monkeypatch.setenv(diskconfig.DISK_CONFIG_DIR_ENV, str(tmp_path))
    (tmp_path / "FAIBASE_EFI").write_text("dummy")

    result = diskconfig.classes_with_efi_variants("INSTALL FAIBASE DEBIAN", "")

    assert result == "INSTALL FAIBASE DEBIAN"


def test_classes_with_efi_variants_unchanged_when_no_matches_even_if_uefi(tmp_path, monkeypatch):
    monkeypatch.setenv(diskconfig.DISK_CONFIG_DIR_ENV, str(tmp_path))

    result = diskconfig.classes_with_efi_variants("INSTALL FAIBASE DEBIAN", "uefi")

    assert result == "INSTALL FAIBASE DEBIAN"


def test_efi_classes_for_skips_class_already_present_in_input(tmp_path, monkeypatch):
    monkeypatch.setenv(diskconfig.DISK_CONFIG_DIR_ENV, str(tmp_path))
    (tmp_path / "FAIBASE_EFI").write_text("dummy")

    result = diskconfig.efi_classes_for("INSTALL FAIBASE FAIBASE_EFI")

    assert result == []


def test_classes_with_efi_variants_warns_when_directory_missing(monkeypatch, caplog):
    monkeypatch.setenv(diskconfig.DISK_CONFIG_DIR_ENV, "/nonexistent/path/xyz-does-not-exist")

    with caplog.at_level("WARNING"):
        result = diskconfig.classes_with_efi_variants("INSTALL FAIBASE", "uefi")

    assert result == "INSTALL FAIBASE"
    assert "nicht lesbar" in caplog.text
