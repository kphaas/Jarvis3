#!/bin/zsh
set -euo pipefail

MP="$HOME/jarvis_mounts/Documents"
SHARE="//jarvisbrain@192.168.30.10/Documents"

mkdir -p "$MP"

if mount | grep -q " on ${MP} "; then
  exit 0
fi

mount_smbfs -N -o ro,noperm,nobrowse "$SHARE" "$MP"
