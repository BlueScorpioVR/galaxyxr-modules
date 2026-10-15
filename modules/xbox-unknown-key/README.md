# Bluetooth Xbox unknown-key recovery (experimental)

Root-only Galaxy XR workaround for hand-navigation locking after Xbox reconnect.
Two manual tests restored navigation by releasing only Linux KEY_UNKNOWN (240),
without Home, disconnecting the controller, or restarting tracking. This does not
prove the firmware root cause; a held unknown key can also coexist with working hands.

The watcher polls once per second. It matches Bluetooth bus 0005, Microsoft vendor
045e and an Xbox Controller/Gamepad name, verifies the key is held, then sends only
EV_KEY 240 value 0 plus SYN_REPORT, once per connected input-device identity.
No product ID is hard-coded. Multiple matching controllers are handled separately.
Third-party/non-Microsoft Xbox-compatible devices are deliberately excluded.
Other Xbox models are eligible, but only product 0b22 has been manually tested.
Controllers without this erroneous held key are left untouched.

Install disabled, then explicitly enable via `sh action.sh on`. KernelSU starts
service.sh on normal rooted module startup. The files survive reboot; execution
does not work without active root. This does not change DFRoot boot settings.
Late/manual root restoration may require `sh action.sh on` to start the watcher.
KernelSU Disable or `sh action.sh off` stops it within a poll interval. Removal
leaves no persistent system changes. No restart/reboot is required for this trial.

This is not Steam Link VR gamepad forwarding and does not add a PC input bridge.
