#!/usr/bin/env python3

'''
Synchronize device interfaces on a NetBox platform using `pynetbox` library
Main function, to import:

- interfaces(nb_session, data):
    - nb_session - pynetbox API session
    - data - data (yaml format)
'''

import pynetbox, logging

from typing import Dict, List, Set
from pynetbox.core.api import Api as NetBoxApi

from pynetbox_functions import _cache_devices, _bulk_create, _bulk_update
from pynetbox_functions import _delete_netbox_obj, _get_device

# Get logging
logger = logging.getLogger(__name__)

def collect_stack_interfaces(intf_name: str, intf_obj: object,
    stack_numbers: Set[str], interface_list: List[Dict[str, str]]) -> List:
    """
    Return a list of interface objects if given interface name 
    exist as a stacked interface in a switch stack

    Args:
        intf_name: Default interface name
        intf_obj: NetBox interface object
        stack_numbers: Lost of stacks members numbers
        interface_list: List of interfaces dictionaries

    Return:
        A list of interface objects if they exist in the given switch stack
    """

    collected_interfaces = []

    for stack_num in stack_numbers:
        stacked_equivalent = f"{stack_num}/{intf_name}"
        if stacked_equivalent in [item.get('interface') for item in interface_list]:
            # Mark for deletion
            collected_interfaces.append(intf_obj)
    return collected_interfaces

def interfaces(nb_session: NetBoxApi, data: Dict[str, List[str]]) -> None:
    """
    Create or update interfaces in NetBox based on YAML data.

    Args:
        nb_session: pynetbox API session
        data: Dictionary containing 'device_interfaces' and 'tagged_vlans' lists

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

    # Collect VLANs from `tagged_vlans` section
    tagged_vlans_data = data.get('tagged_vlans', [])
    for item in tagged_vlans_data:
        for vlan in item.get('tagged_vlans', []):
            vlan_key = (vlan.get('vlan_id', ''), vlan.get('name', ''))
            unique_vlans.add(vlan_key)

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

    #Build a lookup for tagged VLANs by hostname and interface
    tagged_vlans_lookup = {}
    for item in tagged_vlans_data:
        hostname = item.get('hostname', None)
        interface = item.get('interface', None)
        if hostname and interface:
            key = (hostname, interface)
            tagged_vlans_lookup[key] = item.get('tagged_vlans', [])

    nb_interfaces = nb_session.dcim.interfaces

    # Cache all existing interfaces for requested devices 
    cached_interfaces = {}
    cached_modules = {} # Cache modules for each device

    for hostname, device in cached_devices.items():
        try:
            existing_interfaces = {
                intf.name: intf
                for intf in nb_interfaces.filter(device_id = device.id)
            }
            cached_interfaces[hostname] = existing_interfaces

            # Fetch device modules and their interfaces
            modules = list(nb_session.dcim.modules.filter(device_id = device.id))
            cached_modules[hostname] = {}

            for module in modules:
                module_interfaces = {
                    intf.name: intf 
                    for intf in nb_interfaces.filter(module_id = module.id)
                }
                cached_modules[hostname][module.id] = {
                    'module': module,
                    'interfaces': module_interfaces
                }
                # Also add module interfaces to the main interface cache for lookup
                existing_interfaces.update(module_interfaces)

        except Exception as e:
            logger.error(f"Error fetching interfaces/modules for {hostname}: {e}")
            cached_interfaces[hostname] = {}
            cached_modules[hostname] = {}

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
                # Skip it it's a module interface (will be handled separately)
                if hasattr(intf_obj, 'module') and intf_obj.module:
                    continue

                # Check if it's a numeric-only interface (e.g., '1', '48')
                if intf_name.isdigit():
                    # Check if there is a corresponding stacked interface for any stack and add it 
                    interfaces_to_delete += collect_stack_interfaces(intf_name, intf_obj, stack_numbers, interface_list)

            # Handle module interfaces - delete non-stacked module interfaces
            for module_id, module_data in cached_modules.get(hostname, {}).items():
                module_interfaces = module_data['interfaces']

                for intf_name, intf_obj in module_interfaces.items():
                    # Check if it's a non-stacked module interface (e.g., "A1", "A2")
                    if '/' not in intf_name:
                        # Append them to the delete list
                        interfaces_to_delete += collect_stack_interfaces(
                            intf_name, intf_obj, stack_numbers, interface_list)

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

            # Determine if this is a module interface (e.g. 1/A1, 2/A2)
            # Module interfaces have non-numeric port numbers
            is_module_interface = False
            module_id = None

            if '/' in interface_name:
                stack_num, port_num = interface_name.split('/', 1)
                # If port number is not numeric, it's likely a module interface
                if not port_num.isdigit():
                    is_module_interface = True
                    # Try to find the module for this stack member
                    # Look for modules on this device
                    modules_list = list(cached_modules.get(hostname, {}).items())
                    if modules_list:
                        # Use the first available module
                        # TODO: Match by module position or other attributes
                        module_id = modules_list[0][0]
                        logger.debug(f"Assigning module interface {interface_name} to module ID {module_id}")
                    else:
                        logger.warning(
                            f"No module found for module interface {interface_name} on {hostname}. "
                            "It will be created as a device interface instead."
                        )

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

            # Set device or module
            if is_module_interface and module_id:
                payload['module'] = module_id

            # Add optional fields
            if 'poe_mode' in item:
                payload['poe_mode'] = item.get('poe_mode')
            if 'poe_type' in item:
                payload['poe_type'] = item.get('poe_type')

            # Handle VLAN assignment based on trunk mode
            is_trunk = item.get('is_trunk', False)

            # Check if there are additional tagged VLANs from the tagged_vlans section
            lookup_key = (hostname, interface_name)
            additional_tagged_vlans = tagged_vlans_lookup.get(lookup_key, [])

            if is_trunk:
                payload['mode'] = 'tagged' 
                tagged_vlans_ids = []

                # Add the primary VLAN if provided
                if vlan_id:
                    tagged_vlans_ids.append(vlan_id)

                # Add additional tagged VLANs from the tagged_vlans section
                for vlan_info in additional_tagged_vlans:
                    vlan_id = vlan_info.get('vlan_id', '')
                    vlan_name = vlan_info.get('name', '')
                    vlan_key = (vlan_id, vlan_name)
                    additional_vlan_id = cached_vlans.get(vlan_key)
                    if not additional_vlan_id:
                        additional_vlan_id = cached_vlans.get(vlan_id, '')

                    if additional_vlan_id and additional_vlan_id not in tagged_vlans_ids:
                        tagged_vlans_ids.append(additional_vlan_id)
                    elif not additional_vlan_id:
                        logger.warning(
                            f"Tagged VLAN {vlan_id} ({vlan_name}) "
                            f"not found for interface {interface_name} on {hostname}"
                        )
                payload['tagged_vlans'] = tagged_vlans_ids
            else:
                payload['mode'] = 'access' 
                if vlan_id:
                    # For access ports, VLAN goes to untagged_vlan 
                    payload['untagged_vlan'] = vlan_id
                # Ensure no tagged VLANs on access ports
                payload['tagged_vlans'] = []

                # Warn if tagged VLANs were specified for an access port
                if additional_tagged_vlans:
                    logger.warning(
                        f"Interface {interface_name} on {hostname} is in access mode "
                        f"but has {len(additional_tagged_vlans)} tagged VLANs specified. "
                        "Tagged VLANs are only supported in trunk mode."
                    )

            # Update existing interface
            if existing_intf:
                # Check if it's needed to move from device to module or vice versa
                existing_is_module = hasattr(existing_intf, 'module') and existing_intf.module

                if is_module_interface and module_id and not existing_is_module:
                    # Need to delete old device/module interface and create new module/device interface
                    interfaces_to_delete.append(existing_intf)
                    interfaces_to_create.append(payload)
                    logger.info(
                        f"Will recreate interface {interface_name} on {hostname} "
                        "as module interface (was device interface)"
                    )
                elif not is_module_interface and existing_is_module:
                    # Need to delete old module interface and create new device interface
                    interfaces_to_delete.append(existing_intf)
                    interfaces_to_create.append(payload)
                    logger.info(
                        f"Will recreate interface {interface_name} on {hostname} "
                        "as device interface (was module interface)"
                    )
                else:
                    # Same type, just update
                    payload['id'] = existing_intf.id
                    interfaces_to_update.append(payload)
            else:
                # Create new interface
                interfaces_to_create.append(payload)

    # Delete obsolete non-stacked interfaces
    if interfaces_to_delete:
        nr_deleted = 0
        for intf_obj in interfaces_to_delete:
            if _delete_netbox_obj(intf_obj):
                nr_deleted += 1
        logger.info(f"Deleted {nr_deleted} obsolete non-stacked interface(s)")

    # Bulk create new interfaces
    if interfaces_to_create:
        logger.info(f"Bulk create {len(interfaces_to_create)} interfaces")
        _bulk_create(
            nb_interfaces,
            interfaces_to_create,
            "interfaces(s)"
        )

    # Bulk update existing interfaces
    if interfaces_to_update:
        logger.info(f"Bulk update {len(interfaces_to_update)} interfaces")
        _bulk_update(
            nb_interfaces,
            interfaces_to_update,
            "interfaces(s)"
        )

    logger.info(f"Finished processing {len(device_interfaces)} interface entries")

    # Debug section
    #logger.debug(f"\n==++ Interfaces to delete: {interfaces_to_delete}\n")
    #logger.debug(f"\n==++ Interfaces to update: {interfaces_to_update}\n")


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

    # Build a mapping of stack members to master devices
    # For virtual chassis, stack members like rsww1000sp-2 should map to master rsww1000sp
    device_mapping = {} # maps hostname -> actual device to use
    master_devices = {} # maps master hostname -> device object

    for hostname in device_names:
        device = cached_devices.get(hostname)

        if device:
            # Device exists as-is
            device_mapping[hostname] = device
            master_devices[hostname] = device
        else:
            # Device not found - might to be a stack member, try to find master
            # Extract potential master name (e.g., rgww1000sp-1 -> rgww1000sp)
            if '-' in hostname:
                potential_master = hostname.rsplit('-', 1)[0]
                master_device = cached_devices.get(potential_master)

                if not master_device:
                    # Try fetching the master device
                    master_device = _get_device(nb_session, potential_master)

                if master_device:
                    logger.info(
                        f"Device {hostname} not found, using master device {potential_master} "
                        f"(virtual chassis/stack configuration)"
                    )
                    device_mapping[hostname] = master_device
                    master_devices[potential_master] = master_device
                    # Cache for future lookups
                    cached_devices[potential_master] = master_device
                else:
                    logger.warning(f"Neither {hostname} nor master {potential_master} found in NetBox")
            else:
                logger.warning(f"Device {hostname} not found in NetBox")

    # Cache all existing interfaces at once
    cached_interfaces, cached_lags = {}, {}
    nr_interfaces, nr_lags = 0, 0

    nb_interfaces = nb_session.dcim.interfaces

    for hostname, device in master_devices.items():
        try:
            # Fetch all interfaces - convert to list to ensure full iteration
            all_intf = list(nb_interfaces.filter(device_id = device.id))
                        # Also check for virtual chassis members and fetch their interfaces
            # In a stack, interfaces from all members should be accessible from master
            if hasattr(device, 'virtual_chassis') and device.virtual_chassis:
                # Get all devices in the virtual chassis
                vc_id = device.virtual_chassis.id
                vc_members = nb_session.dcim.devices.filter(virtual_chassis_id = vc_id)

                for member in vc_members:
                    if member.id != device.id: # Don't fetch the master again
                        member_intfs = list(nb_interfaces.filter(device_id = member.id))
                        all_intf.extend(member_intfs)
                        logger.info(f"Added {len(member_intfs)} interfaces from VC member {member.name}")

            d_interfaces = {intf.name: intf for intf in all_intf}
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

            # Debug: show interface count per stack
            stack_counts = {}
            for intf_name in d_interfaces.keys():
                if '/' in intf_name:
                    stack_num = intf_name.split('/')[0]
                    stack_counts[stack_num] = stack_counts.get(stack_num, 0) + 1
            if stack_counts:
                logger.info(f"Interface distribution for {hostname}: {stack_counts}")
        except Exception as e:
            logger.error(f"Error fetching interfaces for {hostname}: {e}")
            cached_interfaces[hostname] = {}
            cached_lags[hostname] = {}

    logger.info(f"Cached {nr_interfaces} total interfaces including {nr_lags} LAGs")

    # Group by actual device (master) and trunk
    trunks_by_device = {}
    for item in trunk_interfaces:
        hostname = item.get('hostname')
        trunk_name = item.get('trunk_name')

        # Get the actual device (master in virtual chassis)
        actual_device = device_mapping.get(hostname)
        if not actual_device:
            continue

        # Use master device name as key
        master_hostname = actual_device.name

        if master_hostname not in trunks_by_device:
            trunks_by_device[master_hostname] = {}
        if trunk_name not in trunks_by_device.get(master_hostname):
            trunks_by_device[master_hostname][trunk_name] = []

        trunks_by_device[master_hostname][trunk_name].append(item.get('interface'))

    # Collect interfaces to bulk process   
    lags_to_create = []
    interfaces_to_update = []

    # Process each device
    for hostname, trunks_dict in trunks_by_device.items():
        device = master_devices.get(hostname)
        if not device:
            logger.warning(f"Device {hostname} not found in NetBox, skipping trunks")
            continue

        all_interfaces = cached_interfaces.get(hostname, {})
        existing_lags = cached_lags.get(hostname, {})

        for trunk_name, member_interfaces in trunks_dict.items():
            lag = existing_lags.get(trunk_name)

            # Create LAG if it doesn't exist
            if not lag:
                lag_payload = {
                    'device': device.id,
                    'name': trunk_name,
                    'type': 'lag',
                    'description': f"Link Aggregation Group {trunk_name}"
                }
                lags_to_create.append(lag_payload)
                logger.info(f"Will create LAG {trunk_name} on {hostname}")

            # Process member interfaces
            for member_name in member_interfaces:
                member_name_clean = member_name.strip()
                member_intf = all_interfaces.get(member_name_clean)

                if not member_intf:
                    # Debug: show what interfaces we do have
                    available_interfaces = sorted([name for name in all_interfaces.keys() if '/' in name])
                    logger.warning(
                        f"Member interfaces {member_name} not found on {hostname}, "
                        f"create if first before adding in {trunk_name}. "
                        f"Available stacked interfaces: {available_interfaces}"
                    )
                    continue
                
                # Check if already in the correct LAG
                current_lag = getattr(member_intf, 'lag', None)
                if current_lag and hasattr(current_lag, 'name') and current_lag.name == trunk_name:
                    logger.debug(f"Interface {member_name} already in {trunk_name}")
                    continue
                
                # Will update after LAG creation
                interfaces_to_update.append({
                    'interface_id': member_intf.id,
                    'trunk_name': trunk_name,
                    'member_name': member_name,
                    'hostname': hostname
                })
    # Bulk create LAGs across all devices
    if lags_to_create:
        created_lags = _bulk_create(
            nb_interfaces,
            lags_to_create,
            "LAG interface(s)"
        )

        # Refresh LAG cache for this device after creation
        for hostname, device in master_devices.items():
            try:
                all_intf = list(nb_interfaces.filter(device_id = device.id))
                d_interfaces = {intf.name: intf for intf in all_intf}
                cached_lags[hostname] = {
                    name: intf 
                    for name, intf in all_interfaces.items()
                    if (hasattr(intf.type, 'value') and intf.type.value == 'lag') or 
                    (hasattr(intf.type, 'label') and 'LAG' in intf.type.label)
                }
            except Exception as e:
                logger.error(f"Error refreshing LAGs for {hostname}: {e}")
        
    # Update member interfaces to join LAGs
    member_updates = []
    for update_info in interfaces_to_update:
        hostname = update_info['hostname']
        trunk_name = update_info.get('trunk_name')

        lag = cached_lags.get(hostname, {}).get(trunk_name)
        if not lag:
            logger.error(f"LAG {trunk_name} not found on {hostname} after creation attempt")
            continue
        
        member_updates.append({
            'id': update_info.get('interface_id'),
            'lag': lag.id
        })

    if member_updates:
        _bulk_update(
            nb_interfaces,
            member_updates,
            "trunk member interface(s)"
        )
    
    logger.info(f"Finished processing {len(trunk_interfaces)} trunk entries")

if __name__ == '__main__':
    from pynetbox_functions import _main, _debug
    _main("Synchronizing device interfaces", interfaces)
    _main("Synchronizing device interfaces", trunks)
    #_debug(interfaces)
    #_debug(trunks)