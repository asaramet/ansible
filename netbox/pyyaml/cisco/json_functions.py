#!/usr/bin/env python3

# Return Cisco devices JSON objects

import logging
import re
from pathlib import Path
from std_functions import data_folder
from std_functions import get_hostname_and_stack, get_device_type, get_modules, get_lags, get_vlans, get_interfaces
from std_functions import interface_type_mapping

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

def delete_interfaces_json(data_folder):
    """
    Generate list of incorrectly-named default interfaces to delete for stack members > 1.

    When NetBox creates stack member devices from templates, it creates interfaces with
    stack number 1 in the name (e.g., GigabitEthernet1/0/1) for ALL stack members.
    But stack member 2 should have GigabitEthernet2/0/1, member 3 should have
    GigabitEthernet3/0/1, etc.

    This function returns the list of default interfaces (with stack number = 1) that
    should be deleted for stack members at positions > 1, so they can be replaced with
    correctly-named interfaces from device_interfaces_json().

    Args:
        data_folder: Path to folder containing Cisco config files

    Returns:
        dict: Dictionary with 'delete_interfaces' key containing list of interface dicts:
            - hostname: Device hostname (e.g., 'rhcs1111-2', 'rhcs1111-3')
            - interface: Default interface name to delete (e.g., 'HundredGigE1/0/49')

    Note:
        Only includes interfaces for stack members at position > 1, since position 1
        devices have correctly-named interfaces (with stack number 1).

    Example output:
        {
            'delete_interfaces': [
                {'hostname': 'rhcs1111-2', 'interface': 'TwentyFiveGigE1/0/1'},
                {'hostname': 'rhcs1111-2', 'interface': 'TwentyFiveGigE1/0/2'},
                {'hostname': 'rhcs1111-2', 'interface': 'HundredGigE1/0/49'},
                {'hostname': 'rhcs1111-3', 'interface': 'TwentyFiveGigE1/0/1'},
                ...
            ]
        }
    """
    data = {'delete_interfaces': []}

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

        # Skip if not a stack
        if not is_stack:
            continue

        # Get all interfaces from this config file
        interfaces = get_interfaces(config_file)

        # Collect unique interface names with stack number replaced by 1
        default_interface_names = set()

        for iface in interfaces:
            interface_name = iface['interface']

            # Replace actual stack number with 1 to get default template name
            # Examples:
            #   TwentyFiveGigE2/0/5 -> TwentyFiveGigE1/0/5
            #   HundredGigE2/0/49 -> HundredGigE1/0/49
            #   GigabitEthernet3/0/10 -> GigabitEthernet1/0/10
            default_name = re.sub(r'^(\w+)\d+/', r'\g<1>1/', interface_name)
            default_interface_names.add(default_name)

        # For each stack member beyond position 1, add all default interfaces to delete list
        for switch_num in hostname_info['switches']:
            if int(switch_num) <= 1:
                continue  # Skip position 1 - those interfaces are correctly named

            member_hostname = f"{hostname}-{switch_num}"

            for interface_name in sorted(default_interface_names):
                data['delete_interfaces'].append({
                    'hostname': member_hostname,
                    'interface': interface_name
                })

    logger.debug(f"Generated {len(data['delete_interfaces'])} interfaces to delete from {data_folder}")
    return data

def device_interfaces_json(data_folder):
    """
    Extract device interface information from all Cisco config files in data folder.
    Returns dictionary formatted for NetBox integration via pynetbox.

    Args:
        data_folder: Path to folder containing Cisco config files

    Returns:
        dict: Dictionary with 'device_interfaces' key containing list of interface dicts, each with:
            - hostname: Device hostname (e.g., 'rhcs1111' or 'rgcs1111-1')
            - interface: Interface name (e.g., 'GigabitEthernet1/0/1', '1/0/1')
            - name: Interface description (str or None)
            - type: NetBox interface type (e.g., '1000base-t', '10gbase-x-sfpp')
            - poe_mode: PoE mode (None, 'pse', 'pd')
            - poe_type: PoE type (None, 'type2-ieee802.3at', 'type4-cisco-upoe')
            - vlan_id: Access VLAN ID (str or None)
            - vlan_name: Access VLAN name (str or None)
            - is_lag: Boolean - True if interface is a Port-channel member

    Example output:
        {
            'device_interfaces': [
                {
                    'hostname': 'rggw1111s-1',
                    'interface': '1/0/1',
                    'name': 'Uplink to core',
                    'type': '1000base-t',
                    'poe_mode': 'pse',
                    'poe_type': 'type2-ieee802.3at',
                    'vlan_id': None,
                    'vlan_name': None,
                    'is_lag': True
                },
                ...
            ]
        }
    """
    data = {'device_interfaces': []}

    data_path = Path(data_folder)
    if not data_path.exists():
        logger.error(f"Data folder does not exist: {data_folder}")
        return data

    # Build a VLAN ID -> name mapping from all config files
    vlan_map = {}
    for config_file in data_path.iterdir():
        if not config_file.is_file():
            continue
        vlans = get_vlans(config_file)
        for vlan_id, vlan_name in vlans:
            # Use first occurrence of VLAN name
            if vlan_id not in vlan_map:
                vlan_map[vlan_id] = vlan_name

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

        # Get device type
        device_type = get_device_type(config_file)
        if not device_type:
            logger.warning(f"Could not determine device type for {config_file.name}, skipping interfaces")
            continue

        # Get interface type mapping for this device model
        type_patterns = interface_type_mapping.get(device_type)
        if not type_patterns:
            logger.warning(f"No interface type mapping for device type '{device_type}', skipping {config_file.name}")
            continue

        # Get all interfaces from this config file
        interfaces = get_interfaces(config_file)

        # Process each interface
        for iface in interfaces:
            interface_name = iface['interface']

            # Determine interface type, PoE mode, and PoE type from mapping
            interface_type = None
            poe_mode = None
            poe_type = None

            for pattern, characteristics in type_patterns.items():
                if re.match(pattern, interface_name):
                    interface_type = characteristics['type']
                    poe_mode = characteristics['poe_mode']
                    poe_type = characteristics['poe_type']
                    break

            if not interface_type:
                logger.debug(f"Could not determine type for interface {interface_name} on {hostname}, skipping")
                continue

            # Override PoE settings if "power inline never" is configured
            if iface.get('power_inline') == 'never':
                poe_mode = None
                poe_type = None
            # Override PoE settings if explicit wattage is configured
            elif iface.get('power_inline_max'):
                # Keep the poe_mode and poe_type from mapping, but note the explicit config
                pass

            # Get VLAN name from VLAN ID
            vlan_id = iface.get('vlan_id')
            vlan_name = vlan_map.get(vlan_id) if vlan_id else None

            # Determine if this interface is a LAG member
            is_lag = bool(iface.get('channel_group'))

            # For stacks, determine which switch member owns this interface
            # Interface format: <Type><switch>/<module>/<port>
            switch_match = re.match(r'^.*?(\d+)/\d+/\d+$', interface_name)
            if switch_match and is_stack:
                switch_num = switch_match.group(1)
                device_hostname = f"{hostname}-{switch_num}"
            else:
                device_hostname = hostname

            # Keep full Cisco interface name (e.g., TwentyFiveGigE1/0/1, GigabitEthernet1/0/1)
            # Unlike Aruba which uses simple numeric names like "1/1/1"
            data['device_interfaces'].append({
                'hostname': device_hostname,
                'interface': interface_name,
                'name': iface.get('description'),
                'type': interface_type,
                'poe_mode': poe_mode,
                'poe_type': poe_type,
                'vlan_id': vlan_id,
                'vlan_name': vlan_name,
                'is_lag': is_lag
            })

    logger.debug(f"Extracted {len(data['device_interfaces'])} interfaces from {data_folder}")
    return data

if __name__ == "__main__":
    from functions import _debug

    _debug(delete_interfaces_json, data_folder)