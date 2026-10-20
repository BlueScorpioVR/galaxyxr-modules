#!/system/bin/sh
MODDIR=${0%/*}
. "$MODDIR/lib.sh"
case "${1:-status}" in
  status|report) status ;;
  off) touch "$MODDIR/disable"; rollback ;;
  *) echo 'Usage: action.sh [status|off]'; exit 1 ;;
esac
