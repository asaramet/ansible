#!/usr/bin/env python3

# Collect ProCurve and old HP Switches data and create a hp_modular.yaml configs file 

import re, os, yaml
from tabulate import tabulate
from std_functions import this_folder, main_folder
from std_functions import serial_numbers, config_files
from std_functions import recursive_search, get_hostname
from std_functions import devices_json, trunks_json, interface_names_json
from std_functions import vlans_jason, untagged_vlans_json, tagged_vlans_json
from std_functions import ip_addresses_json


def get_modules(t_file):
    with open(t_file, "r") as f:
        text = f.readlines()

    names = {
        '1': 'A', '2': 'B', '3': 'C', '4': 'D', '5': 'E', '6': 'F',
        '7': 'G', '8': 'H', '9': 'I', '10': 'J', '11': 'K', '12': 'L'
    }
    modules = []
    for line in recursive_search(text, "module"):
        m_list = line.split()
        name = m_list[1]
        if name in names.keys():
            name = names[name]
        modules.append({'module': name, 'type': m_list[3]})
    return modules

# return the modules json object
def modules_json(config_files):
    data = {'modules':[]}
    types = {
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
        "j9993a": "Aruba J9993A"
        }
    for t_file in config_files:
        modules = get_modules(t_file)
        device = get_hostname(t_file)

        for module in modules:
            data['modules'].append({'device': device, 'module_bay': module['module'], 'type': types[module['type'].lower()]})
    return data

# Collect modular switches data and saved it to a YAML file
def modular():
    data_folder = main_folder + "/data/procurve-modular/"

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

    files = config_files(data_folder)
    with open(main_folder + "/data/yaml/procurve_modular.yaml", 'w') as f:
        yaml.dump({"modular": True}, f)
        yaml.dump(devices_json(files, device_type_slags, devices_tags), f)
        yaml.dump(modules_json(files), f)
        yaml.dump(trunks_json(files), f)
        yaml.dump(interface_names_json(files), f)
        yaml.dump(vlans_jason(files), f)
        yaml.dump(untagged_vlans_json(files), f)
        yaml.dump(tagged_vlans_json(files), f)
        yaml.dump(ip_addresses_json(files), f)

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
    # ProCurve Modular Switches
    modular()

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


#---- Debugging ----#
def debug_get_modules():
    table = []
    types = set()
    headers = ["File Name", "Modules"]
    for f in config_files(data_folder):
        modules = get_modules(f)
        table.append([os.path.basename(f), modules])
        for module in modules:
            types.add(module['type'])
    print(tabulate(table, headers, "github"))
    print(types)

if __name__ == "__main__":
    main()
    #debug_get_modules()