#!/usr/bin/env python3

'''
Add collected data to NetBox servers using `pynetbox` library
'''

import pynetbox, argparse, yaml
from pathlib import Path

from nb import development, production
from std_functions import main_folder, location_slug

# Disable warnings about self-signed certificates
from urllib3 import disable_warnings, exceptions
disable_warnings(exceptions.InsecureRequestWarning)

def read_data(nb):
    for device in nb.dcim.devices.all():
        print(f"- {device.name} ({device.device_type.display}) in {device.site.name}")

def load_yaml(file_path):
    yaml_file = Path(file_path)

    with yaml_file.open('r') as f:
        return yaml.safe_load(f)

def add_locations(nb_session, data):
    nb_locations = nb_session.dcim.locations
    nb_sites = nb_session.dcim.sites   

    created = []

    for location in data['locations']:

        if not nb_locations.get(name = location['name']):
            site = nb_sites.get(slug = location['site'])
            name = location["name"]

            parent_location = nb_locations.get(slug = location['parent_location'])

            payload = {
                "name": name,
                "site": site.id,
                "slug": location_slug(name),
                "parent": parent_location.id
            }

            created.append(payload)
            nb_locations.create(payload)

    if not created:
        print("|---\tNo new locations created.")
        return 

    for location in created:
        print(f"|+++\tCreated new location {location}")

def add_switches(nb_session, data_file_path):
    data = load_yaml(data_file_path)

    nb_sites = nb_session.dcim.sites   

    add_locations(nb_session, data)

    #for sw in data["devices"]:
        #print(sw)

def main():
    #------------------
    # Initialize NetBox API with custom session
    #------------------
    parser = argparse.ArgumentParser(
        description="Add collected data to a NetBox server"
    )

    parser.add_argument(
        '-s', "--server",
        choices = ["development", "production"],
        default= "development",
        help = "Select which NetBox server to connect to (default: development)"
    )

    args = parser.parse_args()

    if args.server == "development":
        nb = development
    elif args.server == "production":
        nb = production

    nb.http_session.verify = False # Disable SSL verification

    #------------------
    #  Run functions
    #------------------

    data_file_path = main_folder + "/data/yaml/aruba_8_ports.yaml"
    add_switches(nb, data_file_path)


if __name__ == '__main__':
    main()