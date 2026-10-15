#!/system/bin/sh
# No product-ID restriction: verify Bluetooth + Microsoft + Xbox name instead.
is_xbox() {
    [ "$(cat "$1/device/id/bustype" 2>/dev/null)" = 0005 ] || return 1
    [ "$(cat "$1/device/id/vendor" 2>/dev/null)" = 045e ] || return 1
    case "$(cat "$1/device/name" 2>/dev/null)" in
        Xbox*Controller*|Xbox*Gamepad*|XBOX*Controller*|XBOX*Gamepad*) ;;
        *) return 1 ;;
    esac
    case "${1##*/}" in event*[!0-9]*) return 1 ;; event[0-9]*) ;; *) return 1 ;; esac
}

release_unknown() {
    is_xbox "$1" || return 1
    identity=$(readlink -f "$1/device") || return 1
    [ -n "$identity" ] || return 1
    node="/dev/input/${1##*/}"
    # -p reports current pressed keys with '*'. Match one exact hexadecimal token.
    getevent -p "$node" 2>/dev/null | grep -Eq '(^|[[:space:]])00f0\*([[:space:]]|$)' || return 1
    # Revalidate after querying: do not inject into a reused non-Xbox event node.
    is_xbox "$1" || return 1
    [ "$(readlink -f "$1/device")" = "$identity" ] || return 1
    sendevent "$node" 1 240 0 || return 1
    sendevent "$node" 0 0 0 || return 1
}

scan_once() {
    # Keep only connected identities; bounded memory and reconnects stay eligible.
    connected='|'
    for event in "$1"/event*; do
        is_xbox "$event" || continue
        identity=$(readlink -f "$event/device") || continue
        case "$seen" in
            *"|$identity|"*) connected="$connected$identity|"; continue ;;
        esac
        if release_unknown "$event"; then
            connected="$connected$identity|"
            printf '%s released KEY_UNKNOWN on %s (%s)\n' "$(date +%s)" "${event##*/}" "$(cat "$event/device/id/product")" >> "$MODDIR/status.log"
        fi
    done
    seen=$connected
}
