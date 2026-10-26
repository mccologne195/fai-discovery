#!/bin/bash
set -euo pipefail

UNATTENDED=0
if [ "${1:-}" = "--unattended" ]; then
    UNATTENDED=1
fi
if [ "$UNATTENDED" -eq 1 ]; then
    export GIT_TERMINAL_PROMPT=0
fi

REPO_URL="https://github.com/mccologne195/fai-discovery.git"
REPO_DIR="/opt/fai-discovery-repo"
FAI_CONFIG_DIR="/srv/fai/config"
SITE_CONF="/etc/fai-discovery/site.conf"
ADMINS_FILE="/etc/fai-discovery/admins.json"

log() { echo "==> $*"; }
die() { echo "FEHLER: $*" >&2; exit 1; }

# --- Schritt 1: Root-Check ---
if [ "$EUID" -ne 0 ]; then
    die "Dieses Skript muss als root laufen (sudo)."
fi

if [[ "$REPO_URL" == *"<"*">"* ]]; then
    die "REPO_URL ist noch der Platzhalter '$REPO_URL' - vor dem Ausführen am Skriptanfang auf die eigene Fork-/Mirror-URL anpassen."
fi

# --- Schritt 2: System-User ---
if id faidiscovery &>/dev/null; then
    log "User 'faidiscovery' existiert bereits, überspringe."
else
    log "Lege System-User 'faidiscovery' an."
    useradd --system --create-home --shell /usr/sbin/nologin faidiscovery
fi

# --- Schritt 3: Sparse-Checkout ---
# Deckt alle drei Verzeichnisse ab, aus denen Dateien deployt werden
# (02-webconsole: App-Code; 01-discovery-client + 03-fai-configspace:
# Configspace-Dateien fürs fai-config.git-Checkout).
if [ -d "$REPO_DIR/.git" ] && [ -f "$REPO_DIR/.git/info/sparse-checkout" ]; then
    log "Repo-Checkout existiert bereits und ist vollständig konfiguriert, aktualisiere."
    git -C "$REPO_DIR" pull
    git -C "$REPO_DIR" sparse-checkout set 02-webconsole 01-discovery-client 03-fai-configspace
else
    if [ -d "$REPO_DIR" ]; then
        log "Unvollständigen/vorherigen Checkout-Rest unter $REPO_DIR gefunden, entferne ihn vor Neuanlage."
        rm -rf "$REPO_DIR"
    fi
    log "Klone $REPO_URL nach $REPO_DIR (Sparse-Checkout)."
    git clone --filter=blob:none --no-checkout "$REPO_URL" "$REPO_DIR"
    git -C "$REPO_DIR" sparse-checkout init --cone
    git -C "$REPO_DIR" sparse-checkout set 02-webconsole 01-discovery-client 03-fai-configspace
    git -C "$REPO_DIR" checkout main
fi

# Repo gehört root (per install.sh/sudo geklont), der Webkonsolen-Service
# laeuft aber als eigener User "faidiscovery" - ohne diesen Eintrag
# verweigert git seit der "dubious ownership"-Pruefung (CVE-2022-24765)
# jeden Zugriff aus einem anderen User heraus (u.a. "git describe" fuer
# die Versionsanzeige in der Fusszeile). Systemweit statt nur fuer einen
# User, damit es unabhaengig vom Service-User-Namen funktioniert.
if ! git config --system --get-all safe.directory 2>/dev/null | grep -qxF "$REPO_DIR"; then
    git config --system --add safe.directory "$REPO_DIR"
fi

# --- Schritt 4: Prompts + admins.json/site.conf ---
if [ "$UNATTENDED" -eq 0 ]; then
    [ -e /dev/tty ] || die "Keine Konsole verfügbar - install.sh erst herunterladen, dann ausführen (siehe HOWTO-new-faiserver.md, Abschnitt 2)."
    exec 3</dev/tty
fi

mkdir -p /etc/fai-discovery

if [ -f "$ADMINS_FILE" ] && python3 -c "
import json, sys
try:
    data = json.load(open(sys.argv[1]))
except (FileNotFoundError, json.JSONDecodeError):
    sys.exit(1)
sys.exit(0 if data else 1)
" "$ADMINS_FILE" 2>/dev/null; then
    log "$ADMINS_FILE existiert bereits und enthält mindestens einen Admin, überspringe."
elif [ "$UNATTENDED" -eq 1 ]; then
    log "Unattended-Modus: generiere Admin-Account automatisch."
    admin_user="admin"
    admin_password=$(openssl rand -base64 24)
    password_hash=$(printf '%s' "$admin_password" | python3 -c "
import sys
from werkzeug.security import generate_password_hash
print(generate_password_hash(sys.stdin.read()))
")
    python3 -c "
import json, sys
path, user, pwhash = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    data = json.load(open(path))
except (FileNotFoundError, json.JSONDecodeError):
    data = {}
data[user] = pwhash
with open(path, 'w') as f:
    json.dump(data, f, indent=2)
    f.write('\n')
" "$ADMINS_FILE" "$admin_user" "$password_hash"
    # umask nur in der Subshell: sonst gilt 077 fuer den ganzen Rest des
    # Skripts, und spaeter angelegte Verzeichnisse waeren nur fuer root lesbar.
    ( umask 077
      printf 'Benutzername: %s\nPasswort: %s\n' "$admin_user" "$admin_password" \
          > /root/fai-discovery-initial-admin-password.txt )
    chmod 600 /root/fai-discovery-initial-admin-password.txt
    log "Admin-Account '$admin_user' automatisch angelegt. Passwort steht einmalig in /root/fai-discovery-initial-admin-password.txt."
else
    log "Kein Admin-Account gefunden, lege einen an."
    read -r -u 3 -p "Admin-Benutzername: " admin_user
    while [ -z "$admin_user" ]; do
        read -r -u 3 -p "Benutzername darf nicht leer sein, erneut eingeben: " admin_user
    done
    read -r -s -u 3 -p "Passwort für '$admin_user': " admin_password
    echo
    while [ -z "$admin_password" ]; do
        read -r -s -u 3 -p "Passwort darf nicht leer sein, erneut eingeben: " admin_password
        echo
    done
    password_hash=$(printf '%s' "$admin_password" | python3 -c "
import sys
from werkzeug.security import generate_password_hash
print(generate_password_hash(sys.stdin.read()))
")
    python3 -c "
import json, sys
path, user, pwhash = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    data = json.load(open(path))
except (FileNotFoundError, json.JSONDecodeError):
    data = {}
data[user] = pwhash
with open(path, 'w') as f:
    json.dump(data, f, indent=2)
    f.write('\n')
" "$ADMINS_FILE" "$admin_user" "$password_hash"
    log "Admin-Account '$admin_user' angelegt."
fi
chown root:faidiscovery "$ADMINS_FILE"
chmod 640 "$ADMINS_FILE"

if [ -f "$SITE_CONF" ] && grep -q '^FAI_DISCOVERY_PROFILE_FILE=' "$SITE_CONF" && grep -q '^FAI_DISCOVERY_INTERNAL_URL=' "$SITE_CONF" && grep -q '^FAI_DISCOVERY_NFS_ROOT=' "$SITE_CONF"; then
    log "$SITE_CONF existiert bereits und enthält beide Werte, überspringe."
elif [ "$UNATTENDED" -eq 1 ]; then
    log "Unattended-Modus: verwende Standardwerte für $SITE_CONF."
    profile_file="/srv/fai/config/class/example.profile"
    internal_url="http://$(hostname -f):8080"
    case "$internal_url" in
        http://*.*:8080) ;;
        *) die "hostname -f lieferte keinen vollqualifizierten Hostnamen ('$(hostname -f)') - FAI_DISCOVERY_INTERNAL_URL kann im Unattended-Modus nicht sicher gesetzt werden." ;;
    esac
    nfs_root="nfs://$(hostname -f)$FAI_CONFIG_DIR"

    cat > "$SITE_CONF" <<EOF
FAI_DISCOVERY_PROFILE_FILE=$profile_file
FAI_DISCOVERY_INTERNAL_URL=$internal_url
FAI_DISCOVERY_NFS_ROOT=$nfs_root
EOF
    chmod 644 "$SITE_CONF"
    log "$SITE_CONF geschrieben (Standardwerte)."
else
    log "Lege $SITE_CONF an."
    default_profile="/srv/fai/config/class/example.profile"
    read -r -u 3 -p "Pfad zur FAI-Profil-Datei [$default_profile]: " profile_file
    profile_file="${profile_file:-$default_profile}"

    default_internal_url="http://$(hostname -f):8080"
    read -r -u 3 -p "Interne URL der Webkonsole (für 02-set-hostname.sh) [$default_internal_url]: " internal_url
    internal_url="${internal_url:-$default_internal_url}"

    default_nfs_root="nfs://$(hostname -f)$FAI_CONFIG_DIR"
    read -r -u 3 -p "NFS-Root-Server für die FAI-Installation [$default_nfs_root]: " nfs_root
    nfs_root="${nfs_root:-$default_nfs_root}"

    cat > "$SITE_CONF" <<EOF
FAI_DISCOVERY_PROFILE_FILE=$profile_file
FAI_DISCOVERY_INTERNAL_URL=$internal_url
FAI_DISCOVERY_NFS_ROOT=$nfs_root
EOF
    chmod 644 "$SITE_CONF"
    log "$SITE_CONF geschrieben."
fi

# --- Schritt 5: Dateien verteilen ---
log "Verteile fai-discovery-chboot Wrapper."
install -o root -g root -m 755 "$REPO_DIR/02-webconsole/bin/fai-discovery-chboot" /usr/local/bin/fai-discovery-chboot

log "Verteile sudoers-Regel."
visudo -cf "$REPO_DIR/02-webconsole/etc/sudoers.d/fai-discovery" || die "sudoers-Syntaxprüfung fehlgeschlagen, Datei wurde NICHT übernommen."
install -o root -g root -m 0440 "$REPO_DIR/02-webconsole/etc/sudoers.d/fai-discovery" /etc/sudoers.d/fai-discovery

log "Verteile systemd-Unit."
install -o root -g root -m 644 "$REPO_DIR/02-webconsole/api/fai-discovery-webconsole.service" /etc/systemd/system/fai-discovery-webconsole.service

log "Verteile Configspace-Dateien nach $FAI_CONFIG_DIR."
[ -d "$FAI_CONFIG_DIR/.git" ] || die "$FAI_CONFIG_DIR ist kein Git-Repository. Lokal anlegen: git -C $FAI_CONFIG_DIR init -b main && git -C $FAI_CONFIG_DIR add -A && git -C $FAI_CONFIG_DIR commit -m 'Base config space' (Details: HOWTO-new-faiserver.md, Abschnitt 1.2; fehlt das Verzeichnis ganz, zuerst fai-setup ausfuehren)."
# Der Configspace gehoert haeufig einem normalen Benutzer, install.sh laeuft
# aber als root - git bricht dann mit "dubious ownership" ab, und set -e
# beendet das Skript stumm, noch vor Schritt 5b. Wie bei $REPO_DIR systemweit.
if ! git config --system --get-all safe.directory 2>/dev/null | grep -qxF "$FAI_CONFIG_DIR"; then
    git config --system --add safe.directory "$FAI_CONFIG_DIR"
fi

internal_url=$(grep '^FAI_DISCOVERY_INTERNAL_URL=' "$SITE_CONF" | cut -d= -f2-)

sed "s|__FAI_DISCOVERY_INTERNAL_URL__|$internal_url|" \
    "$REPO_DIR/01-discovery-client/fai-config/hooks/discovery" > "$FAI_CONFIG_DIR/hooks/discovery"
chown root:root "$FAI_CONFIG_DIR/hooks/discovery"
chmod 755 "$FAI_CONFIG_DIR/hooks/discovery"

sed "s|__FAI_DISCOVERY_INTERNAL_URL__|$internal_url|" \
    "$REPO_DIR/03-fai-configspace/fai-config/class/02-set-hostname.sh" > "$FAI_CONFIG_DIR/class/02-set-hostname.sh"
chown root:root "$FAI_CONFIG_DIR/class/02-set-hostname.sh"
chmod 755 "$FAI_CONFIG_DIR/class/02-set-hostname.sh"


git -C "$FAI_CONFIG_DIR" add hooks/discovery class/02-set-hostname.sh
if git -C "$FAI_CONFIG_DIR" diff --cached --quiet; then
    log "Configspace-Dateien unverändert, kein Commit nötig."
else
    git -C "$FAI_CONFIG_DIR" commit -m "fai-discovery: install.sh Deployment $(date -I)" || die "Configspace-Commit fehlgeschlagen - git-Identität für root prüfen (git config --global user.email/user.name)."
    git -C "$FAI_CONFIG_DIR" push || log "WARN: git push fehlgeschlagen, bitte manuell nachholen (git -C $FAI_CONFIG_DIR push)."
fi

# --- Schritt 5b: PXE-Bootmenue (optional, opt-in ueber site.conf) ---
log "Verteile fai-discovery-menu Skript."
install -o root -g root -m 755 "$REPO_DIR/02-webconsole/bin/fai-discovery-menu" /usr/local/bin/fai-discovery-menu
log "Verteile fai-discovery-known Skript."
install -o root -g root -m 755 "$REPO_DIR/02-webconsole/bin/fai-discovery-known" /usr/local/bin/fai-discovery-known

if /usr/local/bin/fai-discovery-menu --is-enabled; then
    log "PXE-Bootmenue aktiviert - verteile systemd-Units und erzeuge das Menue."
    log "WARNUNG: Reihenfolge beachten - UEFI-Clients muessen vom DHCP-Server fai/efi64/syslinux.efi als Bootdatei bekommen (Kea-Klasse pxe-uefi), sonst haengen unbekannte UEFI-Clients in einer Endlosschleife (siehe Dokumentation zum PXE-Bootmenue)."
    install -o root -g root -m 644 "$REPO_DIR/02-webconsole/etc/systemd/system/fai-discovery-menu.service" /etc/systemd/system/fai-discovery-menu.service
    install -o root -g root -m 644 "$REPO_DIR/02-webconsole/etc/systemd/system/fai-discovery-menu.path" /etc/systemd/system/fai-discovery-menu.path
    systemctl daemon-reload
    /usr/local/bin/fai-discovery-menu || die "fai-discovery-menu fehlgeschlagen (siehe Ausgabe oben) - die bestehende default wurde nicht veraendert."
    systemctl enable --now fai-discovery-menu.path
    log "Bekannte Geraete (Status reboot/reinstalling) umgehen das Menue - verteile systemd-Units."
    for unit in service path timer; do
        install -o root -g root -m 644 "$REPO_DIR/02-webconsole/etc/systemd/system/fai-discovery-known.$unit" "/etc/systemd/system/fai-discovery-known.$unit"
    done
    systemctl daemon-reload
    /usr/local/bin/fai-discovery-known || log "WARN: fai-discovery-known fehlgeschlagen (siehe Ausgabe oben) - der Timer versucht es erneut."
    systemctl enable --now fai-discovery-known.path fai-discovery-known.timer
elif [ -f /etc/systemd/system/fai-discovery-menu.path ]; then
    log "PXE-Bootmenue deaktiviert - stoppe Path-Unit und stelle den localboot-default wieder her."
    systemctl disable --now fai-discovery-menu.path
    /usr/local/bin/fai-discovery-menu || die "fai-discovery-menu fehlgeschlagen (siehe Ausgabe oben) - der default konnte nicht auf localboot zurueckgestellt werden."
    if [ -f /etc/systemd/system/fai-discovery-known.path ]; then
        systemctl disable --now fai-discovery-known.path fai-discovery-known.timer
        /usr/local/bin/fai-discovery-known || die "fai-discovery-known fehlgeschlagen (siehe Ausgabe oben) - die localboot-Dateien der bekannten Geraete konnten nicht entfernt werden."
    fi
else
    log "PXE-Bootmenue nicht aktiviert (FAI_DISCOVERY_MENU_ENABLED=true in site.conf), ueberspringe."
fi

# --- Schritt 5c: HTTPS ueber Caddy (optional, opt-in ueber site.conf) ---
# Siehe HOWTO-https.md. Ohne FAI_DISCOVERY_TLS_MODE raeumt das Skript nur eine
# frueher von ihm geschriebene Caddyfile wieder weg (fremde bleiben unberuehrt).
log "Verteile fai-discovery-tls Skript."
install -o root -g root -m 755 "$REPO_DIR/02-webconsole/bin/fai-discovery-tls" /usr/local/bin/fai-discovery-tls
tls_mode=$(grep '^FAI_DISCOVERY_TLS_MODE=' "$SITE_CONF" | tail -1 | cut -d= -f2- | tr -d '"' || true)
tls_port=$(grep '^FAI_DISCOVERY_TLS_PORT=' "$SITE_CONF" | tail -1 | cut -d= -f2- | tr -d '"' || true)
tls_port="${tls_port:-443}"
if [ -n "$tls_mode" ] && [ "$tls_mode" != "off" ]; then
    command -v caddy &>/dev/null || die "FAI_DISCOVERY_TLS_MODE=$tls_mode, aber caddy ist nicht installiert (apt install caddy) - siehe HOWTO-https.md."
    log "HTTPS aktiviert (Modus $tls_mode) - schreibe Caddyfile."
    /usr/local/bin/fai-discovery-tls || die "fai-discovery-tls fehlgeschlagen (siehe Ausgabe oben) - die bestehende Caddyfile wurde nicht veraendert."
    if ! grep -q '^FAI_DISCOVERY_ADMIN_HTTPS_ONLY=true' "$SITE_CONF"; then
        log "HINWEIS: FAI_DISCOVERY_ADMIN_HTTPS_ONLY=true ist nicht gesetzt - die Admin-Seiten bleiben zusaetzlich unverschluesselt ueber Port 8080 erreichbar."
    fi
else
    /usr/local/bin/fai-discovery-tls || die "fai-discovery-tls fehlgeschlagen (siehe Ausgabe oben)."
fi

# --- Schritt 6: Firewall ---
command -v ufw &>/dev/null || die "ufw ist nicht installiert (apt install ufw) - siehe HOWTO-new-faiserver.md, Abschnitt 1.4."
log "Öffne Port 8080/tcp in ufw."
ufw allow 8080/tcp
if [ -n "$tls_mode" ] && [ "$tls_mode" != "off" ]; then
    log "Öffne Port $tls_port/tcp (HTTPS) in ufw."
    ufw allow "$tls_port/tcp"
    if grep -q '^FAI_DISCOVERY_TLS_ACME_CHALLENGE="\?http-01' "$SITE_CONF"; then
        log "Öffne Port 80/tcp (ACME http-01) in ufw."
        ufw allow 80/tcp
    fi
fi

# --- Schritt 7: Service ---
systemctl daemon-reload
if systemctl is-active --quiet fai-discovery-webconsole; then
    log "Service läuft bereits, starte neu (Code-Update übernehmen)."
    systemctl restart fai-discovery-webconsole
else
    log "Starte Service erstmalig."
    systemctl enable --now fai-discovery-webconsole
fi

# --- Schritt 8: Verifikation ---
sleep 2
status_code=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/status/aa:bb:cc:dd:ee:ff || echo "000")
if [ "$status_code" = "200" ]; then
    log "PASS: /status/<mac> antwortet mit 200."
else
    log "FAIL: /status/<mac> antwortet mit $status_code (erwartet: 200)."
fi

admin_code=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/admin/ || echo "000")
if [ "$admin_code" = "401" ]; then
    log "PASS: /admin/ verlangt Auth (401)."
else
    log "FAIL: /admin/ antwortet mit $admin_code (erwartet: 401)."
fi

if [ -n "$tls_mode" ] && [ "$tls_mode" != "off" ]; then
    tls_host=$(grep '^FAI_DISCOVERY_TLS_HOST=' "$SITE_CONF" | tail -1 | cut -d= -f2- | tr -d '"' || true)
    tls_host="${tls_host:-$(hostname -f)}"
    # -k: hier geht es um den Weg Caddy -> Webkonsole, nicht um die Vertrauenskette
    # (die Root einer internal-CA kennt der Server selbst nicht).
    https_code=$(curl -sk -o /dev/null -w "%{http_code}" --resolve "$tls_host:$tls_port:127.0.0.1" \
        "https://$tls_host:$tls_port/admin/" || echo "000")
    if [ "$https_code" = "401" ]; then
        log "PASS: https://$tls_host:$tls_port/admin/ verlangt Auth (401)."
    else
        log "WARN: https://$tls_host:$tls_port/admin/ antwortet mit $https_code (erwartet: 401) - bei acme kann die erste Zertifikatsausstellung etwas dauern, sonst: journalctl -u caddy."
    fi
fi

log "install.sh abgeschlossen."
