#!/bin/bash
set -euo pipefail

UNATTENDED=0
if [ "${1:-}" = "--unattended" ]; then
    UNATTENDED=1
fi
if [ "$UNATTENDED" -eq 1 ]; then
    export GIT_TERMINAL_PROMPT=0
fi

# TODO(Repo-Betreiber): auf die eigene Fork-/Mirror-URL anpassen.
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

# --- Schritt 4: Prompts + admins.json/site.conf ---
if [ "$UNATTENDED" -eq 0 ]; then
    [ -e /dev/tty ] || die "Keine Konsole verfügbar - install.sh erst herunterladen, dann ausführen (siehe HOWTO Abschnitt 0)."
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
    umask 077
    printf 'Benutzername: %s\nPasswort: %s\n' "$admin_user" "$admin_password" \
        > /root/fai-discovery-initial-admin-password.txt
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
[ -d "$FAI_CONFIG_DIR/.git" ] || die "$FAI_CONFIG_DIR ist kein Git-Checkout - Basis-FAI-Setup fehlt, siehe HOWTO-Voraussetzungen."

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

# --- Schritt 6: Firewall ---
command -v ufw &>/dev/null || die "ufw ist nicht installiert (apt install ufw) - siehe HOWTO-Voraussetzungen."
log "Öffne Port 8080/tcp in ufw."
ufw allow 8080/tcp

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

log "install.sh abgeschlossen."
