#!/usr/bin/env python3

# Collect ProCurve and old HP Switches data and create a hp_modular.yaml configs file 

import re, os, yaml
from tabulate import tabulate
from std_functions import this_folder, main_folder
from std_functions import serial_numbers, config_files
from std_functions import devices_json
#from std_functions import devices_json, trunks_json, interface_names_json
#from std_functions import vlans_jason, untagged_vlans_json, tagged_vlans_json
#from std_functions import ip_addresses_json

# Collect stack switches data to a YAML file
def stack(data_folder, output_file_path, device_type_slags, devices_tags):
    files = config_files(data_folder)
    with open(main_folder + output_file_path, 'w') as f:
        yaml.dump(devices_json(files, device_type_slags, devices_tags), f)

def main():
    # ProCurve 2M modular stacks
    data_folder = main_folder + "/data/procurve-modular-stack/"
    output_file_path = "/data/yaml/procurve_modular_stack.yaml"

    device_type_slags = {
        'J9729A': 'hpe-aruba-2920-48g-poep'
    }

    devices_tags = ["switch", "stack"]

    stack(data_folder, output_file_path, device_type_slags, devices_tags)


if __name__ == "__main__":
    main()
