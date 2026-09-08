#!/bin/bash
# fetch-shredos-kernel.sh - laedt das aktuelle x86_64-ShredOS-Release,
# verifiziert die Pruefsumme und extrahiert den Kernel nach
# /srv/tftp/fai/shredos/vmlinuz. Ersetzt die manuelle Prozedur aus
# HOWTO-neuer-faiserver.md Abschnitt 4. Root erforderlich (losetup/mount).
#
# Der Kernel selbst wird bewusst NICHT im Repo versioniert (Binaerdatei,
# ~350MB, ueberschreitet GitHubs 100MB-Hard-Limit fuer den oeffentlichen
# Mirror) - stattdessen bei Bedarf frisch vom offiziellen Release bezogen.
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "Muss als root laufen (losetup/mount)." >&2
    exit 1
fi

DEST="/srv/tftp/fai/shredos/vmlinuz"
API_URL="https://api.github.com/repos/PartialVolume/shredos.x86_64/releases/latest"
WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

echo "Suche aktuelles x86_64-Release..."
release_json="$WORKDIR/release.json"
curl -sSL "$API_URL" -o "$release_json"

# Nur das volle x86-64-.img-Asset (nicht i686, nicht "_lite"/"_plus-partition",
# nicht .iso/.sha1) - Namensschema z.B.
# shredos-2025.11_31_x86-64_v0.42_20260716.img
img_name=$(grep -oE '"name": *"shredos-[^"]*_x86-64_v[0-9][^"]*\.img"' "$release_json" \
    | grep -v "_lite\|_plus-partition" \
    | head -1 \
    | sed -E 's/"name": *"([^"]+)"/\1/')

if [ -z "$img_name" ]; then
    echo "Kein passendes x86-64-.img-Release-Asset gefunden - Release-Seite pruefen:" >&2
    echo "https://github.com/PartialVolume/shredos.x86_64/releases" >&2
    exit 1
fi

base_url="https://github.com/PartialVolume/shredos.x86_64/releases/download/$(grep -oE '"tag_name": *"[^"]+"' "$release_json" | head -1 | sed -E 's/.*"([^"]+)"$/\1/')"
img_url="$base_url/$img_name"
sha1_url="$img_url.sha1"

echo "Lade $img_name..."
curl -sSL "$img_url" -o "$WORKDIR/$img_name"
curl -sSL "$sha1_url" -o "$WORKDIR/$img_name.sha1"

echo "Pruefe SHA1..."
(cd "$WORKDIR" && sha1sum -c "$img_name.sha1")

echo "Extrahiere Kernel..."
loop_dev=$(losetup -fP --show "$WORKDIR/$img_name")
mount_point="$WORKDIR/mnt"
mkdir -p "$mount_point"
mount "${loop_dev}p1" "$mount_point"

mkdir -p "$(dirname "$DEST")"
cp "$mount_point/boot/bzImage" "$DEST"
chown fai:nogroup "$DEST"

umount "$mount_point"
losetup -d "$loop_dev"

echo "Fertig: $DEST ($(du -h "$DEST" | cut -f1))"
