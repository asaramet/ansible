#!/usr/bin/env python3
'''
Clean devices data on a NetBox platform using `pynetbox` library

Main function to import:
    clean(nb_session, data):
        - nb_session: pynetbox API session
        - data: dictionary containing 'devices' list (YAML format)

Checks:
    1. Checking if the device corresponds to required device type
    2. Checking if all the default interfaces are present
Supports:
    - Deckmission the device that fails check 1
    - Deleting the devices that fail the checks
'''

import logging
from typing import Optional, Tuple, Any

from pynetbox.core.api import Api as NetBoxApi

from pynetbox_functions import (
    _delete_netbox_obj,
    _cache_devices,
    _cache_device_types
)

# Get logger
logger = logging.getLogger(__name__)

def _check_device_type(existing_device_types: dict[str, str], device_dict: dict, existing_device: object) -> Optional[str]:
    """
    Check if the required device type is the same as the device in Netbox.

    Args:
        - existing_device_types - a dictionary of existing device types in the form
            - {device_slug: device_model}
        - device_dict: device data that has to be added to NetBox
        - existing_device: existing device object on the platform, with the same hostname

    Returns:
        Existing device name if it has to be modified or None if not.
    """

    # TODO: Check device type
    # Get the NetBox device type model 
    netbox_device_type_model = existing_device.device_type.model

    # Get the requested device type slug
    requested_device_type_slug = device_dict.get('device_type')

    # Compare models
    requested_device_type_model = existing_device_types[requested_device_type_slug]
    if netbox_device_type_model == requested_device_type_model:
        return None

    hostname = existing_device.name
    logger.info(f"Found conflicting device type {hostname}")
    logger.info("Checking for interfaces...")

    # TODO: Check number of interfaces

        # TODO: If correct number update device hostname to its SN and decommission it

        # TODO: If not delete the existing device
    
    return existing_device.name

def clean(nb_session: NetBoxApi, data: dict) -> list[str]:
    """
    Handle device conflicts in the Netbox database and devices to add.

    Args:
        nb_session: pynetbox API session
        data: dictionary containing:
            - 'devices': list of device configurations
            - 'chassis' (optional): list of virtual chassis definitions
        
    Returns:
        List of modified device objects
    """
    # Cache data before loops
    devices_data = data.get('devices', [])
    device_names = [s.get('name') for s in devices_data if s.get('name')]

    logger.debug(f"Caching {len(device_names)} devices...")
    existing_devices = _cache_devices(nb_session, device_names)
    logger.debug(f"Found {len(existing_devices)} existing devices in cache")

    logger.debug(f"Caching existing device types...")
    existing_device_types = _cache_device_types(nb_session)
    logger.debug(f"Found {len(existing_device_types)} device types in cache")

    # Variables
    wrong_type_devices = []

    for device_dict in devices_data:
        device_name = device_dict.get('name')
        if not device_name:
            logger.warning("Skipping device with missing 'name' field")
            error_count += 1
            continue
    
        # Check if device exists and has issues
        existing_device = existing_devices.get(device_name)
        if existing_device:
            device_type_resolve = _check_device_type(existing_device_types, device_dict, existing_device)

            if device_type_resolve:
                wrong_type_devices.append(device_name)

    logger.debug(f"Removed: {wrong_type_devices}")
    logger.info(
        f"Operations complete:\n" 
        f" \u2713 Removed {len(wrong_type_devices)} devices"
    )           
    return wrong_type_devices

if __name__ == '__main__':
    from pynetbox_functions import _main
    #_main("Clean redundant devices on a NetBox server", clean)

    from pynetbox_functions import _debug
    _debug(clean)
