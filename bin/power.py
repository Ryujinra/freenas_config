#!/usr/local/bin/python2.7

import os
import sys
import subprocess
import time
import socket

UPS = 'ups@localhost'

def get_real_power(ups):
    try:
        temp_line = subprocess.check_output('/usr/local/bin/upsc %s '
                                            '| grep \\.realpower' % ups,
                                            shell=True)
        return float(temp_line.strip().split(':')[-1])
    except:
        return None

print ('PUTVAL %s/ups_power/power %f:%f' %
       (socket.gethostname(), time.time(), get_real_power(UPS)))
