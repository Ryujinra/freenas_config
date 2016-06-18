#!/usr/local/bin/python2.7

import os
import sys
import subprocess
from pprint import pprint
from disks import get_disks

if len(sys.argv) < 3:
    raise SystemExit('Usage: %s READ_SECS WRITE_SECS' % sys.argv[0])

read_secs, write_secs = (float(val) for val in sys.argv[1:3])

def set_scterc(disk, read_sec, write_sec):
    try:
        print subprocess.check_output(['/usr/local/sbin/smartctl',
                                       '-l',
                                       'scterc,%d,%d' % (read_sec*10, write_sec*10),
                                       '/dev/%s' % disk])
    except Exception as ex:
        print 'Failed to set TLER on /dev/%s' % disk

disks = get_disks()

for disk in sorted(disks.keys()):
    print '%s (%s):' % (disk, disks[disk])
    set_scterc(disk, read_secs, write_secs)
