#!/usr/bin/env  python3

#----- Return JSON Objects -----#

import re, os, yaml
from tabulate import tabulate

from std_functions import this_folder, main_folder, config_files
from std_functions import device_type, serial_numbers, convert_interfaces_range
from std_functions import get_hostname, get_device_role, get_site
from std_functions import get_trunks, get_interface_names, get_vlans
from std_functions import get_untagged_vlans, get_vlans_names, get_trunk_stack
from std_functions import get_ip_address

from extra_functions import get_location, get_room_location, get_flor_name
from extra_functions import get_parent_location

# create the loactions json objects list
def locations_json(config_files):
    data = {"locations":[]}
    locations = set()
    rooms = {}
    hostnames = {}

    for file in config_files:
        location = get_location(file)
        if not location: continue

        location,room = location
        locations.add(location)
        rooms.update({location: room})

        h_names = get_hostname(file)
        hostname = h_names['0'] if '0' in h_names.keys() else h_names['1']
        hostnames.update({location: hostname})


    for location in locations:
        room = rooms[location]
        building = location.split(".")[0]
        flor_tuple = get_flor_name(room)

        site = get_site(hostnames[location])

        data["locations"].append({"name": building + "." + flor_tuple[0] + " - " + flor_tuple[1], "site": site, "parent_location": get_parent_location(location)})

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
    for t_file in config_files:
        hostname = get_hostname(t_file)

        # get room location
        location = get_location(t_file)

        if location: # Not None
            location, _ = location # ignore room
            location = get_room_location(location)

        # update data for single switches 
        if '0' in hostname.keys():
            hostname = hostname['0']

            d_label = device_type_slags[device_type(hostname)]
            data['devices'].append({'name': hostname, "location": location, 'device_role': get_device_role(t_file, hostname), 'device_type': d_label,
                'site': get_site(hostname), 'tags': tags, 'serial':serial_numbers()[hostname]})
            continue

        # update data for stacks 
        clean_name = hostname['1'][:-2]
        d_label = device_type_slags[device_type(clean_name)]

        master = hostname['1']

        data['chassis'].append({'name': clean_name, 'master': master})

        for h_name in hostname.values(): 
            vc_position = int(h_name[-1])
            vc_priority = 255 if vc_position == 1 else 128
            data['devices'].append({'name': h_name, "location": location, 'device_role': get_device_role(t_file, clean_name), 'device_type': d_label, 
                'site': get_site(clean_name), 'tags': tags, 'serial':serial_numbers()[h_name],
                'virtual_chassis': clean_name, 'vc_position': vc_position, 'vc_priority': vc_priority
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

def interface_names_json(config_files):
    data = {'interface_names':[]}

    for t_file in config_files:
        hostname = get_hostname(t_file)

        for i_tuple in get_interface_names(t_file):
            interface, name = i_tuple

            if '0' in hostname.keys():
                stack_hostname = hostname['0']

            else:
                stack_nr, _ = interface.split('/')
                stack_hostname = hostname[stack_nr]

            if {'hostname': stack_hostname, 'interface': interface, 'name': name} not in data['interface_names']:
                data['interface_names'].append({'hostname': stack_hostname, 'interface': interface, 'name': name})

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

def untagged_vlans_json(config_files):
    data = {'untagged_vlans':[]}

    for t_file in config_files:
        hostname = get_hostname(t_file)
        vlan_sets = get_untagged_vlans(t_file)
        # ex: [('1', 'B10-B13,B15-B20,E2,E4,E6,E8,F2,F4,F6,F8'), ('50', 'A2-A24'), ('101', 'A1,B2,B9,B14,B21-B24,E5,E7,F5,F7,Trk1,Trk20-Trk24')]
        # ex2: [('1', '2/49-2/50'), ('50', '1/2-1/6,1/8,1/10-1/12,1/15,1/19,1/22-1/24,1/27-1/28,1/30-1/32,1/35-1/36,1/39-1/40,1/43-1/44,1/46-1/48,2/3,2/7,2/10,2/12,2/14-2/20,2/22,2/24-2/48')]

        # update data for single switches 
        if '0' in hostname.keys():
            hostname = hostname['0']

            for vlan_id, interfaces_range in vlan_sets:
                vlan_name = get_vlans_names(t_file)[vlan_id]
                for _, interface in convert_interfaces_range(interfaces_range):
                    data['untagged_vlans'].append({'hostname': hostname, 'interface': interface,
                        'vlan_id': vlan_id, 'vlan_name': vlan_name})
                continue
            continue
        
        # update data for stacks 
        trunk_stacks = get_trunk_stack(t_file)
        for vlan_id, interfaces_range in vlan_sets:
            vlan_name = get_vlans_names(t_file)[vlan_id]

            for stack_nr, interface in convert_interfaces_range(interfaces_range):

                # Find stack number for Trunks
                if 'T' in interface: 
                    for nr in range(1,20):
                        if (interface, str(nr)) in trunk_stacks:
                            stack_nr = str(nr)
                            break

                data['untagged_vlans'].append({'hostname': hostname[stack_nr], 'interface': str(interface),
                    'vlan_id': vlan_id, 'vlan_name': vlan_name})

    return data

def tagged_vlans_json(config_files):
    data = {'tagged_vlans':[]}

    for t_file in config_files:
        hostnames = get_hostname(t_file)

        # get list of tagged vlan tuples like:
        # [('5', 'A23-A24,B10,B20,F1,F4'), ('9', 'A23-A24,B10,B20,F1,F4'), ('50', 'A23-A24,B10,B20,F1,F4')]
        vlan_sets = get_untagged_vlans(t_file, 'tagged')

        trunk_stacks = get_trunk_stack(t_file)
        for vlan_id, interfaces_range in vlan_sets:
            vlan_name = get_vlans_names(t_file)[vlan_id]

            # iterate through all the interfaces that belong to a vlan
            for stack_nr, interface in convert_interfaces_range(interfaces_range):
                
                interface = str(interface)
                vlan_stacks = []

                if '0' in hostnames.keys():
                    vlan_stacks.append(hostnames['0'])

                # Find stack number for Trunks
                if 'T' in interface: 
                    for nr in range(0,20):
                        nr = str(nr)
                        if (interface, nr) in trunk_stacks:
                            vlan_stacks.append(hostnames[nr])
                else: 
                    vlan_stacks.append(hostnames[str(stack_nr)])

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

        data['ip_addresses'].append({'hostname': hostname, 'ip': ip, 'vlan_id': vlan_id, 'vlan_name': vlan_name})
    
    return data

#----- Debugging -------
def debug_locations_json(data_folder):
    print("\n== Debug: locations_json ==")

    print(locations_json(config_files(data_folder)))

def debug_devices_json(data_folder):
    device_type_slags = {
      'J9623A': 'hpe-aruba-2620-24',
      'J9772A': 'hpe-aruba-2530-48g-poep',
      'J9853A': 'hpe-aruba-2530-48g-poep-2sfpp',
      'JL256A_stack': "hpe-aruba-2930f-48g-poep-4sfpp",
      'JL075A_stack': 'hpe-aruba-3810m-16sfpp-2-slot-switch',
      'JL693A_stack': "hpe-aruba-2930f-12g-poep-2sfpp",
      'JL322A_stack': 'hpe-aruba-2930m-48g-poep'
    }

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

def debug_interface_names_json(data_folder):
    files = config_files(data_folder)
    devices_tags = ["switch"]
    output = yaml.dump(interface_names_json(files))

    print("\n'interface_names_json()' Output: for ", data_folder)
    print(output)

def debug_untagged_vlans_json(data_folder):
    files = config_files(data_folder)
    devices_tags = ["switch"]
    output = yaml.dump(untagged_vlans_json(files))

    print("\n'untagged_vlans_json()' Output: for ", data_folder)
    print(output)

def debug_tagged_vlans_json(data_folder):
    files = config_files(data_folder)
    devices_tags = ["switch"]
    output = yaml.dump(tagged_vlans_json(files))

    print("\n'tagged_vlans_json()' Output: for ", data_folder)
    print(output)

def debug_ip_addresses_json(data_folder):
    files = config_files(data_folder)
    devices_tags = ["switch"]
    output = yaml.dump(ip_addresses_json(files))

    print("\n'ip_addresses_json()' Output: for ", data_folder)
    print(output)

if __name__ == "__main__":
    print("\n=== Singles JSON ===")
    data_folder = main_folder + "/data/hpe-48-ports/"

    debug_locations_json(data_folder)
    #debug_devices_json(data_folder)
    #debug_trunks_json(data_folder)
    #debug_interface_names_json(data_folder)
    #debug_vlans_json(data_folder)
    #debug_untagged_vlans_json(data_folder)
    #debug_tagged_vlans_json(data_folder)
    #debug_ip_addresses_json(data_folder)

    print("\n=== Stacking JSON ===")
    #data_folder = main_folder + "/data/aruba-stack/"
    data_folder = main_folder + "/data/aruba-stack-2930/"

    #debug_devices_json(data_folder)
    #debug_trunks_json(data_folder)
    #debug_interface_names_json(data_folder)
    #debug_vlans_json(data_folder)
    #debug_untagged_vlans_json(data_folder)
    #debug_tagged_vlans_json(data_folder)
    #debug_ip_addresses_json(data_folder)

    print("\n=== Aruba 6100 ===")
    #data_folder = main_folder + "/data/aruba_6100/"
    data_folder = main_folder + "/data/aruba_6100/"

    print("\n=== Aruba 6300 ===")
    #data_folder = main_folder + "/data/aruba_6100/"
    data_folder = main_folder + "/data/aruba_6300/"