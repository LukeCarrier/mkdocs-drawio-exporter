#!/bin/sh

set -eux -o pipefail

apt-get update
apt-get install -y curl
curl -L -o drawio.deb "https://github.com/jgraph/drawio-desktop/releases/download/v${drawio_version}/drawio-${TARGETARCH}-${drawio_version}.deb"
apt-get install -y dbus dbus-x11 libasound2 xvfb ./drawio.deb
apt-get purge -y curl
rm -rf drawio.deb /var/lib/apt/lists

pip install --upgrade pip
pip install -r requirements.txt

install -d -m 1777 /tmp/.X11-unix
