# All-in-One-FAI-Server (Installationsraum)

Ein einzelner Debian-Server, der **alles** mitbringt, was nötig ist, um Rechner per PXE zu
installieren: FAI, fai-discovery (Webkonsole mit Freigabe), `dnsmasq` als **DHCP- und
DNS-Server**, TFTP und NFS. Es braucht keine weitere Infrastruktur: keinen eigenen DHCP- oder
DNS-Server, keine eigene CA, kein Konfigurationsmanagement, keinen eigenen Mirror. Die Clients
holen ihre Pakete direkt von `deb.debian.org`.

Typischer Einsatz: ein abgetrenntes Netz ("Raum") für Installationen, eine Testumgebung oder eine
komplett neue Infrastruktur, in der der FAI-Server der erste Dienst ist.

> **Status:** Spike, am 2026-10-20 mit Debian 13 auf einer VM erfolgreich getestet (siehe
> [Getestet](#getestet)). Noch nicht abgedeckt: Server mit nur einer Netzwerkkarte samt NAT,
> Secure Boot, IPv6.

## Architektur

```
                    Internet (deb.debian.org, fai-project.org)
                         │
                  ┌──────┴──────┐
                  │   Gateway   │   Router/NAT des Raums
                  └──────┬──────┘
                         │ Raum-Netz (z. B. 192.168.77.0/24)
        ┌────────────────┼────────────────────────────────┐
        │                │                                │
 ┌──────┴───────┐  ┌─────┴──────────────────────────┐  ┌──┴───────────┐
 │ Client 1     │  │ All-in-One-FAI-Server          │  │ Client n     │
 │ (PXE, BIOS)  │  │  dnsmasq   DHCP + DNS          │  │ (PXE, UEFI)  │
 └──────────────┘  │  tftpd-hpa Bootdateien + Menü  │  └──────────────┘
                   │  NFS       NFS-Root + Config   │
                   │  fai-discovery Webkonsole :8080│
                   │  fai-monitor Fortschritt :4711 │
                   └────────────────────────────────┘
                     (optional zweite NIC: Verwaltung)
```

Ablauf für einen Client: PXE-Boot → `dnsmasq` verteilt Adresse und Bootdatei (BIOS:
`fai/pxelinux.0`, UEFI: `fai/efi64/syslinux.efi`) → Menü "Lokal booten / Discover" →
"Discover" meldet das Gerät bei der Webkonsole → der Admin vergibt Hostnamen und Profil und
gibt frei → Installation → Neustart von der Platte. `dnsmasq` trägt den gemeldeten Hostnamen
automatisch in den DNS ein, ein DDNS ist nicht nötig.

## Voraussetzungen

- Debian 13 (amd64), frisch installiert, root-Zugang, Internet für `apt`
- mindestens 2 GB RAM, 20 GB Platte (der NFS-Root braucht rund 2 GB)
- eine Netzwerkkarte für den **Raum** (`ROOM_IF`), in deren Segment **kein anderer DHCP-Server**
  läuft. Der Server bekommt dort eine feste Adresse.
- ein Gateway im Raum, damit Clients `deb.debian.org` erreichen (Router mit NAT)
- Quellen für `fai-config` und `fai-discovery`: Git-URLs **oder** Git-Bundles, falls die
  Repositories nicht öffentlich sind
- ein Konfigurations-Space (`fai-config`) mit der Klasse `NEUTRAL`, siehe
  [Neutraler Konfigurations-Space](#neutraler-konfigurations-space)

## Schnellstart

```bash
# Auf dem Server, als root
git clone <fai-discovery-Repo> && cd fai-discovery/08-installationsraum

ROOM_IF=ens19 \
CONFIG_REPO=<URL des fai-config-Repos>   CONFIG_BRANCH=main \
DISCOVERY_REPO=<URL des fai-discovery-Repos> \
./allinone-bootstrap.sh
```

Bei privaten Repositories statt `*_REPO` die Bundles übergeben (`git bundle create … main`):

```bash
ROOM_IF=ens19 CONFIG_BUNDLE=/root/fai-config.bundle CONFIG_BRANCH=main \
DISCOVERY_BUNDLE=/root/fai-discovery.bundle ./allinone-bootstrap.sh
```

Das Skript meldet jeden Schritt als `[Schritt n]` und bricht bei einem Fehler ab. Es kann
wiederholt werden (`fai-setup -f` baut den NFS-Root neu). Danach:

```bash
ROOM_IF=ens19 ./check-allinone.sh      # Dienste, Ports, DNS, Zeit, PXE-Menü prüfen
cat /root/fai-discovery-initial-admin-password.txt   # Zugang zur Webkonsole (Benutzer: admin)
```

Webkonsole: `https://<Verwaltungs-IP>/admin/` bzw. `https://<FQDN>/admin/` aus dem Raum (HTTPS über Caddy
mit eigener CA, deren Root einmalig importieren: [HOWTO-https.md, Abschnitt 8](../HOWTO-https.md#8-all-in-one-server-installationsraum)).
Mit `WEB_TLS=off` wie bisher `http://<Server>:8080/admin/`. Dann einen Client per PXE booten,
"Discover" wählen und in der Webkonsole freigeben.

## Parameter

Alle als Umgebungsvariablen. Pflicht: `ROOM_IF` und je eine Quelle für fai-config und fai-discovery.

| Variable | Standard | Bedeutung |
|---|---|---|
| `ROOM_IF` | – (Pflicht) | Netzwerkkarte des Raums |
| `ROOM_IP` | `192.168.77.2` | feste Adresse des Servers im Raum |
| `ROOM_PREFIX` / `ROOM_NET` | `24` / `192.168.77.0/24` | Raum-Netz (auch für die NFS-Exporte) |
| `ROOM_GW` | `192.168.77.1` | Gateway, wird per DHCP als Router verteilt |
| `POOL_START` / `POOL_END` | `.100` / `.200` | DHCP-Bereich |
| `DOMAIN` | `home.arpa` | Domain im Raum (RFC 8375). Ein FQDN ist nötig, weil `install.sh` einen verlangt |
| `SERVER_NAME` | aktueller Hostname | Name des Servers (wird **nicht** umbenannt) |
| `UPSTREAM_DNS` | `9.9.9.9 1.1.1.1` | Upstream für den DNS des Raums |
| `MGMT_IF` | Interface der Default-Route | Verwaltungs-NIC für die Firewall-Regeln (22, 8080, 443) |
| `WEB_TLS` | `internal` | HTTPS für die Webkonsole über Caddy mit eigener CA; `off` = nur HTTP auf 8080 |
| `DEB_MIRROR`, `DEB_SECURITY` | `http://deb.debian.org/debian[-security]` | Paketquelle; für einen eigenen Mirror ändern |
| `RELEASE` | `trixie` | Debian-Release |
| `TEST_ROOT_PW` | `fai` | Root-Passwort des NFS-Roots (nur zum Testen!) |
| `CONFIG_REPO` / `CONFIG_BUNDLE` / `CONFIG_BRANCH` | – / – / `main` | Quelle und Branch des Konfigurations-Space |
| `DISCOVERY_REPO` / `DISCOVERY_BUNDLE` | – | Quelle von fai-discovery |
| `HOOKS_DIR` | `./nfsroot-hooks` | NFS-Root-Hooks |
| `DNSMASQ_TEMPLATE` | `./dnsmasq-allinone.conf.template` | Vorlage der `dnsmasq`-Konfiguration (einzige Quelle) |
| `DNSMASQ_LEASE` | `8h` | DHCP-Lease-Zeit |
| `DNSMASQ_LOG_QUERIES` | `no` | `yes` protokolliert jede DNS-Anfrage (nur zum Debuggen, das Journal wächst sonst schnell) |

## Was das Skript tut

1. Raum-NIC statisch konfigurieren (`ifupdown`, kein Gateway auf dieser NIC)
2. FQDN in `/etc/hosts` eintragen (der Hostname bleibt)
3. Pakete installieren: `fai-server`, `nfs-kernel-server`, `tftpd-hpa`, `dnsmasq`, `systemd-timesyncd`,
   `python3-flask`, `ufw`, `git`, `caddy` (nicht bei `WEB_TLS=off`) u. a. Dienste starten dabei noch nicht.
4. `/etc/fai/` (`fai.conf`, `nfsroot.conf`, apt-Quellen) und die NFS-Root-Hooks anlegen
5. Konfigurations-Space nach `/srv/fai/config` klonen
6. Profil-Datei `class/example.profile` mit dem neutralen Profil schreiben
7. `fai-setup -v -f`: NFS-Root bauen, `fai`-Benutzer, TFTP-Baum
8. NFS-Exporte auf das Raum-Netz zuschneiden, TFTP-Optionen setzen
9. `fai-monitor` als systemd-Dienst anlegen
10. fai-discovery per `install.sh --unattended` installieren (PXE-Menü an, HTTPS im Modus `internal`)
11. Firewall (`ufw`): Raum-NIC offen, Verwaltungs-NIC nur Port 22, 8080 und 443
12. `dnsmasq` für DHCP und DNS im Raum konfigurieren und starten (aus der Vorlage, siehe [dnsmasq-Konfiguration](#dnsmasq-konfiguration))
13. Verifikation

## dnsmasq-Konfiguration

Die Konfiguration entsteht aus **einer** Vorlage, [`dnsmasq-allinone.conf.template`](dnsmasq-allinone.conf.template):
`allinone-bootstrap.sh` ersetzt die Platzhalter in `@...@`-Schreibweise aus seinen Parametern und schreibt
`/etc/dnsmasq.d/fai-room.conf`. Änderungen am Verhalten (Optionen, Bootdateien) macht man in der Vorlage.
Danach genügt:

```bash
ROOM_IF=ens19 [weitere Parameter wie beim ersten Lauf] ./allinone-bootstrap.sh dnsmasq
```

Dieser Modus schreibt nur die `dnsmasq`-Konfiguration neu, prüft sie mit `dnsmasq --test` und startet den
Dienst neu. Die vorherige Datei bleibt als `/root/fai-room.conf.vorher` erhalten und wird bei einer ungültigen
Konfiguration automatisch zurückgespielt. Bleibt in der Vorlage ein unbekannter Platzhalter stehen, bricht das
Skript ab, bevor es etwas schreibt.

Was die Konfiguration bewusst macht:

- **Nur DHCP und DNS im Raum:** `bind-interfaces` an die Raum-NIC, `no-resolv` mit festen Upstream-Servern, `local=/<Domain>/`;
  Namen aus anderen Netzen werden nicht aufgelöst.
- **Boot:** BIOS bekommt `fai/pxelinux.0`, UEFI x86-64 (`client-arch 7`) `fai/efi64/syslinux.efi`; Servername und
  Server-IP stehen ausdrücklich in `dhcp-boot`, damit `siaddr` und Option 66/67 stimmen. TFTP liefert `tftpd-hpa`.
- **`dhcp-ignore-clid`:** Leases hängen nur an der MAC-Adresse. Der Installer und das fertig installierte System melden
  unterschiedliche Client-IDs; ohne diese Option bekäme derselbe Rechner zwei Adressen und zwei Leases, und sein DNS-Name
  wanderte.
- **Hostnamen** meldet der Client per DHCP, `dnsmasq` löst sie selbst auf (kein DDNS nötig).
- **`log-queries` aus**, einschaltbar mit `DNSMASQ_LOG_QUERIES=yes`. `log-dhcp` bleibt an.

## Neutraler Konfigurations-Space

Viele FAI-Konfigurations-Spaces ziehen in ihren Basisklassen Dienste mit, die auf einer
frischen Infrastruktur nicht existieren (eigene CA, Konfigurationsmanagement, interne Mirror,
feste Benutzer). Für den Raum gibt es deshalb eine Klasse **`NEUTRAL`** (Overlay unter
[`configspace-neutral/`](configspace-neutral/)):

| Datei | Zweck |
|---|---|
| `class/NEUTRAL.var` | Pakete von `deb.debian.org`, kein APT-Proxy, kein persönlicher Benutzer, Test-Root-Passwort `fai` (Hash **vor echtem Einsatz ersetzen**) |
| `files/etc/apt/sources.list/NEUTRAL` | `sources.list` des Zielsystems (zunächst `http`, weil im frischen Zielsystem noch kein `ca-certificates` ist) |
| `package_config/NEUTRAL` | `systemd-timesyncd`: ein Minimalsystem hat sonst keine Zeitsynchronisation (Clients im Test: `System clock synchronized: no`) |
| `profile-neutral.example` | Profil "Debian 13 neutral": `Classes: INSTALL FAIBASE DEBIAN SECURE NEUTRAL` |

**`NEUTRAL` muss im Profil nach `FAIBASE` und `DEBIAN` stehen**, damit die Werte aus
`NEUTRAL.var` die der Basisklassen überschreiben. Enthält die eigene `DEBIAN`-Klasse Skripte, die
eine Infrastruktur voraussetzen (im Test war das ein Bootstrap gegen eine feste CA-Adresse), dann
am Anfang des Skripts `if ifclass NEUTRAL; then exit 0; fi` ergänzen. Bestehende Profile ohne
`NEUTRAL` bleiben unverändert.

## Betrieb

- **Dienste:** `dnsmasq`, `tftpd-hpa`, `nfs-server`, `fai-monitor`, `fai-discovery-webconsole`, `systemd-timesyncd`
- **Installationslogs:** `/var/log/fai/remote-logs/<hostname>/install-<datum>/` (`FAI_CLASSES`,
  `status.log`, `scripts.log`, `software.log`, `task_error`)
- **Fortschritt:** `/var/log/fai/fai-monitor.log` und `/admin/progress` in der Webkonsole
- **DHCP/DNS:** `journalctl -u dnsmasq` (`log-dhcp` und `log-queries` sind an), Leases in `/var/lib/misc/dnsmasq.leases`
- **Gesundheitsprüfung:** `ROOM_IF=<nic> ./check-allinone.sh`
- **Zugriff auf die Webkonsole** von außerhalb des Raums: `https://<Verwaltungs-IP>/admin/` (Caddy,
  siehe [HOWTO-https.md](../HOWTO-https.md#8-all-in-one-server-installationsraum)); mit `WEB_TLS=off` per SSH-Tunnel
  (`ssh -L 18080:127.0.0.1:8080 <Server>`)

## Getestet

Debian 13, Server und Clients als Proxmox-VMs, Raum als eigenes VLAN mit Router und NAT. Der Server
hatte eine zweite NIC im Raum (die erste diente der Verwaltung).

| Test | Ergebnis |
|---|---|
| BIOS-Client (SeaBIOS): `pxelinux.0`, Menü, Discover, Freigabe, Installation, Neustart | bestanden |
| UEFI-Client (OVMF): `syslinux.efi`, Menü, Discover, Freigabe, Installation, Neustart | bestanden |
| Pakete direkt von `deb.debian.org` (HTTP, danach HTTPS), DNS über `dnsmasq` | bestanden |
| Hostname des installierten Clients im DNS von `dnsmasq` ohne DDNS | bestanden |
| `dnsmasq` mit `dhcp-boot=…,<Name>,<IP>`: `siaddr` und Option 66/67 stimmen (Mitschnitt) | bestanden |
| Bootstrap auf frischem Server: 13 Schritte ohne manuellen Eingriff (nach zwei Korrekturen) | bestanden |

## Stolpersteine

Alles davon ist im Skript berücksichtigt, steht hier aber für alle, die es von Hand nachbauen:

1. **Konfigurations-Space vor `fai-setup` anlegen.** Sonst bricht `fai-setup` mit
   `Cannot create the config space. Please install the package fai-doc` ab.
2. **`ca-certificates` im NFS-Root.** `debootstrap` aus einer `http`-Quelle installiert es nicht,
   dann scheitert im NFS-Root jede HTTPS-Quelle (z. B. `fai-project.org`), und der NFS-Root bekommt eine
   ältere FAI-Version als der Server. Lösung: `FAI_DEBOOTSTRAP_OPTS="--exclude=info --include=ca-certificates"`.
3. **Mehrere Netzwerkkarten:** `SERVERINTERFACE=<Raum-NIC>` in `nfsroot.conf` setzen, sonst nimmt
   `fai-setup` die Adresse der falschen NIC. Die Exporte danach auf das Raum-Netz zuschneiden.
4. **Die `sources.list` des Zielsystems stammt aus dem NFS-Root**, wenn keine Klassenvariante
   von `/etc/apt/sources.list` passt (`fcopy -iSM`). `apt_cdn` in einer `.var`-Datei reicht dafür
   nicht, es braucht eine Klassenvariante (hier `files/etc/apt/sources.list/NEUTRAL`).
5. **`fai-monitor` hat keine systemd-Unit** im Paket `fai-server`. Das Skript legt eine an
   (`Type=forking`, `fai-monitor -d -l /var/log/fai/fai-monitor.log`).
6. **`class/example.profile` fehlt** in einem frischen Klon, wenn das Repository nur
   `example.profile.org` enthält. Die Webkonsole zeigt sonst "kein Profil".
7. **Klassen-Skripte in `class/` laufen als eigener Prozess**, `ifclass` gibt es dort nicht, und
   Klassen, die per Kernel-Kommandozeile (`ADDCLASSES`) kommen, sind dort noch nicht gesetzt.
   Synthetische Klassen müssen `$classes` und `$ADDCLASSES` selbst auswerten.
8. **`ufw`** (falls die Klasse `SECURE` es aktiviert): Raum-NIC komplett offen, auf der
   Verwaltungs-NIC nur 22 und 8080, sonst sperrt man sich aus.
9. **Zeit:** `systemd-timesyncd` explizit installieren. Ein Minimalsystem hat keine Zeitsynchronisation.
10. **Servername nicht ändern, wenn derselbe Name in einem anderen Netz per DDNS vergeben ist.** Ein
    gleichnamiger Eintrag würde dort überschrieben.
11. **Änderungen per SSH:** `fail2ban` sperrt nach wenigen Fehlversuchen. Mit `ControlMaster`
    nur eine Verbindung aufbauen und wiederverwenden.

## Grenzen und offene Punkte

- **Nur eine NIC / NAT:** Der Server selbst braucht eine eigene Anbindung ins Internet für `apt`.
  Ein Betrieb mit einer einzigen NIC samt NAT für die Clients ist nicht umgesetzt (im Design
  vorgesehen: `nftables`, `ip_forward` nur von der Raum-NIC zum Uplink).
- **FAI-Version:** `fai-server` aus Debian ist älter als das Paket von `fai-project.org`. Server
  und NFS-Root sollten dieselbe Version haben. Auf einem reinen Debian ohne die Quelle
  `fai-project.org` meldet das Skript einen Hinweis, richtet die Quelle aber nicht selbst ein.
- **Konfigurations-Space:** Ein öffentlich verfügbares, neutrales Gerüst gibt es noch nicht;
  `configspace-neutral/` ist nur das Overlay für einen bestehenden Konfigurations-Space.
- **Webkonsole nur HTTP**, Admin-Zugang aus einer zufällig erzeugten Datei. Für echten Betrieb
  vorschalten (Reverse Proxy mit TLS) oder auf das Raum-Netz beschränken.
- **Test-Zugangsdaten:** Root-Passwort `fai` im NFS-Root und im neutralen Profil nur zum Testen.
- Nicht geprüft: Secure Boot, IPv6, mehrere Räume, Notebooks mit WLAN-Firmware im Installer.

## Dateien

| Datei | Zweck |
|---|---|
| `allinone-bootstrap.sh` | baut den Server auf (siehe oben); `./allinone-bootstrap.sh dnsmasq` setzt nur die `dnsmasq`-Konfiguration neu |
| `check-allinone.sh` | prüft den laufenden Server, Exit-Code 0 = in Ordnung |
| `dnsmasq-allinone.conf.template` | Vorlage der `dnsmasq`-Konfiguration (einzige Quelle, vom Skript gefüllt) |
| `nfsroot-hooks/` | generische NFS-Root-Hooks (Wait-Online-Korrekturen, SSH-Generator, Known-Hosts) |
| `configspace-neutral/` | Overlay für die Klasse `NEUTRAL` |

Entwurf und Entscheidungen (Anforderungen, Abgrenzung, Risiken): Design-Dokument `2026-10-19-installationsraum-all-in-one-design.md` im internen Entwicklungs-Repository (nicht Teil des öffentlichen Mirrors).
