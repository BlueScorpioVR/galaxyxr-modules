# Galaxy XR ADB port publisher

Reports the headset's wireless-debugging (ADB) port to a host on the tailnet.

## Why

Android picks the wireless-debugging port at random and changes it on every
reboot **and every KernelSU soft restart**, so there is no fixed address to
`adb connect` to. mDNS discovery does not cross Tailscale. This module re-reports
the current port at each service stage, so `adb` can reconnect without reading the
port off the headset each time.

## What it does

At the KernelSU service stage (cold boot and each coordinated soft restart) it:

1. reads adbd's listening port from `ss -lntp`;
2. sends one request to `http://<host>:<port>/report/<token>/<adbd-port>`;
3. records the value locally in `/data/adb/xr-adb-port.state`.

That is all. It changes no system state, exposes no service, and reads only a
local socket list. If the host is unreachable it logs that and stops for the
current generation.

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
`action.sh on` to start reporting immediately.

## Receiver

The host must provide a small endpoint:

* `GET /report/<token>/<port>` — record the port (403 on a bad token).
* `GET /port` — return the last recorded port.

The companion implementation used with this module is a ~90-line Python listener
(`port-listener.py`) that writes the last port to `adb-port.txt`.

## Action

```sh
action.sh status                     # configuration (token redacted), last port, log
action.sh configure <host> [port] <token>
action.sh report                     # publish now
action.sh on | off                   # enable / disable reporting
```

## Limits

* The port is only re-reported when the service stage runs. If the host is off at
  that moment, that generation is skipped; the next boot or soft restart reports.
* The report is best-effort and never blocks the restart: the script always exits
  0 so KernelSU does not quarantine it.
* `ss` must be present (it is on this firmware) and the module needs active root.
