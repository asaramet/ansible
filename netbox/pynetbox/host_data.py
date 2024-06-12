#!/usr/bin/env python3

import os

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
    
def get_hostname(file):
    # return hostname from a config file
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

    return location

def locations_yaml(config_files):
    locations = set()

    for file in config_files:
        locations.add(get_location(file))

    return locations

def collect_data():

    # get data files
    files = os.listdir(data_folder)
    files = [data_folder + f for f in files if os.path.isfile(data_folder + f)]


    print(locations_yaml(files))


def main():
    collect_data()

if __name__ == "__main__":
    main()