# Installation: Web console

The web console is the heart of fai-discovery: a Flask app running as
a systemd service on the FAI server, managing waiting devices,
approvals and admin accounts.

## Requirements

- Python 3 with Flask (`pip install flask` or a distribution package)
- Example Debian:
```bash
  apt-get install python3-flask
```
- `sudo`, `fai-chboot` (part of `fai-server`)
- Root access for the setup
- Optional, only for the live installation progress page
  (`/admin/progress`): `fai-monitor` running as a systemd service, see
  step 9 below

## Installation

### 1. Create the system user

```bash
useradd --system --create-home --shell /usr/sbin/nologin faidiscovery
```

### 2. Deploy the code

Copy `02-webconsole/api/` (Python code, templates, `static/`)
somewhere, e.g. `/opt/fai-discovery/02-webconsole/api/` — the exact
path is up to you, but it must match `WorkingDirectory` in the systemd
unit (step 4).

### 3. `fai-chboot` wrapper and sudoers rule

The web console process runs unprivileged as `faidiscovery` and still
needs to call `fai-chboot` (requires root) through a narrow,
validating wrapper:

```bash
install -o root -g root -m 755 02-webconsole/bin/fai-discovery-chboot /usr/local/bin/fai-discovery-chboot
visudo -cf 02-webconsole/etc/sudoers.d/fai-discovery   # check syntax first
install -o root -g root -m 0440 02-webconsole/etc/sudoers.d/fai-discovery /etc/sudoers.d/fai-discovery
```

### 4. systemd unit

```bash
install -o root -g root -m 644 02-webconsole/api/fai-discovery-webconsole.service /etc/systemd/system/
```

If the code doesn't live under `/opt/fai-discovery-repo/02-webconsole/api`,
adjust `WorkingDirectory=` in the copied unit file.

### 5. `site.conf`

```bash
mkdir -p /etc/fai-discovery
```

Create `/etc/fai-discovery/site.conf` (read via systemd
`EnvironmentFile=` at start — `systemctl restart fai-discovery-webconsole`
is required after every change):

```
FAI_DISCOVERY_PROFILE_FILE=/srv/fai/config/class/example.profile
FAI_DISCOVERY_INTERNAL_URL=http://faiserver:8080
FAI_DISCOVERY_NFS_ROOT=nfs://faiserver/srv/fai/config
```

| Variable | Required | Meaning |
|---|---|---|
| `FAI_DISCOVERY_PROFILE_FILE` | yes | Path to the FAI profile file whose entries are offered in the approval form |
| `FAI_DISCOVERY_INTERNAL_URL` | yes | URL of the web console as reachable from the **target machine** during installation |
| `FAI_DISCOVERY_NFS_ROOT` | yes | NFS root server passed to `fai-chboot -u`. **"localhost" is almost always wrong** — the target machine, not the FAI server, resolves this address. Without a value set, every approval fails. |
| `FAI_DISCOVERY_TYPE_PREFIXES` | no | Comma-separated `code:label` pairs for type-prefix suggestions, e.g. `NB:Notebook,DT:Desktop,SRV:Server` |
| `FAI_DISCOVERY_LOCATION_PREFIXES` | no | Same as above, for location prefixes |
| `FAI_DISCOVERY_DISK_CONFIG_DIR` | no | Directory with `disk_config` files for automatic UEFI detection. Without a value set, the FAI default path is used. |
| `FAI_DISCOVERY_MENU_ENABLED` | no | `true` enables the PXE boot menu for unknown machines (see [section 10](#10-pxe-boot-menu-for-unknown-machines-optional)). Unset or any other value: off. |
| `FAI_DISCOVERY_MENU_TIMEOUT` | no | Seconds the menu waits before booting from the local disk (1–300, default 10) |
| `FAI_DISCOVERY_LANGUAGE` | no | UI language for navigation, forms, error messages and the help page: `de` or `en`. Missing or any other value falls back to `de` (the original default) — safe to leave unset on existing installations. |

### 6. Admin account

Admin accounts live in `/etc/fai-discovery/admins.json`
(`{"username": "werkzeug-password-hash"}`, HTTP Basic Auth). A working
demo example is provided at
`02-webconsole/etc/fai-discovery/admins.json.example`:

```bash
cp 02-webconsole/etc/fai-discovery/admins.json.example /etc/fai-discovery/admins.json
chown root:faidiscovery /etc/fai-discovery/admins.json
chmod 640 /etc/fai-discovery/admins.json
```

**⚠️ Security note:** this demo example contains the working login
`admin` / `admin` so the web console is reachable right after copying
it. **The password must be changed immediately afterwards** — otherwise
anyone who can reach port 8080 can log in with it.

Create your own admin, or change the password:

```bash
python3 -c "from werkzeug.security import generate_password_hash; print(generate_password_hash(input('Password: ')))"
```

Put the resulting hash into `/etc/fai-discovery/admins.json` under the
desired username (keep the JSON valid — no trailing comma after the
last entry). Changes take effect immediately, no restart needed —
`admins.json` is re-read on every request.

### 7. Firewall + start

```bash
ufw allow 8080/tcp   # or the equivalent for your own firewall
systemctl daemon-reload
systemctl enable --now fai-discovery-webconsole
```

### 8. Verification

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080/status/aa:bb:cc:dd:ee:ff   # expected: 200
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080/admin/                       # expected: 401 (auth required)
```

Then open `http://<faiserver>:8080/admin/` in a browser and log in
with the admin account.

### 9. Live installation progress (optional)

The `/admin/progress` page shows real-time FAI task status for every
running installation — essentially the original `fai-monitor-gui`
built into the web console. It reads from `fai-monitor`'s log file,
so `fai-monitor` needs to run continuously as a daemon, not just for
the duration of a single install.

`fai-monitor` itself is part of `fai-server`/`fai-client`; it doesn't
ship a systemd unit, so create one. Its `-d` (daemonize) flag needs
`Proc::Daemon`, packaged separately on Debian:

```bash
apt-get install libproc-daemon-perl
```

`/etc/systemd/system/fai-monitor.service`:

```ini
[Unit]
Description=FAI monitor daemon
After=network.target

[Service]
Type=forking
ExecStart=/usr/sbin/fai-monitor -d -l /var/log/fai/fai-monitor.log
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable --now fai-monitor.service
ss -tlnp | grep 4711   # fai-monitor listens on TCP 4711 by default
```

Without this service, `/admin/progress` simply stays empty — it does
not error out, since it degrades to showing no running installations.

### 10. PXE boot menu for unknown machines (optional)

Without the menu, a machine only reaches discovery mode if someone puts it
there by hand (Discovery page or `fai-chboot`). With the menu enabled, every
machine that has no PXE config of its own sees a Syslinux menu on network
boot: **"Boot from local disk"** (chosen automatically when the countdown
ends, default 10 seconds) or **"Discover this device (register for network
install)"**.

**Machines that are already known skip the menu.** Every machine in the
history (status `reboot` or `reinstalling`) gets its own
`pxelinux.cfg/01-<mac>` with `localboot -1` from `fai-discovery-known`, so it
boots from disk without waiting. Deleting its history entry makes it unknown
again — it sees the menu on the next network boot (within about a minute).
"Reinstall" in the history puts a machine back into discovery mode as usual.

Requirements: the `syslinux-common` package (provides
`/usr/lib/syslinux/modules/`), `/srv/tftp/fai/syslinux.efi` and `ldlinux.c32`
(as for normal PXE operation), and a TFTP server that follows relative
symlinks inside the TFTP root (the default of `tftpd-hpa`).

**Rollout order (mandatory).** The BIOS and UEFI menu modules have the same
file names but are not interchangeable. A UEFI client that loads
`fai/syslinux.efi` and meets the menu hangs in an endless loop
(`Failed to load COM32 file menu.c32`). So:

1. On **every** FAI server that serves the clients, deploy the script and
   create the assets **without** enabling the menu:
   ```bash
   sudo install -o root -g root -m 755 /opt/fai-discovery-repo/02-webconsole/bin/fai-discovery-menu /usr/local/bin/
   sudo /usr/local/bin/fai-discovery-menu --assets-only
   ```
2. In your DHCP server, hand UEFI clients `fai/efi64/syslinux.efi` as the boot
   file (instead of `fai/syslinux.efi`). BIOS clients keep `fai/pxelinux.0`.
3. Only then set `FAI_DISCOVERY_MENU_ENABLED=true` in
   `/etc/fai-discovery/site.conf` (optionally `FAI_DISCOVERY_MENU_TIMEOUT`)
   and run `install.sh` again. It deploys `fai-discovery-menu`,
   `fai-discovery-known` and their systemd units (a path unit that rebuilds
   the menu after kernel changes, plus a path unit and a one-minute timer for
   the known machines), builds the menu and starts the units.

A hand-made `pxelinux.cfg/default` is saved once as
`default.pre-fai-discovery-menu`.

**Disabling:** remove the variable (or set anything but `true`) and run
`install.sh` again. It stops the units, restores the plain `localboot -1`
default and removes the files written by `fai-discovery-known`. A previously
hand-made `default` does not come back automatically — copy it back from
`default.pre-fai-discovery-menu` if needed.

**Verification:**
```bash
systemctl status fai-discovery-known.path fai-discovery-known.timer
sudo /usr/local/bin/fai-discovery-known     # must finish without errors
ls -l /srv/tftp/fai/pxelinux.cfg/           # one 01-<mac> per known machine
head -1 /srv/tftp/fai/pxelinux.cfg/01-*     # "# fai-discovery-known: managed file, ..."
```
