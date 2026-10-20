#!/system/bin/sh
# Sourced by module scripts; MODDIR must be set by the caller.
STATE=/dev/gxr_usb_compat
TARGET=/system/etc/permissions/com.android.future.usb.accessory.xml
ORIGINAL_SHA=2b0a703e3ca1f8fcf94edd44c5071320103b8ea951002b7b7d560496eecd1ad3
GADGET=/config/usb_gadget/g1
init_state() { mkdir -p "$STATE"; chmod 700 "$STATE"; }
log() {
  init_state
  [ "$(stat -c %s "$STATE/log" 2>/dev/null || echo 0)" -lt 65536 ] || tail -n 100 "$STATE/log" > "$STATE/log.next"
  [ ! -f "$STATE/log.next" ] || mv "$STATE/log.next" "$STATE/log"
  echo "$(date '+%F %T') $*" >> "$STATE/log"
}
enabled() { [ ! -e "$MODDIR/disable" ] && [ ! -e "$MODDIR/remove" ]; }
compatible() {
  [ "$(getprop ro.product.model)" = SM-I610 ] &&
  [ "$(getprop ro.build.display.id)" = UML2.260301.001.I610UEU2AZF3 ] &&
  [ -d "$GADGET/functions/accessory.gs2" ] &&
  [ -c /dev/usb_accessory ]
}
mount_record() {
  awk -v p="$TARGET" '$5 == p {print $4}' /proc/1/mountinfo
}
our_mount_root() { echo "/adb/modules/$(basename "$MODDIR")/aoa.xml"; }
apply_aoa() {
  compatible || { log 'ERROR: unsupported model, firmware or accessory driver'; return 1; }
  record=$(mount_record)
  if [ -n "$record" ]; then
    [ "$record" = "$(our_mount_root)" ] || { log 'ERROR: foreign accessory overlay; refusing to stack mounts'; return 1; }
    log 'AOA overlay already present'
    return 0
  fi
  # Validate the original as seen by init, not only this shell namespace.
  sum=$(nsenter --mount=/proc/1/ns/mnt -- sha256sum "$TARGET") || return 1
  [ "${sum%% *}" = "$ORIGINAL_SHA" ] || { log 'ERROR: original accessory XML hash mismatch'; return 1; }
  chcon u:object_r:system_file:s0 "$MODDIR/aoa.xml" || return 1
  nsenter --mount=/proc/1/ns/mnt -- mount --bind "$MODDIR/aoa.xml" "$TARGET" || return 1
  [ "$(mount_record)" = "$(our_mount_root)" ] || { log 'ERROR: overlay mount not verified'; return 1; }
  log 'AOA feature overlay mounted in init namespace; framework must start after this step'
}
prepare_ncm() {
  compatible || return 1
  [ -d "$GADGET/functions/ncm.gs6" ] || { log 'ERROR: expected Samsung NCM driver missing'; return 1; }
  if [ ! -d "$GADGET/functions/ncm.0" ]; then
    mkdir "$GADGET/functions/ncm.0" || return 1
    : > "$STATE/created-ncm"
    log 'Created ncm.0 for the existing Samsung init USB rules'
  fi
}
select_ncm() {
  # Never displace a host-initiated accessory handshake or another explicit mode.
  current=$(svc usb getFunctions 2>&1) || return 1
  case "$current" in
    ncm) log 'NCM already selected'; return 0 ;;
    mtp|none|'') ;;
    *) log "Leaving active USB mode unchanged: $current"; return 0 ;;
  esac
  [ -f "$STATE/prior-functions" ] || printf '%s\n' "$current" > "$STATE/prior-functions"
  : > "$STATE/selected-ncm"
  log 'Requesting temporary NCM via Android USB service; ADB may restart/change port'
  svc usb setFunctions ncm
}
rollback() {
  init_state
  rc=0
  if [ "$(mount_record)" = "$(our_mount_root)" ]; then
    nsenter --mount=/proc/1/ns/mnt -- umount "$TARGET" || rc=1
    log 'AOA overlay removal requested; cached Android feature requires another soft restart to clear'
  fi
  if [ -f "$STATE/selected-ncm" ] && [ "$(svc usb getFunctions 2>&1)" = ncm ]; then
    prior=$(cat "$STATE/prior-functions" 2>/dev/null)
    case "$prior" in
      mtp) svc usb setFunctions mtp || rc=1 ;;
      none|'') svc usb setFunctions || rc=1 ;;
      *) log 'ERROR: invalid previous USB mode; leaving mode untouched'; rc=1 ;;
    esac
  fi
  if [ -f "$STATE/created-ncm" ]; then
    # rmdir cannot remove a bound/in-use configfs function; never remove symlinks.
    if rmdir "$GADGET/functions/ncm.0" 2>/dev/null; then rm -f "$STATE/created-ncm"; fi
  fi
  if [ "$rc" = 0 ]; then rm -f "$STATE/selected-ncm" "$STATE/prior-functions"; fi
  return "$rc"
}
status() {
  if enabled; then echo 'KernelSU preference: ON'; else echo 'KernelSU preference: OFF'; fi
  echo "Android accessory feature: $(pm has-feature android.hardware.usb.accessory)"
  echo "Accessory overlay mount: $(mount_record)"
  echo "USB requested functions: $(svc usb getFunctions 2>&1)"
  echo "USB state: $(getprop sys.usb.state)"
  echo 'Bound gadget functions:'
  ls -l "$GADGET/configs/b.1" 2>/dev/null
  if [ -d "$GADGET/functions/ncm.0" ]; then
    echo "NCM interface: $(cat "$GADGET/functions/ncm.0/ifname")"
  fi
  echo 'Network interfaces (no IP/DHCP is configured by this module):'
  ip -br addr | grep -E '^usb[0-9]+ ' || true
  echo 'Recent module log:'
  tail -n 12 "$STATE/log" 2>/dev/null || true
  echo 'Action is report-only. Test NCM traffic and AOA with real USB hosts.'
}
