#!/system/bin/sh
# KernelSU module action. Usage: action.sh status|configure|report|on|off
MODDIR=${0%/*}
. "$MODDIR/lib.sh"

usage() {
    echo 'Usage: action.sh status|configure|report|on|off'
    echo '  configure <host> [port] <token>   store host/port/token (port defaults to 8099)'
    exit 2
}

case "${1:-status}" in
status)
    exec sh "$MODDIR/auto.sh" status
    ;;
configure)
    [ "$(id -u)" = 0 ] || { echo 'Error: root required'; exit 1; }
    h=${2:-}
    a=${3:-}
    b=${4:-}
    [ -n "$h" ] || usage
    case "$a" in
        '' | *[!0-9]*) p=8099; t=$a ;;
        *) p=$a; t=$b ;;
    esac
    [ -n "$t" ] || usage
    write_conf "$h" "$p" "$t"
    echo "Saved $CONF (mode 600). Run 'action.sh report' to publish now."
    ;;
report)
    [ "$(id -u)" = 0 ] || { echo 'Error: root required'; exit 1; }
    exec sh "$MODDIR/auto.sh" report
    ;;
on)
    [ "$(id -u)" = 0 ] || { echo 'Error: root required'; exit 1; }
    [ ! -f "$MODDIR/remove" ] || { echo 'Error: module is marked for removal'; exit 1; }
    rm -f "$MODDIR/disable"
    nohup sh "$MODDIR/auto.sh" watch >/dev/null 2>&1 &
    echo 'Enabled; watching for port assignments.'
    ;;
off)
    touch "$MODDIR/disable"
    if [ -f "$PIDFILE" ]; then
        kill $(cat "$PIDFILE") 2>/dev/null
        rm -f "$PIDFILE"
    fi
    echo 'Disabled; reporter stopped.'
    ;;
*) usage ;;
esac
