#!/system/bin/sh
MODDIR=${0%/*}
. "$MODDIR/lib.sh"
enabled || exit 0
compatible || exit 1
init_state
# KernelSU supervises this foreground worker and prevents duplicate service trees.
while enabled && [ "$(getprop sys.boot_completed)" != 1 ]; do sleep 2; done
enabled || exit 0
prepare_ncm || exit 1
if [ "$(mount_record)" != "$(our_mount_root)" ]; then
  log 'AOA overlay absent: enable module, then use KernelSU soft restart (post-fs-data runs before Android starts)'
fi
select_ncm || { log 'ERROR: selecting NCM failed'; exit 1; }
while enabled; do sleep 3; done
log 'Module disabled/removed: restoring owned runtime changes'
rollback
