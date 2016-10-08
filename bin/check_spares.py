#!/usr/local/bin/python2.7

import argparse
import subprocess
from pprint import pprint
from disks import get_disks

TIMEOUT = 10 # minutes
CAMCONTROL = '/sbin/camcontrol'

# PK2234P9JT4Y5Y

parser = argparse.ArgumentParser(description='Run badblocks and smart tests on spares')
parser.add_argument('spares', metavar='SERIAL', nargs='+',
                    help='the serial number of a spare')

args = parser.parse_args()
spares = set(args.spares)

disks = [disk for disk, serial in get_disks().iteritems() if serial in spares]

procs = [(subprocess.Popen(['smartctl', '-n', 'standby', '-a', '/dev/%s' % disk],
                           stdout=subprocess.PIPE), disk)
         for disk in disks]

for proc, disk in procs:
    out = proc.communicate()[0].strip()
    #print proc.returncode
    #print out.split('\n')[-1].lower()
    if (not (proc.returncode & 0x2) or
        not out.split('\n')[-1].lower().startswith('device is in standby mode')):
        subprocess.check_call([CAMCONTROL, 'standby', '/dev/%s' % disk,
                              '-t', str(TIMEOUT)])
        print '/dev/%s put in STANDBY' % disk
