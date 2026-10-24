# HOWTO: Web console over HTTPS (Caddy)

*German version: [HOWTO-https.md](HOWTO-https.md)*

The fai-discovery web console itself only speaks HTTP on port 8080. For the admin pages you put
**Caddy** in front of it as a reverse proxy on the same server. Caddy accepts HTTPS on port 443 and
forwards to `127.0.0.1:8080`. `install.sh` sets this up with the script `fai-discovery-tls`, driven by
`/etc/fai-discovery/site.conf`.

Section 8 covers the all-in-one server for an installation room (`08-installationsraum/`).

## 1. Overview

```
 Admin browser ──https:443──► Caddy ──http──► 127.0.0.1:8080  web console (/admin, /approve)
                                                     ▲
 Installation clients ──────────http:8080────────────┘         (/register, /status, /device)
```

- **Installation clients stay on `http://…:8080`.** They send no passwords. HTTPS would require the
  NFS root to trust every CA, and a certificate error would make the client silently retry its
  registration forever.
- **Port 80 stays free by default.** Caddy does not redirect HTTP to HTTPS and by default does not
  use the ACME `http-01` challenge (it is optional, see 4a). FAI servers often already run a web
  server there (e.g. for `FAI_DISCOVERY_BOOT_URL`).
- **Admin pages over HTTPS only** (`FAI_DISCOVERY_ADMIN_HTTPS_ONLY=true`, section 6): direct requests
  to port 8080 are redirected to `https://` *before* the browser asks for the password, so the
  password never crosses the network in clear text.
- **Protection against forms from foreign sites (CSRF):** it keeps working behind Caddy, because
  Caddy passes the Host header through unchanged.

## 2. Requirements

- Debian 13 with fai-discovery installed
- Package `caddy` (Debian 13: version 2.6.2):

  ```bash
  sudo apt install caddy
  ```

  The package ships a default Caddyfile that wants port 80. If another service already listens
  there, Caddy's first start fails. That is harmless: `fai-discovery-tls` replaces this file (after
  backing it up).
- A DNS name (FQDN) under which the admins reach the server
- Port 443 free (or another one, see `FAI_DISCOVERY_TLS_PORT`)
- **No Caddy configuration of your own on the server.** `fai-discovery-tls` takes over the whole
  `/etc/caddy/Caddyfile`. If it finds anything other than the Debian default there, it aborts and
  changes nothing. In that case add the web console to your own configuration
  (`reverse_proxy 127.0.0.1:8080`) and leave `FAI_DISCOVERY_TLS_MODE` empty.

## 3. Choosing a mode

| Mode | Where does the certificate come from? | Renewal | Good for |
|---|---|---|---|
| `acme` | your own ACME CA, e.g. step-ca | automatic | networks with an existing CA |
| `internal` | Caddy's built-in CA | automatic | no CA, e.g. the all-in-one server |
| `files` | certificate made by hand, e.g. your own `openssl` CA | **manual** | one root for several servers, root limited to your own domain |

The settings live in `/etc/fai-discovery/site.conf`. A commented template is in
`02-webconsole/etc/fai-discovery/site.conf.example` (comments in German).

| Variable | Meaning |
|---|---|
| `FAI_DISCOVERY_TLS_MODE` | `acme`, `internal`, `files`; empty/`off` = no HTTPS |
| `FAI_DISCOVERY_TLS_HOST` | name in the certificate and target of the redirect (default: `hostname -f`) |
| `FAI_DISCOVERY_TLS_EXTRA_NAMES` | further names/IPv4 addresses in the certificate, comma-separated |
| `FAI_DISCOVERY_TLS_PORT` | HTTPS port (default `443`) |
| `FAI_DISCOVERY_TLS_ACME_CA` | `acme` only: directory URL of the CA |
| `FAI_DISCOVERY_TLS_ACME_CA_ROOT` | `acme` only: root certificate of the CA (if unset, the system trust store applies) |
| `FAI_DISCOVERY_TLS_ACME_CHALLENGE` | `acme` only: `tls-alpn-01` (default, port 443 only) or `http-01` (needs port 80) |
| `FAI_DISCOVERY_TLS_CERT_FILE` / `_KEY_FILE` | `files` only: certificate and key |
| `FAI_DISCOVERY_ADMIN_HTTPS_ONLY` | `true` = admin pages over HTTPS only (section 6) |

## 4. Setup

### 4a. Mode `acme` (e.g. step-ca)

```bash
# /etc/fai-discovery/site.conf
FAI_DISCOVERY_TLS_MODE=acme
FAI_DISCOVERY_TLS_HOST=faiserver.example.com
FAI_DISCOVERY_TLS_ACME_CA=https://ca.example.com:9000/acme/acme/directory
FAI_DISCOVERY_TLS_ACME_CA_ROOT=/usr/local/share/ca-certificates/example-root.crt
```

- By default the CA validates via **`tls-alpn-01` on the HTTPS port**. It must therefore reach the
  server under the name in `FAI_DISCOVERY_TLS_HOST` on port 443. That involves DNS, routing between
  VLANs and firewalls on both sides.
- **The CA must also offer `tls-alpn-01`.** You only find out with the first attempt. If it does
  not, `journalctl -u caddy` shows something like
  `no solvers available … (configured=[tls-alpn-01] offered=[dns-01 http-01])`. With step-ca, add the
  challenge to the `challenges` list of the ACME provisioner (`ca.json`) and reload the CA:

  ```json
  { "type": "ACME", "name": "acme", "challenges": ["http-01", "dns-01", "tls-alpn-01"] }
  ```

  With remote provisioner management enabled, this also works:
  `step ca provisioner update acme --challenge http-01 --challenge dns-01 --challenge tls-alpn-01`.
- **Alternative `http-01`:** `FAI_DISCOVERY_TLS_ACME_CHALLENGE=http-01`. Port 80 on the FAI server
  must then be free, because Caddy binds it for the challenge. `install.sh` opens it in `ufw`. If a
  web server already runs there (e.g. for `FAI_DISCOVERY_BOOT_URL`), only `tls-alpn-01` works.
- Every name in `FAI_DISCOVERY_TLS_EXTRA_NAMES` must be verifiable the same way. Better leave out
  IP addresses.

### 4b. Mode `internal` (Caddy's built-in CA)

```bash
# /etc/fai-discovery/site.conf
FAI_DISCOVERY_TLS_MODE=internal
FAI_DISCOVERY_TLS_HOST=faiserver.example.com
FAI_DISCOVERY_TLS_EXTRA_NAMES=192.0.2.10      # optional, e.g. to open the console by IP
```

On its first start, Caddy creates a root CA of its own and issues the server certificates from it.
They are short-lived and renewed automatically. The root has to be imported **once** on every admin
machine (section 5). It is located here:

```
/var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt
```

Good to know:

- Every server has its **own** root. With two FAI servers you import two roots.
- Reinstalling the server or deleting `/var/lib/caddy` creates a **new** root.
- This root cannot be limited to your own domain. Anyone with root on the FAI server could issue
  certificates for arbitrary names that the importing browsers would trust. So import it only on the
  admin machines. If that goes too far for you: use mode `files` with a constrained root (4c).

### 4c. Mode `files` (your own CA, by hand)

Worth it if **one** root should cover several servers, or if the root should be limited to your own
domain. Create the CA on an admin machine, not on the FAI server.

```bash
# 1. Root CA, once. Keep homelab-root.key offline afterwards.
openssl req -x509 -new -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -nodes \
  -keyout homelab-root.key -out homelab-root.crt -days 3650 \
  -subj "/CN=Homelab Root CA" \
  -addext "basicConstraints=critical,CA:TRUE,pathlen:0" \
  -addext "keyUsage=critical,keyCertSign,cRLSign" \
  -addext "nameConstraints=critical,permitted;DNS:example.com"

# 2. Server certificate, per FAI server
openssl req -new -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -nodes \
  -keyout faiserver.key -out faiserver.csr -subj "/CN=faiserver.example.com"
openssl x509 -req -in faiserver.csr -CA homelab-root.crt -CAkey homelab-root.key \
  -CAcreateserial -out faiserver.crt -days 397 -extfile <(printf '%s\n' \
  "subjectAltName=DNS:faiserver.example.com" \
  "extendedKeyUsage=serverAuth" \
  "keyUsage=critical,digitalSignature" \
  "basicConstraints=CA:FALSE")
```

- **`nameConstraints`:** the root may only issue certificates for `example.com` and below. Even with
  the root key, nobody can create a valid certificate for foreign sites. If you also open the server
  by IP, the root additionally needs `permitted;IP:<network>/<mask>` and the server certificate
  `IP:<address>` in its `subjectAltName`.
- **`subjectAltName` is mandatory:** browsers no longer look at the CN.
- **Lifetime at most 825 days:** macOS/Safari enforces this for private CAs too. 397 days is safe
  everywhere. Put the renewal date in your calendar.

Copy the files to the FAI server. The key must be readable by the service user `caddy`:

```bash
sudo install -d -m 750 -o root -g caddy /etc/caddy/certs
sudo install -m 644 -o root -g caddy faiserver.crt /etc/caddy/certs/
sudo install -m 640 -o root -g caddy faiserver.key /etc/caddy/certs/
```

```bash
# /etc/fai-discovery/site.conf
FAI_DISCOVERY_TLS_MODE=files
FAI_DISCOVERY_TLS_HOST=faiserver.example.com
FAI_DISCOVERY_TLS_CERT_FILE=/etc/caddy/certs/faiserver.crt
FAI_DISCOVERY_TLS_KEY_FILE=/etc/caddy/certs/faiserver.key
```

To renew, repeat step 2, replace the files and run `sudo systemctl reload caddy`.

### 4d. Applying the settings

Run `install.sh` again. It deploys `fai-discovery-tls`, writes `/etc/caddy/Caddyfile` (after checking
it with `caddy validate`), starts Caddy and opens the HTTPS port in `ufw`. If you only change the TLS
settings, you can call the script directly instead:

```bash
sudo /usr/local/bin/fai-discovery-tls
```

The script is idempotent. On invalid values, or a Caddyfile it did not write, it aborts and changes
nothing.

## 5. Importing the root certificate on the admin machines

Only needed for `internal` and `files`, and for `acme` if the CA is not known there yet. First note
the fingerprint and compare it after copying:

```bash
sudo openssl x509 -in /var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt \
  -noout -subject -fingerprint -sha256
```

| System | Import |
|---|---|
| macOS | `sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain root.crt` |
| Debian/Ubuntu | copy to `/usr/local/share/ca-certificates/<name>.crt`, then `sudo update-ca-certificates` |
| Windows | `certutil -addstore -f Root root.crt` (as administrator) |
| Firefox | own certificate store: Settings → Certificates → Authorities → Import, or set `security.enterprise_roots.enabled` to `true` |

Clicking "visit this website anyway" in the browser is no substitute for importing the root. The
exception only applies to the server certificate shown at that moment. In mode `internal`, Caddy
replaces that certificate about every 12 hours, and the warning comes back.

## 6. Admin pages over HTTPS only

Only switch this on once `https://<FAI_DISCOVERY_TLS_HOST>/admin/` works in the browser:

```bash
# /etc/fai-discovery/site.conf
FAI_DISCOVERY_ADMIN_HTTPS_ONLY=true
```

```bash
sudo systemctl restart fai-discovery-webconsole
```

Afterwards:

- `GET /admin/...` and `HEAD /admin/...` on port 8080 → `308` to
  `https://<FAI_DISCOVERY_TLS_HOST>[:port]/admin/...`, without a password prompt.
- `POST /admin/...` and `/approve` on port 8080 → `403 Nur ueber HTTPS erreichbar` ("only available
  via HTTPS").
- `/register`, `/status`, `/device` and `/metrics` stay unchanged on port 8080.
- Scripts such as `fai-discovery-approve.sh` need the `https://` address.
- The proxy is recognised by the request arriving via the loopback address, so Caddy has to run on
  the same server. `X-Forwarded-For` is deliberately ignored.

## 7. Checking

```bash
H=faiserver.example.com
curl -s  -o /dev/null -w "%{http_code}\n" http://localhost:8080/status/aa:bb:cc:dd:ee:ff  # 200 (clients)
curl -s  -o /dev/null -w "%{http_code}\n" https://$H/admin/                              # 401 (via Caddy)
curl -s  -o /dev/null -w "%{http_code} %{redirect_url}\n" http://$H:8080/admin/          # 308 https://… (with HTTPS_ONLY)
openssl s_client -connect $H:443 -servername $H </dev/null 2>/dev/null \
  | openssl x509 -noout -issuer -subject -enddate                                       # who issued it?
sudo ss -tlnp | grep caddy                                                               # only :443 and 127.0.0.1:2019
```

`curl` without `-k` only succeeds if the calling machine trusts the root. On macOS, `curl` may use a
different trust store than Safari; `--cacert root.crt` checks against the root directly.
`127.0.0.1:2019` is Caddy's local admin API (reachable locally only).

## 8. All-in-one server (installation room)

`08-installationsraum/allinone-bootstrap.sh` sets up HTTPS **by default** in mode `internal`, since an
installation room usually has no CA of its own.

### What the bootstrap does

- Installs `caddy`, but only with HTTPS. With `WEB_TLS=off` it skips the package, so that its default
  Caddyfile does not take port 80 on the next boot.
- Adds to `site.conf`:

  ```
  FAI_DISCOVERY_TLS_MODE=internal
  FAI_DISCOVERY_TLS_HOST=<SERVER_NAME>.<DOMAIN>
  FAI_DISCOVERY_TLS_EXTRA_NAMES=<ROOM_IP>,<management IP>
  FAI_DISCOVERY_ADMIN_HTTPS_ONLY=true
  ```

  The certificate then covers the FQDN (resolvable in the room via `dnsmasq`), the room IP and the
  address of the management NIC (`MGMT_IF`). That way the web console is reachable from the
  management network without a DNS entry.
- Additionally opens port 443 in `ufw` on the management NIC. The room NIC is open anyway.
- Prints the HTTPS addresses and the path to the root at the end.

### After the bootstrap

1. Fetch the root and import it on the admin machine (section 5). The file belongs to the user
   `caddy`, so first make a readable copy on the server:

   ```bash
   # on the server
   sudo install -m 644 /var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt /tmp/fai-room-root.crt
   # on the admin machine
   scp <server>:/tmp/fai-room-root.crt .
   ```

2. Open the web console: `https://<management IP>/admin/` (or `https://<FQDN>/admin/` from inside the
   room). Credentials: `/root/fai-discovery-initial-admin-password.txt`.
3. An SSH tunnel is no longer needed. If you still use one: `ssh -L 8443:127.0.0.1:443 <server>`,
   then `https://<FQDN>:8443` with an entry `127.0.0.1 <FQDN>` in your local `/etc/hosts`. Going
   through `127.0.0.1:8080` directly also works, because that counts as local access, but then the
   traffic is unencrypted up to the tunnel.

### Variants

- **Without HTTPS:** `WEB_TLS=off ./allinone-bootstrap.sh`. The web console stays at
  `http://<server>:8080/admin/` as before.
- **Your own root instead of Caddy's CA** (e.g. the same root for several rooms): create the
  certificate as in 4c, switch `site.conf` to `files` and run `sudo /usr/local/bin/fai-discovery-tls`.
- **Room server with access to an ACME CA:** switch `site.conf` to `acme` (4a). The CA must then reach
  the server on port 443 (or port 80 with `http-01`).
- **Rebuilding:** running the bootstrap again on the same server keeps `/var/lib/caddy` and thus the
  root. After reinstalling the operating system the root is new and has to be imported again.

## 9. Back to HTTP

```bash
# /etc/fai-discovery/site.conf: empty FAI_DISCOVERY_TLS_MODE or set it to off,
# remove FAI_DISCOVERY_ADMIN_HTTPS_ONLY
sudo /usr/local/bin/fai-discovery-tls        # restores the backed-up Caddyfile, stops Caddy
sudo systemctl restart fai-discovery-webconsole
sudo ufw delete allow 443/tcp
```

## 10. Troubleshooting

The script and the web console print their messages in German; they are quoted here as they appear.

| Symptom | Cause / fix |
|---|---|
| `fai-discovery-tls: FEHLER: /etc/caddy/Caddyfile ist weder von fai-discovery-tls noch der Debian-Standard` (neither written by the script nor the Debian default) | Your own Caddy configuration exists: add `reverse_proxy 127.0.0.1:8080` to it yourself, leave `FAI_DISCOVERY_TLS_MODE` empty |
| `caddy validate ist fehlgeschlagen` (validation failed) | Read the output above it; the old Caddyfile stays active |
| Browser: "connection not secure" | Root not imported (section 5), or the console was opened under a name/IP that is not in the certificate (`FAI_DISCOVERY_TLS_EXTRA_NAMES`) |
| `acme`: no certificate, page does not load | `journalctl -u caddy`: CA unreachable, root missing (`FAI_DISCOVERY_TLS_ACME_CA_ROOT`), or the CA cannot reach the server on port 443 (`tls-alpn-01`) |
| `acme`: `no solvers available … offered=[dns-01 http-01]` | The CA does not offer `tls-alpn-01`: enable it in the CA (4a), or use `FAI_DISCOVERY_TLS_ACME_CHALLENGE=http-01` if port 80 is free |
| Caddy does not start, `address already in use` | Port taken: `sudo ss -tlnp \| grep :443`, otherwise set `FAI_DISCOVERY_TLS_PORT` |
| `403 Nur ueber HTTPS erreichbar` (only via HTTPS) | A form or script still talks to port 8080; use the `https://` address |
| `403 Anfrage von fremder Seite abgelehnt` (request from foreign site rejected) | The Origin header does not match the host, e.g. a second proxy in front that rewrites the Host header |
| Admin pages cannot be opened any more | `FAI_DISCOVERY_ADMIN_HTTPS_ONLY` was set before HTTPS worked: remove the line, restart the web console |
