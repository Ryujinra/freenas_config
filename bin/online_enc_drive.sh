#!/bin/sh

# $1 = path to encryption key
# $2 = uuid of drive

echo "geli attach -p -k $1 /dev/gptid/$2 && zpool online zfs gptid/$2.eli"
