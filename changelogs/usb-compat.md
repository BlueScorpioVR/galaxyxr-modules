# USB NCM + AOA 0.1.0

First public release of the existing `gxr-usb-compat` module for Galaxy XR
SM-I610 / I610UEU2AZF3. Runtime shell scripts and AOA XML are unchanged from
the initial local 0.1.0 build; public packaging adds documentation, tests and
reproducible builds. Existing working local installations need not be replaced.

- Prepare Samsung's missing `ncm.0` configfs function and request NCM at service
  startup only from MTP/charging; preserve an active accessory or other mode.
- Advertise `android.hardware.usb.accessory` through a checked, temporary XML
  bind mount before Android framework startup. Original partitions are not written.
- Include report-only Action, owned-state rollback and a disabled default.
- **Owner-confirmed AOA operation with a DJI drone in DJI Fly on 2026-10-19.**
  This report does not identify the models/app version or certify other devices.
- NCM gadget creation/binding checked; end-to-end NCM network traffic unverified.
  No DHCP, IP configuration, NAT or firewall changes are supplied.

**Direct deployment only:** generic installation is intentionally blocked and
the reviewed GXR installer rejects the required early-start hook. Not listed in
the Sources catalogue; no update feed. See `modules/usb-compat/README.md` for
installation, soft-restart activation, verification and recovery instructions.

[Installation and recovery guide](https://github.com/BlueScorpioVR/galaxyxr-modules/blob/main/modules/usb-compat/README.md)

Selecting/restoring USB modes can change the wireless ADB port. Requires active
root, exact firmware and a separate enable/soft restart. AOA and NCM are alternative
USB compositions, not forced simultaneous modes. No headset settings were changed
as part of publishing this release.
