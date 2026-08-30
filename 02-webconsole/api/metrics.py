import os

from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Gauge, generate_latest

import storage
import version

METRICS_ENABLED_ENV = "FAI_DISCOVERY_METRICS_ENABLED"
CONTENT_TYPE = CONTENT_TYPE_LATEST


def enabled():
    raw = os.environ.get(METRICS_ENABLED_ENV, "")
    return raw.strip().lower() == "true"


def render():
    # Eigene Registry pro Aufruf statt des globalen Default-Registry: die
    # Werte kommen bei jedem Scrape frisch aus SQLite (aktueller Stand),
    # kein In-Process-Zustand, der bei jedem Service-Neustart zurueckspringen
    # wuerde.
    registry = CollectorRegistry()

    devices = Gauge(
        "fai_discovery_devices",
        "Aktuelle Anzahl Geraete je Status",
        ["status"],
        registry=registry,
    )
    for status, count in storage.count_by_status().items():
        devices.labels(status=status).set(count)

    info = Gauge(
        "fai_discovery_info",
        "Statische Versionsinformation (Wert immer 1)",
        ["version"],
        registry=registry,
    )
    info.labels(version=version.current_version() or "unknown").set(1)

    return generate_latest(registry)
