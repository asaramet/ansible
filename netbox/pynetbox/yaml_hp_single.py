#!/usr/bin/env python3

# Collect ProCurve and Aruba single switches data and create a hp_single.yaml configs file 

import re, os, yaml
from std_functions import this_folder, main_folder
from std_functions import config_files
from std_functions import search_line
from std_functions import get_hostname, get_site, get_device_role
from std_functions import serial_numbers, device_type

data_folder = main_folder + "/data/hp-single/"

def set_tags():
    return "switch"

# return the devices json object
def devices_json(config_files):
    d_types = { 
        'J9085A': 'hpe-procurve-2610-24',
        'J9086A': 'hpe-procurve-2610-24-12-pwr',
        'J9089A': 'hpe-procurve-2610-48-pwr'
    }

    data = {'devices':[]}
    for t_file in config_files:
        hostname = get_hostname(t_file)
        d_type = d_types[device_type(hostname)]
        data['devices'].append({'name': hostname, 'device_role': get_device_role(t_file), 'device_type': d_type,
            'site': get_site(t_file), 'tags': set_tags(), 'serial':serial_numbers()[hostname]})
    return data

# Collect all the data and saved it to a YAML file
def main():
    # get data files
    files = config_files(data_folder)

    with open(main_folder + "/data/yaml/hp_single.yaml", 'w') as f:
        yaml.dump(devices_json(files), f)

if __name__ == "__main__":
    main()