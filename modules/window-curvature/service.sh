#!/system/bin/sh
MODDIR=${0%/*}
[ ! -f "$MODDIR/disable" ] && [ ! -f "$MODDIR/remove" ] || exit 0
sh "$MODDIR/control.sh" run >> "$MODDIR/service.log" 2>&1 &
