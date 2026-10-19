#!/system/bin/sh
# Shared helpers for the ADB port publisher.
#
# Configuration is read from a file outside the module so no host, port or token
# is ever shipped in the package. Create it with:
#     action.sh configure <host> [port] <token>

CONF=${ADB_PORT_CONF:-/data/adb/xr-adb-port.conf}
STATE=${ADB_PORT_STATE:-/data/adb/xr-adb-port.state}
LOG=${ADB_PORT_LOG:-/data/adb/xr-adb-port.log}

log() {
    printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S' 2>/dev/null)" "$*" >>"$LOG"
}

# Sets HOST, PORT, TOKEN. Returns non-zero unless all three are present.
load_conf() {
    HOST=
    PORT=
    TOKEN=
    [ -f "$CONF" ] && . "$CONF"
    [ -n "$HOST" ] && [ -n "$PORT" ] && [ -n "$TOKEN" ]
}

# Write the configuration atomically with owner-only permissions.
write_conf() {
    umask 077
    printf 'HOST=%s\nPORT=%s\nTOKEN=%s\n' "$1" "$2" "$3" >"$CONF.tmp"
    mv "$CONF.tmp" "$CONF"
}

# Show that a secret exists without printing it.
redact() {
    case "${1:-}" in
        '') printf '%s' '<unset>' ;;
        *) printf '%s… (%s characters)' "$(printf '%s' "$1" | cut -c1)" "${#1}" ;;
    esac
}

# Local address:port of the socket owned by adbd, e.g. "*:37243" -> "37243".
adb_port() {
    ss -lntp 2>/dev/null | awk '/adbd/ {print $4; exit}' | sed 's/.*://'
}

valid_port() {
    case "${1:-}" in '' | *[!0-9]*) return 1 ;; esac
    [ "$1" -ge 1024 ] && [ "$1" -le 65535 ]
}

# Report one port to the configured host. Non-zero on any failure.
report_once() {
    curl -s -m 8 "http://$HOST:$PORT/report/$TOKEN/$1" >/dev/null 2>&1
}
