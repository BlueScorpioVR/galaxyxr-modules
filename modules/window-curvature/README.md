# Galaxy XR Home Space Window Curvature (experimental)

**Experimental stability warning:** an installed 0.1.0 session was followed
by a native SystemUI crash. 0.1.2 repairs the confirmed closed-wrapper cleanup
bug using a separately owned same-node handle; this is not proof that the native
crash is fixed. Do not clear crash quarantine just to retry normal operation.

Adds **Curve window / Flatten window** and a **0-100% strength slider** to the
ordinary app-window contextual menu. Each window starts flat and has its own
strength. Existing menu actions are preserved. No stereo/auto-spatialization
setting, immersive-mode flag, APK, or installed library is replaced.

## Supported build

- Galaxy XR SM-I610, Android 14, firmware I610UEU2AZF3.
- Exact SystemUI APK, renderer and Impress hashes in firmware.sha256 must match.
- Ordinary attached 2D Home Space app windows using XrCaptionMenu. Immersive XR
  apps, system-control windows and other menu implementations are not supported.
- Up to 32 independently controlled windows; task IDs are never persisted.
- **v0.1.2: 100% now gives the same bend as v0.1.0's 75%**, including wide
  windows. Both the curvature ceiling and width-based arc limit are scaled down.
  Maximum native curvature is 3/m, reduced by window width to a nominal
  112.5-degree arc. This is an experimental guard, not a guarantee for all sizes/apps.

## Install and enable

1. Download the ZIP from the
   [0.1.2 release](https://github.com/BlueScorpioVR/galaxyxr-modules/releases/tag/window-curvature/v0.1.2)
   or find Window Curvature in this repository's KernelSU GXR Sources catalogue.
   Install from KernelSU Manager; it installs **disabled**, including updates.
2. Read these limitations, enable its checkbox, and reboot when ready.
3. Open any supported app window's contextual menu, then use the new controls.

Active root and normal KernelSU service startup are required; this module cannot
acquire root. If a full reboot loses root on your setup, re-acquire it and use
KernelSU GXR's documented soft restart to dispatch module services.

The module never restarts SystemUI or the framework itself. Startup is one-shot.
Re-enabling after a live stop requires a new SystemUI incarnation (normally a
reboot); repeated attachment to the same process is deliberately refused.

## Disable / remove

Turning off the KernelSU checkbox is detected by the supervisor. It sends a stop
command, restores every owned window to flat, removes the added controls, and
detaches the owned injector. Allow approximately 5 seconds. Removal uses the same
path. Independent Java watchdogs expire in 3 seconds without injector heartbeats;
native visibility permissions expire in 2 seconds. The controller never kills
Android services. Do not run multiple copies of this module or the old probe.

The Manager action button reports status. Root shell alternatives:

```sh
sh /data/adb/modules/gxr_window_curvature/action.sh status
sh /data/adb/modules/gxr_window_curvature/action.sh off
```

After a crash/interrupted session, the module disables itself and preserves
recovery markers. Reboot with it disabled and inspect failure/runtime.log, then
acknowledge quarantine explicitly before enabling and rebooting again:

```sh
sh /data/adb/modules/gxr_window_curvature/action.sh reset
```

There are no network listeners, remote-control APIs, app preferences, or saved
per-package curves. No PC connection is needed during normal module operation.
Task detach, transition to immersive rendering, or node replacement flattens the
owned window and discards its controls. Returning to Home Space starts flat.

## Known limitations

- Move/resize highlights remain flat; a resize corner can sit behind a curved
  edge. This was accepted by the tester as non-blocking, not fixed.
- Thin white edges can flicker with head movement.
- Dialogs, keyboard, secure windows, extreme aspect ratios and every app have
  not been exhaustively tested. Only supported ordinary contextual menus receive
  controls; "any window" does not mean immersive/system-owned surfaces.
- Width changes are checked at the next heartbeat (about 0.5 seconds), not
  instantaneously. Growing a curved window reduces the ceiling; shrinking it
  does not silently increase the bend during that session.
- Failed native restoration remains retryable and is not reported as success.
- A surviving SystemUI process is required for Java rollback. On process death,
  its scene nodes disappear; no curvature is persisted into the replacement.
- Framebuffer10 was left enabled during development tests. This is not a clean
  stock-renderer certification, and earlier XR Home crashes remain unattributed.

## Build and audit

tools/build_window_curvature.py builds the helper, bundles frida-java-bridge,
verifies pinned dependencies, includes source and license notices, and creates
the disabled ZIP plus SHA256. Test-only Android fakes are never packaged.
Build inputs and output hashes are recorded. See the validation summary below.
The on-device supervisor verifies SHA256SUMS before attachment.

Build prerequisites are Python with frida==17.23.3, Java, ECJ 3.39.0, D8/R8
8.7.18 and Android compile stubs (android-4.1.1.4.jar was used). The build downloads
and verifies the pinned Android arm64 injector and Java-bridge npm archive into
the specified cache; those binaries are release assets, not tracked source files.
Run the following from the repository root:

```sh
python tools/check_window_curvature.py --java <java> --ecj <ecj.jar>
node --test tests/window-curvature-policy.test.mjs
python tools/build_window_curvature.py --java <java> --ecj <ecj.jar> --r8 <r8.jar> --android-jar <android.jar> --cache <cache-directory>
python tools/check_window_curvature_package.py dist/gxr-window-curvature-0.1.2-experimental-disabled.zip
```

### Validation

Staged tests verified independent curves on KernelSU, Chrome and OpenChamber,
menu closure/reopening, and live disable restoring owned windows to flat without
a SystemUI/SpaceFlinger restart. The 0.1.2 repair passed a three-minute test with
multiple curved windows, closing a curved app and reopening it, followed by
automatic flat shutdown without cleanup errors. The owner reported flawless
behavior during that test and subsequently confirmed the installed version runs
fine. A proposed ten-minute test was not run; longer-session and broad lifecycle
coverage remain incomplete, and the original native crash cause is unresolved.

Host regression tests cover the new 100% equalling the previous 75% for both
narrow and width-limited windows, owned same-node rollback after source-wrapper
close, retryable live restore failures, and isolated task/menu cleanup.
