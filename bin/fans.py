#!/usr/local/bin/python3

from __future__ import print_function
import subprocess
import socket
import os
import re
from time import sleep
from datetime import datetime
import argparse
import json
import logging
import logging.handlers
import pickle
from pprint import pprint
import requests
from disks import get_disks_info

# Reset the bmc if fans are stuck at 100%
# ipmitool bmc reset warm

# Set fan thresholds
# ipmitool sensor thresh FAN1 lower 100 200 300
# ipmitool sensor thresh FAN1 upper 2800 2900 3000
# ipmitool sensor thresh FAN2 upper 20000 21000 22000
# ipmitool sensor thresh FAN2 lower 100 200 300
# ipmitool sensor thresh FANA lower 100 200 300
# ipmitool sensor thresh FANA upper 1400 1500 1600

LOG_DIR = '/var/log'
IMPITOOL_BIN = '/usr/local/bin/ipmitool'
DUTY_CYCLE_CMD = IMPITOOL_BIN + ' raw 0x30 0x70 0x66 %d %d'
MODE_CMD = IMPITOOL_BIN + ' raw 0x30 0x45 %d'
FAN_SPEEDS_CMD = IMPITOOL_BIN + ' sdr type fan'
#CPU_TEMP_CMD = IMPITOOL_BIN + ' sdr type temperature'
CPU_TEMP_CMD = '/sbin/sysctl dev.cpu | grep temperature'
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

# warning: this command cause duty cycle reads after this to be wrong
def get_fan_speeds(zones):
    sdr_re = re.compile(r'(FAN\S+)\s*\|.*\|\s*(\S+)\s*\|.*\|\s*(\d+)\s*RPM\s*\n')
    sdr = subprocess.check_output(FAN_SPEEDS_CMD.split())
    return dict((name, {'speed': int(speed), 'status': status})
                    for name, status, speed in sdr_re.findall(sdr.decode('utf-8')))

def get_fan_speeds_safe(zones):
    saved_dc = get_duty_cycles(args.zones)
    try:
        return get_fan_speeds(zones)
    finally:
        for zone in args.zones:
            try: set_duty_cycle(zone, saved_dc[zone])
            except: pass

cpu_re = re.compile(r'^dev\.cpu\.\d+\.temperature:\s*(\d+\.\d+)C$')

def get_cpu_temp():
    lines = [line.strip()
             for line in subprocess.check_output(CPU_TEMP_CMD, shell=True).decode('utf-8').split('\n') if line]
    temps = [float(cpu_re.match(line).groups()[0]) for line in lines]
    return max(temps)

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
        speeds = get_fan_speeds(args.zones)
        print_header(args.zones, speeds)
        print_line('Starting state', saved_mode, saved_dc, speeds)

        set_mode('Full')

        for zone in args.zones:
            for duty_cycle in range(args.dc_max, args.dc_min-10, -10):
                set_duty_cycle(zone, duty_cycle)
                sleep(5)
                print_line('Zone%d DC %d' % (zone, duty_cycle), saved_mode,
                           get_duty_cycles(args.zones), get_fan_speeds(args.zones))
    except KeyboardInterrupt:
        pass
    finally:
        try: set_mode(saved_mode)
        except: pass
        for zone in args.zones:
            try: set_duty_cycle(zone, saved_dc[zone])
            except: pass

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

def get_disk_temps(args):
    disks_info = get_disks_info(args.disk_match)
    return [value['temp_c'] for key, value in disks_info.items()
            if value['temp_c'] is not None]

def log_mode(args):
    logger = get_logger('log_mode', 'temps.log')
    temps = get_disk_temps(args)
    logger.info('%s mean: %s max: %s', temps, sum(temps) / len(temps), max(temps))

def pid(now, set_point, kp, ki, kd, state, time_unit, pv, logger):
    logger.debug('sp: %s pv: %s', set_point, pv)

    error = pv - set_point

    if state:
        logger.debug(state)

        dt = ((now - state['prev_time']).total_seconds()) / time_unit
        state['integral'] += error * dt
        derivative = (error - state['prev_error']) / dt
        cv = args.kp * error + args.ki * state['integral'] + args.kd * derivative
        logger.debug('Kp: %.1f Ki: %.1f Kd: %.1f err: %.3f dt: %.3f int: %.3f deriv: %.3f cv:%.2f',
                     args.kp, args.ki, args.kd, error, dt, state['integral'], derivative, cv)
        logger.debug('prop: %.3f int: %.3f deriv: %.3f',
                     args.kp * error, args.ki * state['integral'], args.kd * derivative)
    else:
        logger.debug('initializing PID state')
        state = {'integral': 0}
        cv = None

    state['prev_time'] = now
    state['prev_error'] = error

    return cv, state

def pid_mode(args, zone=1):
    logger = get_logger('log_mode', 'pid.log')
    logger.debug('-----------------------------')

    temps = get_disk_temps(args)
    temp_max = max(temps)
    temp_mean = sum(temps) / len(temps)
    logger.debug('%s mean: %s max: %s', temps, sum(temps) / len(temps), max(temps))

    if not args.reset and os.path.isfile('/var/run/disk_temp_state.pickle'):
        with open('/var/run/disk_temp_state.pickle', 'rb') as state_file:
            state = pickle.load(state_file)
    else:
        state = None

    now = datetime.now()
    cv, state = pid(now, args.set_point, args.kp, args.ki, args.kd, state, args.time_unit,
                    temp_mean, logger)

    if cv:
        curr_dc = state.get('curr_dc', get_duty_cycle(zone))
        logger.debug('curr_dc: %d', curr_dc)

        duty_cycle = int(round(min(max(curr_dc + cv, args.dc_min), args.dc_max)))
        logger.debug('new duty_cycle: %d', duty_cycle)
        set_duty_cycle(zone, duty_cycle)
        state['curr_dc'] = duty_cycle

    write_influx_pid(args, now, state, logger)

    with open('/var/run/disk_temp_state.pickle', 'wb') as state_file:
        pickle.dump(state, state_file)

def write_influx_pid(args, now, state, logger):
    ts = now.timestamp() * 1000000000
    hostname = socket.gethostname()
    data = ['disk,host=%s value=%d %d' % (hostname, state['curr_dc'], ts),
            'set_point,host=%s value=%d %d' % (hostname, args.set_point, ts)]
    #logger.debug(data)
    resp = requests.post('%s/write' % args.influx_uri, params={'db': args.influx_db}, data='\n'.join(data))
    resp.raise_for_status()

def cpu_mode(args, zone=0):
    curr_dc = -1
    while True:
        try:
            temp = get_cpu_temp()
            dc_per_degree = (args.dc_max - args.dc_min) / (args.cpu_max - args.cpu_start)
            new_dc = args.dc_min + (temp - args.cpu_start) * dc_per_degree
            new_dc = min(max(new_dc, args.dc_min), args.dc_max)
            if new_dc != curr_dc:
                set_duty_cycle(zone, new_dc)
                curr_dc = new_dc
            sleep(1)
            curr_dc = get_duty_cycle(zone)
        except KeyboardInterrupt:
            raise
        except:
            try:
                set_duty_cycle(zone, 100)
            except KeyboardInterrupt:
                raise
            except:
                pass
            pass

def get_data_mode(args):
    saved_dc = get_duty_cycles(args.zones)
    fans = {
        'mode': get_mode(),
        'duty_cycle': saved_dc,
    }
    try:
        fans.update(get_fan_speeds(args.zones))
        cpu = get_cpu_temp()
    finally:
        for zone in args.zones:
            try: set_duty_cycle(zone, saved_dc[zone])
            except: pass
    disks = get_disks_info(args.disk_match)
    temps = [value['temp_c'] for value in disks.values()]
    disks['max'] = max(temps)
    disks['min'] = min(temps)
    disks['mean'] = sum(temps) / len(temps)
    print(json.dumps({'fans': fans, 'disks': disks, 'cpu': cpu}, indent=4, sort_keys=True))

if __name__ == '__main__':
    modes = {
        'test': test_mode,
        'log': log_mode,
        'pid': pid_mode,
        'get': get_data_mode,
        'cpu': cpu_mode,
    }
    parser = argparse.ArgumentParser(description='Fan control')
    parser.add_argument('mode', choices=sorted(modes.keys()),
                        help='the mode to run')
    parser.add_argument('--zones', '-z', type=int, choices=range(1,3), default=1,
                        help='the number of zones (default: 1)')
    parser.add_argument('--dc-min', type=int, choices=range(10,110,10), default=20,
                        help='the minimum duty cycle (default: 10)')
    parser.add_argument('--dc-max', type=int, choices=range(10,110,10), default=100,
                        help='the maximum duty cycle (default: 100)')
    parser.add_argument('--set-point', '-s', type=float, metavar='TEMP_C', default=38,
                        help='the disk temperature set point (default: 38)')
    parser.add_argument('--disk-match', '-d', metavar='REGEX', default=r'^da\d+$',
                        help=r'only use disks that match this regular expression (default: "^da\d+$")')
    parser.add_argument('--reset', '-r', action='store_true',
                        help='reset the state of the PID controller')
    parser.add_argument('--kp', type=float, default=10,
                        help='Kp, the proportional constant (default: 2)')
    parser.add_argument('--ki', type=float, default=0,
                        help='Ki, the integral constant (default: .2)')
    parser.add_argument('--kd', type=float, default=30,
                        help='Kd, the derivative constant (default: .1)')
    parser.add_argument('--time-unit', '-t', type=float, metavar='SECS', default=60.0,
                        help=('the integral time unit (default: 300)'))
    parser.add_argument('--cpu-start', type=float, metavar='TEMP_C', default=54.0,
                        help=('the integral time unit (default: 54.0)'))
    parser.add_argument('--cpu-max', type=float, metavar='TEMP_C', default=70.0,
                        help=('the integral time unit (default: 70.0)'))
    parser.add_argument('--influx-uri', default='http://dashboard.lan:8086',
                        help='send information to the given influx URI')
    parser.add_argument('--influx-db', default='fans',
                        help='send information to the given influx db')
    args = parser.parse_args()

    if args.dc_min > args.dc_max:
        parser.error('duty cycle min must be <= duty cycle max')
    args.zones = range(0, args.zones)

    modes[args.mode](args)
