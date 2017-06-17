#!/usr/local/bin/python2.7

import os
import sys
import subprocess
import time
import socket
from pprint import pprint
from disks import get_disks_info, get_num_cpus, celsius_to_float

MAX_THREADS = 4

def get_cpu_temp(cpu):
    return cpu, celsius_to_float(subprocess.check_output(['/sbin/sysctl', '-n',
                                                          'dev.cpu.%d.temperature' % cpu]))

disks = get_disks_info()
num_cpus = get_num_cpus()
curr_time = time.time()

cpu_temps = [get_cpu_temp(cpu) for cpu in range(num_cpus)]
disk_temps = [(values['serial'].replace(' ', '_'), values['temp_c'])
              for values in disks.values() if values['status'] == 0]

hostname = socket.gethostname()

print os.linesep.join(['PUTVAL %s/cpu_temp-%d/temperature %f:%f' %
                       (hostname, cpu, curr_time, temp)
                       for cpu, temp in cpu_temps])

print os.linesep.join(['PUTVAL %s/disk_temp-%s/temperature %f:%f' %
                       (hostname, disk, curr_time, temp)
                       for disk, temp in disk_temps if temp is not None])
