#!/usr/bin/env python3

# Collect Aruba 6100 data and create a aruba_6100.yaml configs file 

import re, os, yaml

this_folder = os.path.dirname(os.path.realpath(__file__))
main_folder = os.path.dirname(this_folder)
data_folder = main_folder + "/data/aruba_6100/"

def search_line(expression, file):
    with open(file, "r") as file:
        lines = file.readlines()
    
    for i, line in enumerate(lines):
        if re.search(expression, line): return line

    return " " # return empty space if line not found
    
def get_location(file):
    location_line = search_line("snmp-server system-location", file)

    if location_line.isspace(): return " "

    location = location_line.split()[2]

    (building, room) = location.split(".")

    building_nr = str(int(building[1:])) # convert "01" to "1", for example
    if len(building_nr) == 1:
        # add "0" to single digit buildings
        building_nr = "0" + building_nr

    location = building[0] + building_nr + "." + room

    return (location, room)

# get flor number from room number
def get_flor_nr(room_nr):
    flor = room_nr[0]
    flor = int(room_nr[:2]) if flor == '-' else int(flor)

    return str(flor)

# get flor name from room number
def get_flor_name(room_nr):
    flor_name = {
        "-2": "Untergeschoss 2",
        "-1": "Untergeschoss",
        "0": "Erdgeschoss"
    }

    flor = get_flor_nr(room_nr)
    if int(flor) < 1:
        return (flor, flor_name[flor])

    return (flor, "Etage " + flor)

# get location's parent
def get_parent_location(location):
    prefixes = {
        "F": "fl",
        "G": "gp",
        "S": "sm"
    }

    building = location.split(".")[0]
    return prefixes[building[0]] + "-" + "gebude" + "-" + building[1:]

# get room location
def get_room_location(location): 
    # s01-2-etage-2
    flor_tags = {
        "-2": "untergeschoss-2",
        "-1": "untergeschoss",
        "0": "erdgeschoss"
    }
    building, room_nr = location.split(".")
    flor = get_flor_nr(room_nr)
    flor_fx = str(abs(int(flor))) # string to use in the label
    flor_tag = flor_tags[flor] if int(flor) < 1 else "etage-" + flor

    return building.lower() + "-" + flor_fx + "-" + flor_tag
    
# get location site
def get_site(location):
    campuses = {
        "F": "flandernstrasse",
        "G": "gppingen",
        "S": "stadtmitte"
    }
    return "campus-" + campuses[location[0]]

def get_hostname(file):
    hostname_line = search_line("hostname", file)
    return hostname_line.split()[1] if not hostname_line.isspace() else " "

def get_device_ip(file):
    return search_line("ip address", file).split()[2]

# create the loactions json objects list
def locations_json(config_files):
    data = {"locations":[]}
    locations = set()
    rooms = {}

    for file in config_files:
        location,room = get_location(file)
        locations.add(location)
        rooms.update({location:room})

    for location in locations:
        room = rooms[location]
        building = location.split(".")[0]
        flor_tuple = get_flor_name(room)

        data["locations"].append({"name": building + "." + flor_tuple[0] + " - " + flor_tuple[1], "site": get_site(location), "parent_location": get_parent_location(location)})

    return data

# create ip_addresses json objects list
def ip_addressess_json(config_files):
    data = {"ip_addresses":[]}

    for file in config_files:
        hostname = get_hostname(file)
        ip_address = get_device_ip(file)

        data["ip_addresses"].append({"address": ip_address, "dns_name": hostname})

    return data

# get the interfaces configuration from an Aruba 6100 config file
def get_interfaces_config(config_file):
    interface_configs = {
        'vlan': {},
        'lag': {},
        'physical': {}
    }
    current_interface = None

    with open(config_file, "r") as f:
        config_text = f.readlines()

    for line in config_text:
        line = line.rstrip() # remove the trailing newline character
        
        # Detect an interface line
        if line.startswith('interface'):
            current_interface = line
            if 'vlan' in current_interface:
                interface_type = 'vlan'
            elif 'lag' in current_interface:
                interface_type = 'lag'
            else:
                interface_type = 'physical'

            interface_configs[interface_type][current_interface] = []
        elif current_interface:
            # Check if the line is indented
            if line.startswith((' ','\t', '!')):  # Lines part of an interface configuration
                interface_configs[interface_type][current_interface].append(line)
            else:
                # End of the current interface configuration block
                current_interface = None
                interface_type = None

    # Clean up the config by removing any trailing empty configurations
    for interface_type in interface_configs:
        interface_configs[interface_type] = {k: v for k, v in interface_configs[interface_type].items() if v}

    return interface_configs

# create aruba_6100_12g json objects list
def aruba_6100_12g_json(config_files):
    data = {"aruba_6100_12g":[]}

    for file in config_files:
        name = get_hostname(file)
        location,room = get_location(file)
        site = get_site(location)
        location = get_room_location(location)
        primary_ip4 = get_device_ip(file)

        data["aruba_6100_12g"].append({"name": name, "location": location, "site": site, "primary_ip4": primary_ip4})

    return data

def collect_data():

    # get data files
    files = os.listdir(data_folder)
    files = [data_folder + f for f in files if os.path.isfile(data_folder + f)]

    with open(main_folder + "/data/yaml/aruba_6100.yaml", 'w') as f:
        yaml.dump(locations_json(files), f)
        yaml.dump(aruba_6100_12g_json(files), f)
        yaml.dump(ip_addressess_json(files), f)

def debug_gets():
    # print some collected or parsed data
    config_file = data_folder + "rggw1018bp"

    interfaces_config = get_interfaces_config(config_file)

    # Printing the configurations for demonstration purposes
    for interface_type, configs in interfaces_config.items():
        print(f"{interface_type.capitalize()} Interfaces:")
        for interface, config in configs.items():
            print(f"  {interface}:")
            for line in config:
                print(f"    {line}")
            print()

def main():
    collect_data()

if __name__ == "__main__":
    #main()
    debug_gets()

