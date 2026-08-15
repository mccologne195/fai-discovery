# fai-discovery

Preboot-Discovery- und Zero-Touch-Provisioning-Workflow für
[FAI](https://fai-project.org/) (Fully Automatic Installation):
unbekannte Rechner melden sich beim PXE-Boot über eine Webkonsole, ein
Admin vergibt Hostname und FAI-Klassen und gibt die echte Installation
frei — ganz ohne vorherige Inventarisierung oder manuell gepflegte
MAC-Listen.

## Features

- **Webkonsole** mit Übersicht aller wartenden Rechner (Hardware-Daten,
  IP, Firmware-Typ), Freigabe-Formular, Verlauf und einfacher
  HTTP-Basic-Auth
- **Hostnamen-Vorschläge**: konfigurierbare Typ-/Standort-Präfixe
  (z. B. `NB-K-...` für Notebook in Köln) plus Vorschlag aus
  Seriennummer oder Hardware-UUID
- **Automatische UEFI-Erkennung**: wählt beim Freigeben automatisch die
  passende `_EFI`-Variante der gewählten `disk_config`-Klasse, falls
  vorhanden — kein manuelles Umschalten zwischen BIOS/UEFI-Layouts nötig
- **CLI-Fallback** zur Webkonsole für Freigaben ohne Browser
- **Portables Setup-Skript** (`install.sh`) für die Ersteinrichtung auf
  einem neuen FAI-Server

## Voraussetzungen

- Ein laufender FAI-Server (`fai-server`/`fai-client`/`fai-quickstart`,
  Debian/Ubuntu) mit funktionierendem Basis-PXE-Setup
- Ein DHCP-Server mit ISC-dhcpd-kompatiblen PXE-Boot-Optionen
  (`next-server`/`filename`) und einen DNS Server für dynamaische 
  Aktualisierung von Hostnamen und IP, z.B. [Technitium DNS](https://technitium.com/dns/)
- Python 3 mit Flask für die Webkonsole

fai-discovery erfordert **kein** bestimmtes Konfigurationsmanagement-Tool
— siehe [`docs/architecture.md`](docs/architecture.md).

## Quickstart

```bash
curl -fsSL https://raw.githubusercontent.com/<dein-github-user>/fai-discovery/main/install.sh -o install.sh
less install.sh   # vor dem Ausführen ansehen
sudo bash install.sh
```

Wer aus Sicherheitsgründen keine fremden Skripte per `curl | bash`
ausführen möchte, findet die vollständige manuelle Anleitung in
[`docs/installation-manual.md`](docs/installation-manual.md).

## Dokumentation

| Datei | Inhalt |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | Gesamtablauf, welche Komponente wo läuft |
| [`docs/installation-discovery-client.md`](docs/installation-discovery-client.md) | PXE-Boot-Hook (`01-discovery-client/`) |
| [`docs/installation-webconsole.md`](docs/installation-webconsole.md) | Webkonsole (`02-webconsole/`), Admin-Accounts, `site.conf` |
| [`docs/installation-fai-configspace.md`](docs/installation-fai-configspace.md) | Hostnamen-Auflösung während der Installation (`03-fai-configspace/`) |
| [`docs/installation-portable-setup.md`](docs/installation-portable-setup.md) | `install.sh` im Detail |
| [`docs/installation-manual.md`](docs/installation-manual.md) | Alle Schritte manuell, ohne `install.sh` auszuführen |
| [`docs/images`](docs/images) | Screenshots 

## Lizenz

[GPL-3.0](LICENSE)
