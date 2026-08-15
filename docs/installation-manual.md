# Manual installation (without `install.sh`)

All the steps `install.sh` automates, spelled out individually to
follow along and run yourself — for anyone who doesn't want to run
someone else's script via `curl | bash` for security reasons. Every
command is self-contained; none of it needs the script.

Requirement: a running FAI server (`/srv/fai/config` exists and is a
Git checkout), root access.

## 1. Get the repository

```bash
git clone https://github.com/<your-github-user>/fai-discovery.git /opt/fai-discovery-repo
cd /opt/fai-discovery-repo
```

(A full clone is enough for the manual installation — the sparse
checkout in `install.sh` is just an optimization.)

## 2. System user

```bash
useradd --system --create-home --shell /usr/sbin/nologin faidiscovery
```

## 3. `fai-chboot` wrapper and sudoers rule

```bash
install -o root -g root -m 755 02-webconsole/bin/fai-discovery-chboot /usr/local/bin/fai-discovery-chboot
visudo -cf 02-webconsole/etc/sudoers.d/fai-discovery
install -o root -g root -m 0440 02-webconsole/etc/sudoers.d/fai-discovery /etc/sudoers.d/fai-discovery
```

## 4. systemd unit for the web console

```bash
install -o root -g root -m 644 02-webconsole/api/fai-discovery-webconsole.service /etc/systemd/system/
```

By default, the unit expects the code under
`/opt/fai-discovery-repo/02-webconsole/api` (matching step 1). Adjust
`WorkingDirectory=` in the copied file if your path differs.

## 5. `site.conf`

```bash
mkdir -p /etc/fai-discovery
cat > /etc/fai-discovery/site.conf <<'EOF'
FAI_DISCOVERY_PROFILE_FILE=/srv/fai/config/class/example.profile
FAI_DISCOVERY_INTERNAL_URL=http://faiserver:8080
FAI_DISCOVERY_NFS_ROOT=nfs://faiserver/srv/fai/config
EOF
chmod 644 /etc/fai-discovery/site.conf
```

Adjust the values: `FAI_DISCOVERY_PROFILE_FILE` to your own FAI
profile file, `FAI_DISCOVERY_INTERNAL_URL`/`FAI_DISCOVERY_NFS_ROOT` to
the hostname or IP of your own FAI server (**not** `localhost` — both
values must be resolvable from the target machine; see
[`installation-webconsole.md`](installation-webconsole.md) for the
full list of available variables, including the optional
`FAI_DISCOVERY_LANGUAGE` UI language switch).

## 6. Admin account

```bash
cp 02-webconsole/etc/fai-discovery/admins.json.example /etc/fai-discovery/admins.json
chown root:faidiscovery /etc/fai-discovery/admins.json
chmod 640 /etc/fai-discovery/admins.json
```

**⚠️ Contains the demo login `admin`/`admin`.** Set your own password
immediately afterwards:

```bash
python3 -c "from werkzeug.security import generate_password_hash; print(generate_password_hash(input('Password: ')))"
```

Put the resulting hash into `/etc/fai-discovery/admins.json` under
`"admin"` (or use your own username) — keep the JSON valid, no
trailing comma after the last entry.

## 7. Deploy the discovery client hook and hostname resolution

```bash
sed "s|__FAI_DISCOVERY_INTERNAL_URL__|http://faiserver:8080|" \
    01-discovery-client/fai-config/hooks/discovery > /srv/fai/config/hooks/discovery
chown root:root /srv/fai/config/hooks/discovery
chmod 755 /srv/fai/config/hooks/discovery

sed "s|__FAI_DISCOVERY_INTERNAL_URL__|http://faiserver:8080|" \
    03-fai-configspace/fai-config/class/02-set-hostname.sh > /srv/fai/config/class/02-set-hostname.sh
chown root:root /srv/fai/config/class/02-set-hostname.sh
chmod 755 /srv/fai/config/class/02-set-hostname.sh
```

Use the same value as `FAI_DISCOVERY_INTERNAL_URL` from step 5. If
`/srv/fai/config` is a Git checkout:

```bash
git -C /srv/fai/config add hooks/discovery class/02-set-hostname.sh
git -C /srv/fai/config commit -m "fai-discovery: manual deployment"
git -C /srv/fai/config push
```

## 8. Firewall and start the service

```bash
ufw allow 8080/tcp   # or the equivalent for your own firewall
systemctl daemon-reload
systemctl enable --now fai-discovery-webconsole
```

## 9. Verify

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080/status/aa:bb:cc:dd:ee:ff   # expected: 200
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080/admin/                       # expected: 401
```

Open `http://<faiserver>:8080/admin/` in a browser and log in with the
admin account — done.
