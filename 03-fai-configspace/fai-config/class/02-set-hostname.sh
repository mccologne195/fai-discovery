#! /bin/bash
# 02-set-hostname.sh - fragt die Webkonsole nach dem für diese MAC
# freigegebenen Hostnamen und hinterlegt ihn über additional.var, bevor
# die restliche Klassen-Pipeline (insbesondere 50-host-classes und
# scripts/DEBIAN/70-salt, das ohne gesetzten Hostnamen abbricht) läuft.
#
# WICHTIG: fai-class läuft als eigener Kindprozess von task_defclass - eine
# einfache HOSTNAME=...-Zuweisung hier würde nur innerhalb dieses
# Kindprozesses gelten und nie beim eigentlichen Hostnamen-Schreiben
# ankommen. FAIs dokumentierter Mechanismus dafür ist $LOGDIR/additional.var
# (siehe auch class/20-hwdetect.sh in diesem Configspace) - Variablen darin
# werden von task_defvar im richtigen (persistenten) Prozess gesourced.
#
# Läuft als FAI-Klassen-Skript (gesourced, .sh-Endung) - deshalb "return",
# NICHT "exit" bei einem Fehler: "exit" in einem gesourceten Skript beendet
# den kompletten aufrufenden fai-class-Lauf, nicht nur dieses Skript.
#
# ZUSÄTZLICH wird direkt `hostname` aufgerufen (nicht nur additional.var
# geschrieben): dracut setzt im Nfsroot bereits in der Initramfs-Phase
# /proc/sys/kernel/hostname aus der DHCP-Option 12 - lange bevor dieses
# Skript läuft. additional.var allein behebt das nicht für Skripte, die
# es nicht explizit nachladen (z. B. das unveränderte FAI-Standardskript
# scripts/FAIBASE/10-misc). `hostname` ändert dagegen Kernel-globalen
# UTS-Namespace-Zustand und wirkt daher automatisch für jeden danach
# gestarteten Prozess. Details: ../2026-08-12-hostname-fix-design.md.

API_URL="__FAI_DISCOVERY_INTERNAL_URL__"

nic=$(ip route | awk '/^default/ {print $5}' | head -1)
mac=$(< /sys/class/net/"$nic"/address)

# Netzwerk/DNS ist an dieser Stelle (frueh in defclass, kurz nach dem
# NFS-Mount fuer FAI_CONFIG_SRC) manchmal noch nicht vollstaendig bereit -
# ein einzelner fehlgeschlagener curl-Aufruf soll deshalb nicht sofort
# aufgeben, sondern es mit kurzer Pause noch ein paar Mal versuchen.
response=""
for attempt in 1 2 3 4 5; do
    response=$(curl -sf "$API_URL/device/$mac") && break
    echo "02-set-hostname: curl-Versuch $attempt/5 gegen $API_URL fehlgeschlagen, warte 2s und versuche erneut"
    sleep 2
done

if [ -z "$response" ]; then
    echo "02-set-hostname: Webkonsole ($API_URL) nach 5 Versuchen nicht erreichbar - Hostname bleibt beim DHCP-Wert"
    return 0
fi

hostname=$(echo "$response" | grep -o '"hostname":[^,}]*' | sed -E 's/.*"hostname":[[:space:]]*"?([^",}]*)"?.*/\1/')

# Defense in Depth: die Webkonsole validiert hostname bereits serverseitig
# gegen dasselbe Zeichenset (siehe HOSTNAME_RE in chboot.py), aber dieses
# Skript verlässt sich nicht allein darauf - additional.var wird später per
# ". $LOGDIR/additional.var" als root gesourced, ein nicht validierter Wert
# wäre eine Command-Injection-Lücke (in einer Review dieses Teilprojekts
# live nachgestellt und bestätigt).
if [ -n "$LOGDIR" ] && [[ "$hostname" =~ ^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$ ]]; then
    echo "HOSTNAME=$hostname" >> "$LOGDIR/additional.var"
    hostname "$hostname"
    echo "02-set-hostname: Hostname gesetzt und für additional.var vorgemerkt: $hostname (MAC $mac)"
elif [ -n "$hostname" ] && [ "$hostname" != "null" ]; then
    echo "02-set-hostname: ungültiger oder nicht vertrauenswürdiger Hostname verworfen: '$hostname'"
fi
