# Installation: FAI-Configspace-Integration

Löst während der echten Installation den in der Webkonsole vergebenen
Hostnamen auf und setzt ihn — sowohl im laufenden Zielsystem als auch
über FAIs `additional.var`-Mechanismus für nachfolgende
Klassen-Skripte.

## Voraussetzungen

- Funktionierender FAI-Configspace unter `/srv/fai/config`
- Webkonsole (`02-webconsole/`) bereits installiert und erreichbar

## Installation

1. `03-fai-configspace/fai-config/class/02-set-hostname.sh` nach
   `/srv/fai/config/class/02-set-hostname.sh` kopieren.
2. Den Platzhalter `__FAI_DISCOVERY_INTERNAL_URL__` ersetzen (dieselbe
   URL wie beim Discovery-Client-Hook, siehe
   [`installation-discovery-client.md`](installation-discovery-client.md)):

   ```bash
   sed -i "s|__FAI_DISCOVERY_INTERNAL_URL__|http://faiserver:8080|" \
       /srv/fai/config/class/02-set-hostname.sh
   ```

3. Ausführbar machen: `chmod 755 /srv/fai/config/class/02-set-hostname.sh`
4. Der Dateiname `02-*` ist bewusst gewählt: FAI führt Klassen-Skripte in
   alphabetischer Reihenfolge aus, dieses Skript muss früh laufen, bevor
   Skripte, die bereits einen gesetzten Hostnamen erwarten.
5. Falls `/srv/fai/config` ein Git-Checkout ist: committen und pushen.

## Funktionsweise

Das Skript ermittelt die eigene MAC-Adresse (`ip route` + `/sys/class/net`),
fragt `GET <API_URL>/device/<mac>` ab und liest daraus den vom Admin
vergebenen Hostnamen. Der Wert wird serverseitig bereits gegen ein
striktes Zeichenset validiert; das Skript validiert zusätzlich lokal
(Defense in Depth — der Wert wird später als root gesourced, ein nicht
validierter Wert wäre eine Command-Injection-Lücke). Bei gültigem
Hostnamen:

- `hostname "$hostname"` — setzt den Kernel-UTS-Namespace direkt (wichtig,
  da FAIs NFSROOT den DHCP-gelieferten Hostnamen bereits in der
  Initramfs-Phase setzt, lange bevor dieses Skript läuft)
- `echo "HOSTNAME=$hostname" >> "$LOGDIR/additional.var"` — FAIs
  dokumentierter Mechanismus, damit der Wert auch in späteren,
  eigenständigen `fai-class`-Kindprozessen ankommt
