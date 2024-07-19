#!/usr/bin/env  python3

# Standard reusable functions

import re, os, yaml
from tabulate import tabulate

this_folder = os.path.dirname(os.path.realpath(__file__))
main_folder = os.path.dirname(this_folder)

# --- Base functions ---
def search_line(expression, t_file):
    with open(t_file, "r") as f:
        lines = f.readlines()
    
    for i, line in enumerate(lines):
        if re.search(expression, line): return line

    return " " # return empty space if line not found
    
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

# Return a list of file paths from a folder
def config_files(data_folder):
    files = os.listdir(data_folder)
    files = [data_folder + f for f in files if os.path.isfile(data_folder + f)]
    return files

# --- Get functions ---
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

def get_trunks(t_file):
    with open(t_file, "r") as f:
        text = f.readlines()

    trunks = []
    for line in recursive_search(text, "trunk"):
        line_data = line.split()
        trunks.append({"name": line_data[2], 'interfaces': line_data[1]})

    return trunks

# --- Additional function ---
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
    for device_type, d_list in devices().items():
        if hostname in d_list:
            return device_type

    return None

#----- Return JSON Objects -----#

# return the devices json object
# Input: 
# 1. device type slags dict, for example:
# device_type_slags = { 
#     'J8697A': 'hpe-procurve-5406zl',
#     'J8698A': 'hpe-procurve-5412zl',
#     'J8770A': 'hpe-procurve-4204vl',
#     'J8773A': 'hpe-procurve-4208vl',
#     'J9850A': 'hpe-5406r-zl2',
#     'J9851A': 'hpe-5412r-zl2'
# }
# 2. General tags, for example:
# tags = "switch"
# tags = ["switch", "modular_switch"]


def devices_json(config_files, device_type_slags, tags):
    data = {'devices':[]}
    for t_file in config_files:
        hostname = get_hostname(t_file)
        d_label = device_type_slags[device_type(hostname)]
        data['devices'].append({'name': hostname, 'device_role': get_device_role(t_file), 'device_type': d_label,
            'site': get_site(t_file), 'tags': tags, 'serial':serial_numbers()[hostname]})
    return data

#----- Debugging -------
def debug_config_files(data_folder):
    table = []
    headers = ["File name", "Path"]
    for f in config_files(data_folder):
        table.append([ os.path.basename(f), f ])
    print(tabulate(table, headers, "github"))

def debug_get_hostname(data_folder):
    table = []
    headers = ["File name", "Hostname"]
    for f in config_files(data_folder):
        table.append([ os.path.basename(f), get_hostname(f) ])
    print(tabulate(table, headers, "github"))

def debug_get_site(data_folder):
    table = []
    headers = ["File Name", "Location"]
    for f in config_files(data_folder):
        table.append([ os.path.basename(f), get_site(f) ])
    print(tabulate(table, headers, "github"))

def debug_get_device_role(data_folder):
    table = []
    headers = ["File name", "Device role"]
    for f in config_files(data_folder):
        table.append([os.path.basename(f), get_device_role(f)])
    print(tabulate(table, headers, "github"))

def debug_get_trunks(data_folder):
    table = []
    headers = ["File Name", "Trunks"]
    for f in config_files(data_folder):
        table.append([os.path.basename(f), get_trunks(f)])
    print(tabulate(table, headers))

if __name__ == "__main__":
    data_folder = main_folder + "/data/hp-single/"

    #debug_config_files(data_folder)
    #debug_get_hostname(data_folder)
    #debug_get_site(data_folder)
    debug_get_device_role(data_folder)
    debug_get_trunks(data_folder)
