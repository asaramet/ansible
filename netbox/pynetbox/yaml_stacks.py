#!/usr/bin/env python3

# Collect HPE stacked switches data and create a yaml configs files 

import re, os, yaml
from tabulate import tabulate
from std_functions import this_folder, main_folder
from std_functions import config_files
from std_functions import devices_json, trunks_json, interface_names_json
from std_functions import vlans_jason, untagged_vlans_json, tagged_vlans_stack_json
from std_functions import ip_addresses_json
from std_functions import get_hostname

module_types = {
    'jl083a': 'Aruba 3810M/2930M 4SFP+ MACsec Module'
}

# search lines in a text recursively
def recursive_search(pattern, text):
    # base case
    if not text:
        return []

    found_lines = []
    for i, line in enumerate(text):
        if pattern in line:
            found_lines.append(line.strip())

            found_lines += recursive_search(pattern, text[i+1:])
            break 

    return found_lines

def get_modules(t_file):
    with open(t_file, "r") as f:
        text = f.readlines()

    names = {
        'A': 'Uplink'
    }

    modules = []
    hostnames = get_hostname(t_file)

    flexible_modules = recursive_search("flexible-module", text)
    if len(flexible_modules) > 0:
        for line in flexible_modules:
            m_list = line.split()
            modules.append({'hostname': hostnames[m_list[1]], 'module': m_list[3], 'type': m_list[5], 'name': names[m_list[3]]})
        return modules

    return modules

# return the modules json object
def modules_json(config_files, module_types = {}):
    data = {'modules':[]}
    for t_file in config_files:
        modules = get_modules(t_file)

        for module in modules:
            data['modules'].append({'device': module['hostname'], 'name': module['name'], 'module_bay': module['module'], 'type': module_types[module['type'].lower()]})
    return data

# Collect stack switches data to a YAML file
def stack(data_folder, output_file_path, device_type_slags, devices_tags):
    files = config_files(data_folder)
    with open(main_folder + output_file_path, 'w') as f:
        yaml.dump({"modular": False}, f)
        yaml.dump(devices_json(files, device_type_slags, devices_tags), f)
        yaml.dump(trunks_json(files), f)
        yaml.dump(interface_names_json(files), f)
        yaml.dump(vlans_jason(files), f)
        yaml.dump(untagged_vlans_json(files), f)
        yaml.dump(tagged_vlans_stack_json(files), f)
        yaml.dump(ip_addresses_json(files), f)

def stack_module(data_folder, output_file_path, device_type_slags, devices_tags):
    files = config_files(data_folder)
    with open(main_folder + output_file_path, 'w') as f:
        yaml.dump({"modular": True}, f)
        yaml.dump(devices_json(files, device_type_slags, devices_tags), f)
        yaml.dump(trunks_json(files), f)
        yaml.dump(interface_names_json(files), f)
        yaml.dump(vlans_jason(files), f)
        yaml.dump(untagged_vlans_json(files), f)
        yaml.dump(tagged_vlans_stack_json(files), f)
        yaml.dump(ip_addresses_json(files), f)

        yaml.dump(modules_json(files, module_types), f)

def main():
    # Aruba stacks (no extra modules)
    data_folder = main_folder + "/data/aruba-stack/"
    output_file_path = "/data/yaml/aruba_stack.yaml"

    device_type_slags = {
        'JL256A_stack': "hpe-aruba-2930f-48g-poep-4sfpp",
        'JL075A_stack': 'hpe-aruba-3810m-16sfpp-2-slot-switch',
        'JL693A_stack': "hpe-aruba-2930f-12g-poep-2sfpp"
    }

    devices_tags = ["switch", "stack"]

    stack(data_folder, output_file_path, device_type_slags, devices_tags)

    # Aruba 2930 stacks with LWL modules
    data_folder = main_folder + "/data/aruba-stack-2930/"
    output_file_path = "/data/yaml/aruba_stack_2930.yaml"

    device_type_slags = {
        'JL322A_stack': 'hpe-aruba-2930m-48g-poep'
    }

    devices_tags = ["switch", "stack"]

    stack_module(data_folder, output_file_path, device_type_slags, devices_tags)

    # Aruba 2920 stacks with LWL modules
    data_folder = main_folder + "/data/aruba-stack-2920/"
    output_file_path = "/data/yaml/aruba_stack_2920.yaml"

    device_type_slags = {
        'J9729A_stack': 'hpe-aruba-2920-48g-poep',
    }

    devices_tags = ["switch", "stack"]

    #stack_module(data_folder, output_file_path, device_type_slags, devices_tags)

    # Aruba modular stacks
    data_folder = main_folder + "/data/aruba-modular-stack/"
    output_file_path = "/data/yaml/aruba_modular_stack.yaml"

    device_type_slags = {
        'J9850A_stack': 'hpe-5406r-zl2'
    }

    devices_tags = ["switch", "stack"]

    #stack_module(data_folder, output_file_path, device_type_slags, devices_tags)

if __name__ == "__main__":
    main()
