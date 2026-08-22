# Design: Live-Installationsfortschritt in der Webkonsole

**Stand:** 2026-08-22. Ergebnis eines Brainstormings, ausgelöst durch die
Frage, ob sich das, was `fai-monitor-gui` (X11-Tool, manuell per
`ssh -X ... | fai-monitor-gui -` gestartet) anzeigt, auch in
`fai-discovery` selbst einbauen lässt.

## Problem

Während eine Installation läuft, zeigt die Webkonsole nichts an. Ein
freigegebenes Gerät steht in der Historie mit Status `reboot` bzw.
`reinstalling`, aber ob die Installation gerade bei `partition` oder
`configure` steht, sieht man nicht. Aktuell sind zwei getrennte
Werkzeuge nötig:

1. `fai-monitor-gui` per SSH-X11-Forwarding auf `faiserver2` — zeigt
   Task-für-Task-Fortschritt live, aber erfordert eine grafische
   SSH-Session und ist an keiner Stelle in der Webkonsole sichtbar.
2. Der bestehende Log-Viewer (`logs.py`/`logs.html`, Route
   `/admin/history/<mac>/logs`) — zeigt `task_error`/`status.log`/
   `error.log` aus `/var/log/fai/remote-logs/<hostname>/install-<ts>/`,
   aber erst **nachdem** die Installation fertig ist (oder abgebrochen
   wurde), als reines Ok/Fehler-Ergebnis ohne Task-Verlauf.

## Ziel

Eine neue Seite in der Webkonsole zeigt alle **gerade laufenden**
Installationen sowie die letzten **5** abgeschlossenen als Grid mit
Task-Fortschritt pro Host — ersetzt die manuelle
`fai-monitor-gui`-Session vollständig, ohne X11/SSH nötig zu haben.

## Datenquelle

FAI schreibt bei jeder Installation pro Host eine eigene Kopie von
`fai-monitor.log` nach
`/var/log/fai/remote-logs/<hostname>/install-<timestamp>/fai-monitor.log`
(bestätigt anhand eines echten Laufs für `vmrepro`):

```
vmrepro TASKBEGIN setup
vmrepro TASKEND setup 0
vmrepro HOOK updatebase.DEBIAN
vmrepro TASKBEGIN updatebase
vmrepro TASKEND updatebase 0
...
vmrepro TASKEND reboot 0
```

Format: `<hostname> TASKBEGIN <task>`, `<hostname> TASKEND <task>
<exitcode>`, `<hostname> HOOK <name>`. `HOOK`-Zeilen werden beim Parsen
ignoriert (kein eigener Spalten-Eintrag).

Dasselbe Verzeichnis enthält bereits `task_error` (Datei mit dem
Exit-Code des letzten Tasks, fehlt solange die Installation läuft) —
genau der Mechanismus, den `logs.py:read_install_log()` heute schon für
den nachträglichen Ok/Fehler-Status nutzt. Das neue Feature nutzt
denselben Mechanismus für den **Gesamtstatus** (laufend/ok/failed),
nicht für den Task-Verlauf selbst.

## Architektur

Kein neuer Hintergrund-Dienst, kein persistenter State, keine neue
JSON-API. Die Seite arbeitet zustandslos: bei jedem Request werden die
relevanten (kleinen) Log-Dateien frisch von der Platte gelesen und
geparst — bei der Größenordnung des HomeLab (Dutzende Hosts, wenige
Installationen gleichzeitig) vernachlässigbare Kosten, aber deutlich
weniger Komplexität als ein Tail-Thread mit eigenem Lifecycle (Neustart
der Webconsole mitten in einer Installation würde sonst State
verlieren müssen).

### Neues Modul `02-webconsole/api/progress.py`

Analog zu `logs.py`, das bereits `find_latest_install_dir()`
bereitstellt und hier wiederverwendet wird:

- `list_active_installs()` — nimmt `storage.list_history()` (Status
  `reboot`/`reinstalling`), ermittelt pro Host per
  `logs.find_latest_install_dir()` das aktuelle
  `install-<timestamp>/`-Verzeichnis. Teilt auf in:
  - **laufend** (`task_error`-Datei fehlt noch) → immer enthalten,
    unabhängig von der Anzahl
  - **abgeschlossen** (`task_error` vorhanden) → nach Zeitstempel im
    Verzeichnisnamen absteigend sortiert, nur die letzten `N`
    (Default `5`, überschreibbar per Env-Var
    `FAI_DISCOVERY_PROGRESS_HISTORY_LIMIT`, analog zum bestehenden
    `FAI_DISCOVERY_LOG_DIR`-Pattern in `logs.py`)

  Rückgabe-Reihenfolge: laufende zuerst, danach abgeschlossene nach
  Aktualität.

- `read_task_progress(install_dir)` — parst die `fai-monitor.log` in
  diesem Verzeichnis zeilenweise, baut eine **geordnete** Liste
  `[{task, status}]` in Auftrittsreihenfolge. `status` ist
  `"running"`, solange nur `TASKBEGIN` gesehen wurde, sonst `"ok"`
  (Exitcode `0`) oder `"failed"` (Exitcode ≠ `0`). Spalten ergeben sich
  dynamisch aus den beobachteten `TASKBEGIN`-Ereignissen — kein
  hartcodierter Task-Katalog, passt sich automatisch an, falls sich
  die FAI-Config ändert.

  Der **Gesamtstatus** eines Hosts kommt nicht aus den Task-Namen
  (z. B. "letzter Task heißt `reboot`"), sondern direkt aus der
  `task_error`-Datei — robust gegenüber künftigen Änderungen an der
  FAI-Task-Reihenfolge.

### Neue Route in `admin.py`

`GET /admin/progress`, gleicher `@require_auth`-Blueprint wie alle
anderen `/admin/*`-Routen. Rendert die komplette Seite serverseitig bei
jedem Aufruf — keine separate JSON-API nötig.

### Frontend: bestehendes Live-Refresh-Muster wiederverwenden

`templates/dashboard.html` pollt bereits alle 12s dieselbe URL per
`fetch(window.location.href)`, parst die Antwort per `DOMParser` und
ersetzt nur das `innerHTML` eines Container-Elements
(`#device-cards`). `templates/progress.html` übernimmt exakt dasselbe
Muster (Intervall hier 3s, da Installationsfortschritt sich schneller
ändert als wartende Geräte), Container `#progress-grid`. Kein neuer
Websocket-/SSE-Code, keine Client-seitige Template-Logik.

### Template `templates/progress.html`

Erweitert `base.html`, ein Grid: eine Zeile pro Host, eine Spalte pro
dynamisch beobachtetem Task, Zellen mit Status (laufend/ok/failed).
Wiederverwendung bestehender CSS-Klassen/Variablen aus `static/style.css`
(`--accent`/`--danger`, Muster von `.log-status-ok`/`.log-status-failed`)
statt neuer hartcodierter Farben — funktioniert damit automatisch in
Light/Dark/System-Theme. Leerer Zustand ("keine laufende oder kürzlich
abgeschlossene Installation") analog zu `dashboard.empty`.

### i18n

Neue Keys im `TRANSLATIONS`-Dict in `i18n.py` (`progress.*`), jeweils
`de` und `en`, exakt nach vorhandenem Muster (siehe `history.*`,
`logs.*`). Neuer Nav-Link (`nav.progress`) in `base.html` neben den
vier bestehenden Einträgen.

## Fehlerbehandlung

- Log-Datei fehlt oder ist mitten im Poll unlesbar (z. B. Race mit
  laufendem Schreibvorgang) → dieser Host wird für diesen Poll-Zyklus
  übersprungen, keine Exception für die restliche Seite.
- Unerwartete/kaputte Log-Zeilen (Format weicht ab) → Zeile wird beim
  Parsen ignoriert statt einen Fehler zu werfen.
- Kein aktiver/kürzlich abgeschlossener Host → Leerzustand-Meldung.

## Out of Scope

- `fai-config.git`, Configspace-Dateien (`hooks/discovery`,
  `class/02-set-hostname.sh`, `scripts/LAST/50-salt-bootstrap`),
  `install.sh` — dieses Feature ist rein `02-webconsole`-seitig, keine
  Änderungen an diesen Komponenten nötig.
- Kein Ersatz für den bestehenden Log-Viewer (`logs.html`) — der bleibt
  für die vollständige Post-Mortem-Ansicht (inkl. `error.log`,
  vollständiges `fai.log`) bestehen. Die neue Seite ist nur für die
  Live-Übersicht.
- Keine Benachrichtigungen (E-Mail/Chat) bei Fertigstellung — reine
  Anzeige.

## Tests

Neue `test_progress.py`, gespiegelt an bestehenden Konventionen
(`test_storage.py`, `test_logs.py` — `monkeypatch` auf
`FAI_DISCOVERY_LOG_DIR`, `tmp_path`-Fixtures):

- Parser-Test mit echtem Log-Auszug (inkl. `HOOK`-Zeilen, die ignoriert
  werden müssen)
- `list_active_installs()`: Limit-Logik (mehr als `N` abgeschlossene →
  nur die letzten `N`), laufende immer enthalten unabhängig vom Limit
- Route-Test in `test_admin.py` (Auth erforderlich, Leerzustand,
  gerenderter Inhalt)
