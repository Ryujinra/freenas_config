#!/usr/local/bin/python2.7

from pprint import pprint
from disks import get_disks

SERIALS = set(['PK2234P9JT4Y5Y',])

disks = ['/dev/%s' % disk for disk, serial in get_disks().iteritems() if serial in SERIALS]
pprint(disks)

#camcontrol standby /dev/ada5 -t 300
