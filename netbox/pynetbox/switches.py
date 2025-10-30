#!/usr/bin/env python3

'''
Add switches to a NetBox platform using `pynetbox` library
Main function, to import:

- add_switches(nb_session, data):
    - nb_session - pynetbox API session
    - data - List of switch configurations to add(yaml format)
'''

import pynetbox, re, logging

from pynetbox.core.api import Api as NetBoxApi
from typing import Dict, List

from pynetbox_functions import load_yaml, _bulk_create
from pynetbox_functions import _resolve_tags

# Get logger
logger = logging.getLogger(__name__)

def cache_switches(nb_session: NetBoxApi, method: str = "role") -> Dict[str, List[str]]:
    """
    Standalone function to cache existing switched with different methods.

    Args:
        nb_session: pynetbox API session
        method: "role", "tag", or "all" - caching strategy

    Returns a dictionary in the form of {device.name: (device.id, device.serial)}
    """
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
                logger.info(f"Found {len(switches_cache)} existing switches (filtered by role)")
        except Exception as e:
            logger.error(f"Filtering by role failed: {e}")
            switches_cache = {}

    elif method == "tag":
        # Method 2: Filter by tags (tags are not mandatory)
        try:
            tagged_switches = list(nb_devices.filter(tag = "switch"))
            switches_cache = {s.name: (s.id, s.serial) for s in tagged_switches}
            logger.info(f"Found {len(switches_cache)} switches with 'Switch' tag")
        except Exception as e:
            logger.error(f"Filtering by tag failed: {e}")
            switches_cache = {}

    elif method == "all":
        # Method 3: Check all devices filtering them by name (may include routers as well)
        try:
            all_devices = list(nb_devices.all())
            name_pattern = re.compile(r'^(rs|rg|rh|rw)([gs]w|cs)[0-9]+.*$')
            for device in all_devices:
                # Check devices by name
                if (name_pattern.fullmatch(device.name.lower())):
                    switches_cache[device.name] = (device.id, device.serial)

            logger.info(f"Found {len(switches_cache)} existing switches (filtered by name)")
        except Exception as e:
            logger.error(f"Full name scan failed: {e}")
            switches_cache = {}

    return switches_cache

def _switch_dependencies(nb_session: NetBoxApi, switch_dict: Dict[str, str]) -> Dict[str, str | int]:
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

    try:
        # Device Role
        s_role = switch_dict.get('device_role')
        device_role = nb_session.dcim.device_roles.get(slug = s_role)
        if not device_role:
            logger.warning(f"Device role '{s_role}' not found")
            return None 
        dependencies['role'] = device_role.id

        # Device Type
        s_type = switch_dict.get('device_type')
        device_type = nb_session.dcim.device_types.get(slug = s_type)
        if not device_type:
            logger.warning(f"Device type '{s_type} not found'")
            return None
        dependencies['device_type'] = device_type.id

        # Site
        s_site = switch_dict['site']
        site = nb_session.dcim.sites.get(slug = s_site)
        if not site:
            logger.warning(f"Site '{s_site}' not found")
            return None
        dependencies['site'] = site.id

        # Location (optional)
        s_location = switch_dict.get('location', None)
        if s_location:
            location = nb_session.dcim.locations.get(slug = s_location)
            if location:
                dependencies['location'] = location.id
            else:
                logger.warning(f"Location '{s_location}' not found, skipping")

        return dependencies

    except Exception as e:
        logger.error(f"Error resolving dependencies for {switch_dict.get('name')}: {e}")
        return None

def _switch_payload(nb_session: NetBoxApi, switch_dict: Dict[str, str], 
    dependencies: Dict[str, str | int]) -> Dict[str, str | int]:
    """
    Return the payload for creating a new switch on a NetBox server.
    Args:
        nb_session: pynetbox API session
        switch_dict: Switch data dictionary 
        dependencies: Switch dependencies dictionary
    Return:
        The payload dictionary used to create a new switch in a NetBox session
    """
    payload = {
        'name': switch_dict.get('name'),
        'status': 'active'              # default status
    }

    serial = switch_dict.get('serial')
    if serial:
        payload['serial'] = serial

    # Handle tags, NetBox API expects a list of names or IDs
    tag_ids = _resolve_tags(nb_session, switch_dict.get('tags', None))
    if tag_ids:
        payload['tags'] = tag_ids

    # Add dependencies
    payload.update(dependencies)

    return payload


def switches(nb_session: NetBoxApi, data: Dict[str, List[str]]) -> List:
    """
    Add switches to NetBox server from YAML data.

    Args:
        nb_session: pynetbox API session
        data: Dictionary containing 'devices' list
    """
    switches_cache = cache_switches(nb_session)
    nb_devices = nb_session.dcim.devices

    # --- Payload collector ---
    switches_to_create = []
    skipped_count, error_count = 0, 0

    for switch in data.get('devices', []):
        i_name = switch.get('name')
        i_serial = switch.get('serial')

        # skip if switch with the same name and serial number already exists
        if switches_cache.get(i_name):
            cached_id, cached_serial = switches_cache[i_name]

            # Compare serials (handle None values)
            if (i_serial == cached_serial) or (not i_serial and not cached_serial):
                #logger.info(f"Skipping {i_name}: already exists with matching serial")
                skipped_count += 1
                continue
            else:
                logger.warning(f"{i_name} exists but serial differs (cached: {cached_serial}, new: {i_serial})")

        # Resolve dependencies    
        dependencies = _switch_dependencies(nb_session, switch)
        if not dependencies:
            logger.error(f"Skipping {i_name}: missing dependencies")
            error_count += 1
            continue

        # Prepare payload
        try:
            payload = _switch_payload(nb_session, switch, dependencies)
            switches_to_create.append(payload)
        except Exception as e:
            logger.error(f"Error preparing payload for {i_name}: {e}")
            error_count += 1
            continue

    logger.info(f"{len(switches_to_create)} switches to create, {skipped_count} skipped, {error_count} errors.")

    # --- create switches in bulk ---
    new_switches = []
    if switches_to_create:
        new_switches = _bulk_create(nb_devices, switches_to_create, 'switch')

        if new_switches:
            logger.info(f"Successfully created {len(switches_to_create)} switches:")
            for s in new_switches:
                logger.info(f"New switch added: {s.name}")
            return new_switches
    
    logger.info("No new switches created")
    return new_switches
            
if __name__ == '__main__':
    from pynetbox_functions import _main

    _main("Add switches to a NetBox server", switches)
