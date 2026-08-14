# Installation: Portables Setup-Skript (`install.sh`)

`install.sh` automatisiert die komplette Einrichtung aus
[`installation-discovery-client.md`](installation-discovery-client.md),
[`installation-webconsole.md`](installation-webconsole.md) und
[`installation-fai-configspace.md`](installation-fai-configspace.md) in
einem Durchlauf, auf einem neuen FAI-Server.

Wer aus Sicherheitsgründen keine fremden Skripte per `curl | bash`
ausführen möchte: [`installation-manual.md`](installation-manual.md)
beschreibt dieselben Schritte manuell.

## Voraussetzungen

- Debian/Ubuntu mit funktionierendem `fai-server`-Grundsetup
  (`/srv/fai/config` existiert und ist ein Git-Checkout)
- Root-Zugriff
- Interaktives Terminal (das Skript fragt Admin-Zugangsdaten und
  Konfigurationswerte ab — funktioniert nicht in einer reinen
  `curl | bash`-Pipe ohne `/dev/tty`; erst herunterladen, dann ausführen)

## Ausführung

```bash
curl -fsSL https://raw.githubusercontent.com/<dein-github-user>/fai-discovery/main/install.sh -o install.sh
less install.sh   # Inhalt vor dem Ausführen prüfen
sudo bash install.sh
```

## Was das Skript macht

1. Prüft, dass es als root läuft.
2. Legt den System-User `faidiscovery` an (überspringt, falls vorhanden).
3. Klont dieses Repository als Sparse-Checkout nach
   `/opt/fai-discovery-repo` (nur die tatsächlich gebrauchten
   Unterverzeichnisse, nicht das komplette Repo).
4. Fragt interaktiv: Pfad zur FAI-Profil-Datei, interne URL der
   Webkonsole. Legt bei Bedarf einen ersten Admin-Account an
   (Benutzername + Passwort abgefragt, Hash erzeugt).
5. Verteilt `fai-discovery-chboot`, die sudoers-Regel, die
   systemd-Unit sowie `hooks/discovery` und `02-set-hostname.sh`
   (Platzhalter automatisch aufgelöst) nach `/srv/fai/config`.
6. Öffnet Port 8080 in der Firewall (`ufw`).
7. Startet den `fai-discovery-webconsole`-Dienst (bzw. neu, falls
   bereits aktiv — für Updates erneut ausführbar).
8. Verifiziert mit zwei `curl`-Checks, dass die Webkonsole antwortet.

Das Skript ist **idempotent** — mehrfaches Ausführen aktualisiert nur den
Code und startet den Dienst neu, bereits vorhandene Konfiguration
(`site.conf`, `admins.json`) bleibt unangetastet.

## `REPO_URL` anpassen

Die Variable `REPO_URL` am Anfang des Skripts zeigt standardmäßig auf
einen Platzhalter. Wer dieses Repository forkt oder spiegelt, muss sie
auf die eigene Fork-/Mirror-URL anpassen, bevor `install.sh` an andere
weitergegeben wird.
