#!/usr/bin/env python3

# Collect Aruba 6xxx data and create a yaml configs file 

import re, os, yaml
from tabulate import tabulate
from std_functions import main_folder, config_files

from json_functions import locations_json, vlans_json

from json_functions_os_cx import devices_json, device_interfaces_json
from json_functions_os_cx import ip_addresses_json, lags_json

#from std_functions import get_hostname, get_site
#from std_functions import get_hostname

#from extra_functions import get_flor_name, get_parent_location
#from extra_functions import get_location, get_room_location
#from extra_functions import get_interfaces_config
#from extra_functions import get_vlans
#from std_functions import get_vlans





# collect all the vlans from the config files
def collect_vlans(config_files):
    vlans = {}
    for config_file in config_files:
        vlan_ids = vlans.keys()
        #print(vlan_ids)
        collected_vlans = get_vlans(config_file)
        for vlan_id in collected_vlans:
            if vlan_id not in vlan_ids:
                vlans[vlan_id] = collected_vlans[vlan_id]
    return vlans

#def vlans_json(config_files):
#    data = {'vlans':[]}

#    collected_vlans = collect_vlans(config_files)
#    for vlan_id in collected_vlans:
#        name = str(collected_vlans[vlan_id]["name"])
#        data['vlans'].append({'vlan_id': vlan_id, 'name': name})

#    return data

def interfaces_json(config_files):
    data = {"interfaces":[], "interfaces_vlan":[]}

    for config_file in config_files:
        hostname = get_hostname(config_file)['0']
        interfaces = get_interfaces(config_file)
        vlan_names = get_vlan_names(config_file)

        for interface in interfaces:
            description = interface["description"]
            vlan = interface["vlan"]
            if description:
                data["interfaces"].append({"hostname":hostname, "interface":interface["name"], "description":description})

            if vlan:
                data["interfaces_vlan"].append({"hostname":hostname, "interface":interface["name"], "vlan_id":vlan, 
                    "vlan_name":vlan_names[vlan], "vlan_mode":interface["vlan_mode"]})
    return data

# Collect all the data and saved it to a YAML file
def to_yaml(data_folder, output_file_path, device_type_slags, devices_tags):
    files = config_files(data_folder)
    with open(main_folder + output_file_path, 'w') as f:
        yaml.dump(locations_json(files), f)
        yaml.dump(devices_json(files, device_type_slags, devices_tags), f)
        yaml.dump(device_interfaces_json(files), f)
        yaml.dump(ip_addresses_json(files), f)
        yaml.dump(lags_json(files), f)
        yaml.dump(vlans_json(files), f)
#        yaml.dump(interfaces_json(files), f)

def main():
    #--- 6100 ---
    data_folder = main_folder + "/data/aruba_6100/"
    output_file_path = "/data/yaml/aruba_6100.yaml"
    print("Update data for Aruba 6100 Switches into the file: ", output_file_path)

    device_type_slags = {
        "JL679A": "hpe-aruba-6100-12g-poe4-2sfpp"
    }

    devices_tags = ["switch"]

    to_yaml(data_folder, output_file_path, device_type_slags, devices_tags)

    #--- 6300 ---
    data_folder = main_folder + "/data/aruba_6300/"
    output_file_path = "/data/yaml/aruba_6300.yaml"
    print("Update data for Aruba 6300 Switches into the file: ", output_file_path)

    device_type_slags = {
        "JL658A_stack": "hpe-aruba-6300m-24sfpp-4sfp56"
    }

    devices_tags = ["switch", "stack"]

    to_yaml(data_folder, output_file_path, device_type_slags, devices_tags)

#    files = config_files(data_folder)
#    with open(main_folder + output_file_path, 'a') as f:
#        yaml.dump(device_interfaces_json(files), f)

#---- Debugging ----#
def debug_collect_vlans():
    files = os.listdir(data_folder)
    files = [data_folder + f for f in files if os.path.isfile(data_folder + f)]
    info = collect_vlans(files)
    for vlan_id in info:
        print(f"VLAN ID: {vlan_id}, Name: {info[vlan_id]['name']}, Description: {info[vlan_id]['description']}")

def debug_vlans_json(data_folder):
    files = config_files(data_folder)
    devices_tags = ["switch"]
    output = yaml.dump(vlans_json(files))

    print("\n'vlans_json()' Output: for ", data_folder)
    print(output)




def test_to_yaml(data_folder):
    # Create test.yaml file from test folder

    output_file_path = "/data/yaml/test.yaml"

    slags = {
        "JL679A": "hpe-aruba-6100-12g-poe4-2sfpp",
        "JL658A_stack": "hpe-aruba-6300m-24sfpp-4sfp56"
    }

    print("Dump test data into the file: " + output_file_path)
    to_yaml(data_folder, output_file_path, slags, ["switch"])

if __name__ == "__main__":
    main()

    print("\n=== Debugging Aruba 6100 ===")
    data_folder = main_folder + "/data/aruba_6100/"
    #data_folder = main_folder + "/data/aruba_6300/"

    config_file = data_folder + "rggw1018bp"

    #debug_collect_vlans()
    debug_vlans_json(data_folder)

    #test_to_yaml(data_folder)

    print("\n=== Debugging Aruba 6300 ===")
    data_folder = main_folder + "/data/aruba_6300/"

    config_file = data_folder + "rgcs0006"

    #test_to_yaml(data_folder)