#!/system/bin/sh
exec sh "${0%/*}/control.sh" "${1:-status}"
