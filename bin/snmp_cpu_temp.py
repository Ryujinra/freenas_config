#!/usr/local/bin/python3

import sys
import subprocess
import re

# pass .1.3.6.1.2.1.25.1.8 /data/config/bin/snmp_cpu0_temp.sh
# pass .1.3.6.1.2.1.25.1.10 /data/config/bin/snmp_cpu2_temp.sh

arg0 = sys.argv[1]
if arg0 in ('-g'):
    oid = sys.argv[2].strip()
    if oid.replace('.1.3.6.1.2.1.25.1.8', ''):
        which = 4 - int(oid.split('.')[-1])
        out = subprocess.check_output(['/sbin/sysctl', 'dev.cpu'])
        vals = dict((int(key), val) for key, val in re.findall(b'dev\.cpu\.(\d+)\.temperature: (\S+)C', out))

        print(oid)
        print('gauge')
        print(int(float(vals[which]) * 10))
