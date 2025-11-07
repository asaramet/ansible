#!/usr/bin/env python3

# Collect HPE switches data and create yaml configs file 

import re, os, sys, yaml
from tabulate import tabulate

from std_functions import device_type_slags, this_folder, main_folder, config_files

from json_functions import devices_json, lags_json, device_interfaces_json
from json_functions import vlans_json, tagged_vlans_json
from json_functions import ip_addresses_json, modules_json

# Collect single switches data and saved it to a YAML file
def single(data_folder, output_file_path, devices_tags):
    files = config_files(data_folder)

    # For debugging output_file_path will be stdout
    if output_file_path == sys.stdout:
        f = sys.stdout
    else:
        output_file = main_folder + output_file_path
        # ensure the folder exists
        os.makedirs(os.path.dirname(output_file), exist_ok = True)
        f = open(output_file, 'w')

    try:
        yaml.dump({"modular": False}, f)
        #yaml.dump(locations_json(files), f)
        yaml.dump(devices_json(files, device_type_slags, devices_tags), f)
        yaml.dump(lags_json(files), f)
        yaml.dump(device_interfaces_json(files), f)
        yaml.dump(vlans_json(files), f)
        yaml.dump(tagged_vlans_json(files), f)
        yaml.dump(ip_addresses_json(files), f)
    finally:
        if f is not sys.stdout: # Don't close stdout
            f.close()

# Collect modular switches data and saved it to a YAML file
def modular(data_folder, output_file_path, devices_tags):
    files = config_files(data_folder)

    # For debugging output_file_path will be stdout
    if output_file_path == sys.stdout:
        f = sys.stdout
    else:
        output_file = main_folder + output_file_path
        # ensure the folder exists
        os.makedirs(os.path.dirname(output_file), exist_ok = True)
        f = open(output_file, 'w')

    try:
        yaml.dump({"modular": True}, f)
        #yaml.dump(locations_json(files), f)
        yaml.dump(devices_json(files, device_type_slags, devices_tags), f)
        yaml.dump(modules_json(files), f)
        yaml.dump(lags_json(files), f)
        yaml.dump(device_interfaces_json(files), f)
        yaml.dump(vlans_json(files), f)
        yaml.dump(tagged_vlans_json(files), f)
        yaml.dump(ip_addresses_json(files), f)
    finally:
        if f is not sys.stdout: # Don't close stdout
            f.close()

def assign_sfp_modules(t_file):
    with open(main_folder + "/host_vars/99/sfp_modules.yaml", 'r' ) as f:
        modules = yaml.safe_load(f)
    return modules

# Collect stack switches data to a YAML file
def stack(data_folder, output_file_path, devices_tags):
    files = config_files(data_folder)
    with open(main_folder + output_file_path, 'w') as f:
        yaml.dump({"modular": False}, f)
        #yaml.dump(locations_json(files), f)
        yaml.dump(devices_json(files, device_type_slags, devices_tags), f)
        yaml.dump(device_interfaces_json(files), f)
        yaml.dump(lags_json(files), f)
        yaml.dump(vlans_json(files), f)
        yaml.dump(tagged_vlans_json(files), f)
        yaml.dump(ip_addresses_json(files), f)

def stack_module(data_folder, output_file_path, devices_tags):
    files = config_files(data_folder)

    add_stack_interfaces = True
    for f in files:
        if 'rscs0007' in f.split('/'):
            add_stack_interfaces = False

    with open(main_folder + output_file_path, 'w') as f:
        yaml.dump({"modular": True}, f)
        #yaml.dump(locations_json(files), f)
        yaml.dump(devices_json(files, device_type_slags, devices_tags), f)
        yaml.dump(device_interfaces_json(files), f)
        yaml.dump(lags_json(files), f)
        yaml.dump(vlans_json(files), f)
        yaml.dump(tagged_vlans_json(files), f)
        yaml.dump(ip_addresses_json(files), f)

        yaml.dump(modules_json(files), f)

def main():
    # ProCurve Single Switches
    data_folder = main_folder + "/data/procurve-single/"
    output_file_path = "/data/yaml/procurve_single.yaml"

    devices_tags = "switch"

    print("Update data for ProCurve Switches into the file: ", output_file_path) 
    single(data_folder, output_file_path, devices_tags)

    # HPE 8 Ports Switches
    data_folder = main_folder + "/data/hpe-8-ports/"
    output_file_path = "/data/yaml/hpe_8_ports.yaml"

    print("Update data for HPE 8 port Switches into the file: ", output_file_path) 
    single(data_folder, output_file_path, devices_tags)

    # HPE 24 and 48 Ports Switches
    data_folder = main_folder + "/data/hpe-24-ports/"
    output_file_path = "/data/yaml/hpe_24_ports.yaml"

    print("Update data for HPE 24 and 48 port Switches into the file: ", output_file_path) 
    single(data_folder, output_file_path, devices_tags)

    # Aruba 24 and 48 Ports Switches
    data_folder = main_folder + "/data/aruba-48-ports/"
    output_file_path = "/data/yaml/aruba_48_ports.yaml"

    print("Update data for Aruba 24 and 48 port Switches into the file: ", output_file_path)
    single(data_folder, output_file_path, devices_tags)

    # Aruba 8 Ports Switches
    data_folder = main_folder + "/data/aruba-8-ports/"
    output_file_path = "/data/yaml/aruba_8_ports.yaml"


    print("Update data for Aruba 8 port Switches into the file: ", output_file_path) 
    single(data_folder, output_file_path, devices_tags)

    # Aruba 12 Ports Switches
    data_folder = main_folder + "/data/aruba-12-ports/"
    output_file_path = "/data/yaml/aruba_12_ports.yaml"

    print("Update data for Aruba 12 port Switches into the file: ", output_file_path) 
    single(data_folder, output_file_path, devices_tags)

    # ProCurve Modular Switches
    data_folder = main_folder + "/data/procurve-modular/"
    output_file_path = "/data/yaml/procurve_modular.yaml"

    devices_tags = ["switch", "modular-switch"]

    print("Update data for ProCurve modular Switches into the file: ", output_file_path) 
    modular(data_folder, output_file_path, devices_tags)

    # Aruba Modular Switches
    data_folder = main_folder + "/data/aruba-modular/"
    output_file_path = "/data/yaml/aruba_modular.yaml"

    devices_tags = ["switch", "modular-switch"]


    print("Update data for Aruba modular Switches into the file: ", output_file_path) 
    modular(data_folder, output_file_path, devices_tags)

    # Aruba stacks (no extra modules)
    data_folder = main_folder + "/data/aruba-stack/"
    output_file_path = "/data/yaml/aruba_stack.yaml"

    devices_tags = ["switch", "stack"]

    print("Update data for Aruba stacks into the file: ", output_file_path) 
    stack(data_folder, output_file_path, devices_tags)

    # Aruba 2930 stacks with LWL modules
    data_folder = main_folder + "/data/aruba-stack-2930/"
    output_file_path = "/data/yaml/aruba_stack_2930.yaml"


    devices_tags = ["switch", "stack"]

    print("Update data for Aruba 2930 stacks into the file: ", output_file_path) 
    stack_module(data_folder, output_file_path, devices_tags)

    # Aruba 2920 stacks with LWL modules
    data_folder = main_folder + "/data/aruba-stack-2920/"
    output_file_path = "/data/yaml/aruba_stack_2920.yaml"

    devices_tags = ["switch", "stack"]

    #assign_sfp_modules(data_folder)

    print("Update data for Aruba 2920 stacks into the file: ", output_file_path)
    stack_module(data_folder, output_file_path, devices_tags)

    # Aruba modular stacks
    data_folder = main_folder + "/data/aruba-modular-stack/"
    output_file_path = "/data/yaml/aruba_modular_stack.yaml"

    devices_tags = ["switch", "stack"]

    print("Update data for Aruba modular stacks into the file: ", output_file_path)
    stack_module(data_folder, output_file_path, devices_tags)

#----- Debugging -------
def debug_single():
    #data_folder = main_folder + "/data/aruba-12-ports/"
    data_folder = main_folder + "/data/hpe-8-ports/"

    print('---Debugging ', data_folder)
    single(data_folder, sys.stdout, ["switch"])
    print('---END Debugging---')

def debug_modular():
    data_folder = main_folder + "/data/procurve-modular/"

    print("---Debugging ", data_folder)
    modular(data_folder, sys.stdout, ["switch", "modular-switch"])
    print('---END Debugging---')

if __name__ == "__main__":
    #debug_single()
    #debug_modular()

    main()