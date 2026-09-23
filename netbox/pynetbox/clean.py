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
    _cache_devices
)

# Get logger
logger = logging.getLogger(__name__)

def _check_device_type(nb_session:NetBoxApi, device_dict: dict, existing_device: object) -> Optional[str]:
    """
    Check if the required device type is the same as the device in the NetBox.

    Args:
        - device_dict: device data that has to be added to NetBox
        - existing_device: existing device object on the platform, with the same hostname

    Returns:
        Existing device name if it has to be modified or None if not.
    """
    # Asset the device type
    if existing_device.device_type.slug == device_dict.get('device_type'):
        return None

    hostname = existing_device.name
    logger.info(f"Found conflicting device type {hostname}")
    logger.info("Checking for interfaces...")

    # 1. Fetch expected interface count for this specific device type on the fly
    templates = nb_session.dcim.interface_templates.filter(device_type_id=existing_device.device_type.id)
    expected_interface_count = len(list(templates)) if templates else 0

    # 2. Get the actual interfaces currently on the device
    all_actual_interfaces = list(nb_session.dcim.interfaces.filter(device_id=existing_device.id))

    # 3. Filter out VLANs/Virtual interfaces
    physical_interfaces = [
        iface for iface in all_actual_interfaces 
        if getattr(iface.type, 'value', '') != 'virtual'
    ]
    actual_interface_count = len(physical_interfaces)

    logger.info(
        f"Interface count: Expected {expected_interface_count} (template), " 
        f"Found {actual_interface_count} (physical).")

    # 4. Compare and execute logic
    if actual_interface_count == expected_interface_count:
        # Update device hostname to its SN and decommission it
        new_name = existing_device.serial if existing_device.serial else f"{hostname}-decom"
        logger.info(f"Interface counts match. Renaming {hostname} to {new_name} and setting status to 'decommissioning'.")
        
        existing_device.name = new_name
        existing_device.status = 'decommissioning'
        existing_device.save()
    else:
        logger.info(f"Interface count mismatch. Deleting {hostname}.")
        _delete_netbox_obj(existing_device)

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
            device_type_resolve = _check_device_type(nb_session, device_dict, existing_device)

            if device_type_resolve:
                wrong_type_devices.append(device_name)

    logger.info(f"Found conflicting devices: {wrong_type_devices}")
    logger.info(
        f"Operations complete:\n" 
        f" \u2713 Updated {len(wrong_type_devices)} conflicting devices"
    )           
    return wrong_type_devices

if __name__ == '__main__':
    from pynetbox_functions import _main
    _main("Clean redundant devices on a NetBox server", clean)

    #from pynetbox_functions import _debug
    #_debug(clean)
