#!/usr/bin/env python3

#----- Return JSON Objects for Aruba OS-CX -----#

import re, os, yaml
from std_functions import main_folder, config_files, convert_range
from std_functions import device_type, serial_numbers
from std_functions import get_hostname, get_site

from extra_functions import get_location, get_room_location
from extra_functions import get_uplink_vlan, get_interfaces_config
from extra_functions import get_looback_interface


# create devices json objects list
def devices_json(config_files, type_slags, tags):
    data = {"devices":[], "chassis":[]}
    rsm_vlans = ['102','202','302']

    for file in config_files:

        location,room = get_location(file)
        location = get_room_location(location)

        uplink_vlan = get_uplink_vlan(file)
        
        device_role = "bueroswitch" if uplink_vlan in rsm_vlans else "access-layer-switch"

        hostnames = get_hostname(file)
        clean_name = None

        if '0' not in hostnames.keys():
            hostname = hostnames['1']
            clean_name = hostname[:-2]
            data['chassis'].append({'master': hostname, 'name': clean_name})

        for key in hostnames.keys():
            hostname = hostnames[key]

            if not clean_name:
                clean_name = hostname

            if hostname[2:4] == "cs":
                device_role = "distribution-layer-switch"

            d_type = type_slags[device_type(clean_name)]

            data["devices"].append({"name": hostname, "location": location, "site": get_site(clean_name), "device_role": device_role, 
                "device_type": d_type, "serial": serial_numbers()[hostname], "tags": tags })

    return data

def device_interfaces_json(config_files):
    data = {"device_interfaces":[]}

    types = {
        "JL658A": {
            "1-24": "10gbase-x-sfpp",
            "25-28": "25gbase-x-sfp28"
        },
        "JL679A": {
            "1-14": "1000base-t",
            "15-16": "10gbase-x-sfpp"
        }
    }
    poe_types = {
        "JL679A": {
            "1-14": "type2-ieee802.3at",
            "15-16": None
        }
    }
    poe_modes = {
        "JL679A": {
            "1-14": "pd",
            "15-16": None
        }
    }

    poe_type = poe_mode = None

    for f in config_files:
        interfaces = get_interfaces_config(f)["physical"].keys()

        hostnames = get_hostname(f)

        if '0' in hostnames.keys():
            clean_name = hostnames['1'] = hostnames['0']
        else:
            clean_name = hostnames['1'][:-2]

        d_type = device_type(clean_name).split('_')[0]

        # create interface type dictionary
        i_types = {}
        if d_type in types:
            for key, value in types[d_type].items():
                for i_nr in convert_range(key):
                    i_types[str(i_nr)] = value

        # create poe interface dictionaries
        i_poe_types = {} 
        if d_type in poe_types:
            for key, value in poe_types[d_type].items():
                for i_nr in convert_range(key):
                    i_poe_types[str(i_nr)] = value

        i_poe_modes = {}
        if d_type in poe_modes:
            for key, value in poe_modes[d_type].items():
                for i_nr in convert_range(key):
                    i_poe_modes[str(i_nr)] = value

        for value in interfaces:
            _, interface = value.split()

            stack_nr, _, pos_nr = interface.split('/')

            poe_mode = i_poe_modes[pos_nr] if i_poe_modes else None
            poe_type = i_poe_types[pos_nr] if i_poe_types else None
            
            data["device_interfaces"].append({
                'device': hostnames[stack_nr], 'type': i_types[pos_nr],
                'interface': interface, 'stack_nr': stack_nr, 
                'poe_mode': poe_mode, 'poe_type': poe_type })

    return data

# create ip_addresses json objects list
def ip_addresses_json(config_files):
    data = {"ip_addresses":[]}

    for config_file in config_files:
        hostnames = get_hostname(config_file)
        loopback_interface = get_looback_interface(config_file)

        vlan = True # Flag that shows that loopback interface is a vlan
        if len(loopback_interface) == 2:
            vlan = False

        hostname = hostnames['0'] if '0' in hostnames.keys() else hostnames['1']
        name = "vlan " + loopback_interface[0] if vlan else loopback_interface[0]
        description = loopback_interface[2] if vlan else loopback_interface[0]

        data["ip_addresses"].append({"hostname": hostname, "vlan": vlan, "ip": loopback_interface[1], "name": name, "description": description })

    return data

#==== Debug functions ====
def debug_devices_json(data_folder):
    device_type_slags = {
      "JL679A": "hpe-aruba-6100-12g-poe4-2sfpp",
      "JL658A_stack": "hpe-aruba-6300m-24sfpp-4sfp56"
    }

    files = config_files(data_folder)
    devices_tags = ["switch"]
    output = yaml.dump(devices_json(files, device_type_slags, devices_tags))

    print("\n'device_json()' Output: for ", data_folder)
    print(output)

def debug_device_interfaces_json(data_folder):
    files = config_files(data_folder)
    output = yaml.dump(device_interfaces_json(files))

    print("\n'device_interfaces_json()' Output: for ", data_folder)
    print(output)

def debug_ip_addresses_json(data_folder):
    files = config_files(data_folder)
    output = yaml.dump(ip_addresses_json(files))

    print("\n'ip_addreses_json()' Output: for ", data_folder)
    print(output)

if __name__ == "__main__":
    print("\n=== Aruba 6100 ===")
    data_folder = main_folder + "/data/aruba_6100/"

    config_file = data_folder + "rggw1018bp"

    #debug_devices_json(data_folder)
    #debug_device_interfaces_json(data_folder)
    debug_ip_addresses_json(data_folder)

    print("\n=== Aruba 6300 ===")
    data_folder = main_folder + "/data/aruba_6300/"

    config_file = data_folder + "rgcs0006"

    #debug_devices_json(data_folder)
    #debug_device_interfaces_json(data_folder)
    debug_ip_addresses_json(data_folder)