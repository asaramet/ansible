#!/usr/bin/env python3

'''
Synchronize VLANs on a NetBox platform using `pynetbox` library
Main function, to import:

- vlans(nb_session, data):
    - nb_session - pynetbox API session
    - data - data (yaml format)
'''

import pynetbox, logging

from typing import Dict, List
from pynetbox.core.api import Api as NetBoxApi

from pynetbox_functions import _bulk_create

# Configure logging
logging.basicConfig(level = logging.INFO)
#logging.basicConfig(level = logging.DEBUG)
logger = logging.getLogger(__name__)

def vlans(nb_session: NetBoxApi, data: Dict[str, List[str]]) -> None:
    """
    Synchronize VLANs from YAML data to NetBox.
    Args:
        nb_session: pynetbox API session
        data: Dictionary containing 'vlans' key with list of VLAN definitions
    """

    d_vlans = data.get('vlans', [])

    if not d_vlans:
        logger.info("No VLANs found in data.")
        return

    # Fetch and cache all existing VLANS from NetBox
    try:
        existing_vlans = nb_session.ipam.vlans.all()
        # Create a set of (vid, name) tuples for quick lookup
        cached_vlans = {(str(vlan.vid), vlan.name) for vlan in existing_vlans}
        logger.info(f"Found {len(cached_vlans)} existing VLANs")
    except Exception as e:
        logger.error(f"Failed to fetch existing VLANs: {e}", exc_info = True)
        return

    # Collect VLANs to create
    vlans_to_create = []

    for vlan_data in d_vlans:
        vlan_id = vlan_data.get('id')
        vlan_name = vlan_data.get('name')

        # Skip entries with missing required fields
        if not vlan_id or not vlan_name:
            logger.warning(f"Skipping VLAN with missing id or name: {vlan_data}")
            continue

        # Check if VLAN already exists
        if (str(vlan_id), vlan_name) in cached_vlans:
            logger.debug(f"VLAN {vlan_id} ({vlan_name}) already exists, skipping")
        else:
            vlans_to_create.append({
                'vid': int(vlan_id),
                'name': vlan_name
            })
            logger.debug(f"VLAN {vlan_id} ({vlan_name}) will be created")

    # Bulk create missing VLANs
    if not vlans_to_create:
        logger.info("All VLANs already exist")
        return

    logger.info(f"Creating {len(vlans_to_create)} new VLAN(s)...")
    created = _bulk_create(nb_session.ipam.vlans, vlans_to_create, "VLAN")
    logger.info(f"Successfully created {len(created)} VLANs")

if __name__ == '__main__':
    from pynetbox_functions import _main
    _main("Synchronizing VLANs", vlans)