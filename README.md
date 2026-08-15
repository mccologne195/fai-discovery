# fai-discovery

Preboot discovery and zero-touch provisioning workflow for
[FAI](https://fai-project.org/) (Fully Automatic Installation): unknown
machines register themselves with a web console at PXE boot time, an
admin assigns a hostname and FAI classes and approves the actual
installation — no prior inventory or manually maintained MAC lists
required.

## Features

- **Web console** with an overview of all waiting machines (hardware
  data, IP, firmware type), an approval form, history and simple
  HTTP Basic Auth
- **Hostname suggestions**: configurable type/location prefixes
  (e.g. `NB-K-...` for a notebook in Cologne) plus a suggestion
  derived from the serial number or hardware UUID
- **Automatic UEFI detection**: automatically picks the matching
  `_EFI` variant of the chosen `disk_config` class when approving, if
  one exists — no manual switching between BIOS/UEFI layouts needed
- **CLI fallback** to the web console for approvals without a browser
- **Portable setup script** (`install.sh`) for the initial setup on a
  new FAI server
- **Bilingual UI** (German/English), switchable via a single config
  variable — see [Configuration](#configuration) below

## Requirements

- A running FAI server (`fai-server`/`fai-client`/`fai-quickstart`,
  Debian/Ubuntu) with a working base PXE setup
- A DHCP server with ISC-dhcpd-compatible PXE boot options
  (`next-server`/`filename`) and a DNS server for dynamic updates of
  hostname and IP, e.g. [Technitium DNS](https://technitium.com/dns/)
- Python 3 with Flask for the web console

fai-discovery does **not** require any particular configuration
management tool — see [`docs/architecture.md`](docs/architecture.md).

## Quickstart

```bash
curl -fsSL https://raw.githubusercontent.com/<your-github-user>/fai-discovery/main/install.sh -o install.sh
less install.sh   # review before running
sudo bash install.sh
```

If you don't want to run someone else's script via `curl | bash` for
security reasons, the full manual walkthrough is in
[`docs/installation-manual.md`](docs/installation-manual.md).

## Configuration

All web console behavior is controlled through
`/etc/fai-discovery/site.conf` (read via systemd `EnvironmentFile=` —
restart the service after any change). The most notable variable:

| Variable | Required | Meaning |
|---|---|---|
| `FAI_DISCOVERY_LANGUAGE` | no | UI language: `de` or `en`. Missing or any other value falls back to German (the original default). |

See [`docs/installation-webconsole.md`](docs/installation-webconsole.md)
for the complete list of variables (profile file, internal URL, NFS
root, hostname-prefix lists, disk-config directory, language).

## Documentation

| File | Content |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | Overall flow, which component runs where |
| [`docs/installation-discovery-client.md`](docs/installation-discovery-client.md) | PXE boot hook (`01-discovery-client/`) |
| [`docs/installation-webconsole.md`](docs/installation-webconsole.md) | Web console (`02-webconsole/`), admin accounts, `site.conf` |
| [`docs/installation-fai-configspace.md`](docs/installation-fai-configspace.md) | Hostname resolution during installation (`03-fai-configspace/`) |
| [`docs/installation-portable-setup.md`](docs/installation-portable-setup.md) | `install.sh` in detail |
| [`docs/installation-manual.md`](docs/installation-manual.md) | All steps done manually, without running `install.sh` |
| [`docs/images-en`](docs/images-en) | Screenshots (English UI) |
| [`docs/images`](docs/images) | Screenshots (German UI) |

## License

[GPL-3.0](LICENSE)
