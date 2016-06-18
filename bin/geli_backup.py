#!/usr/local/bin/python2.7

import os
import sys
import subprocess
from pprint import pprint
from disks import get_disks

MAX_THREADS = 4

if len(sys.argv) < 2:
    raise SystemExit('Usage: %s OUTPUT_DIR' % sys.argv[0])

out_dir = sys.argv[1]

def backup_geli_metadata(disk, serial):
    try:
        subprocess.check_output(['geli', 'backup', '/dev/%sp2' % disk,
                                 '%s' % os.path.join(out_dir, 'geli_%s.meta' % serial)])
    except:
        try:
            subprocess.check_output(['geli', 'backup', '/dev/%sp1' % disk,
                                     '%s' % os.path.join(out_dir, 'geli_%s.meta' % serial)])
        except:
            pass

disks = get_disks()
_ = [backup_geli_metadata(disk, serial) for disk, serial in disks.iteritems()]
