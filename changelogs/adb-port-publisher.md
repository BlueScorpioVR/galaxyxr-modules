# 0.1.0

- Reports the headset's wireless-debugging (adbd) port to a host on the tailnet
  at the KernelSU service stage, so adb can reconnect after a reboot or soft
  restart without the changing port being read off the device.
- Reads only a local socket list (`ss -lntp`) and sends one request; changes no
  system state and exposes no service.
- Ships no host, port or token: configuration lives outside the package at
  `/data/adb/xr-adb-port.conf` (mode 600) and is set with `action.sh configure`.
- Action reports status, re-publishes on demand, and enables/disables reporting.
- Always exits 0 so a transient host outage cannot quarantine the module.
- Host-tested only; not yet exercised across a headset reboot.
