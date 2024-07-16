#!/usr/bin/env  python3

import os, yaml

this_folder = os.path.dirname(os.path.realpath(__file__))
main_folder = os.path.dirname(this_folder)

# Return a list of devices serial numbers from the yaml file
def serial_numbers():
    yaml_file = main_folder + "/data/src/serial_numbers.yaml"

    s_dict = {}
    with open(yaml_file, 'r') as f:
        for v_dict in yaml.safe_load(f):
            for key, value in v_dict.items():
                s_dict[key] = value

    return s_dict

# Return a list of devices dictionary
def devices():
    yaml_file = main_folder + "/data/src/devices.yaml"

    with open(yaml_file, 'r') as f:
        return yaml.safe_load(f)

    return None

# Return device type for a given hostname
def device_type(hostname):
    for d_type, d_list in devices().items():
        if hostname in d_list:
            return d_type

    return None

if __name__ == "__main__":
    #print(serial_numbers())
    #print(devices())
    print(device_type('rgcs0003'))
    print(device_type('rhsw1004p'))