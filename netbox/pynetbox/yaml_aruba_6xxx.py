#!/usr/bin/env python3

# Collect Aruba 6xxx data and create a yaml configs file 

import re, os, yaml
from tabulate import tabulate
from std_functions import main_folder, config_files

from json_functions import locations_json, vlans_json
from json_functions import device_interfaces_json

from json_functions_os_cx import devices_json
from json_functions_os_cx import ip_addresses_json, lags_json, interfaces_json

# Collect all the data and saved it to a YAML file
def to_yaml(data_folder, output_file_path, device_type_slags, devices_tags):
    files = config_files(data_folder)
    with open(main_folder + output_file_path, 'w') as f:
        yaml.dump(locations_json(files), f)
        yaml.dump(devices_json(files, device_type_slags, devices_tags), f)
        yaml.dump(device_interfaces_json(files), f)
        yaml.dump(ip_addresses_json(files), f)
        yaml.dump(lags_json(files), f)
        yaml.dump(vlans_json(files), f)
        yaml.dump(interfaces_json(files), f)

def main():
    #--- 6100 ---
    data_folder = main_folder + "/data/aruba_6100/"
    output_file_path = "/data/yaml/aruba_6100.yaml"
    print("Update data for Aruba 6100 Switches into the file: ", output_file_path)

    device_type_slags = {
        "JL679A": "hpe-aruba-6100-12g-poe4-2sfpp"
    }

    devices_tags = ["switch"]

    to_yaml(data_folder, output_file_path, device_type_slags, devices_tags)

    #--- 6300 ---
    data_folder = main_folder + "/data/aruba_6300/"
    output_file_path = "/data/yaml/aruba_6300.yaml"
    print("Update data for Aruba 6300 Switches into the file: ", output_file_path)

    device_type_slags = {
        "JL658A_stack": "hpe-aruba-6300m-24sfpp-4sfp56"
    }

    devices_tags = ["switch", "stack"]

    to_yaml(data_folder, output_file_path, device_type_slags, devices_tags)

#---- Debugging ----#
def test_to_yaml(data_folder):
    # Create test.yaml file from test folder

    output_file_path = "/data/yaml/test.yaml"

    slags = {
        "JL679A": "hpe-aruba-6100-12g-poe4-2sfpp",
        "JL658A_stack": "hpe-aruba-6300m-24sfpp-4sfp56"
    }

    print("Dump test data into the file: " + output_file_path)
    to_yaml(data_folder, output_file_path, slags, ["switch"])

if __name__ == "__main__":
    main()

#    print("\n=== Debugging Aruba 6100 ===")
#    data_folder = main_folder + "/data/aruba_6100/"

#    config_file = data_folder + "rggw1018bp"

#    test_to_yaml(data_folder)

#    print("\n=== Debugging Aruba 6300 ===")
#    data_folder = main_folder + "/data/aruba_6300/"

#    config_file = data_folder + "rgcs0006"

#    test_to_yaml(data_folder)