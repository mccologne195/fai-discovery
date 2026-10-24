#!/bin/bash
# check-allinone.sh - prüft einen All-in-One-FAI-Server (Dienste, Ports, DNS, Zeit, PXE-Menü).
# Aufruf: ROOM_IF=ens19 ./check-allinone.sh   (Exit-Code 0 = alles in Ordnung)
set -uo pipefail
: "${ROOM_IF:?ROOM_IF setzen (Netzwerkkarte des Raums)}"
ROOM_IP=$(ip -4 -o addr show dev "$ROOM_IF" 2>/dev/null | awk '{print $4}' | cut -d/ -f1 | head -1)
[ -n "$ROOM_IP" ] || { echo "FEHLER: $ROOM_IF hat keine IPv4-Adresse"; exit 2; }
FQDN=$(hostname -f 2>/dev/null)
FAIL=0
check() {  # Beschreibung, Anzahl/Wert, erwartet-mindestens
    local ok="OK  "; [ "$2" -ge "$3" ] 2>/dev/null || { ok="FEHL"; FAIL=1; }
    printf '%s  %-46s %s\n' "$ok" "$1" "$2"
}
svc() { local a; a=$(systemctl is-active "$1" 2>/dev/null); local n=0; [ "$a" = active ] && n=1; check "Dienst $1" "$n" 1; }

echo "All-in-One-FAI-Server: $FQDN, Raum-NIC $ROOM_IF ($ROOM_IP)"
echo
for u in dnsmasq tftpd-hpa nfs-server fai-monitor fai-discovery-webconsole systemd-timesyncd; do svc "$u"; done
check "DHCP (67/udp)"                  "$(ss -ulnp | grep -c ':67 ')" 1
check "DNS (53/udp auf $ROOM_IP)"      "$(ss -ulnp | grep -c "$ROOM_IP:53")" 1
check "TFTP (69/udp)"                  "$(ss -ulnp | grep -c ':69 ')" 1
check "NFS (2049/tcp)"                 "$(ss -tlnp | grep -c ':2049 ')" 1
check "fai-monitor (4711/tcp)"         "$(ss -tlnp | grep -c ':4711 ')" 1
check "Webkonsole (8080/tcp)"          "$(ss -tlnp | grep -c ':8080 ')" 1
check "DNS löst $FQDN auf"             "$(dig +short +time=3 @"$ROOM_IP" "$FQDN" 2>/dev/null | grep -c .)" 1
check "DNS: Upstream (deb.debian.org)" "$(dig +short +time=3 @"$ROOM_IP" deb.debian.org 2>/dev/null | grep -c .)" 1
check "Zeit synchronisiert"            "$([ "$(timedatectl show -p NTPSynchronized --value)" = yes ] && echo 1 || echo 0)" 1
check "Kernel+initrd im TFTP-Baum"     "$(ls /srv/tftp/fai/vmlinuz-* /srv/tftp/fai/initrd.img-* 2>/dev/null | wc -l)" 2
check "Bootdateien BIOS+UEFI"          "$(ls /srv/tftp/fai/pxelinux.0 /srv/tftp/fai/efi64/syslinux.efi 2>/dev/null | wc -l)" 2
check "PXE-Menü (default)"             "$(grep -c 'fai-discovery-menu' /srv/tftp/fai/pxelinux.cfg/default 2>/dev/null)" 1
check "Exporte nur Raum-Netz"          "$(exportfs -v 2>/dev/null | grep -c '/srv/fai/')" 2
echo
if [ "$FAIL" -eq 0 ]; then echo "Ergebnis: alles in Ordnung"; else echo "Ergebnis: mindestens ein Punkt fehlt (FEHL)"; fi
exit "$FAIL"
