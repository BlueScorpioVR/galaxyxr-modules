#!/system/bin/sh
MODDIR=${0%/*}
[ "$(id -u)" = 0 ] || exit 0
[ ! -f "$MODDIR/disable" ] && [ ! -f "$MODDIR/remove" ] || exit 0
exec sh "$MODDIR/auto.sh" report
