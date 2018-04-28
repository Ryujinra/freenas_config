#!/usr/local/bin/python3

import re
import subprocess
import sys
import argparse
import socket
import os
from datetime import datetime
from pprint import pprint, pformat
import logging
import logging.handlers
import requests

LOG_DIR = '/var/log'
SCAN_CMD = 'smartctl --scan'
CMD = 'smartctl --info --attributes --health --format=brief --log=selftest %s'
sata_re = re.compile(b'^SATA (\d\.\d), (\d\.\d) Gb/s \(current: (\d.\d) Gb/s\)$')

def get_logger(name, filename, level=logging.DEBUG):
    logger = logging.getLogger(name)
    logger.setLevel(level)
    handler = logging.handlers.RotatingFileHandler(os.path.join(LOG_DIR, filename),
                                                   maxBytes=1024*1024, backupCount=5)
    handler.setLevel(level)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(formatter)
    logger.addHandler(console)
    return logger

def parse_smart(hostname, device, output, status):
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
    family = info.get(b'Model Family')
    info = {
        'device': device,
        'host': hostname,
        'model': info[b'Device Model'].decode('utf-8'),
        'serial_number': info[b'Serial Number'].decode('utf-8'),
        'capacity': int(info[b'User Capacity'].split()[0].replace(b',', b'')),
        'enabled': info[b'SMART support is'].lower() == b'enabled',
        'rpm': rpm,

        'sata_speed': float(sata[1]),
        'sata_current_speed': float(sata[2]),
        'sata_version': sata[0],
        'is_ssd': is_ssd,
        'status': status,
    }
    if family:
        info['family'] = family.decode('utf-8')
    else:
        info['family'] = info['model']
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
            for key in ('host', 'device', 'model', 'serial_number')]
    family = info.get('family')
    if family:
        tags.append('family=%s' % family.replace(' ', r'\ '))
    tags.extend(['%s=%d' % (key, info[key]) for key in ('enabled', 'is_ssd', 'capacity', 'rpm')])
    tags = ','.join(tags)
    if not info['is_ssd']:
        fields = ('status=%d,health_ok=%d,read_error_rate=%d,realloc_sector_cnt=%d,seek_error_rate=%d,'
                  'spin_retry_cnt=%d,power_on_hours=%d,udma_crc_error_cnt=%d') % (
                  info['status'],
                  info['health_ok'],
                  attributes[b'Raw_Read_Error_Rate']['raw_value'],
                  attributes[b'Reallocated_Sector_Ct']['raw_value'],
                  attributes[b'Seek_Error_Rate']['raw_value'],
                  attributes[b'Spin_Retry_Count']['raw_value'],
                  attributes[b'Power_On_Hours']['raw_value'],
                  attributes[b'UDMA_CRC_Error_Count']['raw_value'])
        tag_fields = ['%s="%s"' % (key, info[key])
            for key in ('host', 'device', 'model', 'serial_number')]
        if family:
            tag_fields.append('family="%s"' % family)
        tag_fields.extend(['%s=%d' % (key, info[key]) for key in ('enabled', 'is_ssd', 'capacity', 'rpm')])
        fields += ',' + ','.join(tag_fields)
    else:
        raise Exception('SSDs not implemented')
    return 'smart_device,%s %s %d' % (tags, fields, ts)

def main(args):
    logger = get_logger('smart_to_influx', 'smart_to_influx.log',
                        logging.DEBUG if args.debug else logging.INFO)
    try:
        if not args.devices:
            rows = subprocess.check_output(SCAN_CMD.split()).strip().split(b'\n')
            args.devices = [row.strip().split(b' ', 1)[0].decode('utf-8') for row in rows]

        logger.debug('%s', args.devices)

        hostname = socket.gethostname()
        ts = datetime.now().timestamp() * 1000000000
        for device in args.devices:
            resp = None
            try:
                cmd = CMD % device
                logger.debug(cmd)
                result = subprocess.run(cmd.split(), check=False, stdout=subprocess.PIPE)
                if result.returncode == 0 or result.returncode >= 8:
                    info, attrs = parse_smart(hostname, device, result.stdout, result.returncode)
                    logger.debug(pformat(info))
                    if not info['is_ssd']:
                        ss = create_influx_str(ts, info, attrs)
                        if args.debug:
                            logger.debug(ss)
                        else:
                            resp = requests.post('%s/write' % args.influx_uri, params={'db': args.influx_db}, data=ss)
                            resp.raise_for_status()
                else:
                    result.check_returncode()
            except Exception as ex:
                if resp is not None:
                    print(resp.json())
                logger.exception(ex)
    except Exception as ex:
        logger.exception(ex)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Process SMART data')
    parser.add_argument('devices', metavar='DEVICE', nargs='*',
                        help='an device to query')
    parser.add_argument('--influx-uri', default='http://influx.lan:8086',
                        help='send information to the given influx URI')
    parser.add_argument('--influx-db', default='smart',
                        help='send information to the given influx db')
    parser.add_argument('--debug', '-d', action='store_true',
                        help='turn on debug')
    args = parser.parse_args()

    main(args)
