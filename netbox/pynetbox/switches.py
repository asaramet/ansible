#!/usr/bin/env python3

'''
Add or update switches on a NetBox platform using `pynetbox` library

Main function to import:
    switches(nb_session, data):
        - nb_session: pynetbox API session
        - data: dictionary containing 'devices' list (YAML format)

Supports:
    - Creating new switches
    - Updating existing switches with changed attributes
    - Virtual chassis configuration (vc_position, vc_priority, virtual_chassis)
    - Bulk operations with chunking and error handling
'''

import logging
from typing import Optional, Tuple, Any

from pynetbox.core.api import Api as NetBoxApi

from pynetbox_functions import (
    _bulk_create,
    _bulk_update, 
    _cache_devices,
    _resolve_tags,
    _resolve_or_create
)

# Get logger
logger = logging.getLogger(__name__)


def _resolve_dependencies(nb_session: NetBoxApi, switch_dict: dict) -> Optional[dict[str, int]]:
    """
    Resolve all NetBox dependencies for a switch.
    
    Args:
        nb_session: pynetbox API session
        switch_dict: Switch data from YAML
        
    Returns:
        Dictionary with resolved IDs: {role, device_type, site, location (optional)}
        None if any required dependency is missing
    """
    dependencies = {}
    switch_name = switch_dict.get('name', 'unknown')
    
    try:
        # Device Role (required)
        role_slug = switch_dict.get('device_role')
        if not role_slug:
            logger.warning(f"{switch_name}: Missing 'device_role'")
            return None
            
        device_role = nb_session.dcim.device_roles.get(slug=role_slug)
        if not device_role:
            logger.warning(f"{switch_name}: Device role '{role_slug}' not found")
            return None
        dependencies['role'] = device_role.id
        
        # Device Type (required)
        type_slug = switch_dict.get('device_type')
        if not type_slug:
            logger.warning(f"{switch_name}: Missing 'device_type'")
            return None
            
        device_type = nb_session.dcim.device_types.get(slug=type_slug)
        if not device_type:
            logger.warning(f"{switch_name}: Device type '{type_slug}' not found")
            return None
        dependencies['device_type'] = device_type.id
        
        # Site (required)
        site_slug = switch_dict.get('site')
        if not site_slug:
            logger.warning(f"{switch_name}: Missing 'site'")
            return None
            
        site = nb_session.dcim.sites.get(slug=site_slug)
        if not site:
            logger.warning(f"{switch_name}: Site '{site_slug}' not found")
            return None
        dependencies['site'] = site.id
        
        # Location (optional)
        location_slug = switch_dict.get('location')
        if location_slug:
            location = nb_session.dcim.locations.get(slug=location_slug)
            if location:
                dependencies['location'] = location.id
            else:
                logger.debug(f"{switch_name}: Location '{location_slug}' not found, skipping")
        
        return dependencies
        
    except Exception as e:
        logger.error(f"{switch_name}: Error resolving dependencies: {e}", exc_info=True)
        return None


def process_chassis(nb_session: NetBoxApi, chassis_data: list[dict]) -> dict[str, int]:
    """
    Process chassis section - create virtual chassis and set master devices.
    
    This should be called AFTER processing devices to ensure master devices exist.
    
    Args:
        nb_session: pynetbox API session
        chassis_data: list of chassis dictionaries with 'name' and 'master' fields
        
    Returns:
        dictionary mapping chassis name to chassis ID
    """
    if not chassis_data:
        logger.debug("No chassis data to process")
        return {}
    
    logger.info(f"Processing {len(chassis_data)} virtual chassis...")
    
    chassis_map = {}
    created_count = 0
    master_set_count = 0
    
    for chassis in chassis_data:
        vc_name = chassis.get('name')
        master_name = chassis.get('master')
        
        if not vc_name:
            logger.warning("Skipping chassis entry with missing 'name'")
            continue
        
        # Create or get virtual chassis (without master)
        vc_id = _resolve_or_create(
            nb_session.dcim.virtual_chassis,
            vc_name,
            lookup_field='name'
        )
        
        if vc_id:
            chassis_map[vc_name] = vc_id
            created_count += 1
            
            # Set master device if specified
            if master_name:
                try:
                    # Get the virtual chassis object
                    vc = nb_session.dcim.virtual_chassis.get(vc_id)
                    
                    # Check if master is already set correctly
                    if vc.master and vc.master.name == master_name:
                        logger.debug(f"VC {vc_name}: master already set to {master_name}")
                        master_set_count += 1
                        continue
                    
                    # Get the master device
                    master_device = nb_session.dcim.devices.get(name=master_name)
                    if not master_device:
                        logger.warning(f"Master device '{master_name}' not found for VC {vc_name}")
                        continue
                    
                    # Update virtual chassis with master
                    vc.master = master_device.id
                    vc.save()
                    logger.info(f"Set master for VC {vc_name}: {master_name}")
                    master_set_count += 1
                    
                except Exception as e:
                    logger.error(f"Error setting master for VC {vc_name}: {e}", exc_info=True)
        else:
            logger.error(f"Failed to create/resolve virtual chassis: {vc_name}")
    
    logger.info(
        f"Chassis processing complete: {created_count} chassis resolved, "
        f"{master_set_count} masters set"
    )
    
    return chassis_map


def _build_switch_payload(
    nb_session: NetBoxApi, 
    switch_dict: dict, 
    dependencies: dict[str, int]
) -> Optional[dict]:
    """
    Build payload for creating a new switch.
    
    Args:
        nb_session: pynetbox API session
        switch_dict: Switch data from YAML
        dependencies: Resolved dependency IDs
        
    Returns:
        Payload dictionary ready for NetBox API, or None on error
    """
    try:
        payload = {
            'name': switch_dict.get('name'),
            'status': 'active'
        }
        
        # Add serial only if present and not null
        serial = switch_dict.get('serial')
        if serial:  # This handles None, empty string, null
            payload['serial'] = serial
        
        # Add dependencies
        payload.update(dependencies)
        
        # Handle tags
        tag_ids = _resolve_tags(nb_session, switch_dict.get('tags'))
        if tag_ids:
            payload['tags'] = tag_ids
        
        # Handle virtual chassis fields
        vc_name = switch_dict.get('virtual_chassis')
        if vc_name:
            vc_id = _resolve_or_create(
                nb_session.dcim.virtual_chassis,
                vc_name,
                lookup_field='name'
            )
            
            if vc_id:
                payload['virtual_chassis'] = vc_id
                
                # Add vc_position if present
                if 'vc_position' in switch_dict:
                    payload['vc_position'] = switch_dict['vc_position']
                
                # Add vc_priority if present
                if 'vc_priority' in switch_dict:
                    payload['vc_priority'] = switch_dict['vc_priority']
            else:
                logger.warning(
                    f"{switch_dict.get('name')}: Failed to resolve virtual chassis '{vc_name}'"
                )
        return payload
        
    except Exception as e:
        logger.error(
            f"{switch_dict.get('name', 'unknown')}: Error building payload: {e}", 
            exc_info=True
        )
        return None


def _build_update_payload(
    nb_session: NetBoxApi,
    switch_dict: dict,
    existing_switch: object,
    dependencies: dict[str, int]
) -> Optional[dict]:
    """
    Build payload for updating an existing switch (only changed fields).
    
    Args:
        nb_session: pynetbox API session
        switch_dict: Switch data from YAML
        existing_switch: Existing NetBox device object
        dependencies: Resolved dependency IDs
        
    Returns:
        Update payload with only changed fields, or None if no changes needed
    """
        #logger.debug(f"\n\u2317 Switch Dict: {switch_dict}\n\u2318 New: {new_inventory}\n\u2319 Old: {old_inventory}")
    try:
        changes = {'id': existing_switch.id}
        has_changes = False
        
        # Check serial number - only update if new serial is not null/empty
        new_serial = switch_dict.get('serial')
        old_serial = getattr(existing_switch, 'serial', '') or ''
        
        # Only compare and update if new serial is provided (not None, not empty)
        if new_serial:
            if new_serial != old_serial:
                changes['serial'] = new_serial
                has_changes = True
                logger.debug(f"{existing_switch.name}: Serial changed: '{old_serial}' -> '{new_serial}'")
        # If new_serial is None/empty, skip serial update (preserve existing)

        # Check inventory number (asset tag)
        new_inventory = (switch_dict.get('asset_tag') or '').strip()
        old_inventory = str(getattr(existing_switch, 'asset_tag', '') or '').strip()

        if new_inventory and new_inventory != old_inventory:
            changes['asset_tag'] = new_inventory
            has_changes = True
            logger.debug(f"{existing_switch.name}: Asset tag changed: '{old_inventory}' -> '{new_inventory}'")

        # Check device role
        if dependencies.get('role') != getattr(existing_switch.role, 'id', None):
            changes['role'] = dependencies['role']
            has_changes = True
        
        # Check device type
        if dependencies.get('device_type') != getattr(existing_switch.device_type, 'id', None):
            changes['device_type'] = dependencies['device_type']
            has_changes = True
        
        # Check site
        if dependencies.get('site') != getattr(existing_switch.site, 'id', None):
            changes['site'] = dependencies['site']
            has_changes = True
        
        # Check location
        new_location = dependencies.get('location')
        old_location = getattr(existing_switch.location, 'id', None) if existing_switch.location else None
        if new_location != old_location:
            changes['location'] = new_location
            has_changes = True
        
        # Check tags
        tag_ids = _resolve_tags(nb_session, switch_dict.get('tags'))
        existing_tag_ids = sorted([tag.id for tag in existing_switch.tags]) if existing_switch.tags else []
        if sorted(tag_ids) != existing_tag_ids:
            changes['tags'] = tag_ids
            has_changes = True
        
        # Check virtual chassis configuration
        vc_name = switch_dict.get('virtual_chassis')
        if vc_name:
            
            vc_id = _resolve_or_create(
                nb_session.dcim.virtual_chassis,
                vc_name,
                lookup_field='name'
            )
            
            if vc_id:
                # Check virtual_chassis
                old_vc_id = getattr(existing_switch.virtual_chassis, 'id', None) if existing_switch.virtual_chassis else None
                if vc_id != old_vc_id:
                    changes['virtual_chassis'] = vc_id
                    has_changes = True
                
                # Check vc_position
                if 'vc_position' in switch_dict:
                    new_vc_position = switch_dict['vc_position']
                    old_vc_position = getattr(existing_switch, 'vc_position', None)
                    if new_vc_position != old_vc_position:
                        changes['vc_position'] = new_vc_position
                        has_changes = True
                
                # Check vc_priority
                if 'vc_priority' in switch_dict:
                    new_vc_priority = switch_dict['vc_priority']
                    old_vc_priority = getattr(existing_switch, 'vc_priority', None)
                    if new_vc_priority != old_vc_priority:
                        changes['vc_priority'] = new_vc_priority
                        has_changes = True
        
        return changes if has_changes else None
        
    except Exception as e:
        logger.error(
            f"{switch_dict.get('name', 'unknown')}: Error building update payload: {e}",
            exc_info=True
        )
        return None


def _handle_serial_conflict(
    nb_session: NetBoxApi,
    switch_dict: dict,
    existing_switch: object,
    dependencies: dict[str, int]
) -> Optional[dict]:
    """
    Handle serial number conflicts by renaming existing device.
    
    Simplified logic:
    1. If device has different serial than new data → rename existing to old serial
    2. Skip creating new device (will be handled separately)
    3. Log info that device was skipped for creation
    
    Args:
        nb_session: pynetbox API session
        switch_dict: Switch data from YAML
        existing_switch: Existing NetBox device object
        dependencies: Resolved dependency IDs
        
    Returns:
        Update payload for existing device, or None if no conflict
    """
    # Get serial numbers
    new_serial = switch_dict.get('serial')
    old_serial = getattr(existing_switch, 'serial', '') or ''
    
    # Get asset tags
    new_asset_tag = (switch_dict.get('asset_tag') or '').strip()
    old_asset_tag = str(getattr(existing_switch, 'asset_tag', '') or '').strip()
    
    # Case 1: Serial conflict - different serial numbers
    if new_serial and old_serial and new_serial != old_serial:
        logger.info(f"Serial conflict detected for {existing_switch.name}: "
                   f"existing serial '{old_serial}' vs new serial '{new_serial}'")
        
        # Rename existing device to its current serial number
        update_payload = {
            'id': existing_switch.id,
            'name': old_serial
        }
        
        # Update asset tag
        if old_asset_tag:
            update_payload['asset_tag'] = None
            update_payload['name'] = f"{update_payload['name']} ({old_asset_tag})"
        # Keep other attributes the same except name
        if old_serial:
            update_payload['serial'] = old_serial
        
        # Log that we're skipping creation of new device
        logger.info(f"Skipped creating new device '{switch_dict['name']}' with serial '{new_serial}' - "
                   f"it will be created separately later")
        
        return update_payload
    
    # Case 2: No existing serial but new serial provided - update existing device
    elif new_serial and not old_serial:
        logger.info(f"Adding serial to device {existing_switch.name}: '{new_serial}'")
        # This will be handled by normal update logic, no conflict
        return None
    
    # Case 3: No new serial but existing serial - keep existing
    elif not new_serial and old_serial:
        logger.info(f"Keeping existing serial for {existing_switch.name}: '{old_serial}'")
        # This will be handled by normal update logic, no conflict
        return None
    
    # Case 4: No serials at all - nothing to do
    else:
        return None


def _categorize_switches(
    nb_session: NetBoxApi,
    switches_data: list[dict]
) -> Tuple[list[dict], list[dict], int]:
    """
    Categorize switches into: to_create, to_update, and error_count.
    
    Args:
        nb_session: pynetbox API session
        switches_data: list of switch dictionaries from YAML
        
    Returns:
        Tuple of (create_payloads, update_payloads, error_count)
    """
    # Extract all switch names for efficient caching
    switch_names = [s.get('name') for s in switches_data if s.get('name')]
    
    # Cache existing devices in bulk
    logger.info(f"Caching {len(switch_names)} devices...")
    existing_devices = _cache_devices(nb_session, switch_names)
    logger.info(f"Found {len(existing_devices)} existing devices in cache")
    
    create_payloads = []
    update_payloads = []
    error_count = 0
    skipped_count = 0
    
    for switch_dict in switches_data:
        switch_name = switch_dict.get('name')
        if not switch_name:
            logger.warning("Skipping switch with missing 'name' field")
            error_count += 1
            continue
        
        # Resolve dependencies
        dependencies = _resolve_dependencies(nb_session, switch_dict)
        if not dependencies:
            error_count += 1
            continue
        logger.debug(f"-> Switch dependencies: {dependencies}")
        
        # Check if switch exists
        existing_switch = existing_devices.get(switch_name)
        
        if existing_switch:
            # Check for serial conflicts first
            conflict_update = _handle_serial_conflict(
                nb_session, switch_dict, existing_switch, dependencies
            )
            
            if conflict_update:
                # We have a serial conflict - rename existing device
                update_payloads.append(conflict_update)
                logger.info(f"Resolved serial conflict for {switch_name}: "
                          f"renamed existing device to '{conflict_update['name']}'")
                continue
            
            # No conflict, proceed with normal update logic
            update_payload = _build_update_payload(
                nb_session, switch_dict, existing_switch, dependencies
            )
            if update_payload:
                update_payloads.append(update_payload)
            else:
                skipped_count += 1
                logger.debug(f"{switch_name}: No changes detected, skipping")
        else:
            # Build create payload
            create_payload = _build_switch_payload(nb_session, switch_dict, dependencies)
            if create_payload:
                create_payloads.append(create_payload)
            else:
                error_count += 1
    
    logger.info(
        f"Categorization complete: {len(create_payloads)} to create, "
        f"{len(update_payloads)} to update, {skipped_count} unchanged, {error_count} errors"
    )

    if create_payloads:
        logger.debug(f"✓ Payloads to create:")
        index = 1
        for payload in create_payloads:
            logger.debug(f"{index}: {payload}")
            index = index + 1 
    
    if update_payloads:
        logger.debug(f"• Payloads to update:")
        index = 1
        for payload in update_payloads:
            logger.debug(f"{index}: {payload}")
            index = index + 1 
    
    return create_payloads, update_payloads, error_count


def switches(nb_session: NetBoxApi, data: dict) -> list:
    """
    Add or update switches on NetBox server from YAML data.
    
    This function:
    - Creates/updates switches first (so they exist)
    - Then processes chassis section (sets master devices)
    - Handles virtual chassis configuration
    - Uses bulk operations with automatic chunking
    
    Processing order is important:
    1. Create/update switches → devices exist in NetBox
    2. Process chassis → can now set master devices
    3. Optionally update switches again if chassis affected them
    
    Args:
        nb_session: pynetbox API session
        data: dictionary containing:
            - 'devices': list of switch configurations
            - 'chassis' (optional): list of virtual chassis definitions
        
    Returns:
        List of created and updated device objects
    """
    switches_data = data.get('devices', [])
    
    if not switches_data:
        logger.warning("No devices found in data")
        return []
    
    logger.info(f"Processing {len(switches_data)} switch(es)...")
    
    # Step 1: Process devices (create/update switches)
    # This ensures all switches exist before chassis processing
    create_payloads, update_payloads, error_count = _categorize_switches(
        nb_session, switches_data
    )
    
    nb_devices = nb_session.dcim.devices
    results = []
    
    # Create new switches
    if create_payloads:
        logger.info(f"Creating {len(create_payloads)} new switch(es)...")
        created_switches = _bulk_create(nb_devices, create_payloads, 'switch')
        results.extend(created_switches)
        
        if created_switches:
            logger.info(f"Successfully created {len(created_switches)} switch(es)")
            for switch in created_switches:
                logger.info(f"  Created: {switch.name}")
    
    # Update existing switches
    if update_payloads:
        logger.info(f"Updating {len(update_payloads)} existing switch(es)...")
        updated_switches = _bulk_update(nb_devices, update_payloads, 'switch')
        results.extend(updated_switches)
        
        if updated_switches:
            logger.info(f"Successfully updated {len(updated_switches)} switch(es)")
            for switch in updated_switches:
                logger.info(f"  Updated: {switch.name}")
    
    # Step 2: Process chassis (now that switches exist)
    chassis_data = data.get('chassis', [])
    if chassis_data:
        logger.info("Processing chassis section...")
        chassis_map = process_chassis(nb_session, chassis_data)
        logger.info(f"Virtual chassis ready: {len(chassis_map)} chassis processed")
    
    # Summary
    logger.info(
        f"Operation complete: {len(create_payloads)} created, "
        f"{len(update_payloads)} updated, {error_count} errors"
    )
    
    return results


if __name__ == '__main__':
    from pynetbox_functions import _main
    _main("Add or update switches on a NetBox server", switches)

    #from pynetbox_functions import _debug
    #_debug(switches)
    #_debug(_categorize_switches, "devices")

