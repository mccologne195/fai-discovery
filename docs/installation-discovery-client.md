# Installation: Discovery client (PXE boot hook)

Reports a booting machine to the web console and waits for approval.
Does **not** run as its own daemon — it's a single Bash script that
FAI executes inside the NFSROOT during the discovery boot.

## Requirements

- A working FAI configspace under `/srv/fai/config` (default path, see
  the `fai-server` documentation)
- The web console (`02-webconsole/`) already installed and reachable

## Installation

1. Copy `01-discovery-client/fai-config/hooks/discovery` to
   `/srv/fai/config/hooks/discovery`.
2. Replace the placeholder `__FAI_DISCOVERY_INTERNAL_URL__` in the
   copied file with the actual URL of the web console, e.g.:

   ```bash
   sed -i "s|__FAI_DISCOVERY_INTERNAL_URL__|http://faiserver:8080|" \
       /srv/fai/config/hooks/discovery
   ```

   This URL must be reachable from the **target machine** (not just
   from the FAI server itself) — usually the hostname or IP of the FAI
   server, since the web console runs there too.
3. Make it executable: `chmod 755 /srv/fai/config/hooks/discovery`
4. If `/srv/fai/config` is a Git checkout (FAI convention):
   `git -C /srv/fai/config add hooks/discovery && git -C /srv/fai/config commit`

## Activation

The `discovery` action is not triggered automatically — it must be set
explicitly on the kernel command line when a new, unknown machine is
supposed to be discovered:

```bash
fai-chboot -Fv -u nfs://faiserver/srv/fai/config -a discovery <MAC>
```

The web console does this automatically itself when it detects a
still-unknown machine — see
[`installation-webconsole.md`](installation-webconsole.md).

## How it works

When run, the hook collects:

- The MAC address and IP of the default route
- CPU model, disk size (`dmidecode`/`lsblk`), RAM size (may read 0GB
  on VMs)
- Firmware type (UEFI if `/sys/firmware/efi` exists, otherwise BIOS)
- Serial number and hardware UUID (`dmidecode`, if available)

and sends this as JSON to `POST <API_URL>/register`. It then polls
`GET <API_URL>/status/<mac>` in a loop until the status changes to
`reboot` (approval granted), then reboots.
