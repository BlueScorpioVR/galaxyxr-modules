#!/system/bin/sh
# One attach per SystemUI incarnation; never restart or kill Android services.
set -u
MODDIR=$(CDPATH= cd -P "${0%/*}" && pwd) || exit 1
STATE=/dev/gxr-window-curvature
LOG="$MODDIR/runtime.log"
INJECTOR="$MODDIR/bin/frida-inject"
umask 077
[ "$(id -u)" = 0 ] || { echo 'Root required.'; exit 1; }
allowed() { [ ! -f "$MODDIR/disable" ] && [ ! -f "$MODDIR/remove" ]; }
start_time() { sed 's/.*) //' "/proc/$1/stat" 2>/dev/null | awk '{print $20}'; }
identity() { printf '%s:%s:%s' "$(cat /proc/sys/kernel/random/boot_id)" "$1" "$(start_time "$1")"; }
fail() {
  : > "$MODDIR/disable"
  printf '%s\n' "$*" > "$MODDIR/failure"
  echo "DISABLED - $*"
  exit 1
}
owns_state() { [ -f "$STATE/module-path" ] && [ "$(cat "$STATE/module-path")" = "$MODDIR" ]; }
case "${1:-status}" in
status)
  if allowed; then echo 'KernelSU checkbox: ON'; else echo 'KernelSU checkbox: OFF'; fi
  if owns_state; then
    cat "$STATE/status" 2>/dev/null
    echo 'Runtime supervisor state is present; see runtime.log for per-window values.'
  else echo 'Runtime not running.'; fi
  [ ! -f "$MODDIR/failure" ] || cat "$MODDIR/failure"
  [ ! -f "$LOG" ] || tail -4 "$LOG"
  echo 'Enable/re-enable: turn checkbox on and reboot. No app curvature is saved across reboot.'
  if ! owns_state && [ ! -f "$MODDIR/session-open" ] && [ ! -f "$MODDIR/failure" ]; then
    echo 'GXR_UPDATE_STATE=STOCK'
  fi
  ;;
off)
  : > "$MODDIR/disable"
  # Supervisor notices the marker within one second and sends a graceful stop.
  n=0
  while owns_state && [ "$n" -lt 18 ]; do sleep 1; n=$((n + 1)); done
  if owns_state; then echo 'Stop remains pending; inspect runtime.log. Do not reattach.'; exit 1; fi
  if [ -f "$MODDIR/session-open" ] || [ -f "$MODDIR/failure" ]; then
    echo 'Restoration is unverified or quarantined; reboot disabled before reset.'
    exit 1
  fi
  echo 'Disabled. No automatic re-enable or Android service restart.'
  echo 'GXR_UPDATE_STATE=STOCK'
  ;;
reset)
  [ -f "$MODDIR/disable" ] || { echo 'Disable the module first.'; exit 1; }
  [ ! -d "$STATE" ] || { echo 'Runtime state remains; reboot first.'; exit 1; }
  previous=$(cat "$MODDIR/injected-identity" 2>/dev/null || true)
  boot=$(cat /proc/sys/kernel/random/boot_id)
  case "$previous" in "$boot":*) echo 'Reboot first; same-boot quarantine cannot be reset.'; exit 1 ;; esac
  # Preserve diagnostics without replaying stale FATAL/Error lines into the
  # installer's restoration-status parser after quarantine is acknowledged.
  if [ -f "$LOG" ]; then
    archived="$MODDIR/runtime.pre-reset.$(date +%s).$$.log"
    [ ! -e "$archived" ] && mv "$LOG" "$archived" || exit 1
  fi
  rm -f "$MODDIR/session-open" "$MODDIR/failure"
  echo 'Quarantine acknowledged. Module remains disabled; enable and reboot when ready.'
  ;;
run)
  [ "$(id -u)" = 0 ] || { echo 'Root required.'; exit 1; }
  allowed || exit 0
  maximum=${2:-0}
  case "$maximum" in ''|*[!0-9]*) fail 'Invalid optional test duration' ;; esac
  [ "$maximum" -eq 0 ] || { [ "$maximum" -ge 15 ] && [ "$maximum" -le 600 ]; } || fail 'Test duration must be 15..600 seconds'
  count=0
  until [ "$(getprop sys.boot_completed)" = 1 ]; do
    allowed || exit 0
    count=$((count + 1))
    [ "$count" -lt 90 ] || fail 'Boot wait expired; no attachment performed'
    sleep 2
  done
  [ "$(getprop ro.product.model)" = SM-I610 ] || fail 'Wrong device model'
  [ "$(getprop ro.build.fingerprint)" = 'samsung/xrvst2ue/xrvst2:14/UML2.260301.001/I610UEU2AZF3:user/release-keys' ] || fail 'Unsupported firmware fingerprint'
  (cd "$MODDIR" && sha256sum -c SHA256SUMS) >/dev/null 2>&1 || fail 'Module payload integrity check failed'
  sha256sum -c "$MODDIR/firmware.sha256" >/dev/null 2>&1 || fail 'Firmware APK/native hash mismatch'
  set -- $(pidof com.android.systemui)
  [ "$#" -eq 1 ] || fail 'Expected one SystemUI process'
  target=$1
  target_identity=$(identity "$target")
  [ -n "$(start_time "$target")" ] || fail 'Cannot identify SystemUI incarnation'
  [ "$(cat "$MODDIR/injected-identity" 2>/dev/null || true)" != "$target_identity" ] || fail 'Already attached to this SystemUI incarnation; reboot before re-enabling'
  [ ! -f "$MODDIR/session-open" ] || fail 'Previous session interrupted; reboot disabled, inspect logs, then use action.sh reset'
  mkdir "$STATE" 2>/dev/null || fail 'Another runtime or stale runtime state exists; do not retry'
  chmod 700 "$STATE"
  printf '%s\n' "$MODDIR" > "$STATE/module-path"
  printf '%s\n' "$target_identity" > "$STATE/target"
  printf '%s\n' "$$" > "$STATE/supervisor-pid"
  printf '%s\n' 'STARTING' > "$STATE/status"
  injector_pid=
  injector_start=
  graceful=0
  failed=0
  finish() {
    trap - EXIT INT TERM HUP
    if [ -n "$injector_pid" ]; then
      printf 'stop\n' >&3 2>/dev/null || true
      n=0
      while [ "$n" -lt 10 ]; do
        if grep -q '^GXR_CURVATURE_STOPPED ' "$LOG"; then graceful=1; break; fi
        kill -0 "$injector_pid" 2>/dev/null || break
        sleep 1
        n=$((n + 1))
      done
      if [ "$(start_time "$injector_pid")" = "$injector_start" ]; then
        kill -TERM "$injector_pid" 2>/dev/null || true
        sleep 2
        if [ "$(start_time "$injector_pid")" = "$injector_start" ]; then kill -KILL "$injector_pid" 2>/dev/null || true; fi
      fi
      wait "$injector_pid" 2>/dev/null || true
      exec 3>&-
    fi
    if [ "$graceful" -eq 1 ] && [ "$failed" -eq 0 ]; then
      rm -f "$MODDIR/session-open"
      echo 'STOPPED - agent confirmed all owned tasks flat; injector detached'
    elif [ "$graceful" -eq 1 ]; then
      : > "$MODDIR/disable"
      printf '%s\n' 'Unexpected runtime stop; flat restoration confirmed. Reboot disabled before reset.' > "$MODDIR/failure"
      echo 'DISABLED - unexpected runtime stop; flat restoration confirmed'
    else
      : > "$MODDIR/disable"
      printf '%s\n' 'Runtime interrupted or restoration unverified; Java heartbeat expiry remains active. Reboot disabled before reset.' > "$MODDIR/failure"
      echo 'DISABLED - restoration unverified; no automatic reattachment'
    fi
    if owns_state; then
      rm -f "$STATE/control" "$STATE/status" "$STATE/supervisor-pid" "$STATE/injector-pid" "$STATE/module-path" "$STATE/target"
      rmdir "$STATE" 2>/dev/null || true
    fi
  }
  trap finish EXIT
  trap 'failed=1; exit 1' INT TERM HUP
  mkfifo "$STATE/control" || fail 'Cannot create injector control pipe'
  exec 3<> "$STATE/control"
  : > "$LOG"
  printf '%s\n' "$target_identity" > "$MODDIR/injected-identity"
  printf '%s\n' "$target_identity" > "$MODDIR/session-open"
  "$INJECTOR" -p "$target" -s "$MODDIR/bin/agent.js" -R qjs -i < "$STATE/control" >> "$LOG" 2>&1 &
  injector_pid=$!
  injector_start=$(start_time "$injector_pid")
  printf '%s\n' "$injector_pid" > "$STATE/injector-pid"
  count=0
  ready=0
  while allowed; do
    if ! kill -0 "$injector_pid" 2>/dev/null || [ "$(identity "$target")" != "$target_identity" ]; then failed=1; break; fi
    if grep -q '^GXR_CURVATURE_FATAL ' "$LOG"; then failed=1; break; fi
    if grep -q '^GXR_CURVATURE_STOPPED ' "$LOG"; then failed=1; break; fi
    printf 'pulse\n' >&3 || { failed=1; break; }
    count=$((count + 1))
    if grep -q '^GXR_CURVATURE_READY ' "$LOG"; then
      ready=1
      printf '%s\n' 'RUNNING - supervised, independent Home Space windows' > "$STATE/status"
    elif [ "$ready" -eq 0 ] && [ "$count" -ge 25 ]; then failed=1; break; fi
    # Keep open injector stdout FD valid while bounding the mutable log size.
    if [ "$ready" -eq 1 ] && [ "$count" -gt 25 ] && [ "$(wc -c < "$LOG")" -gt 524288 ]; then
      tail -n 40 "$LOG" > "$LOG.trim"
      cat "$LOG.trim" > "$LOG"
      rm -f "$LOG.trim"
    fi
    [ "$maximum" -eq 0 ] || [ "$count" -lt "$maximum" ] || break
    sleep 1
  done
  ;;
*) echo 'Usage: action.sh status|off|reset; control.sh run [test-seconds]'; exit 1 ;;
esac
