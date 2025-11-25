#!/usr/bin/env  python3

#----- Return JSON Objects -----#

import re, os, sys, yaml 
from tabulate import tabulate

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sort_data import get_switch_type
from functions import serial_numbers, get_ip_address, get_device_role, get_vlans_names

from std_functions import device_type_slags, main_folder, config_files
from std_functions import convert_interfaces_range
from std_functions import get_os_version, get_hostname
from std_functions import get_lags, get_interface_names, get_vlans
from std_functions import get_untagged_vlans, get_tagged_vlans, get_lag_stack
from std_functions import get_modules
from std_functions import module_types_dict, modules_interfaces
from std_functions import convert_range

from std_functions import get_location, get_flor_name
from std_functions import get_parent_location, floor_slug, site_slug

from extra_functions import interfaces_types

# create the loactions json objects list
def locations_json(config_files):
    data = {"locations":[]}
    locations = set()
    rooms = {}
    sites = {}
    is_racks = {}

    for file in config_files:
        location = get_location(file)
        if not location: continue

        is_rack = False
        location, room, is_rack = location
        locations.add(location)
        rooms.update({location: room})
        sites.update({location: site_slug(file)})
        is_racks.update({location: is_rack})

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
            'is_rack': is_rack
        })

    return data

# return the devices json object
# Input: 
# 1. device type slags dict, for example:
# device_type_slags = { 
#     'J8697A': 'hpe-procurve-5406zl',
#     'J8698A': 'hpe-procurve-5412zl',
#     'J8770A': 'hpe-procurve-4204vl',
#     'J8773A': 'hpe-procurve-4208vl',
#     'J9850A': 'hpe-5406r-zl2',
#     'J9851A': 'hpe-5412r-zl2'
# }
# 2. General tags, for example:
# tags = "switch"
# tags = ["switch", "modular_switch"]
def devices_json(config_files, device_type_slags, tags):
    #data = {'devices':[]}
    data = {'devices':[], 'chassis':[]}
    serials = serial_numbers()

    for t_file in config_files:
        hostname = get_hostname(t_file)

        # get room location
        #location = get_location(t_file)
        location = None # it was decided to add them manually
        site = site_slug(t_file)

        if location: # Not None
            location, _, _ = location # ignore room and rack
            location = floor_slug(location)

        # update data for single switches 
        if '0' in hostname.keys():
            hostname = hostname['0']

            d_label = device_type_slags[get_switch_type(t_file)]

            serial = serials[hostname] if hostname in serials.keys() else None

            data['devices'].append({'name': hostname, #"location": location, 
                'device_role': get_device_role(t_file, hostname), 'device_type': d_label, 
                'site': site, 'tags': tags, 'serial':serial})
            continue

        # update data for stacks 
        clean_name = hostname['1'][:-2]
        d_label = device_type_slags[get_switch_type(t_file)['1']]


        master = hostname['1']

        data['chassis'].append({'name': clean_name, 'master': master})

        for h_name in hostname.values(): 
            vc_position = int(h_name[-1])
            vc_priority = 255 if vc_position == 1 else 64

            serial = serials[h_name] if h_name in serials.keys() else None

            if vc_position == 2: vc_priority = 128
            data['devices'].append({'name': h_name, # "location": location, 
                'device_role': get_device_role(t_file, clean_name), 'device_type': d_label, 
                'site': site, 'tags': tags, 'serial':serial,
                'virtual_chassis': clean_name, 'vc_position': vc_position, 
                'vc_priority': vc_priority
            })

    return data

# return lags and interfaces json objects
def lags_json(config_files):
    data = {'lags':[], 'lag_interfaces':[]}

    for t_file in config_files:
        hostnames = get_hostname(t_file)
        trk_lists = get_lags(t_file)

        if '0' in hostnames.keys(): # single switch
            hostname = hostnames['0']
        else:
            hostname = hostnames['1']

        for lag in trk_lists:
            if lag == []: continue
            #trk_name = lag['name'].title()
            trk_name = lag['name']
            if trk_name.startswith('t'):
                trk_name = trk_name.title()

            interfaces = lag['interfaces'].replace('-', ',').split(',')

            for interface in interfaces:
                if {'hostname': hostname, 'name': trk_name} not in data['lags']:
                    data['lags'].append({'hostname': hostname, 'name': trk_name})

                data['lag_interfaces'].append({'hostname': hostname, 'interface': interface, 'lag_name': trk_name})

    return data

def vlans_json(config_files):
    # collect unique vlans
    vlans = set()

    for t_file in config_files:
        for vlan in get_vlans(t_file):
            vlans.add(vlan)

    # save them to a json dict
    data = {'vlans':[]}
    for vlan in vlans:
        data['vlans'].append({'name': vlan[1], 'id': vlan[0]})

    return data

def untagged_vlans(config_files):
    data = {'untagged_vlans': []}

    for t_file in config_files:
        hostname_map = get_hostname(t_file)

        # Get untagged and tagged vlan sets
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
            if vlan_name == "VLAN 1": vlan_name = "DEFAULT_VLAN"
            interfaces = convert_interfaces_range(int_range)

            for stack_nr, interface in interfaces:
                if is_lag is None:
                    is_lag = interface in lags

                # For lag interfaces in stacks, correct stack_nr
                if is_stack and 'T' in interface:
                    for nr in range(1, 20):
                        if (interface, str(nr)) in lag_stacks:
                            stack_nr = str(nr)
                            break

                hostname = (
                    hostname_map
                    if not is_stack else hostname_map.get(stack_nr, f"unknown-{stack_nr}")
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
    data = {'device_interfaces': [], 'delete_interfaces': []}
    unique_interfaces = set()
    unique_delete_interfaces = set()

    # Get untagged VLAN data first
    vlan_data = untagged_vlans(config_files)['untagged_vlans']

    # Normalize hostnames to strings and build a proper lookup
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
        prefix = '1/1/' if os_version == 'ArubaOS-CX' else ''

        # Process module interfaces
        for module in get_modules(t_file):
            interfaces_dict = modules_interfaces(module['type'], module['module'])
            for keys_range, type_value in interfaces_dict['types'].items():
                for key in convert_range(keys_range):
                    i_types["type"][key] = type_value
                    i_types["poe_type"][key] = interfaces_dict['poe_types'].get(keys_range)
                    i_types["poe_mode"][key] = interfaces_dict['poe_mode'].get(keys_range)

        # Process normal interfaces
        for interface, name in get_interface_names(t_file):
            if interface == "mgmt":
                continue

            if interface.lower().startswith('vlan '):
                i_types["type"][interface] = "virtual"

            if interface.lower().startswith('lag '):
                i_types["type"][interface] = "lag"

            i_nr = interface.split('/')[-1]
            stack_nr = interface.split('/')[0] if '/' in interface else '0'
            stack_hostname = hostname.get('0', hostname.get(stack_nr))

            if stack_hostname is None:
                continue

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

        # Interfaces to delete
        # Skip for OS-CX: interfaces already have full member/slot/port paths
        if os_version and 'CX' not in os_version:
            for stack_nr, stack_name in hostname.items():
                if int(stack_nr) > 0:
                    for interface in i_types['type']:
                        unique_delete_interfaces.add((stack_name, interface))

    # Build final lists
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
    data = {'tagged_vlans':[]}

    for t_file in config_files:
        hostnames = get_hostname(t_file)
        os_version = get_os_version(t_file)

        # get list of tagged vlan tuples like:
        # iOS: [('5', 'A23-A24,B10,B20,F1,F4'), ('9', 'A23-A24,B10,B20,F1,F4')]
        # OS_CX: [('341', '1/13,2/15,Lag 1'), ('350', '1/13')]
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
                        # LAG interface
                        interface_list.append(('0', intf.lower()))
                    elif '/' in intf:
                        # Format: "1/1/13" -> member 1, keep full interface name
                        parts = intf.split('/')
                        member = parts[0] if len(parts) >= 2 else '0'
                        interface_list.append((member, intf))
                    else:
                        # Single switch, just port number
                        interface_list.append(('0', intf))
            else:
                # iOS format: use existing convert_interfaces_range
                interface_list = convert_interfaces_range(interfaces_range)

            vlan_stacks = set()

            # Iterate through all the interfaces that belong to a vlan
            for stack_nr, interface in interface_list:
                interface = str(interface)

                if '0' in hostnames.keys():
                    # Single switch
                    vlan_stacks.add(hostnames['0'])
                    continue

                # Find stack number for lags
                if interface.startswith('lag '):
                    if os_version == 'ArubaOS-CX':
                        # For OS_CX stacks, LAGs are global - add all members
                        for member in hostnames.keys():
                            vlan_stacks.add(hostnames[member])
                    else:
                        # For iOS stacks, find specific member(s) for this LAG
                        for nr in range(0,20):
                            nr = str(nr)
                            if (interface, nr) in lag_stacks:
                                vlan_stacks.add(hostnames[nr])
                elif 'T' in interface:
                    # iOS Trk interfaces
                    for nr in range(0,20):
                        nr = str(nr)
                        if (interface, nr) in lag_stacks:
                            vlan_stacks.add(hostnames[nr])
                else:
                    # Regular physical interface
                    vlan_stacks.add(hostnames[str(stack_nr)])

            for hostname in vlan_stacks:
                interface_exists = False # flag to notify that the interface exist in data['tagged_vlans'][hostname]
                for v_dict in data['tagged_vlans']:
                    if v_dict['hostname'] == hostname and v_dict['interface'] == interface:
                        # update the interface list with vlan data
                        v_dict['tagged_vlans'].append({'name': vlan_name, 'vlan_id': vlan_id})
                        interface_exists = True # update flag
                        break # exit the loop with updated flag

                # create a new dictionary entry if the interface vlan list does not exists
                if not interface_exists:
                    data['tagged_vlans'].append({ 'hostname': hostname, 'interface': interface,
                        'tagged_vlans': [{'name': vlan_name, 'vlan_id': vlan_id}] })
                    interface_exists = False
    return data

def ip_addresses_json(config_files):
    data = {'ip_addresses':[]}

    for t_file in config_files:
        hostnames = get_hostname(t_file)

        hostname = hostnames['0'] if '0' in hostnames.keys() else hostnames['1']

        vlan_id, vlan_name, ip = get_ip_address(t_file)

        is_vlan = False
        name = None

        # Check if this is a management interface
        if vlan_id == 'mgmt':
            # Management interface
            name = 'mgmt'
            vlan_id = None  # Reset vlan_id to None for mgmt interfaces
        elif vlan_id:
            # VLAN interface
            is_vlan = True
            name = 'vlan ' + vlan_id

        data['ip_addresses'].append({
            'hostname': hostname,
            'ip': ip,
            'vlan_id': vlan_id,
            'vlan_name': vlan_name,
            'vlan': is_vlan,
            'name': name
        })

    return data

# return the modules json object
def modules_json(config_files):
    data = {'modules':[]}
    m_types = module_types_dict()

    for t_file in config_files:
        modules = get_modules(t_file)

        for module in modules:
            new_position = module['module']
            if module['stack'] != '0':
                new_position = module['stack'] + '/' + module['module']

            data['modules'].append({'device': module['hostname'], 'module_bay': module['module'], 
                'type': m_types[module['type'].lower()], 
                'name': module['name'], 'new_position': new_position})
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

        "aruba_6100",
        "aruba_6300",
    ]

    for folder in data_folders:
        data_folder = os.path.join(main_folder, "data", folder)

        print("\n Folder: ", data_folder)


        #debug_locations_json(data_folder)
        debug_devices_json(data_folder)
        #debug_device_interfaces_json(data_folder)
        #debug_lags_json(data_folder)

        #debug_vlans_json(data_folder)
        #debug_untagged_vlans(data_folder)
        #debug_tagged_vlans_json(data_folder)


        #debug_ip_addresses_json(data_folder)

        #debug_modules_json(data_folder)