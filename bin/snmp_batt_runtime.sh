#!/bin/sh

if [ "$1" = "-g" ]
then
    echo .1.3.6.1.2.1.25.1.21
    echo gauge
    /usr/local/bin/upsc ups@localhost battery.runtime
fi
exit 0
