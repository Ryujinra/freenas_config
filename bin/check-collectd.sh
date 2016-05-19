#!/bin/bash

# Set the file path and the line I want to add
conf=/etc/local/collectd.conf
inc='Include "/root/config/collectd/*.conf"'

# Fail if I'm not running as root
if (( EUID ))
then
    echo "ERROR: Must be run as root. Exiting." >&2
    exit 1
fi

# Check to see if the line is in the config file
if grep -q Include $conf
then
    : All good, exit quietly.
else
    : Missing the include line! Add it!
    echo "$inc" >> $conf
    service collectd restart
    logger -p user.warn -t "collectd" \
         "Added Include line to collectd.conf and restarted."
    echo "Added include to collectd.conf" | \
         mail -s "Collectd fixed on NAS" fhriley@gmail.com 
fi
