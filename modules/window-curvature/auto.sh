#!/system/bin/sh
case "${1:-status}" in
apply) exec sh "${0%/*}/service.sh" ;;
*) exec sh "${0%/*}/control.sh" "${1:-status}" ;;
esac
