# Installation: FAI configspace integration

During the actual installation, resolves the hostname assigned in the
web console and sets it — both in the running target system and via
FAI's `additional.var` mechanism for later class scripts.

## Requirements

- A working FAI configspace under `/srv/fai/config`
- The web console (`02-webconsole/`) already installed and reachable

## Installation

1. Copy `03-fai-configspace/fai-config/class/02-set-hostname.sh` to
   `/srv/fai/config/class/02-set-hostname.sh`.
2. Replace the placeholder `__FAI_DISCOVERY_INTERNAL_URL__` (same URL
   as for the discovery client hook, see
   [`installation-discovery-client.md`](installation-discovery-client.md)):

   ```bash
   sed -i "s|__FAI_DISCOVERY_INTERNAL_URL__|http://faiserver:8080|" \
       /srv/fai/config/class/02-set-hostname.sh
   ```

3. Make it executable: `chmod 755 /srv/fai/config/class/02-set-hostname.sh`
4. The `02-*` filename is chosen deliberately: FAI runs class scripts
   in alphabetical order, and this script must run early, before
   scripts that expect a hostname to already be set.
5. If `/srv/fai/config` is a Git checkout: commit and push.

## How it works

The script determines its own MAC address (`ip route` +
`/sys/class/net`), queries `GET <API_URL>/device/<mac>` and reads the
hostname assigned by the admin from the response. The value is already
validated server-side against a strict character set; the script
additionally validates it locally (defense in depth — the value is
later sourced as root, so an unvalidated value would be a command
injection hole). On a valid hostname:

- `hostname "$hostname"` — sets the kernel UTS namespace directly
  (important, since FAI's NFSROOT already sets the DHCP-provided
  hostname during the initramfs phase, long before this script runs)
- `echo "HOSTNAME=$hostname" >> "$LOGDIR/additional.var"` — FAI's
  documented mechanism so the value also reaches later, independent
  `fai-class` child processes
