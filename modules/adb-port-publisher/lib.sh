#!/system/bin/sh
# Shared helpers for the ADB port publisher.
#
# Configuration is read from a file outside the module so no host, port or token
# is ever shipped in the package. Create it with:
#     action.sh configure <host> [port] <token>

CONF=${ADB_PORT_CONF:-/data/adb/xr-adb-port.conf}
STATE=${ADB_PORT_STATE:-/data/adb/xr-adb-port.state}
LOG=${ADB_PORT_LOG:-/data/adb/xr-adb-port.log}
LOCK=${ADB_PORT_LOCK:-/data/adb/xr-adb-port.lock}
PIDFILE=${ADB_PORT_PIDFILE:-/data/adb/xr-adb-port.pid}

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

valid_port() {
    case "${1:-}" in '' | *[!0-9]*) return 1 ;; esac
    [ "$1" -ge 1024 ] && [ "$1" -le 65535 ]
}

# The wireless-debugging port is published by the framework as a property once
# its TLS listener is up. That property is authoritative and costs one tiny
# property read. The socket scan is only a fallback for legacy TCP mode: with -p
# it walks every process's fd table (~350 ms), so it must never be polled.
property_port() {
    for prop in service.adb.tls.port service.adb.tcp.port persist.adb.tcp.port; do
        p=$(getprop "$prop" 2>/dev/null)
        if valid_port "$p"; then
            printf '%s\n' "$p"
            return 0
        fi
    done
    return 1
}

socket_port() {
    ss -lntp 2>/dev/null | awk '/adbd/ {print $4; exit}' | sed 's/.*://'
}

read_port() {
    p=$(property_port) || p=$(socket_port)
    valid_port "$p" || return 1
    printf '%s\n' "$p"
}

# Port from an "AdbDebuggingManager: Received tls port=<n>" log line.
line_port() {
    case "${1:-}" in
        *"Received tls port="*) ;;
        *) return 1 ;;
    esac
    p=${1##*Received tls port=}
    p=${p%%[!0-9]*}
    valid_port "$p" || return 1
    printf '%s\n' "$p"
}

report_once() {
    curl -s -m 8 "http://$HOST:$PORT/report/$TOKEN/$1" >/dev/null 2>&1
}

# Publish a port. $2=1 forces a report even when it matches the saved value.
# Returns 0 when the receiver has the value (state file updated). The lock keeps
# the logcat watcher, the reconciler and a manual report from racing.
publish() {
    p=$1
    valid_port "$p" || return 1
    if [ "${2:-0}" != 1 ] && [ "$(cat "$STATE" 2>/dev/null)" = "$p" ]; then
        return 0
    fi
    if ! mkdir "$LOCK" 2>/dev/null; then
        # Reclaim a lock left behind by a killed publisher.
        [ -n "$(find "$LOCK" -mmin +2 2>/dev/null)" ] && rmdir "$LOCK" 2>/dev/null
        mkdir "$LOCK" 2>/dev/null || return 1
    fi
    if report_once "$p"; then
        printf '%s\n' "$p" >"$STATE"
        log "published adbd port $p"
        rmdir "$LOCK" 2>/dev/null
        return 0
    fi
    log "report failed for adbd port $p"
    rmdir "$LOCK" 2>/dev/null
    return 1
}
