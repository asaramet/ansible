#!/usr/bin/env python3

"""
Module management functions for NetBox automation.

This module provides functions to manage switch modules (module bays) in NetBox,
including deletion of old modules and creation of new ones based on YAML data.
"""

from typing import Dict, List, Tuple
from pynetbox.core.api import Api as NetBoxApi
import logging

from pynetbox_functions import (
    _cache_devices,
    _bulk_create,
    _bulk_update,
    _delete_netbox_obj
)

logger = logging.getLogger(__name__)

def modules(nb_session: NetBoxApi, data: Dict[str, List[Dict]]) -> List[Dict[str, str | int]]:
    """
    Update switch modules on a NetBox server from YAML data.
    
    This function:
    1. Deletes old-style module bays (e.g., "Module A", "Module B")
    2. Checks for existing module bays with the new naming scheme
    3. If duplicates exist, keeps one and deletes the rest
    4. Updates existing module bay or creates new one if it doesn't exist
    
    Args:
        nb_session: pynetbox API session
        data: Dictionary containing 'modules' list with module configurations
        
    Returns:
        List of payloads processed (created or updated)
        
    Example YAML structure:
        modules:
          - device: swgs0001sp-1
            module_bay: A
            name: Module A
            new_position: 1/A
            type: Aruba 2920 2-Port 10GbE SFP+ Module
    """
    if 'modules' not in data:
        logger.warning("No 'modules' key found in data")
        return []
    
    modules_data = data['modules']
    
    if not modules_data:
        logger.info("No modules to process")
        return []
    
    logger.info(f"Processing {len(modules_data)} module configuration(s)")
    
    # Step 1: Cache all devices mentioned in the module data
    device_names = _extract_unique_device_names(modules_data)
    devices_cache = _cache_devices(nb_session, device_names)
    
    if not devices_cache:
        logger.error("No devices found in NetBox. Cannot proceed with module updates.")
        return []
    
    # Step 2: Delete old-style module bays (e.g., "Module A", "Module B")
    old_modules_to_delete = _collect_old_style_modules_to_delete(
        nb_session, modules_data, devices_cache
    )
    old_deleted_count = _bulk_delete_modules(old_modules_to_delete)
    
    # Step 3: Process new-style module bays (create/update/handle duplicates)
    create_payloads, update_payloads, duplicate_deleted_count = _process_module_operations(
        nb_session, modules_data, devices_cache
    )
    
    # Step 4: Create new module bays in bulk
    created_count = 0
    if create_payloads:
        created_modules = _bulk_create(
            nb_session.dcim.module_bays, 
            create_payloads, 
            "module bay"
        )
        created_count = len(created_modules)
    
    # Step 5: Update existing module bays in bulk
    updated_count = 0
    if update_payloads:
        updated_modules = _bulk_update(
            nb_session.dcim.module_bays,
            update_payloads,
            "module bay"
        )
        updated_count = len(updated_modules)
    
    total_deleted = old_deleted_count + duplicate_deleted_count
    logger.info(
        f"Module processing complete: {total_deleted} deleted "
        f"({old_deleted_count} old-style, {duplicate_deleted_count} duplicates), "
        f"{created_count} created, {updated_count} updated"
    )
    
    return create_payloads + update_payloads


def _extract_unique_device_names(modules_data: List[Dict]) -> List[str]:
    """
    Extract unique device names from modules data.
    
    Args:
        modules_data: List of module configuration dictionaries
        
    Returns:
        List of unique device names
    """
    device_names = set()
    
    for module in modules_data:
        device_name = module.get('device')
        if device_name:
            device_names.add(device_name)
        else:
            logger.warning(f"Module configuration missing 'device' field: {module}")
    
    device_list = list(device_names)
    logger.debug(f"Extracted {len(device_list)} unique device name(s)")
    
    return device_list


def _bulk_delete_modules(modules: List[object]) -> int:
    """
    Delete module bays using the standard _delete_netbox_obj function.
    
    Args:
        modules: List of module bay objects to delete
        
    Returns:
        Number of successfully deleted module bays
    """
    if not modules:
        return 0
    
    deleted_count = 0
    
    logger.info(f"Attempting to delete {len(modules)} module bay(s)...")
    
    for module in modules:
        if _delete_netbox_obj(module):
            deleted_count += 1
    
    logger.info(f"Successfully deleted {deleted_count}/{len(modules)} module bay(s)")
    
    return deleted_count


def _collect_old_style_modules_to_delete(
    nb_session: NetBoxApi,
    modules_data: List[Dict],
    devices_cache: Dict[str, object]
) -> List[object]:
    """
    Collect old-style module bays (like "Module A", "Module B") that need to be deleted.
    
    These are the default module names that should be replaced with the new naming scheme
    (device-bay format like "swgs0001sp-1-A").
    
    Args:
        nb_session: pynetbox API session
        modules_data: List of module configuration dictionaries
        devices_cache: Dictionary mapping device names to device objects
        
    Returns:
        List of old-style module bay objects to delete
    """
    modules_to_delete = []
    
    # Build a mapping of device_name -> list of old module names to delete
    device_module_map = {}
    
    for module_config in modules_data:
        device_name = module_config.get('device')
        old_module_name = module_config.get('name')  # e.g., "Module A"
        
        if not device_name or not old_module_name:
            continue
        
        if device_name not in device_module_map:
            device_module_map[device_name] = set()
        
        device_module_map[device_name].add(old_module_name)
    
    # Query for existing module bays with old-style names
    logger.info(f"Checking for old-style module bays to delete on {len(device_module_map)} device(s)")
    
    for device_name, old_module_names in device_module_map.items():
        device_obj = devices_cache.get(device_name)
        
        if not device_obj:
            logger.warning(f"Device '{device_name}' not found in cache, skipping")
            continue
        
        try:
            # Get all module bays for this device
            existing_bays = nb_session.dcim.module_bays.filter(
                device_id=device_obj.id
            )
            
            # Filter to only old-style names (e.g., "Module A", "Module B")
            for bay in existing_bays:
                if bay.name in old_module_names:
                    modules_to_delete.append(bay)
                    logger.debug(
                        f"Marked old-style module for deletion: '{bay.name}' on {device_name} (ID: {bay.id})"
                    )
                    
        except Exception as e:
            logger.error(
                f"Error querying module bays for device {device_name}: {e}",
                exc_info=True
            )
    
    logger.info(f"Found {len(modules_to_delete)} old-style module bay(s) to delete")
    
    return modules_to_delete

def _process_module_operations(
    nb_session: NetBoxApi, 
    modules_data: List[Dict],
    devices_cache: Dict[str, object]
) -> Tuple[List[Dict], List[Dict], int]:
    """
    Process module configurations to determine create, update, and delete operations.
    
    For each module configuration:
    1. Check if module bay with target name exists
    2. If multiple exist, keep one and delete duplicates
    3. If one exists, prepare update payload
    4. If none exist, prepare create payload
    
    Args:
        nb_session: pynetbox API session
        modules_data: List of module configuration dictionaries
        devices_cache: Dictionary mapping device names to device objects
        
    Returns:
        Tuple of (create_payloads, update_payloads, deleted_count)
    """
    create_payloads = []
    update_payloads = []
    deleted_count = 0
    skipped_count = 0
    
    # Cache module types to avoid repeated lookups
    module_types_cache = {}
    
    logger.info(f"Processing {len(modules_data)} module bay configuration(s)")
    
    for module_config in modules_data:
        device_name = module_config.get('device')
        module_bay = module_config.get('module_bay')
        name_description = module_config.get('name')
        module_type_name = module_config.get('type')
        new_position = module_config.get('new_position')
        
        # Validate required fields
        if not all([device_name, module_bay, name_description, module_type_name]):
            logger.warning(
                f"Module config missing required fields (device, module_bay, name, type): {module_config}"
            )
            skipped_count += 1
            continue
        
        # Get device from cache
        device_obj = devices_cache.get(device_name)
        if not device_obj:
            logger.warning(
                f"Device '{device_name}' not found, skipping module bay {module_bay}"
            )
            skipped_count += 1
            continue
        
        # Resolve module type (with caching)
        if module_type_name not in module_types_cache:
            module_type_id = _resolve_module_type(nb_session, module_type_name)
            module_types_cache[module_type_name] = module_type_id
        else:
            module_type_id = module_types_cache[module_type_name]
        
        if not module_type_id:
            logger.warning(
                f"Module type '{module_type_name}' not found for {device_name}, skipping"
            )
            skipped_count += 1
            continue
        
        # Build the target module bay name
        module_name = f"{device_name}-{module_bay}"
        
        # Check for existing module bays with this name on this device
        try:
            existing_bays = list(nb_session.dcim.module_bays.filter(
                device_id=device_obj.id,
                name=module_name
            ))
            
            if len(existing_bays) > 1:
                # Multiple duplicates found - keep first, delete rest
                logger.warning(
                    f"Found {len(existing_bays)} duplicate module bays named '{module_name}' "
                    f"on {device_name}, keeping one and deleting {len(existing_bays) - 1}"
                )
                
                keep_bay = existing_bays[0]
                duplicates = existing_bays[1:]
                
                # Delete duplicates
                for duplicate in duplicates:
                    if _delete_netbox_obj(duplicate):
                        deleted_count += 1
                
                # Prepare update for the one we kept
                update_payload = _build_module_payload(
                    module_name=module_name,
                    device_id=device_obj.id,
                    description=name_description,
                    module_type_id=module_type_id,
                    label=new_position,
                    existing_id=keep_bay.id
                )
                update_payloads.append(update_payload)
                logger.debug(f"Prepared update for existing module bay: {module_name}")
                
            elif len(existing_bays) == 1:
                # Exactly one exists - update it
                existing_bay = existing_bays[0]
                update_payload = _build_module_payload(
                    module_name=module_name,
                    device_id=device_obj.id,
                    description=name_description,
                    module_type_id=module_type_id,
                    label=new_position,
                    existing_id=existing_bay.id
                )
                update_payloads.append(update_payload)
                logger.debug(f"Prepared update for existing module bay: {module_name}")
                
            else:
                # None exist - create new
                create_payload = _build_module_payload(
                    module_name=module_name,
                    device_id=device_obj.id,
                    description=name_description,
                    module_type_id=module_type_id,
                    label=new_position,
                    existing_id=None
                )
                create_payloads.append(create_payload)
                logger.debug(f"Prepared create for new module bay: {module_name}")
                
        except Exception as e:
            logger.error(
                f"Error processing module bay {module_name} on {device_name}: {e}",
                exc_info=True
            )
            skipped_count += 1
    
    if skipped_count > 0:
        logger.warning(f"Skipped {skipped_count} module bay(s) due to errors or missing data")
    
    logger.info(
        f"Prepared {len(create_payloads)} create(s), {len(update_payloads)} update(s), "
        f"deleted {deleted_count} duplicate(s)"
    )
    
    return create_payloads, update_payloads, deleted_count


def _build_module_payload(
    module_name: str,
    device_id: int,
    description: str,
    module_type_id: int,
    label: str | None = None,
    existing_id: int | None = None
) -> Dict:
    """
    Build a module bay payload for create or update operation.
    
    Args:
        module_name: Name for the module bay (e.g., "swgs0001sp-1-A")
        device_id: Device ID
        description: Description text
        module_type_id: Module type ID
        label: Label from new_position field (optional)
        existing_id: If provided, includes 'id' for update operation
        
    Returns:
        Payload dictionary
    """
    payload = {
        'name': module_name,
        'position': module_name,
        'device': device_id,
        'description': description,
        'module_type': module_type_id
    }
    
    # Add label if provided
    if label:
        payload['label'] = label
    
    # Add ID for update operations
    if existing_id is not None:
        payload['id'] = existing_id
    
    return payload


def _resolve_module_type(nb_session: NetBoxApi, module_type_name: str) -> int | None:
    """
    Resolve module type name to module type ID.
    
    Args:
        nb_session: pynetbox API session
        module_type_name: Name of the module type (e.g., "Aruba 2920 2-Port 10GbE SFP+ Module")
        
    Returns:
        Module type ID or None if not found
    """
    try:
        module_type = nb_session.dcim.module_types.get(model=module_type_name)
        
        if module_type:
            logger.debug(f"Found module type: {module_type_name} (ID: {module_type.id})")
            return module_type.id
        else:
            logger.warning(f"Module type not found: {module_type_name}")
            return None
            
    except Exception as e:
        logger.error(
            f"Error resolving module type '{module_type_name}': {e}",
            exc_info=True
        )
        return None

if __name__ == '__main__':
    from pynetbox_functions import _main, _debug
    _main("Processing modules data on a NetBox server", modules)