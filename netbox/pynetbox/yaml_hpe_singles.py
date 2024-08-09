#!/usr/bin/env python3

# Collect HPE switches data and create yaml configs file 

import re, os, yaml
from tabulate import tabulate
from std_functions import this_folder, main_folder
from std_functions import config_files
from std_functions import devices_json, trunks_json, interface_names_json
from std_functions import vlans_jason, untagged_vlans_json, tagged_vlans_json
from std_functions import ip_addresses_json

# Collect single switches data and saved it to a YAML file
def single(data_folder, output_file_path, device_type_slags, devices_tags):
    files = config_files(data_folder)
    with open(main_folder + output_file_path, 'w') as f:
        yaml.dump({"modular": False}, f)
        yaml.dump(devices_json(files, device_type_slags, devices_tags), f)
        yaml.dump(trunks_json(files), f)
        yaml.dump(interface_names_json(files), f)
        yaml.dump(vlans_jason(files), f)
        yaml.dump(untagged_vlans_json(files), f)
        yaml.dump(tagged_vlans_json(files), f)
        yaml.dump(ip_addresses_json(files), f)

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

    single(data_folder, output_file_path, device_type_slags, devices_tags)

    # HPE 24 and 48 Ports Switches
    data_folder = main_folder + "/data/hpe-48-ports/"
    output_file_path = "/data/yaml/hpe_48_ports.yaml"

    device_type_slags = {
      'J9623A': 'hpe-aruba-2620-24',
      'J9772A': 'hpe-aruba-2530-48g-poep',
      'J9853A': 'hpe-aruba-2530-48g-poep-2sfpp'
    }

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

    single(data_folder, output_file_path, device_type_slags, devices_tags)

    # Aruba 8 Ports Switches
    data_folder = main_folder + "/data/aruba-8-ports/"
    output_file_path = "/data/yaml/aruba_8_ports.yaml"

    device_type_slags = {
        'JL258A': "hpe-aruba-2930f-8g-poep-2sfpp"
    }

    single(data_folder, output_file_path, device_type_slags, devices_tags)

    # Aruba 12 Ports Switches
    data_folder = main_folder + "/data/aruba-12-ports/"
    output_file_path = "/data/yaml/aruba_12_ports.yaml"

    device_type_slags = {
        'JL693A': "hpe-aruba-2930f-12g-poep-2sfpp"
    }

    single(data_folder, output_file_path, device_type_slags, devices_tags)

if __name__ == "__main__":
    main()