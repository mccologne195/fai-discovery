# Installation: Discovery-Client (PXE-Boot-Hook)

Meldet einen bootenden Rechner bei der Webkonsole an und wartet auf
Freigabe. Läuft **nicht** als eigener Dienst — es ist ein einzelnes
Bash-Skript, das FAI während des Discovery-Boots im NFSROOT ausführt.

## Voraussetzungen

- Funktionierender FAI-Configspace unter `/srv/fai/config` (Standardpfad,
  siehe `fai-server`-Dokumentation)
- Webkonsole (`02-webconsole/`) bereits installiert und erreichbar

## Installation

1. `01-discovery-client/fai-config/hooks/discovery` nach
   `/srv/fai/config/hooks/discovery` kopieren.
2. Den Platzhalter `__FAI_DISCOVERY_INTERNAL_URL__` in der kopierten
   Datei durch die tatsächliche URL der Webkonsole ersetzen, z. B.:

   ```bash
   sed -i "s|__FAI_DISCOVERY_INTERNAL_URL__|http://faiserver:8080|" \
       /srv/fai/config/hooks/discovery
   ```

   Diese URL muss vom **Zielrechner** aus erreichbar sein (nicht nur vom
   FAI-Server selbst) — üblicherweise Hostname oder IP des FAI-Servers,
   da die Webkonsole dort mitläuft.
3. Ausführbar machen: `chmod 755 /srv/fai/config/hooks/discovery`
4. Falls `/srv/fai/config` ein Git-Checkout ist (FAI-Konvention):
   `git -C /srv/fai/config add hooks/discovery && git -C /srv/fai/config commit`

## Aktivierung

Die `discovery`-Aktion wird nicht automatisch ausgelöst — sie muss
gezielt über die Kernel-Cmdline gesetzt werden, wenn ein neuer,
unbekannter Rechner discovered werden soll:

```bash
fai-chboot -Fv -u nfs://faiserver/srv/fai/config -a discovery <MAC>
```

Das übernimmt die Webkonsole beim Erkennen eines noch unbekannten
Rechners automatisch selbst — siehe
[`installation-webconsole.md`](installation-webconsole.md).

## Funktionsweise

Der Hook sammelt beim Ausführen:

- MAC-Adresse und IP der Default-Route
- CPU-Modell, Festplattengröße (`dmidecode`/`lsblk`), RAM-Größe (bei VMs kann hier auch 0GB stehen)
- Firmware-Typ (UEFI, falls `/sys/firmware/efi` existiert, sonst BIOS)
- Seriennummer und Hardware-UUID (`dmidecode`, falls verfügbar)

und sendet das als JSON an `POST <API_URL>/register`. Danach pollt er
`GET <API_URL>/status/<mac>` in einer Schleife, bis der Status auf
`reboot` wechselt (Freigabe erfolgt), und bootet dann neu.
