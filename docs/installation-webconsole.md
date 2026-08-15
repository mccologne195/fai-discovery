# Installation: Web console

The web console is the heart of fai-discovery: a Flask app running as
a systemd service on the FAI server, managing waiting devices,
approvals and admin accounts.

## Requirements

- Python 3 with Flask (`pip install flask` or a distribution package)
- `sudo`, `fai-chboot` (part of `fai-server`)
- Root access for the setup

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
