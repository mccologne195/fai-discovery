# HOWTO: Webkonsole per HTTPS (Caddy)

*English version: [HOWTO-eng-https.md](HOWTO-eng-https.md)*

Die fai-discovery-Webkonsole selbst spricht nur HTTP auf Port 8080. Für die Admin-Seiten setzt man
**Caddy** als Reverse Proxy auf denselben Server. Caddy nimmt HTTPS auf Port 443 an und reicht an
`127.0.0.1:8080` weiter. Das erledigt `install.sh` mit dem Skript `fai-discovery-tls`, gesteuert über
`/etc/fai-discovery/site.conf`.

Abschnitt 8 beschreibt den All-in-One-Server im Installationsraum (`08-installationsraum/`).

## 1. Überblick

```
 Admin-Browser ──https:443──► Caddy ──http──► 127.0.0.1:8080  Webkonsole (/admin, /approve)
                                                     ▲
 Installations-Clients ─────────http:8080────────────┘         (/register, /status, /device)
```

- **Die Installations-Clients bleiben auf `http://…:8080`.** Sie übertragen keine Passwörter. Für
  HTTPS müsste das NFS-Root jeder CA vertrauen, und ein Zertifikatsfehler würde die Anmeldung
  stillschweigend endlos wiederholen lassen.
- **Port 80 bleibt standardmäßig frei.** Caddy leitet nicht von HTTP auf HTTPS um und nutzt
  standardmäßig auch keine ACME-Challenge `http-01` (sie ist optional, siehe 4a). Auf FAI-Servern
  liegt dort oft schon ein Webserver (z. B. für `FAI_DISCOVERY_BOOT_URL`).
- **Admin-Seiten nur noch über HTTPS** (`FAI_DISCOVERY_ADMIN_HTTPS_ONLY=true`, Abschnitt 6):
  Direkte Aufrufe auf Port 8080 werden auf `https://` umgeleitet, *bevor* der Browser nach dem
  Passwort fragt. Das Passwort geht damit nie im Klartext über das Netz.
- **Schutz vor fremden Formularen (CSRF):** Er funktioniert auch hinter Caddy, weil Caddy den
  Host-Header unverändert durchreicht.

## 2. Voraussetzungen

- Debian 13 mit fai-discovery (siehe `HOWTO-neuer-faiserver.md`)
- Paket `caddy` (Debian 13: Version 2.6.2):

  ```bash
  sudo apt install caddy
  ```

  Das Paket bringt eine Standard-Caddyfile mit, die Port 80 belegen will. Läuft dort schon ein
  anderer Dienst, scheitert der erste Start von Caddy. Das ist harmlos, denn `fai-discovery-tls`
  ersetzt diese Datei (sie wird vorher gesichert).
- Ein DNS-Name für den Server (FQDN), unter dem die Admins ihn aufrufen
- Port 443 frei (oder ein anderer, siehe `FAI_DISCOVERY_TLS_PORT`)
- **Keine eigene Caddy-Konfiguration auf dem Server.** `fai-discovery-tls` übernimmt die ganze
  `/etc/caddy/Caddyfile`. Ist dort schon etwas anderes eingerichtet als der Debian-Standard, bricht
  es ab und ändert nichts. Dann bindet man die Webkonsole selbst ein (`reverse_proxy 127.0.0.1:8080`)
  und lässt `FAI_DISCOVERY_TLS_MODE` leer.

## 3. Modus wählen

| Modus | Woher kommt das Zertifikat? | Erneuerung | Passt für |
|---|---|---|---|
| `acme` | eigene ACME-CA, z. B. step-ca | automatisch | Netz mit vorhandener CA |
| `internal` | Caddys eingebaute CA | automatisch | ohne CA, z. B. All-in-One-Server |
| `files` | Zertifikat von Hand, z. B. eigene `openssl`-CA | **von Hand** | eine Root für mehrere Server, Root auf die eigene Domain beschränkt |

Die Einstellungen stehen in `/etc/fai-discovery/site.conf`. Eine kommentierte Vorlage liegt in
`02-webconsole/etc/fai-discovery/site.conf.example`.

| Variable | Bedeutung |
|---|---|
| `FAI_DISCOVERY_TLS_MODE` | `acme`, `internal`, `files`, leer/`off` = kein HTTPS |
| `FAI_DISCOVERY_TLS_HOST` | Name im Zertifikat und Ziel der Umleitung (Default: `hostname -f`) |
| `FAI_DISCOVERY_TLS_EXTRA_NAMES` | weitere Namen/IPv4-Adressen im Zertifikat, kommagetrennt |
| `FAI_DISCOVERY_TLS_PORT` | HTTPS-Port (Default `443`) |
| `FAI_DISCOVERY_TLS_ACME_CA` | nur `acme`: Directory-URL der CA |
| `FAI_DISCOVERY_TLS_ACME_CA_ROOT` | nur `acme`: Root-Zertifikat der CA (fehlt es, gilt der System-Truststore) |
| `FAI_DISCOVERY_TLS_ACME_CHALLENGE` | nur `acme`: `tls-alpn-01` (Default, nur Port 443) oder `http-01` (braucht Port 80) |
| `FAI_DISCOVERY_TLS_CERT_FILE` / `_KEY_FILE` | nur `files`: Zertifikat und Schlüssel |
| `FAI_DISCOVERY_ADMIN_HTTPS_ONLY` | `true` = Admin-Seiten nur über HTTPS (Abschnitt 6) |

## 4. Einrichten

### 4a. Modus `acme` (z. B. step-ca)

```bash
# /etc/fai-discovery/site.conf
FAI_DISCOVERY_TLS_MODE=acme
FAI_DISCOVERY_TLS_HOST=faiserver.example.com
FAI_DISCOVERY_TLS_ACME_CA=https://ca.example.com:9000/acme/acme/directory
FAI_DISCOVERY_TLS_ACME_CA_ROOT=/usr/local/share/ca-certificates/example-root.crt
```

- Die CA prüft standardmäßig per **`tls-alpn-01` auf dem HTTPS-Port**. Sie muss den Server also
  unter dem Namen aus `FAI_DISCOVERY_TLS_HOST` auf Port 443 erreichen. Das betrifft DNS, Routing
  zwischen VLANs und Firewalls auf beiden Seiten.
- **Die CA muss `tls-alpn-01` auch anbieten.** Ob sie das tut, zeigt erst der erste Versuch. Tut sie
  es nicht, steht in `journalctl -u caddy` z. B.
  `no solvers available … (configured=[tls-alpn-01] offered=[dns-01 http-01])`. Bei step-ca ergänzt
  man die Challenge in der `challenges`-Liste des ACME-Provisioners (`ca.json`) und lädt die CA neu:

  ```json
  { "type": "ACME", "name": "acme", "challenges": ["http-01", "dns-01", "tls-alpn-01"] }
  ```

  Mit aktivierter Remote-Verwaltung geht es auch so:
  `step ca provisioner update acme --challenge http-01 --challenge dns-01 --challenge tls-alpn-01`.
- **Alternative `http-01`:** `FAI_DISCOVERY_TLS_ACME_CHALLENGE=http-01`. Dann muss Port 80 auf dem
  FAI-Server frei sein, weil Caddy ihn für die Challenge belegt. `install.sh` öffnet ihn in `ufw`.
  Läuft dort schon ein Webserver (z. B. für `FAI_DISCOVERY_BOOT_URL`), geht nur `tls-alpn-01`.
- Jeder Name in `FAI_DISCOVERY_TLS_EXTRA_NAMES` muss genauso prüfbar sein. IP-Adressen lieber
  weglassen.

### 4b. Modus `internal` (Caddys eingebaute CA)

```bash
# /etc/fai-discovery/site.conf
FAI_DISCOVERY_TLS_MODE=internal
FAI_DISCOVERY_TLS_HOST=faiserver.example.com
FAI_DISCOVERY_TLS_EXTRA_NAMES=192.0.2.10      # optional, z. B. für den Aufruf per IP
```

Caddy legt beim ersten Start selbst eine Root-CA an und stellt die Server-Zertifikate daraus aus.
Sie sind kurzlebig und werden automatisch erneuert. Die Root muss **einmal** auf jedem
Admin-Rechner importiert werden (Abschnitt 5). Sie liegt hier:

```
/var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt
```

Gut zu wissen:

- Jeder Server hat seine **eigene** Root. Bei zwei FAI-Servern importiert man zwei Roots.
- Wird der Server neu installiert oder `/var/lib/caddy` gelöscht, entsteht eine **neue** Root.
- Diese Root lässt sich nicht auf die eigene Domain beschränken. Wer root auf dem FAI-Server hat,
  könnte damit Zertifikate für beliebige Namen ausstellen, denen die importierenden Browser
  vertrauen. Deshalb nur auf den Admin-Rechnern importieren. Wem das zu weit geht: Modus `files`
  mit einer beschränkten Root (4c).

### 4c. Modus `files` (eigene CA von Hand)

Lohnt sich, wenn **eine** Root für mehrere Server gelten soll oder die Root auf die eigene Domain
beschränkt sein soll. Die CA erstellt man auf einem Admin-Rechner, nicht auf dem FAI-Server.

```bash
# 1. Root-CA, einmalig. homelab-root.key danach offline aufbewahren.
openssl req -x509 -new -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -nodes \
  -keyout homelab-root.key -out homelab-root.crt -days 3650 \
  -subj "/CN=Homelab Root CA" \
  -addext "basicConstraints=critical,CA:TRUE,pathlen:0" \
  -addext "keyUsage=critical,keyCertSign,cRLSign" \
  -addext "nameConstraints=critical,permitted;DNS:example.com"

# 2. Server-Zertifikat, pro FAI-Server
openssl req -new -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -nodes \
  -keyout faiserver.key -out faiserver.csr -subj "/CN=faiserver.example.com"
openssl x509 -req -in faiserver.csr -CA homelab-root.crt -CAkey homelab-root.key \
  -CAcreateserial -out faiserver.crt -days 397 -extfile <(printf '%s\n' \
  "subjectAltName=DNS:faiserver.example.com" \
  "extendedKeyUsage=serverAuth" \
  "keyUsage=critical,digitalSignature" \
  "basicConstraints=CA:FALSE")
```

- **`nameConstraints`:** Die Root darf nur Zertifikate für `example.com` und darunter ausstellen.
  Selbst mit dem Root-Schlüssel lässt sich kein gültiges Zertifikat für fremde Seiten erzeugen.
  Ruft man den Server auch per IP auf, braucht die Root zusätzlich `permitted;IP:<Netz>/<Maske>`
  und das Server-Zertifikat `IP:<Adresse>` im `subjectAltName`.
- **`subjectAltName` ist Pflicht:** Browser werten den CN nicht mehr aus.
- **Laufzeit höchstens 825 Tage:** macOS/Safari verlangt das auch bei privaten CAs. Mit 397 Tagen
  ist man überall auf der sicheren Seite. Den Termin für die Erneuerung im Kalender notieren.

Dateien auf den FAI-Server bringen. Der Schlüssel muss für den Dienstbenutzer `caddy` lesbar sein:

```bash
sudo install -d -m 750 -o root -g caddy /etc/caddy/certs
sudo install -m 644 -o root -g caddy faiserver.crt /etc/caddy/certs/
sudo install -m 640 -o root -g caddy faiserver.key /etc/caddy/certs/
```

```bash
# /etc/fai-discovery/site.conf
FAI_DISCOVERY_TLS_MODE=files
FAI_DISCOVERY_TLS_HOST=faiserver.example.com
FAI_DISCOVERY_TLS_CERT_FILE=/etc/caddy/certs/faiserver.crt
FAI_DISCOVERY_TLS_KEY_FILE=/etc/caddy/certs/faiserver.key
```

Zum Erneuern Schritt 2 wiederholen, die Dateien ersetzen und `sudo systemctl reload caddy` ausführen.

### 4d. Übernehmen

`install.sh` erneut ausführen. Es verteilt `fai-discovery-tls`, schreibt `/etc/caddy/Caddyfile`
(nach Prüfung mit `caddy validate`), startet Caddy und öffnet den HTTPS-Port in `ufw`. Wer nur an den
TLS-Einstellungen etwas ändert, kann stattdessen direkt das Skript aufrufen:

```bash
sudo /usr/local/bin/fai-discovery-tls
```

Das Skript ist idempotent. Bei ungültigen Werten oder einer Caddyfile, die nicht von ihm stammt,
bricht es ab und ändert nichts.

## 5. Root-Zertifikat auf den Admin-Rechnern importieren

Nur nötig für `internal` und `files`, und für `acme`, falls die CA dort noch nicht bekannt ist.
Zuerst den Fingerabdruck notieren und nach dem Kopieren vergleichen:

```bash
sudo openssl x509 -in /var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt \
  -noout -subject -fingerprint -sha256
```

| System | Import |
|---|---|
| macOS | `sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain root.crt` |
| Debian/Ubuntu | nach `/usr/local/share/ca-certificates/<name>.crt` kopieren, dann `sudo update-ca-certificates` |
| Windows | `certutil -addstore -f Root root.crt` (als Administrator) |
| Firefox | eigener Zertifikatsspeicher: Einstellungen → Zertifikate → Zertifizierungsstellen → Importieren, oder `security.enterprise_roots.enabled` auf `true` |

Ein Klick auf „Website trotzdem besuchen“ im Browser ersetzt den Import der Root nicht. Die Ausnahme
gilt nur für das gerade gezeigte Server-Zertifikat. Im Modus `internal` tauscht Caddy dieses etwa alle
12 Stunden aus, und die Warnung kommt wieder.

## 6. Admin-Seiten nur noch über HTTPS

Erst einschalten, wenn `https://<FAI_DISCOVERY_TLS_HOST>/admin/` im Browser funktioniert:

```bash
# /etc/fai-discovery/site.conf
FAI_DISCOVERY_ADMIN_HTTPS_ONLY=true
```

```bash
sudo systemctl restart fai-discovery-webconsole
```

Danach:

- `GET /admin/...` und `HEAD /admin/...` auf Port 8080 → `308` nach
  `https://<FAI_DISCOVERY_TLS_HOST>[:Port]/admin/...`, ohne Passwortabfrage.
- `POST /admin/...` und `/approve` auf Port 8080 → `403 Nur ueber HTTPS erreichbar`.
- `/register`, `/status`, `/device` und `/metrics` bleiben auf Port 8080 unverändert.
- Skripte wie `fai-discovery-approve.sh` brauchen die `https://`-Adresse.
- Erkannt wird der Proxy daran, dass die Anfrage über die Loopback-Adresse kommt. Caddy muss also
  auf demselben Server laufen. `X-Forwarded-For` wird bewusst nicht ausgewertet.

### Firewall: Port 8080 bleibt offen

Port 8080 **nicht schließen.** Die Installations-Clients sprechen die Webkonsole weiter über
`http://…:8080` an (`FAI_DISCOVERY_INTERNAL_URL`: `/register`, `/status`, `/device`). Ist der Port zu,
meldet sich kein Gerät mehr an: Der Discovery-Hook versucht es endlos weiter, und bei der Installation
fällt der Hostname auf den DHCP-Wert zurück. Für Admins ist 8080 mit `FAI_DISCOVERY_ADMIN_HTTPS_ONLY`
unkritisch (Umleitung vor der Passwortabfrage, POST wird abgelehnt).

Was geht: 8080 auf die Netze beschränken, aus denen Geräte installiert werden. Nicht auf einzelne
Adressen, denn die Clients bekommen ihre Adresse per DHCP. Beispiel mit zwei Installationsnetzen:

```bash
sudo ufw allow from 192.0.2.0/24 to any port 8080 proto tcp
sudo ufw allow from 198.51.100.0/24 to any port 8080 proto tcp
sudo ufw delete allow 8080/tcp               # die bisherige Regel "Anywhere" entfernen
sudo ufw status | grep 8080
```

Danach eine Discovery mit einem echten Gerät aus jedem Netz testen. Wichtig: `install.sh` führt bei
jedem Lauf `ufw allow 8080/tcp` aus und öffnet den Port damit wieder für alle. Nach jedem
`install.sh`-Lauf die Regel "Anywhere" erneut entfernen. Wer `/metrics` (`FAI_DISCOVERY_METRICS_ENABLED`)
von einem Prometheus-Server abfragt, muss dessen Adresse ebenfalls freigeben.

Port 443 muss für die Admin-Rechner offen sein, bei `acme` zusätzlich für die CA. Bei
`FAI_DISCOVERY_TLS_ACME_CHALLENGE=http-01` braucht die CA außerdem Port 80, auch für jede spätere
Erneuerung. Diesen Port also nicht schließen.

## 7. Prüfen

```bash
H=faiserver.example.com
curl -s  -o /dev/null -w "%{http_code}\n" http://localhost:8080/status/aa:bb:cc:dd:ee:ff  # 200 (Clients)
curl -s  -o /dev/null -w "%{http_code}\n" https://$H/admin/                              # 401 (über Caddy)
curl -s  -o /dev/null -w "%{http_code} %{redirect_url}\n" http://$H:8080/admin/          # 308 https://… (mit HTTPS_ONLY)
openssl s_client -connect $H:443 -servername $H </dev/null 2>/dev/null \
  | openssl x509 -noout -issuer -subject -enddate                                       # wer hat ausgestellt?
sudo ss -tlnp | grep caddy                                                               # nur :443 und 127.0.0.1:2019
```

`curl` ohne `-k` klappt nur, wenn der aufrufende Rechner der Root vertraut. Unter macOS nutzt `curl`
unter Umständen einen anderen Zertifikatsspeicher als Safari; `--cacert root.crt` prüft direkt gegen
die Root. `127.0.0.1:2019` ist
Caddys lokale Admin-Schnittstelle (nur lokal erreichbar).

## 8. All-in-One-Server (Installationsraum)

`08-installationsraum/allinone-bootstrap.sh` richtet HTTPS **standardmäßig** im Modus `internal`
ein, denn ein Installationsraum hat in der Regel keine eigene CA.

### Was der Bootstrap erledigt

- Installiert `caddy`, nur mit HTTPS. Mit `WEB_TLS=off` unterbleibt das, damit die
  Standard-Caddyfile nicht beim nächsten Boot Port 80 belegt.
- Ergänzt `site.conf` um:

  ```
  FAI_DISCOVERY_TLS_MODE=internal
  FAI_DISCOVERY_TLS_HOST=<SERVER_NAME>.<DOMAIN>
  FAI_DISCOVERY_TLS_EXTRA_NAMES=<ROOM_IP>,<Verwaltungs-IP>
  FAI_DISCOVERY_ADMIN_HTTPS_ONLY=true
  ```

  Das Zertifikat gilt damit für den FQDN (im Raum per `dnsmasq` auflösbar), die Raum-IP und die
  Adresse der Verwaltungs-NIC (`MGMT_IF`). Die Webkonsole ist so ohne DNS-Eintrag im
  Verwaltungsnetz erreichbar.
- Öffnet in `ufw` auf der Verwaltungs-NIC zusätzlich Port 443. Die Raum-NIC ist ohnehin offen.

  Port 8080 brauchen nur die Clients im Raum, und die Raum-NIC ist komplett offen. Aus dem
  Verwaltungsnetz ist 8080 mit HTTPS also überflüssig. Es ist trotzdem offen, weil der Bootstrap es auf
  der Verwaltungs-NIC freigibt und `install.sh` zusätzlich `ufw allow 8080/tcp` für alle setzt. Wer das
  schließen will:

  ```bash
  sudo ufw delete allow in on <MGMT_IF> to any port 8080 proto tcp
  sudo ufw delete allow 8080/tcp
  sudo ufw status verbose                      # Raum-NIC: alles erlaubt, Verwaltung: 22 und 443
  ```

  Nach jedem erneuten Bootstrap oder `install.sh`-Lauf wiederholen.
- Zeigt zum Schluss die HTTPS-Adressen und den Pfad zur Root an.

### Nach dem Bootstrap

1. Root holen und auf dem Admin-Rechner importieren (Abschnitt 5). Die Datei gehört dem Benutzer
   `caddy`, deshalb erst auf dem Server lesbar kopieren:

   ```bash
   # auf dem Server
   sudo install -m 644 /var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt /tmp/fai-room-root.crt
   # auf dem Admin-Rechner
   scp <Server>:/tmp/fai-room-root.crt .
   ```

2. Webkonsole öffnen: `https://<Verwaltungs-IP>/admin/` (oder `https://<FQDN>/admin/` aus dem Raum).
   Zugangsdaten: `/root/fai-discovery-initial-admin-password.txt`.
3. Ein SSH-Tunnel ist nicht mehr nötig. Wer ihn trotzdem nutzt: `ssh -L 8443:127.0.0.1:443 <Server>`
   und dann `https://<FQDN>:8443` mit einem Eintrag `127.0.0.1 <FQDN>` in der lokalen `/etc/hosts`.
   Über `127.0.0.1:8080` direkt ginge es auch, weil das als lokaler Zugriff gilt, dann aber
   unverschlüsselt bis zum Tunnel.

### Varianten

- **Ohne HTTPS:** `WEB_TLS=off ./allinone-bootstrap.sh`. Webkonsole wie bisher unter
  `http://<Server>:8080/admin/`.
- **Eigene Root statt Caddys CA** (z. B. dieselbe Root für mehrere Räume): Zertifikat nach 4c
  erzeugen, in `site.conf` auf `files` umstellen und `sudo /usr/local/bin/fai-discovery-tls`
  ausführen.
- **Raum-Server mit Zugang zu einer ACME-CA:** in `site.conf` auf `acme` umstellen (4a). Die CA muss
  den Server dann auf Port 443 erreichen (bzw. auf Port 80 bei `http-01`).
- **Neuaufbau:** Ein erneuter Bootstrap auf demselben Server behält `/var/lib/caddy` und damit die
  Root. Nach einer Neuinstallation des Betriebssystems ist die Root neu und muss neu importiert
  werden.

## 9. Zurück zu HTTP

```bash
# /etc/fai-discovery/site.conf: FAI_DISCOVERY_TLS_MODE leeren oder auf off setzen,
# FAI_DISCOVERY_ADMIN_HTTPS_ONLY entfernen
sudo /usr/local/bin/fai-discovery-tls        # stellt die gesicherte Caddyfile wieder her, stoppt Caddy
sudo systemctl restart fai-discovery-webconsole
sudo ufw delete allow 443/tcp
```

## 10. Fehlersuche

| Symptom | Ursache / Abhilfe |
|---|---|
| `fai-discovery-tls: FEHLER: /etc/caddy/Caddyfile ist weder von fai-discovery-tls noch der Debian-Standard` | Eigene Caddy-Konfiguration vorhanden: diese selbst um `reverse_proxy 127.0.0.1:8080` ergänzen, `FAI_DISCOVERY_TLS_MODE` leer lassen |
| `caddy validate ist fehlgeschlagen` | Ausgabe darüber lesen; die alte Caddyfile bleibt aktiv |
| Browser: „Verbindung nicht sicher“ | Root nicht importiert (Abschnitt 5), oder Aufruf unter einem Namen/einer IP, die nicht im Zertifikat steht (`FAI_DISCOVERY_TLS_EXTRA_NAMES`) |
| `acme`: kein Zertifikat, Seite lädt nicht | `journalctl -u caddy`: CA nicht erreichbar, Root fehlt (`FAI_DISCOVERY_TLS_ACME_CA_ROOT`), oder die CA erreicht den Server nicht auf Port 443 (`tls-alpn-01`) |
| `acme`: `no solvers available … offered=[dns-01 http-01]` | CA bietet kein `tls-alpn-01` an: in der CA freischalten (4a) oder `FAI_DISCOVERY_TLS_ACME_CHALLENGE=http-01`, wenn Port 80 frei ist |
| Caddy startet nicht, `address already in use` | Port belegt: `sudo ss -tlnp \| grep :443`, sonst `FAI_DISCOVERY_TLS_PORT` setzen |
| `403 Nur ueber HTTPS erreichbar` | Formular oder Skript spricht noch Port 8080 an; `https://`-Adresse nutzen |
| `403 Anfrage von fremder Seite abgelehnt` | Origin-Header passt nicht zum Host, z. B. ein weiterer Proxy davor, der den Host-Header umschreibt |
| Admin-Seiten lassen sich nicht mehr öffnen | `FAI_DISCOVERY_ADMIN_HTTPS_ONLY` vor funktionierendem HTTPS gesetzt: Zeile entfernen, Webkonsole neu starten |
