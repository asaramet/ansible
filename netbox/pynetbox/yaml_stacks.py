#!/usr/bin/env python3

# Collect HPE stacked switches data and create a yaml configs files 

import re, os, yaml
from tabulate import tabulate
from std_functions import this_folder, main_folder
from std_functions import config_files, device_type
from std_functions import devices_json, trunks_json, interface_names_json
from std_functions import vlans_json, untagged_vlans_json, tagged_vlans_json
from std_functions import ip_addresses_json
from std_functions import get_hostname

module_types = {
    'jl083a': 'Aruba 3810M/2930M 4SFP+ MACsec Module',
    'j9731a': 'Aruba 2920 2-Port 10GbE SFP+ Module',
    'j9733a': 'Aruba 2920 2-Port Stacking Module',
    'j9827a': 'Aruba J9827A',
    'j9993a': 'Aruba J9993A',
    'j9988a': 'Aruba J9988A',
    'j9996a': 'Aruba J9996A'
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

    modules = []
    hostnames = get_hostname(t_file)

    # Modules for Aruba 2930 stacks
    names = {
        'A': 'Uplink'
    }

    flexible_modules = recursive_search("flexible-module", text)
    if len(flexible_modules) > 0:
        for line in flexible_modules:
            m_list = line.split()
            modules.append({'hostname': hostnames[m_list[1]], 'module': m_list[3], 'type': m_list[5], 'name': names[m_list[3]]})
        return modules

    clean_hostname, _ = hostnames['1'].split('-')

    # Modules for Aruba 2920 stacks
    module_2920 = {
        'rsgw7009sp': [ ('1', 'A', 'j9731a'), ('1', 'B', 'j9731a') ],
        'rsgw5313sp': [ ('1', 'A', 'j9731a'), ('1', 'STK', 'j9733a'), ('2', 'A', 'j9731a'), ('2', 'STK', 'j9733a'), ('3', 'A', 'j9731a'), ('3', 'STK', 'j9733a') ],
        'rsgw10118sp': [ ('1', 'A', 'j9731a'), ('1', 'STK', 'j9733a'), ('2', 'A', 'j9731a'), ('2', 'STK', 'j9733a'), ('3', 'STK', 'j9733a') ], 
        'rsgw1u140sp': [ ('1', 'A', 'j9731a'), ('1', 'STK', 'j9733a'), ('2', 'A', 'j9731a'), ('2', 'STK', 'j9733a'), ('3', 'STK', 'j9733a') ],
        'rsgw12205sp': [ ('1', 'A', 'j9731a'), ('1', 'STK', 'j9733a'), ('2', 'A', 'j9731a'), ('2', 'STK', 'j9733a'), ('3', 'STK', 'j9733a') ],
        'rsgw2112sp': [ ('1', 'A', 'j9731a'), ('1', 'STK', 'j9733a'), ('2', 'A', 'j9731a'), ('2', 'STK', 'j9733a'), ('3', 'A', 'j9731a'), ('3', 'STK', 'j9733a') ],
        'rsgw9108sp': [ ('1', 'A', 'j9731a'), ('1', 'STK', 'j9733a'), ('2', 'A', 'j9731a'), ('2', 'STK', 'j9733a'), ('3', 'STK', 'j9733a') ]
    }

    names = {
        'A': 'Module A',
        'B': 'Module B',
        'STK': 'Stacking Module'
    }

    if clean_hostname in module_2920.keys():
        for stack, module, m_type in module_2920[clean_hostname]:
            modules.append({'hostname': hostnames[stack], 'module': module, 'type': m_type, 'name': names[module]})
        return modules

    # Modules for Aruba Modular stacks
    module_chassis = {
        'rscs0007': [
            ('1', 'MM1', 'j9827a'), ('1', 'A', 'j9993a'), ('1', 'B', 'j9993a'), ('1', 'C', 'j9993a'), ('1', 'D', 'j9993a'), ('1', 'E', 'j9988a'), ('1', 'F', 'j9996a'),
            ('2', 'MM1', 'j9827a'), ('2', 'A', 'j9993a'), ('2', 'B', 'j9993a'), ('2', 'C', 'j9993a'), ('2', 'D', 'j9993a'), ('2', 'E', 'j9988a'), ('2', 'F', 'j9996a') 
         ]
    }

    if clean_hostname in module_chassis.keys():
        for stack, module, m_type in module_chassis[clean_hostname]:
            modules.append({'hostname': hostnames[stack], 'module': module, 'type': m_type, 'name': module})
        return modules

    return modules

def assign_sfp_modules(t_file):
    with open(main_folder + "/host_vars/99/sfp_modules.yaml", 'r' ) as f:
        modules = yaml.safe_load(f)
    return modules

# return the modules json object
def modules_json(config_files, module_types = {}):
    data = {'modules':[]}
    for t_file in config_files:
        modules = get_modules(t_file)

        for module in modules:
            _, stack_nr = module['hostname'].split('-')
            new_position = stack_nr + '/' + module['module']
            data['modules'].append({'device': module['hostname'], 'name': module['name'], 'module_bay': module['module'], 'new_position': new_position, 'type': module_types[module['type'].lower()]})
    return data

def device_interfaces_nr(config_files):
    nr_of_interfaces = {
        'JL256A_stack': (48, '1000base-t', 'pd', 'type2-ieee802.3at'),
        'JL075A_stack': (16, '10gbase-x-sfpp', None, None),
        'JL693A_stack': (12, '1000base-t', 'pd', 'type2-ieee802.3at'),
        'JL322A_stack': (48, '1000base-t', 'pd', 'type2-ieee802.3at'),
        'J9729A_stack': (48, '1000base-t', 'pd', 'type2-ieee802.3at'),
        'J9850A_stack': (None, None, None, None)
    }

    uplink_interfaces = {
        'JL693A_stack': ('13-14', '1000base-t', None, None)
    }

    sfp_interfaces = {
        'JL256A_stack': [('49-52', '10gbase-x-sfpp', None, None)],
        'JL693A_stack': [('15-16', '10gbase-x-sfpp', None, None)],
        #'JL322A_stack': ('A1-A4', '10gbase-x-sfpp', None, None)
        'J9850A_stack': [
            ('A1-A8', '10gbase-x-sfpp', None, None),
            ('B1-B8', '10gbase-x-sfpp', None, None),
            ('C1-C8', '10gbase-x-sfpp', None, None),
            ('D1-D8', '10gbase-x-sfpp', None, None),
            ('E1-E24', '1gbase-x-sfpp', None, None),
            ('F1-F2', '40gbase-q-sfpp', None, None)
        ]
    }

    data = {'device_interfaces':[]}
    for t_file in config_files:
        hostname = get_hostname(t_file)

        clean_name = hostname['1'][:-2]

        type_key = device_type(clean_name)
        nr_of_i, type_of_i, poe_mode, poe_type = nr_of_interfaces[type_key]

        for stack_nr, h_name in hostname.items():
            if not nr_of_i: continue

            for nr in range(1, int(nr_of_i) + 1):
                data['device_interfaces'].append({'name': h_name, 'stack_nr': stack_nr, 'interface': nr, 
                    'type': type_of_i, 'poe_mode': poe_mode, 'poe_type': poe_type})

        if type_key in uplink_interfaces.keys():
            range_of_i, type_of_i, poe_mode, poe_type = uplink_interfaces[type_key]
            start_i, end_i = range_of_i.split('-')

            for stack_nr, h_name in hostname.items():
                for nr in range(int(start_i), int(end_i) + 1, 1):
                    data['device_interfaces'].append({'name': h_name, 'stack_nr': stack_nr, 'interface': nr, 
                        'type': type_of_i, 'poe_mode': poe_mode, 'poe_type': poe_type})

        if type_key in sfp_interfaces.keys():
            for interfaces_range in sfp_interfaces[type_key]:
                range_of_i, type_of_i, poe_mode, poe_type = interfaces_range
                start_i, end_i = range_of_i.split('-')

                prefix_start = ''
                if re.match(r'[^\d]+', start_i): 
                    prefix_start = re.match(r'[^\d]+', start_i).group()
                    prefix_end = re.match(r'[^\d]+', end_i).group()

                    # Ensure the prefixes are the same
                    if prefix_start != prefix_end:
                        raise ValueError("Prefixes do not match")
                    
                    start_i = re.search(r'\d+', start_i).group()
                    end_i = re.search(r'\d+', end_i).group()

                for stack_nr, h_name in hostname.items():
                    for nr in range(int(start_i), int(end_i) + 1, 1):
                        data['device_interfaces'].append({'name': h_name, 'stack_nr': stack_nr, 'interface': prefix_start + str(nr), 
                            'type': type_of_i, 'poe_mode': poe_mode, 'poe_type': poe_type})

    return data

# Collect stack switches data to a YAML file
def stack(data_folder, output_file_path, device_type_slags, devices_tags):
    files = config_files(data_folder)
    with open(main_folder + output_file_path, 'w') as f:
        yaml.dump({"modular": False}, f)
        yaml.dump({"add_stack_interfaces": True}, f)
        yaml.dump(devices_json(files, device_type_slags, devices_tags), f)
        yaml.dump(device_interfaces_nr(files), f)
        yaml.dump(trunks_json(files), f)
        yaml.dump(interface_names_json(files), f)
        yaml.dump(vlans_json(files), f)
        yaml.dump(untagged_vlans_json(files), f)
        yaml.dump(tagged_vlans_json(files), f)
        yaml.dump(ip_addresses_json(files), f)

def stack_module(data_folder, output_file_path, device_type_slags, devices_tags):
    files = config_files(data_folder)

    add_stack_interfaces = True
    for f in files:
        if 'rscs0007' in f.split('/'):
            add_stack_interfaces = False

    with open(main_folder + output_file_path, 'w') as f:
        yaml.dump({"modular": True}, f)
        yaml.dump({"add_stack_interfaces": add_stack_interfaces}, f)
        yaml.dump(devices_json(files, device_type_slags, devices_tags), f)
        yaml.dump(device_interfaces_nr(files), f)
        yaml.dump(trunks_json(files), f)
        yaml.dump(interface_names_json(files), f)
        yaml.dump(vlans_json(files), f)
        yaml.dump(untagged_vlans_json(files), f)
        yaml.dump(tagged_vlans_json(files), f)
        yaml.dump(ip_addresses_json(files), f)

        yaml.dump(modules_json(files, module_types), f)

#----- Debugging -------
def debug_device_interfaces_nr(data_folder):
    files = config_files(data_folder)
    print(device_interfaces_nr(files))

def debug_get_modules(data_folder):
    table = []
    headers = ["File name", "Modules"]
    for f in config_files(data_folder):
        table.append([ os.path.basename(f), get_modules(f) ])
    print("\n== Debug: get_modules ==")
    print(tabulate(table, headers, "github"))


def test_stack_module_yaml():
    # Create test.yaml file from test folder
    data_folder = main_folder + "/data/test/"
    output_file_path = "/data/yaml/test.yaml"

    device_type_slags = {
        'JL322A_stack': 'hpe-aruba-2930m-48g-poep',
        'J9729A_stack': 'hpe-aruba-2920-48g-poep',
        'J9850A_stack': 'hpe-5406r-zl2'
    }

    devices_tags = ["switch", "stack"]

    print("Update test file: ", output_file_path) 
    stack_module(data_folder, output_file_path, device_type_slags, devices_tags)

def main():
    # Run Debugging
    #debug_data_folder = main_folder + "/data/aruba-stack/"
    #debug_data_folder = main_folder + "/data/aruba-stack-2930/"
    #debug_data_folder = main_folder + "/data/aruba-stack-2920/"
    debug_data_folder = main_folder + "/data/aruba-modular-stack/"

    #debug_device_interfaces_nr(debug_data_folder)
    #debug_get_modules(debug_data_folder)

    test_stack_module_yaml()

    # Aruba stacks (no extra modules)
    data_folder = main_folder + "/data/aruba-stack/"
    output_file_path = "/data/yaml/aruba_stack.yaml"

    device_type_slags = {
        'JL256A_stack': "hpe-aruba-2930f-48g-poep-4sfpp",
        'JL075A_stack': 'hpe-aruba-3810m-16sfpp-2-slot-switch',
        'JL693A_stack': "hpe-aruba-2930f-12g-poep-2sfpp"
    }

    devices_tags = ["switch", "stack"]

    print("Update data for Aruba stacks into the file: ", output_file_path) 
    stack(data_folder, output_file_path, device_type_slags, devices_tags)

    # Aruba 2930 stacks with LWL modules
    data_folder = main_folder + "/data/aruba-stack-2930/"
    output_file_path = "/data/yaml/aruba_stack_2930.yaml"

    device_type_slags = {
        'JL322A_stack': 'hpe-aruba-2930m-48g-poep'
    }

    devices_tags = ["switch", "stack"]

    print("Update data for Aruba 2930 stacks into the file: ", output_file_path) 
    stack_module(data_folder, output_file_path, device_type_slags, devices_tags)

    # Aruba 2920 stacks with LWL modules
    data_folder = main_folder + "/data/aruba-stack-2920/"
    output_file_path = "/data/yaml/aruba_stack_2920.yaml"

    device_type_slags = {
        'J9729A_stack': 'hpe-aruba-2920-48g-poep',
    }

    devices_tags = ["switch", "stack"]

    assign_sfp_modules(data_folder)

    print("Update data for Aruba 2920 stacks into the file: ", output_file_path)
    stack_module(data_folder, output_file_path, device_type_slags, devices_tags)

    # Aruba modular stacks
    data_folder = main_folder + "/data/aruba-modular-stack/"
    output_file_path = "/data/yaml/aruba_modular_stack.yaml"

    device_type_slags = {
        'J9850A_stack': 'hpe-5406r-zl2'
    }

    devices_tags = ["switch", "stack"]

    print("Update data for Aruba modular stacks into the file: ", output_file_path)
    stack_module(data_folder, output_file_path, device_type_slags, devices_tags)

if __name__ == "__main__":
    main()
