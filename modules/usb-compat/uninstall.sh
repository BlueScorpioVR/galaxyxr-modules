#!/system/bin/sh
MODDIR=${0%/*}
. "$MODDIR/lib.sh"
touch "$MODDIR/disable"
rollback
