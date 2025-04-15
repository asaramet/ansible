#!/usr/bin/env python3

# Extra reusable functions

import re, os, yaml
from tabulate import tabulate
from std_functions import main_folder, config_files, search_line
from std_functions import convert_range
from std_functions import device_type, get_hostname, interfaces_dict

# get the interfaces configuration from a config file
def get_interfaces_config(config_file):
    interface_configs = {
        'mgmt': {},
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
            elif 'mgmt' in current_interface:
                interface_type = 'mgmt'
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

# get vlan interface with IP loopback
def get_loopback_interface(config_file):
    interfaces = get_interfaces_config(config_file)

    #loopback_int = interfaces['mgmt'] if 'mgmt' in interfaces.keys() else interfaces['vlan']
    if 'mgmt' in interfaces.keys():
        mgmt = interfaces['mgmt'] 
        
    if 'vlan' in interfaces.keys():
        vlans = interfaces['vlan']

    if mgmt: # managment interface
        mgmt = mgmt.values()
        if len(mgmt) != 1: return # skip if too much interfaces

        mgmt = list(mgmt)[0][1].strip()
        ip = mgmt.split()[2]

        return 'mgmt', ip

    vlan = list(vlans.keys())[1:]

    if len(vlan) != 1: # more or none interface vlans
        return

    vlan = vlan[0].split()[2]

    [description, ip] = list(vlans.values())[1]

    ip = ip.split()[2]
    description = description.split()[1]

    return vlan, ip, description

# Get uplink vlan
def get_uplink_vlan(config_file):
    return get_loopback_interface(config_file)[0]

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

def get_lag_interfaces(config_file):
    """
    Extracts LAG information from the interfaces dictionary.
    
    Args:
        config_file (text file): Aruba OS-CX switch configuration file containing interface configurations.
    
    Returns:
        dict: A dictionary where keys are LAG IDs and values are lists of interfaces belonging to each LAG.
    """
    lag_interfaces = {}
    
    interfaces = get_interfaces_config(config_file)['physical']
    for interface, configs in interfaces.items():
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

def interfaces_types(config_file):
    data = {'type': {}, 'poe_type': {}, 'poe_mode': {}}

    interfaces = interfaces_dict()

    types = interfaces['types']
    poe_modes = interfaces['poe_modes']
    poe_types = interfaces['poe_types']

    poe_type = poe_mode = None

    hostnames = get_hostname(config_file)
    hostname = hostnames['0'] if '0' in hostnames.keys() else hostnames['1'][:-2]

    d_type = device_type(hostname).split('_')[0]

    #print(d_type)
    # create interface type dictionary
    if d_type in types.keys():
        for key, value in types[d_type].items():
            for i_nr in convert_range(key):
                data['type'][str(i_nr)] = value

    # create poe interface dictionaries
    if d_type in poe_types.keys():
        for key, value in poe_types[d_type].items():
            for i_nr in convert_range(key):
                data['poe_type'][str(i_nr)] = value

    if d_type in poe_modes.keys():
        for key, value in poe_modes[d_type].items():
            for i_nr in convert_range(key):
                data['poe_mode'][str(i_nr)] = value

    return data

#---- Debugging ----#
def debug_get_interfaces_config(config_file):
    # print some collected or parsed data

    interfaces_config = get_interfaces_config(config_file)

    # Printing the configurations for demonstration purposes
    for interface_type, configs in interfaces_config.items():
        print(f"{interface_type.capitalize()} Interfaces:")
        for interface, config in configs.items():
            print(f"  {interface}:")
            for line in config:
                print(f"    {line}")
            print()

def debug_get_loopback_interface(data_folder):
    table = []
    headers = ["File Name", "Loopback interface"]
    for f in config_files(data_folder):
        table.append([os.path.basename(f), get_loopback_interface(f)])
    print("\n== Debug: get_loopback_interface ==")
    print(tabulate(table, headers))

def debug_get_uplink_vlan(data_folder):
    table = []
    headers = ["File Name", "Uplink VLAN"]
    for f in config_files(data_folder):
        table.append([os.path.basename(f), get_uplink_vlan(f)])
    print("\n== Debug: get_uplink_vlan ==")
    print(tabulate(table, headers))

def debug_get_interfaces(data_folder):
    for config_file in config_files(data_folder):
        interfaces = get_interfaces(config_file)

        print("Interfaces List:", interfaces)

        # Print out the extracted interfaces
        for interface in interfaces:
            print(f"Interface Name: {interface['name']}")
            print(f"Description: {interface['description']}")
            print(f"VLAN: {interface['vlan']}")
            print(f"VLAN Mode: {interface['vlan_mode']}")
            print()    

def debug_get_lag_interfaces(data_folder):
    print("\n== Debug: get_lag_interfaces ==")

    for f in config_files(data_folder):
        lag_interfaces = get_lag_interfaces(f)

        print(os.path.basename(f), get_lag_interfaces(f))

def debug_get_vlan_names(data_folder):
    print("\n== Debug: get_vlan_names ==")
    for f in config_files(data_folder):
        print(os.path.basename(f), '---> ', get_vlan_names(f))

def debug_interfaces_types(data_folder):
    print("\n== Debug: interfaces_types ==")
    for f in config_files(data_folder):
        print(os.path.basename(f), '---> ', interfaces_types(f))

if __name__ == "__main__":
    #main()

    print("\n=== Aruba 6100 ===")
    data_folder = main_folder + "/data/aruba_6100/"
    config_file = data_folder + "rggw1018bp"

    #debug_get_interfaces_config(config_file)
    #debug_get_loopback_interface(data_folder)
    #debug_get_uplink_vlan(data_folder)
    #debug_get_interfaces(data_folder)
    #debug_get_lag_interfaces(data_folder)
    #debug_get_vlan_names(data_folder)
    #debug_interfaces_types(data_folder)

    #debug_get_interfaces_config(config_file)

    print("\n=== Aruba 6300 ===")
    data_folder = main_folder + "/data/aruba_6300/"
    config_file = data_folder + "rgcs0006"

    #debug_get_interfaces_config(config_file)
    #debug_get_loopback_interface(data_folder)
    #debug_get_uplink_vlan(data_folder)
    #debug_get_interfaces(data_folder)
    #debug_get_lag_interfaces(data_folder)
    #debug_get_vlan_names(data_folder)
    #debug_interfaces_types(data_folder)

    #debug_get_interfaces_config(config_file)

    print("\n=== HPE Singles ===")
    data_folder = main_folder + "/data/procurve-single/"
    #data_folder = main_folder + "/data/hpe-8-ports/"
    #data_folder = main_folder + "/data/hpe-48-ports/"

    #debug_interfaces_types(data_folder)

    print("\n=== Aruba 8 Ports ===")
    #data_folder = main_folder + "/data/aruba-48-ports/"
    #data_folder = main_folder + "/data/aruba-8-ports/"
    data_folder = main_folder + "/data/aruba-12-ports/"

    #debug_interfaces_types(data_folder)

    print("\n=== HPE Stacking ===")
    data_folder = main_folder + "/data/aruba-stack/"

    #debug_interfaces_types(data_folder)

    print("\n=== HPE Stacking 2930 ===")
    data_folder = main_folder + "/data/aruba-stack-2930/"

    #debug_interfaces_types(data_folder)

    print("\n=== HPE Stacking 2920 ===")
    data_folder = main_folder + "/data/aruba-stack-2920/"

    #debug_interfaces_types(data_folder)
    
    print("\n=== ProCurve Modular ===")
    data_folder = main_folder + "/data/procurve-modular/"

    debug_interfaces_types(data_folder)

    print("\n=== ProCurve Single ===")
    data_folder = main_folder + "/data/procurve-single/"

    #debug_interfaces_types(data_folder)

    print("\n=== All ===")
    config_file = data_folder + "rhsw1u107p"
