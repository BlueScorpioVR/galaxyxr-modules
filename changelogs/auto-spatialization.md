# 0.1.0

- Set user 0's Labs auto-spatialization preference to ON once at service startup.
- Bounded boot wait, disable checks, settings lock and verified readback.
- Preserve the original preference for explicit restore; preserve later user choices.
- Reviewed GXR package format: disabled, skip-mount, checksums and status/restore action.
- No thermal, size-limit, system/vendor, USB or boot-root changes.
- Host-tested only; headset activation and reboot behavior not yet tested.
