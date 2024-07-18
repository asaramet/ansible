#!/usr/bin/env  python3

# Standard reusable functions

import re, os, yaml
from tabulate import tabulate

this_folder = os.path.dirname(os.path.realpath(__file__))
main_folder = os.path.dirname(this_folder)

# Return a list of file paths from a folder
def config_files(data_folder):
    files = os.listdir(data_folder)
    files = [data_folder + f for f in files if os.path.isfile(data_folder + f)]
    return files

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

def get_hostname(t_file):
    hostname_line = search_line("hostname", t_file)
    return hostname_line.split()[1].replace('"','') if not hostname_line.isspace() else " "

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

#----- Debugging -------
def debug_get_hostname(data_folder):
    table = []
    headers = ["File name", "Hostname"]
    for f in config_files(data_folder):
        table.append([ os.path.basename(f), get_hostname(f) ])
    print(tabulate(table, headers, "github"))


if __name__ == "__main__":
    data_folder = main_folder + "/data/hp-single/"

    debug_get_hostname(data_folder)

    print(config_files(data_folder))