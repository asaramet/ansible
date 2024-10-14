#!/usr/bin/env python3

# Standard reusable functions for Aruba OS-CX

import re, os, yaml
from tabulate import tabulate
from std_functions import main_folder, config_files

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
def get_looback_interface(config_file):
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
    return get_looback_interface(config_file)[0]



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

def debug_get_looback_interface(data_folder):
    table = []
    headers = ["File Name", "VLAN interface"]
    for f in config_files(data_folder):
        table.append([os.path.basename(f), get_looback_interface(f)])
    print("\n== Debug: get_looback_interface ==")
    print(tabulate(table, headers))

def debug_get_uplink_vlan(data_folder):
    table = []
    headers = ["File Name", "Uplink VLAN"]
    for f in config_files(data_folder):
        table.append([os.path.basename(f), get_uplink_vlan(f)])
    print("\n== Debug: get_uplink_vlan ==")
    print(tabulate(table, headers))

if __name__ == "__main__":
    print("\n=== Aruba 6100 ===")
    data_folder = main_folder + "/data/aruba_6100/"

    config_file = data_folder + "rggw1018bp"
    debug_get_interfaces_config(config_file)

    debug_get_looback_interface(data_folder)
    debug_get_uplink_vlan(data_folder)

    print("\n=== Aruba 6300 ===")
    data_folder = main_folder + "/data/aruba_6300/"

    config_file = data_folder + "rgcs0006"
    debug_get_interfaces_config(config_file)

    debug_get_looback_interface(data_folder)
    debug_get_uplink_vlan(data_folder)