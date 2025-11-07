#!/usr/bin/env python3

"""
Interface management functions for NetBox
Handles creation, update, and deletion of device interfaces with VLAN assignments
"""

import logging
from typing import Dict, List, Optional
from pynetbox.core.api import Api as NetBoxApi

# Import the standard delete function from pynetbox_functions
from pynetbox_functions import _bulk_create, _bulk_update
from pynetbox_functions import _cache_devices
    
logger = logging.getLogger(__name__)

def interfaces(nb_session: NetBoxApi, data: Dict[str, List[Dict]]) -> None:
    """
    Create or update interfaces in NetBox based on YAML data.
    
    Process flow:
    1. Delete interfaces specified in 'delete_interfaces'
    2. Create/update interfaces from 'device_interfaces'
    3. Add tagged VLANs from 'tagged_vlans' to trunk interfaces
    
    Args:
        nb_session: pynetbox API session
        data: Dictionary containing:
            - 'delete_interfaces': List of interfaces to delete
            - 'device_interfaces': List of interfaces to create/update
            - 'tagged_vlans': List of trunk interfaces with tagged VLANs
    """
    
    # Step 1: Delete interfaces if specified
    if 'delete_interfaces' in data and data['delete_interfaces']:
        logger.info("=== Starting interface deletion ===")
        _delete_interfaces(nb_session, data['delete_interfaces'])
    
    # Step 2: Create or update interfaces
    if 'device_interfaces' in data and data['device_interfaces']:
        logger.info("=== Starting interface creation/update ===")
        _process_device_interfaces(nb_session, data)
    
    logger.info("=== Interface management completed ===")


def _bulk_delete_interfaces(interfaces: List[object]) -> int:
    """
    Delete interfaces using the standard _delete_netbox_obj function.
    
    Args:
        interfaces: List of interface objects to delete
    
    Returns:
        Number of successfully deleted interfaces
    """
    if not interfaces:
        return 0
    
    deleted_count = 0
    
    logger.info(f"Attempting to delete {len(interfaces)} interfaces...")
    
    # Use the existing _delete_netbox_obj function for consistency
    for interface in interfaces:
        if _delete_netbox_obj(interface):
            deleted_count += 1
    
    logger.info(f"Successfully deleted {deleted_count}/{len(interfaces)} interfaces")
    return deleted_count


def delete_device_interfaces(nb_session: NetBoxApi, data: Dict[str, List[Dict]]) -> None:
    """
    Delete module interfaces that are incorrectly assigned to devices.
    
    Module interfaces (e.g., 1/A1, 2/B1, 3/C2) should be on modules, not devices.
    This function:
    1. Identifies interfaces that look like module interfaces
    2. Checks if they're assigned to devices (wrong!)
    3. Collects them in a list
    4. Deletes them
    
    Use this to clean up interfaces created in the wrong location before
    recreating them correctly on modules.
    
    Args:
        nb_session: pynetbox API session
        data: Dictionary containing 'device_interfaces' with interface data
    
    Example:
        >>> # Preview first
        >>> preview_delete_device_interfaces(nb_session, data)
        >>> 
        >>> # Then delete
        >>> delete_device_interfaces(nb_session, data)
    """
    from pynetbox_functions import _cache_devices, _delete_netbox_obj
    
    if 'device_interfaces' not in data or not data['device_interfaces']:
        logger.info("No device_interfaces in data, nothing to delete")
        return
    
    logger.info("=== Scanning for misplaced module interfaces ===")
    
    # Collect device names
    device_names = list(set([entry.get('hostname') for entry in data['device_interfaces'] if entry.get('hostname')]))
    
    if not device_names:
        logger.warning("No valid device names found in data")
        return
    
    # Cache devices
    cached_devices = _cache_devices(nb_session, device_names)
    logger.info(f"Cached {len(cached_devices)} devices")
    
    # Get all interfaces for these devices
    device_ids = [device.id for device in cached_devices.values()]
    cached_interfaces = _cache_interfaces_by_device(nb_session, device_ids)
    logger.info(f"Cached {len(cached_interfaces)} total interfaces")
    
    # Identify module interfaces on devices (wrong placement)
    misplaced_interfaces = []
    
    for interface_key, interface in cached_interfaces.items():
        interface_name = interface.name
        
        # Check if this looks like a module interface
        module_letter = _extract_module_letter(interface_name)
        
        if module_letter:
            # This is a module interface name (e.g., 1/A1, 2/B2)
            # Check if it's assigned to a device (wrong!) instead of a module
            
            has_device = hasattr(interface, 'device') and interface.device
            has_module = hasattr(interface, 'module') and interface.module
            
            if has_device and not has_module:
                # Module interface wrongly on device!
                device_name = interface.device.name if hasattr(interface.device, 'name') else 'unknown'
                misplaced_interfaces.append({
                    'interface': interface,
                    'name': interface_name,
                    'device': device_name,
                    'module_letter': module_letter
                })
                logger.debug(
                    f"Found misplaced: {interface_name} on device {device_name} "
                    f"(should be on module {device_name}-{module_letter})"
                )
    
    # Report findings
    if not misplaced_interfaces:
        logger.info("No misplaced module interfaces found - all correctly assigned!")
        return
    
    logger.warning(
        f"Found {len(misplaced_interfaces)} module interface(s) incorrectly on devices"
    )
    
    # Show what will be deleted
    logger.info("Module interfaces to delete:")
    for item in misplaced_interfaces:
        logger.info(
            f"  - {item['name']} on device {item['device']} "
            f"(should be on module {item['device']}-{item['module_letter']})"
        )
    
    # Delete them
    logger.info(f"Deleting {len(misplaced_interfaces)} misplaced module interfaces...")
    
    deleted_count = 0
    failed_count = 0
    
    for item in misplaced_interfaces:
        if _delete_netbox_obj(item['interface']):
            deleted_count += 1
        else:
            failed_count += 1
    
    # Summary
    logger.info(
        f"Deletion complete: {deleted_count}/{len(misplaced_interfaces)} deleted"
    )
    if failed_count > 0:
        logger.warning(f"{failed_count} failed to delete (may have dependencies)")
    
    logger.info("=== Module interface cleanup completed ===")


def preview_delete_device_interfaces(nb_session: NetBoxApi, data: Dict[str, List[Dict]]) -> List[Dict]:
    """
    Preview which module interfaces would be deleted (dry-run).
    
    Same as delete_device_interfaces but doesn't actually delete anything.
    
    Args:
        nb_session: pynetbox API session
        data: Dictionary containing 'device_interfaces'
    
    Returns:
        List of dicts with interface details that would be deleted
    """
    from pynetbox_functions import _cache_devices
    
    if 'device_interfaces' not in data or not data['device_interfaces']:
        logger.info("No device_interfaces in data")
        return []
    
    logger.info("=== Preview: Scanning for misplaced module interfaces ===")
    
    # Collect device names
    device_names = list(set([entry.get('hostname') for entry in data['device_interfaces'] if entry.get('hostname')]))
    
    if not device_names:
        return []
    
    # Cache devices and interfaces
    cached_devices = _cache_devices(nb_session, device_names)
    device_ids = [device.id for device in cached_devices.values()]
    cached_interfaces = _cache_interfaces_by_device(nb_session, device_ids)
    
    # Identify misplaced
    misplaced = []
    
    for interface_key, interface in cached_interfaces.items():
        interface_name = interface.name
        module_letter = _extract_module_letter(interface_name)
        
        if module_letter:
            has_device = hasattr(interface, 'device') and interface.device
            has_module = hasattr(interface, 'module') and interface.module
            
            if has_device and not has_module:
                device_name = interface.device.name if hasattr(interface.device, 'name') else 'unknown'
                misplaced.append({
                    'interface_id': interface.id,
                    'name': interface_name,
                    'device': device_name,
                    'module_letter': module_letter,
                    'should_be_on': f"{device_name}-{module_letter}"
                })
    
    # Report
    if not misplaced:
        logger.info("No misplaced module interfaces found")
    else:
        logger.info(f"Found {len(misplaced)} misplaced module interface(s):")
        for item in misplaced:
            logger.info(
                f"  - {item['name']} on device {item['device']} "
                f"(should be on {item['should_be_on']})"
            )
    
    logger.info("=== Preview complete (no deletion) ===")
    return misplaced


def _bulk_delete_interfaces(interfaces: List[object]) -> int:
    """
    Delete interfaces using the standard _delete_netbox_obj function.
    
    Args:
        interfaces: List of interface objects to delete
    
    Returns:
        Number of successfully deleted interfaces
    """
    if not interfaces:
        return 0
    
    # Import the standard delete function from pynetbox_functions
    from pynetbox_functions import _delete_netbox_obj
    
    deleted_count = 0
    
    logger.info(f"Attempting to delete {len(interfaces)} interfaces...")
    
    # Use the existing _delete_netbox_obj function for consistency
    for interface in interfaces:
        if _delete_netbox_obj(interface):
            deleted_count += 1
    
    logger.info(f"Successfully deleted {deleted_count}/{len(interfaces)} interfaces")
    return deleted_count


def _delete_interfaces(nb_session: NetBoxApi, delete_list: List[Dict[str, str]]) -> None:
    """
    Delete specified interfaces from NetBox using bulk operations.
    
    Args:
        nb_session: pynetbox API session
        delete_list: List of dicts with 'hostname' and 'interface' keys
    """
    if not delete_list:
        return
    
    # Step 1: Extract unique hostnames
    hostnames = list(set([entry.get('hostname') for entry in delete_list if entry.get('hostname')]))
    
    if not hostnames:
        logger.warning("No valid hostnames found in delete_list")
        return
    
    # Step 2: Bulk fetch devices using existing function
    logger.info(f"Fetching {len(hostnames)} devices for interface deletion...")
    from pynetbox_functions import _cache_devices
    cached_devices = _cache_devices(nb_session, hostnames)
    
    if not cached_devices:
        logger.warning("No devices found for deletion")
        return
    
    # Step 3: Bulk fetch all interfaces for these devices
    device_ids = [device.id for device in cached_devices.values()]
    logger.info(f"Fetching interfaces for {len(device_ids)} devices...")
    cached_interfaces = _cache_interfaces_by_device(nb_session, device_ids)
    
    # Step 4: Identify interfaces to delete
    interfaces_to_delete = []
    not_found_count = 0
    
    for entry in delete_list:
        hostname = entry.get('hostname')
        interface_name = entry.get('interface')
        
        if not hostname or not interface_name:
            logger.warning(f"Skipping invalid delete entry: {entry}")
            continue
        
        device = cached_devices.get(hostname)
        if not device:
            logger.warning(f"Device {hostname} not found in cache")
            not_found_count += 1
            continue
        
        # Look up interface in cache
        interface_key = f"{device.id}:{interface_name}"
        interface = cached_interfaces.get(interface_key)
        
        if not interface:
            logger.info(f"Interface {interface_name} not found on {hostname} (already deleted or never existed)")
            not_found_count += 1
            continue
        
        interfaces_to_delete.append(interface)
        logger.debug(f"Marked interface {interface_name} on {hostname} for deletion")
    
    # Step 5: Bulk delete interfaces
    deleted_count = _bulk_delete_interfaces(interfaces_to_delete)
    
    logger.info(f"Deletion summary: {deleted_count} deleted, {not_found_count} not found")


def _process_device_interfaces(nb_session: NetBoxApi, data: Dict[str, List[Dict]]) -> None:
    """
    Process and create/update device interfaces with VLAN assignments using bulk operations.
    
    Args:
        nb_session: pynetbox API session
        data: Dictionary containing 'device_interfaces' and optionally 'tagged_vlans'
    """
    from pynetbox_functions import _cache_devices, _bulk_create, _bulk_update
    
    device_interfaces = data.get('device_interfaces', [])
    tagged_vlans_data = data.get('tagged_vlans', [])
    
    # Build a lookup for tagged VLANs by hostname and interface
    tagged_vlans_lookup = _build_tagged_vlans_lookup(tagged_vlans_data)
    
    # IMPORTANT: Collect ALL interfaces to process
    # Some interfaces may only be in tagged_vlans (trunks), not in device_interfaces
    all_interfaces_to_process = {}  # Key: "hostname:interface", Value: entry dict
    
    # First, add all from device_interfaces
    for entry in device_interfaces:
        hostname = entry.get('hostname')
        interface_name = entry.get('interface')
        if hostname and interface_name:
            key = f"{hostname}:{interface_name}"
            all_interfaces_to_process[key] = entry.copy()
    
    # Then, add trunk interfaces from tagged_vlans that aren't in device_interfaces
    for trunk_entry in tagged_vlans_data:
        hostname = trunk_entry.get('hostname')
        interface_name = trunk_entry.get('interface')
        if hostname and interface_name:
            key = f"{hostname}:{interface_name}"
            if key not in all_interfaces_to_process:
                # This trunk interface is not in device_interfaces, add it
                all_interfaces_to_process[key] = {
                    'hostname': hostname,
                    'interface': interface_name,
                    'is_trunk': True,
                    'type': 'lag',  # Assume LAG/trunk type
                    'name': f"Trunk {interface_name}",  # Default description
                }
                logger.debug(f"Added trunk interface {interface_name} on {hostname} (only in tagged_vlans)")
    
    if not all_interfaces_to_process:
        logger.info("No interfaces to process")
        return
    
    # Cache devices to minimize API calls
    device_names = list(set([entry['hostname'] for entry in all_interfaces_to_process.values()]))
    cached_devices = _cache_devices(nb_session, device_names)
    
    # Cache modules for devices (for module interfaces like 2/A2)
    cached_modules = _cache_modules_for_devices(nb_session, cached_devices)
    
    # Cache VLANs for the devices
    cached_vlans = _cache_vlans_for_devices(nb_session, cached_devices)
    
    # Cache existing interfaces for these devices
    device_ids = [device.id for device in cached_devices.values()]
    cached_interfaces = _cache_interfaces_by_device(nb_session, device_ids)
    
    # Prepare payloads for bulk operations
    create_payloads = []
    update_payloads = []
    interfaces_for_vlan_assignment = []  # Track interfaces that need VLAN updates
    
    for key, entry in all_interfaces_to_process.items():
        hostname = entry.get('hostname')
        interface_name = entry.get('interface')
        
        if not hostname or not interface_name:
            logger.warning(f"Skipping invalid interface entry: {entry}")
            continue
        
        device = cached_devices.get(hostname)
        if not device:
            logger.warning(f"Device {hostname} not found in cache, skipping interface {interface_name}")
            continue
        
        # Check if this interface has tagged VLANs (making it a trunk)
        lookup_key = f"{hostname}:{interface_name}"
        tagged_vlans_list = tagged_vlans_lookup.get(lookup_key, [])
        is_trunk = len(tagged_vlans_list) > 0 or entry.get('is_trunk', False)
        
        logger.debug(f"Processing interface {interface_name} on {hostname}: is_trunk={is_trunk}, tagged_vlans={len(tagged_vlans_list)}")
        logger.debug(f"Raw entry data: hostname={hostname}, interface={interface_name}, type={entry.get('type')}, name={entry.get('name')}")
        
        # Prepare interface payload
        interface_payload = _prepare_interface_payload(
            device=device,
            entry=entry,
            is_trunk=is_trunk,
            cached_vlans=cached_vlans,
            cached_modules=cached_modules,
            nb_session=nb_session
        )
        
        # Check if interface exists
        interface_key = f"{device.id}:{interface_name}"
        existing_interface = cached_interfaces.get(interface_key)
        
        if existing_interface:
            # Prepare for update
            interface_payload['id'] = existing_interface.id
            update_payloads.append(interface_payload)
            interfaces_for_vlan_assignment.append({
                'interface': existing_interface,
                'device': device,
                'tagged_vlans': tagged_vlans_list,
                'is_trunk': is_trunk
            })
        else:
            # Prepare for creation
            create_payloads.append(interface_payload)
            interfaces_for_vlan_assignment.append({
                'interface_name': interface_name,
                'device': device,
                'tagged_vlans': tagged_vlans_list,
                'is_trunk': is_trunk,
                'payload': interface_payload
            })
    
    # Perform bulk operations
    created_interfaces = []
    if create_payloads:
        logger.info(f"Creating {len(create_payloads)} interfaces...")
        created_interfaces = _bulk_create(
            endpoint=nb_session.dcim.interfaces,
            payloads=create_payloads,
            kind='interface'
        )
    
    updated_interfaces = []
    if update_payloads:
        logger.info(f"Updating {len(update_payloads)} interfaces...")
        updated_interfaces = _bulk_update(
            endpoint=nb_session.dcim.interfaces,
            payloads=update_payloads,
            kind='interface'
        )
    
    # Assign tagged VLANs to trunk interfaces (must be done after interface creation/update)
    _assign_tagged_vlans_bulk(
        nb_session=nb_session,
        interfaces_data=interfaces_for_vlan_assignment,
        created_interfaces=created_interfaces,
        updated_interfaces=updated_interfaces,
        cached_vlans=cached_vlans
    )
    
    logger.info(f"Interface processing summary: {len(created_interfaces)} created, {len(updated_interfaces)} updated")


def _build_tagged_vlans_lookup(tagged_vlans_data: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Build a lookup dictionary for tagged VLANs by hostname and interface.
    
    Args:
        tagged_vlans_data: List of dicts with 'hostname', 'interface', and 'tagged_vlans'
    
    Returns:
        Dictionary with keys like "hostname:interface" mapping to list of tagged VLANs
    """
    lookup = {}
    
    for entry in tagged_vlans_data:
        hostname = entry.get('hostname')
        interface_name = entry.get('interface')
        tagged_vlans = entry.get('tagged_vlans', [])
        
        if hostname and interface_name:
            key = f"{hostname}:{interface_name}"
            lookup[key] = tagged_vlans
    
    return lookup


def _cache_modules_for_devices(nb_session: NetBoxApi, cached_devices: Dict[str, object]) -> Dict[str, object]:
    """
    Cache all modules for given devices in bulk.
    
    Module interfaces (like 2/A2) need to be assigned to the module, not the device.
    Module naming convention: {device_name}-{module_letter}
    Example: swgw1001ap-2-A for device swgw1001ap-2, module A
    
    Args:
        nb_session: pynetbox API session
        cached_devices: Dictionary of cached device objects
    
    Returns:
        Dictionary with keys "device_name:module_letter" mapping to module objects
        Example: {"swgw1001ap-2:A": <module object>}
    """
    if not cached_devices:
        return {}
    
    cached_modules = {}
    device_ids = [device.id for device in cached_devices.values()]
    
    try:
        # Bulk fetch all modules for the devices
        chunk_size = 500
        
        for i in range(0, len(device_ids), chunk_size):
            chunk = device_ids[i:i + chunk_size]
            modules = nb_session.dcim.modules.filter(device_id=chunk)
            
            # Check if we actually got any modules
            modules_list = list(modules)
            if not modules_list:
                logger.debug(f"No modules found for device IDs chunk: {chunk[:3]}... ({len(chunk)} devices)")
                continue
            
            logger.debug(f"Found {len(modules_list)} modules for chunk of {len(chunk)} devices")
            
            for module in modules_list:
                try:
                    # Safely get module name
                    module_name = getattr(module, 'name', None)
                    if not module_name:
                        logger.debug(f"Module object missing 'name' attribute, skipping: {module}")
                        continue
                    
                    # Module name format: {device_name}-{module_letter}
                    # Extract the module letter (last part after last hyphen)
                    module_parts = module_name.split('-')
                    if len(module_parts) > 0:
                        module_letter = module_parts[-1]  # e.g., "A", "B", "C"
                        
                        # Find the device name for this module
                        device_name = None
                        if hasattr(module, 'device'):
                            device_name = getattr(module.device, 'name', None)
                        
                        if device_name:
                            key = f"{device_name}:{module_letter}"
                            cached_modules[key] = module
                            logger.debug(f"Cached module {module_name} as {key}")
                        else:
                            logger.debug(f"Module {module_name} has no device.name, skipping")
                except Exception as e:
                    logger.debug(f"Error processing individual module: {e}")
        
        if cached_modules:
            logger.info(f"Cached {len(cached_modules)} modules for {len(cached_devices)} devices")
        else:
            logger.info(f"No modules found for {len(cached_devices)} devices (devices may not have modules)")
        
        return cached_modules
        
    except Exception as e:
        logger.warning(f"Error caching modules: {e}. Module interfaces may fail.", exc_info=True)
        return {}


def _cache_interfaces_by_device(nb_session: NetBoxApi, device_ids: List[int]) -> Dict[str, object]:
    """
    Cache all interfaces for given device IDs in bulk.
    
    Args:
        nb_session: pynetbox API session
        device_ids: List of device IDs
    
    Returns:
        Dictionary with keys "device_id:interface_name" mapping to interface objects
    """
    if not device_ids:
        return {}
    
    cached_interfaces = {}
    
    try:
        # Bulk fetch all interfaces for the devices
        # Note: NetBox API may have limits on filter size, so we might need to chunk
        chunk_size = 500  # Adjust based on your NetBox configuration
        
        for i in range(0, len(device_ids), chunk_size):
            chunk = device_ids[i:i + chunk_size]
            interfaces = nb_session.dcim.interfaces.filter(device_id=chunk)
            
            for interface in interfaces:
                key = f"{interface.device.id}:{interface.name}"
                cached_interfaces[key] = interface
        
        logger.info(f"Cached {len(cached_interfaces)} interfaces for {len(device_ids)} devices")
        return cached_interfaces
        
    except Exception as e:
        logger.error(f"Error caching interfaces: {e}", exc_info=True)
        return {}


def _cache_vlans_for_devices(nb_session: NetBoxApi, cached_devices: Dict[str, object]) -> Dict[str, object]:
    """
    Cache ALL VLANs from NetBox platform for assignment to interfaces.
    
    Args:
        nb_session: pynetbox API session
        cached_devices: Dictionary of cached device objects (not used, kept for compatibility)
    
    Returns:
        Dictionary with structure: {vid_or_name: vlan_object}
        Where vid_or_name can be either the VLAN ID (as string) or the VLAN name
    """
    cached_vlans = {}
    
    try:
        # Fetch ALL VLANs from NetBox platform
        logger.info("Caching all VLANs from NetBox platform...")
        all_vlans = nb_session.ipam.vlans.all()
        
        for vlan in all_vlans:
            # Index by vid (VLAN ID on switch) as string
            vid_key = str(vlan.vid)
            
            # Store by vid - if duplicate vid exists, last one wins
            # (VLANs with same vid can exist at different sites)
            cached_vlans[vid_key] = vlan
            
            # Also store by name for flexible lookup
            cached_vlans[vlan.name] = vlan
            
            logger.debug(f"Cached VLAN: vid={vlan.vid}, name={vlan.name}, site={vlan.site.name if vlan.site else 'Global'}, netbox_id={vlan.id}")
        
        logger.info(f"Cached {len(all_vlans)} VLANs from NetBox platform")
        
    except Exception as e:
        logger.error(f"Error caching VLANs from NetBox: {e}", exc_info=True)
    
    return cached_vlans


def _get_vlan_object(nb_session: NetBoxApi, device: object, vlan_id: Optional[str], 
                     vlan_name: Optional[str], cached_vlans: Dict) -> Optional[object]:
    """
    Get VLAN object from global cache or NetBox.
    
    IMPORTANT: vlan_id here is the VLAN ID on the switch (vid), NOT the NetBox database ID
    
    Args:
        nb_session: pynetbox API session
        device: Device object (used only for logging)
        vlan_id: VLAN ID on the switch (vid) as string (e.g., "5", "50", "350")
        vlan_name: VLAN name
        cached_vlans: Cached VLANs dictionary (global, not site-specific)
    
    Returns:
        VLAN object or None
    """
    if not vlan_id and not vlan_name:
        return None
    
    # Try to get from cache by VLAN ID (vid) first
    if vlan_id:
        vlan_id_str = str(vlan_id)  # Ensure it's a string
        vlan = cached_vlans.get(vlan_id_str)
        if vlan:
            logger.debug(f"Found VLAN in cache: vid={vlan_id}, name={vlan.name}, site={vlan.site.name if vlan.site else 'Global'}, netbox_id={vlan.id}")
            return vlan
    
    # Try by name
    if vlan_name:
        vlan = cached_vlans.get(vlan_name)
        if vlan:
            logger.debug(f"Found VLAN by name in cache: name={vlan_name}, vid={vlan.vid}, site={vlan.site.name if vlan.site else 'Global'}, netbox_id={vlan.id}")
            return vlan
    
    # Fallback to direct API call (search globally, not by site)
    try:
        # Search by vid (VLAN ID on switch) - no site restriction
        if vlan_id:
            # Try to find VLAN with this vid (might return multiple, we take first)
            vlans = nb_session.ipam.vlans.filter(vid=int(vlan_id))
            if vlans:
                vlan = vlans[0]  # Take first match
                logger.debug(f"Found VLAN via API: vid={vlan_id}, name={vlan.name}, site={vlan.site.name if vlan.site else 'Global'}, netbox_id={vlan.id}")
                return vlan
        
        if vlan_name:
            # Search by name globally
            vlans = nb_session.ipam.vlans.filter(name=vlan_name)
            if vlans:
                vlan = vlans[0]  # Take first match
                logger.debug(f"Found VLAN by name via API: name={vlan_name}, vid={vlan.vid}, site={vlan.site.name if vlan.site else 'Global'}, netbox_id={vlan.id}")
                return vlan
    except Exception as e:
        logger.warning(f"Error looking up VLAN (vid: {vlan_id}, Name: {vlan_name}): {e}")
    
    # VLAN not found - provide helpful diagnostic info
    logger.warning(
        f"VLAN not found for device {device.name}: "
        f"vid={vlan_id}, name={vlan_name}. "
        f"Total VLANs in cache: {len(cached_vlans)}"
    )
    if cached_vlans and logger.isEnabledFor(logging.DEBUG):
        # Log first few available VLANs to help debugging
        sample_vlans = list(cached_vlans.items())[:10]
        logger.debug(f"Sample of available VLANs: {[(k, getattr(v, 'vid', 'N/A')) for k, v in sample_vlans if hasattr(v, 'vid')]}")
    
    return None


def _extract_module_letter(interface_name: str) -> Optional[str]:
    """
    Extract module letter from interface name.
    
    Module interfaces follow pattern: {slot}/{module_letter}{port}
    Examples:
    - "2/A2" → "A"
    - "1/B1" → "B"
    - "3/C10" → "C"
    - "1/15" → None (not a module interface)
    - "Trk1" → None (trunk, not a module interface)
    
    Args:
        interface_name: Interface name (e.g., "2/A2")
    
    Returns:
        Module letter if this is a module interface, None otherwise
    """
    if '/' not in interface_name:
        # No slash, not a module interface (e.g., "Trk1")
        return None
    
    # Split by slash
    parts = interface_name.split('/')
    if len(parts) != 2:
        return None
    
    # Second part should be module letter + port number (e.g., "A2")
    port_part = parts[1]
    
    # Check if first character is a letter (module letter)
    if port_part and port_part[0].isalpha():
        return port_part[0].upper()  # Return uppercase letter
    
    return None


def _prepare_interface_payload(device: object, entry: Dict, is_trunk: bool,
                              cached_vlans: Dict, cached_modules: Dict, nb_session: NetBoxApi) -> Dict:
    """
    Prepare interface payload for bulk create/update.
    
    Handles both device interfaces and module interfaces.
    Module interfaces (e.g., 2/A2) are assigned to modules, not devices.
    
    Args:
        device: Device object
        entry: Interface data dictionary
        is_trunk: Whether this is a trunk interface
        cached_vlans: Cached VLANs dictionary
        cached_modules: Cached modules dictionary
        nb_session: pynetbox API session
    
    Returns:
        Interface payload dictionary
    """
    interface_name = entry['interface']
    
    # Detect if this is a module interface and get the module
    module_letter = _extract_module_letter(interface_name)
    module = None
    
    if module_letter:
        # This is a module interface (e.g., 2/A2 → module A)
        module_key = f"{device.name}:{module_letter}"
        module = cached_modules.get(module_key)
        
        if module:
            logger.debug(f"Interface {interface_name} will be assigned to module {module.name}")
        else:
            logger.warning(
                f"Interface {interface_name} appears to be a module interface (module {module_letter}), "
                f"but module {device.name}-{module_letter} not found. Will assign to device instead."
            )
    
    # Prepare interface payload
    interface_payload = {
        'name': interface_name,
        'type': entry.get('type', '1000base-t'),
        'description': entry.get('name', ''),
    }
    
    logger.debug(f"Creating interface payload: name='{interface_name}', type={entry.get('type', '1000base-t')}")
    
    # CRITICAL: Assign to module OR device
    if module:
        interface_payload['module'] = module.id
        logger.debug(f"Assigning to module ID {module.id} (module: {getattr(module, 'name', 'unknown')})")
        # Module interfaces don't have 'device' field
    else:
        interface_payload['device'] = device.id
        logger.debug(f"Assigning to device ID {device.id} (device: {device.name})")
    
    # Add PoE settings if present
    if entry.get('poe_mode'):
        interface_payload['poe_mode'] = entry['poe_mode']
    if entry.get('poe_type'):
        interface_payload['poe_type'] = entry['poe_type']
    
    # CRITICAL: Determine mode and handle VLAN assignments properly
    if is_trunk:
        # This is a trunk interface - tagged mode
        interface_payload['mode'] = 'tagged'
        # IMPORTANT: When switching to tagged mode, must clear untagged_vlan
        # NetBox doesn't allow both tagged VLANs and untagged_vlan in tagged mode
        interface_payload['untagged_vlan'] = None  # Clear any existing untagged VLAN
    else:
        # This is an access interface
        interface_payload['mode'] = 'access'
        
        # Handle untagged VLAN for access interfaces
        if entry.get('vlan_id') or entry.get('vlan_name'):
            untagged_vlan = _get_vlan_object(
                nb_session, device, entry.get('vlan_id'), 
                entry.get('vlan_name'), cached_vlans
            )
            if untagged_vlan:
                interface_payload['untagged_vlan'] = untagged_vlan.id
    
    return interface_payload


def _assign_tagged_vlans_bulk(nb_session: NetBoxApi, interfaces_data: List[Dict],
                              created_interfaces: List, updated_interfaces: List,
                              cached_vlans: Dict) -> None:
    """
    Assign tagged VLANs to trunk interfaces after they've been created/updated.
    
    Args:
        nb_session: pynetbox API session
        interfaces_data: List of dicts with interface and VLAN info
        created_interfaces: List of newly created interface objects
        updated_interfaces: List of updated interface objects
        cached_vlans: Cached VLANs dictionary
    """
    # Build a lookup for newly created interfaces by device_id and name
    created_lookup = {}
    for iface in created_interfaces:
        key = f"{iface.device.id}:{iface.name}"
        created_lookup[key] = iface
    
    # Build a lookup for updated interfaces by device_id and name
    updated_lookup = {}
    for iface in updated_interfaces:
        key = f"{iface.device.id}:{iface.name}"
        updated_lookup[key] = iface
    
    vlan_assignment_count = 0
    
    for data in interfaces_data:
        if not data.get('is_trunk') or not data.get('tagged_vlans'):
            continue
        
        # Get the interface object
        interface = data.get('interface')
        device = data['device']
        
        if not interface:
            # This was a newly created interface, look it up
            interface_name = data.get('interface_name')
            if device and interface_name:
                key = f"{device.id}:{interface_name}"
                interface = created_lookup.get(key)
        else:
            # This was an updated interface - get the refreshed version
            key = f"{device.id}:{interface.name}"
            # Try to get updated version, fallback to the one we have
            interface = updated_lookup.get(key, interface)
            
            # CRITICAL: If we're converting from access to trunk, need to refresh the object
            # to ensure mode change has been applied
            if interface.mode != 'tagged':
                try:
                    # Refresh the interface object from NetBox
                    interface = nb_session.dcim.interfaces.get(interface.id)
                    logger.debug(f"Refreshed interface {interface.name} on {device.name}, mode is now: {interface.mode}")
                except Exception as e:
                    logger.warning(f"Could not refresh interface {interface.name}: {e}")
        
        if not interface:
            logger.warning(f"Could not find interface object for VLAN assignment")
            continue
        
        tagged_vlans_list = data['tagged_vlans']
        
        # Get VLAN objects
        vlan_objects = []
        for vlan_entry in tagged_vlans_list:
            vlan_id = vlan_entry.get('vlan_id')
            vlan_name = vlan_entry.get('name')
            
            vlan_obj = _get_vlan_object(nb_session, device, vlan_id, vlan_name, cached_vlans)
            if vlan_obj:
                vlan_objects.append(vlan_obj.id)
            else:
                logger.warning(f"Could not find VLAN {vlan_name} (vid: {vlan_id}) for interface {interface.name} on {device.name}")
        
        if vlan_objects:
            try:
                # IMPORTANT: Clear any existing tagged VLANs first, then set new ones
                # This ensures we don't have leftover VLANs from previous configuration
                interface.tagged_vlans = vlan_objects
                interface.save()
                vlan_assignment_count += 1
                logger.info(f"Assigned {len(vlan_objects)} tagged VLANs to {interface.name} on {device.name}")
            except Exception as e:
                logger.error(f"Error assigning tagged VLANs to {interface.name} on {device.name}: {e}", exc_info=True)
    
    if vlan_assignment_count > 0:
        logger.info(f"Total trunk interfaces configured: {vlan_assignment_count}")
        logger.warning(f"Could not find VLAN {vlan_name} (ID: {vlan_id}) for interface {interface.name} on {device.name}")
        
        if vlan_objects:
            try:
                # Set tagged VLANs
                interface.tagged_vlans = vlan_objects
                interface.save()
                logger.info(f"Assigned {len(vlan_objects)} tagged VLANs to {interface.name} on {device.name}")
            except Exception as e:
                logger.error(f"Error assigning tagged VLANs to {interface.name} on {device.name}: {e}", exc_info=True)


# Main execution function for standalone testing
if __name__ == "__main__":
    from pynetbox_functions import _main
    
    _main(
        description="Manage device interfaces in NetBox (create, update, delete with VLAN assignments)",
        #function=interfaces
        function=delete_device_interfaces
    )