#!/bin/sh

set -eux -o pipefail

if [ "$mkdocs_gid" != "0" ]; then
    conflicting_group="$( (getent group "$mkdocs_gid" || true) | cut -d: -f1)"
    if [ -n "$conflicting_group" ]; then
        echo "$0: removing existing group $conflicting_group with gid $mkdocs_gid" >&2
        groupdel "$conflicting_group"
    fi
    groupadd -g "$mkdocs_gid" mkdocs
fi

if [ "$mkdocs_uid" != "0" ]; then
    conflicting_user="$( (getent passwd "$mkdocs_uid" || true) | cut -d: -f1)"
    if [ -n "$conflicting_user" ]; then
        echo "$0: removing existing user $conflicting_user with uid $mkdocs_uid" >&2
        userdel "$conflicting_user"
    fi
    useradd -u "$mkdocs_uid" -g mkdocs -m mkdocs
fi

install -d /run/dbus -m 777
