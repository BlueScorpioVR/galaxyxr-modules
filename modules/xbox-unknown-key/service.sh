#!/system/bin/sh
MODDIR=${0%/*}
[ "$(id -u)" = 0 ] || exit 1
[ ! -f "$MODDIR/disable" ] && [ ! -f "$MODDIR/remove" ] || exit 0
. "$MODDIR/lib.sh"
LOCK="$MODDIR/.watcher"
if ! mkdir "$LOCK" 2>/dev/null; then
    old=$(cat "$LOCK/pid" 2>/dev/null)
    case "$old" in ''|*[!0-9]*) ;; *)
        if kill -0 "$old" 2>/dev/null && tr '\000' ' ' < "/proc/$old/cmdline" 2>/dev/null | grep -Fq "$MODDIR/service.sh"; then
            exit 0
        fi ;;
    esac
    rm -f "$LOCK/pid"
    rmdir "$LOCK" 2>/dev/null || exit 1
    mkdir "$LOCK" || exit 1
fi
echo $$ > "$LOCK/pid"
cleanup() {
    if [ "$(cat "$LOCK/pid" 2>/dev/null)" = "$$" ]; then
        rm -f "$LOCK/pid"
        rmdir "$LOCK" 2>/dev/null
    fi
}
trap 'exit 0' TERM INT
trap cleanup EXIT
while [ "$(getprop sys.boot_completed)" != 1 ]; do
    [ ! -f "$MODDIR/disable" ] && [ ! -f "$MODDIR/remove" ] || exit 0
    sleep 1
done
seen='|'
echo 'Watcher started; no Home/button/axis injection.' > "$MODDIR/status.log"
while [ ! -f "$MODDIR/disable" ] && [ ! -f "$MODDIR/remove" ]; do
    scan_once /sys/class/input
    sleep 1
done
