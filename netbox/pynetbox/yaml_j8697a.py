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
    return "Site"

# Collect all the data and saved it to a YAML file
def main():
    # get data files
    files = os.listdir(data_folder)
    files = [data_folder + f for f in files if os.path.isfile(data_folder + f)]

    with open(main_folder + "/data/yaml/j8697a.yaml", 'w') as f:
        yaml.dump(locations_json(files), f)

#---- Debugging ----#
def debug_get_hostname():
    files = os.listdir(data_folder)
    files = [data_folder + f for f in files if os.path.isfile(data_folder + f)]
    table = []
    headers = ["File name", "Hostname"]
    for f in files:
        table.append([ os.path.basename(f), get_hostname(f) ])
    print(tabulate(table, headers, "github"))

def debug_get_site():
    files = os.listdir(data_folder)
    files = [data_folder + f for f in files if os.path.isfile(data_folder + f)]
    table = []
    headers = ["File Name", "Location"]
    for f in files:
        table.append([ os.path.basename(f), get_site(f) ])
    print(tabulate(table, headers, "github"))


if __name__ == "__main__":
    #main()
    #debug_get_hostname()
    debug_get_site()