#!/bin/sh

# AA: CPU_FAN1
# BB: CPU_FAN2
# CC: REAR_FAN1
# DD: REAR_FAN2
# EE: FRNT_FAN1
# FF: FRNT_FAN2

# 0x00 smart fan(bios configured)
# 0x01 stoped fan
# 0x02 lower rpm value
# ......  
# 0x64 max rpm value

/usr/local/bin/ipmitool raw 0x3a 0x01 0x64 0x64 0x64 0x64 0x64 0x64 0x00 0x00
