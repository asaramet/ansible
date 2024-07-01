#!/usr/bin/env python3

# Collect Aruba J8697A data and create a j8697a.yaml configs file 

import re, os, yaml
from tabulate import tabulate

this_folder = os.path.dirname(os.path.realpath(__file__))
main_folder = os.path.dirname(this_folder)
data_folder = main_folder + "/data/aruba-J8697A/"

def search_line(expression, t_file):
    with open(t_file, "r") as f:
        lines = f.readlines()
    
    for i, line in enumerate(lines):
        if re.search(expression, line): return line

    return " " # return empty space if line not found
    
def get_hostname(t_file):
    hostname_line = search_line("hostname", t_file)
    return hostname_line.split()[1].replace('"','') if not hostname_line.isspace() else " "

def get_site(t_file):
    campuses = {
        "h": "flandernstrasse",
        "g": "gppingen",
        "s": "stadtmitte",
        "w": "weststadt"
    }
    return "campus-" + campuses[get_hostname(t_file)[1]]

def get_device_role(t_file):
    role_code = get_hostname(t_file)[2:4]
    if role_code == "cs":
        return "distribution-layer-switch"
    return "access-layer-switch"

def set_tags():
    return "switch"

# return the devices json object
def devices_json(config_files):
    data = {'devices':[]}
    for t_file in config_files:
        data['devices'].append({'name': get_hostname(t_file), 'device_role': get_device_role(t_file), 
            'site': get_site(t_file), 'tags': set_tags()})
    return data

# search lines in a text recursively
def recursive_search(text, pattern):
    # base case
    if not text:
        return []

    found_lines = []
    for i, line in enumerate(text):
        if line.startswith(pattern):
            found_lines.append(line.strip())

            found_lines += recursive_search(text[i+1:], pattern)
            break 

    return found_lines

def get_modules(t_file):
    with open(t_file, "r") as f:
        text = f.readlines()

    names = {'1': 'A', '2': 'B', '3': 'C', '4': 'D', '5': 'E', '6': 'F'}
    modules = []
    for line in recursive_search(text, "module"):
        m_list = line.split()
        modules.append({'module': names[m_list[1]], 'type': m_list[3]})
        #modules.append({'module': m_list[1], 'type': m_list[3]})
    return modules

# return the modules json object
def modules_json(config_files):
    data = {'modules':[]}
    types = {
        "j8702a": "ProCurve 24-port 10/100/1000Base-T PoE Switch Module",
        "j8705a": "HP J8705A ProCurve PoE 20 Port Gig-T SFP Plus 4 Port Mini GBIC ZL Module",
        "j8706a": "ProCurve Switch 5400zl 24p Mini-GBIC Module",
        "j8707a": "HP 4-Port 10GbE X2 ZL Module",
        "j9534a": "Aruba J9534A",
        "j9537a": "Aruba J9537A",
        "j9538a": "Aruba J9538A"
        }
    for t_file in config_files:
        modules = get_modules(t_file)
        device = get_hostname(t_file)

        for module in modules:
            data['modules'].append({'device': device, 'module_bay': module['module'], 'type': types[module['type']]})
    return data

def get_trunks(t_file):
    with open(t_file, "r") as f:
        text = f.readlines()

    trunks = []
    for line in recursive_search(text, "trunk"):
        line_data = line.split()
        trunks.append({"name": line_data[2], 'interfaces': line_data[1]})

    return trunks

# return trunks and interfaces json objects
def trunks_json(config_files):
    data = {'trunks':[], 'trunk_interfaces':[]}

    for t_file in config_files:
        hostname = get_hostname(t_file)
        trk_lists = get_trunks(t_file)

        for trunk in trk_lists:
            trk_name = trunk['name']
            data['trunks'].append({'hostname': hostname, 'name': trk_name})

            #there is always max 2 interfaces in a trunk, but sometimes they are created with '-' instead of ','
            interfaces = trunk['interfaces'].replace('-', ',').split(',') 
            for interface in interfaces:
                data['trunk_interfaces'].append({'hostname': hostname, 'interface': interface, 'trunk_name': trk_name})

    return data

# return a tuple, ex: (interface, interface_name), recursively from a switch config
def recursive_names_tuple(text, pattern = 'interface'):
    # Base case
    if not text:
        return []

    names_tuple = []
    for i, line in enumerate(text):

        if line.startswith(pattern):
            # Found a pattern line
            p_line = line.strip().split()[1]
            
            # Check the next line for the name
            if i + 1 < len(text) and text[i + 1].strip().startswith('name'):
                name_line = text[i + 1].strip()
                name = name_line.split(' ', 1)[1].strip('"')
                names_tuple.append((p_line, name))
                
                # Recur from the line after the name line
                names_tuple += recursive_names_tuple(text[i + 2:])
            else:
                # Recur from the next line if no name found
                names_tuple += recursive_names_tuple(text[i + 1:])
            break

    return names_tuple

def get_interface_names(t_file):
    with open(t_file, "r") as f:
        text = f.readlines()

    return recursive_names_tuple(text)

def interface_names_json(config_files):
    data = {'interface_names':[]}

    for t_file in config_files:
        hostname = get_hostname(t_file)
        for i_tuple in get_interface_names(t_file):
            interface, name = i_tuple
            data['interface_names'].append({'hostname': hostname, 'interface': interface, 'name': name})
    
    return data

# Collect all the data and saved it to a YAML file
def main():
    # get data files
    files = os.listdir(data_folder)
    files = [data_folder + f for f in files if os.path.isfile(data_folder + f)]

    with open(main_folder + "/data/yaml/j8697a.yaml", 'w') as f:
        yaml.dump(devices_json(files), f)
        yaml.dump(modules_json(files), f)
        yaml.dump(trunks_json(files), f)
        yaml.dump(interface_names_json(files), f)

#---- Debugging ----#
def text_files():
    files = os.listdir(data_folder)
    files = [data_folder + f for f in files if os.path.isfile(data_folder + f)]
    return files

def debug_get_hostname():
    table = []
    headers = ["File name", "Hostname"]
    for f in text_files():
        table.append([ os.path.basename(f), get_hostname(f) ])
    print(tabulate(table, headers, "github"))

def debug_get_site():
    table = []
    headers = ["File Name", "Location"]
    for f in text_files():
        table.append([ os.path.basename(f), get_site(f) ])
    print(tabulate(table, headers, "github"))

def debug_get_device_role():
    table = []
    headers = ["File name", "Device role"]
    for f in text_files():
        table.append([os.path.basename(f), get_device_role(f)])
    print(tabulate(table, headers, "github"))

def debug_get_modules():
    table = []
    types = set()
    headers = ["File Name", "Modules"]
    for f in text_files():
        modules = get_modules(f)
        table.append([os.path.basename(f), modules])
        for module in modules:
            types.add(module['type'])
    print(tabulate(table, headers, "github"))
    print(types)

def debug_get_trunks():
    table = []
    headers = ["File Name", "Trunks"]
    for f in text_files():
        table.append([os.path.basename(f), get_trunks(f)])
    print(tabulate(table, headers))

def debug_get_interface_names():
    for f in text_files():
        print(os.path.basename(f), '---> ', get_interface_names(f))

if __name__ == "__main__":
    main()
    #debug_get_hostname()
    #debug_get_site()
    #debug_get_device_role()
    #debug_get_modules()
    #debug_get_trunks()
    debug_get_interface_names()
