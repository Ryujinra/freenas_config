#!/usr/local/bin/python2.7

import os
import sys
import subprocess
import time
import socket
from multiprocessing.pool import ThreadPool
from pprint import pprint

MAX_THREADS = 4

def to_float(temp):
    temp = temp.rstrip()
    return float(temp[:-1] if temp[-1].lower() == 'c' else temp)

def get_disks():
    return subprocess.check_output(['/sbin/sysctl', '-n', 'kern.disks']).rstrip().split()

def get_num_cpus():
    return int(subprocess.check_output(['/sbin/sysctl', '-n', 'hw.ncpu']))

def get_disk_serial(disk):
    try:
        temp_line = subprocess.check_output("/usr/local/sbin/smartctl -i /dev/%s "
                                            "| grep -i 'Serial Number: '" % disk,
                                            shell=True)
        return disk, temp_line.strip().split()[-1]
    except:
        return disk, None

def get_disk_temp(disk):
    try:
        temp_line = subprocess.check_output("/usr/local/sbin/smartctl -A /dev/%s "
                                            "| grep -i '194 *Temperature_'" % disk,
                                            shell=True)
        return disk, to_float(temp_line.strip().split()[9])
    except Exception as ex:
        return disk, None

def get_cpu_temp(cpu):
    return cpu, to_float(subprocess.check_output(['/sbin/sysctl', '-n',
                                                  'dev.cpu.%d.temperature' % cpu]))

disks = get_disks()
num_cpus = get_num_cpus()
pool = ThreadPool(min(len(disks), MAX_THREADS))
curr_time = time.time()

cpu_temps = [get_cpu_temp(cpu) for cpu in range(num_cpus)]
disk_serials = dict(pool.map(get_disk_serial, disks))
disk_temps = pool.map(get_disk_temp, disks)
disk_temps = [(disk_serials[disk], temp) for disk, temp in disk_temps]

hostname = socket.gethostname()

print os.linesep.join(['PUTVAL %s/cpu_temp/temperature-cpu%d %f:%f' %
                       (hostname, cpu, curr_time, temp)
                       for cpu, temp in cpu_temps])

print os.linesep.join(['PUTVAL %s/disk_temp/temperature-%s %f:%f' %
                       (hostname, disk, curr_time, temp)
                       for disk, temp in disk_temps if temp is not None])
