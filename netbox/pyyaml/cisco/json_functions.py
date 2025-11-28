#!/usr/bin/env python3

# Return Cisco devices JSON objects

import logging
import re
from pathlib import Path
from std_functions import data_folder
from std_functions import get_hostname_and_stack, get_device_type, get_modules, get_lags, get_vlans

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
    """
    Extract device and chassis information from all Cisco config files in data folder.
    Returns dictionary formatted for NetBox integration via pynetbox.

    Args:
        data_folder: Path to folder containing Cisco config files

    Returns:
        dict: Dictionary with 'devices' and 'chassis' keys:
            - devices: List of device dicts, each with:
                - name: Device hostname (e.g., 'rhcs0007' or 'rgcs0003-1')
                - tags: List of tags (e.g., ['switch'], ['switch', 'stack'])
                - device_type: Device model (e.g., 'ws-c2960x-24pd-l', 'cat4500es8')
                - serial: Serial number from serial_numbers.yaml
                - site: Site slug (e.g., 'campus-h')
                - device_role: Device role from get_device_role()
                - virtual_chassis: (stack only) Chassis name
                - vc_position: (stack only) Position in stack (int)
                - vc_priority: (stack only) Priority (255=primary, 128=secondary, 64=default)

            - chassis: List of virtual chassis dicts (for stacks), each with:
                - master: Master switch name (e.g., 'rgcs0003-1')
                - name: Chassis name (e.g., 'rgcs0003')

    Example output for single switch:
        {
            'devices': [
                {
                    'name': 'rhcs1111',
                    'tags': ['switch'],
                    'device_type': 'ws-c2960x-24pd-l',
                    'serial': 'FOCXXXXABCD',
                    'site': 'campus-h',
                    'device_role': 'access-switch'
                }
            ],
            'chassis': []
        }

    Example output for stack:
        {
            'devices': [
                {
                    'name': 'rgcs1234-1',
                    'tags': ['switch', 'stack'],
                    'device_type': 'cat4500es8',
                    'serial': 'CAT1123456G',
                    'site': 'campus-g',
                    'device_role': 'core-switch',
                    'virtual_chassis': 'rgcs1234',
                    'vc_position': 1,
                    'vc_priority': 255
                },
                ...
            ],
            'chassis': [
                {
                    'master': 'rgcs1234-1',
                    'name': 'rgcs1234'
                }
            ]
        }
    """
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
                'device_type': f"cisco-{get_device_type(config_file)}",
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
                'device_type': f"cisco-{get_device_type(config_file)}",
                'serial': serial_nums[name],
                'site': site_slug(name),
                'device_role': get_device_role(config_file, hostname),
                'virtual_chassis': hostname,
                'vc_position': int(switch_nr),
                'vc_priority': vc_priority
            })

    return data

def modules_json(data_folder):
    """
    Extract module information from all Cisco config files in data folder.
    Returns dictionary formatted for NetBox integration via pynetbox.

    Args:
        data_folder: Path to folder containing Cisco config files

    Returns:
        dict: Dictionary with 'modules' key containing list of module dicts, each with:
            - device: Device hostname (e.g., 'rgcs0003-1')
            - module_bay: Slot number as string (e.g., '1', '2')
            - name: Descriptive name (e.g., 'Slot 1')
            - new_position: Switch/slot format (e.g., '1/1', '2/3')
            - type: Module model name (e.g., 'WS-X45-SUP8-E')

    Example output:
        {
            'modules': [
                {
                    'device': 'rgcs1234-1',
                    'module_bay': '1',
                    'name': 'Slot 1',
                    'new_position': '1/1',
                    'type': 'WS-X45-SUP8-E'
                },
                ...
            ]
        }
    """
    data = {'modules': []}

    data_path = Path(data_folder)
    if not data_path.exists():
        logger.error(f"Data folder does not exist: {data_folder}")
        return data

    # Iterate through each config file in the data folder
    for config_file in data_path.iterdir():
        if not config_file.is_file():
            continue

        # Get modules from this config file
        modules = get_modules(config_file)

        # Transform each module to NetBox format
        for module in modules:
            # Skip if module model is unknown
            if not module['module_model']:
                logger.warning(f"Unknown module type {module['slot_type']} in {config_file.name}, skipping")
                continue

            data['modules'].append({
                'device': module['hostname'],
                'module_bay': module['slot'],
                'name': f"Slot {module['slot']}",
                'new_position': f"{module['switch']}/{module['slot']}",
                'type': module['module_model']
            })

    logger.debug(f"Extracted {len(data['modules'])} modules from {data_folder}")
    return data

def lags_json(data_folder):
    """
    Extract LAG (Port-channel) information from all Cisco config files in data folder.
    Returns dictionary formatted for NetBox integration via pynetbox.

    Args:
        data_folder: Path to folder containing Cisco config files

    Returns:
        dict: Dictionary with 'lags' key containing list of LAG dicts, each with:
            - hostname: Device hostname (e.g., 'rhcs1234' or 'rgcs1234-1')
            - name: LAG/Port-channel name (e.g., 'Port-channel1', 'Port-channel15')

    Note:
        For stacks/VSS, Port-channels are global to the stack but are assigned to
        the first switch member (hostname-1) following NetBox conventions.

    Example output:
        {
            'lags': [
                {
                    'hostname': 'rgcs1234-1',
                    'name': 'Port-channel1'
                },
                {
                    'hostname': 'rgcs1234-1',
                    'name': 'Port-channel15'
                },
                {
                    'hostname': 'rhcs1234',
                    'name': 'Port-channel5'
                }
            ]
        }
    """
    data = {"lags": []}

    data_path = Path(data_folder)
    if not data_path.exists():
        logger.error(f"Data folder does not exist: {data_folder}")
        return data

    # Iterate through each config file in the data folder
    for config_file in data_path.iterdir():
        if not config_file.is_file():
            continue

        # Get hostname and stack info
        hostname_info = get_hostname_and_stack(config_file)
        if not hostname_info:
            continue

        hostname = hostname_info['hostname']
        is_stack = hostname_info['stack']

        # For stacks, assign LAGs to the first switch member
        if is_stack:
            hostname = f"{hostname}-1"

        # Get all LAGs from this config file
        lags = get_lags(config_file)

        # Add each LAG to the data
        for lag in lags:
            data['lags'].append({
                'hostname': hostname,
                'name': lag['name']
            })

    logger.debug(f"Extracted {len(data['lags'])} LAGs from {data_folder}")
    return data 

def vlans_json(data_folder):
    """
    Extract unique VLAN definitions from all Cisco config files in data folder.
    Returns dictionary formatted for NetBox integration via pynetbox.

    Args:
        data_folder: Path to folder containing Cisco config files

    Returns:
        dict: Dictionary with 'vlans' key containing list of unique VLAN dicts, each with:
            - id: VLAN ID as string (e.g., '20', '20')
            - name: VLAN name (e.g., 'ADMIN', 'USER')

    Note:
        VLANs are deduplicated across all config files. If the same VLAN ID appears
        in multiple files with different names, the first occurrence is used.

    Example output:
        {
            'vlans': [
                {'id': '10', 'name': 'ADMIN'},
                {'id': '20', 'name': 'USER'}
            ]
        }
    """
    data = {'vlans': []}

    data_path = Path(data_folder)
    if not data_path.exists():
        logger.error(f"Data folder does not exist: {data_folder}")
        return data

    # Collect unique VLANs across all config files
    # Use a set to automatically handle duplicates
    all_vlans = set()

    # Iterate through each config file in the data folder
    for config_file in data_path.iterdir():
        if not config_file.is_file():
            continue

        # Get VLANs from this config file
        vlans = get_vlans(config_file)
        all_vlans.update(vlans)

    # Convert set to sorted list of dictionaries
    # Sort by VLAN ID (numerically)
    sorted_vlans = sorted(all_vlans, key=lambda x: int(x[0]))

    for vlan_id, vlan_name in sorted_vlans:
        data['vlans'].append({
            'id': vlan_id,
            'name': vlan_name
        })

    logger.debug(f"Extracted {len(data['vlans'])} unique VLANs from {data_folder}")
    return data

def device_interfaces_json(data_folder):
    data = {'device_interfaces': []}

    return data

if __name__ == "__main__":
    from functions import _debug

    _debug(vlans_json, data_folder)

'''
device_interfaces:
- hostname: rscs0007-1
  interface: 1/C2
  is_lag: false
  name: V.S05.313.0 rsgw5313sp/uplink/xx
  poe_mode: null
  poe_type: null
  type: 10gbase-x-sfpp
  vlan_id: null
  vlan_name: null
- hostname: rscs0007-2
  interface: 2/C6
  is_lag: false
  name: V.S19.1xx.0 rsgw191xxsp/uplink/trk1
  poe_mode: null
  poe_type: null
  type: 10gbase-x-sfpp
  vlan_id: null
  vlan_name: null
'''