#!/usr/bin/env python3

# Collect ProCurve and Aruba single switches data and create a hp_single.yaml configs file 

import re, os, yaml
from std_functions import this_folder, main_folder, config_files
from std_functions import devices_json, trunks_json, interface_names_json
from std_functions import vlans_jason, untagged_vlans_json, tagged_vlans_json
from std_functions import ip_addresses_json

data_folder = main_folder + "/data/hp-single/"

devices_tags = "switch"

device_type_slags = {
    'J9085A': 'hpe-procurve-2610-24',
    'J9086A': 'hpe-procurve-2610-24-12-pwr',
    'J9089A': 'hpe-procurve-2610-48-pwr'
}

# Collect all the data and saved it to a YAML file
def main():
    # get data files
    files = config_files(data_folder)

    with open(main_folder + "/data/yaml/hp_single.yaml", 'w') as f:
        yaml.dump({"modular": False}, f)
        yaml.dump(devices_json(files, device_type_slags, devices_tags), f)
        yaml.dump(trunks_json(files), f)
        yaml.dump(interface_names_json(files), f)
        yaml.dump(vlans_jason(files), f)
        yaml.dump(untagged_vlans_json(files), f)
        yaml.dump(tagged_vlans_json(files), f)
        yaml.dump(ip_addresses_json(files), f)

if __name__ == "__main__":
    main()