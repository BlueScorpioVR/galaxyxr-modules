# BlueScorpioVR Galaxy XR modules

Personal, experimental modules for Samsung Galaxy XR (SM-I610), using
[KernelSU GXR](https://github.com/4uva4ek/KernelSU-GXR).
Not affiliated with Samsung, Google or the KernelSU GXR maintainers.

## Auto-spatialization default ON

Sets user 0's Android System setting `auto_spatialization_settings` to `1`
once after Android boot completes, each time KernelSU dispatches the module's
service stage. It does not poll or continuously enforce the setting.

This enables the saved Labs preference; it does **not** force every window into
3D, change per-window choices, remove size/content restrictions, or bypass thermal
protections. Android may still turn the preference/effect off later.

### Install

1. In KernelSU GXR, add `https://github.com/BlueScorpioVR/galaxyxr-modules`
   under Modules → Sources, or install the release ZIP with the reviewed GXR installer.
2. Installation leaves the module **disabled**. Enable it separately.
3. After acquiring root, use the documented KernelSU soft restart to dispatch services.
   On the tested setup, Tailscale had to be force-stopped before a soft restart.
4. Action reports the preference, saved original value and last startup log; it
   does not enable the module or prove that any particular window is spatialized.

**Full reboot prerequisite:** the ZIP persists, but the module cannot acquire root.
DFRoot/KernelSU must be running and dispatch services after each full reboot.
Without that, the Android setting normally persists, but the module cannot repair
a preference reset. This project does not enable automatic rooting.

### Disable / rollback

Unchecking stops future startup writes. It does not immediately undo a completed
one-shot settings change. To disable **and restore** the preference captured before
the first application:

```sh
su -c 'sh /data/adb/modules/gxr_bsvr_auto_spatialization/action.sh off'
```

Restoration only writes if the current value is still `1`; a later user choice is
preserved. If the original value was already `1`, restoring it naturally leaves it
on. Errors retain the recovery record and block reviewed replacement. To request
OFF explicitly, use the Labs toggle or:

```sh
settings --user 0 put system auto_spatialization_settings 0
```

Disable the module first or the next service startup will set it back to `1`.
Restore before removing the module; there is no automatic uninstall script.
No system/vendor files, USB configuration, firmware or boot integration are changed.

### Validation / limitations

The setting was read and written successfully on firmware I610UEU2AZF3 and its
saved value was verified in SettingsProvider storage. All nine host tests pass.
Version 0.1.0 was installed through KernelSU GXR 1.0.8's reviewed installer;
all eight payload checksums passed. After separately enabling it, the one-shot
service changed the preference from 0 to 1 and status verified the saved original
value of 0. No restart was performed for that activation. UI behavior, restoration
on the headset and automatic reapplication across reboot remain unverified.

### Build and test

Requires Python 3 and a POSIX shell (Git Bash works on Windows):

```sh
python -m unittest discover -s tests -v
python tools/build.py
```

The build produces a deterministic ZIP and SHA-256 sidecar under `dist/`, plus the
update feed. Only reviewed module payload files are packaged; no vendor binaries,
device identifiers, logs or credentials are published.
