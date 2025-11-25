#!/usr/bin/env python3

# Return Cisco devices JSON objects

import logging
import re
from pathlib import Path
from std_functions import data_folder
from std_functions import get_hostname_and_stack, get_device_type

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from functions import serial_numbers, get_device_role, campuses

logger = logging.getLogger(__name__)

def set_tags(hostname):
    '''
    Define device tags, from the hostname
    '''
    tags = []
    if int(hostname[5]) == 0:
        tags.append('router')
    else: tags.append('switch')
    
    if len(hostname.split('-')) > 1:
        tags.append('stack')
    
    return tags

def site_slug(hostname):
    # Return site slug from hostname
    return f"campus-{campuses[hostname[1]]}"


def devices_json(data_folder):
    data = {'devices': [], 'chassis': []}

    data_path = Path(data_folder)
    if not data_path.exists():
        logger.error(f"Data folder does not exist: {data_folder}")
        return data

    serial_nums = serial_numbers()
    # Iterate through each config file in the data folder
    for config_file in data_path.iterdir():
        if not config_file.is_file():
            continue

        device = get_hostname_and_stack(config_file)
        if not device:
            continue

        hostname = device['hostname']

        if not device['stack']:
            data['devices'].append({
                'name': hostname,
                'tags': set_tags(hostname),
                'device_type': get_device_type(config_file),
                'serial': serial_nums[hostname],
                'site': site_slug(hostname),
                'device_role': get_device_role(config_file, hostname)
            })
            continue

        data['chassis'].append({
            'master':f"{hostname}-1",
            'name': hostname
        })

        for switch_nr in device['switches']:
            name = f"{hostname}-{switch_nr}"
            vc_priority = 64
            if int(switch_nr) == 1:
                vc_priority = 255
            if int(switch_nr) == 2:
                vc_priority = 128
            data['devices'].append({
                'name': name,
                'tags': set_tags(name),
                'device_type': get_device_type(config_file),
                'serial': serial_nums[name],
                'site': site_slug(name),
                'device_role': get_device_role(config_file, hostname),
                'virtual_chassis': hostname,
                'vc_position': int(switch_nr),
                'vc_priority': vc_priority
            })

    return data

if __name__ == "__main__":
    from functions import _debug

    _debug(devices_json, data_folder)