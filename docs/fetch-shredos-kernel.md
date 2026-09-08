# `fetch-shredos-kernel.sh`

Downloads the current [ShredOS](https://github.com/PartialVolume/shredos.x86_64)
x86_64 release, verifies its checksum and extracts the kernel to
`/srv/tftp/fai/shredos/vmlinuz` — the file the "Securely wipe (ShredOS)"
button in the web console's history needs at PXE boot time.

The kernel itself is **not** checked into this repository: it's a
~350MB binary, well past GitHub's 100MB hard limit for pushes. Fetching
it on demand avoids that entirely.

## Requirements

- Root access (`losetup`/`mount` need it)
- `curl`, `sha1sum`, `losetup`, `mount` — all standard on Debian/Ubuntu
- Internet access to `api.github.com` and `github.com` (release
  download)

## Running it

```bash
sudo /opt/fai-discovery-repo/02-webconsole/bin/fetch-shredos-kernel.sh
```

## What the script does

1. Queries the GitHub API for the latest release of
   `PartialVolume/shredos.x86_64`.
2. Picks the full x86-64 `.img` asset (skips the `i686`, `_lite` and
   `_plus-partition` variants, and the `.iso` builds).
3. Downloads the image and its `.sha1` checksum file, then verifies it.
4. Mounts the image's boot partition via a loopback device.
5. Copies `/boot/bzImage` to `/srv/tftp/fai/shredos/vmlinuz` and sets
   `chown fai:nogroup` to match the rest of `/srv/tftp/fai`.
6. Cleans up the loopback mount and temporary download.

Safe to run again — it simply overwrites the file with whatever the
current release is at the time.

Current ShredOS releases (v0.42+) ship a single self-contained
`bzImage` with an embedded initramfs, so no separate `initrd` is
needed in the generated PXE config.
