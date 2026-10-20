# Galaxy XR USB NCM + AOA — 0.1.0

Reversible, experimental USB compatibility module for **Samsung Galaxy XR
SM-I610, firmware I610UEU2AZF3**, using KernelSU GXR. Module ID:
`gxr-usb-compat` (unchanged from the initial locally installed build).

**AOA works with DJI Fly:** on 2026-10-19 the owner reported a successful test
of AOA mode with their DJI drone in DJI Fly. This is a hands-on compatibility
report, not a claim of support for every DJI controller, app version or drone.
The drone/controller models, Fly version and individual functions exercised
were not recorded in that report. **NCM network traffic remains unverified.**

## What it fixes

- **NCM:** Samsung's init USB rules reference `ncm.0`, but the firmware creates
  only `ncm.gs6`. This module creates the missing configfs `ncm.0` function and
  lets Android's existing USB rules compose/bind it. At service startup it
  requests NCM only from MTP/charging, leaving active accessory, RNDIS and other
  explicit modes alone. Android retains USB ADB when it is enabled.
- **AOA (Android Open Accessory):** the kernel accessory device is present, but
  Android does not advertise `android.hardware.usb.accessory`. Before framework
  startup, the module bind-mounts the original accessory-library permissions XML
  plus that feature declaration into init's mount namespace. It checks the
  original XML's exact SHA-256 and refuses unsupported firmware/foreign overlays.
- **Recovery:** Action reports state/logs. Disable/removal makes the foreground
  service worker attempt to undo only the module's own changes.

No system/vendor partition writes, root acquisition, automatic Android restart,
DHCP, IP assignment, NAT, firewall changes or blanket USB permission grants.
There are no bundled vendor binaries, credentials or device identifiers.

NCM and AOA are alternative USB compositions; this module does not force both
at once. AOA is entered through the real USB host's handshake, not fabricated
DJI strings or a forced `accessory` property.

## Installation — direct deployment only

Download the ZIP and `.sha256` sidecar from the
[0.1.0 release](https://github.com/BlueScorpioVR/galaxyxr-modules/releases/tag/usb-compat/v0.1.0).
Verify the ZIP's SHA-256 before extracting it. It ships **disabled**.

**Do not use a generic KernelSU installer.** This module's `customize.sh`
intentionally refuses it: the Samsung installer can rewrite startup metadata.
The reviewed `gxr_*` installer rejects early-start hooks such as this module's
`post-fs-data.sh`. Consequently this package is **not in `modules.json`**, has
no automatic update feed, and cannot currently be installed through Sources.
Do not rename its ID to try to bypass the installer restrictions.

For a first installation, place the verified ZIP in `/sdcard/Download/` and run
the following **inside a root shell on the headset** (not in a Windows shell):

```sh
set -eu
stage=/data/local/tmp/gxr-usb-compat-0.1.0
dest=/data/adb/modules/gxr-usb-compat
test ! -e "$stage"
test ! -e "$dest"
mkdir "$stage"
unzip /sdcard/Download/gxr-usb-compat-0.1.0.zip -d "$stage"
cd "$stage"
sha256sum -c SHA256SUMS
test -f disable
cp -R "$stage" "$dest"
chown -R 0:0 "$dest"
find "$dest" -type d -exec chmod 755 {} \;
find "$dest" -type f -exec chmod 644 {} \;
chmod 755 "$dest/"*.sh
chmod 444 "$dest/aoa.xml"
chcon u:object_r:system_file:s0 "$dest/aoa.xml"
cd "$dest"
sha256sum -c SHA256SUMS
```

These instructions refuse an existing module directory. **Do not overlay or
replace a live installation.** For updates, disable/restore first, verify that
the module's overlay is absent, and retain the old directory outside
`/data/adb/modules/` before deploying a new disabled package. If you already
have the initial local 0.1.0 build working, this first public release does not
require reinstalling it: its shell scripts and AOA XML are unchanged.

## Activation

1. Acquire root with DFRoot/KernelSU GXR, then enable the module in KernelSU.
2. Use the documented **KernelSU soft restart**, not a full reboot. Its standard
   post-fs-data stage runs after Android stops and before Android starts again;
   the accessory feature declaration must be visible at that point. Checking
   the box or launching `service.sh` alone does not refresh Android's features.
3. Reconnect ADB and run the status command below, then test a real USB host.

Selecting NCM can restart ADB and change the wireless-debugging port. On older
KernelSU GXR builds affected by the Tailscale non-UTF-8 process-scan bug, a soft
restart may require force-stopping Tailscale first (disconnecting the VPN alone
does not stop its process). That workaround cuts tailnet connectivity.

The module persists on disk, but does not acquire root or enable root-on-boot.
After a full reboot, root and module startup must be arranged separately.

## Verification and limits

```sh
su -c 'sh /data/adb/modules/gxr-usb-compat/action.sh status'
```

Expect `Android accessory feature: true` after a successful startup, the owned
overlay mount, and an `ncm.0` function/link when NCM is selected. Those checks
alone do not establish DJI communication or a working Ethernet connection.

- AOA requires a compatible USB host, data cable, handshake and app permission.
- NCM requires a host driver and IP setup; this package supplies no DHCP/tethering.
- Unlock/disconnect can reset Android's mode to its saved default. The module
  does not rewrite that persistent setting or continuously force USB modes.
- AOA was confirmed by the owner in DJI Fly on 2026-10-19. NCM function creation
  and binding were checked manually, but end-to-end NCM networking is untested.
- Host/mock tests check mode preservation, rollback decisions, shell syntax,
  XML and reproducible packaging; they do not simulate the real USB protocol.
- Other firmware, device models, full cold-boot root persistence and long-term
  stability are not validated. This remains an experimental module.

## Disable, removal and recovery

Uncheck the module; its running worker attempts rollback within its polling
cycle. Explicit disable/rollback is also available:

```sh
su -c 'sh /data/adb/modules/gxr-usb-compat/action.sh off'
```

The worker unmounts only its own overlay. It restores the captured MTP/charging
mode only if it selected NCM and NCM is still current; an active AOA/other mode
is left alone. It attempts to remove the function it created, but leaves an
in-use configfs function for Android/kernel teardown. USB rollback can change
ADB's port. `uninstall.sh` uses the same recovery logic.

Android caches the accessory feature: after the overlay is removed, another
soft restart is needed to clear the feature. Disable before restarting to avoid
reapplication. A full reboot clears volatile mounts/configfs state, but an
enabled module can reapply when root/startup stages run. DFRoot's **Disable KSU
Modules** option is the fallback if a broken module prevents Android startup.

## Build and tests

```sh
python tools/build_usb.py
python -m unittest discover -s tests -v
```

The reproducible ZIP and SHA-256 sidecar are written to `dist/`. The build
packages an explicit file list, empty `disable`/`skip_mount` markers and payload
checksums. `aoa.xml` retains its Android Open Source Project Apache-2.0 notice.
