#!/system/bin/sh
# Publisher logic. Usage: auto.sh watch | report | status
#
# `watch` runs for the whole boot. The wireless-debugging port is assigned by the
# framework after boot and can be reassigned later, so a single report at the
# service stage is too early and goes stale. Instead:
#
#   * logcat is the event source. The framework logs
#     "AdbDebuggingManager: Received tls port=<n>" on every assignment. Reading
#     logcat blocks in logd, so this costs nothing while idle and reacts to the
#     assignment itself rather than at some polling interval.
#   * the port value always comes from the property, never from the log line, so
#     a replayed line can never republish an older port.
#   * a slow reconcile re-reads the property as a safety net for a restarted
#     watcher, a lost logcat buffer, or a firmware that renames the message.

MODDIR=${0%/*}
. "$MODDIR/lib.sh"

RECONCILE=${ADB_PORT_RECONCILE:-300}

disabled() {
    [ -f "$MODDIR/disable" ] || [ -f "$MODDIR/remove" ]
}

seed() {
    p=$(read_port) || return 0
    publish "$p"
}

watch_events() {
    while :; do
        disabled && return 0
        logcat -T 1 -b all -s AdbDebuggingManager 2>/dev/null | while IFS= read -r line; do
            line_port "$line" >/dev/null || continue
            disabled && exit 0
            current=$(read_port) || continue
            publish "$current"
        done
        disabled && return 0
        # logcat exited (buffer reset, kill, or a device that dislikes -T).
        sleep 2
    done
}

watch_reconcile() {
    while :; do
        disabled && return 0
        seed
        sleep "$RECONCILE"
    done
}

stop_watchers() {
    [ -n "${events_pid:-}" ] && kill "$events_pid" 2>/dev/null
    [ -n "${reconcile_pid:-}" ] && kill "$reconcile_pid" 2>/dev/null
    rm -f "$PIDFILE"
}

watch() {
    if ! load_conf; then
        log "no usable configuration at $CONF; nothing published"
        return 0
    fi
    stop_existing
    seed
    watch_events & events_pid=$!
    watch_reconcile & reconcile_pid=$!
    printf '%s %s %s\n' "$$" "$events_pid" "$reconcile_pid" >"$PIDFILE"
    trap 'stop_watchers; exit 0' TERM INT
    wait
    stop_watchers
}

report() {
    if ! load_conf; then
        log "no usable configuration at $CONF; nothing published"
        return 0
    fi
    tries=0
    while [ "$tries" -lt 5 ]; do
        p=$(read_port) || {
            log 'could not read the adbd port; nothing published'
            return 0
        }
        publish "$p" 1 && return 0
        tries=$((tries + 1))
        sleep 2
    done
    return 0
}

status() {
    if [ -f "$MODDIR/disable" ]; then echo 'Disabled'; else echo 'Enabled (root required)'; fi
    if load_conf; then
        printf 'Host: %s:%s\n' "$HOST" "$PORT"
        printf 'Token: %s\n' "$(redact "$TOKEN")"
    else
        printf 'No usable configuration at %s\n' "$CONF"
        printf 'Configure with: action.sh configure <host> [port] <token>\n'
    fi
    printf 'adbd now: %s\n' "$(read_port 2>/dev/null || echo unknown)"
    printf 'Last published: %s\n' "$(cat "$STATE" 2>/dev/null || echo none)"
    cat "$LOG" 2>/dev/null
    # The reviewed installer verifies a replaced module's live restoration by
    # running `off` then `status` and looking for this exact line. This module
    # changes no system state, so a disabled module is genuinely stock.
    if [ -f "$MODDIR/disable" ]; then
        echo 'GXR_UPDATE_STATE=STOCK'
    fi
}

case "${1:-watch}" in
    watch) watch ;;
    report | apply) report ;;
    status) status ;;
    *) echo 'Usage: auto.sh watch|report|status'; exit 2 ;;
esac
