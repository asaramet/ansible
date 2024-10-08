#!/usr/bin/env python3

# Collect Aruba 6xxx data and create a yaml configs file 

import re, os, yaml
from tabulate import tabulate
from std_functions import this_folder, main_folder
from std_functions import config_files, search_line
from std_functions import get_hostname, device_type

def get_location(file):
    location_line = search_line("snmp-server system-location", file)

    if location_line.isspace(): return " "

    location = location_line.split()[2]

    if location.split('.')[0] == 'V':
        location = location[2:]

    building, room = location.split(".", 1)

    building_nr = str(int(building[1:])) # convert "01" to "1", for example
    if len(building_nr) == 1:
        # add "0" to single digit buildings
        building_nr = "0" + building_nr

    location = building[0] + building_nr + "." + room

    return (location, room)

# get flor number from room number
def get_flor_nr(room_nr):
    flor = room_nr[0]
    flor = int(room_nr[:2]) if flor == '-' else int(flor)

    return str(flor)

# get flor name from room number
def get_flor_name(room_nr):
    flor_name = {
        "-2": "Untergeschoss 2",
        "-1": "Untergeschoss",
        "0": "Erdgeschoss"
    }

    flor = get_flor_nr(room_nr)
    if int(flor) < 1:
        return (flor, flor_name[flor])

    return (flor, "Etage " + flor)

# get location's parent
def get_parent_location(location):
    prefixes = {
        "F": "fl",
        "G": "gp",
        "S": "sm",
        "W": "ws"
    }

    building = location.split(".")[0]
    return prefixes[building[0]] + "-" + "gebude" + "-" + building[1:]

# get room location
def get_room_location(location): 
    # s01-2-etage-2
    flor_tags = {
        "-2": "untergeschoss-2",
        "-1": "untergeschoss",
        "0": "erdgeschoss"
    }
    building, room_nr = location.split(".")
    flor = get_flor_nr(room_nr)
    flor_fx = str(abs(int(flor))) # string to use in the label
    flor_tag = flor_tags[flor] if int(flor) < 1 else "etage-" + flor

    return building.lower() + "-" + flor_fx + "-" + flor_tag
    
# get location site
def get_site(location):
    campuses = {
        "F": "flandernstrasse",
        "G": "gppingen",
        "S": "stadtmitte",
        "W": "weststadt"
    }
    return "campus-" + campuses[location[0]]

# get the interfaces configuration from an Aruba 6100 config file
def get_interfaces_config(config_file):
    interface_configs = {
        'vlan': {},
        'lag': {},
        'physical': {}
    }
    current_interface = None

    with open(config_file, "r") as f:
        config_text = f.readlines()

    for line in config_text:
        line = line.rstrip() # remove the trailing newline character
        
        # Detect an interface line
        if line.startswith('interface'):
            current_interface = line
            if 'vlan' in current_interface:
                interface_type = 'vlan'
            elif 'lag' in current_interface:
                interface_type = 'lag'
            else:
                interface_type = 'physical'

            interface_configs[interface_type][current_interface] = []
        elif current_interface:
            # Check if the line is indented
            if line.startswith((' ','\t', '!')):  # Lines part of an interface configuration
                interface_configs[interface_type][current_interface].append(line)
            else:
                # End of the current interface configuration block
                current_interface = None
                interface_type = None

    # Clean up the config by removing any trailing empty configurations
    for interface_type in interface_configs:
        interface_configs[interface_type] = {k: v for k, v in interface_configs[interface_type].items() if v}

    return interface_configs

# Get uplink vlan
def get_uplink_vlan(config_file):
    return get_vlan_interface(config_file)[0]

# get vlan interface with IP loopback
def get_vlan_interface(config_file):
    vlan_interfaces = get_interfaces_config(config_file)['vlan']

    vlan = list(vlan_interfaces.keys())[1:]
    if len(vlan) != 1: # more or none interface vlans
        return 

    vlan = vlan[0].split()[2]

    [description, ip] = list(vlan_interfaces.values())[1]

    ip = ip.split()[2]
    description = description.split()[1]

    return vlan, ip, description

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

def get_interfaces_recursively(config_text_list, interfaces = None, current_interface = None, found_interface_flag = False):
    # initialize interfaces properly if not provided
    if not interfaces:
        interfaces = []

    if not config_text_list:
        # Append the last interface if the recursion is terminating and an interface was being processed
        if found_interface_flag and current_interface is not None:
            interfaces.append(current_interface)
        return interfaces # Terminate recursion

    line = config_text_list[0] # get a line

    # Find interface and save it to current_interface they start recursively from the next line
    if line.startswith('interface ') and not found_interface_flag: 
        name = " ".join(line.split()[1:])
        current_interface = {'name': name, 'description': None, 'vlan': None, 'vlan_mode': None} 

        return get_interfaces_recursively(config_text_list[1:], interfaces, current_interface, True)

    # if the line starts with a word and the flag is True, switch the flag to False and append the current interface
    if not re.match(r'\s', line) and found_interface_flag:
        found_interface_flag = False
        interfaces.append(current_interface)
        return get_interfaces_recursively(config_text_list, interfaces, current_interface, found_interface_flag)

    # Remove spaces
    line = line.strip()

    # Match vlan access
    if line.startswith('description') and found_interface_flag: 
        description = " ".join(line.split()[1:])
        current_interface['description'] = description

    # Match vlan access
    elif 'vlan access' in line:
        vlan_id = line.split()[-1]
        current_interface['vlan'] = vlan_id
        current_interface['vlan_mode'] = "access"
        
    # Match vlan trunk
    elif 'vlan trunk' in line:
        mode = line.split()[2]
        vlan_id = line.split()[-1]
        current_interface['vlan_mode'] = "tagged-all"
        if mode == 'native':
            current_interface['vlan'] = vlan_id

    return get_interfaces_recursively(config_text_list[1:], interfaces, current_interface, found_interface_flag)

def get_interfaces(config_file):
    """
    Parse a configuration file and extract interface names, descriptions, and VLAN assignments.

    Args:
    - config_file (str): The path to the configuration file to parse.

    Returns:
    - list of dicts: A list of dictionaries, each representing an interface with keys:
                     'name' (str): Interface name
                     'description' (str): Interface description or "none" if not provided
                     'vlan' (str): Native/untagged VLAN ID assigned to the interface
    """
    with open(config_file, 'r') as f:
        config_text_list = f.readlines()

    return  get_interfaces_recursively(config_text_list)

# create the loactions json objects list
def locations_json(config_files):
    data = {"locations":[]}
    locations = set()
    rooms = {}

    for file in config_files:
        location,room = get_location(file)
        locations.add(location)
        rooms.update({location:room})

    for location in locations:
        room = rooms[location]
        building = location.split(".")[0]
        flor_tuple = get_flor_name(room)

        data["locations"].append({"name": building + "." + flor_tuple[0] + " - " + flor_tuple[1], "site": get_site(location), "parent_location": get_parent_location(location)})

    return data

# create devices json objects list
def devices_json(config_files):
    data = {"devices":[]}
    rsm_vlans = ['102','202','302']

    device_types = {
        'JL679A': 'hpe-aruba-6100-12g-poe4-2sfpp',
        'JL658A': 'hpe-aruba-6300m-24sfpp-4sfp56'
    }

    for file in config_files:

        location,room = get_location(file)
        site = get_site(location)
        location = get_room_location(location)

        uplink_vlan = get_uplink_vlan(file)
        
        device_role = "bueroswitch" if uplink_vlan in rsm_vlans else "access-layer-switch"

        hostnames = get_hostname(file)
        for key in hostnames.keys():
            hostname = hostnames[key]
            d_type = device_types[device_type(hostname)]
            data["devices"].append({"name": hostname, "location": location, "site": site, "device_role": device_role, "device_type": d_type, "serial": None, "tags": None })

    return data

# create ip_addresses json objects list
def ip_addressess_json(config_files):
    data = {"ip_addresses":[]}

    for config_file in config_files:
        hostname = get_hostname(config_file)['0']

        vlan_interface = get_vlan_interface(config_file)

        data["ip_addresses"].append({"hostname": hostname, "ip": vlan_interface[1], "vlan_nr": vlan_interface[0], "vlan_name": vlan_interface[2]})

    return data

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
def to_yaml(data_folder, output_file_path):
    files = config_files(data_folder)
    with open(main_folder + output_file_path, 'w') as f:
        yaml.dump(locations_json(files), f)
        yaml.dump(devices_json(files), f)
        yaml.dump(ip_addressess_json(files), f)
        yaml.dump(lags_json(files), f)
        yaml.dump(vlans_jason(files), f)
        yaml.dump(interfaces_json(files), f)

def main():
    data_folder = main_folder + "/data/aruba_6100/"
    output_file_path = "/data/yaml/aruba_6100.yaml"

    print("Update data for Aruba 6100 Switches into the file: ", output_file_path)
    to_yaml(data_folder, output_file_path)

    data_folder = main_folder + "/data/aruba_6300/"
    output_file_path = "/data/yaml/aruba_6300.yaml"

    print("Update data for Aruba 6300 Switches into the file: ", output_file_path)
    to_yaml(data_folder, output_file_path)

#---- Debugging ----#
def debug_get_interfaces_config():
    # print some collected or parsed data
    config_file = data_folder + "rggw1018bp"

    interfaces_config = get_interfaces_config(config_file)

    # Printing the configurations for demonstration purposes
    for interface_type, configs in interfaces_config.items():
        print(f"{interface_type.capitalize()} Interfaces:")
        for interface, config in configs.items():
            print(f"  {interface}:")
            for line in config:
                print(f"    {line}")
            print()

def debug_ip_addresses_json():
    files = os.listdir(data_folder)
    files = [data_folder + f for f in files if os.path.isfile(data_folder + f)]

    for dict in ip_addressess_json(files)['ip_addresses']:
        print(dict)

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

def debug_get_interfaces():
    config_files = [data_folder + "rsgw7203p"]
    config_files.append(data_folder + "rggw1018bp")

    for config_file in config_files:
        interfaces = get_interfaces(config_file)

        print("Interfaces List:", interfaces)

        # Print out the extracted interfaces
        for interface in interfaces:
            print(f"Interface Name: {interface['name']}")
            print(f"Description: {interface['description']}")
            print(f"VLAN: {interface['vlan']}")
            print(f"VLAN Mode: {interface['vlan_mode']}")
            print()    

def debug_get_uplink_vlan():
    files = os.listdir(data_folder)
    files = [data_folder + f for f in files if os.path.isfile(data_folder + f)]

    rsm_vlans = ['102','202','302']
    for f in files:
        vlan = get_uplink_vlan(f)
        if vlan in rsm_vlans:
            print("Bueroswitch - ", vlan)
        else:
            print("Access Switch - ", vlan)

def debug_get_location(data_folder):
    table = []
    headers = ["File Name", "Location"]
    for f in config_files(data_folder):
        table.append([os.path.basename(f), get_location(f)])
    print("\n== Debug: get_location() ==")
    print(tabulate(table, headers))

def test_to_yaml(data_folder):
    # Create test.yaml file from test folder

    output_file_path = "/data/yaml/test.yaml"

    print("Dump test data into the file: " + output_file_path)
    to_yaml(data_folder, output_file_path)

def debug_devices_json(data_folder):
    print("Aruba....")

    print(devices_json(config_files(data_folder)))

if __name__ == "__main__":
    #main()

    data_folder = main_folder + "/data/aruba_6100/"
    #data_folder = main_folder + "/data/aruba_6300/"

    debug_devices_json(data_folder)
    #test_to_yaml(data_folder)

    #debug_get_interfaces_config()
    #debug_ip_addresses_json()
    #debug_get_lag_interfaces()
    #debug_lags_json()
    #debug_get_vlans()
    #debug_collect_vlans()
    #debug_get_interfaces()
    #debug_get_uplink_vlan()

    #debug_get_location(data_folder)

    data_folder = main_folder + "/data/aruba_6300/"

    debug_devices_json(data_folder)
    #debug_get_location(data_folder)

    #test_to_yaml(data_folder)