#!/system/bin/sh
MODDIR=${0%/*}
touch "$MODDIR/disable"
# Nothing to restore: no settings, partitions or key layouts were modified.
