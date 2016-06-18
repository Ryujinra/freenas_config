import os
import sys
import subprocess
import time
import socket
from multiprocessing.pool import ThreadPool
from pprint import pprint

MAX_THREADS = 4

def get_disk_devs():
    return subprocess.check_output(['/sbin/sysctl', '-n', 'kern.disks']).rstrip().split()

def get_disk_serial(disk):
    try:
        temp_line = subprocess.check_output("/usr/local/sbin/smartctl -i /dev/%s "
                                            "| grep -i 'Serial Number: '" % disk,
                                            shell=True)
        return disk, temp_line.strip().split()[-1]
    except:
        return disk, None

def get_disks():
  disks = get_disk_devs()
  pool = ThreadPool(min(len(disks), MAX_THREADS))
  return dict(pool.map(get_disk_serial, disks))
