#!/usr/bin/env python3

'''
Synchronize device interfaces on a NetBox platform using `pynetbox` library
Main function, to import:

- interfaces(nb_session, data):
    - nb_session - pynetbox API session
    - data - data (yaml format)
'''

import pynetbox, logging

from typing import Dict, List
from pynetbox.core.api import Api as NetBoxApi

from pynetbox_functions import _cache_devices, _bulk_create, _bulk_update, _delete_netbox_obj

# Configure logging
#logging.basicConfig(level = logging.INFO)
logging.basicConfig(level = logging.DEBUG)
logger = logging.getLogger(__name__)

def interfaces(nb_session: NetBoxApi, data: Dict[str, List[str]]) -> None:
    """
    Create or update interfaces in NetBox based on YAML data.
    Args:
        nb_session: pynetbox API session
        data: Dictionary containing 'device_interfaces' list
    """
    if 'device_interfaces' not in data:
        logger.warning("No 'device_interfaces' key found in data")
        return

    device_interfaces = data.get('device_interfaces', [])
    if not device_interfaces:
        logger.info("No interfaces to process")
        return

    # Cache all devices mentioned in the data
    device_names = list(set(item.get('hostname') for item in device_interfaces))
    logger.info(f"Processing {len(device_interfaces)} interfaces for {len(device_names)} devices")

    cached_devices = _cache_devices(nb_session, device_names)
    logger.info(f"Found {len(cached_devices)} devices out of {len(set(device_names))} requested")


    # Cache all VLANs that are mentioned in the data
    unique_vlans = set()
    for item in device_interfaces:
        if 'vlan_id' in item and item.get('vlan_id'):
            vlan_key = (item.get('vlan_id'), item.get('vlan_name', ''))
            unique_vlans.add(vlan_key)

    logger.info(f"Processing {len(unique_vlans)} VLANs requested")

    # Fetch all VLANs in one or minimal requests
    cached_vlans = {}
    if unique_vlans:
        try:
            vlan_ids = [vid for vid, _ in unique_vlans]
            all_vlans = nb_session.ipam.vlans.filter(vid = vlan_ids)
            for vlan in all_vlans:
                vid = str(vlan.vid)
                key = (vid, vlan.name)
                cached_vlans[key] = vlan.id
                # Also cache by VIS only for fallback
                cached_vlans[vid, ''] = vlan.id
        except Exception as e:
            logger.warning(f"Error caching VLANs: {e}")

    logger.info(f"Fetched total of {len(cached_vlans)} VLANs")

    # Cache all existing interfaces for requested devices 
    cached_interfaces = {}
    for hostname, device in cached_devices.items():
        try:
            existing_interfaces = {
                intf.name: intf
                for intf in nb_session.dcim.interfaces.filter(device_id = device.id)
            }
            cached_interfaces[hostname] = existing_interfaces
        except Exception as e:
            logger.error(f"Error fetching interfaces for {hostname}: {e}")
            cached_interfaces[hostname] = {}

    # Group interface by device for efficient processing
    interfaces_by_device = {}
    for item in device_interfaces:
        hostname = item.get('hostname')
        if hostname not in interfaces_by_device:
            interfaces_by_device[hostname] = []
        interfaces_by_device[hostname].append(item)

    # Collect interfaces to create and update
    interfaces_to_create = []
    interfaces_to_update = []
    interfaces_to_delete = []

    # Process each device's interface
    logger.info(f"Processing {len(cached_interfaces)} interfaces for {len(cached_devices)} devices")
    for hostname, interface_list in interfaces_by_device.items():
        device = cached_devices.get(hostname)
        if not device:
            logger.warning(f"Device {hostname} no found in NetBox, skipping interfaces")
            continue

        existing_interfaces = cached_interfaces.get(hostname, {})

        # Check if this device has stack-numbered interfaces (e.g., "1/1", "2/1")
        has_stacked_interfaces = any('/' in item.get('interface') for item in interface_list)

        if has_stacked_interfaces:
            # Extract unique stack numbers from the data
            stack_numbers = set()
            for item in interface_list:
                if '/' in item.get('interface'):
                    stack_num = item.get('interface').split('/')[0]
                    stack_numbers.add(stack_num)

            # Find interfaces without stack numbers that should be deleted
            for intf_name, intf_obj in existing_interfaces.items():
                # Check if it's a numeric-only interface (e.g., '1', '48')
                if intf_name.isdigit():
                    # Check if there is a corresponding stacked interface for any stack
                    for stack_num in stack_numbers:
                        stacked_equivalent = f"{stack_num}/{intf_name}"
                        if stacked_equivalent in [item.get('interface') for item in interface_list]:
                            # Mark for deletion
                            interfaces_to_delete.append(intf_obj)
                            logger.info(
                                f"Will delete non-stacked interface '{intf_name}' on {hostname} "
                                f"(stacked interface '{stacked_equivalent}' exists)"
                            )
                            break

        for item in interface_list:
            interface_name = item.get('interface')
            existing_intf = existing_interfaces.get(interface_name)

            # Validate required fields
            i_type = item.get('type')
            if not i_type:
                logger.error(
                    f"Missing or empty 'type' field for interface {interface_name} "
                    f"on device {hostname}. Skipping this interface."
                )
                continue 

            # Resolve VLAN if provided
            vlan_id = None
            if 'vlan_id' in item and item.get('vlan_id'):
                vid = item.get('vlan_id')
                vname = item.get('vlan_name')

                vlan_key = (vid, vname)
                vlan_id = cached_vlans.get(vlan_key)

                if not vlan_id:
                    # Try without name as fallback
                    vlan_id = cached_vlans.get((vid, ''))
                if not vlan_id:
                    logger.warning(f"VLAN {vid} ({vname}) not found in cache")

            # Build interface payload
            payload = {
                'device': device.id,
                'name': interface_name,
                'type': i_type,
                'description': item.get('name', '')
            }
            # Add optional fields
            if 'poe_mode' in item:
                payload['poe_mode'] = item.get('poe_mode')
            if 'poe_type' in item:
                payload['poe_type'] = item.get('poe_type')

            # Handle VLAN assignment based on trunk mode
            is_trunk = item.get('is_trunk', False)
            if is_trunk:
                payload['mode'] = 'tagged' 
                if vlan_id:
                    # For trunk ports, VLAN goes to tagged_vlans (as a list)
                    payload['tagged_vlans'] = [vlan_id]
            else:
                payload['mode'] = 'access' 
                if vlan_id:
                    # For access ports, VLAN goes to untagged_vlan 
                    payload['untagged_vlan'] = vlan_id
                # Ensure no tagged VLANs on access ports
                payload['tagged_vlans'] = []

            if existing_intf:
                # Update existing interface
                payload['id'] = existing_intf.id
                interfaces_to_update.append(payload)
            else:
                # Create new interface
                interfaces_to_create.append(payload)

    # Bulk create new interfaces
    if interfaces_to_create:
        logger.info(f"Bulk create {len(interfaces_to_create)} interfaces")
        _bulk_create(
            nb_session.dcim.interfaces,
            interfaces_to_create,
            f"interfaces(s)"
        )

    # Bulk update existing interfaces
    if interfaces_to_update:
        logger.info(f"Bulk update {len(interfaces_to_update)} interfaces")
        _bulk_update(
            nb_session.dcim.interfaces,
            interfaces_to_update,
            f"interfaces(s)"
        )

    # Delete obsolete non-stacked interfaces
    if interfaces_to_delete:
        nr_deleted = 0
        for intf_obj in interfaces_to_delete:
            if _delete_netbox_obj(intf_obj):
                nr_deleted += 1
        logger.info(f"Deleted {nr_deleted} obsolete non-stacked interface(s)")

    logger.info(f"Finished processing {len(device_interfaces)} interface entries")

def trunks(nb_session: NetBoxApi, data: Dict[str, List[Dict]]) -> None:
    """
    Create or update LAG interfaces in NetBox based on YAML data.
    Args:
        nb_session: pynetbox API session
        data: Dictionary containing 'trunk_interfaces' list
    """

    if 'trunk_interfaces' not in data:
        logger.warning("No 'trunk_interfaces' key found in data")
        return

    trunk_interfaces = data.get('trunk_interfaces')
    if not trunk_interfaces:
        logger.info("No trunks to process")
        return

    # Cache all devices mentioned in the data
    device_names = list(set(item.get('hostname') for item in trunk_interfaces))
    cached_devices = _cache_devices(nb_session, device_names)
    logger.info(f"Processing {len(trunk_interfaces)} LAG interfaces for {len(cached_devices)} devices")

    # Cache all existing interfaces at once
    cached_interfaces, cached_lags = {}, {}
    nr_interfaces, nr_lags = 0, 0

    for hostname, device in cached_devices.items():
        try:
            d_interfaces = {
                intf.name: intf 
                for intf in nb_session.dcim.interfaces.filter(device_id = device.id)
            }
            cached_interfaces[hostname] = d_interfaces
            nr_interfaces += len(d_interfaces)

            # Separate LAG interfaces
            cached_lags[hostname] = {
                name: intf 
                for name, intf in d_interfaces.items()
                if (hasattr(intf.type, 'value') and intf.type.value == 'lag') or
                   (hasattr(intf.type, 'label') and 'LAG' in intf.type.label)
            }
            nr_lags += len(cached_lags[hostname])
        except Exception as e:
            logger.error(f"Error fetching interfaces for {hostname}: {e}")
            cached_interfaces[hostname] = {}
            cached_lags[hostname] = {}

    logger.info(f"Found {nr_lags} LAG interfaces in {nr_interfaces} total")

    # Group by device and trunk

if __name__ == '__main__':
    from pynetbox_functions import _main
    #_main("Synchronizing device interfaces", interfaces)
    _main("Synchronizing device interfaces", trunks)