#!/bin/sh

set -eu
export DISPLAY=:40
rm -f "/tmp/.X${DISPLAY#:}-lock"
nohup Xvfb "$DISPLAY" -ac &
sleep 1

eval "$(dbus-launch --sh-syntax)"
socket="${DBUS_SESSION_BUS_ADDRESS#unix:path=}"
socket="${socket%%,*}"
ln -sf "$socket" /run/dbus/system_bus_socket
sleep 1

set +eu
mkdocs "$@"
