#!/bin/sh
set -eu

PUID="${PUID:-1000}"
PGID="${PGID:-1000}"

case "$PUID:$PGID" in
    *[!0-9:]*|:*|*:|*:*:*)
        echo "PUID and PGID must be positive numeric identifiers" >&2
        exit 64
        ;;
esac

if [ "$PUID" -eq 0 ] || [ "$PGID" -eq 0 ]; then
    echo "PUID and PGID must not run House Brain as root" >&2
    exit 64
fi

target_has_config_access() {
    gosu "$PUID:$PGID" sh -c '
        test -r /config && test -w /config && test -x /config || exit 1
        for path in \
            /config/autonomy.yaml \
            /config/house_brain.db \
            /config/autonomy-backups
        do
            test ! -e "$path" || {
                test -r "$path" && test -w "$path" || exit 1
                test ! -d "$path" || test -x "$path" || exit 1
            }
        done
    '
}

if [ "$(id -u)" -eq 0 ]; then
    mkdir -p /config
    if target_has_config_access; then
        exec gosu "$PUID:$PGID" "$@"
    fi
    if ! chown -R "$PUID:$PGID" /config; then
        echo "Cannot prepare /config for PUID:PGID ($PUID:$PGID)." >&2
        echo "Set the bind mount owner on the host or choose matching identifiers." >&2
        exit 77
    fi
    if ! target_has_config_access; then
        echo "/config is not readable and writable by PUID:PGID ($PUID:$PGID)." >&2
        exit 77
    fi
    exec gosu "$PUID:$PGID" "$@"
fi

if [ "$(id -u)" -ne "$PUID" ] || [ "$(id -g)" -ne "$PGID" ]; then
    echo "Container user does not match PUID:PGID ($PUID:$PGID)" >&2
    exit 77
fi

exec "$@"
