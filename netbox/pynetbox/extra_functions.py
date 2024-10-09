#!/usr/bin/env python3

# Extra reusable functions

import re, os, yaml
from tabulate import tabulate
from std_functions import this_folder, main_folder
from std_functions import config_files, search_line
from std_functions import get_hostname, device_type

def get_location(file):
    location_line = search_line("location", file)

    if not location_line or location_line.isspace(): return None

    location = location_line.split()[-1].strip('"')

    if location.split('.')[0] == 'V':
        location = location[2:]

        rack_in_l = location.split('.') # Rack number specified in location
        if len(rack_in_l) > 2:
            location = rack_in_l[0] + '.' + rack_in_l[1]

    building, room = location.split(".", 1)

    building_nr = str(int(building[1:])) # convert "01" to "1", for example
    if len(building_nr) == 1:
        # add "0" to single digit buildings
        building_nr = "0" + building_nr

    location = building[0] + building_nr + "." + room

    return (location, room)

# get flor number from room number
def get_flor_nr(room_nr):
    if not room_nr: return None

    if room_nr[0] == 'u':
        room_nr = '-' + room_nr[1:]

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
    if not location: return None

    # s01-2-etage-2
    flor_tags = {
        "-2": "untergeschoss-2",
        "-1": "untergeschoss",
        "0": "erdgeschoss"
    }
    building, room_nr = location.split(".", 1)
    flor = get_flor_nr(room_nr)
    flor_fx = str(abs(int(flor))) # string to use in the label
    flor_tag = flor_tags[flor] if int(flor) < 1 else "etage-" + flor

    return building.lower() + "-" + flor_fx + "-" + flor_tag
    






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

#---- Debugging ----#
def debug_get_location(data_folder):
    table = []
    headers = ["File Name", "Location"]
    for f in config_files(data_folder):
        table.append([os.path.basename(f), get_location(f)])
    print("\n== Debug: get_location() ==")
    print(tabulate(table, headers))

def debug_get_room_location(data_folder):
    table = []
    headers = ["File Name", "Room Location"]

    for f in config_files(data_folder):
        location = get_location(f)

        if location:
            location, _ = location

        table.append([os.path.basename(f), get_room_location(location)])
    print("\n== Debug: get_room_location() ==")
    print(tabulate(table, headers))

def debug_get_flor_nr(data_folder):
    table = []
    headers = ["File Name", "Location", "Flor number"]

    for f in config_files(data_folder):
        location = get_location(f)
        room = None

        if location:
            location , room = location

        table.append([os.path.basename(f), location, get_flor_nr(room)])
    print("\n== Debug: get_flor_nr() ==")
    print(tabulate(table, headers))




#---- Debugging JSON ----#


#--- Redundant ---#
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

def debug_get_lag_interfaces():
    file = data_folder + "rggw1018bp"
    lag_interfaces = get_lag_interfaces(file)
    for lag, interfaces in lag_interfaces.items():
        print(f"LAG {lag}: {interfaces}")

    print(lag_interfaces)

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

if __name__ == "__main__":
    #main()

    print("\n=== Aruba 6100 ===")
    data_folder = main_folder + "/data/aruba_6100/"

    #debug_get_interfaces_config()
    #debug_ip_addresses_json()
    #debug_get_lag_interfaces()
    #debug_lags_json()
    #debug_get_vlans()
    #debug_collect_vlans()
    #debug_get_interfaces()
    #debug_get_uplink_vlan()

    #debug_get_location(data_folder)
    #debug_get_room_location(data_folder)
    debug_get_flor_nr(data_folder)

    #debug_locations_json(data_folder)

    print("\n=== Aruba 6300 ===")
    data_folder = main_folder + "/data/aruba_6300/"

    #debug_get_location(data_folder)
    #debug_get_room_location(data_folder)

    print("\n=== HPE Singles ===")
    data_folder = main_folder + "/data/hpe-8-ports/"

    debug_get_location(data_folder)
    debug_get_room_location(data_folder)

    print("\n=== HPE Stacking ===")
    #data_folder = main_folder + "/data/aruba-stack/"
    data_folder = main_folder + "/data/aruba-stack-2930/"

    debug_get_location(data_folder)
    debug_get_room_location(data_folder)

    print("\n=== ProCurve Modular ===")
    data_folder = main_folder + "/data/procurve-modular/"

    #debug_get_location(data_folder)
    #debug_get_room_location(data_folder)

    print("\n=== ProCurve Single ===")
    data_folder = main_folder + "/data/procurve-single/"

    #debug_get_location(data_folder)
    debug_get_room_location(data_folder)
    #debug_get_flor_nr(data_folder)

    #debug_locations_json(data_folder)