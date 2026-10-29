#!/bin/bash
# deploy-splash.sh - verteilt die Vollbild-Anzeige in den FAI-Configspace oder entfernt sie wieder.
#
# Gesteuert ueber /etc/fai-discovery/site.conf:
#   FAI_DISCOVERY_SPLASH_ENABLED=true        Splash verteilen (nur der exakte Wert "true" schaltet ihn ein)
#   FAI_DISCOVERY_SPLASH_MACS=mac1,mac2,...  optional: nur fuer diese Clients, sonst fuer alle
#   FAI_DISCOVERY_LANGUAGE=de|en             Sprache der Anzeige (wie die Webkonsole), Standard de
#
# Wird von install.sh aufgerufen, geht aber auch einzeln:
#   SITE_CONF=... FAI_CONFIG_DIR=... ./deploy-splash.sh
# Aenderungen im Git des Configspace werden nur vorgemerkt (git add), nicht committet; install.sh
# committet sie zusammen mit den uebrigen Configspace-Dateien. Mit DEPLOY_SPLASH_NO_GIT=1 bleibt das Git
# des Configspace voellig unberuehrt (kein git add, kein exclude-Eintrag).
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
SITE_CONF=${SITE_CONF:-/etc/fai-discovery/site.conf}
FAI_CONFIG_DIR=${FAI_CONFIG_DIR:-/srv/fai/config}
SRC="$HERE/fai-config"
SPLASH_DIR="$FAI_CONFIG_DIR/splash"
SUBR="$FAI_CONFIG_DIR/hooks/subroutines"
BEGIN='# BEGIN fai-splash'

OWN=(); [ "$(id -u)" -eq 0 ] && OWN=(-o root -g root)

log() { echo "[deploy-splash] $*"; }
die() { echo "[deploy-splash] FEHLER: $*" >&2; exit 1; }
conf() { { grep -E "^$1=" "$SITE_CONF" 2>/dev/null || true; } | tail -1 | cut -d= -f2- | tr -d '"' | tr -d "'"; }

[ -d "$FAI_CONFIG_DIR/hooks" ] || die "$FAI_CONFIG_DIR/hooks existiert nicht (kein FAI-Configspace?)"

# Block aus hooks/subroutines entfernen (Markerblock und der von Hand eingetragene Vorlaeufer)
strip_block() {
    [ -f "$SUBR" ] || return 0
    local tmp; tmp=$(mktemp)
    awk '
        /^# BEGIN fai-splash/ { skip = 1 }
        /^# fai-splash \(09-install-splash\)/ { legacy = 1 }
        skip { if (/^# END fai-splash/) skip = 0; next }
        legacy { if (/^fi[[:space:]]*$/) legacy = 0; next }
        { print }
    ' "$SUBR" > "$tmp"
    # Leerzeilen am Dateiende zusammenfassen
    cat -s "$tmp" > "$SUBR"
    rm -f "$tmp"
}

enabled=$(conf FAI_DISCOVERY_SPLASH_ENABLED)
macs=$(conf FAI_DISCOVERY_SPLASH_MACS)

if [ "$enabled" = "true" ]; then
    # MAC-Liste pruefen und normalisieren
    allow=""
    if [ -n "$macs" ]; then
        IFS=',' read -ra list <<< "$macs"
        for m in "${list[@]}"; do
            m=$(echo "$m" | tr -d '[:space:]' | tr 'A-F' 'a-f')
            [ -z "$m" ] && continue
            [[ "$m" =~ ^([0-9a-f]{2}:){5}[0-9a-f]{2}$ ]] || die "FAI_DISCOVERY_SPLASH_MACS: '$m' ist keine gueltige MAC-Adresse."
            allow+="$m"$'\n'
        done
    fi

    log "Splash aktiviert - verteile $SPLASH_DIR."
    mkdir -p "$SPLASH_DIR"
    install ${OWN[@]+"${OWN[@]}"} -m 755 "$SRC/splash/fai-splash" "$SPLASH_DIR/fai-splash"
    install ${OWN[@]+"${OWN[@]}"} -m 644 "$SRC/splash/icon.png" "$SPLASH_DIR/icon.png"
    {
        echo "# Von install.sh aus site.conf erzeugt (FAI_DISCOVERY_SPLASH_ENABLED/_MACS), nicht von Hand aendern."
        echo "# Nur diese Clients bekommen den Splash; 'all' = alle. Die Datei ist per git exclude lokal."
        if [ -n "$allow" ]; then printf '%s' "$allow"; else echo "all"; fi
    } > "$SPLASH_DIR/allow-macs"
    chmod 644 "$SPLASH_DIR/allow-macs"
    if [ -n "$allow" ]; then log "Splash nur fuer: $(echo "$allow" | tr '\n' ' ')"; else log "Splash fuer alle Clients."; fi

    # Sprache der Anzeige: FAI_DISCOVERY_LANGUAGE aus site.conf (wie die Webkonsole), de oder en, sonst de
    lang=$(conf FAI_DISCOVERY_LANGUAGE | tr 'A-Z' 'a-z')
    case "$lang" in
        de|en) ;;
        "") lang=de ;;
        *) log "WARNUNG: FAI_DISCOVERY_LANGUAGE='$lang' unbekannt (de oder en), nehme de."; lang=de ;;
    esac
    echo "$lang" > "$SPLASH_DIR/lang"
    chmod 644 "$SPLASH_DIR/lang"
    log "Sprache der Anzeige: $lang"

    [ -f "$SUBR" ] || printf '#! /bin/bash\n\n# sourced during task_setup\n' > "$SUBR"
    strip_block
    { echo; cat "$SRC/hooks-subroutines.snippet"; } >> "$SUBR"
    chmod 644 "$SUBR" 2>/dev/null || true

    # allow-macs gehoert nur diesem Server und darf nicht per git auf andere wandern
    if [ -d "$FAI_CONFIG_DIR/.git" ] && [ -z "${DEPLOY_SPLASH_NO_GIT:-}" ]; then
        excl="$FAI_CONFIG_DIR/.git/info/exclude"; mkdir -p "$(dirname "$excl")"
        for f in splash/allow-macs splash/lang; do
            grep -qxF "$f" "$excl" 2>/dev/null || echo "$f" >> "$excl"
        done
        git -C "$FAI_CONFIG_DIR" add -- splash hooks/subroutines
    fi
else
    if [ -d "$SPLASH_DIR" ] || { [ -f "$SUBR" ] && grep -qE '^# (BEGIN fai-splash|fai-splash \(09-install-splash\))' "$SUBR"; }; then
        log "Splash nicht aktiviert (FAI_DISCOVERY_SPLASH_ENABLED=true in site.conf) - entferne vorhandene Dateien."
    else
        log "Splash nicht aktiviert (FAI_DISCOVERY_SPLASH_ENABLED=true in site.conf), ueberspringe."
    fi
    rm -rf "$SPLASH_DIR"
    strip_block
    if [ -d "$FAI_CONFIG_DIR/.git" ] && [ -z "${DEPLOY_SPLASH_NO_GIT:-}" ]; then
        git -C "$FAI_CONFIG_DIR" add -A -- splash hooks/subroutines 2>/dev/null || true
    fi
fi
