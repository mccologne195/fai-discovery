#!/bin/bash
# allinone-bootstrap.sh - All-in-One-FAI-Server: FAI + fai-discovery + dnsmasq (DHCP und DNS) + TFTP + NFS
# auf einer frischen Debian-13-Installation, ohne weitere Infrastruktur (kein anderer DHCP- oder DNS-Server,
# keine eigene CA, kein Konfigurationsmanagement, kein eigener Mirror). Pakete direkt von deb.debian.org.
#
# Jeder Schritt wird mit "[Schritt n]" protokolliert. Das Skript ist für Wiederholungsläufe gedacht
# (Pakete, Konfiguration, "fai-setup -f"); Einzelheiten und Stolpersteine: README.md.
#
# Voraussetzungen (müssen vorher da sein):
#   - Debian 13 (amd64), root, Internet für apt
#   - eine Netzwerkkarte für den "Raum" (ROOM_IF), in deren Segment kein anderer DHCP-Server läuft
#   - Quellen für fai-config (Konfigurations-Space mit neutralem Profil, siehe configspace-neutral/)
#     und fai-discovery: entweder Git-URLs (CONFIG_REPO/DISCOVERY_REPO) oder Git-Bundles
#     (CONFIG_BUNDLE/DISCOVERY_BUNDLE), z. B. wenn die Repos privat sind
#
# Aufruf (Beispiel):
#   ROOM_IF=ens19 CONFIG_BUNDLE=/root/fai-config.bundle DISCOVERY_BUNDLE=/root/fai-discovery.bundle \
#     ./allinone-bootstrap.sh
set -euo pipefail

: "${ROOM_IF:?ROOM_IF setzen (Netzwerkkarte des Raums, z. B. ens19)}"
: "${ROOM_IP:=192.168.77.2}"
: "${ROOM_PREFIX:=24}"
: "${ROOM_NET:=192.168.77.0/24}"
: "${ROOM_GW:=192.168.77.1}"
: "${POOL_START:=192.168.77.100}"
: "${POOL_END:=192.168.77.200}"
: "${POOL_MASK:=255.255.255.0}"
: "${DOMAIN:=home.arpa}"
: "${SERVER_NAME:=$(hostname -s)}"
: "${UPSTREAM_DNS:=9.9.9.9 1.1.1.1}"
: "${MGMT_IF:=$(ip route show default 2>/dev/null | awk '/default/{print $5; exit}')}"
: "${DEB_MIRROR:=http://deb.debian.org/debian}"
: "${DEB_SECURITY:=http://deb.debian.org/debian-security}"
: "${RELEASE:=trixie}"
: "${TEST_ROOT_PW:=fai}"
: "${CONFIG_REPO:=}"
: "${CONFIG_BUNDLE:=}"
: "${CONFIG_BRANCH:=main}"
: "${DISCOVERY_REPO:=}"
: "${DISCOVERY_BUNDLE:=}"
: "${HOOKS_DIR:=$(dirname "$(readlink -f "$0")")/nfsroot-hooks}"
# dnsmasq: Vorlage ist die einzige Quelle (dnsmasq-allinone.conf.template); log-queries nur zum Debuggen
: "${DNSMASQ_TEMPLATE:=$(dirname "$(readlink -f "$0")")/dnsmasq-allinone.conf.template}"
: "${DNSMASQ_LOG_QUERIES:=no}"
: "${DNSMASQ_LEASE:=8h}"
# Webkonsole per HTTPS (Caddy mit eigener CA, siehe HOWTO-https.md): "internal" (Standard) oder "off"
: "${WEB_TLS:=internal}"
MODE="${1:-all}"    # "all" (Standard) oder "dnsmasq" (nur die dnsmasq-Konfiguration neu schreiben und neu starten)

FQDN="$SERVER_NAME.$DOMAIN"
STEP=0
step() { STEP=$((STEP+1)); echo; echo "[Schritt $STEP] $*"; }
die()  { echo "FEHLER: $*" >&2; exit 1; }

# dnsmasq-Konfiguration aus der Vorlage erzeugen, prüfen und (neu) starten
configure_dnsmasq() {
    [ -f "$DNSMASQ_TEMPLATE" ] || die "dnsmasq-Vorlage fehlt: $DNSMASQ_TEMPLATE"
    local tpl upstream logq
    tpl=$(cat "$DNSMASQ_TEMPLATE")
    upstream=$(for d in $UPSTREAM_DNS; do echo "server=$d"; done)
    if [ "$DNSMASQ_LOG_QUERIES" = yes ]; then logq="log-queries"; else logq="# log-queries: aus (DNSMASQ_LOG_QUERIES=yes zum Debuggen)"; fi
    tpl=${tpl//@ROOM_IF@/$ROOM_IF};       tpl=${tpl//@DOMAIN@/$DOMAIN}
    tpl=${tpl//@UPSTREAM_SERVERS@/$upstream}
    tpl=${tpl//@FQDN@/$FQDN};             tpl=${tpl//@ROOM_IP@/$ROOM_IP}
    tpl=${tpl//@POOL_START@/$POOL_START}; tpl=${tpl//@POOL_END@/$POOL_END}
    tpl=${tpl//@POOL_MASK@/$POOL_MASK};   tpl=${tpl//@LEASE_TIME@/$DNSMASQ_LEASE}
    tpl=${tpl//@ROOM_GW@/$ROOM_GW};       tpl=${tpl//@SERVER_NAME@/$SERVER_NAME}
    tpl=${tpl//@LOG_QUERIES@/$logq}
    if [[ $tpl =~ @[A-Z_]+@ ]]; then die "unersetzter Platzhalter in der dnsmasq-Vorlage: ${BASH_REMATCH[0]}"; fi
    [ -f /etc/dnsmasq.d/fai-room.conf ] && cp -a /etc/dnsmasq.d/fai-room.conf /root/fai-room.conf.vorher
    printf '%s\n' "$tpl" > /etc/dnsmasq.d/fai-room.conf
    dnsmasq --test || { [ -f /root/fai-room.conf.vorher ] && cp -a /root/fai-room.conf.vorher /etc/dnsmasq.d/fai-room.conf; die "dnsmasq-Konfiguration ungültig (vorherige Datei wiederhergestellt)"; }
    systemctl enable dnsmasq >/dev/null 2>&1
    systemctl restart dnsmasq
    sleep 2
    systemctl is-active dnsmasq
}

[ "$(id -u)" -eq 0 ] || die "als root ausführen"
ip link show "$ROOM_IF" >/dev/null 2>&1 || die "Raum-NIC $ROOM_IF nicht gefunden"
case "$MODE" in
    all)
        [ -n "$CONFIG_REPO$CONFIG_BUNDLE" ] || die "CONFIG_REPO oder CONFIG_BUNDLE setzen"
        [ -n "$DISCOVERY_REPO$DISCOVERY_BUNDLE" ] || die "DISCOVERY_REPO oder DISCOVERY_BUNDLE setzen"
        [ -d "$HOOKS_DIR" ] || die "NFS-Root-Hooks fehlen: $HOOKS_DIR"
        case "$WEB_TLS" in internal|off) ;; *) die "WEB_TLS '$WEB_TLS' unbekannt (erlaubt: internal, off)" ;; esac
        ;;
    dnsmasq)
        step "dnsmasq-Konfiguration neu schreiben (Vorlage: $DNSMASQ_TEMPLATE)"
        configure_dnsmasq
        echo "Fertig. Vorherige Datei: /root/fai-room.conf.vorher, aktive: /etc/dnsmasq.d/fai-room.conf"
        exit 0
        ;;
    *) die "unbekannter Modus '$MODE' (erlaubt: all, dnsmasq)" ;;
esac
export DEBIAN_FRONTEND=noninteractive

step "Raum-NIC $ROOM_IF statisch konfigurieren ($ROOM_IP/$ROOM_PREFIX, kein Gateway)"
cat > "/etc/network/interfaces.d/$ROOM_IF" <<EOF
auto $ROOM_IF
iface $ROOM_IF inet static
    address $ROOM_IP/$ROOM_PREFIX
EOF
ifup "$ROOM_IF" 2>&1 | tail -1 || true
ip -br a show "$ROOM_IF"

step "Hostname/FQDN: $FQDN (Eintrag in /etc/hosts, Namen nicht umbenennen)"
sed -i "/[[:space:]]$SERVER_NAME\([[:space:]]\|\$\)/d" /etc/hosts
echo "$ROOM_IP $FQDN $SERVER_NAME" >> /etc/hosts
[ "$(hostname -f)" = "$FQDN" ] || die "hostname -f liefert '$(hostname -f)', erwartet $FQDN"

step "Pakete installieren (Mindest-Pakete + dnsmasq + Zeitsync), Dienste noch nicht starten"
printf '#!/bin/sh\nexit 101\n' > /usr/sbin/policy-rc.d; chmod 755 /usr/sbin/policy-rc.d
apt-get update -qq
apt-get install -y -q --no-install-recommends \
    fai-server nfs-kernel-server tftpd-hpa openssh-server openssh-client \
    libproc-daemon-perl syslinux-common python3-flask \
    sudo git curl ca-certificates ufw dnsmasq systemd-timesyncd tcpdump bind9-dnsutils
# Caddy nur mit HTTPS: das Paket bringt eine Standard-Caddyfile mit, die sonst beim naechsten Boot Port 80 belegt
if [ "$WEB_TLS" != off ]; then
    apt-get install -y -q --no-install-recommends caddy
fi
rm -f /usr/sbin/policy-rc.d
# Ausgabe erst in eine Variable (nicht "apt-cache | grep -q": mit pipefail liefert das SIGPIPE-Fehlalarme)
FAI_POLICY=$(apt-cache policy fai-server)
case "$FAI_POLICY" in
    *fai-project.org*) ;;
    *)
        echo "HINWEIS: Die Paketquelle fai-project.org ist nicht eingerichtet, fai-server kommt aus Debian ($(dpkg-query -W -f='${Version}' fai-server))."
        echo "         Server und NFS-Root sollten dieselbe FAI-Version haben, siehe README (Abschnitt Grenzen)."
        ;;
esac
systemctl disable dnsmasq >/dev/null 2>&1 || true
systemctl enable --now systemd-timesyncd >/dev/null 2>&1 || true

step "/etc/fai: fai.conf, nfsroot.conf, apt-Quellen, NFS-Root-Hooks (ohne CA, Quelle deb.debian.org)"
ROOTPW_HASH=$(openssl passwd -6 "$TEST_ROOT_PW")
cat > /etc/fai/fai.conf <<EOF
LOGUSER=fai
FAI_CONFIG_SRC=nfs://$FQDN/srv/fai/config
EOF
cat > /etc/fai/nfsroot.conf <<EOF
FAI_DEBOOTSTRAP="$RELEASE $DEB_MIRROR"
FAI_ROOTPW='$ROOTPW_HASH'
NFSROOT=/srv/fai/nfsroot
TFTPROOT=/srv/tftp/fai
NFSROOT_HOOKS=/etc/fai/nfsroot-hooks/
FAI_DEBOOTSTRAP_OPTS="--exclude=info --include=ca-certificates"
SERVERINTERFACE=$ROOM_IF
FAI_CONFIGDIR=/srv/fai/config
NFSROOT_ETC_HOSTS="$ROOM_IP $FQDN $SERVER_NAME"
EOF
cat > /etc/fai/apt/sources.list <<EOF
deb $DEB_MIRROR $RELEASE main contrib non-free non-free-firmware
deb $DEB_MIRROR $RELEASE-updates main contrib non-free non-free-firmware
deb $DEB_SECURITY $RELEASE-security main contrib non-free non-free-firmware
EOF
mkdir -p /etc/fai/nfsroot-hooks
install -m 755 "$HOOKS_DIR"/* /etc/fai/nfsroot-hooks/
ls /etc/fai/nfsroot-hooks

step "Konfigurations-Space ($CONFIG_BRANCH) nach /srv/fai/config"
if [ -d /srv/fai/config ] && [ -n "$(ls -A /srv/fai/config 2>/dev/null)" ]; then
    mv /srv/fai/config "/srv/fai/config.fai-setup-default.$(date +%s)"
fi
git config --system --add safe.directory /srv/fai/config
git clone -q -b "$CONFIG_BRANCH" "${CONFIG_BUNDLE:-$CONFIG_REPO}" /srv/fai/config
git -C /srv/fai/config log --oneline -1
ls /srv/fai/config/class/NEUTRAL.var >/dev/null || die "class/NEUTRAL.var fehlt im Konfigurations-Space (falscher Branch?)"

step "Profil-Datei class/example.profile (nur das neutrale Profil)"
cat > /srv/fai/config/class/example.profile <<'EOF'
Default: Debian 13 neutral

Name: Debian 13 neutral
Description: Base install trixie ohne Zusatzdienste, Pakete von debian.org
Short: A linux-host, no xorg, root password: fai (Test/Greenfield)
Long: Neutrale Minimalinstallation mit fail2ban und ufw firewall.
Kein step-ca, kein Salt, kein persönlicher Benutzer.
Root password: fai (nur zum Testen).
Classes: INSTALL FAIBASE DEBIAN SECURE NEUTRAL
EOF

step "fai-setup (NFS-Root bauen, fai-User, TFTP, Exporte) - dauert einige Minuten"
fai-setup -v -f > /root/greenfield-fai-setup.log 2>&1 || { tail -20 /root/greenfield-fai-setup.log; die "fai-setup fehlgeschlagen (siehe /root/greenfield-fai-setup.log)"; }
tail -3 /root/greenfield-fai-setup.log

step "NFS-Exporte auf das Raum-Netz $ROOM_NET zuschneiden, TFTP-Optionen"
cat > /etc/exports <<EOF
/srv/fai/config $ROOM_NET(async,ro,no_subtree_check,insecure)
/srv/fai/nfsroot $ROOM_NET(async,ro,no_subtree_check,no_root_squash,insecure)
EOF
sed -i 's#^TFTP_OPTIONS=.*#TFTP_OPTIONS="--secure --blocksize 512"#; s#^TFTP_ADDRESS=.*#TFTP_ADDRESS="0.0.0.0:69"#' /etc/default/tftpd-hpa
systemctl enable --now nfs-server tftpd-hpa >/dev/null 2>&1 || true
exportfs -ra
systemctl restart tftpd-hpa

step "fai-monitor als systemd-Dienst anlegen (fai-server liefert keine Unit)"
cat > /etc/systemd/system/fai-monitor.service <<'EOF'
[Unit]
Description=FAI monitor daemon
After=network.target

[Service]
Type=forking
ExecStart=/usr/sbin/fai-monitor -d -l /var/log/fai/fai-monitor.log
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now fai-monitor

step "fai-discovery installieren (install.sh --unattended, Quelle: lokales Bare-Repo/URL)"
if [ -n "$DISCOVERY_BUNDLE" ]; then
    rm -rf /root/fai-discovery.git
    git clone -q --bare "$DISCOVERY_BUNDLE" /root/fai-discovery.git
    git -C /root/fai-discovery.git config uploadpack.allowFilter true
    git -C /root/fai-discovery.git config uploadpack.allowAnySHA1InWant true
    DISC_SRC="file:///root/fai-discovery.git"
else
    DISC_SRC="$DISCOVERY_REPO"
fi
git --git-dir="${DISC_SRC#file://}" show main:install.sh 2>/dev/null > /root/install.sh \
    || { git clone -q "$DISC_SRC" /root/fai-discovery-install && cp /root/fai-discovery-install/install.sh /root/install.sh; }
sed -i "s#^REPO_URL=.*#REPO_URL=\"$DISC_SRC\"#" /root/install.sh
mkdir -p /etc/fai-discovery
cat > /etc/fai-discovery/site.conf <<EOF
FAI_DISCOVERY_PROFILE_FILE=/srv/fai/config/class/example.profile
FAI_DISCOVERY_INTERNAL_URL=http://$FQDN:8080
FAI_DISCOVERY_NFS_ROOT=nfs://$FQDN/srv/fai/config
FAI_DISCOVERY_MENU_ENABLED=true
EOF
if [ "$WEB_TLS" != off ]; then
    # Zertifikat fuer den FQDN und die Raum- und Verwaltungs-IP, Admin-Seiten nur noch per HTTPS
    MGMT_IP=$(ip -4 -o addr show "$MGMT_IF" 2>/dev/null | awk '{print $4}' | cut -d/ -f1 | head -1)
    cat >> /etc/fai-discovery/site.conf <<EOF
FAI_DISCOVERY_TLS_MODE=internal
FAI_DISCOVERY_TLS_HOST=$FQDN
FAI_DISCOVERY_TLS_EXTRA_NAMES=$ROOM_IP${MGMT_IP:+,$MGMT_IP}
FAI_DISCOVERY_ADMIN_HTTPS_ONLY=true
EOF
fi
bash /root/install.sh --unattended 2>&1 | grep -E "==>|FEHLER|WARN|FAIL|PASS" | cut -c1-160

step "Firewall (ufw ist durch die Klasse SECURE aktiv): Raum offen, Verwaltung nur ssh, 8080 und 443"
ufw allow in on "$ROOM_IF" >/dev/null
ufw allow in on "$MGMT_IF" to any port 22 proto tcp >/dev/null
ufw allow in on "$MGMT_IF" to any port 8080 proto tcp >/dev/null
[ "$WEB_TLS" = off ] || ufw allow in on "$MGMT_IF" to any port 443 proto tcp >/dev/null
ufw status | head -12

step "dnsmasq: DHCP + DNS im Raum ($ROOM_NET), Upstream: $UPSTREAM_DNS"
configure_dnsmasq

step "Verifikation"
ok() { printf '%-52s %s\n' "$1" "$2"; }
ok "dnsmasq DHCP (67/udp auf $ROOM_IF)"      "$(ss -ulnp | grep -c ':67 ')"
ok "dnsmasq DNS (53/udp)"                     "$(ss -ulnp | grep -c "$ROOM_IP:53")"
ok "tftpd-hpa (69/udp)"                       "$(ss -ulnp | grep -c ':69 ')"
ok "NFS (2049/tcp)"                           "$(ss -tlnp | grep -c ':2049 ')"
ok "fai-monitor (4711/tcp)"                   "$(ss -tlnp | grep -c ':4711 ')"
ok "Webconsole (8080/tcp)"                    "$(ss -tlnp | grep -c ':8080 ')"
[ "$WEB_TLS" = off ] || ok "Webconsole HTTPS (Caddy, 443/tcp)" "$(ss -tlnp | grep -c ':443 ')"
ok "DNS: $FQDN (dnsmasq)"                     "$(dig +short +time=3 @"$ROOM_IP" "$FQDN" 2>/dev/null || true)"
ok "DNS: deb.debian.org (Upstream via dnsmasq)" "$(dig +short +time=3 @"$ROOM_IP" deb.debian.org 2>/dev/null | head -1 || true)"
ok "Zeit synchronisiert"                      "$(timedatectl show -p NTPSynchronized --value)"
ok "PXE-Menü-Default"                        "$(head -c 60 /srv/tftp/fai/pxelinux.cfg/default | tr '\n' ' ')"
echo
if [ "$WEB_TLS" = off ]; then
    echo "Fertig. Admin-Zugang: /root/fai-discovery-initial-admin-password.txt, Webconsole http://$FQDN:8080 (Raum) bzw. Verwaltungs-IP:8080"
else
    echo "Fertig. Admin-Zugang: /root/fai-discovery-initial-admin-password.txt, Webconsole https://$FQDN (Raum) bzw. https://${MGMT_IP:-<Verwaltungs-IP>}"
    echo "       Root-Zertifikat zum Import in Browser/System: /var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt"
fi
echo "Schritte insgesamt: $STEP (alle ohne manuellen Eingriff)"
