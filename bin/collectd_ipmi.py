#!/usr/local/bin/python2.7

import os
import subprocess
import csv
import time
import socket
from cStringIO import StringIO
from pprint import pprint

TYPES = {
    'volts': (float, 'power'),
    'rpm': (int, 'fanspeed'),
    'degrees c': (float, 'temperature'),
    }

def get_data():
    out = subprocess.check_output(['/usr/local/bin/ipmitool', '-c', 'sdr', 'list', 'full'])
    csv_data = StringIO(out)
    reader = csv.reader(csv_data)
    return ((name.replace(' ', '_'), TYPES[typ.lower()][0](value), TYPES[typ.lower()][1])
            for name, value, typ, status in reader
            if status.lower() == 'ok' and typ.lower() in TYPES)


data = get_data()
#pprint(list(data))

print os.linesep.join(['PUTVAL %s/ipmi/%s-%s %f:%f' %
                       (socket.gethostname(), type, name, time.time(), value)
                       for name, value, type in data])
