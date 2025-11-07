#!/usr/bin/env python3

'''
LAG (Link Aggregation Group) management functions for NetBox
'''

import logging
from typing import Dict, List, Tuple, Set
from collections import defaultdict

from pynetbox.core.api import Api as NetBoxApi

# Import helper functions from pynetbox_functions
from pynetbox_functions import (
    _cache_devices,
    _bulk_create,
    _bulk_update,
)

logger = logging.getLogger(__name__)

def lags(nb_session: NetBoxApi, data: Dict[str, List[Dict]]) -> None:
    """
    Update switch LAGs on a NetBox server from YAML data.

    This function:
    1. Creates LAG interfaces that don't exist
    2. Updates member interfaces to associate them with their LAG
    3. Handles virtual chassis - automatically includes interfaces from all VC members

    Args:
        nb_session: pynetbox API session
        data: Dictionary containing 'lags' and 'lag_interfaces' lists
    
    Returns:
        None
    
    Example data structure:
        {
            'lags': [
                {'hostname': 'rsgw1u140sp-1', 'name': 'Trk1'},
                {'hostname': 'rsgw1u140sp-1', 'name': 'Trk10'},
            ],
            'lag_interfaces': [
                {'hostname': 'rsgw1u140sp-1', 'interface': '1/A1', 'lag_name': 'Trk1'},
                {'hostname': 'rsgw1u140sp-1', 'interface': '2/A1', 'lag_name': 'Trk1'},  # 2/A1 from VC member
            ]
        }
    
    Note on Virtual Chassis:
        When a device is part of a virtual chassis, the function automatically
        includes interfaces from all member devices. For example, if 'switch-1' 
        is the master of a VC with member 'switch-2', interfaces like '2/A1' 
        (where '2' is the stack number) will be found and associated with LAGs
        on 'switch-1'.
    """
    if not data:
        logger.warning("No data provided to lags function")
        return

    lag_list = data.get('lags', [])
    lag_interface_list = data.get('lag_interfaces', [])

    if not lag_list:
        logger.info("No LAGs to process")
        return

    logger.info(f"Processing {len(lag_list)} LAGs and {len(lag_interface_list)} LAG member interfaces")

    # Step 1: Get all unique device names from both lists
    device_names = _extract_unique_device_names(lag_list, lag_interface_list)
    logger.debug(f"Found {len(device_names)} unique devices")

    # Step 2: Cache all devices to minimize API calls
    devices_cache = _cache_devices(nb_session, list(device_names))
    if not devices_cache:
        logger.error("Failed to cache devices - no devices found")
        return

    logger.info(f"Cached {len(devices_cache)} devices")

    # Step 3: Cache all existing interfaces for these devices
    interfaces_cache = _cache_interfaces_for_devices(nb_session, devices_cache)
    logger.info(f"Cached {len(interfaces_cache)} existing interfaces")

    # Step 4: Process LAG interfaces - create missing ones
    _process_lag_interfaces(nb_session, lag_list, devices_cache, interfaces_cache)

    # Step 5: Re-cache interfaces to include newly created LAGs
    interfaces_cache = _cache_interfaces_for_devices(nb_session, devices_cache)
    logger.debug(f"Re-cached {len(interfaces_cache)} interfaces after LAG creation")

    # Step 6: Process member interfaces - update them to point to their LAGs
    _process_member_interfaces(nb_session, lag_interface_list, devices_cache, interfaces_cache)

    logger.info("LAG processing completed successfully")


def _extract_unique_device_names(lag_list: List[Dict], lag_interface_list: List[Dict]) -> Set[str]:
    """
    Extract all unique device names from LAG and LAG interface lists.
    
    Args:
        lag_list: List of LAG definitions
        lag_interface_list: List of LAG member interface definitions
    
    Returns:
        Set of unique device hostnames
    """
    device_names = set()
    
    for lag in lag_list:
        if 'hostname' in lag:
            device_names.add(lag['hostname'])
    
    for lag_iface in lag_interface_list:
        if 'hostname' in lag_iface:
            device_names.add(lag_iface['hostname'])
    
    return device_names


def _cache_interfaces_for_devices(
    nb_session: NetBoxApi,
    devices_cache: Dict[str, object]
) -> Dict[Tuple[str, str], object]:
    """
    Cache all interfaces for a list of devices and their virtual chassis members.
    
    For devices in a virtual chassis, this function also caches interfaces from
    all member devices in the chassis, allowing interfaces like "2/A1" from 
    member device "switch-2" to be found when processing "switch-1".
    
    Args:
        nb_session: pynetbox API session
        devices_cache: Dictionary mapping device name to device object
    
    Returns:
        Dictionary mapping (hostname, interface_name) to interface object
    """
    if not devices_cache:
        return {}
    
    # Get all device IDs, including virtual chassis members
    device_ids = set()
    vc_device_map = {}  # Map VC member device to master device for lookups
    
    for hostname, device in devices_cache.items():
        device_ids.add(device.id)
        
        # If device is part of a virtual chassis, get all member devices
        if hasattr(device, 'virtual_chassis') and device.virtual_chassis:
            vc_id = device.virtual_chassis.id
            logger.debug(f"Device {hostname} is part of virtual chassis ID {vc_id}")
            
            # Fetch all devices in this virtual chassis
            try:
                vc_members = nb_session.dcim.devices.filter(virtual_chassis_id=vc_id)
                for vc_member in vc_members:
                    device_ids.add(vc_member.id)
                    # Map the VC member to the master device for lookup purposes
                    vc_device_map[vc_member.name] = hostname
                    logger.debug(f"  Added VC member {vc_member.name} (ID: {vc_member.id})")
            except Exception as e:
                logger.warning(f"Failed to fetch virtual chassis members for {hostname}: {e}")
    
    try:
        # Fetch all interfaces for these devices (including VC members) in bulk
        interfaces = nb_session.dcim.interfaces.filter(device_id=list(device_ids))
        
        # Build cache with composite key: (hostname, interface_name)
        interfaces_dict = {}
        for interface in interfaces:
            # Get device name from the interface's device attribute
            device_name = interface.device.name if hasattr(interface.device, 'name') else None
            if not device_name:
                continue
            
            # For interfaces on VC members, create entries for both the actual device
            # and the master device (for lookup flexibility)
            key = (device_name, interface.name)
            interfaces_dict[key] = interface
            
            # If this device is a VC member, also map it to the master device
            if device_name in vc_device_map:
                master_hostname = vc_device_map[device_name]
                master_key = (master_hostname, interface.name)
                interfaces_dict[master_key] = interface
                logger.debug(f"  Mapped interface {interface.name} from {device_name} to master {master_hostname}")
        
        logger.debug(f"Cached {len(interfaces_dict)} interface entries from {len(device_ids)} devices (including VC members)")
        return interfaces_dict
        
    except Exception as e:
        logger.error(f"Failed to cache interfaces: {e}", exc_info=True)
        return {}


def _process_lag_interfaces(
    nb_session: NetBoxApi,
    lag_list: List[Dict],
    devices_cache: Dict[str, object],
    interfaces_cache: Dict[Tuple[str, str], object]
) -> None:
    """
    Process LAG interfaces - create those that don't exist.
    
    Args:
        nb_session: pynetbox API session
        lag_list: List of LAG definitions from YAML
        devices_cache: Cached device objects
        interfaces_cache: Cached interface objects
    """
    if not lag_list:
        return
    
    # Separate existing and missing LAGs
    existing_lags, missing_lags = _identify_missing_lags(
        lag_list, devices_cache, interfaces_cache
    )
    
    logger.info(f"Found {len(existing_lags)} existing LAGs, {len(missing_lags)} to create")
    
    # Create missing LAGs
    if missing_lags:
        _create_lag_interfaces(nb_session, missing_lags, devices_cache)
    else:
        logger.info("All LAG interfaces already exist")


def _identify_missing_lags(
    lag_list: List[Dict],
    devices_cache: Dict[str, object],
    interfaces_cache: Dict[Tuple[str, str], object]
) -> Tuple[List[Dict], List[Dict]]:
    """
    Identify which LAGs already exist and which need to be created.
    
    Args:
        lag_list: List of LAG definitions
        devices_cache: Cached device objects
        interfaces_cache: Cached interface objects
    
    Returns:
        Tuple of (existing_lags, missing_lags)
    """
    existing = []
    missing = []
    
    for lag in lag_list:
        hostname = lag.get('hostname')
        lag_name = lag.get('name')
        
        if not hostname or not lag_name:
            logger.warning(f"Skipping LAG with missing hostname or name: {lag}")
            continue
        
        # Check if device exists
        if hostname not in devices_cache:
            logger.warning(f"Device {hostname} not found in cache, skipping LAG {lag_name}")
            continue
        
        # Check if LAG interface already exists
        interface_key = (hostname, lag_name)
        if interface_key in interfaces_cache:
            existing.append(lag)
            logger.debug(f"LAG {lag_name} already exists on {hostname}")
        else:
            missing.append(lag)
            logger.debug(f"LAG {lag_name} needs to be created on {hostname}")
    
    return existing, missing


def _create_lag_interfaces(
    nb_session: NetBoxApi,
    missing_lags: List[Dict],
    devices_cache: Dict[str, object]
) -> List[object]:
    """
    Create LAG interfaces in NetBox.
    
    Args:
        nb_session: pynetbox API session
        missing_lags: List of LAG definitions to create
        devices_cache: Cached device objects
    
    Returns:
        List of created interface objects
    """
    payloads = []
    
    for lag in missing_lags:
        hostname = lag.get('hostname')
        lag_name = lag.get('name')
        
        device = devices_cache.get(hostname)
        if not device:
            logger.warning(f"Cannot create LAG {lag_name}: device {hostname} not in cache")
            continue
        
        # Build payload for LAG interface creation
        payload = {
            'device': device.id,
            'name': lag_name,
            'type': 'lag',  # NetBox interface type for LAG
        }
        
        # Add optional fields if present in YAML
        if 'description' in lag:
            payload['description'] = lag['description']
        if 'mtu' in lag:
            payload['mtu'] = lag['mtu']
        if 'enabled' in lag:
            payload['enabled'] = lag['enabled']
        if 'mode' in lag:
            payload['mode'] = lag['mode']
        
        payloads.append(payload)
    
    if not payloads:
        logger.warning("No valid LAG interface payloads to create")
        return []
    
    # Use bulk create from pynetbox_functions
    created = _bulk_create(nb_session.dcim.interfaces, payloads, "LAG interface")
    
    return created


def _process_member_interfaces(
    nb_session: NetBoxApi,
    lag_interface_list: List[Dict],
    devices_cache: Dict[str, object],
    interfaces_cache: Dict[Tuple[str, str], object]
) -> None:
    """
    Process member interfaces - update them to associate with their LAG.
    
    Args:
        nb_session: pynetbox API session
        lag_interface_list: List of member interface definitions
        devices_cache: Cached device objects
        interfaces_cache: Cached interface objects (including LAGs)
    """
    if not lag_interface_list:
        logger.info("No LAG member interfaces to process")
        return
    
    # Build update payloads
    update_payloads = _build_member_interface_payloads(
        lag_interface_list, devices_cache, interfaces_cache
    )
    
    if not update_payloads:
        logger.info("No member interface updates needed")
        return
    
    logger.info(f"Updating {len(update_payloads)} member interfaces")
    
    # Use bulk update from pynetbox_functions
    _bulk_update(nb_session.dcim.interfaces, update_payloads, "member interface")


def _build_member_interface_payloads(
    lag_interface_list: List[Dict],
    devices_cache: Dict[str, object],
    interfaces_cache: Dict[Tuple[str, str], object]
) -> List[Dict]:
    """
    Build update payloads for member interfaces.
    
    Args:
        lag_interface_list: List of member interface definitions
        devices_cache: Cached device objects
        interfaces_cache: Cached interface objects
    
    Returns:
        List of update payloads with interface IDs and LAG associations
    """
    payloads = []
    skipped = 0
    
    for member in lag_interface_list:
        hostname = member.get('hostname')
        interface_name = member.get('interface')
        lag_name = member.get('lag_name')
        
        if not all([hostname, interface_name, lag_name]):
            logger.warning(f"Skipping incomplete member interface definition: {member}")
            skipped += 1
            continue
        
        # Validate device exists
        if hostname not in devices_cache:
            logger.warning(f"Device {hostname} not found, skipping interface {interface_name}")
            skipped += 1
            continue
        
        # Get member interface from cache
        member_key = (hostname, interface_name)
        member_interface = interfaces_cache.get(member_key)
        
        if not member_interface:
            logger.warning(
                f"Member interface {interface_name} not found on {hostname} - "
                f"interface may need to be created first"
            )
            skipped += 1
            continue
        
        # Get LAG interface from cache
        lag_key = (hostname, lag_name)
        lag_interface = interfaces_cache.get(lag_key)
        
        if not lag_interface:
            logger.error(
                f"LAG interface {lag_name} not found on {hostname} - "
                f"cannot associate member {interface_name}"
            )
            skipped += 1
            continue
        
        # Check if update is needed
        current_lag_id = getattr(member_interface.lag, 'id', None) if member_interface.lag else None
        
        if current_lag_id == lag_interface.id:
            logger.debug(f"{hostname}:{interface_name} already in LAG {lag_name}")
            continue
        
        # Build update payload
        payload = {
            'id': member_interface.id,
            'lag': lag_interface.id,
        }
        
        payloads.append(payload)
        logger.debug(f"Will update {hostname}:{interface_name} to join LAG {lag_name}")
    
    if skipped > 0:
        logger.warning(f"Skipped {skipped} member interface(s) due to missing data")
    
    return payloads


def _group_lags_by_device(lag_list: List[Dict]) -> Dict[str, List[str]]:
    """
    Group LAG names by device hostname.
    
    Args:
        lag_list: List of LAG definitions
    
    Returns:
        Dictionary mapping hostname to list of LAG names
    """
    grouped = defaultdict(list)
    
    for lag in lag_list:
        hostname = lag.get('hostname')
        lag_name = lag.get('name')
        
        if hostname and lag_name:
            grouped[hostname].append(lag_name)
    
    return dict(grouped)

if __name__ == '__main__':
    from pynetbox_functions import _main, _debug
    _main("Update/add LAGs to a NetBox server", lags)