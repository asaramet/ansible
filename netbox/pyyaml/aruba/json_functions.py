#!/usr/bin/env  python3

#----- Return JSON Objects -----#

import re, sys, yaml
from pathlib import Path
from tabulate import tabulate

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from sort_data import get_switch_type
from functions import serial_numbers, get_ip_address, get_device_role, get_vlans_names

from std_functions import device_type_slags, config_files
from std_functions import convert_interfaces_range
from std_functions import get_os_version, get_hostname
from std_functions import get_lags, get_interface_names, get_vlans
from std_functions import get_untagged_vlans, get_tagged_vlans, get_lag_stack
from std_functions import get_modules
from std_functions import module_types_dict, modules_interfaces, interfaces_types
from std_functions import convert_range

from std_functions import get_location, get_flor_name
from std_functions import get_parent_location, floor_slug, site_slug

def locations_json(config_files):
    """
    Create locations JSON objects from config files.

    Extracts location information (rooms, floors, sites) from switch config files
    and returns structured data for NetBox location creation.

    Args:
        config_files: List of config file paths (Path objects or strings)

    Returns:
        dict: Dictionary with 'locations' key containing list of location objects:
              - room: Room slug (e.g., 'rg.eg.001')
              - floor: Floor name (e.g., 'rg.eg - Ground Floor')
              - site: Site slug (e.g., 'campus-rg')
              - parent_location: Parent location slug (e.g., 'rg.eg')
              - is_rack: Boolean indicating if location is a rack

    Example:
        locations = locations_json(config_files)
        # Returns: {'locations': [
        #   {'room': 'rg.eg.001', 'floor': 'rg.eg - Ground Floor',
        #    'site': 'campus-rg', 'parent_location': 'rg.eg', 'is_rack': False}
        # ]}
    """
    data = {"locations": []}
    locations = set()
    rooms = {}
    sites = {}
    is_racks = {}

    for file in config_files:
        location = get_location(file)
        if not location:
            continue

        location, room, is_rack = location
        locations.add(location)
        rooms[location] = room
        sites[location] = site_slug(file)
        is_racks[location] = is_rack

    for location in locations:
        room = rooms[location]
        building = location.split(".")[0]
        flor_tuple = get_flor_name(room)

        site = sites[location]
        is_rack = is_racks[location]

        data["locations"].append({
            "room": location,
            "floor": f"{building}.{flor_tuple[0]} - {flor_tuple[1]}",
            "site": site,
            "parent_location": get_parent_location(location),
            "is_rack": is_rack
        })

    return data

def devices_json(config_files, device_type_slags, tags):
    """
    Create devices and chassis JSON objects from config files.

    Processes single switches and stacks, creating device entries with proper
    virtual chassis configuration for stacks.

    Args:
        config_files: List of config file paths (Path objects or strings)
        device_type_slags: Dict mapping device type codes to NetBox slugs
                          (e.g., {'J8697A': 'hpe-procurve-5406zl'})
        tags: Device tags, string or list (e.g., 'switch' or ['switch', 'stack'])

    Returns:
        dict: Dictionary with two keys:
              - 'devices': List of device objects with name, role, type, site, serial, tags
              - 'chassis': List of virtual chassis objects (for stacks only)

    Example:
        # Single switch:
        {'devices': [{'name': 'rggw1004sp', 'device_role': 'access',
                      'device_type': 'aruba-2930m-48g', 'site': 'campus-rg',
                      'tags': ['switch'], 'serial': 'SN123456'}],
         'chassis': []}

        # Stack:
        {'devices': [{'name': 'rscs0007-1', 'device_role': 'core', ...,
                      'virtual_chassis': 'rscs0007', 'vc_position': 1, 'vc_priority': 255},
                     {'name': 'rscs0007-2', ..., 'vc_position': 2, 'vc_priority': 128}],
         'chassis': [{'name': 'rscs0007', 'master': 'rscs0007-1'}]}
    """
    data = {'devices': [], 'chassis': []}
    serials = serial_numbers()

    for t_file in config_files:
        hostname = get_hostname(t_file)
        site = site_slug(t_file)

        # Location is added manually in NetBox (not automated)
        location = None

        if location:  # Not None
            location, _, _ = location  # ignore room and rack
            location = floor_slug(location)

        # Process single switches
        if '0' in hostname:
            hostname = hostname['0']
            d_label = device_type_slags[get_switch_type(t_file)]
            serial = serials.get(hostname)

            data['devices'].append({
                'name': hostname,
                'device_role': get_device_role(t_file, hostname),
                'device_type': d_label,
                'site': site,
                'tags': tags,
                'serial': serial
            })
            continue

        # Process stacks
        clean_name = hostname['1'][:-2]
        d_label = device_type_slags[get_switch_type(t_file)['1']]
        master = hostname['1']

        data['chassis'].append({'name': clean_name, 'master': master})

        for h_name in hostname.values():
            vc_position = int(h_name[-1])
            vc_priority = 255 if vc_position == 1 else 128 if vc_position == 2 else 64
            serial = serials.get(h_name)

            data['devices'].append({
                'name': h_name,
                'device_role': get_device_role(t_file, clean_name),
                'device_type': d_label,
                'site': site,
                'tags': tags,
                'serial': serial,
                'virtual_chassis': clean_name,
                'vc_position': vc_position,
                'vc_priority': vc_priority
            })

    return data

def lags_json(config_files):
    """
    Create LAGs and LAG interface membership JSON objects.

    Extracts Link Aggregation Groups (LAGs/trunks) and their member interfaces
    from config files.

    Args:
        config_files: List of config file paths (Path objects or strings)

    Returns:
        dict: Dictionary with two keys:
              - 'lags': List of LAG objects with hostname and LAG name
              - 'lag_interfaces': List of interface-to-LAG mappings

    Example:
        {'lags': [{'hostname': 'rggw1004sp', 'name': 'Trk1'}],
         'lag_interfaces': [
             {'hostname': 'rggw1004sp', 'interface': '45', 'lag_name': 'Trk1'},
             {'hostname': 'rggw1004sp', 'interface': '46', 'lag_name': 'Trk1'}
         ]}
    """
    data = {'lags': [], 'lag_interfaces': []}

    for t_file in config_files:
        hostnames = get_hostname(t_file)
        trk_lists = get_lags(t_file)

        # Get hostname (single switch or first stack member)
        hostname = hostnames['0'] if '0' in hostnames else hostnames['1']

        for lag in trk_lists:
            if not lag:
                continue

            trk_name = lag['name']
            # Title-case trunk names starting with 't' (e.g., 'trk1' -> 'Trk1')
            if trk_name.startswith('t'):
                trk_name = trk_name.title()

            # Parse interface list (handles ranges like '45-46')
            interfaces = lag['interfaces'].replace('-', ',').split(',')

            for interface in interfaces:
                # Add LAG if not already present (deduplicate)
                if {'hostname': hostname, 'name': trk_name} not in data['lags']:
                    data['lags'].append({'hostname': hostname, 'name': trk_name})

                data['lag_interfaces'].append({
                    'hostname': hostname,
                    'interface': interface,
                    'lag_name': trk_name
                })

    return data

def vlans_json(config_files):
    """
    Create VLANs JSON objects from config files.

    Collects all unique VLANs across all config files and returns them with
    VLAN IDs and names.

    Args:
        config_files: List of config file paths (Path objects or strings)

    Returns:
        dict: Dictionary with 'vlans' key containing list of VLAN objects:
              - id: VLAN ID (e.g., '10')
              - name: VLAN name (e.g., 'ADMIN')

    Example:
        {'vlans': [
            {'id': '10', 'name': 'ADMIN'},
            {'id': '20', 'name': 'USERS'}
        ]}
    """
    # Collect unique VLANs from all config files
    vlans = set()
    for t_file in config_files:
        for vlan in get_vlans(t_file):
            vlans.add(vlan)

    # Format as JSON data
    data = {'vlans': []}
    for vlan in vlans:
        data['vlans'].append({'id': vlan[0], 'name': vlan[1]})

    return data

def untagged_vlans(config_files):
    """
    Create untagged (access) VLAN assignments for interfaces.

    Processes interface-to-VLAN mappings for access ports, handling both single
    switches and stacks. For stacks, correctly assigns interfaces to their
    respective stack members.

    Args:
        config_files: List of config file paths (Path objects or strings)

    Returns:
        dict: Dictionary with 'untagged_vlans' key containing list of assignments:
              - hostname: Device hostname
              - interface: Interface name/number
              - vlan_id: VLAN ID (e.g., '10')
              - vlan_name: VLAN name (e.g., 'ADMIN')
              - is_lag: Boolean indicating if interface is a LAG

    Example:
        {'untagged_vlans': [
            {'hostname': 'rggw1004sp', 'interface': '1', 'vlan_id': '10',
             'vlan_name': 'ADMIN', 'is_lag': False},
            {'hostname': 'rscs0007-1', 'interface': 'Trk1', 'vlan_id': '20',
             'vlan_name': 'USERS', 'is_lag': True}
        ]}
    """
    data = {'untagged_vlans': []}

    for t_file in config_files:
        hostname_map = get_hostname(t_file)
        untagged_sets = get_untagged_vlans(t_file)
        tagged_sets = get_tagged_vlans(t_file)
        vlan_names = get_vlans_names(t_file)

        # Collect all LAG interfaces from tagged VLANs
        lags = {
            interface
            for _, int_range in tagged_sets
            for _, interface in convert_interfaces_range(int_range)
        }

        # Determine if device is single (flat) or stack
        is_stack = isinstance(hostname_map, dict) and '0' not in hostname_map
        lag_stacks = get_lag_stack(t_file) if is_stack else None

        for vlan_id, int_range, is_lag in untagged_sets:
            vlan_name = vlan_names.get(vlan_id, f"VLAN {vlan_id}")
            if vlan_name == "VLAN 1":
                vlan_name = "DEFAULT_VLAN"

            interfaces = convert_interfaces_range(int_range)

            for stack_nr, interface in interfaces:
                if is_lag is None:
                    is_lag = interface in lags

                # For LAG interfaces in stacks, determine correct stack member
                if is_stack and 'T' in interface:
                    for nr in range(1, 20):
                        if (interface, str(nr)) in lag_stacks:
                            stack_nr = str(nr)
                            break

                # Get hostname (single switch or stack member)
                hostname = (
                    hostname_map if not is_stack
                    else hostname_map.get(stack_nr, f"unknown-{stack_nr}")
                )

                data['untagged_vlans'].append({
                    'hostname': hostname,
                    'interface': str(interface),
                    'vlan_id': vlan_id,
                    'vlan_name': vlan_name,
                    'is_lag': is_lag
                })

    return data

def device_interfaces_json(config_files):
    """
    Create device interfaces and delete-interfaces JSON objects.

    Extracts all interfaces with their properties (type, PoE, VLAN assignments)
    from config files. Also generates a list of interfaces to delete for stacks
    (NetBox creates default interfaces for member 1, but members 2+ need their own).

    Args:
        config_files: List of config file paths (Path objects or strings)

    Returns:
        dict: Dictionary with two keys:
              - 'device_interfaces': List of interface objects with hostname, name,
                type, PoE settings, VLAN assignments
              - 'delete_interfaces': List of interfaces to remove from NetBox
                (for stack members > 1)

    Example:
        {'device_interfaces': [
            {'hostname': 'rggw1004sp', 'interface': '1', 'name': 'Port 1',
             'type': '1000base-t', 'poe_mode': 'pse', 'poe_type': 'type2-ieee802.3at',
             'vlan_id': '10', 'vlan_name': 'ADMIN', 'is_lag': False}
         ],
         'delete_interfaces': [
            {'hostname': 'rscs0007-2', 'interface': '1'}
         ]}
    """
    data = {'device_interfaces': [], 'delete_interfaces': []}
    unique_interfaces = set()
    unique_delete_interfaces = set()

    # Get untagged VLAN data first for VLAN lookup
    vlan_data = untagged_vlans(config_files)['untagged_vlans']

    # Build VLAN lookup table
    vlan_lookup = {}
    for entry in vlan_data:
        host = entry['hostname']
        if isinstance(host, dict):
            host = host.get('0')  # Fallback to stack 0 if needed
        if host is not None:
            vlan_lookup[(host, entry['interface'])] = {
                'vlan_id': entry.get('vlan_id'),
                'vlan_name': entry.get('vlan_name'),
                'is_lag': entry.get('is_lag', False)
            }

    for t_file in config_files:
        hostname = get_hostname(t_file)
        i_types = interfaces_types(t_file)
        os_version = get_os_version(t_file)

        # Process module interfaces (modular switches with expansion modules)
        for module in get_modules(t_file):
            interfaces_dict = modules_interfaces(module['type'], module['module'])
            for keys_range, type_value in interfaces_dict['types'].items():
                for key in convert_range(keys_range):
                    i_types["type"][key] = type_value
                    i_types["poe_type"][key] = interfaces_dict['poe_types'].get(keys_range)
                    i_types["poe_mode"][key] = interfaces_dict['poe_mode'].get(keys_range)

        # Process all interfaces
        for interface, name in get_interface_names(t_file):
            if interface == "mgmt":
                continue

            # Set type for virtual and LAG interfaces
            if interface.lower().startswith('vlan '):
                i_types["type"][interface] = "virtual"
            if interface.lower().startswith('lag '):
                i_types["type"][interface] = "lag"

            # Extract interface number and stack member
            i_nr = interface.split('/')[-1]
            stack_nr = interface.split('/')[0] if '/' in interface else '0'
            stack_hostname = hostname.get('0', hostname.get(stack_nr))

            if stack_hostname is None:
                continue

            # Get VLAN info from lookup table
            vlan_info = vlan_lookup.get((stack_hostname, interface), {})
            entry = (
                stack_hostname,
                interface,
                name,
                i_types["type"].get(i_nr),
                i_types["poe_mode"].get(i_nr),
                i_types["poe_type"].get(i_nr),
                vlan_info.get('vlan_id'),
                vlan_info.get('vlan_name'),
                vlan_info.get('is_lag', False)
            )

            unique_interfaces.add(entry)

        # Generate interfaces to delete for stack members > 1
        # Skip for ArubaOS-CX: interfaces already have full member/slot/port paths
        if os_version and 'CX' not in os_version:
            for stack_nr, stack_name in hostname.items():
                if int(stack_nr) > 0:
                    for interface in i_types['type']:
                        unique_delete_interfaces.add((stack_name, interface))

    # Build final lists from sets
    data['device_interfaces'] = [
        {
            'hostname': h, 'interface': i, 'name': n, 'type': t,
            'poe_mode': p_mode, 'poe_type': p_type,
            'vlan_id': v_id, 'vlan_name': v_name, 'is_lag': is_lag
        }
        for h, i, n, t, p_mode, p_type, v_id, v_name, is_lag in unique_interfaces
    ]

    data['delete_interfaces'] = [
        {'hostname': h, 'interface': i}
        for h, i in unique_delete_interfaces
    ]

    return data


def tagged_vlans_json(config_files):
    """
    Create tagged (trunk) VLAN assignments for interfaces.

    Processes trunk interfaces and their allowed VLANs, handling both single
    switches and stacks. Supports multiple OS formats (ArubaOS/ProCurve and
    ArubaOS-CX).

    Args:
        config_files: List of config file paths (Path objects or strings)

    Returns:
        dict: Dictionary with 'tagged_vlans' key containing list of trunk assignments:
              - hostname: Device hostname
              - interface: Interface name/number
              - tagged_vlans: List of allowed VLANs with vlan_id and name

    Example:
        {'tagged_vlans': [
            {'hostname': 'rggw1004sp', 'interface': 'Trk1',
             'tagged_vlans': [
                 {'vlan_id': '10', 'name': 'ADMIN'},
                 {'vlan_id': '20', 'name': 'USERS'}
             ]}
        ]}
    """
    data = {'tagged_vlans': []}

    for t_file in config_files:
        hostnames = get_hostname(t_file)
        os_version = get_os_version(t_file)
        vlan_sets = get_tagged_vlans(t_file)
        lag_stacks = get_lag_stack(t_file)
        vlan_names = get_vlans_names(t_file)

        for vlan_id, interfaces_range in vlan_sets:
            # Get VLAN name, or use default if not defined
            vlan_name = vlan_names.get(vlan_id, f"VLAN {vlan_id}")
            if vlan_name == "VLAN 1":
                vlan_name = "DEFAULT_VLAN"

            # Parse interfaces based on OS version
            if os_version == 'ArubaOS-CX':
                # OS_CX format: "1/1/13,2/1/15,Lag 1" (full interface paths)
                interface_list = []
                for intf in interfaces_range.split(','):
                    intf = intf.strip()
                    if intf.startswith('Lag '):
                        interface_list.append(('0', intf.lower()))
                    elif '/' in intf:
                        # Format: "1/1/13" -> member 1, keep full interface name
                        parts = intf.split('/')
                        member = parts[0] if len(parts) >= 2 else '0'
                        interface_list.append((member, intf))
                    else:
                        interface_list.append(('0', intf))
            else:
                # ArubaOS/ProCurve format: use convert_interfaces_range
                interface_list = convert_interfaces_range(interfaces_range)

            vlan_stacks = set()

            # Determine which stack members have this VLAN on this interface
            for stack_nr, interface in interface_list:
                interface = str(interface)

                if '0' in hostnames:
                    # Single switch
                    vlan_stacks.add(hostnames['0'])
                    continue

                # Handle LAG interfaces
                if interface.startswith('lag '):
                    if os_version == 'ArubaOS-CX':
                        # For ArubaOS-CX stacks, LAGs are global - add all members
                        for member in hostnames.keys():
                            vlan_stacks.add(hostnames[member])
                    else:
                        # For ArubaOS stacks, find specific member(s) for this LAG
                        for nr in range(0, 20):
                            nr = str(nr)
                            if (interface, nr) in lag_stacks:
                                vlan_stacks.add(hostnames[nr])
                elif 'T' in interface:
                    # ArubaOS Trk interfaces
                    for nr in range(0, 20):
                        nr = str(nr)
                        if (interface, nr) in lag_stacks:
                            vlan_stacks.add(hostnames[nr])
                else:
                    # Regular physical interface
                    vlan_stacks.add(hostnames[str(stack_nr)])

            # Add VLAN to each hostname's interface (append if exists, create if new)
            for hostname in vlan_stacks:
                interface_exists = False
                for v_dict in data['tagged_vlans']:
                    if v_dict['hostname'] == hostname and v_dict['interface'] == interface:
                        # Update existing interface with new VLAN
                        v_dict['tagged_vlans'].append({'name': vlan_name, 'vlan_id': vlan_id})
                        interface_exists = True
                        break

                # Create new entry if interface doesn't exist
                if not interface_exists:
                    data['tagged_vlans'].append({
                        'hostname': hostname,
                        'interface': interface,
                        'tagged_vlans': [{'name': vlan_name, 'vlan_id': vlan_id}]
                    })

    return data

def ip_addresses_json(config_files):
    """
    Create IP address assignments for VLAN and management interfaces.

    Extracts IP addresses from VLAN interfaces (Layer 3 SVIs) and management
    interfaces from config files.

    Args:
        config_files: List of config file paths (Path objects or strings)

    Returns:
        dict: Dictionary with 'ip_addresses' key containing list of IP assignments:
              - hostname: Device hostname (single switch or first stack member)
              - ip: IP address with CIDR (e.g., '192.168.1.1/24')
              - vlan_id: VLAN ID (for VLAN interfaces) or None (for mgmt)
              - vlan_name: VLAN name
              - vlan: Boolean indicating if this is a VLAN interface
              - name: Interface name (e.g., 'vlan 10' or 'mgmt')

    Example:
        {'ip_addresses': [
            {'hostname': 'rggw1004sp', 'ip': '192.168.1.1/24',
             'vlan_id': '10', 'vlan_name': 'ADMIN', 'vlan': True, 'name': 'vlan 10'},
            {'hostname': 'rsgw7009p', 'ip': '10.0.0.1/24',
             'vlan_id': None, 'vlan_name': None, 'vlan': False, 'name': 'mgmt'}
        ]}
    """
    data = {'ip_addresses': []}

    for t_file in config_files:
        hostnames = get_hostname(t_file)
        hostname = hostnames['0'] if '0' in hostnames else hostnames['1']
        vlan_id, vlan_name, ip = get_ip_address(t_file)

        is_vlan = False
        name = None

        # Determine interface type
        if vlan_id == 'mgmt':
            name = 'mgmt'
            vlan_id = None  # Management interface has no VLAN ID
        elif vlan_id:
            is_vlan = True
            name = f'vlan {vlan_id}'

        data['ip_addresses'].append({
            'hostname': hostname,
            'ip': ip,
            'vlan_id': vlan_id,
            'vlan_name': vlan_name,
            'vlan': is_vlan,
            'name': name
        })

    return data

def modules_json(config_files):
    """
    Create modules JSON objects for modular switches.

    Extracts expansion module information from modular switches (e.g., Aruba
    5400R with line cards, 2920 with SFP modules).

    Args:
        config_files: List of config file paths (Path objects or strings)

    Returns:
        dict: Dictionary with 'modules' key containing list of module objects:
              - device: Device hostname (with stack number for stacks)
              - module_bay: Module slot identifier (e.g., 'A', 'B', '1')
              - type: Module type slug for NetBox
              - name: Module name (e.g., 'Module A', 'Uplink')
              - new_position: Full position including stack (e.g., '1/A' for stack member 1, slot A)

    Example:
        {'modules': [
            {'device': 'rscs0007-1', 'module_bay': 'A', 'type': 'aruba-j9993a',
             'name': 'Module A', 'new_position': '1/A'},
            {'device': 'rsgw1004sp', 'module_bay': 'A', 'type': 'aruba-j9729a',
             'name': 'Module A', 'new_position': 'A'}
        ]}
    """
    data = {'modules': []}
    m_types = module_types_dict()

    for t_file in config_files:
        modules = get_modules(t_file)

        for module in modules:
            # Build position string (with stack prefix if applicable)
            new_position = module['module']
            if module['stack'] != '0':
                new_position = f"{module['stack']}/{module['module']}"

            data['modules'].append({
                'device': module['hostname'],
                'module_bay': module['module'],
                'type': m_types[module['type'].lower()],
                'name': module['name'],
                'new_position': new_position
            })

    return data

#----- Debugging -------
def debug_locations_json(data_folder):
    print("\n== Debug: locations_json ==")

    print(yaml.dump(locations_json(config_files(data_folder))))

def debug_devices_json(data_folder):

    files = config_files(data_folder)
    devices_tags = ["switch"]
    output = yaml.dump(devices_json(files, device_type_slags, devices_tags))

    print("\n'device_json()' Output: for ", data_folder)
    print(output)

def debug_lags_json(data_folder):
    files = config_files(data_folder)
    devices_tags = ["switch"]
    output = yaml.dump(lags_json(files))

    print("\n'lags_json()' Output: for ", data_folder)
    print(output)

def debug_vlans_json(data_folder):
    files = config_files(data_folder)
    devices_tags = ["switch"]
    output = yaml.dump(vlans_json(files))

    print("\n'vlans_json()' Output: for ", data_folder)
    print(output)

def debug_device_interfaces_json(data_folder):
    files = config_files(data_folder)
    devices_tags = ["switch"]
    output = yaml.dump(device_interfaces_json(files))

    print("\n'device_interfaces_json()' Output: for ", data_folder)
    print(output)

def debug_untagged_vlans(data_folder):
    files = config_files(data_folder)
    devices_tags = ["switch"]
    output = yaml.dump(untagged_vlans(files))

    print("\n'untagged_vlans()' Output: for ", data_folder)
    print(output)

def debug_tagged_vlans_json(data_folder):
    files = config_files(data_folder)
    devices_tags = ["switch"]
    output = yaml.dump(tagged_vlans_json(files))

    print("\n'tagged_vlans_json()' Output: for ", data_folder)
    print(output)

def debug_ip_addresses_json(data_folder):
    files = config_files(data_folder)

    print("\n'ip_addresses_json()' Output: for ", data_folder)
    for dict in ip_addresses_json(files)['ip_addresses']:
        print(dict)

def debug_modules_json(data_folder):
    files = config_files(data_folder)
    output = yaml.dump(modules_json(files))

    print("\n'modules_json()' Output: for ", data_folder)
    print(output)

if __name__ == "__main__":
    print("\n=== Debuging ===")

    data_folders = [
        "aruba-8-ports",
        #"aruba-12-ports",
        #"aruba-48-ports",
        #"hpe-8-ports",
        "aruba-stack",
        #"aruba-stack-2920",
        #"aruba-stack-2930",
        #"aruba-modular",
        #"aruba-modular-stack",
        #"procurve-single",
        #"procurve-modular",

        #"aruba_6100",
        "aruba_6300",
    ]

    from std_functions import project_dir
    for folder in data_folders:
        data_folder = project_dir.joinpath('data', folder)

        print("\n Folder: ", data_folder)


        debug_locations_json(data_folder)
        debug_devices_json(data_folder)
        debug_device_interfaces_json(data_folder)
        debug_lags_json(data_folder)

        debug_vlans_json(data_folder)
        debug_untagged_vlans(data_folder)
        debug_tagged_vlans_json(data_folder)


        debug_ip_addresses_json(data_folder)

        debug_modules_json(data_folder)