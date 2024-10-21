#!/usr/bin/env python3

#----- Return JSON Objects for Aruba OS-CX -----#

import re, os, yaml
from std_functions import main_folder, config_files, convert_range
from std_functions import device_type, serial_numbers
from std_functions import get_hostname, get_site
from std_functions import get_location, get_room_location

from extra_functions import get_uplink_vlan, get_interfaces_config
from extra_functions import get_looback_interface, get_lag_interfaces
from extra_functions import get_interfaces, get_vlan_names, interfaces_types

# create devices json objects list
def devices_json(config_files, type_slags, tags):
    data = {"devices":[], "chassis":[]}
    rsm_vlans = ['102','202','302']

    for file in config_files:

        location,room = get_location(file)
        location = get_room_location(location)
        
        site = get_site(file)
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

            data["devices"].append({"name": hostname, "location": location, "site": site, "device_role": device_role, 
                "device_type": d_type, "serial": serial_numbers()[hostname], "tags": tags })

    return data

def device_interfaces_json(config_files):
    data = {"device_interfaces":[]}

    for f in config_files:
        interfaces = get_interfaces_config(f)["physical"].keys()

        hostnames = get_hostname(f)
        if '0' in hostnames.keys():
            hostnames['1'] = hostnames['0']

        i_types = interfaces_types(f)

        for value in interfaces:
            _, interface = value.split()

            stack_nr, _, pos_nr = interface.split('/')

            poe_mode = i_types['poe_mode'][pos_nr] if i_types['poe_mode'] else None
            poe_type = i_types['poe_type'][pos_nr] if i_types['poe_type'] else None
            
            data["device_interfaces"].append({
                'device': hostnames[stack_nr], 'type': i_types['type'][pos_nr],
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

# create lags json objects list
def lags_json(config_files):
    data = {"lags":[], "lag_interfaces":[]}

    for config_file in config_files:

        hostnames = get_hostname(config_file)
        hostname = hostnames['0'] if '0' in hostnames.keys() else hostnames['1']

        lag_interfaces = get_lag_interfaces(config_file).items()
        if not lag_interfaces:
            continue
        for lag, interfaces in lag_interfaces:
            data["lags"].append({"hostname": hostname, "lag_id": lag})
            for interface in interfaces:
                data["lag_interfaces"].append({"hostname": hostname, "lag_id": lag, "interface": interface})

    return data

def interfaces_json(config_files):
    data = {"interfaces":[], "interfaces_vlan":[]}

    for config_file in config_files:
        hostnames = get_hostname(config_file)
        interfaces = get_interfaces(config_file)
        vlan_names = get_vlan_names(config_file)

        hostname = hostnames['0'] if '0' in hostnames.keys() else hostnames['1']

        i_types = interfaces_types(config_file)

        for interface in interfaces:
            name = interface["name"]
            description = interface["description"]
            vlan = interface["vlan"]

            i_type = None

            if 'lag' in name:
                i_type = 'lag'

            if 'vlan' in name:
                i_type = 'virtual'

            if '/' in name:
                _, _, i_pos = name.split('/')
                i_type = i_types["type"][i_pos] 

            if description:
                data["interfaces"].append({"hostname":hostname, "interface":name, "description":description, "type": i_type})

            if vlan:
                data["interfaces_vlan"].append({"hostname":hostname, "interface":interface["name"], "vlan_id":vlan, 
                    "vlan_name":vlan_names[vlan], "vlan_mode":interface["vlan_mode"], "type": i_type})
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

def debug_lags_json(data_folder):
    files = config_files(data_folder)
    output = yaml.dump(lags_json(files))

    print("\n'lags_json()' Output: for ", data_folder)
    print(output)

def debug_interfaces_json(data_folder):
    files = config_files(data_folder)
    output = yaml.dump(interfaces_json(files))

    print("\n'interfaces_json()' Output: for ", data_folder)
    print(output)

if __name__ == "__main__":
    print("\n=== Aruba 6100 ===")
    data_folder = main_folder + "/data/aruba_6100/"

    config_file = data_folder + "rggw1018bp"

    #debug_devices_json(data_folder)
    debug_device_interfaces_json(data_folder)
    #debug_ip_addresses_json(data_folder)
    #debug_lags_json(data_folder)
    #debug_interfaces_json(data_folder)

    print("\n=== Aruba 6300 ===")
    data_folder = main_folder + "/data/aruba_6300/"

    config_file = data_folder + "rgcs0006"

    #debug_devices_json(data_folder)
    debug_device_interfaces_json(data_folder)
    #debug_ip_addresses_json(data_folder)
    #debug_lags_json(data_folder)
    #debug_interfaces_json(data_folder)
