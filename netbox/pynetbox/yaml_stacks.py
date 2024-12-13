#!/usr/bin/env python3

# Collect HPE stacked switches data and create a yaml configs files 

import re, os, yaml
from tabulate import tabulate
from std_functions import this_folder, main_folder, get_hostname, get_modules
from std_functions import config_files, device_type, recursive_search
from json_functions import devices_json, trunks_json, device_interfaces_json
from json_functions import vlans_json, untagged_vlans_json, tagged_vlans_json
from json_functions import ip_addresses_json, locations_json, modules_json

def assign_sfp_modules(t_file):
    with open(main_folder + "/host_vars/99/sfp_modules.yaml", 'r' ) as f:
        modules = yaml.safe_load(f)
    return modules

# Collect stack switches data to a YAML file
def stack(data_folder, output_file_path, device_type_slags, devices_tags):
    files = config_files(data_folder)
    with open(main_folder + output_file_path, 'w') as f:
        yaml.dump({"modular": False}, f)
        yaml.dump({"add_stack_interfaces": True}, f)
        yaml.dump(locations_json(files), f)
        yaml.dump(devices_json(files, device_type_slags, devices_tags), f)
        yaml.dump(device_interfaces_json(files), f)
        yaml.dump(trunks_json(files), f)
        yaml.dump(vlans_json(files), f)
        yaml.dump(untagged_vlans_json(files), f)
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
        yaml.dump({"add_stack_interfaces": add_stack_interfaces}, f)
        yaml.dump(locations_json(files), f)
        yaml.dump(devices_json(files, device_type_slags, devices_tags), f)
        yaml.dump(device_interfaces_json(files), f)
        yaml.dump(trunks_json(files), f)
        yaml.dump(vlans_json(files), f)
        yaml.dump(untagged_vlans_json(files), f)
        yaml.dump(tagged_vlans_json(files), f)
        yaml.dump(ip_addresses_json(files), f)

        yaml.dump(modules_json(files), f)

#----- Debugging -------
def test_stack_module_yaml():
    # Create test.yaml file from test folder
    data_folder = main_folder + "/data/test/"
    output_file_path = "/data/yaml/test.yaml"

    device_type_slags = {
        'JL322A_stack': 'hpe-aruba-2930m-48g-poep',
        'J9729A_stack': 'hpe-aruba-2920-48g-poep',
        'J9850A_stack': 'hpe-5406r-zl2'
    }

    devices_tags = ["switch", "stack"]

    print("Update test file: ", output_file_path) 
    stack_module(data_folder, output_file_path, device_type_slags, devices_tags)

def main():
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
        'J9729A_stack': 'hpe-aruba-2920-48g-poep',
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

if __name__ == "__main__":
    main()

    # Run Debugging
    #debug_data_folder = main_folder + "/data/aruba-stack/"
    #debug_data_folder = main_folder + "/data/aruba-stack-2930/"
    #debug_data_folder = main_folder + "/data/aruba-stack-2920/"
    #debug_data_folder = main_folder + "/data/aruba-modular-stack/"

    #test_stack_module_yaml()
