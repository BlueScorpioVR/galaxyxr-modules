#!/system/bin/sh
MODDIR=${0%/*}
case "${1:-status}" in
  off) exec sh "$MODDIR/auto.sh" off ;;
  status|report) exec sh "$MODDIR/auto.sh" status ;;
  *) echo 'Error: expected status, report or off'; exit 1 ;;
esac
