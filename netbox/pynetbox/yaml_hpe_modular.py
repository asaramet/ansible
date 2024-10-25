#!/usr/bin/env python3

# Collect HPE modular switches data and create yaml configs file 

import re, os, yaml
from tabulate import tabulate
from std_functions import this_folder, main_folder, config_files
from std_functions import recursive_search, get_hostname, get_modules

from json_functions import devices_json, trunks_json, device_interfaces_json
from json_functions import vlans_json, untagged_vlans_json, tagged_vlans_json
from json_functions import ip_addresses_json, locations_json

# Collect modular switches data and saved it to a YAML file
def modular(data_folder, output_file_path, device_type_slags, devices_tags, module_types):
    files = config_files(data_folder)
    with open(main_folder + output_file_path, 'w') as f:
        yaml.dump({"modular": True}, f)
        yaml.dump(locations_json(files), f)
        yaml.dump(devices_json(files, device_type_slags, devices_tags), f)
        yaml.dump(modules_json(files, module_types), f)
        yaml.dump(trunks_json(files), f)
        yaml.dump(device_interfaces_json(files), f)
        yaml.dump(vlans_json(files), f)
        yaml.dump(untagged_vlans_json(files), f)
        yaml.dump(tagged_vlans_json(files), f)
        yaml.dump(ip_addresses_json(files), f)

def main():
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
        'J9729A': 'hpe-aruba-2920-48g-poep'
    }

    print("Update data for ProCurve modular Switches into the file: ", output_file_path) 
    modular(data_folder, output_file_path, device_type_slags, devices_tags, module_types)

    # Aruba Modular Switches
    data_folder = main_folder + "/data/aruba-modular/"
    output_file_path = "/data/yaml/aruba_modular.yaml"

    devices_tags = ["switch", "modular-switch"]

    device_type_slags = { 
        'JL322A_module': "hpe-aruba-2930m-48g-poep"
    }

    print("Update data for Aruba modular Switches into the file: ", output_file_path) 
    modular(data_folder, output_file_path, device_type_slags, devices_tags, module_types)

if __name__ == "__main__":
    main()