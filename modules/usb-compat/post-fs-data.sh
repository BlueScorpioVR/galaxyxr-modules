#!/system/bin/sh
MODDIR=${0%/*}
. "$MODDIR/lib.sh"
enabled || exit 0
init_state
apply_aoa || { log 'ERROR: AOA preparation failed'; exit 1; }
prepare_ncm || { log 'ERROR: NCM preparation failed'; exit 1; }
