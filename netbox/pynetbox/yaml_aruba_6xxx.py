#!/usr/bin/env python3

# Collect Aruba 6xxx data and create a yaml configs file 

import re, os, yaml
from tabulate import tabulate
from std_functions import main_folder, config_files

from json_functions import locations_json

from json_functions_os_cx import devices_json, device_interfaces_json
from json_functions_os_cx import ip_addresses_json

#from std_functions import get_hostname, get_site
#from std_functions import get_hostname

#from extra_functions import get_flor_name, get_parent_location
#from extra_functions import get_location, get_room_location
#from extra_functions import get_looback_interface






def get_lag_interfaces(config_file):
    """
    Extracts LAG information from the interfaces dictionary.
    
    Args:
        config_file (text file): Aruba 6100 switch configuration file containing interface configurations.
    
    Returns:
        dict: A dictionary where keys are LAG IDs and values are lists of interfaces belonging to each LAG.
    """
    lag_interfaces = {}
    
    interfaces_dict = get_interfaces_config(config_file)['physical']
    for interface, configs in interfaces_dict.items():
        for config in configs:
            config = config.strip()
            if config.startswith('lag'):
                lag_id = config.split()[1]
                if lag_id not in lag_interfaces:
                    lag_interfaces[lag_id] = []

                interface = interface.split()[1]
                lag_interfaces[lag_id].append(interface)
                break
    
    return lag_interfaces

def get_vlans(config_file):
    """
    Parses VLAN information from a given configuration file content.

    Args:
        file_content (str): The content of the configuration file as a string.

    Returns:
        dict: A dictionary where each key is a VLAN ID (str) and the value is another
              dictionary with keys 'name' and 'description'. If a VLAN does not have a
              name or description, the corresponding value will be None.
    """

    with open(config_file, "r") as f:
        config_text = f.readlines()

    vlans = {}
    vlan_pattern = re.compile(r"vlan (\d+)")
    name_pattern = re.compile(r"\s+name (.+)")
    description_pattern = re.compile(r"\s+description (.+)")
    current_vlan = None

    for line in config_text:
        vlan_match = vlan_pattern.match(line)
        name_match = name_pattern.match(line)
        description_match = description_pattern.match(line)

        if vlan_match:
            current_vlan = vlan_match.group(1)
            vlans[current_vlan] = {'name': 'default', 'description': 'default'}
        elif name_match and current_vlan:
            vlans[current_vlan]['name'] = name_match.group(1)
        elif description_match and current_vlan:
            vlans[current_vlan]['description'] = description_match.group(1)

    return vlans

def get_vlan_names(config_file):
    with open(config_file, "r") as f:
        lines = f.readlines()

    # vlans dictionary in form of {'vlan_id': 'vlan_name'}
    vlans = {}

    current_vlan = None
    for line in lines:
        line = line.strip()
        
        if line.startswith("vlan "):
            current_vlan = line.split()[1]
        elif line.startswith("name ") and current_vlan is not None:
            vlan_name = line.split(" ", 1)[1]
            vlans[current_vlan] = vlan_name
            current_vlan = None

        if current_vlan == "1":
            vlans["1"] = "default"
            current_vlan = None
    
    return vlans

# create lags json objects list
def lags_json(config_files):
    data = {"lags":[], "lag_interfaces":[]}

    for config_file in config_files:
        hostname = get_hostname(config_file)['0']

        lag_interfaces = get_lag_interfaces(config_file).items()
        if not lag_interfaces:
            continue
        for lag, interfaces in lag_interfaces:
            data["lags"].append({"hostname": hostname, "lag_id": lag})
            for interface in interfaces:
                data["lag_interfaces"].append({"hostname": hostname, "lag_id": lag, "interface": interface})

    return data

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

def vlans_jason(config_files):
    data = {'vlans':[]}

    collected_vlans = collect_vlans(config_files)
    for vlan_id in collected_vlans:
        name = str(collected_vlans[vlan_id]["name"])
        data['vlans'].append({'vlan_id': vlan_id, 'name': name})

    return data

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
        yaml.dump(ip_addresses_json(files), f)
#        yaml.dump(lags_json(files), f)
#        yaml.dump(vlans_jason(files), f)
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

    files = config_files(data_folder)
    with open(main_folder + output_file_path, 'a') as f:
        yaml.dump(device_interfaces_json(files), f)

#---- Debugging ----#
def debug_get_lag_interfaces():
    file = data_folder + "rggw1018bp"
    lag_interfaces = get_lag_interfaces(file)
    for lag, interfaces in lag_interfaces.items():
        print(f"LAG {lag}: {interfaces}")

    print(lag_interfaces)

def debug_lags_json():
    files = os.listdir(data_folder)
    files = [data_folder + f for f in files if os.path.isfile(data_folder + f)]
    print(lags_json(files))

def debug_get_vlans():
    file = data_folder + "rggw1018bp"
    vlans = get_vlans(file)
    print(vlans)
    for vlan_id, info in vlans.items():
        print(f"VLAN ID: {vlan_id}, Name: {info['name']}, Description: {info['description']}")

def debug_collect_vlans():
    files = os.listdir(data_folder)
    files = [data_folder + f for f in files if os.path.isfile(data_folder + f)]
    info = collect_vlans(files)
    for vlan_id in info:
        print(f"VLAN ID: {vlan_id}, Name: {info[vlan_id]['name']}, Description: {info[vlan_id]['description']}")





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

    #debug_get_lag_interfaces()
    #debug_lags_json()
    #debug_get_vlans()
    #debug_collect_vlans()

    #test_to_yaml(data_folder)

    print("\n=== Debugging Aruba 6300 ===")
    data_folder = main_folder + "/data/aruba_6300/"

    config_file = data_folder + "rgcs0006"

    #test_to_yaml(data_folder)