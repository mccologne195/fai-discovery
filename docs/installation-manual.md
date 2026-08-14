# Manuelle Installation (ohne `install.sh`)

Alle Schritte, die `install.sh` automatisiert, hier einzeln zum
Nachvollziehen und selbst Ausführen — für alle, die aus
Sicherheitsgründen keine fremden Skripte per `curl | bash` laufen lassen
wollen. Jeder Befehl ist eigenständig verständlich; nichts davon braucht
das Skript.

Voraussetzung: ein laufender FAI-Server (`/srv/fai/config` existiert und
ist ein Git-Checkout), Root-Zugriff.

## 1. Repository beziehen

```bash
git clone https://github.com/<dein-github-user>/fai-discovery.git /opt/fai-discovery-repo
cd /opt/fai-discovery-repo
```

(Ein vollständiger Klon reicht für die manuelle Installation — der
Sparse-Checkout in `install.sh` ist nur eine Optimierung.)

## 2. System-User

```bash
useradd --system --create-home --shell /usr/sbin/nologin faidiscovery
```

## 3. `fai-chboot`-Wrapper und sudoers-Regel

```bash
install -o root -g root -m 755 02-webconsole/bin/fai-discovery-chboot /usr/local/bin/fai-discovery-chboot
visudo -cf 02-webconsole/etc/sudoers.d/fai-discovery
install -o root -g root -m 0440 02-webconsole/etc/sudoers.d/fai-discovery /etc/sudoers.d/fai-discovery
```

## 4. systemd-Unit für die Webkonsole

```bash
install -o root -g root -m 644 02-webconsole/api/fai-discovery-webconsole.service /etc/systemd/system/
```

Standardmäßig erwartet die Unit den Code unter
`/opt/fai-discovery-repo/02-webconsole/api` (passend zu Schritt 1). Bei
abweichendem Pfad `WorkingDirectory=` in der kopierten Datei anpassen.

## 5. `site.conf`

```bash
mkdir -p /etc/fai-discovery
cat > /etc/fai-discovery/site.conf <<'EOF'
FAI_DISCOVERY_PROFILE_FILE=/srv/fai/config/class/example.profile
FAI_DISCOVERY_INTERNAL_URL=http://faiserver:8080
FAI_DISCOVERY_NFS_ROOT=nfs://faiserver/srv/fai/config
EOF
chmod 644 /etc/fai-discovery/site.conf
```

Werte anpassen: `FAI_DISCOVERY_PROFILE_FILE` auf die eigene FAI-Profil-Datei,
`FAI_DISCOVERY_INTERNAL_URL`/`FAI_DISCOVERY_NFS_ROOT` auf Hostname oder IP
des eigenen FAI-Servers (**nicht** `localhost` — beide Werte müssen vom
Zielrechner aus auflösbar sein, siehe
[`installation-webconsole.md`](installation-webconsole.md) für alle
verfügbaren Variablen).

## 6. Admin-Account

```bash
cp 02-webconsole/etc/fai-discovery/admins.json.example /etc/fai-discovery/admins.json
chown root:faidiscovery /etc/fai-discovery/admins.json
chmod 640 /etc/fai-discovery/admins.json
```

**⚠️ Enthält den Demo-Zugang `admin`/`admin`.** Sofort danach eigenes
Passwort setzen:

```bash
python3 -c "from werkzeug.security import generate_password_hash; print(generate_password_hash(input('Passwort: ')))"
```

Ausgegebenen Hash in `/etc/fai-discovery/admins.json` unter `"admin"`
eintragen (oder eigenen Benutzernamen verwenden) — gültiges JSON prüfen,
kein Komma nach dem letzten Eintrag.

## 7. Discovery-Client-Hook und Hostnamen-Auflösung deployen

```bash
sed "s|__FAI_DISCOVERY_INTERNAL_URL__|http://faiserver:8080|" \
    01-discovery-client/fai-config/hooks/discovery > /srv/fai/config/hooks/discovery
chown root:root /srv/fai/config/hooks/discovery
chmod 755 /srv/fai/config/hooks/discovery

sed "s|__FAI_DISCOVERY_INTERNAL_URL__|http://faiserver:8080|" \
    03-fai-configspace/fai-config/class/02-set-hostname.sh > /srv/fai/config/class/02-set-hostname.sh
chown root:root /srv/fai/config/class/02-set-hostname.sh
chmod 755 /srv/fai/config/class/02-set-hostname.sh
```

Denselben Wert wie `FAI_DISCOVERY_INTERNAL_URL` aus Schritt 5 einsetzen.
Falls `/srv/fai/config` ein Git-Checkout ist:

```bash
git -C /srv/fai/config add hooks/discovery class/02-set-hostname.sh
git -C /srv/fai/config commit -m "fai-discovery: manuelles Deployment"
git -C /srv/fai/config push
```

## 8. Firewall und Dienst starten

```bash
ufw allow 8080/tcp   # oder äquivalent für die eigene Firewall
systemctl daemon-reload
systemctl enable --now fai-discovery-webconsole
```

## 9. Verifizieren

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080/status/aa:bb:cc:dd:ee:ff   # erwartet: 200
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080/admin/                       # erwartet: 401
```

Im Browser `http://<faiserver>:8080/admin/` öffnen und mit dem
Admin-Account anmelden — fertig.
