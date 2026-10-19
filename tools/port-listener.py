#!/usr/bin/env python3
"""Receive the Galaxy XR headset's wireless-debugging (ADB) port over Tailscale.

The headset's adbd port is chosen by Android and changes on every reboot and
KernelSU soft restart, so there is no fixed address to ``adb connect`` to. The
KernelSU module ``gxr_bsvr_adb_port_publisher`` reports the current port here;
this listener records it so the port can be looked up instead of read off the
headset.

Endpoints:
    GET /report/<token>/<port>   record the port (writes adb-port.txt)
    GET /port                    return the last recorded port

Writes require the token. The listener binds 0.0.0.0 by default, so it is
reachable over the tailnet and the local LAN; never expose it publicly.

Run it on the PC that stays on while you use the headset:

    python port-listener.py                  # first run creates token.txt
    python port-listener.py --port 8099 --bind 0.0.0.0 --dir .

Then configure the headset with the printed token:

    su -c 'sh /data/adb/modules/gxr_bsvr_adb_port_publisher/action.sh \
        configure <this-pc>.<tailnet>.ts.net 8099 <token>'

The port must match ``--port`` here and the module's configured port.
"""

from __future__ import annotations

import argparse
import datetime
import os
import re
import secrets
import socket
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def choose_dir(value: str | None) -> Path:
    return Path(value).expanduser().resolve() if value else Path(__file__).resolve().parent


def ensure_token(directory: Path, log) -> str:
    path = directory / "token.txt"
    if path.is_file():
        token = path.read_text(encoding="utf-8").strip()
        if token:
            return token
    token = secrets.token_hex(16)
    path.write_text(token + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    log(f"created {path}")
    print(f"New token written to {path}")
    print(f"Configure the headset with it:\n  {token}\n", flush=True)
    return token


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", default=None,
                        help="where token/adb-port/listener.log live (default: script directory)")
    parser.add_argument("--bind", default="0.0.0.0", help="address to bind (default 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8099, help="TCP port (default 8099)")
    args = parser.parse_args()

    directory = choose_dir(args.dir)
    directory.mkdir(parents=True, exist_ok=True)
    port_file = directory / "adb-port.txt"
    log_file = directory / "listener.log"

    def log(message: str) -> None:
        stamp = datetime.datetime.now().isoformat(timespec="seconds")
        with open(log_file, "a", encoding="utf-8") as handle:
            handle.write(f"{stamp} {message}\n")

    token = ensure_token(directory, log)

    class Handler(BaseHTTPRequestHandler):
        server_version = "xr-adb-port/1"

        def _reply(self, code: int, body: str = "") -> None:
            payload = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            if payload:
                self.wfile.write(payload)

        def do_GET(self) -> None:  # noqa: N802 (http.server API)
            parts = [p for p in self.path.split("?", 1)[0].split("/") if p]

            if parts == ["port"]:
                try:
                    self._reply(200, port_file.read_text(encoding="utf-8").strip())
                except FileNotFoundError:
                    self._reply(404, "unknown")
                return

            if len(parts) == 3 and parts[0] == "report":
                given, port = parts[1], parts[2]
                peer = self.client_address[0]
                if given != token:
                    log(f"rejected bad token from {peer}")
                    self._reply(403, "bad token")
                    return
                if not re.fullmatch(r"[0-9]{1,5}", port) or not (1024 <= int(port) <= 65535):
                    log(f"rejected bad port {port!r} from {peer}")
                    self._reply(400, "bad port")
                    return
                port_file.write_text(port + "\n", encoding="utf-8")
                log(f"adb port {port} reported by {peer}")
                self._reply(200, port)
                return

            self._reply(404, "not found")

        def log_message(self, *args) -> None:  # keep stdout quiet; we log to file
            return

    try:
        server = ThreadingHTTPServer((args.bind, args.port), Handler)
    except OSError as error:
        print(f"Cannot bind {args.bind}:{args.port}: {error}", file=sys.stderr)
        print("Another listener may already be running on that port.", file=sys.stderr)
        return 1

    log(f"listener starting on {args.bind}:{args.port}")
    print(f"Listening on {args.bind}:{args.port}")
    print(f"  token    {directory / 'token.txt'}")
    print(f"  port file {port_file}")
    print(f"  log      {log_file}")
    print(f"  local check: curl http://127.0.0.1:{args.port}/port")
    sys.stdout.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
