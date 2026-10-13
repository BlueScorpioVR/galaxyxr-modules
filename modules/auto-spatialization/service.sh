#!/system/bin/sh
MODDIR=${0%/*}
exec sh "$MODDIR/auto.sh" apply
