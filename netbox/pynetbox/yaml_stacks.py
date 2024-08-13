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
        yaml.dump({"modular": False}, f)
        yaml.dump(devices_json(files, device_type_slags, devices_tags), f)
        #yaml.dump(trunks_json(files), f)

def stack_module(data_folder, output_file_path, device_type_slags, devices_tags):
    pass

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

    stack(data_folder, output_file_path, device_type_slags, devices_tags)

    # HPE stacks with LWL modules
    data_folder = main_folder + "/data/hpe-stack/"
    output_file_path = "/data/yaml/hpe_stack.yaml"

    device_type_slags = {
        'J9729A_stack': 'hpe-aruba-2920-48g-poep',
        'JL322A_stack': 'hpe-aruba-2930m-48g-poep'
    }

    devices_tags = ["switch", "stack"]

    stack_module(data_folder, output_file_path, device_type_slags, devices_tags)

    # Aruba modular staks
    data_folder = main_folder + "/data/aruba-modular-stack/"
    output_file_path = "/data/yaml/aruba_modular_stack.yaml"

    device_type_slags = {
        'J9850A_stack': 'hpe-5406r-zl2'
    }

    devices_tags = ["switch", "stack"]

    #stack_module(data_folder, output_file_path, device_type_slags, devices_tags)

if __name__ == "__main__":
    main()
