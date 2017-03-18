import os
import sys
import subprocess
import time
import socket
import re
from multiprocessing.pool import ThreadPool
from pprint import pprint

NCPU_CMD = '/sbin/sysctl -n hw.ncpu'

def get_num_cpus():
    return int(subprocess.check_output(NCPU_CMD.split()))

SMARTCTL = '/usr/local/sbin/smartctl'
TEMP_CMD = "{smartctl} -n standby -A /dev/{dev} | grep -i '194 *Temperature_'"
SERIAL_CMD = "{smartctl} -i /dev/{dev} | grep -i 'Serial Number: '"
DEVS_CMD = '/sbin/sysctl -n kern.disks'
POOL = ThreadPool(1)#get_num_cpus())

def to_float(temp):
    temp = temp.rstrip()
    return float(temp[:-1] if temp[-1].lower() == 'c' else temp)

def get_disk_devs(match=''):
    match_re = re.compile(match)
    return [dev for dev in subprocess.check_output(DEVS_CMD.split()).rstrip().split()
            if match_re.match(dev)]

def get_disk_serial(dev):
    try:
        temp_line = subprocess.check_output(SERIAL_CMD.format(smartctl=SMARTCTL, dev=dev),
                                            shell=True)
        return dev, temp_line.strip().split()[-1]
    except:
        return dev, None

def get_disks():
    disks = get_disk_devs()
    return dict(POOL.map(get_disk_serial, disks))

def get_disk_temp(dev):
    try:
        result = subprocess.Popen(TEMP_CMD.format(smartctl=SMARTCTL, dev=dev),
                                  stdout=subprocess.PIPE, shell=True)
    except subprocess.CalledProcessError as err:
        return dev, None, err.returncode
    try:
        out_line = result.communicate()[0]
        return dev, to_float(out_line.strip().split()[9]), result.returncode
    except Exception as ex:
        return dev, None, result.returncode

def get_disks_info(match=''):
    serials = dict(POOL.map(get_disk_serial, get_disk_devs(match)))
    disk_temps = POOL.map(get_disk_temp, serials.keys())
    return dict((dev, {'temp_c': temp, 'status': status, 'serial': serials[dev]})
                for dev, temp, status in disk_temps)

if __name__ == '__main__':
    pprint(get_disks())
    pprint(get_disks_info())
