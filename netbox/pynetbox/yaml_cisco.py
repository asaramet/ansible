#!/usr/bin/env python3

# Collect Cisco devices data and create a yaml configs files 

import re, os, yaml
from tabulate import tabulate
from std_functions import this_folder, main_folder, serial_numbers
from std_functions import config_files, search_line, recursive_search
from std_functions import get_site
#from std_functions import devices_json, trunks_json, interface_names_json
#from std_functions import vlans_json, untagged_vlans_json, tagged_vlans_json
#from std_functions import ip_addresses_json

def routers_list():
    with open(main_folder + "/host_vars/99/devices.yaml", 'r' ) as f:
        routers = yaml.safe_load(f)['routers']
    return routers    

def get_hostname(t_file):
    return search_line('hostname', t_file).split()[1]

def get_stacks(t_file):
    with open(t_file, "r") as f:
        text = f.readlines()

    switches = []

    for line in recursive_search("switch", text, True):
        line = line.split()
        if line[2] == 'provision':
            switches.append({'stack': line[1], 'type': line[3], 'modular': False})

    if switches: # not an empty list
        return switches

    # get modular stacks
    module_types = {
        'rgcs0003': 'ws-c4506-e'
    }

    hostname = search_line('hostname', t_file).split()[1]

    for line in recursive_search("module", text, True):
        line = line.split()
        switches.append({'stack': line[-1], 'type': module_types[hostname], 'modular': True})

    return switches

def get_hostnames(t_file):
    hostnames = {}

    hostname = get_hostname(t_file)
    stacks = get_stacks(t_file)

    for stack in stacks:
        stack = stack['stack']

        hostnames[stack] = hostname + '-' + stack

    return hostnames

def get_device_role(t_file, hostname):

    if hostname in routers_list():
        return "router"

    role_code = hostname[2:4]
    if role_code == "cs":
        return "distribution-layer-switch"

    return "access-layer-switch"

# ==== JSON functions ====
def devices_json(config_files):
    data = {'devices':[], 'chassis':[]}
    for t_file in config_files:
        clean_name = get_hostname(t_file)
        stacks = get_stacks(t_file)
        hostnames = get_hostnames(t_file)

        device_role = get_device_role(t_file, clean_name)

        tags = ['router'] if device_role == 'router' else ["switch", "stack"]

        master = hostnames['1']

        data['chassis'].append({'name': clean_name, 'master': master})

        for stack in stacks:
            stack_nr = stack['stack']
            hostname = hostnames[stack_nr]

            vc_position = int(stack_nr)
            vc_priority = 255 if vc_position == 1 else 128

            data['devices'].append({'name': hostname, 'device_role': device_role, 'device_type': stack['type'],
                'site': get_site(clean_name), 'tags': tags, 'serial':serial_numbers()[hostname],
                'virtual_chassis': clean_name, 'vc_position': vc_position, 'vc_priority': vc_priority
            })

    return data


# Collect stack switches data to a YAML file
def stack(data_folder, output_file_path):
    files = config_files(data_folder)
    with open(main_folder + output_file_path, 'w') as f:
        yaml.dump(devices_json(files), f)
        #yaml.dump(device_interfaces_nr(files), f)
        #yaml.dump(trunks_json(files), f)
        #yaml.dump(interface_names_json(files), f)
        #yaml.dump(vlans_json(files), f)
        #yaml.dump(untagged_vlans_json(files), f)
        #yaml.dump(tagged_vlans_json(files), f)
        #yaml.dump(ip_addresses_json(files), f)

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
def debug_routers_list():
    print("\n== Debug: routers_list ==")
    print(routers_list())

def debug_get_stacks(data_folder):
    table = []
    headers = ["File name", "Switches"]

    for f in config_files(data_folder):
        table.append([ os.path.basename(f), get_stacks(f) ])

    print("\n== Debug: get_stacks ==")
    print(tabulate(table, headers, "github"))

def debug_get_hostnames(data_folder):
    table = []
    headers = ["File name", "Hostnames"]

    for f in config_files(data_folder):
        table.append([ os.path.basename(f), get_hostnames(f) ])

    print("\n== Debug: get_hostnames ==")
    print(tabulate(table, headers, "github"))

def debug_get_device_role(data_folder):
    table = []
    headers = ["File name", "Device role"]

    for f in config_files(data_folder):
        table.append([ os.path.basename(f), get_device_role(f, get_hostname(f)) ])

    print("\n== Debug: get_device_role ==")
    print(tabulate(table, headers, "github"))

#---- debug JSON -----
def debug_devices_json(data_folder):
    files = config_files(data_folder)
    output = yaml.dump(devices_json(files))

    print("\n'device_json()' Output: for ", data_folder)
    print(output)

def main():
    # Aruba stacks (no extra modules)
    data_folder = main_folder + "/data/cisco/"
    output_file_path = "/data/yaml/cisco.yaml"

    print("Update data for Cisco devices into the file: ", output_file_path) 
    stack(data_folder, output_file_path)


if __name__ == "__main__":
    # Run main
    main()

    # Run Debugging
    data_folder = main_folder + "/data/cisco/"

    debug_routers_list()
    debug_get_stacks(data_folder)
    debug_get_hostnames(data_folder)
    debug_get_device_role(data_folder)

    #debug_devices_json(data_folder)