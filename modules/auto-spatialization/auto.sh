#!/system/bin/sh
set -eu
MODDIR=${0%/*}
KEY=auto_spatialization_settings
ORIGINAL="$MODDIR/original-value"
LOG="$MODDIR/startup.log"
LOCK="$MODDIR/.settings-lock"
read_value() { settings --user 0 get system "$KEY"; }
valid_value() {
  case "$1" in null|0|1) return 0 ;; *) return 1 ;; esac
}
log() { printf '%s\n' "$*" > "$LOG"; }
lock() {
  tries=0
  until mkdir "$LOCK" 2>/dev/null; do
    tries=$((tries + 1))
    [ "$tries" -lt 10 ] || { echo 'Error: settings operation busy; inspect .settings-lock'; exit 1; }
    sleep 1
  done
  trap 'rmdir "$LOCK"' EXIT
}
case "${1:-status}" in
apply)
  tries=0
  until [ "$(getprop sys.boot_completed)" = 1 ]; do
    [ ! -f "$MODDIR/disable" ] && [ ! -f "$MODDIR/remove" ] || exit 0
    tries=$((tries + 1))
    [ "$tries" -lt 60 ] || { log 'Error: boot wait expired; no setting changed'; exit 1; }
    sleep 2
  done
  lock
  [ ! -f "$MODDIR/disable" ] && [ ! -f "$MODDIR/remove" ] || exit 0
  current=$(read_value)
  valid_value "$current" || { log 'Error: unexpected preference value; refused'; exit 1; }
  if [ ! -f "$ORIGINAL" ]; then
    printf '%s\n' "$current" > "$ORIGINAL.tmp"
    chmod 600 "$ORIGINAL.tmp"
    mv "$ORIGINAL.tmp" "$ORIGINAL"
  else
    valid_value "$(cat "$ORIGINAL")" || { log 'Error: invalid recovery record'; exit 1; }
  fi
  settings --user 0 put system "$KEY" 1
  [ "$(read_value)" = 1 ] || { log 'Error: preference readback failed'; exit 1; }
  log 'Preference set to 1 at service startup; thermal/window policies unchanged'
  echo 'Preference ON; physical spatialization not verified'
  ;;
off)
  : > "$MODDIR/disable"
  lock
  if [ -f "$ORIGINAL" ]; then
    original=$(cat "$ORIGINAL")
    valid_value "$original" || { echo 'Error: invalid recovery record'; exit 1; }
    current=$(read_value)
    if [ "$current" = 1 ]; then
      if [ "$original" = null ]; then
        settings --user 0 delete system "$KEY" >/dev/null
      else
        settings --user 0 put system "$KEY" "$original"
      fi
      [ "$(read_value)" = "$original" ] || { echo 'Error: restoration readback failed'; exit 1; }
    fi
    rm "$ORIGINAL"
  fi
  log 'Disabled; original preference restored or later user choice preserved'
  echo 'GXR_UPDATE_STATE=STOCK'
  ;;
status)
  if [ -f "$MODDIR/disable" ]; then echo 'Module preference OFF'; else echo 'Module preference ON'; fi
  printf 'Labs preference: %s\n' "$(read_value)"
  [ ! -f "$LOG" ] || cat "$LOG"
  if [ -f "$ORIGINAL" ]; then
    printf 'Saved original: %s\n' "$(cat "$ORIGINAL")"
    echo 'Recovery record present; use action.sh off before replacement/removal'
  elif [ ! -d "$LOCK" ]; then
    echo 'GXR_UPDATE_STATE=STOCK'
  else
    echo 'Error: settings operation in progress'; exit 1
  fi
  ;;
*) echo 'Error: unsupported operation'; exit 1 ;;
esac
