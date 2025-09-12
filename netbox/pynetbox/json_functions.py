#!/usr/bin/env  python3

#----- Return JSON Objects -----#

import re, os, yaml
from tabulate import tabulate

from sort_data import get_switch_type

from std_functions import device_type_slags, main_folder, config_files
from std_functions import serial_numbers, convert_interfaces_range
from std_functions import get_os_version, get_hostname, get_device_role
from std_functions import get_trunks, get_interface_names, get_vlans
from std_functions import get_untagged_vlans, get_tagged_vlans, get_vlans_names, get_trunk_stack
from std_functions import get_ip_address, get_modules, module_types_dict
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
        location = get_location(t_file)
        site = site_slug(t_file)

        if location: # Not None
            location, _, _ = location # ignore room and rack
            location = floor_slug(location)

        # update data for single switches 
        if '0' in hostname.keys():
            hostname = hostname['0']

            d_label = device_type_slags[get_switch_type(t_file)]

            serial = serials[hostname] if hostname in serials.keys() else None

            data['devices'].append({'name': hostname, "location": location, 
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
            data['devices'].append({'name': h_name, "location": location, 
                'device_role': get_device_role(t_file, clean_name), 'device_type': d_label, 
                'site': site, 'tags': tags, 'serial':serial,
                'virtual_chassis': clean_name, 'vc_position': vc_position, 
                'vc_priority': vc_priority
            })

    return data

# return trunks and interfaces json objects
def trunks_json(config_files):
    data = {'trunks':[], 'trunk_interfaces':[]}

    for t_file in config_files:
        hostnames = get_hostname(t_file)
        trk_lists = get_trunks(t_file)

        if '0' in hostnames.keys(): # single switch
            hostname = hostnames['0']
        else:
            hostname = hostnames['1']

        for trunk in trk_lists:
            if trunk == []: continue
            trk_name = trunk['name'].title()

            interfaces = trunk['interfaces'].replace('-', ',').split(',')

            for interface in interfaces:
                if {'hostname': hostname, 'name': trk_name} not in data['trunks']:
                    data['trunks'].append({'hostname': hostname, 'name': trk_name})

                data['trunk_interfaces'].append({'hostname': hostname, 'interface': interface, 'trunk_name': trk_name})

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
        trunk_stacks = get_trunk_stack(t_file) if is_stack else None

        for vlan_id, int_range, is_trunk in untagged_sets:
            vlan_name = vlan_names.get(vlan_id, f"VLAN {vlan_id}")
            if vlan_name == "VLAN 1": vlan_name = "DEFAULT_VLAN"
            interfaces = convert_interfaces_range(int_range)

            for stack_nr, interface in interfaces:
                if is_trunk is None:
                    is_trunk = interface in lags

                # For trunk interfaces in stacks, correct stack_nr
                if is_stack and 'T' in interface:
                    for nr in range(1, 20):
                        if (interface, str(nr)) in trunk_stacks:
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
                    'is_trunk': is_trunk
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
                'is_trunk': entry.get('is_trunk', False)
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
                i_types["type"][interface] = "Virtual"

            if interface.lower().startswith('lag '):
                i_types["type"][interface] = "LAG"

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
                vlan_info.get('is_trunk', False)
            )

            unique_interfaces.add(entry)

        # Interfaces to delete
        for stack_nr, stack_name in hostname.items():
            if int(stack_nr) > 0:
                for interface in i_types['type']:
                    unique_delete_interfaces.add((stack_name, prefix + interface))

    # Build final lists
    data['device_interfaces'] = [
        {
            'hostname': h, 'interface': i, 'name': n, 'type': t,
            'poe_mode': p_mode, 'poe_type': p_type,
            'vlan_id': v_id, 'vlan_name': v_name, 'is_trunk': is_trunk
        }
        for h, i, n, t, p_mode, p_type, v_id, v_name, is_trunk in unique_interfaces
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

        # get list of tagged vlan tuples like:
        # [('5', 'A23-A24,B10,B20,F1,F4'), ('9', 'A23-A24,B10,B20,F1,F4'), ('50', 'A23-A24,B10,B20,F1,F4')]
        vlan_sets = get_tagged_vlans(t_file)

        trunk_stacks = get_trunk_stack(t_file)
        for vlan_id, interfaces_range in vlan_sets:
            vlan_name = get_vlans_names(t_file)[vlan_id]

            vlan_stacks = set()

            # iterate through all the interfaces that belong to a vlan
            for stack_nr, interface in convert_interfaces_range(interfaces_range):
                
                interface = str(interface)

                if '0' in hostnames.keys():
                    vlan_stacks.add(hostnames['0'])
                    continue

                # Find stack number for Trunks
                if 'T' in interface: 
                    for nr in range(0,20):
                        nr = str(nr)
                        if (interface, nr) in trunk_stacks:
                            vlan_stacks.add(hostnames[nr])
                else: 
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
        if vlan_id:
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

            data['modules'].append({'device': module['hostname'], 'module_bay': module['module'], 'type': m_types[module['type'].lower()], 
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

def debug_trunks_json(data_folder):
    files = config_files(data_folder)
    devices_tags = ["switch"]
    output = yaml.dump(trunks_json(files))

    print("\n'trunks_json()' Output: for ", data_folder)
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
        #"/data/aruba-8-ports/",
        #"/data/aruba-12-ports/",
        # "/data/aruba-48-ports/"
         "/data/hpe-8-ports/",
        # "/data/aruba-stack/"
        #"/data/aruba-stack-2920/"
         "/data/aruba-stack-2930/",
        # "/data/aruba-modular/"
        # "/data/aruba-modular-stack/"
        # "/data/procurve-single/"
        # "/data/procurve-modular/"

        #"/data/aruba_6100/",
        #"/data/aruba_6300/"
    ]

    for folder in data_folders:
        data_folder = main_folder + folder

        print("\n Folder: ", data_folder)


        debug_locations_json(data_folder)
        #debug_devices_json(data_folder)
        #debug_device_interfaces_json(data_folder)
        #debug_trunks_json(data_folder)

        #debug_vlans_json(data_folder)
        #debug_untagged_vlans(data_folder)
        #debug_tagged_vlans_json(data_folder)


        #debug_ip_addresses_json(data_folder)

        #debug_modules_json(data_folder)