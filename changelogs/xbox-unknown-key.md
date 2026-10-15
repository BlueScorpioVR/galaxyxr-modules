# 0.1.0

- Release held Linux KEY_UNKNOWN (scan code 240) once per Bluetooth Microsoft Xbox connection.
- Match bus 0005, vendor 045e, and an Xbox Controller or Gamepad name. No product-ID restriction.
- Send only the key-up and a sync report. No Home event, button remap, axis change, or tracking restart.
- Installs disabled. Explicit enable starts a one-second rooted watcher; disable stops it within one poll.
- Requires active KernelSU root after boot. It cannot run while the headset is unrooted.
- Verified on Galaxy XR with one Xbox Wireless Controller (product 0b22). Other matching models are eligible but not yet live-tested.
