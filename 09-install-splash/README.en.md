# 09-install-splash: full-screen display in the install environment

Instead of white text on a black terminal, the client shows a full-screen display during discovery and
installation: the fai-discovery icon, the current status and a progress bar.

German version of this file: [README.md](README.md).

The basic idea comes from FAI (Fully Automatic Installation) by Thomas Lange, <https://fai-project.org>. The display
mentions this in small print at the bottom.

> **Status:** Part of fai-discovery, bilingual (German/English), can be switched off in `site.conf` (default: off).
> Tested in a test VM (UEFI/OVMF, Proxmox VGA `std`, 1280x800) and on a Lenovo ThinkPad T490 (Intel i915,
> 1920x1080): discovery, approval, installation (Debian 13) up to "Installation complete", progress bar, keys and
> reboot with Enter. Not tested: the error display in a real run, BIOS boot, other graphics chips (AMD, NVIDIA).

## What is shown

The texts appear in German or English, depending on `FAI_DISCOVERY_LANGUAGE` in `site.conf` (`de` or `en`,
default `de`, the same setting as the web console). The table shows the English texts.

| Phase | Display |
|-------|---------|
| Discovery | "Reporting device", then "Waiting for approval" with MAC and IP and a moving bar, after approval "Approved" |
| Installation | "Installation in progress", "Step n of 17: <task>" and a progress bar in percent |
| End | "Installation complete" (green, 100 %). If `reboot` is missing from `FAI_FLAGS`, it says "Press Enter to reboot": Enter on the display reboots the machine (through `faireboot`). Alternatively press Alt+F1 and Enter there, as before |
| Error | "Error in step: <task>" (red) with a hint to Alt+F1/Alt+F2 |

The end is already shown at `TASKBEGIN faiend`, because without the `reboot` flag `task_faiend` waits for Enter and
`TASKEND faiend` therefore never arrives. Key presses made on the display before that point are discarded, so an
accidental Enter does not trigger a reboot.

The display runs on its own virtual terminal (tty8). **Alt+F1** still shows the FAI log, **Alt+F2** the shell
(`createvt`), and **Alt+F8** returns to the display. On notebooks where the function keys act as media keys, also
press **Fn**.

## How it works

- `fai-splash` is a Python 3 script using only the standard library (Python and the PSF console fonts are already in
  the NFSROOT, nothing is installed additionally).
- It draws directly into `/dev/fb0` (32 bit, with `write()`) and puts tty8 into graphics mode so the console does
  not write over it. If there is no framebuffer yet (BIOS boot: the DRM driver loads later), it waits up to
  3 minutes for one. If none appears, or it is not 32 bit, it exits quietly and the installation continues on the
  text console as before.
- Installation progress comes from `$LOGDIR/fai-monitor.log`: FAI writes `TASKBEGIN`/`TASKEND`/`TASKERROR` there
  for every task (`sendmon` in `/usr/lib/fai/subroutines`). No changes to FAI or to individual task hooks are needed.
- Messages from hooks (discovery) go through `fai-splash say -k info|wait|ok|error -m NAME [-s SUBLINE]
  [-d DETAIL] [-p PERCENT]`. `-m` takes the line and subline from the bilingual text catalogue (`TEXT` in
  `fai-splash`, names `msg.*`); `-l`/`-s` set texts directly.
- All visible texts are in `TEXT` (and `TASKS` for the step names), each with `de` and `en`. The language is taken
  from `FAI_SPLASH_LANG`, otherwise from the file `splash/lang` next to the script, otherwise German.
  `deploy-splash.sh` writes `splash/lang` from `FAI_DISCOVERY_LANGUAGE`.
- The icon `icon.png` comes from `icon/fai-discovery-icon-512.png` and is decoded and scaled at run time. The colours
  of the stripes are taken from the icon palette.

## Files

```
09-install-splash/
├── README.md / README.en.md
├── test_fai_splash.py      tests (translations, language selection, font)
├── deploy-splash.sh        deploys/removes the splash according to site.conf (called by install.sh)
└── fai-config/
    ├── hooks-subroutines.snippet   block for hooks/subroutines
    └── splash/
        ├── fai-splash      the service, usage see above
        ├── icon.png        icon (512 px)
        ├── allow-macs      (created by deploy-splash.sh) for which clients the splash runs
        └── lang            (created by deploy-splash.sh) de or en
```

## Setup and control through site.conf

The splash is **opt-in** and is switched on in `/etc/fai-discovery/site.conf`:

```
FAI_DISCOVERY_SPLASH_ENABLED=true
# optional: only for these clients (comma separated), otherwise for all
FAI_DISCOVERY_SPLASH_MACS=00:11:22:33:44:55,66:77:88:99:aa:bb
# language of the display (de or en, like the web console), default de
FAI_DISCOVERY_LANGUAGE=en
```

Then run `install.sh` again (or `deploy-splash.sh` on its own: `./deploy-splash.sh`). Depending on the setting it
deploys or removes:

- `splash/` in the config space (`fai-splash`, `icon.png`, `allow-macs`, `lang`),
- a block marked with `# BEGIN fai-splash` and `# END fai-splash` in `hooks/subroutines` that starts the service in
  `task_setup`.

Without `FAI_DISCOVERY_SPLASH_ENABLED=true` both are removed again. `allow-macs` and `lang` are local through
`.git/info/exclude`, so one server's settings do not travel to other servers through the config-space Git. Without
`allow-macs` the splash stays off.

The discovery messages come from `hooks/discovery` (a helper function `splash()` and five calls with `-m NAME`,
contained in `01-discovery-client/fai-config/hooks/discovery`). Without `fai-splash` nothing happens there.

Changes take effect on the client immediately: the config space is read over NFS at boot, no NFSROOT rebuild is
needed.

## Testing (development)

Preview a state as PNG, without a framebuffer, with any PSF font:

```bash
FAI_SPLASH_FONT=lat0-16.psf.gz ./fai-splash preview out.png --state install --size 1920x1080 --lang en
# states: boot, wait, install, done, error; language: de, en
```

The tests (translations complete, placeholders equal in both languages, language selection, font table):

```bash
python3 -m pytest 09-install-splash/test_fai_splash.py
```

## Lessons from the test on the T490 (not obvious, please note)

All of this only showed up on real hardware; none of it occurs in the VM (`bochs`):

1. **The graphics driver changes after start.** At boot the kernel uses `efifb`; `udev` loads the real driver
   (e.g. `i915`) only in `task_setup` (`udevadm trigger`), after the service has started. The new framebuffer sits at a
   different place in memory. On every pass the service therefore compares name, size and stride from
   `/sys/class/graphics/fb0/` and rebuilds everything when they change.
2. **Panning.** `fbcon` scrolls by panning, so the visible area no longer starts at line 0 and only part of the
   picture is seen. The service resets the offset to 0 with `FBIOPAN_DISPLAY`.
3. **Write with `write()`, not `mmap`.** Image data written through `mmap` does not reliably appear on the display
   with `i915` (the picture stays static). `write()` on `/dev/fb0` marks the lines as changed, and a following
   `FBIOPAN_DISPLAY` triggers a flip.
4. **`VT_PROCESS` instead of `VT_AUTO`.** The kernel forbids switching virtual terminals while the active console
   is in graphics mode and in `VT_AUTO` mode (`set_console` in `vt_ioctl.c`), and then also rejects a repeated
   `VT_ACTIVATE` on the same terminal. The service uses `VT_PROCESS` with `SIGUSR1`/`SIGUSR2` and acknowledges the
   switch requests.

## Allow list and diagnostics

- **`splash/allow-macs`:** created by `deploy-splash.sh` from site.conf. The service only starts on clients whose
  MAC (any NIC) is listed; the line `all` enables it for everyone; without the file it stays off. Comments start
  with `#`. This lets you try the splash on a production server with a single device first.
- **Switch off for one boot:** `nosplash` on the kernel command line.
- **Diagnostics:** the service writes `/tmp/fai/splash.log` on the client (`task_savelog` does not copy it to the
  server). With `splashdebug` on the kernel command line it also sends its state as `SPLASH ...` lines to the FAI
  monitor; they appear in `/var/log/fai/fai-monitor.log` on the server (heartbeat every 15 s, framebuffer, errors).
  This allows debugging a client without being able to log in.

## Limits

- The display only starts when FAI starts in the NFSROOT. The kernel and initrd phase (a few seconds) stays text on
  black. Plymouth in the initrd would be needed for that and is deliberately not part of this.
- Only 32-bit framebuffers. On systems without `/dev/fb0` (e.g. `nomodeset` without an EFI framebuffer) it stays on
  the text console.
- The texts use an 8x16 PSF console font, enlarged by an integer factor. Which letter is which glyph is defined by
  the font's Unicode table (without a table the Latin-9 order is used). Umlauts work, characters outside the font
  (e.g. "…") do not. Further languages therefore need a suitable font in the NFSROOT.
- To add a language, add it as another key in `TEXT`/`TASKS` and in `LANGUAGES`.
- The task weights for the bar (`TASKS` in `fai-splash`) are estimates; `instsoft` counts the most.
