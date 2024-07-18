#!/usr/bin/env python3

# Collect ProCurve and Aruba single switches data and create a hp_single.yaml configs file 

import re, os, yaml
from std_functions import this_folder, main_folder
from std_functions import search_line, get_hostname
from std_functions import serial_numbers, device_type

#data_folder = main_folder + "/data/hp-modular/"
data_folder = main_folder + "/data/hp-single/"

# Collect all the data and saved it to a YAML file
def main():
    # get data files
    files = os.listdir(data_folder)
    print(files)
    files = [data_folder + f for f in files if os.path.isfile(data_folder + f)]
    print(files)

#    with open(main_folder + "/data/yaml/hp_single.yaml", 'w') as f:
#        yaml.dump(devices_json(files), f)

if __name__ == "__main__":
    main()