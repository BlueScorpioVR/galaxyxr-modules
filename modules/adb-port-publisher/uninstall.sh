#!/system/bin/sh
MODDIR=${0%/*}
touch "$MODDIR/disable"
# The publisher changes no system state, so nothing needs restoring. The
# configuration, state and log live outside the module and are intentionally
# left in place; remove /data/adb/xr-adb-port.* to delete them.
