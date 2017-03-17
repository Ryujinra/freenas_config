from __future__ import print_function
import subprocess
import re
from time import sleep
from datetime import datetime
import argparse
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

def get_duty_cycles():
    return get_duty_cycle(0), get_duty_cycle(1)

def get_mode():
    mode = int(subprocess.check_output((MODE_CMD % 0).split()), 16)
    return MODES.get(mode, 'Unknown')

def set_mode(mode):
    mode = dict((val, key) for key, val in MODES.iteritems())[mode]
    subprocess.check_output((MODE_CMD % 1 + ' %d' % mode).split())

def get_speeds():
    sdr_re = re.compile(r'(FAN\S+)\s*\|.*\|\s*(\S+)\s*\|.*\|\s*(\d+)\s*RPM\s*\n')
    saved_dc = get_duty_cycles()
    try:
        # this command cause duty cycle reads after this to be wrong
        sdr = subprocess.check_output(FAN_SPEEDS_CMD.split())
        return dict((name, {'speed': int(speed), 'status': status})
                    for name, status, speed in sdr_re.findall(sdr))
    finally:
        try: set_duty_cycle(0, saved_dc[0])
        except: pass
        try: set_duty_cycle(1, saved_dc[1])
        except: pass

def print_header(fans):
    rpm = 'Curr_RPM' + '_' * len(fans) * 9
    print('{:25}___Duty%___ {}'.format('', rpm))
    fan_headers = ' '.join(['{%s:10}' % key for key in sorted(fans.keys())])
    print(("{cond:15} {mode:8} {duty0:>5} {duty1:>5} %s" % fan_headers).format(
        cond='', mode="MODE", duty0="Zone0", duty1="Zone1",
        **dict((key, key) for key in fans.keys())))

def print_line(cond, mode, duties, speeds):
    fans = ' '.join(['{:10}'.format('%s(%s)' % (speeds[key]['speed'], speeds[key]['status']))
                     for key in sorted(speeds.keys())])
    print('{cond:15} {mode:8} {duty0:>5} {duty1:>5} {fans}'.format(
        cond=cond, mode=mode, duty0=duties[0], duty1=duties[1], fans=fans))

def test_mode(args):
    print(datetime.now().strftime('%A, %b %d, %H:%M:%S'))
    saved_mode = get_mode()
    saved_dc = get_duty_cycles()
    speeds = get_speeds()
    print_header(speeds)
    print_line('Starting state', saved_mode, saved_dc, speeds)
    try:
        set_mode('Full')
        sleep(1)

        for duty_cycle in range(args.dc_max, args.dc_min-10, -10):
            set_duty_cycle(0, duty_cycle)
            set_duty_cycle(1, duty_cycle)
            sleep(5)
            print_line('Duty cycle %d' % duty_cycle, saved_mode, get_duty_cycles(), get_speeds())
    except KeyboardInterrupt:
        pass
    finally:
        try: set_mode(saved_mode)
        except: pass
        try: set_duty_cycle(0, saved_dc[0])
        except: pass
        try: set_duty_cycle(1, saved_dc[1])
        except: pass
        sleep(5)
    print_line('Ending state', get_mode(), get_duty_cycles(), get_speeds())

def log_mode(args):
    pass

def pid_mode(args):
    pass

if __name__ == '__main__':
    modes = {
        'test': test_mode,
        'log': log_mode,
        'pid': pid_mode,
    }
    parser = argparse.ArgumentParser(description='Fan control')
    parser.add_argument('mode', choices=sorted(modes.keys()),
                        help='the mode to run')
    parser.add_argument('--zones', '-z', type=int, choices=range(1,3), default=1,
                        help='the number of zones (default: 1)')
    parser.add_argument('--dc-min', type=int, choices=range(10,110,10), default=10,
                        help='the minimum duty cycle (default: 10)')
    parser.add_argument('--dc-max', type=int, choices=range(10,110,10), default=100,
                        help='the maximum duty cycle (default: 100)')
    args = parser.parse_args()

    if args.dc_min > args.dc_max:
        parser.error('duty cycle min must be <= duty cycle max')

    modes[args.mode](args)
