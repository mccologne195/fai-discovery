# Installation: Webkonsole

Die Webkonsole ist das Herzstück von fai-discovery: Flask-App, läuft als
systemd-Service auf dem FAI-Server, verwaltet wartende Geräte, Freigaben
und Admin-Accounts.

## Voraussetzungen

- Python 3 mit Flask (`pip install flask` oder Distributionspaket)
- `sudo`, `fai-chboot` (Teil von `fai-server`)
- Root-Zugriff für die Einrichtung

## Installation

### 1. System-User anlegen

```bash
useradd --system --create-home --shell /usr/sbin/nologin faidiscovery
```

### 2. Code deployen

`02-webconsole/api/` (Python-Code, Templates, `static/`) irgendwohin
kopieren, z. B. `/opt/fai-discovery/02-webconsole/api/` — der genaue Pfad
ist frei wählbar, muss aber zur `WorkingDirectory` in der systemd-Unit
(Schritt 4) passen.

### 3. `fai-chboot`-Wrapper und sudoers-Regel

Der Webkonsolen-Prozess läuft unprivilegiert als `faidiscovery` und darf
trotzdem `fai-chboot` (braucht Root) über einen schmalen, validierenden
Wrapper aufrufen:

```bash
install -o root -g root -m 755 02-webconsole/bin/fai-discovery-chboot /usr/local/bin/fai-discovery-chboot
visudo -cf 02-webconsole/etc/sudoers.d/fai-discovery   # Syntax vorab prüfen
install -o root -g root -m 0440 02-webconsole/etc/sudoers.d/fai-discovery /etc/sudoers.d/fai-discovery
```

### 4. systemd-Unit

```bash
install -o root -g root -m 644 02-webconsole/api/fai-discovery-webconsole.service /etc/systemd/system/
```

Falls der Code nicht unter `/opt/fai-discovery-repo/02-webconsole/api`
liegt, `WorkingDirectory=` in der kopierten Unit-Datei anpassen.

### 5. `site.conf`

```bash
mkdir -p /etc/fai-discovery
```

`/etc/fai-discovery/site.conf` anlegen (wird per systemd
`EnvironmentFile=` beim Start gelesen — nach jeder Änderung ist
`systemctl restart fai-discovery-webconsole` nötig):

```
FAI_DISCOVERY_PROFILE_FILE=/srv/fai/config/class/example.profile
FAI_DISCOVERY_INTERNAL_URL=http://faiserver:8080
FAI_DISCOVERY_NFS_ROOT=nfs://faiserver/srv/fai/config
```

| Variable | Pflicht | Bedeutung |
|---|---|---|
| `FAI_DISCOVERY_PROFILE_FILE` | ja | Pfad zur FAI-Profil-Datei, deren Einträge im Freigabe-Formular zur Auswahl stehen |
| `FAI_DISCOVERY_INTERNAL_URL` | ja | URL der Webkonsole, wie sie vom **Zielrechner** während der Installation erreichbar ist |
| `FAI_DISCOVERY_NFS_ROOT` | ja | An `fai-chboot -u` übergebener NFS-Root-Server. **„localhost" ist fast immer falsch** — der Zielrechner, nicht der FAI-Server, löst diese Adresse auf. Ohne gesetzten Wert schlägt jede Freigabe fehl. |
| `FAI_DISCOVERY_TYPE_PREFIXES` | nein | Kommagetrennte `Code:Label`-Paare für Typ-Präfix-Vorschläge, z. B. `NB:Notebook,DT:Desktop,SRV:Server` |
| `FAI_DISCOVERY_LOCATION_PREFIXES` | nein | Wie oben, für Standort-Präfixe |
| `FAI_DISCOVERY_DISK_CONFIG_DIR` | nein | Verzeichnis mit `disk_config`-Dateien für die automatische UEFI-Erkennung. Ohne gesetzten Wert wird der FAI-Standardpfad verwendet. |

### 6. Admin-Account

Admin-Zugänge liegen in `/etc/fai-discovery/admins.json`
(`{"username": "werkzeug-password-hash"}`, HTTP Basic Auth). Ein
funktionsfähiges Demo-Beispiel liegt unter
`02-webconsole/etc/fai-discovery/admins.json.example`:

```bash
cp 02-webconsole/etc/fai-discovery/admins.json.example /etc/fai-discovery/admins.json
chown root:faidiscovery /etc/fai-discovery/admins.json
chmod 640 /etc/fai-discovery/admins.json
```

**⚠️ Sicherheitshinweis:** Dieses Demo-Beispiel enthält den funktionierenden
Zugang `admin` / `admin`, damit die Webkonsole direkt nach dem Kopieren
erreichbar ist. **Das Passwort muss unmittelbar danach geändert werden**
— sonst kann sich jeder, der Port 8080 erreicht, damit anmelden.

Eigenen Admin anlegen bzw. Passwort ändern:

```bash
python3 -c "from werkzeug.security import generate_password_hash; print(generate_password_hash(input('Passwort: ')))"
```

Den ausgegebenen Hash in `/etc/fai-discovery/admins.json` unter dem
gewünschten Benutzernamen eintragen (auf gültiges JSON achten — kein
Komma nach dem letzten Eintrag). Änderungen wirken sofort, kein
Neustart nötig — `admins.json` wird bei jedem Request neu gelesen.

### 7. Firewall + Start

```bash
ufw allow 8080/tcp   # oder äquivalent für die eigene Firewall
systemctl daemon-reload
systemctl enable --now fai-discovery-webconsole
```

### 8. Verifikation

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080/status/aa:bb:cc:dd:ee:ff   # erwartet: 200
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080/admin/                       # erwartet: 401 (Auth erforderlich)
```

Danach im Browser `http://<faiserver>:8080/admin/` öffnen und mit dem
Admin-Account anmelden.
