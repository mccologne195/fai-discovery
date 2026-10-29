# HOWTO: Set up fai-discovery on a new FAI server

This guide covers what has to be in place **before** you run `install.sh`, how to run it, and the
problems that people hit on a freshly installed FAI server. It does **not** cover the installation of
FAI itself (NFS export, TFTP, DHCP); see the [FAI Guide](https://fai-project.org/fai-guide/) for that.

The detailed per-component descriptions are in [`docs/`](docs/):
[web console](docs/installation-webconsole.md), [discovery client](docs/installation-discovery-client.md),
[config space](docs/installation-fai-configspace.md), [all steps by hand](docs/installation-manual.md),
[`install.sh` in detail](docs/installation-portable-setup.md).

Contents: [1. Prerequisites](#1-prerequisites) ·
[2. Run install.sh](#2-run-installsh) · [3. Verify](#3-verify) · [4. Optional features](#4-optional-features) ·
[5. Firewall](#5-firewall) · [6. Updating](#6-updating) · [7. Troubleshooting](#7-troubleshooting)

> This guide was derived from running test servers. A complete walk-through on a freshly installed
> minimal system has not been done for every step. If a step does not work as written, please open an issue.

## 1. Prerequisites

### 1.1 A working base FAI server

You need a FAI server that can already do a plain PXE installation: DHCP hands out `next-server` and a
boot file name, TFTP serves `/srv/tftp/fai`, `/srv/fai/nfsroot` and `/srv/fai/config` are exported via NFS,
and `fai-chboot` works.

Two things are easy to miss if the server was not set up by the complete `fai-setup(8)` run
(for example when the pieces were created by hand):

- **SSH access for the log user.** After every installation the client uses `task_chboot` and
  `task_savelog` to talk back to the server over SSH, as the `LOGUSER` from `/etc/fai/fai.conf`
  (user `fai`, home `/var/log/fai/remote-logs` by default). If the `.ssh` directory in that home is owned
  by `root`, both tasks fail with `Permission denied` although the key is correct. This only shows up as a
  `WARNING` near the end of `fai.log`; the installation itself still succeeds.
  Fix: `sudo chown -R fai:nogroup /var/log/fai/remote-logs/.ssh` (use the user and group of your `fai`
  account: `getent passwd fai`).
- **Ownership of the PXE config directory.** `/srv/tftp/fai/pxelinux.cfg` (the directory itself) must be
  writable by that user. Otherwise `task_chboot` ends with `Rename for <MAC> failed. Permission denied`
  and the client boots into the installer again instead of from its disk.
  Fix: `sudo chown fai:nogroup /srv/tftp/fai/pxelinux.cfg`.

Other settings that go wrong silently on a new server:

- **`APTPROXY` in `class/DEBIAN.var`** must point to **this** server (where `apt-cacher-ng` runs), not to
  an address copied from another setup. A wrong value makes `apt` fail inside the target system, which
  then looks like a GRUB or UEFI package problem although almost no package was installed.
- **Root password in the NFSROOT.** If `FAI_ROOTPW` in `/etc/fai/nfsroot.conf` was set or changed after the
  NFSROOT was built, root has `*` in `/etc/shadow` there and you cannot log in to the install environment.
  Fix: `sudo fai-make-nfsroot -f` and check `grep '^root:' /srv/fai/nfsroot/etc/shadow`.

### 1.2 Config space is not a Git repository

`install.sh` copies a few files into the config space (`/srv/fai/config`) and **commits** them there, so
your changes stay traceable. It therefore expects `/srv/fai/config` to be a Git repository. A server that
was installed from the FAI DVD or set up with `fai-setup` has the example config space in
`/srv/fai/config`, but as a plain directory without a `.git`.

**Symptom** (`install.sh` stops in step 5):

```
FEHLER: /srv/fai/config ist kein Git-Repository. Lokal anlegen: git -C /srv/fai/config init -b main && ...
```

(`FEHLER` is German for "error": the messages of `install.sh` are in German. Older versions said
`/srv/fai/config ist kein Git-Checkout - Basis-FAI-Setup fehlt`, which means the same.)

**Fix:** turn the directory into a local Git repository. No remote server is needed.

```bash
# identity for the commits that install.sh makes as root
sudo git config --system user.name  "FAI Server"
sudo git config --system user.email "root@localhost"

# needed if the directory belongs to another user ("dubious ownership")
sudo git config --system --add safe.directory /srv/fai/config

cd /srv/fai/config
sudo git init -b main
sudo git add -A
sudo git commit -m "Base config space"
```

Then run `install.sh` again. It is safe to repeat.

Good to know:

- **No remote is required.** At the end `install.sh` runs `git push`. Without a remote, this prints
  `WARN: git push fehlgeschlagen ...` and continues; nothing is lost. Add a remote
  (`git -C /srv/fai/config remote add origin <url>`) if you want your config space backed up elsewhere.
- **Identity.** Without `user.name` and `user.email` for root, the commit made by `install.sh` fails with
  a message about the Git identity. The two `git config --system` lines above prevent that (they write `/etc/gitconfig`, so they apply no matter which home directory `sudo` uses).
- **Existing checkout.** If your config space already is a Git checkout of your own repository, nothing
  needs to be done. `install.sh` adds the `safe.directory` entry itself, but only *after* this check.
- **Your own files.** `git add -A` commits everything that is in the directory right now. Check
  `git status` first if you keep secrets or very large files there.

### 1.3 A profile file

The approval form of the web console offers entries from a **profile file**, configured as
`FAI_DISCOVERY_PROFILE_FILE` in `site.conf`. `install.sh` suggests `/srv/fai/config/class/example.profile`.
That file does not exist on a fresh server unless you create it. Look first for what you already have:

```bash
ls /srv/fai/config/class/*.profile
```

A profile file consists of blocks separated by blank lines. `Name:` and `Classes:` are required, `Short:`,
`Long:` and `Description:` are optional text. An optional `Default: <name>` block at the top selects the
entry that is preselected in the form.

```
Default: Debian 13 minimal

Name: Debian 13 minimal
Description: Base installation without extra services
Short: A Linux host, no X
Classes: INSTALL FAIBASE DEBIAN
```

Every class in `Classes:` must exist in your config space. The repository contains a larger example in
[`08-installationsraum/configspace-neutral/profile-neutral.example`](08-installationsraum/configspace-neutral/profile-neutral.example).

### 1.4 Packages (Debian 13)

This is enough for a FAI server plus fai-discovery, without `fai-quickstart` and without recommends:

```bash
sudo apt install --no-install-recommends \
  fai-server nfs-kernel-server tftpd-hpa openssh-server openssh-client \
  libproc-daemon-perl syslinux-common \
  python3-flask \
  sudo git curl ca-certificates ufw openssl
```

| Package | Used for |
|---|---|
| `fai-server` | `fai-chboot`, `fai-make-nfsroot`, `fai-monitor` |
| `nfs-kernel-server`, `tftpd-hpa` | NFS export and TFTP for the PXE boot |
| `openssh-server`, `openssh-client` | return channel for `task_chboot` and `task_savelog` |
| `libproc-daemon-perl` | `fai-monitor`, whose log feeds the progress display |
| `syslinux-common` | modules for the PXE boot menu (BIOS and UEFI) |
| `python3-flask` | the web console (needed even before it starts, to create the admin account) |
| `sudo` | the web console calls the wrapper `fai-discovery-chboot` through `sudo` |
| `git`, `curl`, `ca-certificates` | repository checkout, `install.sh`, HTTPS |
| `ufw` | `install.sh` stops without it and opens port 8080/tcp |
| `openssl` | random initial admin password in unattended mode |

Optional: `python3-prometheus-client` for the `/metrics` endpoint. Without it the web console starts
anyway and `/metrics` answers with 503.

### 1.5 Names and addresses

Two values in `site.conf` are baked into files that the **booting client** reads in a minimal environment,
where the DNS search domain is usually missing:

- `FAI_DISCOVERY_INTERNAL_URL`: use a fully qualified name or an IP address, for example
  `http://fai.example.com:8080`. A short name like `http://faiserver:8080` fails silently on the client.
- `FAI_DISCOVERY_NFS_ROOT`: `nfs://fai.example.com/srv/fai/config`. `localhost` is almost always wrong,
  because the client resolves the name, not the server. Without a value, every approval fails.

## 2. Run install.sh

Download, read and run it. It cannot be piped (`curl | bash`) because it asks questions on the terminal:

```bash
curl -fsSL https://raw.githubusercontent.com/mccologne195/fai-discovery/main/install.sh -o install.sh
less install.sh
sudo bash install.sh
```

On the first run it asks for an admin user name and password, the profile file and the internal URL.
Later runs skip everything that exists already, so you can repeat it after a failure or for updates.

For automatic setups there is `sudo bash install.sh --unattended`. It uses defaults derived from
`hostname -f` (so the host needs a fully qualified name), creates the account `admin` and writes the
generated password to `/root/fai-discovery-initial-admin-password.txt` (mode 600). Change that password
afterwards.

`install.sh` creates the user `faidiscovery`, checks out the repository to `/opt/fai-discovery-repo`
(sparse), installs the wrapper `/usr/local/bin/fai-discovery-chboot`, the `sudoers` rule and the systemd
unit, copies `hooks/discovery` and `class/02-set-hostname.sh` into the config space and commits them,
opens port 8080 and starts the service.

`site.conf` is read when the service starts. After **every** change to `/etc/fai-discovery/site.conf`:

```bash
sudo systemctl restart fai-discovery-webconsole
```

## 3. Verify

```bash
systemctl is-active fai-discovery-webconsole
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080/status/aa:bb:cc:dd:ee:ff   # expected: 200
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080/admin/                       # expected: 401
```

`install.sh` runs the same two checks at the end. Then open `http://<server>:8080/admin/` in a browser,
log in with the admin account, trigger a discovery for a test machine and boot it per PXE
(see [`docs/installation-webconsole.md`](docs/installation-webconsole.md), section 8).

## 4. Optional features

- **PXE boot menu for unknown machines** (`FAI_DISCOVERY_MENU_ENABLED=true`): see
  [`docs/installation-webconsole.md`](docs/installation-webconsole.md#10-pxe-boot-menu-for-unknown-machines-optional).
  Mind the rollout order: the menu modules for BIOS and UEFI have the same names but are **not**
  interchangeable. A UEFI client that is sent to a BIOS module loops forever with
  `Failed to load COM32 file menu.c32`. Create the assets for **both** firmware types first, point the
  DHCP boot file for UEFI clients to the `efi64` variant, and switch the menu on last.
  **A server installed from the FAI DVD** still hands out `fai/syslinux.efi` in `/etc/dhcp/dhcpd.conf`; without the
  change the menu never shows up on UEFI machines (PXE stops right after the download). For isc-dhcp-server, in the
  `PXEClient:Arch:00007` block: `filename "fai/efi64/syslinux.efi";`, then
  `sudo dhcpd -t -cf /etc/dhcp/dhcpd.conf && sudo systemctl restart isc-dhcp-server`. Kea and dnsmasq examples are in
  the same section of the web console documentation. Check first which DHCP server really serves the clients
  (`systemctl is-active isc-dhcp-server kea-dhcp4-server dnsmasq`); a `dhcpd.conf` on the FAI server may be unused.
- **Full-screen display on the client during discovery and installation** (`FAI_DISCOVERY_SPLASH_ENABLED=true`,
  German or English according to `FAI_DISCOVERY_LANGUAGE`): instead of white text on a black terminal, clients show the
  fai-discovery icon, the status ("Waiting for approval", "Step 11 of 17: Installing packages") and a progress bar;
  after the installation, Enter on the display reboots the machine if `reboot` is not in `FAI_FLAGS`. Alt+F1 still
  shows the FAI log. Requirements in the NFSROOT (nothing to install, just check): `python3`, a console font
  (`/usr/share/consolefonts/lat0-16.psf.gz`, package `kbd`) and a kernel with framebuffer support (Debian default);
  without a framebuffer the text console stays and the installation runs as usual. Switch it on in
  `/etc/fai-discovery/site.conf`, then run `install.sh` again (it calls `09-install-splash/deploy-splash.sh`):

  ```
  FAI_DISCOVERY_SPLASH_ENABLED=true
  # optional, to try it carefully: only for these clients (comma separated)
  #FAI_DISCOVERY_SPLASH_MACS=00:11:22:33:44:55
  ```

  It deploys `splash/` (`fai-splash`, `icon.png`, `allow-macs`, `lang`) into the config space and a block marked
  `# BEGIN fai-splash` / `# END fai-splash` into `hooks/subroutines`; `allow-macs` and `lang` stay out of the config-space
  Git through `.git/info/exclude`. On a production server, first enable it for a single machine with
  `FAI_DISCOVERY_SPLASH_MACS`, watch one discovery and one installation, then remove the variable and run
  `install.sh` again. If a client shows nothing, add `splashdebug` to its kernel command line and look for
  `SPLASH ...` lines with `sudo grep SPLASH /var/log/fai/fai-monitor.log`. To switch it off, remove the variable
  (or set anything but `true`) and run `install.sh` again; a single boot can skip it with `nosplash` on the kernel
  command line. Details, how it works and the lessons from real hardware: `09-install-splash/README.en.md`.
- **HTTPS for the admin pages** through Caddy: [`HOWTO-eng-https.md`](HOWTO-eng-https.md).
- **Secure wipe with ShredOS:** [`docs/fetch-shredos-kernel.md`](docs/fetch-shredos-kernel.md).
- **Language of the web console:** `FAI_DISCOVERY_LANGUAGE=en` (default is `de`).
- **Hostname helpers:** `FAI_DISCOVERY_TYPE_PREFIXES` and `FAI_DISCOVERY_LOCATION_PREFIXES`.
- **No 2-minute wait for laptops with WLAN:** `FAI_DISCOVERY_RD_NEEDNET=0`, see the notes in
  `02-webconsole/etc/fai-discovery/site.conf.example` and section 7.

## 5. Firewall

Port 8080/tcp must stay open for the networks your **installation clients** are in. The discovery client
and the installing machines talk to it without authentication and directly, not through a reverse proxy.
You can restrict it to your installation networks, but not to single source addresses, because clients get
their IP address from DHCP. This stays true when you put HTTPS (Caddy) in front of the admin pages.
Note that `install.sh` runs `ufw allow 8080/tcp` for everybody again on every run.

## 6. Updating

```bash
cd /opt/fai-discovery-repo && sudo git pull --ff-only
sudo systemctl restart fai-discovery-webconsole
```

**The wrapper is not updated by `git pull`.** `/usr/local/bin/fai-discovery-chboot` is deliberately a copy,
not a symlink: `sudoers` grants passwordless root rights to exactly this file, so it must not live in a
checkout that the web console process can write to. After a change to `02-webconsole/bin/fai-discovery-chboot`
run `install.sh` again or copy it by hand:

```bash
sudo install -o root -g root -m 755 /opt/fai-discovery-repo/02-webconsole/bin/fai-discovery-chboot \
  /usr/local/bin/fai-discovery-chboot
```

Do this **before** restarting the service if a new `site.conf` variable depends on a new wrapper
version.

## 7. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `install.sh`: `/srv/fai/config ist kein Git-Repository` (older: `kein Git-Checkout`) | the config space is a plain directory | [section 1.2](#12-config-space-is-not-a-git-repository) |
| `install.sh`: `Configspace-Commit fehlgeschlagen` | no Git identity for root | `sudo git config --system user.name` and `user.email` |
| `install.sh`: `dubious ownership` | the config space belongs to another user | `git config --system --add safe.directory /srv/fai/config` |
| `WARN: git push fehlgeschlagen` | the config space has no remote | harmless; add a remote or ignore |
| `install.sh`: `ufw ist nicht installiert` | package missing | `sudo apt install ufw` |
| after the installation: `task_chboot` / `task_savelog` `Permission denied` | `.ssh` of the log user belongs to root | [section 1.1](#11-a-working-base-fai-server), SSH access |
| `Rename for <MAC> failed. Permission denied` | `pxelinux.cfg` directory not owned by the FAI user | `chown fai:nogroup /srv/tftp/fai/pxelinux.cfg` |
| packages cannot be installed on the target, looks like a GRUB problem | `APTPROXY` points to another server | fix `class/DEBIAN.var` |
| the client cannot reach the web console | short name in `FAI_DISCOVERY_INTERNAL_URL` | use a fully qualified name or an IP, restart the service |
| every approval fails | `FAI_DISCOVERY_NFS_ROOT` missing or `localhost` | set it as in section 1.5, restart the service |
| a changed `site.conf` value has no effect | the file is read only at start | `systemctl restart fai-discovery-webconsole` |
| the profile list is empty | `FAI_DISCOVERY_PROFILE_FILE` does not exist | [section 1.3](#13-a-profile-file) |
| a new `site.conf` variable has no effect although the repository is up to date | the wrapper in `/usr/local/bin` is old | [section 6](#6-updating) |
| the client waits about 2 minutes at `systemd-networkd-wait-online` and has a WLAN interface | dracut waits for an interface that never gets "configured" | set `FAI_DISCOVERY_RD_NEEDNET=0` in `site.conf` (needs the current wrapper), restart the service |
| UEFI client loops with `Failed to load COM32 file menu.c32` | BIOS menu modules for a UEFI client | [section 4](#4-optional-features), rollout order of the menu |
| no login possible in the install environment | root has `*` in the NFSROOT | `fai-make-nfsroot -f` |
