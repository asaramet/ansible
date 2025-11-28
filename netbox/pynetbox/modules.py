#!/usr/bin/env python3

"""
Module management functions for NetBox automation.

This module provides functions to manage switch modules (module bays) in NetBox,
including deletion of old modules and creation of new ones based on YAML data.
"""

from typing import Tuple
from pynetbox.core.api import Api as NetBoxApi
import logging

from pynetbox_functions import (
    _cache_devices,
    _bulk_create,
    _bulk_update,
    _delete_netbox_obj
)

logger = logging.getLogger(__name__)


def module_bays(nb_session: NetBoxApi, data: dict[str, list[dict]]) -> list[dict[str, str | int]]:
    """
    Update switch module bays on a NetBox server from YAML data.
    
    This function manages module bays (slots) but does NOT install modules in them.
    Use the modules() function after this to install actual modules.
    
    This function:
    1. Deletes old-style module bays (e.g., "Module A", "Module B")
    2. Checks for existing module bays with the new naming scheme
    3. If duplicates exist, keeps one and deletes the rest
    4. Updates existing module bay or creates new one if it doesn't exist
    
    Args:
        nb_session: pynetbox API session
        data: dictionary containing 'modules' list with module configurations
        
    Returns:
        list of payloads processed (created or updated)
        
    Example YAML structure:
        modules:
          - device: swgw1001ap-1
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
    
    logger.info(f"Processing {len(modules_data)} module bay configuration(s)")
    
    # Step 1: Cache all devices mentioned in the module data
    device_names = _extract_unique_device_names(modules_data)
    devices_cache = _cache_devices(nb_session, device_names)
    
    if not devices_cache:
        logger.error("No devices found in NetBox. Cannot proceed with module bay updates.")
        return []
    
    # Step 2: Delete all old-format module bays in one efficient pass
    # This includes:
    # - Old device-bay format (e.g., "swgw1001ap-1-A")
    # - Old-style names (e.g., "Module A", "Module B")
    old_bays_to_delete = _collect_all_old_format_bays(
        nb_session, modules_data, devices_cache
    )
    old_bays_deleted_count = _bulk_delete_modules(old_bays_to_delete)
    
    # Step 3: Process new-style module bays (create/update/handle duplicates)
    # This will determine which bays need changes and which modules need to be deleted
    create_payloads, update_payloads, modules_to_delete, duplicate_deleted_count = _process_module_operations(
        nb_session, modules_data, devices_cache
    )
    
    # Step 4: Delete modules only from bays that need to be updated/recreated
    existing_modules_deleted_count = _bulk_delete_installed_modules(modules_to_delete)
    
    # Step 5: Create new module bays in bulk
    created_count = 0
    if create_payloads:
        created_modules = _bulk_create(
            nb_session.dcim.module_bays, 
            create_payloads, 
            "module bay"
        )
        created_count = len(created_modules)
    
    # Step 6: Update existing module bays in bulk
    updated_count = 0
    if update_payloads:
        updated_modules = _bulk_update(
            nb_session.dcim.module_bays,
            update_payloads,
            "module bay"
        )
        updated_count = len(updated_modules)
    
    total_deleted = (existing_modules_deleted_count + old_bays_deleted_count + 
                     duplicate_deleted_count)
    total_changes = created_count + updated_count
    total_skipped = len(modules_data) - total_changes - len(create_payloads)
    
    logger.info(
        f"Module bay processing complete: {total_deleted} deleted "
        f"({existing_modules_deleted_count} modules from changed bays, "
        f"{old_bays_deleted_count} old-format bays, "
        f"{duplicate_deleted_count} duplicate bays), "
        f"{created_count} created, {updated_count} updated, {total_skipped} unchanged"
    )
    
    return create_payloads + update_payloads


def modules(nb_session: NetBoxApi, data: dict[str, list[dict]]) -> list[dict[str, str | int]]:
    """
    Install modules into module bays on a NetBox server from YAML data.
    
    This function is idempotent - it only creates modules that don't already exist
    or that need to be recreated (if module_bays() deleted them).
    
    For each module configuration:
    1. Finds the module bay (by device and bay name)
    2. Looks up the module type by model name
    3. Checks if correct module already exists in the bay
    4. Only creates module if it doesn't exist or was deleted
    5. Warns if module type doesn't exist
    
    Args:
        nb_session: pynetbox API session
        data: dictionary containing 'modules' list with module configurations
        
    Returns:
        list of payloads processed (created)
        
    Example YAML structure:
        modules:
          - device: swgw1001ap-1
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
        logger.info("No modules to install")
        return []
    
    logger.info(f"Installing {len(modules_data)} module(s) into module bays")
    
    # Step 1: Cache all devices
    device_names = _extract_unique_device_names(modules_data)
    devices_cache = _cache_devices(nb_session, device_names)
    
    if not devices_cache:
        logger.error("No devices found in NetBox. Cannot proceed with module installation.")
        return []
    
    # Step 2: Process module installations
    create_payloads, skipped_count = _process_module_installations(
        nb_session, modules_data, devices_cache
    )
    
    # Step 3: Create new modules in bulk
    created_count = 0
    if create_payloads:
        created_modules = _bulk_create(
            nb_session.dcim.modules,
            create_payloads,
            "module"
        )
        created_count = len(created_modules)
    
    logger.info(
        f"Module installation complete: {created_count} created, "
        f"{skipped_count} skipped (missing module type or bay)"
    )
    
    return create_payloads


def _extract_unique_device_names(modules_data: list[dict]) -> list[str]:
    """
    Extract unique device names from modules data.
    
    Args:
        modules_data: list of module configuration dictionaries
        
    Returns:
        list of unique device names
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


def _bulk_delete_modules(modules: list[object]) -> int:
    """
    Delete module bays using the standard _delete_netbox_obj function.
    
    Args:
        modules: list of module bay objects to delete
        
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


def _bulk_delete_installed_modules(modules: list[object]) -> int:
    """
    Delete installed modules (not module bays) using the standard _delete_netbox_obj function.
    
    Args:
        modules: list of module objects to delete
        
    Returns:
        Number of successfully deleted modules
    """
    if not modules:
        return 0
    
    deleted_count = 0
    
    logger.info(f"Attempting to delete {len(modules)} installed module(s)...")
    
    for module in modules:
        if _delete_netbox_obj(module):
            deleted_count += 1
    
    logger.info(f"Successfully deleted {deleted_count}/{len(modules)} installed module(s)")
    
    return deleted_count


def _collect_all_old_format_bays(
    nb_session: NetBoxApi,
    modules_data: list[dict],
    devices_cache: dict[str, object]
) -> list[object]:
    """
    Collect all old-format module bays that need to be deleted.
    
    This combines two types of old bays:
    1. Device-bay format (e.g., "swgw1001ap-1-A")
    2. Old-style names (e.g., "Module A", "Module B")
    
    By combining them, we only query each device once instead of twice.
    
    Args:
        nb_session: pynetbox API session
        modules_data: list of module configuration dictionaries
        devices_cache: dictionary mapping device names to device objects
        
    Returns:
        list of old-format module bay objects to delete
    """
    modules_to_delete = []
    
    # Build a mapping of device_name -> set of old bay names to delete
    device_old_names_map = {}
    
    for module_config in modules_data:
        device_name = module_config.get('device')
        module_bay_letter = module_config.get('module_bay')
        old_style_name = module_config.get('name')  # e.g., "Module A"
        
        if not device_name:
            continue
        
        if device_name not in device_old_names_map:
            device_old_names_map[device_name] = set()
        
        # Add device-bay format name (e.g., "swgw1001ap-1-A")
        if module_bay_letter:
            device_bay_name = f"{device_name}-{module_bay_letter}"
            device_old_names_map[device_name].add(device_bay_name)
        
        # Add old-style name (e.g., "Module A")
        if old_style_name:
            device_old_names_map[device_name].add(old_style_name)
    
    # Query for existing module bays with old names (only one query per device)
    logger.info(f"Checking for old-format module bays on {len(device_old_names_map)} device(s)")
    
    for device_name, old_names in device_old_names_map.items():
        device_obj = devices_cache.get(device_name)
        
        if not device_obj:
            logger.warning(f"Device '{device_name}' not found in cache, skipping")
            continue
        
        try:
            # Get all module bays for this device (single query)
            existing_bays = nb_session.dcim.module_bays.filter(
                device_id=device_obj.id
            )
            
            # Filter to only old-format names
            for bay in existing_bays:
                if bay.name in old_names:
                    modules_to_delete.append(bay)
                    logger.debug(
                        f"Marked old-format bay for deletion: '{bay.name}' "
                        f"on {device_name} (ID: {bay.id})"
                    )
                    
        except Exception as e:
            logger.error(
                f"Error querying module bays for device {device_name}: {e}",
                exc_info=True
            )
    
    logger.info(f"Found {len(modules_to_delete)} old-format module bay(s) to delete")
    
    return modules_to_delete


def _collect_existing_modules_to_delete(
    nb_session: NetBoxApi,
    modules_data: list[dict],
    devices_cache: dict[str, object]
) -> list[object]:
    """
    Collect existing modules (installed in module bays) that need to be deleted.
    
    This function finds modules that are already installed in bays that we're about
    to manage. These modules need to be deleted before we can create new ones with
    the correct configuration.
    
    For example, if there's already a module in bay "1/A" with description "Uplink",
    we need to delete it before inserting our new module with proper configuration.
    
    Args:
        nb_session: pynetbox API session
        modules_data: list of module configuration dictionaries
        devices_cache: dictionary mapping device names to device objects
        
    Returns:
        list of existing module objects to delete
    """
    modules_to_delete = []
    
    # Build a mapping of device_name -> set of positions we're managing
    device_position_map = {}
    
    for module_config in modules_data:
        device_name = module_config.get('device')
        new_position = module_config.get('new_position')  # e.g., "1/A"
        
        if not device_name or not new_position:
            continue
        
        if device_name not in device_position_map:
            device_position_map[device_name] = set()
        
        device_position_map[device_name].add(new_position)
    
    # Query for existing modules on these devices at these positions
    logger.info(f"Checking for existing modules to delete on {len(device_position_map)} device(s)")
    
    for device_name, positions in device_position_map.items():
        device_obj = devices_cache.get(device_name)
        
        if not device_obj:
            logger.warning(f"Device '{device_name}' not found in cache, skipping")
            continue
        
        try:
            # Get all modules for this device
            existing_modules = nb_session.dcim.modules.filter(
                device_id=device_obj.id
            )
            
            # Check each module to see if it's in a bay we're managing
            for module in existing_modules:
                # Get the module bay for this module
                if hasattr(module, 'module_bay') and module.module_bay:
                    # Get the full bay object to check its name
                    try:
                        bay = nb_session.dcim.module_bays.get(module.module_bay.id)
                        if bay and bay.name in positions:
                            modules_to_delete.append(module)
                            logger.debug(
                                f"Marked existing module for deletion: "
                                f"Module in bay '{bay.name}' on {device_name} (Module ID: {module.id})"
                            )
                    except Exception as e:
                        logger.warning(
                            f"Error checking bay for module {module.id} on {device_name}: {e}"
                        )
                    
        except Exception as e:
            logger.error(
                f"Error querying modules for device {device_name}: {e}",
                exc_info=True
            )
    
    logger.info(f"Found {len(modules_to_delete)} existing module(s) to delete")
    
    return modules_to_delete


def _process_module_operations(
    nb_session: NetBoxApi, 
    modules_data: list[dict],
    devices_cache: dict[str, object]
) -> Tuple[list[dict], list[dict], list[object], int]:
    """
    Process module configurations to determine create, update, and delete operations.
    
    Now returns modules that need to be deleted (only when bay config changes).
    
    For each module configuration:
    1. Check if module bay with target name exists
    2. If multiple exist, keep one and delete duplicates
    3. If one exists and config matches, skip (no changes needed)
    4. If one exists and config differs, prepare update and mark module for deletion
    5. If none exist, prepare create
    
    Args:
        nb_session: pynetbox API session
        modules_data: list of module configuration dictionaries
        devices_cache: dictionary mapping device names to device objects
        
    Returns:
        Tuple of (create_payloads, update_payloads, modules_to_delete, deleted_count)
    """
    create_payloads = []
    update_payloads = []
    modules_to_delete = []  # Only modules in bays that need updating
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
        
        # Build the target module bay name (position format like "1/A")
        if not new_position:
            logger.warning(
                f"Module config missing 'new_position' for {device_name}-{module_bay}, skipping"
            )
            skipped_count += 1
            continue
        
        module_bay_position = new_position  # e.g., "1/A", "2/A"
        device_bay_label = f"{device_name}-{module_bay}"  # e.g., "swgw1001ap-1-A"
        
        # Check for existing module bays with this name (position) on this device
        try:
            existing_bays = list(nb_session.dcim.module_bays.filter(
                device_id=device_obj.id,
                name=module_bay_position
            ))
            
            if len(existing_bays) > 1:
                # Multiple duplicates found - keep first, delete rest
                logger.warning(
                    f"Found {len(existing_bays)} duplicate module bays named '{module_bay_position}' "
                    f"on {device_name}, keeping one and deleting {len(existing_bays) - 1}"
                )
                
                keep_bay = existing_bays[0]
                duplicates = existing_bays[1:]
                
                # Delete duplicates and their modules
                for duplicate in duplicates:
                    # Collect modules from duplicate bays for deletion
                    try:
                        dup_modules = nb_session.dcim.modules.filter(
                            device_id=device_obj.id,
                            module_bay_id=duplicate.id
                        )
                        modules_to_delete.extend(dup_modules)
                    except Exception as e:
                        logger.warning(f"Error collecting modules from duplicate bay: {e}")
                    
                    if _delete_netbox_obj(duplicate):
                        deleted_count += 1
                
                # Check if the kept bay needs updating
                if _bay_needs_update(keep_bay, device_bay_label, name_description):
                    # Bay config changed - need to delete module and update bay
                    try:
                        existing_modules = nb_session.dcim.modules.filter(
                            device_id=device_obj.id,
                            module_bay_id=keep_bay.id
                        )
                        modules_to_delete.extend(existing_modules)
                    except Exception as e:
                        logger.warning(f"Error collecting modules for update: {e}")
                    
                    update_payload = _build_module_payload(
                        module_name=module_bay_position,
                        device_id=device_obj.id,
                        description=name_description,
                        label=device_bay_label,
                        existing_id=keep_bay.id
                    )
                    update_payloads.append(update_payload)
                    logger.debug(f"Prepared update for existing module bay: {module_bay_position} on {device_name}")
                else:
                    # No changes needed
                    logger.debug(f"Module bay {module_bay_position} on {device_name} is up to date, skipping")
                    skipped_count += 1
                
            elif len(existing_bays) == 1:
                # Exactly one exists - check if it needs updating
                existing_bay = existing_bays[0]
                
                if _bay_needs_update(existing_bay, device_bay_label, name_description):
                    # Bay config changed - need to delete module and update bay
                    try:
                        existing_modules = nb_session.dcim.modules.filter(
                            device_id=device_obj.id,
                            module_bay_id=existing_bay.id
                        )
                        modules_to_delete.extend(existing_modules)
                    except Exception as e:
                        logger.warning(f"Error collecting modules for update: {e}")
                    
                    update_payload = _build_module_payload(
                        module_name=module_bay_position,
                        device_id=device_obj.id,
                        description=name_description,
                        label=device_bay_label,
                        existing_id=existing_bay.id
                    )
                    update_payloads.append(update_payload)
                    logger.debug(f"Prepared update for existing module bay: {module_bay_position} on {device_name}")
                else:
                    # No changes needed
                    logger.debug(f"Module bay {module_bay_position} on {device_name} is up to date, skipping")
                    skipped_count += 1
                
            else:
                # None exist - create new
                create_payload = _build_module_payload(
                    module_name=module_bay_position,
                    device_id=device_obj.id,
                    description=name_description,
                    label=device_bay_label,
                    existing_id=None
                )
                create_payloads.append(create_payload)
                logger.debug(f"Prepared create for new module bay: {module_bay_position} on {device_name}")
                
        except Exception as e:
            logger.error(
                f"Error processing module bay {module_bay_position} on {device_name}: {e}",
                exc_info=True
            )
            skipped_count += 1
    
    if skipped_count > 0:
        logger.warning(f"Skipped {skipped_count} module bay(s) due to errors or missing data")
    
    if skipped_count > 0:
        logger.info(f"Skipped {skipped_count} module bay(s) - already up to date")
    
    logger.info(
        f"Prepared {len(create_payloads)} create(s), {len(update_payloads)} update(s), "
        f"deleted {deleted_count} duplicate(s), {len(modules_to_delete)} module(s) need deletion"
    )
    
    return create_payloads, update_payloads, modules_to_delete, deleted_count


def _bay_needs_update(existing_bay, target_label: str, target_description: str) -> bool:
    """
    Check if a module bay needs updating by comparing current values to target values.
    
    Only checks bay-specific attributes (label and description).
    Module type is not stored on the bay - it's on the installed module.
    
    Args:
        existing_bay: Existing NetBox module bay object
        target_label: Target label value
        target_description: Target description value
        
    Returns:
        True if bay needs updating, False if it's already correct
    """
    # Check label
    current_label = getattr(existing_bay, 'label', None)
    if current_label != target_label:
        logger.debug(f"Bay label mismatch: '{current_label}' != '{target_label}'")
        return True
    
    # Check description
    current_description = getattr(existing_bay, 'description', None)
    if current_description != target_description:
        logger.debug(f"Bay description mismatch: '{current_description}' != '{target_description}'")
        return True
    
    # All bay values match - no update needed
    return False


def _build_module_payload(
    module_name: str,
    device_id: int,
    description: str,
    label: str | None = None,
    existing_id: int | None = None
) -> dict:
    """
    Build a module bay payload for create or update operation.
    
    NOTE: Module bays DO NOT have a 'module_type' field. That field is only on 
    the installed module itself. Module bays only define the slot structure.
    
    The name field should be the position (e.g., "1/A", "2/A") so that when modules
    are inserted, interfaces get proper names like "1/A/1", "1/A/2" instead of 
    weird names based on device-bay format.
    
    Args:
        module_name: Position for the module bay (e.g., "1/A", "2/A") - becomes 'name'
        device_id: Device ID
        description: Description text (e.g., "Module A") - human readable
        label: Label text (e.g., "swgw1001ap-1-A") - device-bay identifier
        existing_id: If provided, includes 'id' for update operation
        
    Returns:
        Payload dictionary
    """
    payload = {
        'name': module_name,          # Position like "1/A" - used for interface naming
        'device': device_id,
        'description': description,    # Human readable like "Module A"
        'position': module_name       # Position is same as name for module bays
    }
    
    # Add label (device-bay format like "swgw1001ap-1-A")
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


def _process_module_installations(
    nb_session: NetBoxApi,
    modules_data: list[dict],
    devices_cache: dict[str, object]
) -> Tuple[list[dict], int]:
    """
    Process module configurations to install modules into module bays.
    
    Note: This function assumes module_bays() has already been run, which
    deletes any existing modules. Therefore, we only create new modules,
    never update existing ones.
    
    For each module configuration:
    1. Find the module bay (device-bay naming scheme)
    2. Look up the module type
    3. Prepare create payload (existing modules should have been deleted)
    
    Args:
        nb_session: pynetbox API session
        modules_data: list of module configuration dictionaries
        devices_cache: dictionary mapping device names to device objects
        
    Returns:
        Tuple of (create_payloads, skipped_count)
    """
    create_payloads = []
    skipped_count = 0
    
    # Cache module types to avoid repeated lookups
    module_types_cache = {}
    
    logger.info(f"Processing {len(modules_data)} module installation(s)")
    
    for module_config in modules_data:
        device_name = module_config.get('device')
        module_bay_letter = module_config.get('module_bay')
        module_type_name = module_config.get('type')
        new_position = module_config.get('new_position')
        
        # Validate required fields
        if not all([device_name, module_bay_letter, module_type_name]):
            logger.warning(
                f"Module config missing required fields (device, module_bay, type): {module_config}"
            )
            skipped_count += 1
            continue
        
        # Get device from cache
        device_obj = devices_cache.get(device_name)
        if not device_obj:
            logger.warning(
                f"Device '{device_name}' not found, skipping module installation"
            )
            skipped_count += 1
            continue
        
        # Build module bay name (position format like "1/A")
        if not new_position:
            logger.warning(
                f"Module config missing 'new_position' for {device_name}, skipping module installation"
            )
            skipped_count += 1
            continue
        
        module_bay_position = new_position  # e.g., "1/A", "2/A"
        
        # Find the module bay by position name
        try:
            module_bay = nb_session.dcim.module_bays.get(
                device_id=device_obj.id,
                name=module_bay_position
            )
            
            if not module_bay:
                logger.warning(
                    f"Module bay '{module_bay_position}' not found on device {device_name}. "
                    f"Run module_bays() first to create the bay."
                )
                skipped_count += 1
                continue
                
        except Exception as e:
            logger.error(
                f"Error finding module bay {module_bay_position} on {device_name}: {e}",
                exc_info=True
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
                f"Module type '{module_type_name}' not found in NetBox. "
                f"Please create this module type or import it as a template first."
            )
            skipped_count += 1
            continue
        
        # Check if a module already exists in this bay
        # If it exists and matches our config, skip it (idempotent behavior)
        try:
            existing_module = nb_session.dcim.modules.get(
                device_id=device_obj.id,
                module_bay_id=module_bay.id
            )
            
            if existing_module:
                # Module exists - check if it matches our config
                current_module_type_id = getattr(getattr(existing_module, 'module_type', None), 'id', None)
                current_label = getattr(existing_module, 'label', None)
                
                # Debug logging to see what we're comparing
                logger.debug(
                    f"Comparing module in bay {module_bay_position} on {device_name}: "
                    f"current_module_type_id={current_module_type_id} vs target={module_type_id}, "
                    f"current_label='{current_label}' vs target='{new_position}'"
                )
                
                # Check if module type matches (this is the critical field)
                module_type_matches = (current_module_type_id == module_type_id)
                
                # Check if label matches - be flexible about empty/None labels
                # If label is empty/None, we consider it a match (can update it later if needed)
                label_matches = (
                    current_label == new_position or  # Exact match
                    not current_label  # Empty/None label is OK - we can update it
                )
                
                if module_type_matches and label_matches:
                    # Module already correct (or label just needs updating, which is minor)
                    if not current_label and new_position:
                        logger.debug(
                            f"Module in bay {module_bay_position} on {device_name} has empty label, "
                            f"but module type matches. Considering it correct."
                        )
                    else:
                        logger.debug(
                            f"Module in bay {module_bay_position} on {device_name} is already correct, skipping"
                        )
                    skipped_count += 1
                    continue
                else:
                    # Module exists but doesn't match
                    mismatch_reasons = []
                    if not module_type_matches:
                        mismatch_reasons.append(f"module_type: {current_module_type_id} != {module_type_id}")
                    if current_label and current_label != new_position:
                        # Only report label mismatch if current label exists and is different
                        mismatch_reasons.append(f"label: '{current_label}' != '{new_position}'")
                    
                    logger.warning(
                        f"Module in bay {module_bay_position} on {device_name} exists but doesn't match config. "
                        f"Mismatches: {', '.join(mismatch_reasons)}. Skipping to avoid error."
                    )
                    skipped_count += 1
                    continue
                
        except Exception as e:
            # If we get a "not found" error or any error checking for the module,
            # that's actually fine - it means the module doesn't exist (as expected)
            logger.debug(f"No existing module found in bay {module_bay_position} (will create): {e}")
        
        # Create new module (this is the expected path when module doesn't exist)
        try:
            create_payload = _build_module_installation_payload(
                device_id=device_obj.id,
                module_bay_id=module_bay.id,
                module_type_id=module_type_id,
                label=new_position,
                existing_id=None
            )
            create_payloads.append(create_payload)
            logger.debug(
                f"Prepared create for module in bay {module_bay_position} on {device_name}"
            )
        except Exception as e:
            logger.error(
                f"Error preparing module creation for bay {module_bay_position} on {device_name}: {e}",
                exc_info=True
            )
            skipped_count += 1
    
    logger.info(
        f"Prepared {len(create_payloads)} module create(s), skipped {skipped_count}"
    )
    
    return create_payloads, skipped_count


def _build_module_installation_payload(
    device_id: int,
    module_bay_id: int,
    module_type_id: int,
    label: str | None = None,
    existing_id: int | None = None
) -> dict:
    """
    Build a module installation payload for create or update operation.
    
    Args:
        device_id: Device ID
        module_bay_id: Module bay ID
        module_type_id: Module type ID
        label: Label from new_position field (optional)
        existing_id: If provided, includes 'id' for update operation
        
    Returns:
        Payload dictionary
    """
    payload = {
        'device': device_id,
        'module_bay': module_bay_id,
        'module_type': module_type_id
    }
    
    # Add label if provided
    if label:
        payload['label'] = label
    
    # Add ID for update operations
    if existing_id is not None:
        payload['id'] = existing_id
    
    return payload


if __name__ == '__main__':
    from pynetbox_functions import _main, _debug
    _main("Update switch module bays in NetBox", module_bays)
    _main("Update switch module in NetBox", modules)
    #_debug("Update switch module bays in NetBox", module_bays)
    #_debug("Update switch module in NetBox", modules)