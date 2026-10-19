#!/system/bin/sh
# Publisher logic. Usage: auto.sh report | status
#
# `report` runs at the KernelSU service stage (cold boot and each coordinated
# soft restart). The wireless-debugging port is chosen by adbd and changes on
# both, so it is re-reported every generation.
#
# `report` always exits 0: KernelSU records a non-zero exit as a failed service
# script and quarantines it until the next cold boot, which would block later
# reports for no benefit. Failures are written to the log instead.

MODDIR=${0%/*}
. "$MODDIR/lib.sh"

MAX_TRIES=${ADB_PORT_MAX_TRIES:-45}
INTERVAL=${ADB_PORT_INTERVAL:-2}

report() {
    if ! load_conf; then
        log "no usable configuration at $CONF; nothing published"
        exit 0
    fi

    tries=0
    while [ "$tries" -lt "$MAX_TRIES" ]; do
        p="$(adb_port)"
        if valid_port "$p"; then
            if report_once "$p"; then
                printf '%s\n' "$p" >"$STATE"
                log "published adbd port $p"
                exit 0
            fi
            log "report failed for adbd port $p"
        fi
        tries=$((tries + 1))
        sleep "$INTERVAL"
    done

    log 'host unreachable; adbd port not published this generation'
    exit 0
}

status() {
    if [ -f "$MODDIR/disable" ]; then echo 'Disabled'; else echo 'Enabled (requires active root)'; fi
    if load_conf; then
        printf 'Host: %s:%s\n' "$HOST" "$PORT"
        printf 'Token: %s\n' "$(redact "$TOKEN")"
    else
        printf 'No usable configuration at %s\n' "$CONF"
        printf 'Configure with: action.sh configure <host> [port] <token>\n'
    fi
    printf 'Last published: %s\n' "$(cat "$STATE" 2>/dev/null || echo none)"
    cat "$LOG" 2>/dev/null
}

case "${1:-report}" in
    report | apply) report ;;
    status) status ;;
    *) echo 'Usage: auto.sh report|status'; exit 2 ;;
esac
