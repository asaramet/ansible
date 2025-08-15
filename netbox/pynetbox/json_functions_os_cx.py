#!/usr/bin/env python3

#----- Return JSON Objects for Aruba OS-CX -----#

import re, os, yaml
from std_functions import main_folder, config_files, convert_range
from std_functions import device_type, serial_numbers
from std_functions import get_hostname, get_site
from std_functions import get_location, get_room_location

from extra_functions import get_uplink_vlan, get_interfaces_config
from extra_functions import get_loopback_interface, get_lag_interfaces
from extra_functions import get_interfaces, get_vlan_names, interfaces_types

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

    debug_lags_json(data_folder)
    #debug_interfaces_json(data_folder)

    print("\n=== Aruba 6300 ===")
    data_folder = main_folder + "/data/aruba_6300/"

    config_file = data_folder + "rgcs0006"

    debug_lags_json(data_folder)
    #debug_interfaces_json(data_folder)
