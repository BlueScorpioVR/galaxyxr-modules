# Galaxy XR ADB port publisher

Reports the headset's wireless-debugging (ADB) port to a host on the tailnet.

## Why

Android assigns the wireless-debugging port after boot and can reassign it later,
and it changes on every reboot **and every KernelSU soft restart**, so there is no
fixed address to `adb connect` to. mDNS discovery does not cross Tailscale.

A one-shot report at the service stage is too early: on the reference device the
framework assigned the TLS port roughly two minutes *after* that stage, which left
the published value stale. v0.1.1 therefore reports on the assignment event.

## How it works

`service.sh` runs `auto.sh watch` for the whole boot:

1. **Seed** from the port property and publish it.
2. **Events.** `logcat -b all -s AdbDebuggingManager` blocks in logd until the
   framework logs `Received tls port=<n>` — emitted on every port assignment. The
   value is then re-read from the property, never taken from the log line, so a
   replayed line cannot republish an older port. Idle cost is effectively zero.
3. **Reconcile.** Every 5 minutes (`ADB_PORT_RECONCILE`), re-read the property and
   publish if it changed. This covers a restarted watcher, a lost logcat buffer,
   or a future firmware that renames the message.
4. Publishing is deduplicated against the saved value and serialised with a lock,
   so the event watcher, the reconciler and a manual report cannot race.

The port comes from `service.adb.tls.port` (then `service.adb.tcp.port` and
`persist.adb.tcp.port`). The old `ss -lntp` socket scan remains only as a fallback
for legacy TCP mode: with `-p` it walks every process's fd table (~350 ms per
call), so it is never polled.

It changes no system state, exposes no service, and reads only a property plus
logcat.

## Install and configure

The package installs **disabled** and ships no host, port or token — configure it
after installing:

```sh
su -c 'sh /data/adb/modules/gxr_bsvr_adb_port_publisher/action.sh configure <host> [port] <token>'
su -c 'sh /data/adb/modules/gxr_bsvr_adb_port_publisher/action.sh report'
```

Configuration is stored at `/data/adb/xr-adb-port.conf` (mode 600), outside the
module, so it survives module updates and is never published. `port` defaults to
`8099`. Then enable the module in KernelSU and soft restart, or use
`action.sh on` to start watching immediately.

## Receiver

The host must provide a small endpoint:

* `GET /report/<token>/<port>` — record the port (403 on a bad token).
* `GET /port` — return the last recorded port.

The companion implementation is a ~90-line Python listener (`port-listener.py`)
that writes the last port to `adb-port.txt`.

## Action

```sh
action.sh status                     # configuration (token redacted), adbd now, last port, log
action.sh configure <host> [port] <token>
action.sh report                     # publish now (forces a report)
action.sh on | off                   # start / stop watching
```

## Limits

* The event watcher depends on the `AdbDebuggingManager` log message. If a future
  firmware changes it, the 5-minute reconcile still recovers the port.
* Reports are best-effort: a failed report leaves the saved value untouched and is
  retried on the next event or reconcile.
* Needs active root; `service.adb.tls.port` is not readable by the shell user.
