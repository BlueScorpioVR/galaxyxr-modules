# 0.1.1

- Report on the framework's port-assignment event instead of once at the service
  stage. On the reference device the TLS port was assigned ~2 minutes after that
  stage, so the 0.1.0 value went stale on every boot.
- Watch `logcat -s AdbDebuggingManager` for `Received tls port=<n>`; the value is
  re-read from the port property so a replayed log line cannot republish an old
  port. Blocking in logd means no polling while idle.
- Add a 5-minute property reconcile as a safety net for a restarted watcher, a
  lost logcat buffer, or a renamed log message.
- Source the port from `service.adb.tls.port` (then the TCP properties) instead of
  `ss -lntp`. The socket scan walks every process's fd table (~350 ms per call), so
  it is now only a fallback for legacy TCP mode.
- Deduplicate publishes and serialise them with a lock so the event watcher, the
  reconciler and a manual report cannot race.
- `service.sh` now runs a long-lived watcher; `action.sh on` starts it, `off`
  stops reporting.

# 0.1.0

- Reports the headset's wireless-debugging (adbd) port to a host on the tailnet
  at the KernelSU service stage.
- Reads only a local socket list (`ss -lntp`) and sends one request; changes no
  system state and exposes no service.
- Ships no host, port or token: configuration lives outside the package at
  `/data/adb/xr-adb-port.conf` (mode 600) and is set with `action.sh configure`.
- Action reports status, re-publishes on demand, and enables/disables reporting.
- Always exits 0 so a transient host outage cannot quarantine the module.
