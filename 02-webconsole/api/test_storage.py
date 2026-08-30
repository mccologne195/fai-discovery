import sqlite3

import storage


def test_register_creates_waiting_device(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    storage.init_db()

    storage.register_device("aa:bb:cc:dd:ee:ff", "192.168.10.55", "Intel i5", "16", "500G")

    device = storage.get_device("aa:bb:cc:dd:ee:ff")
    assert device["status"] == "waiting"
    assert device["ip"] == "192.168.10.55"
    assert device["hostname"] is None


def test_register_overwrites_existing_and_resets_status(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    storage.init_db()

    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu1", "1", "1G")
    storage.approve_device("aa:bb:cc:dd:ee:ff", "host1", "FAIBASE", "admin")
    storage.register_device("aa:bb:cc:dd:ee:ff", "2.2.2.2", "cpu2", "2", "2G")

    device = storage.get_device("aa:bb:cc:dd:ee:ff")
    assert device["status"] == "waiting"
    assert device["ip"] == "2.2.2.2"
    assert device["hostname"] is None


def test_get_status_unknown_mac_returns_waiting(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    storage.init_db()

    assert storage.get_status("11:22:33:44:55:66") == "waiting"


def test_list_waiting_devices_excludes_approved(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    storage.init_db()

    storage.register_device("aa:aa:aa:aa:aa:aa", "1.1.1.1", "cpu", "1", "1G")
    storage.register_device("bb:bb:bb:bb:bb:bb", "2.2.2.2", "cpu", "1", "1G")
    storage.approve_device("bb:bb:bb:bb:bb:bb", "host2", "FAIBASE", "admin")

    waiting = storage.list_waiting_devices()
    assert [d["mac"] for d in waiting] == ["aa:aa:aa:aa:aa:aa"]


def test_approve_device_sets_fields(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    storage.init_db()
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")

    ok = storage.approve_device("aa:bb:cc:dd:ee:ff", "vmtest01", "FAIBASE DEBIAN", "admin")

    assert ok is True
    device = storage.get_device("aa:bb:cc:dd:ee:ff")
    assert device["status"] == "reboot"
    assert device["hostname"] == "vmtest01"
    assert device["classes"] == "FAIBASE DEBIAN"
    assert device["approved_by"] == "admin"
    assert device["approved_at"] is not None


def test_approve_device_unknown_mac_returns_false(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    storage.init_db()

    assert storage.approve_device("11:22:33:44:55:66", "h", "c", "admin") is False


def test_list_history_only_approved_newest_first(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    storage.init_db()

    storage.register_device("aa:aa:aa:aa:aa:aa", "1.1.1.1", "cpu", "1", "1G")
    storage.register_device("bb:bb:bb:bb:bb:bb", "2.2.2.2", "cpu", "1", "1G")
    storage.approve_device("aa:aa:aa:aa:aa:aa", "host1", "FAIBASE", "admin")
    storage.approve_device("bb:bb:bb:bb:bb:bb", "host2", "FAIBASE", "alice")

    history = storage.list_history()
    assert [d["mac"] for d in history] == ["bb:bb:bb:bb:bb:bb", "aa:aa:aa:aa:aa:aa"]


def test_mark_reinstalling_sets_status(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    storage.init_db()
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")
    storage.approve_device("aa:bb:cc:dd:ee:ff", "vmtest01", "FAIBASE", "admin")

    result = storage.mark_reinstalling("aa:bb:cc:dd:ee:ff")

    assert result is True
    assert storage.get_device("aa:bb:cc:dd:ee:ff")["status"] == "reinstalling"


def test_mark_reinstalling_ignores_waiting_entry(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    storage.init_db()
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")

    result = storage.mark_reinstalling("aa:bb:cc:dd:ee:ff")

    assert result is False
    assert storage.get_device("aa:bb:cc:dd:ee:ff")["status"] == "waiting"


def test_mark_reinstalling_unknown_mac_returns_false(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    storage.init_db()

    assert storage.mark_reinstalling("11:22:33:44:55:66") is False


def test_list_history_includes_reinstalling_entries(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    storage.init_db()
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")
    storage.approve_device("aa:bb:cc:dd:ee:ff", "vmtest01", "FAIBASE", "admin")
    storage.mark_reinstalling("aa:bb:cc:dd:ee:ff")

    history = storage.list_history()

    assert [d["mac"] for d in history] == ["aa:bb:cc:dd:ee:ff"]
    assert history[0]["status"] == "reinstalling"


def test_delete_device_removes_reboot_entry(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    storage.init_db()
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")
    storage.approve_device("aa:bb:cc:dd:ee:ff", "vmtest01", "FAIBASE", "admin")

    result = storage.delete_device("aa:bb:cc:dd:ee:ff")

    assert result is True
    assert storage.get_device("aa:bb:cc:dd:ee:ff") is None


def test_delete_device_ignores_waiting_entry(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    storage.init_db()
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")

    result = storage.delete_device("aa:bb:cc:dd:ee:ff")

    assert result is False
    assert storage.get_device("aa:bb:cc:dd:ee:ff") is not None


def test_delete_device_unknown_mac_returns_false(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    storage.init_db()

    assert storage.delete_device("11:22:33:44:55:66") is False


def test_discard_waiting_device_marks_entry_discarded(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    storage.init_db()
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")

    result = storage.discard_waiting_device("aa:bb:cc:dd:ee:ff")

    assert result is True
    device = storage.get_device("aa:bb:cc:dd:ee:ff")
    assert device is not None
    assert device["status"] == "discarded"


def test_discard_waiting_device_removes_entry_from_waiting_list(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    storage.init_db()
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")

    storage.discard_waiting_device("aa:bb:cc:dd:ee:ff")

    assert storage.list_waiting_devices() == []


def test_discard_waiting_device_ignores_reboot_entry(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    storage.init_db()
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")
    storage.approve_device("aa:bb:cc:dd:ee:ff", "vmtest01", "FAIBASE", "admin")

    result = storage.discard_waiting_device("aa:bb:cc:dd:ee:ff")

    assert result is False
    assert storage.get_device("aa:bb:cc:dd:ee:ff") is not None


def test_discard_waiting_device_unknown_mac_returns_false(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    storage.init_db()

    assert storage.discard_waiting_device("11:22:33:44:55:66") is False


def test_register_device_stores_uuid_and_serial(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    storage.init_db()

    storage.register_device(
        "aa:bb:cc:dd:ee:ff", "192.168.10.55", "Intel i5", "16", "500G",
        uuid="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", serial="ABC123",
    )

    device = storage.get_device("aa:bb:cc:dd:ee:ff")
    assert device["uuid"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert device["serial"] == "ABC123"


def test_register_device_defaults_uuid_and_serial_to_empty_string(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    storage.init_db()

    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")

    device = storage.get_device("aa:bb:cc:dd:ee:ff")
    assert device["uuid"] == ""
    assert device["serial"] == ""


def test_get_connection_migrates_pre_existing_table_without_uuid_serial_columns(tmp_path, monkeypatch):
    db_path = tmp_path / "devices.db"
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(db_path))

    # Simuliert eine devices.db von vor der uuid/serial-Migration (2026-08-10).
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE devices (
            mac TEXT PRIMARY KEY,
            ip TEXT,
            cpu TEXT,
            ram TEXT,
            disk TEXT,
            registered_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'waiting',
            hostname TEXT,
            classes TEXT,
            approved_by TEXT,
            approved_at TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO devices (mac, ip, cpu, ram, disk, registered_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G", "2026-08-01T00:00:00+00:00"),
    )
    conn.commit()
    conn.close()

    storage.init_db()

    device = storage.get_device("aa:bb:cc:dd:ee:ff")
    assert device["mac"] == "aa:bb:cc:dd:ee:ff"
    assert device["uuid"] is None
    assert device["serial"] is None


def test_list_history_filters_by_mac_substring(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    storage.init_db()
    storage.register_device("aa:aa:aa:aa:aa:aa", "1.1.1.1", "cpu", "1", "1G")
    storage.register_device("bb:bb:bb:bb:bb:bb", "2.2.2.2", "cpu", "1", "1G")
    storage.approve_device("aa:aa:aa:aa:aa:aa", "host1", "FAIBASE", "admin")
    storage.approve_device("bb:bb:bb:bb:bb:bb", "host2", "FAIBASE", "alice")

    history = storage.list_history(query="aa:aa:aa")

    assert [d["mac"] for d in history] == ["aa:aa:aa:aa:aa:aa"]


def test_list_history_filters_by_hostname_substring(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    storage.init_db()
    storage.register_device("aa:aa:aa:aa:aa:aa", "1.1.1.1", "cpu", "1", "1G")
    storage.register_device("bb:bb:bb:bb:bb:bb", "2.2.2.2", "cpu", "1", "1G")
    storage.approve_device("aa:aa:aa:aa:aa:aa", "vmtest01", "FAIBASE", "admin")
    storage.approve_device("bb:bb:bb:bb:bb:bb", "vmweb02", "FAIBASE", "alice")

    history = storage.list_history(query="test01")

    assert [d["mac"] for d in history] == ["aa:aa:aa:aa:aa:aa"]


def test_list_history_filters_by_classes_substring(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    storage.init_db()
    storage.register_device("aa:aa:aa:aa:aa:aa", "1.1.1.1", "cpu", "1", "1G")
    storage.register_device("bb:bb:bb:bb:bb:bb", "2.2.2.2", "cpu", "1", "1G")
    storage.approve_device("aa:aa:aa:aa:aa:aa", "host1", "FAIBASE DEBIAN", "admin")
    storage.approve_device("bb:bb:bb:bb:bb:bb", "host2", "FAIBASE UBUNTU", "alice")

    history = storage.list_history(query="DEBIAN")

    assert [d["mac"] for d in history] == ["aa:aa:aa:aa:aa:aa"]


def test_list_history_filters_by_approved_by_substring(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    storage.init_db()
    storage.register_device("aa:aa:aa:aa:aa:aa", "1.1.1.1", "cpu", "1", "1G")
    storage.register_device("bb:bb:bb:bb:bb:bb", "2.2.2.2", "cpu", "1", "1G")
    storage.approve_device("aa:aa:aa:aa:aa:aa", "host1", "FAIBASE", "admin")
    storage.approve_device("bb:bb:bb:bb:bb:bb", "host2", "FAIBASE", "alice")

    history = storage.list_history(query="alice")

    assert [d["mac"] for d in history] == ["bb:bb:bb:bb:bb:bb"]


def test_list_history_filters_by_uuid_substring(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    storage.init_db()
    storage.register_device(
        "aa:aa:aa:aa:aa:aa", "1.1.1.1", "cpu", "1", "1G",
        uuid="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    )
    storage.register_device("bb:bb:bb:bb:bb:bb", "2.2.2.2", "cpu", "1", "1G", uuid="other-uuid")
    storage.approve_device("aa:aa:aa:aa:aa:aa", "host1", "FAIBASE", "admin")
    storage.approve_device("bb:bb:bb:bb:bb:bb", "host2", "FAIBASE", "alice")

    history = storage.list_history(query="aaaaaaaa")

    assert [d["mac"] for d in history] == ["aa:aa:aa:aa:aa:aa"]


def test_list_history_filters_by_serial_substring(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    storage.init_db()
    storage.register_device("aa:aa:aa:aa:aa:aa", "1.1.1.1", "cpu", "1", "1G", serial="SN-ABC123")
    storage.register_device("bb:bb:bb:bb:bb:bb", "2.2.2.2", "cpu", "1", "1G", serial="SN-XYZ999")
    storage.approve_device("aa:aa:aa:aa:aa:aa", "host1", "FAIBASE", "admin")
    storage.approve_device("bb:bb:bb:bb:bb:bb", "host2", "FAIBASE", "alice")

    history = storage.list_history(query="ABC123")

    assert [d["mac"] for d in history] == ["aa:aa:aa:aa:aa:aa"]


def test_list_history_query_no_match_returns_empty_list(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    storage.init_db()
    storage.register_device("aa:aa:aa:aa:aa:aa", "1.1.1.1", "cpu", "1", "1G")
    storage.approve_device("aa:aa:aa:aa:aa:aa", "host1", "FAIBASE", "admin")

    assert storage.list_history(query="does-not-exist") == []


def test_list_history_empty_query_returns_all(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    storage.init_db()
    storage.register_device("aa:aa:aa:aa:aa:aa", "1.1.1.1", "cpu", "1", "1G")
    storage.approve_device("aa:aa:aa:aa:aa:aa", "host1", "FAIBASE", "admin")

    assert [d["mac"] for d in storage.list_history(query="")] == ["aa:aa:aa:aa:aa:aa"]


def test_list_history_query_escapes_percent_wildcard(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    storage.init_db()
    storage.register_device("aa:aa:aa:aa:aa:aa", "1.1.1.1", "cpu", "1", "1G")
    storage.approve_device("aa:aa:aa:aa:aa:aa", "host50xyz", "FAIBASE", "admin")

    # "50%" darf nicht als SQL-Wildcard "50" + irgendwas interpretiert werden -
    # ein Hostname wie "host50xyz" enthält kein wörtliches "50%".
    assert storage.list_history(query="50%") == []


def test_list_history_query_escapes_underscore_wildcard(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    storage.init_db()
    storage.register_device("aa:aa:aa:aa:aa:aa", "1.1.1.1", "cpu", "1", "1G")
    storage.approve_device("aa:aa:aa:aa:aa:aa", "hostAxyz", "FAIBASE", "admin")

    # "A_" als literale Suche darf nicht "A" + ein beliebiges Zeichen matchen.
    assert storage.list_history(query="A_") == []


def test_register_device_stores_firmware(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    storage.init_db()

    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G", firmware="uefi")

    device = storage.get_device("aa:bb:cc:dd:ee:ff")

    assert device["firmware"] == "uefi"


def test_register_device_defaults_firmware_to_empty_string(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    storage.init_db()

    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")

    device = storage.get_device("aa:bb:cc:dd:ee:ff")

    assert device["firmware"] == ""


def test_register_device_preserves_hostname_as_previous_hostname_on_reregistration(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    storage.init_db()
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")
    storage.approve_device("aa:bb:cc:dd:ee:ff", "vmtest01", "FAIBASE", "admin")

    storage.register_device("aa:bb:cc:dd:ee:ff", "2.2.2.2", "cpu2", "2", "2G")

    device = storage.get_device("aa:bb:cc:dd:ee:ff")
    assert device["hostname"] is None
    assert device["previous_hostname"] == "vmtest01"


def test_register_device_never_approved_leaves_previous_hostname_none(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    storage.init_db()

    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")

    device = storage.get_device("aa:bb:cc:dd:ee:ff")
    assert device["previous_hostname"] is None


def test_register_device_repeated_reregistration_without_approval_keeps_previous_hostname(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    storage.init_db()
    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")
    storage.approve_device("aa:bb:cc:dd:ee:ff", "vmtest01", "FAIBASE", "admin")
    storage.register_device("aa:bb:cc:dd:ee:ff", "2.2.2.2", "cpu2", "2", "2G")

    # Erneute Registrierung, ohne dass zwischenzeitlich wieder freigegeben wurde
    # (z. B. Discovery zweimal versehentlich ausgelöst) - previous_hostname darf
    # nicht auf NULL zurückfallen, weil das aktuelle hostname-Feld schon leer ist.
    storage.register_device("aa:bb:cc:dd:ee:ff", "3.3.3.3", "cpu3", "3", "3G")

    device = storage.get_device("aa:bb:cc:dd:ee:ff")
    assert device["previous_hostname"] == "vmtest01"


def test_get_connection_migrates_pre_existing_table_without_previous_hostname_column(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    conn = storage.get_connection()
    conn.execute("ALTER TABLE devices RENAME TO devices_old")
    conn.execute(
        """
        CREATE TABLE devices (
            mac TEXT PRIMARY KEY,
            ip TEXT,
            cpu TEXT,
            ram TEXT,
            disk TEXT,
            registered_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'waiting',
            hostname TEXT,
            classes TEXT,
            approved_by TEXT,
            approved_at TEXT,
            uuid TEXT,
            serial TEXT,
            firmware TEXT
        )
        """
    )
    conn.execute("DROP TABLE devices_old")
    conn.commit()
    conn.close()

    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G")

    device = storage.get_device("aa:bb:cc:dd:ee:ff")
    assert device["previous_hostname"] is None


def test_get_connection_migrates_pre_existing_table_without_firmware_column(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    conn = storage.get_connection()
    conn.execute("ALTER TABLE devices RENAME TO devices_old")
    conn.execute(
        """
        CREATE TABLE devices (
            mac TEXT PRIMARY KEY,
            ip TEXT,
            cpu TEXT,
            ram TEXT,
            disk TEXT,
            registered_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'waiting',
            hostname TEXT,
            classes TEXT,
            approved_by TEXT,
            approved_at TEXT,
            uuid TEXT,
            serial TEXT
        )
        """
    )
    conn.execute("DROP TABLE devices_old")
    conn.commit()
    conn.close()

    storage.register_device("aa:bb:cc:dd:ee:ff", "1.1.1.1", "cpu", "1", "1G", firmware="bios")

    device = storage.get_device("aa:bb:cc:dd:ee:ff")
    assert device["firmware"] == "bios"


def test_count_by_status_empty_db_returns_zero_for_all_known_statuses(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    storage.init_db()

    counts = storage.count_by_status()

    assert counts == {"waiting": 0, "reboot": 0, "reinstalling": 0, "discarded": 0}


def test_count_by_status_reflects_current_devices(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    storage.init_db()

    storage.register_device("aa:bb:cc:dd:ee:01", "1.1.1.1", "cpu", "1", "1G")
    storage.register_device("aa:bb:cc:dd:ee:02", "1.1.1.2", "cpu", "1", "1G")
    storage.approve_device("aa:bb:cc:dd:ee:02", "host2", "FAIBASE", "admin")
    storage.register_device("aa:bb:cc:dd:ee:03", "1.1.1.3", "cpu", "1", "1G")
    storage.discard_waiting_device("aa:bb:cc:dd:ee:03")

    counts = storage.count_by_status()

    assert counts == {"waiting": 1, "reboot": 1, "reinstalling": 0, "discarded": 1}


def test_count_by_class_empty_db_returns_empty_dict(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    storage.init_db()

    assert storage.count_by_class() == {}


def test_count_by_class_ignores_devices_without_classes(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    storage.init_db()
    storage.register_device("aa:bb:cc:dd:ee:01", "1.1.1.1", "cpu", "1", "1G")
    storage.register_device("aa:bb:cc:dd:ee:02", "1.1.1.2", "cpu", "1", "1G")
    storage.discard_waiting_device("aa:bb:cc:dd:ee:02")

    assert storage.count_by_class() == {}


def test_count_by_class_counts_each_token_across_devices(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    storage.init_db()
    storage.register_device("aa:bb:cc:dd:ee:01", "1.1.1.1", "cpu", "1", "1G")
    storage.approve_device("aa:bb:cc:dd:ee:01", "host1", "FAIBASE DEBIAN XORG GNOME", "admin")
    storage.register_device("aa:bb:cc:dd:ee:02", "1.1.1.2", "cpu", "1", "1G")
    storage.approve_device("aa:bb:cc:dd:ee:02", "host2", "FAIBASE DEBIAN XORG CINNAMON", "admin")
    storage.register_device("aa:bb:cc:dd:ee:03", "1.1.1.3", "cpu", "1", "1G")
    storage.approve_device("aa:bb:cc:dd:ee:03", "host3", "FAIBASE DEBIAN", "admin")

    counts = storage.count_by_class()

    assert counts == {
        "FAIBASE": 3,
        "DEBIAN": 3,
        "XORG": 2,
        "GNOME": 1,
        "CINNAMON": 1,
    }


def test_count_by_class_counts_reinstalling_devices_too(tmp_path, monkeypatch):
    monkeypatch.setenv("FAI_DISCOVERY_DB_PATH", str(tmp_path / "devices.db"))
    storage.init_db()
    storage.register_device("aa:bb:cc:dd:ee:01", "1.1.1.1", "cpu", "1", "1G")
    storage.approve_device("aa:bb:cc:dd:ee:01", "host1", "FAIBASE SERVER", "admin")
    storage.mark_reinstalling("aa:bb:cc:dd:ee:01")

    assert storage.count_by_class() == {"FAIBASE": 1, "SERVER": 1}
