#!/usr/local/bin/python3

import re
import subprocess
import sys
import argparse
import socket
import os
from datetime import datetime
from pprint import pprint
import logging
import logging.handlers
import requests

LOG_DIR = '/var/log'
SCAN_CMD = 'smartctl --scan'
CMD = 'smartctl --info --attributes --health --format=brief %s'
sata_re = re.compile(b'^SATA (\d\.\d), (\d\.\d) Gb/s \(current: (\d.\d) Gb/s\)$')

def get_logger(name, filename):
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    handler = logging.handlers.RotatingFileHandler(os.path.join(LOG_DIR, filename),
                                                   maxBytes=1024*1024, backupCount=5)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    #console = logging.StreamHandler()
    #console.setLevel(logging.DEBUG)
    #console.setFormatter(formatter)
    #logger.addHandler(console)
    return logger

def parse_smart(hostname, device, output):
    info, data = output.strip().split(b'=== START OF READ SMART DATA SECTION ===')
    data = data.strip()
    info = info.strip().split(b'=== START OF INFORMATION SECTION ===')[-1].strip()

    info = dict(line.strip().split(b':', 1) for line in info.split(b'\n'))
    info = dict((key.strip(), val.strip()) for key, val in info.items())
    sata = sata_re.match(info[b'SATA Version is']).groups()
    if info[b'Rotation Rate'].lower() == b'solid state device':
        rpm = 0
        is_ssd = True
    else:
        rpm = int(info[b'Rotation Rate'].split()[0])
        is_ssd = False
    info = {
        'device': device,
        'host': hostname,
        'model': info[b'Device Model'].decode('utf-8'),
        'family': info[b'Model Family'].decode('utf-8'),
        'serial_number': info[b'Serial Number'].decode('utf-8'),
        'capacity': int(info[b'User Capacity'].split()[0].replace(b',', b'')),
        'enabled': info[b'SMART support is'].lower() == b'enabled',
        'rpm': rpm,

        'sata_speed': float(sata[1]),
        'sata_current_speed': float(sata[2]),
        'sata_version': sata[0],
        'is_ssd': is_ssd,
    }
    wwn = info.get(b'LU WWN Device Id')
    if wwn:
       info['wwn']: wwn.replace(b' ', b'')
    attributes = {}
    data = data.split(b'\n')
    info['health_ok'] = data[0].split(b': ')[-1].lower() == b'passed'

    for row in data[5:]:
        values = row.strip().split()
        try:
            id = int(values[0])
        except:
            break
        attributes[values[1]] = {
            'id': id,
            'flags': values[2],
            'value': int(values[3]),
            'worst': int(values[4]),
            'threshold': int(values[5]),
            'fail': values[6],
        }
        try:
            attributes[values[1]]['raw_value'] = int(values[7].split()[0])
        except:
            pass
    #pprint(info)
    #pprint(data)
    #pprint(attributes)
    return info, attributes

def create_influx_str(ts, info, attributes):
    tags = ['%s=%s' % (key, info[key].replace(' ', r'\ '))
            for key in ('host', 'device', 'model', 'family', 'serial_number')]
    tags.extend(['%s=%d' % (key, info[key]) for key in ('enabled', 'is_ssd', 'capacity', 'rpm')])
    tags = ','.join(tags)
    if not info['is_ssd']:
        fields = ('health_ok=%d,read_error_rate=%d,realloc_sector_cnt=%d,seek_error_rate=%d,'
                  'spin_retry_cnt=%d,power_on_hours=%d,udma_crc_error_cnt=%d') % (info['health_ok'],
                  attributes[b'Raw_Read_Error_Rate']['raw_value'],
                  attributes[b'Reallocated_Sector_Ct']['raw_value'],
                  attributes[b'Seek_Error_Rate']['raw_value'],
                  attributes[b'Spin_Retry_Count']['raw_value'],
                  attributes[b'Power_On_Hours']['raw_value'],
                  attributes[b'UDMA_CRC_Error_Count']['raw_value'])
        tag_fields = ['%s="%s"' % (key, info[key])
            for key in ('host', 'device', 'model', 'family', 'serial_number')]
        tag_fields.extend(['%s=%d' % (key, info[key]) for key in ('enabled', 'is_ssd', 'capacity', 'rpm')])
        fields += ',' + ','.join(tag_fields)
    else:
        raise Exception('SSDs not implemented')
    return 'smart_device,%s %s %d' % (tags, fields, ts)

def main(args):
    logger = get_logger('smart_to_influx', 'smart_to_influx.log')
    try:
        if not args.devices:
            rows = subprocess.check_output(SCAN_CMD.split()).strip().split(b'\n')
            args.devices = [row.strip().split(b' ', 1)[0].decode('utf-8') for row in rows]

        hostname = socket.gethostname()
        ts = datetime.now().timestamp() * 1000000000
        for device in args.devices:
            try:
                info, attrs = parse_smart(hostname, device, subprocess.check_output((CMD % device).split()))
                if not info['is_ssd']:
                    ss = create_influx_str(ts, info, attrs)
                    resp = requests.post('%s/write' % args.influx_uri, params={'db': args.influx_db}, data=ss)
                    resp.raise_for_status()
            except Exception as ex:
                print(resp.json())
                logger.exception(ex)
    except Exception as ex:
        logger.exception(ex)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Process SMART data')
    parser.add_argument('devices', metavar='DEVICE', nargs='*',
                        help='an device to query')
    parser.add_argument('--influx-uri', default='http://dashboard.lan:8086',
                        help='send information to the given influx URI')
    parser.add_argument('--influx-db', default='smart',
                        help='send information to the given influx db')
    args = parser.parse_args()

    main(args)
