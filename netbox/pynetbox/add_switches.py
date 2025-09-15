#!/usr/bin/env python3

'''
Add switches to NetBox servers with efficient caching and error handling
Main function, to import:

- add_switches(nb_session, data):
    - nb_session - pynetbox API session
    - data - List of switch configurations to add(yaml format)
'''

import pynetbox, re

from nb import development, production
from std_functions import main_folder
from pynetbox_functions import load_yaml, _bulk_create_with_fallback

# Disable warnings about self-signed certificates
from urllib3 import disable_warnings, exceptions
disable_warnings(exceptions.InsecureRequestWarning)

def cache_switches(nb_session, method = "role"):
    """
    Standalone function to cache existing switched with different methods.

    Args:
        nb_session: pynetbox API session
        method: "role", "tag", or "all" - caching strategy

    Returns a dictionary in the form of {device.name: (device.id, device.serial)}
    """
    print("|++ Caching existing switches")

    nb_devices = nb_session.dcim.devices
    nb_device_roles = nb_session.dcim.device_roles

    switches_cache = {}
    switch_role_slugs = [
        "access-layer-switch", 
        "bueroswitch", 
        "distribution-layer-switch"
    ]
    # --- Cache existing switches ---
    if method == "role":
        # Method 1: Filter by device role (most accurate)
        try:
            switch_roles = [role for role in 
                (nb_device_roles.get(slug = s) for s in switch_role_slugs) if role is not None]
            if switch_roles:
                switch_role_ids = [role.id for role in switch_roles]
                existing_switches = list(nb_devices.filter(role_id = switch_role_ids))
                switches_cache = {s.name: (s.id, s.serial) for s in existing_switches}
                print(f"|++ Found {len(switches_cache)} existing switches (filtered by role)")
        except Exception as e:
            print(f"|-- Error filtering bt role: {e}")
            switches_cache = {}

    elif method == "tag":
        # Method 2: Filter by tags (tags are not mandatory)
        try:
            tagged_switches = list(nb_devices.filter(tag = "switch"))
            switches_cache = {s.name: (s.id, s.serial) for s in tagged_switches}
            print(f"|++ Found {len(switches_cache)} switches with 'Switch' tag")
        except Exception as e:
            print(f"|-- Tag filtering failed: {e}")

    elif method == "all":
        # Method 3: Check all devices filtering them by name (may include routers as well)
        try:
            all_devices = list(nb_devices.all())
            name_pattern = re.compile(r'^(rs|rg|rh|rw)([gs]w|cs)[0-9]+.*$')
            for device in all_devices:
                # Check devices by name
                if (name_pattern.fullmatch(device.name.lower())):
                    switches_cache[device.name] = (device.id, device.serial)

            print(f"|++ Found {len(switches_cache)} existing switches (filtered by name)")
        except Exception as e:
            print(f"|-- Full name scan failed: {e}")

    return switches_cache

def _switch_dependencies(nb_session, switch_dict):
    """
    Generate all dependencies for a new switch, from a switch_dict, such as:
      - device_role: switch
        device_type: hpe-aruba-2930f-8g-poep-2sfpp
        location: s09-0-1
        name: rsgw9001
        serial: CN8AAAAAAA
        site: campus-stadtmitte
        tags: switch

    Returns a dict with resolved IDs
    """

    dependencies = {}
    dependencies = switch_dict

    return dependencies

def add_switches(nb_session, data):
    print("|* Add switches")

    switches_cache = cache_switches(nb_session)
    nb_devices = nb_session.dcim.devices

    # --- payload collector ---
    switches_to_create = []
    skipped_count, error_count = 0, 0

    for item in data.get('devices', []):
        i_name = item.get('name')
        i_serial = item.get('serial')

        # skip if switch with the same name and serial number already exists
        if switches_cache.get(i_name):
            cached_id, cached_serial = switches_cache[i_name]

            # Compare serials (handle None values)
            if (i_serial == cached_serial) or (not i_serial and not cached_serial):
                print(f"|-- Skipping {i_name}: already exists with matching serial")
                skipped_count += 1
                continue
            else:
                print(f"|-- Warrning: {i_name} exists but serial differs (cached: {cached_serial}, new: {i_serial})")

        # Resolve dependencies    
        dependencies = _switch_dependencies(nb_session, item)
        if not dependencies:
            print(f"|-- Skipping {i_name}: missing dependencies")
            error_count += 1
            continue

        
        switches_to_create.append(dependencies)

    # --- create switches in bulk ---
    #new_switches = _bulk_create_with_fallback(nb_devices, switches_to_create, 'switch')
    import yaml, sys
    print(yaml.dump(switches_to_create, sys.stdout))

#    if new_switches:
#        for s in new_switches:
#            print(f"|+ New switch added: {s.name}")
        
#------------------
# Main function
#------------------
def main():
    #------------------
    # Initialize NetBox API with custom session
    #------------------
    import argparse
    parser = argparse.ArgumentParser(
        description="Add switches to a NetBox server"
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

    files_yaml = [
        #"aruba_8_ports.yaml",
        "aruba_stack_2930.yaml",
        #"aruba_6300.yaml"
    ]
    
    for file_name in files_yaml:
        data_file_path = f"{main_folder}/data/yaml/{file_name}"

        data = load_yaml(data_file_path)
        add_switches(nb, data)

if __name__ == '__main__':
    main()