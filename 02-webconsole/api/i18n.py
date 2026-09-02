import os

LANGUAGE_ENV = "FAI_DISCOVERY_LANGUAGE"
DEFAULT_LANGUAGE = "de"
SUPPORTED_LANGUAGES = {"de", "en"}

TRANSLATIONS = {
    "nav.dashboard": {"de": "Dashboard", "en": "Dashboard"},
    "nav.history": {"de": "Historie", "en": "History"},
    "nav.fleet": {"de": "Fleet", "en": "Fleet"},
    "nav.discovery": {"de": "Discovery", "en": "Discovery"},
    "nav.help": {"de": "Hilfe", "en": "Help"},
    "fontsize.aria_label": {"de": "Textgröße", "en": "Text size"},
    "footer.version_unknown": {"de": "unbekannt", "en": "unknown"},

    "dashboard.title": {"de": "Dashboard – fai-discovery", "en": "Dashboard – fai-discovery"},
    "dashboard.heading": {"de": "Wartende Geräte", "en": "Waiting devices"},
    "dashboard.search_placeholder": {
        "de": "Suche nach MAC oder Hostname …",
        "en": "Search by MAC or hostname …",
    },
    "dashboard.since": {"de": "seit", "en": "since"},
    "dashboard.approve_button": {"de": "Freigeben", "en": "Approve"},
    "dashboard.discard_confirm": {
        "de": (
            "Gerät {mac} wirklich stoppen/löschen?\n\n"
            "Deaktiviert die PXE-Boot-Konfiguration (kein erneutes Discovery-Booten) "
            "und entfernt den Eintrag aus dieser Liste. Bereits laufende "
            "Discovery-Sessions werden dadurch nicht sofort unterbrochen."
        ),
        "en": (
            "Really stop/delete device {mac}?\n\n"
            "Disables the PXE boot configuration (no further discovery boot) "
            "and removes the entry from this list. Already-running discovery "
            "sessions are not interrupted immediately by this."
        ),
    },
    "dashboard.discard_button": {"de": "Stop/Löschen", "en": "Stop/Delete"},
    "dashboard.empty": {
        "de": "Aktuell wartet kein Gerät auf Freigabe.",
        "en": "No device is currently waiting for approval.",
    },

    "history.title": {"de": "Historie – fai-discovery", "en": "History – fai-discovery"},
    "history.heading": {"de": "Freigabe-Historie", "en": "Approval history"},
    "history.search_placeholder": {
        "de": "Suche nach MAC, Hostname, Profil, Seriennummer, UUID oder Admin …",
        "en": "Search by MAC, hostname, profile, serial number, UUID or admin …",
    },
    "history.search_button": {"de": "Suchen", "en": "Search"},
    "history.col_mac": {"de": "MAC", "en": "MAC"},
    "history.col_hostname": {"de": "Hostname", "en": "Hostname"},
    "history.col_profile": {"de": "Profil", "en": "Profile"},
    "history.col_approved_by": {"de": "Freigegeben von", "en": "Approved by"},
    "history.col_approved_at": {"de": "Am", "en": "On"},
    "history.delete_confirm": {
        "de": "Eintrag für {mac} wirklich löschen?\n\nHinweis: Nur nach Abschluss der Installation löschen!",
        "en": "Really delete the entry for {mac}?\n\nNote: only delete after the installation has finished!",
    },
    "history.delete_button": {"de": "Löschen", "en": "Delete"},
    "history.reinstall_confirm": {
        "de": (
            "Gerät {mac} wirklich neu installieren?\n\n"
            "Versetzt das Gerät zurück in den Discovery-Modus. Beim nächsten "
            "PXE-Boot erscheint es wieder im Dashboard und wartet auf erneute "
            "Freigabe."
        ),
        "en": (
            "Really reinstall device {mac}?\n\n"
            "Puts the device back into discovery mode. On its next PXE boot it "
            "reappears on the dashboard and waits for approval again."
        ),
    },
    "history.reinstall_button": {"de": "Neuinstallation", "en": "Reinstall"},
    "history.logs_button": {"de": "Logs", "en": "Logs"},
    "history.status_reinstalling": {
        "de": "Wartet auf Neuinstallation",
        "en": "Waiting for reinstall",
    },
    "history.no_results": {
        "de": "Keine Treffer für „{query}\".",
        "en": 'No results for "{query}".',
    },
    "history.no_entries": {"de": "Noch keine Freigaben.", "en": "No approvals yet."},

    "fleet.title": {"de": "Fleet – fai-discovery", "en": "Fleet – fai-discovery"},
    "fleet.heading": {"de": "Fleet-Übersicht", "en": "Fleet overview"},
    "fleet.search_placeholder": {
        "de": "Suche nach MAC, Hostname, Profil, Seriennummer, UUID oder Admin …",
        "en": "Search by MAC, hostname, profile, serial number, UUID or admin …",
    },
    "fleet.search_button": {"de": "Suchen", "en": "Search"},
    "fleet.col_mac": {"de": "MAC", "en": "MAC"},
    "fleet.col_hostname": {"de": "Hostname", "en": "Hostname"},
    "fleet.col_ip": {"de": "IP", "en": "IP"},
    "fleet.col_cpu": {"de": "CPU", "en": "CPU"},
    "fleet.col_ram": {"de": "RAM", "en": "RAM"},
    "fleet.col_disk": {"de": "Disk", "en": "Disk"},
    "fleet.col_uuid": {"de": "UUID", "en": "UUID"},
    "fleet.col_serial": {"de": "Seriennummer", "en": "Serial number"},
    "fleet.col_firmware": {"de": "Firmware", "en": "Firmware"},
    "fleet.col_profile": {"de": "Profil", "en": "Profile"},
    "fleet.col_approved_at": {"de": "Installiert am", "en": "Installed on"},
    "fleet.no_results": {
        "de": "Keine Treffer für „{query}\".",
        "en": 'No results for "{query}".',
    },
    "fleet.no_entries": {"de": "Noch keine installierten Geräte.", "en": "No installed devices yet."},

    "discovery.title": {
        "de": "Discovery-Modus auslösen – fai-discovery",
        "en": "Trigger discovery mode – fai-discovery",
    },
    "discovery.heading": {"de": "Discovery-Modus auslösen", "en": "Trigger discovery mode"},
    "discovery.description": {
        "de": (
            "Ein oder mehrere noch nicht registrierte Geräte per MAC-Adresse "
            "gezielt in den Discovery-Modus versetzen."
        ),
        "en": (
            "Explicitly put one or more not-yet-registered devices into "
            "discovery mode by MAC address."
        ),
    },
    "discovery.macs_label": {
        "de": "MAC-Adressen (kommagetrennt)",
        "en": "MAC addresses (comma-separated)",
    },
    "discovery.submit_button": {"de": "Discovery starten", "en": "Start discovery"},
    "discovery.col_mac": {"de": "MAC", "en": "MAC"},
    "discovery.col_status": {"de": "Status", "en": "Status"},
    "discovery.col_message": {"de": "Meldung", "en": "Message"},
    "discovery.status_ok": {"de": "OK", "en": "OK"},
    "discovery.status_error": {"de": "Fehler", "en": "Error"},
    "discovery.error_no_macs": {
        "de": "Bitte mindestens eine MAC-Adresse eingeben.",
        "en": "Please enter at least one MAC address.",
    },
    "discovery.error_invalid_mac": {
        "de": "ungültiges MAC-Format",
        "en": "invalid MAC format",
    },
    "discovery.error_already_registered": {
        "de": (
            "Gerät ist bereits registriert (Status: {status}) — Discovery-Trigger "
            "nur für unregistrierte Geräte."
        ),
        "en": (
            "Device is already registered (status: {status}) — discovery trigger "
            "only works for unregistered devices."
        ),
    },

    "approve.title": {"de": "Freigeben {mac} – fai-discovery", "en": "Approve {mac} – fai-discovery"},
    "approve.heading": {"de": "Gerät freigeben: {mac}", "en": "Approve device: {mac}"},
    "approve.error_profile_unreadable": {
        "de": "Profil-Datei nicht lesbar: {path}",
        "en": "Profile file not readable: {path}",
    },
    "approve.error_invalid_form": {
        "de": (
            "Bitte einen gültigen Hostnamen eingeben (nur Kleinbuchstaben, Ziffern, "
            "Bindestriche; muss mit Buchstabe oder Ziffer beginnen und enden; max. "
            "63 Zeichen) und ein Profil auswählen."
        ),
        "en": (
            "Please enter a valid hostname (lowercase letters, digits, hyphens "
            "only; must start and end with a letter or digit; max. 63 characters) "
            "and choose a profile."
        ),
    },
    "approve.error_chboot_failed": {
        "de": "fai-chboot fehlgeschlagen: {detail}",
        "en": "fai-chboot failed: {detail}",
    },
    "approve.hostname_help_heading": {
        "de": "Hilfen für den Hostnamen (optional)",
        "en": "Hostname helpers (optional)",
    },
    "approve.hostname_help_hint": {
        "de": (
            "Setzt jeweils einen festen Platz im Hostnamen-Feld unten (Typ – "
            "Standort – Serial/UUID) und baut es bei jedem Klick komplett neu "
            "zusammen — manuell eingetippter Text wird dabei ersetzt."
        ),
        "en": (
            "Each sets a fixed slot in the hostname field below (type – "
            "location – serial/UUID) and rebuilds it completely on every click "
            "— manually typed text is replaced by this."
        ),
    },
    "approve.apply_type": {"de": "Typ übernehmen", "en": "Apply type"},
    "approve.apply_location": {"de": "Standort übernehmen", "en": "Apply location"},
    "approve.apply_serial": {"de": "Serial übernehmen: {value}", "en": "Apply serial: {value}"},
    "approve.apply_uuid": {"de": "UUID übernehmen: {value}", "en": "Apply UUID: {value}"},
    "approve.hostname_label": {"de": "Hostname", "en": "Hostname"},
    "approve.hostname_hint": {
        "de": (
            "Nur Kleinbuchstaben, Ziffern, Bindestriche; muss mit Buchstabe oder "
            "Ziffer beginnen und enden; max. 63 Zeichen."
        ),
        "en": (
            "Lowercase letters, digits, hyphens only; must start and end with "
            "a letter or digit; max. 63 characters."
        ),
    },
    "approve.previous_hostname_heading": {
        "de": "Zuvor installiert als",
        "en": "Previously installed as",
    },
    "approve.previous_hostname_hint": {
        "de": (
            "Dieses Gerät lief zuletzt unter dem Hostnamen „{hostname}\". Übernehmen "
            "ersetzt den kompletten Inhalt des Hostnamen-Felds unten."
        ),
        "en": (
            'This device was last known under the hostname "{hostname}". '
            "Applying it replaces the entire content of the hostname field below."
        ),
    },
    "approve.apply_previous_hostname": {
        "de": "Vorherigen Hostnamen übernehmen",
        "en": "Apply previous hostname",
    },
    "approve.profile_label": {"de": "Zielprofil", "en": "Target profile"},
    "approve.profile_placeholder": {"de": "Profil wählen …", "en": "Choose profile …"},
    "approve.reboot_label": {
        "de": "Nach der Installation automatisch neu starten",
        "en": "Reboot automatically after installation",
    },
    "approve.reboot_hint": {
        "de": "Standardmäßig aus: der Client bleibt nach der Installation stehen, bis am Gerät selbst ENTER gedrückt wird.",
        "en": "Off by default: the client stays halted after installation until ENTER is pressed on the device itself.",
    },
    "approve.verbose_label": {
        "de": "Ausführliche Installationsausgabe",
        "en": "Verbose installation output",
    },
    "approve.verbose_hint": {
        "de": "Betrifft nur die Ausgabe des FAI-Installers auf dem Client, nicht die Fehlerausgabe von fai-chboot selbst in der Webkonsole (die bleibt immer erhalten).",
        "en": "Only affects the FAI installer's output on the client, not fai-chboot's own error output in the webconsole (which always stays on).",
    },
    "approve.submit_button": {"de": "Freigeben", "en": "Approve"},

    "logs.title": {"de": "Install-Logs – fai-discovery", "en": "Install logs – fai-discovery"},
    "logs.heading": {"de": "Install-Logs für {hostname}", "en": "Install logs for {hostname}"},
    "logs.run_label": {"de": "Lauf", "en": "Run"},
    "logs.status_ok": {"de": "Erfolgreich (task_error 0)", "en": "Successful (task_error 0)"},
    "logs.status_failed": {
        "de": "Fehler (task_error {code})",
        "en": "Error (task_error {code})",
    },
    "logs.status_unknown": {"de": "Status unbekannt", "en": "Status unknown"},
    "logs.status_heading": {"de": "Task-Status", "en": "Task status"},
    "logs.error_heading": {"de": "Fehler/Warnungen", "en": "Errors/warnings"},
    "logs.full_log_link": {"de": "Vollständiges fai.log ansehen", "en": "View full fai.log"},
    "logs.back_to_history": {"de": "Zurück zur Historie", "en": "Back to history"},

    "nav.progress": {"de": "Fortschritt", "en": "Progress"},

    "progress.title": {"de": "Installationsfortschritt – fai-discovery", "en": "Installation progress – fai-discovery"},
    "progress.heading": {"de": "Live-Installationsfortschritt", "en": "Live installation progress"},
    "progress.empty": {
        "de": "Aktuell läuft keine Installation, keine kürzlich abgeschlossene vorhanden.",
        "en": "No installation is currently running, and none finished recently.",
    },
    "progress.status_running": {"de": "läuft", "en": "running"},
    "progress.status_ok": {"de": "fertig", "en": "done"},
    "progress.status_failed": {"de": "fehlgeschlagen", "en": "failed"},
    "progress.run_label": {"de": "Lauf", "en": "Run"},

    "errors.unknown_mac": {"de": "Unbekannte MAC", "en": "Unknown MAC"},
    "errors.invalid_mac": {"de": "Ungültige MAC-Adresse", "en": "Invalid MAC address"},
    "errors.unknown_or_undeletable": {
        "de": "Unbekannter oder nicht löschbarer Eintrag",
        "en": "Unknown or non-deletable entry",
    },
    "errors.unknown_or_not_reinstallable": {
        "de": "Unbekannter oder nicht neu installierbarer Eintrag",
        "en": "Unknown or non-reinstallable entry",
    },
    "errors.unknown_or_no_logs": {
        "de": "Unbekannter Eintrag oder keine Logs vorhanden",
        "en": "Unknown entry or no logs available",
    },
    "errors.unknown_or_undiscardable": {
        "de": "Unbekanntes oder nicht verwerfbares Gerät",
        "en": "Unknown or non-discardable device",
    },
    "errors.chboot_failed": {
        "de": "fai-chboot fehlgeschlagen: {detail}",
        "en": "fai-chboot failed: {detail}",
    },

    "help.title": {"de": "Hilfe – fai-discovery", "en": "Help – fai-discovery"},
    "help.heading": {"de": "Hilfe", "en": "Help"},

    "help.workflow_heading": {"de": "Ablauf", "en": "Workflow"},
    "help.workflow_text": {
        "de": (
            'Ein Gerät bootet im Discovery-Modus und registriert sich selbst bei '
            'dieser Webkonsole. Es erscheint anschließend als Karte im '
            '<a href="{dashboard_url}">Dashboard</a> unter '
            '„Wartende Geräte". Ein Admin vergibt dort einen Hostnamen und ein '
            'Zielprofil und gibt das Gerät frei. Das Gerät bootet daraufhin neu '
            'und beginnt die eigentliche Installation. Nach der Freigabe erscheint '
            'der Eintrag in der <a href="{history_url}">Historie</a>.'
        ),
        "en": (
            'A device boots into discovery mode and registers itself with this '
            'web console. It then appears as a card on the '
            '<a href="{dashboard_url}">dashboard</a> under '
            '"Waiting devices". An admin assigns a hostname and a target profile '
            'there and approves the device. The device then reboots and starts '
            'the actual installation. After approval, the entry appears in the '
            '<a href="{history_url}">history</a>.'
        ),
    },

    "help.manual_discovery_heading": {
        "de": "Discovery-Modus manuell auslösen",
        "en": "Triggering discovery mode manually",
    },
    "help.manual_discovery_text": {
        "de": (
            'Über <a href="{discovery_url}">Discovery</a> lässt sich ein noch '
            'nicht registriertes Gerät gezielt per MAC-Adresse in den '
            'Discovery-Modus versetzen (statt darauf zu warten, dass es sich von '
            'selbst meldet). Mehrere MAC-Adressen können kommagetrennt eingegeben '
            'werden — jede wird einzeln verarbeitet, ein Fehler bei einer MAC '
            'blockiert nicht die übrigen. Bereits registrierte Geräte (wartend '
            'oder schon freigegeben) werden abgelehnt, um ihren bestehenden '
            'PXE-Eintrag nicht versehentlich zu überschreiben. Über den '
            '"Stop/Löschen" Button kann der Discovery-Modus eines Clients '
            'gestoppt werden, anschließend startet der Client neu.'
        ),
        "en": (
            'Via <a href="{discovery_url}">Discovery</a> a not-yet-registered '
            'device can be explicitly put into discovery mode by MAC address '
            '(instead of waiting for it to report in on its own). Multiple MAC '
            'addresses can be entered comma-separated — each is processed '
            'individually, an error on one MAC does not block the others. '
            'Already-registered devices (waiting or already approved) are '
            'rejected, to avoid accidentally overwriting their existing PXE '
            'entry. The "Stop/Delete" button can be used to stop a client\'s '
            'discovery mode, after which the client reboots.'
        ),
    },

    "help.hostname_rules_heading": {"de": "Hostnamen-Regeln", "en": "Hostname rules"},
    "help.hostname_rules_text": {
        "de": (
            "Nur Kleinbuchstaben, Ziffern, Bindestriche; muss mit Buchstabe oder "
            "Ziffer beginnen und enden; max. 63 Zeichen."
        ),
        "en": (
            "Lowercase letters, digits, hyphens only; must start and end with "
            "a letter or digit; max. 63 characters."
        ),
    },

    "help.uefi_heading": {
        "de": "Automatische UEFI-Erkennung",
        "en": "Automatic UEFI detection",
    },
    "help.uefi_text": {
        "de": (
            'Meldet ein Gerät beim Discovery-Boot UEFI-Firmware, wählt die '
            'Webkonsole beim Freigeben automatisch die passende '
            '<code>_EFI</code>-Variante der Disk-Config (falls für das gewählte '
            'Profil eine existiert, z. B. <code>FAIBASE_EFI</code> statt '
            '<code>FAIBASE</code>) — mit GPT-Partitionstabelle und EFI System '
            'Partition. Existiert keine <code>_EFI</code>-Variante, bleibt es '
            'beim Standard-Layout, wie bisher. Das Verzeichnis, in dem nach '
            'diesen Dateien gesucht wird, lässt sich über '
            '<code>FAI_DISCOVERY_DISK_CONFIG_DIR</code> in '
            '<code>/etc/fai-discovery/site.conf</code> konfigurieren (Default: '
            '<code>/srv/fai/config/disk_config</code>). '
            'Voraussetzung: Ein Profil sollte nur eine einzige Disk-Layout-Klasse '
            'enthalten (z. B. <code>FAIBASE</code> oder <code>BTRFS</code>, nicht '
            'beide kombiniert) — sonst kann die automatische Auswahl auf UEFI ein '
            'anderes Layout treffen als auf BIOS.'
        ),
        "en": (
            'If a device reports UEFI firmware during the discovery boot, the '
            'web console automatically chooses the matching <code>_EFI</code> '
            'variant of the disk config when approving (if one exists for the '
            'selected profile, e.g. <code>FAIBASE_EFI</code> instead of '
            '<code>FAIBASE</code>) — with a GPT partition table and an EFI '
            'System Partition. If no <code>_EFI</code> variant exists, it falls '
            'back to the standard layout as before. The directory these files '
            'are searched in can be configured via '
            '<code>FAI_DISCOVERY_DISK_CONFIG_DIR</code> in '
            '<code>/etc/fai-discovery/site.conf</code> (default: '
            '<code>/srv/fai/config/disk_config</code>). '
            'Requirement: a profile should contain only a single disk-layout '
            'class (e.g. <code>FAIBASE</code> or <code>BTRFS</code>, not both '
            'combined) — otherwise the automatic selection may pick a different '
            'layout on UEFI than on BIOS.'
        ),
    },

    "help.hostname_helpers_heading": {
        "de": "Hilfen für den Hostnamen: Präfixe & Vorschläge",
        "en": "Hostname helpers: prefixes & suggestions",
    },
    "help.hostname_helpers_text1": {
        "de": (
            'Ist in <code>/etc/fai-discovery/site.conf</code> mindestens eine der '
            'Variablen <code>FAI_DISCOVERY_TYPE_PREFIXES</code> (Gerätetyp, z. B. '
            '<code>NB:Notebook,DT:Desktop</code>) oder '
            '<code>FAI_DISCOVERY_LOCATION_PREFIXES</code> (Standort, z. B. '
            '<code>K:Köln,B:Berlin</code>) gesetzt, erscheint im Freigabe-Formular '
            'ein zusätzlicher Block mit einem Dropdown je Liste. Der jeweils '
            'erste Eintrag einer Liste ist im Dropdown vorausgewählt — die '
            'Reihenfolge in <code>site.conf</code> bestimmt also die '
            'Standardauswahl. Zusätzlich bietet die Webkonsole, sofern beim '
            'Discovery-Boot eine verwertbare Seriennummer bzw. UUID erfasst '
            'wurde, je einen Vorschlag-Button dafür an. '
            '<strong>Wichtig:</strong> Änderungen an <code>site.conf</code> '
            'werden erst nach einem Neustart des Webkonsole-Diensts wirksam — '
            'ein Eintragen der Präfix-Variablen allein reicht nicht, ohne '
            'Neustart bleibt der Hilfe-Block auf der Freigabe-Seite unverändert.'
        ),
        "en": (
            'If at least one of the variables '
            '<code>FAI_DISCOVERY_TYPE_PREFIXES</code> (device type, e.g. '
            '<code>NB:Notebook,DT:Desktop</code>) or '
            '<code>FAI_DISCOVERY_LOCATION_PREFIXES</code> (location, e.g. '
            '<code>K:Cologne,B:Berlin</code>) is set in '
            '<code>/etc/fai-discovery/site.conf</code>, the approval form shows '
            'an extra block with one dropdown per list. The first entry of a '
            'list is preselected in the dropdown — so the order in '
            '<code>site.conf</code> determines the default choice. In addition, '
            'if a usable serial number or UUID was captured during the '
            'discovery boot, the web console offers one suggestion button for '
            'each. <strong>Important:</strong> changes to <code>site.conf</code> '
            'only take effect after restarting the web console service — '
            'adding the prefix variables alone is not enough, without a '
            'restart the helper block on the approval page stays unchanged.'
        ),
    },
    "help.hostname_helpers_text2": {
        "de": (
            "Jeder der bis zu vier Buttons (Typ übernehmen, Standort übernehmen, "
            "Serial übernehmen, UUID übernehmen) setzt einen festen Platz im "
            "Hostnamen-Feld. Das Feld wird bei jedem Klick komplett aus allen "
            "bisher gesetzten Plätzen neu zusammengesetzt, in der festen "
            "Reihenfolge Typ – Standort – Serial/UUID, unabhängig davon in "
            "welcher Reihenfolge geklickt wurde. Serial und UUID teilen sich "
            "denselben (dritten) Platz — ein zweiter Klick auf den jeweils "
            "anderen Button ersetzt den vorherigen Wert. Das Hostnamen-Feld "
            "bleibt jederzeit frei editierbar; nur ein erneuter Button-Klick "
            "überschreibt manuell eingetippten Text wieder mit der "
            "Zusammensetzung aus den drei Plätzen. Alle vier Hilfen sind ein "
            "Angebot, kein Zwang — ein komplett frei eingetippter Hostname "
            "funktioniert unverändert."
        ),
        "en": (
            "Each of the up to four buttons (apply type, apply location, apply "
            "serial, apply UUID) sets a fixed slot in the hostname field. The "
            "field is completely rebuilt on every click from all slots set so "
            "far, in the fixed order type – location – serial/UUID, regardless "
            "of the order they were clicked in. Serial and UUID share the same "
            "(third) slot — a second click on the other button replaces the "
            "previous value. The hostname field stays freely editable at any "
            "time; only another button click overwrites manually typed text "
            "again with the composition from the three slots. All four helpers "
            "are an offer, not a requirement — a completely freely typed "
            "hostname works unchanged."
        ),
    },

    "help.history_delete_heading": {
        "de": "Historie-Einträge löschen",
        "en": "Deleting history entries",
    },
    "help.history_delete_text": {
        "de": (
            'In der Historie kann jeder Eintrag über den „Löschen"-Button '
            'endgültig entfernt werden (nach Bestätigung). Das betrifft nur '
            'bereits freigegebene Geräte, keine noch wartenden. '
            '<strong>Wichtig:</strong> Einträge sollten erst nach Abschluss der '
            'Installation auf dem Gerät gelöscht werden, da der Eintrag auch '
            'während der Installation als Quelle für die Hostnamen-Auflösung '
            'dient.'
        ),
        "en": (
            'In the history, every entry can be permanently removed via the '
            '"Delete" button (after confirmation). This only affects '
            'already-approved devices, not ones still waiting. '
            '<strong>Important:</strong> entries should only be deleted after '
            'the installation on the device has finished, since the entry also '
            'serves as the source for hostname resolution during the '
            'installation.'
        ),
    },

    "help.history_search_heading": {
        "de": "Suche in der Historie",
        "en": "Searching the history",
    },
    "help.history_search_text": {
        "de": (
            'Das Suchfeld oberhalb der Historie-Tabelle durchsucht gleichzeitig '
            'MAC, Hostname, Profil, Seriennummer, UUID und „Freigegeben von" — '
            'es reicht, einen Teil eines dieser Werte einzugeben, eine exakte '
            'Übereinstimmung ist nicht nötig. <strong>Wichtig:</strong> Die '
            'Suche läuft serverseitig, die Seite lädt beim Absenden neu; anders '
            'als beim Suchfeld im Dashboard wird also nicht schon während der '
            'Eingabe gefiltert. Liefert die Suche keinen Treffer, erscheint '
            'statt der Tabellenzeilen ein Hinweis, dass es für den eingegebenen '
            'Begriff keine Treffer gibt.'
        ),
        "en": (
            'The search field above the history table simultaneously searches '
            'MAC, hostname, profile, serial number, UUID and "approved by" — '
            'it is enough to enter part of one of these values, an exact match '
            'is not required. <strong>Important:</strong> the search runs '
            'server-side, the page reloads on submit; unlike the search field '
            'on the dashboard, results are not filtered while typing. If the '
            'search finds no match, a message is shown instead of the table '
            'rows stating that there were no results for the entered term.'
        ),
    },

    "help.history_reinstall_heading": {
        "de": "Neuinstallation über die Historie",
        "en": "Reinstalling via the history",
    },
    "help.history_reinstall_text": {
        "de": (
            'In der Historie kann jeder Eintrag über den „Neuinstallation"-Button '
            '(nach Bestätigung) zurück in den Discovery-Modus versetzt werden — '
            'technisch identisch zum manuellen Discovery-Trigger, nur ohne die '
            'MAC-Adresse erneut eintippen zu müssen. Der Eintrag bleibt danach '
            'sichtbar, zeigt aber statt der Buttons das Badge „Wartet auf '
            'Neuinstallation" — als optische Bestätigung, dass der Klick '
            'gewirkt hat. Sobald das Gerät daraufhin erneut per PXE bootet, '
            'meldet es sich wieder frisch bei der Webkonsole und erscheint im '
            'Dashboard unter „Wartende Geräte" — der Historie-Eintrag '
            'verschwindet dabei, da er ja nicht mehr freigegeben ist. Beim '
            'erneuten Freigeben wird der zuletzt vergebene Hostname als '
            'Ein-Klick-Vorschlag angeboten.'
        ),
        "en": (
            'In the history, every entry can be put back into discovery mode via '
            'the "Reinstall" button (after confirmation) — technically identical '
            'to the manual discovery trigger, just without having to retype the '
            'MAC address. The entry stays visible afterwards, but shows the '
            '"Waiting for reinstall" badge instead of the buttons — a visual '
            'confirmation that the click took effect. Once the device boots via '
            'PXE again, it re-registers with the web console and reappears on '
            'the dashboard under "Waiting '
            'devices" — the history entry disappears in the process, since it is '
            'no longer approved. When approving it again, the most recently '
            'assigned hostname is offered as a one-click suggestion.'
        ),
    },

    "help.history_logs_heading": {
        "de": "Install-Logs ansehen",
        "en": "Viewing install logs",
    },
    "help.history_logs_text": {
        "de": (
            'Jeder Historie-Eintrag hat einen „Logs"-Button, der die von FAI nach '
            'jeder Installation automatisch abgelegten Log-Dateien anzeigt: eine '
            'kompakte Liste aller ausgeführten Scripts mit OK/Fehler-Status, sowie '
            '— falls vorhanden — gesammelte Fehler-/Warnmeldungen. Für die '
            'Tiefenanalyse verlinkt die Seite zusätzlich das vollständige, sehr '
            'ausführliche fai.log. Bei mehrfacher Neuinstallation unter demselben '
            'Hostnamen wird immer der jeweils neueste Installationslauf angezeigt.'
        ),
        "en": (
            'Every history entry has a "Logs" button showing the log files FAI '
            'automatically saves after each installation: a compact list of all '
            'executed scripts with OK/failed status, plus — if present — '
            'collected error/warning messages. For deeper analysis, the page also '
            'links to the full, very detailed fai.log. If a device was reinstalled '
            'multiple times under the same hostname, the most recent installation '
            'run is always shown.'
        ),
    },

    "help.progress_heading": {
        "de": "Live-Installationsfortschritt",
        "en": "Live installation progress",
    },
    "help.progress_text": {
        "de": (
            'Über <code>Fortschritt</code> in der Navigation zeigt die '
            'Webkonsole für alle gerade laufenden Installationen den '
            'FAI-Task-Status live an — ähnlich der originalen '
            '<code>fai-monitor-gui</code>, nur im Browser statt als '
            'X11/Tk-Anwendung. Datenquelle ist das globale '
            '<code>fai-monitor.log</code> auf dem Server (Dienst '
            '<code>fai-monitor.service</code>); die Zuordnung zu einem '
            'Gerät erfolgt über dessen MAC-Adresse, nicht über den '
            'Hostnamen — so bleibt die Zuordnung auch dann korrekt, wenn '
            'der Hostname erst während der laufenden Installation gesetzt '
            'wird. Bereits abgeschlossene Installationen erscheinen auf '
            'dieser Seite nicht mehr; deren Task-Status lässt sich weiterhin '
            'über die „Logs"-Ansicht in der Historie nachvollziehen.'
        ),
        "en": (
            'Via <code>Progress</code> in the navigation, the web console '
            'shows the live FAI task status for all currently running '
            'installations — similar to the original '
            '<code>fai-monitor-gui</code>, but in the browser instead of '
            'an X11/Tk application. The data source is the global '
            '<code>fai-monitor.log</code> on the server (service '
            '<code>fai-monitor.service</code>); matching to a device '
            'happens via its MAC address rather than its hostname — so '
            'the match stays correct even when the hostname is only set '
            'during the running installation. Already-finished '
            'installations no longer appear on this page; their task '
            'status can still be reviewed via the "Logs" view in the '
            'history.'
        ),
    },

    "help.language_heading": {
        "de": "Sprache der Webkonsole",
        "en": "Web console language",
    },
    "help.language_text": {
        "de": (
            'Über <code>FAI_DISCOVERY_LANGUAGE</code> in '
            '<code>/etc/fai-discovery/site.conf</code> lässt sich die Sprache '
            'der Webkonsole (Navigation, Formulare, Fehlermeldungen, diese '
            'Hilfe-Seite) auf <code>de</code> oder <code>en</code> festlegen. '
            'Fehlt die Variable oder hat sie einen anderen Wert, bleibt es beim '
            'bisherigen Verhalten (Deutsch). <strong>Wichtig:</strong> wie bei '
            'den übrigen <code>site.conf</code>-Variablen ist nach einer '
            'Änderung ein Neustart des Webkonsole-Diensts nötig.'
        ),
        "en": (
            'The <code>FAI_DISCOVERY_LANGUAGE</code> variable in '
            '<code>/etc/fai-discovery/site.conf</code> sets the web console '
            'language (navigation, forms, error messages, this help page) to '
            '<code>de</code> or <code>en</code>. If the variable is missing or '
            'has a different value, it falls back to the previous behavior '
            '(German). <strong>Important:</strong> as with the other '
            '<code>site.conf</code> variables, a restart of the web console '
            'service is required after a change.'
        ),
    },

    "help.display_heading": {
        "de": "Darstellung: Farbschema & Textgröße",
        "en": "Display: color scheme & text size",
    },
    "help.display_text": {
        "de": (
            'Der Button oben rechts in der Navigation schaltet zwischen '
            '„System" (folgt der Geräteeinstellung), „Light" und „Dark" um — '
            'ein Klick springt jeweils zur nächsten Option. Die Buttons '
            '„100%"/„125%"/„150%" daneben vergrößern nur den Text, nicht das '
            'restliche Layout (für bessere Lesbarkeit bei Sehschwäche). Beide '
            'Einstellungen werden im Browser gespeichert und gelten auf allen '
            'Seiten, bis sie geändert werden.'
        ),
        "en": (
            'The button in the top right of the navigation cycles between '
            '"System" (follows the device setting), "Light" and "Dark" — one '
            'click advances to the next option. The "100%"/"125%"/"150%" '
            'buttons next to it only enlarge the text, not the rest of the '
            'layout (for better readability with impaired vision). Both '
            'settings are stored in the browser and apply on all pages until '
            'changed.'
        ),
    },
}


def current_language():
    value = os.environ.get(LANGUAGE_ENV, DEFAULT_LANGUAGE)
    return value if value in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def t(key, **kwargs):
    text = TRANSLATIONS[key][current_language()]
    return text.format(**kwargs) if kwargs else text
