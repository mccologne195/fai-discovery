# 09-install-splash: Vollbild-Anzeige im Install-Environment

Statt weißer Schrift auf schwarzem Terminal zeigt der Client beim Discovery- und
Installations-Boot eine Vollbild-Anzeige mit dem FAI-Discovery-Icon, dem aktuellen Status und
einem Fortschrittsbalken.

Englische Fassung dieser Datei: [README.en.md](README.en.md).

Die Grundidee stammt von FAI (Fully Automatic Installation) von Thomas Lange, <https://fai-project.org>. Die Anzeige
nennt das klein am unteren Rand.

> **Status:** Fester Bestandteil von fai-discovery, zweisprachig (Deutsch/Englisch), per `site.conf` abschaltbar
> (Standard: aus). Getestet in einer Test-VM (UEFI/OVMF, Proxmox-VGA `std`, 1280x800) und live auf
> einem Lenovo ThinkPad T490 (Intel i915, 1920x1080): Discovery, Freigabe, Installation (Debian 13) bis
> "Installation abgeschlossen", Fortschrittsbalken, Tasten und Neustart per Enter. Nicht getestet:
> Fehleranzeige im echten Lauf, BIOS-Boot, andere Grafikchips (AMD, NVIDIA).

## Was angezeigt wird

Die Texte erscheinen auf Deutsch oder Englisch, je nach `FAI_DISCOVERY_LANGUAGE` in der `site.conf` (`de` oder `en`,
Standard `de`, dieselbe Einstellung wie bei der Webkonsole). Die Tabelle zeigt die deutschen Texte.

| Phase | Anzeige |
|-------|---------|
| Discovery | "Gerät wird gemeldet", dann "Warte auf Freigabe" mit MAC und IP und einem laufenden Balken, nach der Freigabe "Freigabe erteilt" |
| Installation | "Installation läuft", "Schritt n von 17: <Task>" und ein Fortschrittsbalken in Prozent |
| Ende | "Installation abgeschlossen" (grün, 100 %). Fehlt das Flag `reboot` in `FAI_FLAGS`, steht dort "Zum Neustart Enter drücken": Enter auf der Anzeige startet das Gerät neu (über `faireboot`). Alternativ wie bisher Alt+F1 und dort Enter |
| Fehler | "Fehler im Schritt: <Task>" (rot) mit Hinweis auf Alt+F1/Alt+F2 |

Das Ende wird schon bei `TASKBEGIN faiend` angezeigt, weil `task_faiend` ohne `reboot`-Flag auf Enter wartet
und `TASKEND faiend` deshalb nie kommt. Tastendrücke, die vor diesem Zeitpunkt auf der Anzeige gemacht wurden,
werden verworfen, ein versehentliches Enter löst also keinen Neustart aus.

Die Anzeige läuft auf einem eigenen virtuellen Terminal (tty8). Mit **Alt+F1** sieht man weiter
das FAI-Log, mit **Alt+F2** die Shell (`createvt`), mit **Alt+F8** wieder die Anzeige. Auf Notebooks, bei
denen die Funktionstasten als Medientasten belegt sind, zusätzlich **Fn** drücken.

## Funktionsweise

- `fai-splash` ist ein Python-3-Skript nur mit der Standardbibliothek (Python und die
  PSF-Konsolenschriften sind im NFSROOT schon vorhanden, es wird nichts nachinstalliert).
- Es zeichnet direkt in `/dev/fb0` (32 Bit, per `write()`) und schaltet tty8 in den Grafikmodus, damit
  die Konsole nicht darüber schreibt. Gibt es noch keinen Framebuffer (BIOS-Boot: der DRM-Treiber wird erst
  später geladen), wartet es bis zu 3 Minuten darauf. Kommt keiner oder hat er nicht 32 Bit, beendet es sich
  still, und die Installation läuft wie bisher auf der Textkonsole.
- Der Installationsfortschritt kommt aus `$LOGDIR/fai-monitor.log`: FAI schreibt dort bei jedem
  Task `TASKBEGIN`/`TASKEND`/`TASKERROR` hinein (`sendmon` in `/usr/lib/fai/subroutines`). Dadurch
  braucht es keine Eingriffe in FAI oder in einzelne Task-Hooks.
- Meldungen von Hooks (Discovery) laufen über `fai-splash say -k info|wait|ok|error -m NAME
  [-s UNTERZEILE] [-d DETAIL] [-p PROZENT]`. `-m` holt Zeile und Unterzeile aus dem zweisprachigen Textverzeichnis
  (`TEXT` in `fai-splash`, Namen `msg.*`); mit `-l`/`-s` lassen sich Texte direkt vorgeben.
- Alle sichtbaren Texte stehen in `TEXT` (und `TASKS` für die Schritt-Namen) je mit `de` und `en`. Die Sprache
  bestimmt `FAI_SPLASH_LANG`, sonst die Datei `splash/lang` neben dem Skript, sonst Deutsch. `deploy-splash.sh`
  schreibt `splash/lang` aus `FAI_DISCOVERY_LANGUAGE`.
- Das Icon `icon.png` stammt aus `icon/fai-discovery-icon-512.png` und wird zur Laufzeit dekodiert
  und skaliert. Die Farben der Streifen sind der Palette des Icons entnommen.

## Dateien

```
09-install-splash/
├── README.md / README.en.md
├── test_fai_splash.py      Tests (Übersetzungen, Sprachwahl, Schrift)
├── deploy-splash.sh        verteilt/entfernt den Splash nach site.conf (von install.sh aufgerufen)
└── fai-config/
    ├── hooks-subroutines.snippet   Block für hooks/subroutines
    └── splash/
        ├── fai-splash      Dienst, Aufruf siehe oben
        ├── icon.png        Icon (512 px)
        ├── allow-macs      (erzeugt von deploy-splash.sh) für welche Clients der Splash läuft
        └── lang            (erzeugt von deploy-splash.sh) de oder en
```

## Einbau und Steuerung über site.conf

Der Splash ist **opt-in** und wird in `/etc/fai-discovery/site.conf` eingeschaltet:

```
FAI_DISCOVERY_SPLASH_ENABLED=true
# optional: nur für diese Clients (kommagetrennt), sonst für alle
FAI_DISCOVERY_SPLASH_MACS=00:11:22:33:44:55,66:77:88:99:aa:bb
# Sprache der Anzeige (de oder en, wie die Webkonsole), Standard de
FAI_DISCOVERY_LANGUAGE=en
```

Danach `install.sh` erneut ausführen (oder `deploy-splash.sh` einzeln: `./deploy-splash.sh`). Es
verteilt beziehungsweise entfernt, je nach Einstellung:

- `splash/` im Config-Space (`fai-splash`, `icon.png`, `allow-macs`, `lang`),
- einen mit `# BEGIN fai-splash` und `# END fai-splash` markierten Block in `hooks/subroutines`, der den
  Dienst in `task_setup` startet.

Ohne `FAI_DISCOVERY_SPLASH_ENABLED=true` werden beide wieder entfernt. `allow-macs` und `lang` sind per
`.git/info/exclude` lokal, damit die Einstellungen eines Servers nicht über das Config-Space-Git auf
andere Server wandern. Ohne `allow-macs` bleibt der Splash aus.

Die Discovery-Meldungen kommen aus `hooks/discovery` (Hilfsfunktion `splash()` und fünf Aufrufe mit `-m NAME`, in
`01-discovery-client/fai-config/hooks/discovery` enthalten). Ohne `fai-splash` passiert dort nichts.

Die Änderungen werden Client-seitig sofort wirksam: Der Config-Space wird beim Boot per NFS gelesen,
ein NFSROOT-Neubau ist nicht nötig.

## Test (Entwicklung)

Vorschau eines Zustands als PNG, ohne Framebuffer, mit einer beliebigen PSF-Schrift:

```bash
FAI_SPLASH_FONT=lat0-16.psf.gz ./fai-splash preview out.png --state install --size 1920x1080 --lang en
# Zustände: boot, wait, install, done, error; Sprache: de, en
```

Die Tests (Übersetzungen vollständig, Platzhalter in beiden Sprachen gleich, Sprachwahl, Schrift-Tabelle):

```bash
python3 -m pytest 09-install-splash/test_fai_splash.py
```

## Lehren aus dem Test am T490 (nicht offensichtlich, bitte beachten)

Alles hier hat sich erst an echter Hardware gezeigt, in der VM (`bochs`) tritt nichts davon auf:

1. **Der Grafiktreiber wechselt nach dem Start.** Beim Boot nutzt der Kernel `efifb`; `udev` lädt den
   Treiber (z. B. `i915`) erst in `task_setup` (`udevadm trigger`) nach, also nach dem Start des Dienstes.
   Der neue Framebuffer liegt woanders im Speicher. Der Dienst vergleicht daher bei jedem Durchlauf
   Name, Größe und Stride aus `/sys/class/graphics/fb0/` und baut bei Änderung alles neu auf.
2. **Panning.** `fbcon` scrollt per Panning, der sichtbare Ausschnitt beginnt dann nicht bei Zeile 0 und
   man sieht nur einen Teil des Bildes. Der Dienst setzt den Versatz mit `FBIOPAN_DISPLAY` auf 0.
3. **Schreiben per `write()`, nicht per `mmap`.** Über `mmap` geschriebene Bilddaten erscheinen bei
   `i915` nicht zuverlässig auf dem Display (Bild bleibt statisch). `write()` auf `/dev/fb0` markiert die
   Zeilen als geändert, danach löst ein `FBIOPAN_DISPLAY` einen Flip aus.
4. **`VT_PROCESS` statt `VT_AUTO`.** Der Kernel verbietet das Umschalten der virtuellen Terminals, wenn die
   aktive Konsole im Grafikmodus und im Modus `VT_AUTO` ist (`set_console` in `vt_ioctl.c`), und lehnt dann
   auch ein erneutes `VT_ACTIVATE` auf dasselbe Terminal ab. Der Dienst nutzt `VT_PROCESS` mit
   `SIGUSR1`/`SIGUSR2` und quittiert die Umschaltanfragen.

## Freigabeliste und Diagnose

- **`splash/allow-macs`:** Erzeugt `deploy-splash.sh` aus site.conf. Der Dienst startet nur auf Clients,
  deren MAC (eine beliebige NIC) in der Datei steht, die Zeile `all` schaltet ihn für alle ein, ohne die
  Datei bleibt er aus. Kommentare mit `#`. So lässt sich der Splash auf einem Produktivserver erst nur für
  ein Gerät testen.
- **Abschalten pro Boot:** `nosplash` auf der Kernel-Kommandozeile.
- **Diagnose:** Der Dienst schreibt `/tmp/fai/splash.log` auf dem Client (wird von `task_savelog` nicht auf
  den Server kopiert). Mit `splashdebug` auf der Kernel-Kommandozeile schickt er seinen Zustand
  zusätzlich als `SPLASH ...`-Zeilen an den FAI-Monitor, sie erscheinen in `/var/log/fai/fai-monitor.log`
  des Servers (Herzschlag alle 15 s, Framebuffer, Fehler). So lässt sich ein Client debuggen, ohne dass man
  sich anmelden kann.

## Grenzen

- Die Anzeige beginnt erst, wenn FAI im NFSROOT startet. Kernel- und initrd-Phase (einige
  Sekunden) bleiben Text auf schwarz. Plymouth in der initrd wäre dafür nötig und ist bewusst
  nicht Teil des Prototyps.
- Nur Framebuffer mit 32 Bit. Auf Systemen ohne `/dev/fb0` (z. B. `nomodeset` ohne EFI-Framebuffer)
  bleibt es bei der Textkonsole.
- Die Texte nutzen eine 8x16-PSF-Konsolenschrift, vergrößert um einen ganzzahligen Faktor. Welcher Buchstabe welches
  Zeichen ist, steht in der Unicode-Tabelle der Schrift (ohne Tabelle gilt die Latin-9-Reihenfolge). Umlaute gehen,
  Zeichen außerhalb der Schrift (z. B. „…“) nicht. Weitere Sprachen brauchen daher eine passende Schrift im NFSROOT.
- Hinweis zu den Texten: Neue Sprachen kommen als dritter Schlüssel in `TEXT`/`TASKS` und in `LANGUAGES` dazu.
- Task-Gewichte für den Balken (`TASKS` in `fai-splash`) sind Schätzwerte, `instsoft` zählt am
  meisten.
