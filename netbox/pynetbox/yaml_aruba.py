#!/usr/bin/env python3

# Collect HPE switches data and create yaml configs file 

import re, os, sys, yaml
from tabulate import tabulate

from std_functions import this_folder, main_folder, config_files

from json_functions import devices_json, trunks_json, device_interfaces_json
from json_functions import vlans_json, tagged_vlans_json
from json_functions import ip_addresses_json, locations_json, modules_json

# Collect single switches data and saved it to a YAML file
def single(data_folder, output_file_path, device_type_slags, devices_tags):
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
        yaml.dump(locations_json(files), f)
        yaml.dump(devices_json(files, device_type_slags, devices_tags), f)
        yaml.dump(trunks_json(files), f)
        yaml.dump(device_interfaces_json(files), f)
        yaml.dump(vlans_json(files), f)
        yaml.dump(tagged_vlans_json(files), f)
        yaml.dump(ip_addresses_json(files), f)
    finally:
        if f is not sys.stdout: # Don't close stdout
            f.close()

# Collect modular switches data and saved it to a YAML file
def modular(data_folder, output_file_path, device_type_slags, devices_tags):
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
        yaml.dump(locations_json(files), f)
        yaml.dump(devices_json(files, device_type_slags, devices_tags), f)
        yaml.dump(modules_json(files), f)
        yaml.dump(trunks_json(files), f)
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
def stack(data_folder, output_file_path, device_type_slags, devices_tags):
    files = config_files(data_folder)
    with open(main_folder + output_file_path, 'w') as f:
        yaml.dump({"modular": False}, f)
        yaml.dump(locations_json(files), f)
        yaml.dump(devices_json(files, device_type_slags, devices_tags), f)
        yaml.dump(device_interfaces_json(files), f)
        yaml.dump(trunks_json(files), f)
        yaml.dump(vlans_json(files), f)
        yaml.dump(tagged_vlans_json(files), f)
        yaml.dump(ip_addresses_json(files), f)

def stack_module(data_folder, output_file_path, device_type_slags, devices_tags):
    files = config_files(data_folder)

    add_stack_interfaces = True
    for f in files:
        if 'rscs0007' in f.split('/'):
            add_stack_interfaces = False

    with open(main_folder + output_file_path, 'w') as f:
        yaml.dump({"modular": True}, f)
        yaml.dump(locations_json(files), f)
        yaml.dump(devices_json(files, device_type_slags, devices_tags), f)
        yaml.dump(device_interfaces_json(files), f)
        yaml.dump(trunks_json(files), f)
        yaml.dump(vlans_json(files), f)
        yaml.dump(tagged_vlans_json(files), f)
        yaml.dump(ip_addresses_json(files), f)

        yaml.dump(modules_json(files), f)

def main():
    # ProCurve Single Switches
    data_folder = main_folder + "/data/procurve-single/"
    output_file_path = "/data/yaml/procurve_single.yaml"

    devices_tags = "switch"

    device_type_slags = {
        'J9085A': 'hpe-procurve-2610-24',
        'J9086A': 'hpe-procurve-2610-24-12-pwr',
        'J9089A': 'hpe-procurve-2610-48-pwr'
    }

    print("Update data for ProCurve Switches into the file: ", output_file_path) 
    single(data_folder, output_file_path, device_type_slags, devices_tags)

    # HPE 8 Ports Switches
    data_folder = main_folder + "/data/hpe-8-ports/"
    output_file_path = "/data/yaml/hpe_8_ports.yaml"

    device_type_slags = {
        'J9562A': 'hpe-procurve-2915-8-poe',
        'J9565A': 'hpe-procurve-2615-8-poe',
        'J9774A': 'hpe-aruba-2530-8g-poep',
        'J9780A': 'hpe-aruba-2530-8-poep'
    }

    print("Update data for HPE 8 port Switches into the file: ", output_file_path) 
    single(data_folder, output_file_path, device_type_slags, devices_tags)

    # HPE 24 and 48 Ports Switches
    data_folder = main_folder + "/data/hpe-24-ports/"
    output_file_path = "/data/yaml/hpe_24_ports.yaml"

    device_type_slags = {
      'J9623A': 'hpe-aruba-2620-24',
      'J9772A': 'hpe-aruba-2530-48g-poep',
      'J9853A': 'hpe-aruba-2530-48g-poep-2sfpp',
      'J9145A': 'hpe-procurve-2910al-24g'
    }

    print("Update data for HPE 24 and 48 port Switches into the file: ", output_file_path) 
    single(data_folder, output_file_path, device_type_slags, devices_tags)

    # Aruba 24 and 48 Ports Switches
    data_folder = main_folder + "/data/aruba-48-ports/"
    output_file_path = "/data/yaml/aruba_48_ports.yaml"

    device_type_slags = {
      'JL255A': "hpe-aruba-2930f-24g-poep-4sfpp", 
      'JL256A': "hpe-aruba-2930f-48g-poep-4sfpp",
      'JL322A': "hpe-aruba-2930m-48g-poep",
      'JL357A': "hpe-aruba-2540-48g-poep-4sfpp"
    }

    print("Update data for Aruba 24 and 48 port Switches into the file: ", output_file_path)
    single(data_folder, output_file_path, device_type_slags, devices_tags)

    # Aruba 8 Ports Switches
    data_folder = main_folder + "/data/aruba-8-ports/"
    output_file_path = "/data/yaml/aruba_8_ports.yaml"

    device_type_slags = {
        'JL258A': "hpe-aruba-2930f-8g-poep-2sfpp"
    }

    print("Update data for Aruba 8 port Switches into the file: ", output_file_path) 
    single(data_folder, output_file_path, device_type_slags, devices_tags)

    # Aruba 12 Ports Switches
    data_folder = main_folder + "/data/aruba-12-ports/"
    output_file_path = "/data/yaml/aruba_12_ports.yaml"

    device_type_slags = {
        'JL693A': "hpe-aruba-2930f-12g-poep-2sfpp"
    }

    print("Update data for Aruba 12 port Switches into the file: ", output_file_path) 
    single(data_folder, output_file_path, device_type_slags, devices_tags)

    # ProCurve Modular Switches
    data_folder = main_folder + "/data/procurve-modular/"
    output_file_path = "/data/yaml/procurve_modular.yaml"

    devices_tags = ["switch", "modular-switch"]

    device_type_slags = { 
        'J8697A': 'hpe-procurve-5406zl',
        'J8698A': 'hpe-procurve-5412zl',
        'J8770A': 'hpe-procurve-4204vl',
        'J8773A': 'hpe-procurve-4208vl',
        'J9850A': 'hpe-5406r-zl2',
        'J9851A': 'hpe-5412r-zl2',
        'J9729A': 'hpe-aruba-2920-48g-poep',
        'J9729A_stack': 'hpe-aruba-2920-48g-poep'
    }

    print("Update data for ProCurve modular Switches into the file: ", output_file_path) 
    modular(data_folder, output_file_path, device_type_slags, devices_tags)

    # Aruba Modular Switches
    data_folder = main_folder + "/data/aruba-modular/"
    output_file_path = "/data/yaml/aruba_modular.yaml"

    devices_tags = ["switch", "modular-switch"]

    device_type_slags = { 
        'JL322A_module': "hpe-aruba-2930m-48g-poep"
    }

    print("Update data for Aruba modular Switches into the file: ", output_file_path) 
    modular(data_folder, output_file_path, device_type_slags, devices_tags)

    # Aruba stacks (no extra modules)
    data_folder = main_folder + "/data/aruba-stack/"
    output_file_path = "/data/yaml/aruba_stack.yaml"

    device_type_slags = {
        'JL256A_stack': "hpe-aruba-2930f-48g-poep-4sfpp",
        'JL075A_stack': 'hpe-aruba-3810m-16sfpp-2-slot-switch',
        'JL693A_stack': "hpe-aruba-2930f-12g-poep-2sfpp"
    }

    devices_tags = ["switch", "stack"]

    print("Update data for Aruba stacks into the file: ", output_file_path) 
    stack(data_folder, output_file_path, device_type_slags, devices_tags)

    # Aruba 2930 stacks with LWL modules
    data_folder = main_folder + "/data/aruba-stack-2930/"
    output_file_path = "/data/yaml/aruba_stack_2930.yaml"

    device_type_slags = {
        'JL322A_stack': 'hpe-aruba-2930m-48g-poep'
    }

    devices_tags = ["switch", "stack"]

    print("Update data for Aruba 2930 stacks into the file: ", output_file_path) 
    stack_module(data_folder, output_file_path, device_type_slags, devices_tags)

    # Aruba 2920 stacks with LWL modules
    data_folder = main_folder + "/data/aruba-stack-2920/"
    output_file_path = "/data/yaml/aruba_stack_2920.yaml"

    device_type_slags = {
        'J9729A_stack': 'hpe-aruba-2920-48g-poep'
    }

    devices_tags = ["switch", "stack"]

    #assign_sfp_modules(data_folder)

    print("Update data for Aruba 2920 stacks into the file: ", output_file_path)
    stack_module(data_folder, output_file_path, device_type_slags, devices_tags)

    # Aruba modular stacks
    data_folder = main_folder + "/data/aruba-modular-stack/"
    output_file_path = "/data/yaml/aruba_modular_stack.yaml"

    device_type_slags = {
        'J9850A_stack': 'hpe-5406r-zl2'
    }

    devices_tags = ["switch", "stack"]

    print("Update data for Aruba modular stacks into the file: ", output_file_path)
    stack_module(data_folder, output_file_path, device_type_slags, devices_tags)

#----- Debugging -------
def debug_single():
    #data_folder = main_folder + "/data/aruba-12-ports/"
    data_folder = main_folder + "/data/hpe-8-ports/"
    device_type_slags = {
        'JL258A': "hpe-aruba-2930f-8g-poep-2sfpp",
        'JL693A': "hpe-aruba-2930f-12g-poep-2sfpp",

        'J9562A': 'hpe-procurve-2915-8-poe',
        'J9565A': 'hpe-procurve-2615-8-poe',
        'J9774A': 'hpe-aruba-2530-8g-poep',
        'J9780A': 'hpe-aruba-2530-8-poep'
    }

    print('---Debugging ', data_folder)
    single(data_folder, sys.stdout, device_type_slags, ["switch"])
    print('---END Debugging---')

def debug_modular():
    data_folder = main_folder + "/data/procurve-modular/"

    device_type_slags = { 
        'J8697A': 'hpe-procurve-5406zl',
        'J8698A': 'hpe-procurve-5412zl',
        'J8770A': 'hpe-procurve-4204vl',
        'J8773A': 'hpe-procurve-4208vl',
        'J9850A': 'hpe-5406r-zl2',
        'J9851A': 'hpe-5412r-zl2',
        'J9729A': 'hpe-aruba-2920-48g-poep',
        'J9729A_stack': 'hpe-aruba-2920-48g-poep'
    }

    print("---Debugging ", data_folder)
    modular(data_folder, sys.stdout, device_type_slags, ["switch", "modular-switch"])
    print('---END Debugging---')

if __name__ == "__main__":
    #debug_single()
    #debug_modular()

    main()