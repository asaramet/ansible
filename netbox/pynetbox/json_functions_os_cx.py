#!/usr/bin/env python3

#----- Return JSON Objects for Aruba OS-CX -----#

import re, os, yaml
from std_functions import main_folder, config_files
from std_functions import device_type, serial_numbers
from std_functions import get_hostname, get_site

from extra_functions import get_location, get_room_location

from std_functions_os_cx import get_uplink_vlan


# create devices json objects list
def devices_json(config_files, type_slags, tags):
    data = {"devices":[], "chassis":[]}
    rsm_vlans = ['102','202','302']

    for file in config_files:

        location,room = get_location(file)
        location = get_room_location(location)

        uplink_vlan = get_uplink_vlan(file)
        
        device_role = "bueroswitch" if uplink_vlan in rsm_vlans else "access-layer-switch"

        hostnames = get_hostname(file)
        clean_name = None

        if '0' not in hostnames.keys():
            hostname = hostnames['1']
            clean_name = hostname[:-2]
            data['chassis'].append({'master': hostname, 'name': clean_name})

        for key in hostnames.keys():
            hostname = hostnames[key]

            if not clean_name:
                clean_name = hostname

            if hostname[2:4] == "cs":
                device_role = "distribution-layer-switch"

            d_type = type_slags[device_type(clean_name)]

            data["devices"].append({"name": hostname, "location": location, "site": get_site(clean_name), "device_role": device_role, 
                "device_type": d_type, "serial": serial_numbers()[hostname], "tags": tags })

    return data


def debug_devices_json(data_folder):
    device_type_slags = {
      "JL679A": "hpe-aruba-6100-12g-poe4-2sfpp",
      "JL658A_stack": "hpe-aruba-6300m-24sfpp-4sfp56"
    }

    files = config_files(data_folder)
    devices_tags = ["switch"]
    output = yaml.dump(devices_json(files, device_type_slags, devices_tags))

    print("\n'device_json()' Output: for ", data_folder)
    print(output)

if __name__ == "__main__":
    print("\n=== Aruba 6100 ===")
    data_folder = main_folder + "/data/aruba_6100/"

    config_file = data_folder + "rggw1018bp"

    debug_devices_json(data_folder)

    print("\n=== Aruba 6300 ===")
    data_folder = main_folder + "/data/aruba_6300/"

    config_file = data_folder + "rgcs0006"

    debug_devices_json(data_folder)