#!/bin/bash
# fai-discovery-approve.sh - CLI-Fallback zur Webkonsole (02-webconsole).
# Ruft fai-chboot NICHT mehr selbst auf - das übernimmt seit Teilprojekt 2
# die Webkonsole serverseitig beim /approve-Request (ein Ausführungsort
# statt zwei, die synchron gehalten werden müssen).
set -euo pipefail

API_URL="${FAI_DISCOVERY_PUBLIC_URL:-https://fai-discovery.example.com}"

if [ "$#" -ne 3 ]; then
    echo "Nutzung: $0 <MAC> <HOSTNAME> <FAI_KLASSEN>" >&2
    exit 1
fi

if [ -z "${FAI_DISCOVERY_USER:-}" ] || [ -z "${FAI_DISCOVERY_PASSWORD:-}" ]; then
    echo "Fehler: FAI_DISCOVERY_USER und FAI_DISCOVERY_PASSWORD müssen gesetzt sein" >&2
    exit 1
fi

mac_raw=$1
hostname=$2
classes=$3
mac=$(echo "$mac_raw" | tr '[:upper:]' '[:lower:]')

if ! [[ "$mac" =~ ^[0-9a-f]{2}(:[0-9a-f]{2}){5}$ ]]; then
    echo "Fehler: '$mac_raw' ist keine gültige MAC-Adresse (Format aa:bb:cc:dd:ee:ff)" >&2
    exit 1
fi

# json_escape - escapes backslashes, double quotes and control characters
# for safe embedding in a JSON string value (gleiche Technik wie
# hooks/discovery aus Teilprojekt 1).
json_escape() {
    local s=$1
    s=${s//\\/\\\\}
    s=${s//\"/\\\"}
    s=${s//$'\n'/\\n}
    s=${s//$'\r'/\\r}
    s=${s//$'\t'/\\t}
    printf '%s' "$s"
}

payload=$(printf '{"mac":"%s","hostname":"%s","classes":"%s"}' \
    "$mac" "$(json_escape "$hostname")" "$(json_escape "$classes")")

if ! curl -sS -f -u "${FAI_DISCOVERY_USER}:${FAI_DISCOVERY_PASSWORD}" \
    -X POST -H "Content-Type: application/json" \
    -d "$payload" \
    "$API_URL/approve" > /dev/null; then
    echo "Fehler: Freigabe fehlgeschlagen" >&2
    exit 1
fi

echo "Freigegeben: $mac -> $hostname ($classes)"
