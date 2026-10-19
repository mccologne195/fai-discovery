import logging
import os

# prometheus_client ist nur fuer /metrics noetig. Fehlt das Paket
# (python3-prometheus-client), soll die Webconsole trotzdem starten - sonst
# bricht sie auf einer schlanken Installation schon beim Import ab.
try:
    from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Gauge, generate_latest

    AVAILABLE = True
except ImportError:
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"
    CollectorRegistry = Gauge = generate_latest = None
    AVAILABLE = False

import storage
import version

METRICS_ENABLED_ENV = "FAI_DISCOVERY_METRICS_ENABLED"
CONTENT_TYPE = CONTENT_TYPE_LATEST
MISSING_LIBRARY_MESSAGE = (
    "Metriken sind aktiviert, aber python3-prometheus-client ist nicht installiert "
    "(apt install python3-prometheus-client)\n"
)


def enabled():
    raw = os.environ.get(METRICS_ENABLED_ENV, "")
    return raw.strip().lower() == "true"


if not AVAILABLE and enabled():
    logging.getLogger(__name__).warning(MISSING_LIBRARY_MESSAGE.strip())


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

    class_counts = storage.count_by_class()
    if class_counts:
        class_usage = Gauge(
            "fai_discovery_class_usage",
            "Anzahl aktuell installierter Geraete, die diese FAI-Klasse enthalten",
            ["class"],
            registry=registry,
        )
        for cls, count in class_counts.items():
            class_usage.labels(**{"class": cls}).set(count)

    info = Gauge(
        "fai_discovery_info",
        "Statische Versionsinformation (Wert immer 1)",
        ["version"],
        registry=registry,
    )
    info.labels(version=version.current_version() or "unknown").set(1)

    return generate_latest(registry)
