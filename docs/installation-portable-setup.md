# Installation: Portable setup script (`install.sh`)

`install.sh` automates the complete setup from
[`installation-discovery-client.md`](installation-discovery-client.md),
[`installation-webconsole.md`](installation-webconsole.md) and
[`installation-fai-configspace.md`](installation-fai-configspace.md) in
one run, on a new FAI server.

If you don't want to run someone else's script via `curl | bash` for
security reasons: [`installation-manual.md`](installation-manual.md)
describes the same steps manually.

## Requirements

- Debian/Ubuntu with a working base `fai-server` setup
  (`/srv/fai/config` exists and is a Git checkout)
- Python 3 with Flask (`pip install flask` or a distribution package,
  e.g. `python3-flask` on Debian) — needed for the admin account in
  step 4, before the web console even starts
- Example Debian:
   ```bash
  apt-get install python3-flask
  ```
- `ufw` installed (step 6 opens port 8080/tcp via `ufw allow` — often
  not preinstalled on a fresh minimal install, `apt install ufw`)
- Root access
- An interactive terminal (the script prompts for admin credentials
  and configuration values — doesn't work in a plain `curl | bash`
  pipe without `/dev/tty`; download first, then run)

## Running it

```bash
curl -fsSL https://raw.githubusercontent.com/<your-github-user>/fai-discovery/main/install.sh -o install.sh
less install.sh   # review the content before running
sudo bash install.sh
```

## What the script does

1. Checks that it's running as root.
2. Creates the system user `faidiscovery` (skips if it already exists).
3. Clones this repository as a sparse checkout to
   `/opt/fai-discovery-repo` (only the subdirectories actually needed,
   not the whole repo).
4. Interactively asks for: the path to the FAI profile file, the
   internal URL of the web console. Creates an initial admin account if
   needed (prompts for username + password, generates the hash).
5. Deploys `fai-discovery-chboot`, the sudoers rule, the systemd unit,
   as well as `hooks/discovery` and `02-set-hostname.sh` (placeholder
   resolved automatically) to `/srv/fai/config`.
6. Opens port 8080 in the firewall (`ufw`).
7. Starts the `fai-discovery-webconsole` service (or restarts it if
   already active — safe to run again for updates).
8. Verifies with two `curl` checks that the web console responds.

The script is **idempotent** — running it multiple times only updates
the code and restarts the service; existing configuration
(`site.conf`, `admins.json`) is left untouched.

## Adjusting `REPO_URL`

The `REPO_URL` variable at the top of the script points to a
placeholder by default. If you fork or mirror this repository, adjust
it to your own fork/mirror URL before handing `install.sh` to anyone
else.
