#!/usr/bin/env python3

# Collect HPE modular switches data and create yaml configs file 

import re, os, yaml
from tabulate import tabulate
from std_functions import this_folder, main_folder, config_files
from std_functions import recursive_search, get_hostname

from json_functions import devices_json, trunks_json, interface_names_json
from json_functions import vlans_json, untagged_vlans_json, tagged_vlans_json
from json_functions import ip_addresses_json, locations_json

module_types = {
    "j8702a": "ProCurve 24-port 10/100/1000Base-T PoE Switch Module",
    "j8705a": "HP J8705A ProCurve PoE 20 Port Gig-T SFP Plus 4 Port Mini GBIC ZL Module",
    "j8706a": "ProCurve Switch 5400zl 24p Mini-GBIC Module",
    "j8707a": "HP 4-Port 10GbE X2 ZL Module",
    "j8765a": "ProCurve Switch VL 24-Port 10/100-TX Module",
    "j8766a": "HP ProCurve J8766A VL 1-Port 10GbE X2 ZL Module",
    "j8768a": "ProCurve Switch 24-port Gig-T vl Module",
    "j9033a": "HP ProCurve Switch vl 20-Port Gig-T+ 4 SFP Module",
    "j9534a": "Aruba J9534A",
    "j9550a": "HP 24-Port GiG-T v2 ZL Module",
    "j9537a": "Aruba J9537A",
    "j9538a": "Aruba J9538A",
    "j9731a": "Aruba 2920 2-Port 10GbE SFP+ Module",
    "j9729a": "Aruba 2920 2-Port 10GbE SFP+ Module", # same as j9731a
    "j9986a": "Aruba J9986A",
    "j9990a": "Aruba J9990A",
    "j9992a": "Aruba J9992A",
    "j9993a": "Aruba J9993A",
    'jl083a': 'Aruba 3810M/2930M 4SFP+ MACsec Module'
}

def get_modules(t_file):
    with open(t_file, "r") as f:
        text = f.readlines()

    names = {
        '1': 'A', '2': 'B', '3': 'C', '4': 'D', '5': 'E', '6': 'F',
        '7': 'G', '8': 'H', '9': 'I', '10': 'J', '11': 'K', '12': 'L'
    }

    modules = []

    flexible_modules = recursive_search("flexible-module", text)
    if len(flexible_modules) > 0:
        for line in flexible_modules:
            m_list = line.split()
            modules.append({'module': m_list[1], 'type': m_list[3]})
        return modules

    for line in recursive_search("module", text, True):
        m_list = line.split()
        name = m_list[1]
        if name in names.keys():
            name = names[name]
        modules.append({'module': name, 'type': m_list[3]})
    return modules

# return the modules json object
def modules_json(config_files, module_types = {}):
    data = {'modules':[]}
    for t_file in config_files:
        modules = get_modules(t_file)
        hostnames = get_hostname(t_file)

        device = hostnames['0']

        for module in modules:
            data['modules'].append({'device': device, 'module_bay': module['module'], 'type': module_types[module['type'].lower()]})
    return data

# Collect modular switches data and saved it to a YAML file
def modular(data_folder, output_file_path, device_type_slags, devices_tags, module_types):
    files = config_files(data_folder)
    with open(main_folder + output_file_path, 'w') as f:
        yaml.dump({"modular": True}, f)
        yaml.dump(locations_json(files), f)
        yaml.dump(devices_json(files, device_type_slags, devices_tags), f)
        yaml.dump(modules_json(files, module_types), f)
        yaml.dump(trunks_json(files), f)
        yaml.dump(interface_names_json(files), f)
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

#---- Debugging ----#
def debug_get_modules(data_folder):
    table = []
    types = set()
    headers = ["File Name", "Modules"]
    for f in config_files(data_folder):
        modules = get_modules(f)
        table.append([os.path.basename(f), modules])
        for module in modules:
            types.add(module['type'])
    print(tabulate(table, headers, "github"))

if __name__ == "__main__":
    main()

    data_folder = main_folder + "/data/procurve-modular/"
    #data_folder = main_folder + "/data/aruba-modular/"
    #debug_get_modules(data_folder)