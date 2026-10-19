# Galaxy XR ADB port publisher

Reports the headset's wireless-debugging (ADB) port to a small receiver on a PC,
so `adb connect` works after every reboot and soft restart without reading the
changing port off the headset.

## Why

Android assigns the wireless-debugging port after boot and can reassign it later,
and it changes on every reboot **and every KernelSU soft restart**, so there is no
fixed address to connect to. mDNS discovery does not cross networks, so it is no
help when the PC sits on another subnet or behind a VPN such as Tailscale.

A one-shot report at the service stage is too early: on the reference device the
framework assigned the TLS port roughly two minutes *after* that stage, leaving
the published value stale. This module reports on the assignment event instead.

## When you may not need this

If the headset and PC share a LAN and you only connect by hand, Android's wireless
debugging already advertises itself over mDNS, and adb can find and attach to the
paired device without a port. `adb mdns services` even prints the current port, so
on a LAN that is a quick manual fallback too.

This module is for what mDNS cannot reach:

* the PC and headset on **different networks** (a tailnet such as Tailscale, or a
  VPN);
* a LAN that **blocks multicast or isolates clients**, where discovery stays empty;
* **scripts, CI or agents**, which cannot rely on adb's interactive discovery and
  need a stable place to read the port.

## How it works

`service.sh` runs `auto.sh watch` for the whole boot:

1. **Seed** from the port property and publish it.
2. **Events.** `logcat -b all -s AdbDebuggingManager` blocks in logd until the
   framework logs `Received tls port=<n>` — emitted on every port assignment. The
   value is then re-read from the property, never taken from the log line, so a
   replayed line cannot republish an older port. Idle cost is effectively zero.
3. **Reconcile.** Every 5 minutes (`ADB_PORT_RECONCILE`), re-read the property and
   publish if it changed. Covers a restarted watcher, a lost logcat buffer, or a
   firmware that renames the message — and retries a report that failed because
   the PC was unreachable.
4. Publishing is deduplicated and serialised with a lock, so the event watcher,
   the reconciler and a manual report cannot race.

The port comes from `service.adb.tls.port` (then `service.adb.tcp.port` and
`persist.adb.tcp.port`). The old `ss -lntp` scan remains only as a fallback for
legacy TCP mode: with `-p` it walks every process's fd table (~350 ms per call),
so it is never polled.

It changes no system state, exposes no service on the headset, and reads only a
property plus logcat.

## Setup

Two sides: a receiver on the PC, and this module on the headset. The only network
requirement is that the headset can reach the PC on the receiver's TCP port.

* **Same LAN:** use the PC's LAN address. No VPN needed.
* **Different networks:** a tailnet such as Tailscale is the easy path; a stable
  MagicDNS name also survives DHCP changes better than a LAN IP.

Whichever you use, the module needs it at configure time and the PC needs to reach
the headset's wireless-debugging port for `adb connect`.

### 1. PC side (receiver)

Requirements: Python 3 and `adb`, plus network reachability between the two.

1. Copy `tools/port-listener.py` from this repository into a **private** directory
   that is not a git checkout, for example `%USERPROFILE%\xr-adb-port\`.
2. Start it:

   ```powershell
   cd "$env:USERPROFILE\xr-adb-port"
   python port-listener.py
   ```

   The first run creates `token.txt` (mode 600) and prints the token. It then
   listens on `0.0.0.0:8099` and writes:

   | File | Purpose |
   | --- | --- |
   | `token.txt` | Shared secret. Never commit or share it. |
   | `adb-port.txt` | Last reported port (read this). |
   | `listener.log` | Report history with the reporting peer address. |

3. Check it is up. `404 unknown` is correct until the headset reports:

   ```powershell
   curl.exe http://127.0.0.1:8099/port
   ```

4. Start it automatically at login. Save this as `start-listener.cmd` next to the
   listener, then copy it into your Startup folder
   (`shell:startup` / `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup`):

   ```bat
   @echo off
   cd /d "%~dp0"
   start "" pythonw port-listener.py
   ```

   On Linux/macOS use a systemd user unit or launchd job in the same way; the
   command is `python3 port-listener.py`.

Notes:

* `--port`, `--bind` and `--dir` let you change the port, bind address and state
  directory. The port must match the value configured on the headset.
* Leaving it bound to `0.0.0.0` is convenient on a home LAN; writes still require
  the token. Do **not** expose it through a public port or an internet-facing
  tunnel (Tailscale Funnel included).
* If the listener is down when the headset assigns a port, the report fails but the
  saved value is left alone; the module retries on the next assignment or on the
  five-minute reconcile once the listener is back.

### 2. Headset side (module)

Install the package (it installs **disabled**) and keep the token from step 1:

```sh
su -c 'sh /data/adb/modules/gxr_bsvr_adb_port_publisher/action.sh configure <pc-host> 8099 <token>'
```

`<pc-host>` is any address the headset can reach: the PC's LAN IP when both are on
the same network, or a tailnet name such as `mypc.<tailnet>.ts.net` or its `100.x`
address when they are not. Configuration is stored outside the module at
`/data/adb/xr-adb-port.conf` (mode 600), so it survives module updates and is never
shipped in a package.

Then enable it in KernelSU (checkbox, then soft restart), or start it immediately:

```sh
su -c 'sh /data/adb/modules/gxr_bsvr_adb_port_publisher/action.sh on'
su -c 'sh /data/adb/modules/gxr_bsvr_adb_port_publisher/action.sh status'
```

`status` shows the host, a masked token, the current adbd port, the last published
value and the log.

### 3. Connect from the PC

```powershell
$port = Get-Content "$env:USERPROFILE\xr-adb-port\adb-port.txt"
adb connect <headset-ip>:$port
adb devices
```

If the headset has moved port and the file has not caught up yet, retry in a few
seconds; the watcher publishes as soon as the framework assigns the new port.

## Action reference

```sh
action.sh status                              # config (token masked), adbd now, last port, log
action.sh configure <host> [port] <token>     # port defaults to 8099
action.sh report                              # publish now (forces a report)
action.sh on | off                            # start / stop watching
```

`off` stops the watcher and reports `GXR_UPDATE_STATE=STOCK`, which is what the
reviewed GXR installer checks when replacing the module.

## Receiver API

Any receiver can replace the bundled listener; the module only speaks these two
requests:

* `GET /report/<token>/<port>` — record the port. `403` on a bad token, `400` on an
  out-of-range port.
* `GET /port` — return the last recorded port.

## Limits

* The event watcher depends on the `AdbDebuggingManager` log message. If a future
  firmware changes it, the five-minute reconcile still recovers the port.
* Needs active root; `service.adb.tls.port` is not readable by the shell user.
* The headset must be awake and reachable from the PC over whatever path you
  configured (LAN or tailnet).

## Uninstall

```sh
su -c 'ksud module uninstall gxr_bsvr_adb_port_publisher'
# Optional: remove the configuration, state and log kept outside the module
su -c 'rm -f /data/adb/xr-adb-port.conf /data/adb/xr-adb-port.state /data/adb/xr-adb-port.log /data/adb/xr-adb-port.pid'
```
