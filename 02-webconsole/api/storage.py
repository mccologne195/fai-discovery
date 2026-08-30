import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def db_path():
    return Path(os.environ.get("FAI_DISCOVERY_DB_PATH", "/var/lib/fai-discovery/devices.db"))


def get_connection():
    # Schema-Erstellung passiert hier bei jedem Verbindungsaufbau (idempotent
    # dank IF NOT EXISTS, für SQLite vernachlässigbare Kosten). Dadurch
    # braucht app.py keinen expliziten init_db()-Aufruf beim Modul-Import -
    # ein solcher Aufruf würde beim reinen `import app` in Tests bereits vor
    # dem monkeypatch der Umgebungsvariable laufen und fälschlich versuchen,
    # das Produktions-Verzeichnis /var/lib/fai-discovery anzulegen.
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS devices (
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
            firmware TEXT,
            previous_hostname TEXT
        )
        """
    )
    # Migration für vor 2026-08-10 angelegte devices.db-Dateien: CREATE TABLE
    # IF NOT EXISTS legt bei bereits existierender Tabelle keine neuen
    # Spalten nach - fehlende Spalten hier defensiv nachziehen, ohne
    # bestehende Daten anzufassen.
    existing_columns = {row[1] for row in conn.execute("PRAGMA table_info(devices)").fetchall()}
    for column in ("uuid", "serial", "firmware", "previous_hostname"):
        if column not in existing_columns:
            conn.execute(f"ALTER TABLE devices ADD COLUMN {column} TEXT")
    return conn


def init_db():
    get_connection().close()


def register_device(mac, ip, cpu, ram, disk, uuid="", serial="", firmware=""):
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO devices (mac, ip, cpu, ram, disk, registered_at, status, hostname, classes, approved_by, approved_at, uuid, serial, firmware)
            VALUES (?, ?, ?, ?, ?, ?, 'waiting', NULL, NULL, NULL, NULL, ?, ?, ?)
            ON CONFLICT(mac) DO UPDATE SET
                ip = excluded.ip,
                cpu = excluded.cpu,
                ram = excluded.ram,
                disk = excluded.disk,
                registered_at = excluded.registered_at,
                status = 'waiting',
                hostname = NULL,
                classes = NULL,
                approved_by = NULL,
                approved_at = NULL,
                uuid = excluded.uuid,
                serial = excluded.serial,
                firmware = excluded.firmware,
                previous_hostname = COALESCE(hostname, previous_hostname)
            """,
            (mac, ip, cpu, ram, disk, datetime.now(timezone.utc).isoformat(), uuid, serial, firmware),
        )
        conn.commit()
    finally:
        conn.close()


def get_device(mac):
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM devices WHERE mac = ?", (mac,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_status(mac):
    record = get_device(mac)
    if record is None:
        return "waiting"
    return record["status"]


def list_waiting_devices():
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM devices WHERE status = 'waiting' ORDER BY registered_at ASC"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def mark_reinstalling(mac):
    conn = get_connection()
    try:
        cur = conn.execute(
            "UPDATE devices SET status = 'reinstalling' WHERE mac = ? AND status = 'reboot'",
            (mac,),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def list_history(query=None):
    conn = get_connection()
    try:
        sql = "SELECT * FROM devices WHERE status IN ('reboot', 'reinstalling')"
        params = []
        if query:
            escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            like_term = f"%{escaped}%"
            sql += (
                " AND ("
                "mac LIKE ? ESCAPE '\\' OR "
                "hostname LIKE ? ESCAPE '\\' OR "
                "classes LIKE ? ESCAPE '\\' OR "
                "approved_by LIKE ? ESCAPE '\\' OR "
                "uuid LIKE ? ESCAPE '\\' OR "
                "serial LIKE ? ESCAPE '\\'"
                ")"
            )
            params.extend([like_term] * 6)
        sql += " ORDER BY approved_at DESC"
        rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def approve_device(mac, hostname, classes, approved_by):
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            UPDATE devices
            SET status = 'reboot', hostname = ?, classes = ?, approved_by = ?, approved_at = ?
            WHERE mac = ?
            """,
            (hostname, classes, approved_by, datetime.now(timezone.utc).isoformat(), mac),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def delete_device(mac):
    conn = get_connection()
    try:
        cur = conn.execute(
            "DELETE FROM devices WHERE mac = ? AND status = 'reboot'",
            (mac,),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def count_by_status():
    conn = get_connection()
    try:
        counts = {"waiting": 0, "reboot": 0, "reinstalling": 0, "discarded": 0}
        rows = conn.execute("SELECT status, COUNT(*) AS n FROM devices GROUP BY status").fetchall()
        for row in rows:
            if row["status"] in counts:
                counts[row["status"]] = row["n"]
        return counts
    finally:
        conn.close()


def count_by_class():
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT classes FROM devices WHERE classes IS NOT NULL AND classes != ''"
        ).fetchall()
        counts = {}
        for row in rows:
            for cls in row["classes"].split():
                counts[cls] = counts.get(cls, 0) + 1
        return counts
    finally:
        conn.close()


def discard_waiting_device(mac):
    conn = get_connection()
    try:
        cur = conn.execute(
            "UPDATE devices SET status = 'discarded' WHERE mac = ? AND status = 'waiting'",
            (mac,),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()
