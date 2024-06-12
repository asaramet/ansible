#!/usr/bin/env python3

import os, yaml

this_folder = os.path.dirname(os.path.realpath(__file__))
main_folder = os.path.dirname(this_folder)
data_folder = main_folder + "/data/aruba_6100/"

def search_line(expression, file):
    with open(file, "r") as file:
        lines = file.readlines()
    
    for i, line in enumerate(lines):
        if line.find(expression) == 0:
            return line

    return " " # return empty space if line not found
    
# return hostname from a config file
def get_hostname(file):
    hostname_line = search_line("hostname", file)
    return hostname_line.split()[1] if not hostname_line.isspace() else " "

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

# get flor name from room number
def get_flor(room_nr):
    flor_name = {
        "-2": "Untergeschoss 2",
        "-1": "Untergeschoss",
        "0": "Erdgeschoss"
    }

    flor = room_nr[0]
    flor = int(room_nr[:2]) if flor == '-' else int(flor)

    if flor < 1:
        return (str(flor), flor_name[str(flor)])

    return (str(flor), "Etage " + str(flor))

# get location's parent
def get_parent_location(location):
    prefixes = {
        "F": "fl",
        "G": "gp",
        "S": "sm"
    }

    building = location.split(".")[0]
    return prefixes[building[0]] + "-" + "gebude" + "-" + building[1:]

# get location site
def get_site(location):
    campuses = {
        "F": "flandernstrasse",
        "G": "gppingen",
        "S": "stadtmitte"
    }
    return "campus-" + campuses[location[0]]

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
        flor_tuple = get_flor(room)

        data["locations"].append({"name": building + "." + flor_tuple[0] + " - " + flor_tuple[1], "site": get_site(location), "parent_location": get_parent_location(location)})

    return data

def collect_data():

    # get data files
    files = os.listdir(data_folder)
    files = [data_folder + f for f in files if os.path.isfile(data_folder + f)]


    with open(main_folder + "/data/yaml/locations.yaml", 'w') as locations_yaml:
        yaml.dump(locations_json(files), locations_yaml)


def main():
    collect_data()

if __name__ == "__main__":
    main()