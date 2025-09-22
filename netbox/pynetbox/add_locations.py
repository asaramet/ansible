#!/usr/bin/env python3

'''
Add collected locations data to a NetBox platform using `pynetbox` library
Main function, to import:

- add_locations(nb_session, data):
    - nb_session - NetBox HTTPS session
    - data - data (yaml format)
'''

import pynetbox, logging

from typing import Dict, List
from pynetbox.core.api import Api as NetBoxApi

from std_functions import main_folder, floor_slug, room_slug
from pynetbox_functions import load_yaml, _bulk_create_with_fallback, _delete_netbox_obj, _main

# Configure logging
logging.basicConfig(level = logging.INFO)
logger = logging.getLogger(__name__)

def add_locations(nb_session: NetBoxApi, data: Dict[str, List[str]]) -> None:
    """
    Add locations to a NetBox server from YAML data.

    Args:
        nb_session: pynetbox API session
        data: Dictionary containing 'locations' list
    """
    nb_locations = nb_session.dcim.locations
    nb_sites = nb_session.dcim.sites   
    nb_racks = nb_session.dcim.racks

    # --- cache existing sites and locations ---
    sites = list(nb_sites.all())
    sites_cache = {s.slug: s for s in sites}
    sites_id_to_slug = {s.id: s.slug for s in sites}

    locations_cache = {(loc.site.slug, loc.name): loc for loc in nb_locations.all()}

    # --- payload collectors ---
    floors_to_create, rooms_to_create, racks_to_create = [], [], []

    for item in data.get('locations', []):
        site_slug = item['site']
        site = sites_cache.get(site_slug) or nb_site.get(slug = site_slug)

        if not site: 
            logger.warning(f"Site {site_slug} not found, skipping {item.get('floor')}")
            continue

        # Add floor payload, if missing
        floor_name = item.get('floor')
        floor_key = (site_slug, floor_name)
        if floor_key not in locations_cache:
            parent_obj = None
            if item.get('parent_location'):
                parent_obj = nb_locations.get(slug = item.get('parent_location'))
            payload = {
                'name': floor_name,
                'site': site.id,
                'slug': floor_slug(floor_name)
            }

            if parent_obj:
                payload['parent'] = parent_obj.id
            
            floors_to_create.append(payload)

        # Handle room (room can be "name" or tuple (name, rack))
        room_name, rack_name = item.get('room'), None
        if isinstance(room_name, tuple):
            room_name, rack_name = room_name

        room_key = (site.slug, room_name)
        if room_key not in locations_cache:
            # floor will exist after bulk_create, so just reference it by slug later
            rooms_to_create.append({ 
                "name": room_name,
                "site": site.id,
                "slug": room_slug(room_name),
                "parent_floor_name": floor_name
            })

            # add rack if given in the room label
            if rack_name:
                racks_to_create.append({
                    "name": f"V.{room_name}.{rack_name}",
                    "site": site.id,
                    "parent_room_name": room_name
                })

    # --- create floors in bulk ---
    new_floors = _bulk_create_with_fallback(nb_locations, floors_to_create, "floor")
    if new_floors:
        # refresh cache after changes
        locations_cache = {(loc.site.slug, loc.name): loc for loc in nb_locations.all()}

    # --- resolve rooms parent (floor) and create rooms in bulk
    resolved_rooms_payloads = []
    for r in rooms_to_create:
        site_slug = sites_id_to_slug.get(r.get('site'))
        parent_floor_name = r.pop('parent_floor_name')
        parent_floor = locations_cache.get((site_slug, parent_floor_name))
        if not parent_floor:
            logger.warning(f"Skipping: Couldn't resolve parent floor {parent_floor_name} for room {r.get('name')}.")
            continue
        r['parent'] = parent_floor.id
        resolved_rooms_payloads.append(r)

    new_rooms = _bulk_create_with_fallback(nb_locations, resolved_rooms_payloads, 'room')
    if new_rooms:
        locations_cache = {(loc.site.slug, loc.name): loc for loc in nb_locations.all()}

    # --- resolve racks and create them in bulk ---
    resolved_racks_payloads = []
    for rk in racks_to_create:
        site_slug = sites_id_to_slug.get(rk.get('site'))
        parent_room = locations_cache.get((site_slug, rk.get('parent_room_name')))
        if not parent_room:
            logger.warning(f"Skipping: Couldn't resolve parent room {rk["[parent_room_name]"]} for rack {rk['name']}.")
            continue
        rk['location'] = parent_room.id
        resolved_racks_payloads.append(rk)

    new_racks = _bulk_create_with_fallback(nb_racks, resolved_racks_payloads, 'rack')

    # Output messages
    if not (new_floors or new_rooms or new_racks):
        logger.info("No new locations created.")
        return
    if new_floors:
        for f in new_floors:
            logger.info(f"New floor added: {f.name}")
    if new_rooms:
        for r in new_rooms:
            logger.info(f"New room added: {r.name}")
    if new_racks:
        for rk in new_racks:
            logger.info(f"|+ New rack added: {rk.name}")

#------------------
# Delete some data
#------------------
def delete_locations(nb_session: NetBoxApi, data: Dict[str, List[str]]) -> None:
    """
    Remove locations from a NetBox database over pynetbox API
    Args:
        nb_session: pynetbox API Session 
        data: Dictionary containing 'locations' list
    """
    logger.info("Remove locations (rooms, floors)")
    nb_locations = nb_session.dcim.locations

    rooms = [loc.get('room') for loc in data.get('locations', []) if loc.get('room')]
    floors = [loc.get('floor') for loc in data.get('locations', []) if loc.get('floor')]

    if not rooms and not floors:
        logger.info("No rooms or floors defined in data")
        return

    combined_names = list({*(rooms or []), *(floors or [])}) # unique set

    # try fetch all matching locations in one call; fall back to per-name fetch if not supported
    existing_locs = {}

    try:
        # many pynetbox combinations accept name__in for multi-value filter
        records = nb_locations.filter(name__in = combined_names)
        existing_locs = {r.name: r for r in records}

    except Exception:
        # fallback: query one-by-one
        for n in combined_names:
            r = nb_locations.get(name = n)
            if r: existing_locs[n] = r

    done_flag = False

    # Delete rooms first to reduce dependencies
    for room in rooms:
        obj = existing_locs.get(room)
        if not obj:
            logger.info(f"Skipping: Room {room} not found")
            continue

        done_flag = _delete_netbox_obj(obj) or done_flag

    for floor in floors:
        obj = existing_locs.get(floor)
        if not obj:
            logger.info(f"Skipping: Floor {floor} not found")
            continue
        done_flag = _delete_netbox_obj(obj) or done_flag

    if not done_flag:
        logger.info("Nothing was removed *|")

#------------------
# Debugging
#------------------

def debug_locations(nb_session: NetBoxApi, data: Dict) -> List:
    import yaml
    from sys import stdout

    return_list = []
    for location in data['locations']:
        if not location['is_rack']:
            return_list.append(location)

    yaml.dump(return_list, stdout)

    return return_list

if __name__ == '__main__':
    _main("Add collected locations data to a NetBox server", add_locations)
    #_main("Delete collected locations data", delete_locations)

    #_main("Debug locations data", debug_locations)