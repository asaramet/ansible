#!/usr/bin/env python3

# Collect HPE stacked switches data and create a yaml configs files 

import re, os, yaml
from tabulate import tabulate
from std_functions import this_folder, main_folder
from std_functions import config_files
from std_functions import devices_json
#from std_functions import devices_json, trunks_json, interface_names_json
#from std_functions import vlans_jason, untagged_vlans_json, tagged_vlans_json
#from std_functions import ip_addresses_json

# Collect stack switches data to a YAML file
def stack(data_folder, output_file_path, device_type_slags, devices_tags):
    files = config_files(data_folder)
    with open(main_folder + output_file_path, 'w') as f:
        yaml.dump(devices_json(files, device_type_slags, devices_tags), f)

def stack_module(data_folder, output_file_path, device_type_slags, devices_tags):
    pass

def main():
    # Aruba stacks (no extra modules)
    data_folder = main_folder + "/data/aruba-stack/"
    output_file_path = "/data/yaml/aruba_stack.yaml"

    device_type_slags = {
        'JL256A_stack': '',
        'JL075A_stack': '',
        'JL693A_stack': ''
    }

    devices_tags = ["switch", "stack"]

    stack(data_folder, output_file_path, device_type_slags, devices_tags)

    # HPE stacks with LWL modules
    data_folder = main_folder + "/data/hpe-stack/"
    output_file_path = "/data/yaml/hpe_stack.yaml"

    device_type_slags = {
        'J9729A_stack': 'hpe-aruba-2920-48g-poep',
        'JL322A_stack': ''
    }

    devices_tags = ["switch", "stack"]

    stack_module(data_folder, output_file_path, device_type_slags, devices_tags)

    # Aruba modular staks
    data_folder = main_folder + "/data/aruba-modular-stack/"
    output_file_path = "/data/yaml/aruba_modular_stack.yaml"

    device_type_slags = {
        'J9850A_stack': ''
    }

    devices_tags = ["switch", "stack"]

    #stack_module(data_folder, output_file_path, device_type_slags, devices_tags)

if __name__ == "__main__":
    main()
