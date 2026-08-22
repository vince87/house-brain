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

if [ "$(id -u)" -eq 0 ]; then
    mkdir -p /config
    chown -R "$PUID:$PGID" /config
    exec gosu "$PUID:$PGID" "$@"
fi

if [ "$(id -u)" -ne "$PUID" ] || [ "$(id -g)" -ne "$PGID" ]; then
    echo "Container user does not match PUID:PGID ($PUID:$PGID)" >&2
    exit 77
fi

exec "$@"
