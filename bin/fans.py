from __future__ import print_function
import subprocess
import re
from time import sleep
from datetime import datetime
import argparse
import json
from pprint import pprint

IMPITOOL_BIN = '/usr/local/bin/ipmitool'
DUTY_CYCLE_CMD = IMPITOOL_BIN + ' raw 0x30 0x70 0x66 %d %d'
MODE_CMD = IMPITOOL_BIN + ' raw 0x30 0x45 %d'
FAN_SPEEDS_CMD = IMPITOOL_BIN + ' sdr type fan'
MODES = {0: 'Standard', 1: 'Full', 2: 'Optimal', 4: 'HeavyIO'}

def get_duty_cycle(zone):
    return int(subprocess.check_output((DUTY_CYCLE_CMD % (0, zone)).split()), 16)

def set_duty_cycle(zone, value):
    subprocess.check_output((DUTY_CYCLE_CMD % (1, zone) + ' %d' % value).split())

def get_duty_cycles(zones):
    return [get_duty_cycle(zone) for zone in zones]

def get_mode():
    mode = int(subprocess.check_output((MODE_CMD % 0).split()), 16)
    return MODES.get(mode, 'Unknown')

def set_mode(mode):
    mode = dict((val, key) for key, val in MODES.iteritems())[mode]
    subprocess.check_output((MODE_CMD % 1 + ' %d' % mode).split())

def get_speeds(zones):
    sdr_re = re.compile(r'(FAN\S+)\s*\|.*\|\s*(\S+)\s*\|.*\|\s*(\d+)\s*RPM\s*\n')
    # warning: this command cause duty cycle reads after this to be wrong
    sdr = subprocess.check_output(FAN_SPEEDS_CMD.split())
    return dict((name, {'speed': int(speed), 'status': status})
                    for name, status, speed in sdr_re.findall(sdr))

def print_header(zones, fans):
    rpm = 'Curr_RPM' + '_' * len(fans) * 9
    duty = '_' * (3 * (len(zones) - 1)) + 'Duty%' + '_' * (3 * (len(zones) - 1))
    print('{:25}{} {}'.format('', duty, rpm))

    zones = ' '.join(['{:>5}'.format('Zone%d' % zone) for zone in zones])
    fan_headers = ' '.join(['{%s:10}' % key for key in sorted(fans.keys())])
    print(("{cond:15} {mode:8} {zones} %s" % fan_headers).format(
        cond='', mode="MODE", zones = zones,
        **dict((key, key) for key in fans.keys())))

def print_line(cond, mode, duties, speeds):
    fans = ' '.join(['{:10}'.format('%s(%s)' % (speeds[key]['speed'], speeds[key]['status']))
                     for key in sorted(speeds.keys())])
    duties = ' '.join(['{:>5}'.format(dc) for dc in duties])
    print('{cond:15} {mode:8} {duties} {fans}'.format(
        cond=cond, mode=mode, duties=duties, fans=fans))

def test_mode(args):
    print(datetime.now().strftime('%A, %b %d, %H:%M:%S'))
    saved_dc = get_duty_cycles(args.zones)
    saved_mode = get_mode()
    try:
        speeds = get_speeds(args.zones)
        print_header(args.zones, speeds)
        print_line('Starting state', saved_mode, saved_dc, speeds)

        set_mode('Full')

        for zone in args.zones:
            for duty_cycle in range(args.dc_max, args.dc_min-10, -10):
                set_duty_cycle(zone, duty_cycle)
                sleep(5)
                print_line('Zone%d DC %d' % (zone, duty_cycle), saved_mode,
                           get_duty_cycles(args.zones), get_speeds(args.zones))
    except KeyboardInterrupt:
        pass
    finally:
        try: set_mode(saved_mode)
        except: pass
        for zone in args.zones:
            try: set_duty_cycle(zone, saved_dc[zone])
            except: pass

def log_mode(args):
    pass

def pid_mode(args):
    pass

def get_data_mode(args):
    saved_dc = get_duty_cycles(args.zones)
    data = {
        'mode': get_mode(),
        'duty_cycle': saved_dc,
    }
    try:
        data.update(get_speeds(args.zones))
    finally:
        for zone in args.zones:
            try: set_duty_cycle(zone, saved_dc[zone])
            except: pass
    print(json.dumps(data, indent=4, sort_keys=True))

if __name__ == '__main__':
    modes = {
        'test': test_mode,
        'log': log_mode,
        'pid': pid_mode,
        'get': get_data_mode,
    }
    parser = argparse.ArgumentParser(description='Fan control')
    parser.add_argument('mode', choices=sorted(modes.keys()),
                        help='the mode to run')
    parser.add_argument('--zones', '-z', type=int, choices=range(1,3), default=2,
                        help='the number of zones (default: 1)')
    parser.add_argument('--dc-min', type=int, choices=range(10,110,10), default=10,
                        help='the minimum duty cycle (default: 10)')
    parser.add_argument('--dc-max', type=int, choices=range(10,110,10), default=100,
                        help='the maximum duty cycle (default: 100)')
    args = parser.parse_args()

    if args.dc_min > args.dc_max:
        parser.error('duty cycle min must be <= duty cycle max')
    args.zones = range(0, args.zones)

    modes[args.mode](args)
