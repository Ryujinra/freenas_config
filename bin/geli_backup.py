#!/usr/local/bin/python2.7

import os
import sys
import subprocess
from multiprocessing.pool import ThreadPool
from pprint import pprint

MAX_THREADS = 4

if len(sys.argv) < 2:
    raise SystemExit('Usage: %s OUTPUT_DIR' % sys.argv[0])

out_dir = sys.argv[1]

def get_disks():
    return subprocess.check_output(['/sbin/sysctl', '-n', 'kern.disks']).rstrip().split()

def get_disk_serial(disk):
    try:
        temp_line = subprocess.check_output("/usr/local/sbin/smartctl -i /dev/%s "
                                            "| grep -i 'Serial Number: '" % disk,
                                            shell=True)
        return disk, temp_line.strip().split()[-1]
    except:
        return disk, None

def backup_geli_metadata(disk):
    try:
        subprocess.check_output(['geli', 'backup', '/dev/%sp2' % disk,
                                 '%s' % os.path.join(out_dir, 'geli_%s.meta' % disk_serials[disk])])
    except:
        try:
            subprocess.check_output(['geli', 'backup', '/dev/%sp1' % disk,
                                     '%s' % os.path.join(out_dir, 'geli_%s.meta' % disk_serials[disk])])
        except:
            pass

disks = get_disks()

pool = ThreadPool(min(len(disks), MAX_THREADS))
disk_serials = dict(pool.map(get_disk_serial, disks))

_ = [backup_geli_metadata(disk) for disk in disks]
