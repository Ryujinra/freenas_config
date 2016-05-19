#!/usr/local/bin/python2.7

import os
import sys
import subprocess
from pprint import pprint

if len(sys.argv) < 3:
    raise SystemExit('Usage: %s READ_SECS WRITE_SECS' % sys.argv[0])

read_secs, write_secs = (float(val) for val in sys.argv[1:3])

def get_disks():
    return subprocess.check_output(['/sbin/sysctl', '-n', 'kern.disks']).rstrip().split()

def set_scterc(disk, read_sec, write_sec):
    try:
        print subprocess.check_output(['/usr/local/sbin/smartctl',
                                       '-l',
                                       'scterc,%d,%d' % (read_sec*10, write_sec*10),
                                       '/dev/%s' % disk])
    except Exception as ex:
        print 'Failed to set TLER on /dev/%s' % disk

def get_disk_serial(disk):
    try:
        temp_line = subprocess.check_output("/usr/local/sbin/smartctl -i /dev/%s "
                                            "| grep -i 'Serial Number: '" % disk,
                                            shell=True)
        return disk, temp_line.strip().split()[-1]
    except:
        return disk, None

disks = get_disks()
disk_serials = dict(map(get_disk_serial, disks))

for disk in sorted(disks):
    print '%s-%s:' % (disk, disk_serials[disk])
    set_scterc(disk, read_secs, write_secs)
