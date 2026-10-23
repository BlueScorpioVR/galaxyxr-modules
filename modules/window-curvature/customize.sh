#!/system/bin/sh
[ "$BOOTMODE" = true ] || abort 'Install from the running KernelSU Manager, not recovery.'
[ "$ARCH" = arm64 ] || abort 'Android arm64 is required.'
[ "$(getprop ro.product.model)" = SM-I610 ] || abort 'This build is for Galaxy XR SM-I610 only.'
ui_print 'Experimental Home Space curvature; installing DISABLED.'
ui_print 'Enable in KernelSU and reboot when ready. No interface restart is performed.'
set_perm_recursive "$MODPATH" 0 0 0755 0644
set_perm "$MODPATH/bin/frida-inject" 0 0 0755
for script in service.sh action.sh auto.sh control.sh uninstall.sh; do
  set_perm "$MODPATH/$script" 0 0 0755
done
: > "$MODPATH/disable"
: > "$MODPATH/skip_mount"
