#!/system/bin/sh
MODDIR=${0%/*}
case "${1:-status}" in
    status)
        if [ -f "$MODDIR/disable" ]; then echo 'Disabled'; else echo 'Enabled (requires active root)'; fi
        cat "$MODDIR/status.log" 2>/dev/null
        exit 0 ;;
    off)
        touch "$MODDIR/disable"
        echo 'Disabled; watcher exits within one poll interval.' ;;
    on)
        [ "$(id -u)" = 0 ] || exit 1
        [ ! -f "$MODDIR/remove" ] || exit 1
        rm -f "$MODDIR/disable"
        nohup sh "$MODDIR/service.sh" >/dev/null 2>&1 &
        echo 'Enabled; reconnect Xbox to verify.' ;;
    *) echo 'Usage: action.sh status|on|off'; exit 2 ;;
esac
