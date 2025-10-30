#!/usr/bin/env python3

'''
Process modules for switches on a NetBox platform using `pynetbox` library
Main function, to import:

- modules(nb_session, data):
    - nb_session - pynetbox API session
    - data - data (yaml format)
'''

import pynetbox, logging

from typing import Dict, List, Tuple, Optional
from pynetbox.core.api import Api as NetBoxApi

from pynetbox_functions import _bulk_create, _bulk_update
from pynetbox_functions import _manufacturer, _cache_devices, _extract_stack_number

# Get logger
logger = logging.getLogger(__name__)

def switch_modules(nb_session: NetBoxApi, type_names: List[str]) -> Dict[str, object]:
    """
    Get existing module types and create the missing ones.

    Args:
        nb_session: pynetbox API session
        type_names: List of module type names 

    Returns:
        Dictionary of module type name to object
    """
    if not type_names: 
        return {}

    nb_module_types = nb_session.dcim.module_types
    existing_types = nb_module_types.filter(model__in = type_names)
    types_dict = {mt.model: mt for mt in existing_types}

    # Find missing types
    missing_types = [name for name in type_names if name not in types_dict]

    if not missing_types: 
        return types_dict

    # Creating missing types
    create_payloads = []
    manufacturer_id = _manufacturer(nb_session, 'Aruba') # Default switch manufacturer TODO: add others

    for type_name in missing_types:
        create_payloads.append({
            'manufacturer': manufacturer_id,
            'model': type_name,
            'part_number': type_name
        })

    try:
        created_types = _bulk_create(nb_module_types, create_payloads, 'module types')
        for created_type in created_types:
            types_dict[created_type.model] = created_type
    except Exception as e:
        logger.error(f"Failed to create module type: {e}", exc_info = True)

    return types_dict

def cleanup_module_interfaces(nb_session: NetBoxApi, device: object, module_bay: object, module_type: object) -> Tuple[List[str], List[str]]:
    """
    Find and delete interfaces that should belong to a module but are currently on the device.

    Args:
        nb_session: pynetbox API session
        device: Device object
        module_bay: Module bay object where module will be installed
        module_type: Module type that will be installed

    Returns: 
        Tuple of (deleted_interfaces, errors)
    """
    deleted, errors = [], []

    try:
        # Get interface templates fot this module type
        interface_templates = list(nb_session.dcim.interface_templates.filter(module_type_id = module_type.id))

        if not interface_templates:
            logger.debug(f"No interface templates for module type {module_type.model}")
            return deleted, errors
        
        # Get bay position to construct expected interface names
        bay_position = getattr(module_bay, 'position', None) or getattr(module_bay, 'name', '')

        # Build list of interface names that should be on the module
        expected_interface_names = []
        for template in interface_templates:
            # Interface name format: {bay_position}-{template_name}
            # e.g., "1/A" + "1" = "1/A1"
            interface_name = f"{bay_position}{template.name}"
            expected_interface_names.append(interface_name)

        if not expected_interface_names:
            return deleted, errors

        logger.info(f"Checking for orphaned interfaces on device {device.name}: {expected_interface_names}")

        # Find these interfaces on the device (not on any module)
        for iface_name in expected_interface_names:
            try:
                # Get interface by name on this device
                existing_interface = nb_session.dcim.interfaces.get(device_id = device.id, name = iface_name)

                if existing_iface:
                    # Check if it's on a module already
                    if hasattr(existing_interface, 'module') and existing_interface.module:
                        logger.debug(f"Interface {iface_name} already belongs to module {existing_interface.module.id}, skipping")
                        continue

                    # This interface exists on the device but not on a module | Delete it
                    logger.warning(f"Deleting orphaned interface {iface_name} from device {device.name} (will be recreated on module)")
                    existing_interface.delete()
                    deleted.append(iface_name)

            except Exception as e:
                error_msg = f"Failed to delete {iface_name}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)

        if deleted:
            logger.info(f"Deleted {len(deleted)} orphaned interface(s) from device {device.name}: {deleted}")

        return deleted, errors

    except Exception as e:
        logger.error(f"Error during interface cleanup: {e}", exc_info = True)
        return deleted, [str(e)]

def check_module_interface_conflicts(nb_session: NetBoxApi, device: object, module_type: object, module_bay: object) -> bool:
    """
    Check if creating a module would cause interface name conflicts.

    Args:
        nb_session: pynetbox API session
        device: Device object
        module_type: Module type object
        module_bay: Module bay object

    Returns:
        True if conflict exist, False otherwise
    """
    try:
        # Get interface templates for this module type
        interface_templates = list(nb_session.dcim.interface_templates.filter(module_type_id = module_type.id))

        if not interface_templates:
            # No interface templates, no conflicts
            return False

        # Get existing interfaces on the device
        existing_interfaces = {iface.name for iface in nb_session.dcim.interfaces.filter(device_id = device.id)}

        # Check if any template interface names would conflict
        bay_position = getattr(module_bay, 'position', None) or getattr(module_bay, 'name', '')

        conflicts = []
        for template in interface_templates:
            # NetBox will generate interface names based on bay postion + template name
            # For example: bay position "1/A" + template name "1" = interface name "1/A1"
            potential_name = f"{bay_position}{template.name}"

            if potential_name in existing_interfaces:
                conflicts.append(potential_name)
                logger.warning(f"Interface conflict detected: {potential_name} already exists on {device.name}")

                # Check if this interface belongs to a module already
                existing_iface = existing_interfaces[potential_name]
                if hasattr(existing_iface, 'module') and existing_iface.module:
                    logger.warning(f"\tInterface {potential_name} belongs to module ID {existing_iface.module.id}")
        
        if conflicts:
            logger.warning(f"Found {len(conflicts)} interface conflicts for module type {module_type.model} in bay {bay_position}: {conflicts}")
            return True

        return False

    except Exception as e:
        logger.error(f"Error checking interface conflicts: {e}", exc_info = True)
        # On error assume conflicts exist
        return True

def get_module_bay(nb_session: NetBoxApi, device: object, bay_name: str, stack_number: str = None) -> Optional[object]:
    """
    Get module bay for both stacked and single switches.
    Prioritizes properly named bays ({hostname}-{bay}) over default template bays.

    Args:
        nb_session: pynetbox API session
        device: Device object
        bay_name: Original bay name (e.g., "A")
        stack_number: Stack number (e.g, "1"), optional for single switches

    Returns:
        Module bay object or None
    """
    device_id = device.id
    device_name = device.name
    nb_module_bays = nb_session.dcim.module_bays

    # Try multiple naming patterns
    try:
        # Priority 1: Properly named bay with hostname prefix (e.g., "swgr1001u-1-A")
        specific_bay_name = f"{device_name}-{bay_name}"
        module_bay = nb_module_bays.get(device_id = device_id, name = specific_bay_name)
        if module_bay:
            logger.debug(f"Found module bay by specific name: {specific_bay_name}")
            return module_bay


        # Priority 2: Try by position (e.g., "1/A" or "2/A")
        if stack_number:
            position_name = f"{stack_number}/{bay_name}"
            module_bay = nb_module_bays.get(device_id = device_id, position = position_name)
            if module_bay:
                logger.debug(f"Found module bay by position: {position_name} for {device_name}")
                return module_bay

            # Also try by label
            module_bay = nb_module_bays.get(device_id = device_id, label = position_name)
            if module_bay:
                logger.debug(f"Found module bay by label: {position_name} for {device_name}")
                return module_bay


        # Priority 3: Generic name patterns (fallback only)
        fallback_names = [
            bay_name,               # Simple "A"
            f"Module {bay_name}",   # "Module A"
            "Uplink"                # Special case
        ]

        for name in fallback_names:
            module_bay = nb_module_bays.get(device_id = device_id, name = name)
            if module_bay: 
                logger.warning(f"Found module bay by fallback name '{name}' for {device_name}" +
                    f" This is a default template bay, consider renaming to {specific_bay_name}")
                return module_bay

        # Priority 4: Search all module bays and match by patterns
        all_bays = nb_module_bays.filter(device_id = device_id)
        for bay in all_bays:
            # Check various name patterns
            if (bay.name and bay.name.endswith(f"-{bay_name}")):
                logger.debug(f"Found module bay by pattern match: {bay.name}")
                return bay
            
            # Check by description pattern
            if (hasattr(bay, 'description') and bay.description and 
                f"Module {bay_name}" in bay.description):
                logger.debug(f"Found module bay by description: {bay.name}")
                return bay

        logger.debug(f"No module bay found for device {device_name}, bay {bay_name}")
        return None

    except Exception as e:
        logger.error(f"Error fetching module bay {bay_name} for device ID {device_id}: {e}", exc_info = True)
        return None

def create_module_bay(nb_session: NetBoxApi, device: object, bay_name: str, stack_number: str = None, new_position: str = None) -> Optional[object]:
    """
    Create or update module bay

    Args:
        nb_session: pynetbox API session
        device: Device object
        bay_name: Original bay name (e.g., "A")
        stack_number: Stack number (e.g., "1")
        new_position: Target position (e.g., "1/A")

    Returns:
        Module bay object or None
    """
    device_name = device.name
    module_bay_name = f"{device_name}-{bay_name}"

    position = f"{stack_number}/{bay_name}" if stack_number else bay_name
    position = new_position if new_position else position
    label = position # Same as position
    description = f"Module {bay_name}"

    try:
        # Create module bay
        payload = {
            'device': device.id,
            'name': module_bay_name,
            'position': position,
            'label': label,
            'description': description
        }

        new_bay = nb_session.dcim.module_bays.create(payload)
        logger.info(f"Created module bay {module_bay_name} for device {device_name}")

        return new_bay

    except Exception as e:
        # If creation fails, it might already exist, try to find it again
        logger.error(f"Failed to create module bay {module_bay_name}: {e}", exc_info = True)

        return get_module_bay(nb_session, device, bay_name, stack_number)

def prepare_module_payloads(nb_session: NetBoxApi, modules_data: List[Dict[str, str]]) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """
    Prepare payloads for bulk create and update operations.

    Args:
        nb_session: pynetbox API session
        modules_data: List of module data dictionaries

    Returns:
        Tuple of payloads to (create, update, errors)
    """
    if not modules_data: 
        return [],[],[]

    create_payloads, update_payloads, errors = [], [], []

    # Cache required data
    device_names = [mod['device'] for mod in modules_data]
    module_type_names = list(set(mod['type'] for mod in modules_data))

    logger.info(f"Processing {len(modules_data)} modules for {len(device_names)} devices")

    # Fetch devices in bulk
    devices_dict = _cache_devices(nb_session, device_names)
    logger.info(f"Found {len(devices_dict)} devices out of {len(set(device_names))} requested")

    # Get module types and create them if they don't exists
    module_types_dict = switch_modules(nb_session, module_type_names)
    logger.info(f"Module types available: {len(module_types_dict)}")

    # Build a list of required (devices_id, bay_id) pairs
    device_bay_pairs = []
    device_bay_to_data = {} # Map to store original module data

    for module_data in modules_data:
        device_name = module_data['device']
        module_bay_name = module_data['module_bay']

        device = devices_dict.get(device_name)
        if device:
            key = f"{device_name}_{module_bay_name}"
            device_bay_to_data[key] = {
                'device': device,
                'module_data': module_data
            }
            device_bay_pairs.append((device.id, module_bay_name))
        else:
            errors.append({
                'device': device_name,
                'module_bay': module_bay_name,
                'status': 'error',
                'message': f"Device {device_name} not found"
            })

    # Process modules
    for key, info in device_bay_to_data.items():
        device = info['device']
        module_data = info['module_data']
        device_name = device.name
        module_bay_name = module_data['module_bay']
        module_type_name = module_data['type']

        try:
            # Get module type
            module_type = module_types_dict.get(module_type_name)
            if not module_type:
                errors.append({
                    'device': device_name,
                    'module_bay': module_bay_name,
                    'status': 'error',
                    'message': f"Module type {module_type_name} not found or could not be created"
                })
                continue
        
            # Handle special naming and positioning for stacked switches
            stack_number = _extract_stack_number(device_name, module_data)
            new_position = module_data.get('new_position', None) if stack_number else None

            # Get module bay with stack-aware logic
            module_bay = get_module_bay(nb_session, device, module_bay_name, stack_number)

            # Create module bay if it doesn't exist
            if not module_bay:
                logger.info(f"Module bay {module_bay_name} not found, attempting to create for switch {device_name}")
                module_bay = create_module_bay(nb_session, device, module_bay_name, stack_number, new_position)

            if not module_bay:
                errors.append({
                    'device': device_name,
                    'module_bay': module_bay_name,
                    'status': 'error',
                    'message': f"Module bay {module_bay_name} not found and could not be created on device {device_name}"
                })
                continue

            # Check if module already exist
            nb_modules = nb_session.dcim.modules
            existing_modules_list = list(nb_modules.filter(device_id = device.id, module_bay_id = module_bay.id))

            ## Also check if there's a module of this type anywhere on the device than might have been moved
            if not existing_modules_list:
                same_type_modules = list(nb_modules.filter(device_id = device.id, module_type_id = module_type.id))
                if same_type_modules:
                    logger.info(f"Found {len(same_type_modules)} module(s) of type {module_type_name} on device {device_name} in other bays")
                    # Check if any of these modules are in the bay we're trying to use
                    for mod in same_type_modules:
                        if hasattr(mod, 'module_bay') and mod.module_bay and mod.module_bay.id == module_bay.id:
                            logger.warning(f"Module already exists in bay {module_bay_name}, using existing module ID {mod.id}")
                            existing_modules_list = [mod]
                            break

            if len(existing_modules_list) > 1:
                logger.warning(f"Found {len(existing_modules_list)} modules in bay {module_bay_name} (ID: {module_bay.id}) for device {device_name}")
                for mod in existing_modules_list:
                    logger.warning(f"\t- Module ID {mod.id}: {mod.module_type.model if hasattr(mod.module_type, 'model') else 'Unknown'}")

            existing_module = existing_modules_list[0] if existing_modules_list else None

            # Prepare payload 
            payload = {
                'device': device.id,
                'module_bay': module_bay.id,
                'module_type': module_type.id,
                # Store metadata for result reporting (these won't be sent to NetBox)
                '_device_name': device_name,
                '_module_bay_name': module_bay_name
            }

            # Add optional fields
            if 'serial' in module_data and module_data['serial']:
                payload['serial'] = module_data['serial'] 

            if 'asset_tag' in module_data and module_data['asset_tag']:
                payload['asset_tag'] = module_data['asset_tag']

            if 'status' in module_data and module_data['status']:
                payload['status'] = module_data['status']

            if existing_module:
                # Check if update is needed
                needs_update = False

                if existing_module.module_type.id != module_type.id:
                    needs_update = True

                # Check other fields (skip metadata fields starting with '_')
                if not needs_update:
                    for key, value in payload.items():
                        if not key.startswith('_') and key not in ['device', 'module_bay']:
                            if hasattr(existing_module, key):
                                existing_value = getattr(existing_module, key)
                                # Handle None values
                                if existing_value != value:
                                    needs_update = True
                                    break

                if needs_update:
                    payload['id'] = existing_module.id # Required for update
                    update_payloads.append(payload)
                else:
                    # No update needed
                    errors.append({
                        'device': device_name,
                        'module_bay': module_bay_name,
                        'module_id': existing_module.id,
                        'status': 'no_change',
                        'message': f"Module in bay {module_bay_name} already up to date"
                    })
            else:
                # New module. First check for conflicts first and
                if not check_module_interface_conflicts(nb_session, device, module_type, module_bay):
                    # New module - safe to create
                    create_payloads.append(payload)
                else:
                    # Interface conflict detected
                    logger.warning(f"Skipping module creation for {device_name} bay {module_bay_name} - interface conflicts detected")
                    errors.append({
                        'device': device_name,
                        'module_bay': module_bay_name,
                        'status': 'error',
                        'message': f"Cannot create module - interfaces from module type already exists on device"
                    })

        except Exception as e:
            errors.append({
                'device': module_data.get('device', 'unknown'),
                'module_bay': module_data.get('module_bay', 'unknown'),
                'status': 'error',
                'message': f"Error preparing payload: {str(e)}"
            })

            logger.error(f"Error preparing payload for {module_data.get('device', 'unknown')}: {e}", exc_info = True)

    return create_payloads, update_payloads, errors

def modules(nb_session: NetBoxApi, data: Dict[str, List[str]]) -> List[Dict[str, str | int]]:
    """
    Update switch modules on a NetBox server from YAML data.

    Args:
        nb_session: pynetbox API session
        data: Dictionary containing 'chassis' list
    Returns:
        List of device update payloads or None if no updated needed
    """

    if 'modules' not in data:
        logger.warning("No 'modules' key found in data")
        return []

    # Separate modules into create and update lists
    create_payloads, update_payloads, errors = prepare_module_payloads(nb_session, data['modules'])

    results = []

    # Handle error first
    results.extend(errors)

    nb_modules = nb_session.dcim.modules

    # Bulk create new modules
    if create_payloads:
        try:
            created_modules = _bulk_create(nb_modules, create_payloads, 'modules')
            for i, module in enumerate(created_modules):
                payload = create_payloads[i]
                results.append({
                    'device': payload['_device_name'],
                    'module_bay': payload['_module_bay_name'],
                    'module_id': module.id,
                    'status': 'created',
                    'message': f"Module created in bay {payload['_module_bay_name']}"
                })
        except Exception as e:
            logger.error(f"Bulk create failed: {e}", exc_info = True)
            # Add error entries for failed creates
            for payload in create_payloads:
                results.append({
                    'device': payload['_device_name'],
                    'module_bay': payload['_module_bay_name'],
                    'status': 'error',
                    'message': f"Bulk create failed: {str(e)}"
                })

    # Bulk update existing modules
    if update_payloads:
        try:
            updated_modules = _bulk_update(nb_modules, update_payloads, 'modules')
            for i, module in enumerate(updated_modules):
                payload = update_payloads[i]
                results.append({
                    'device': payload['_device_name'],
                    'module_bay': payload['_module_bay_name'],
                    'module_id': module.id,
                    'status': 'updated',
                    'message': f"Module updated in bay {payload['_module_bay_name']}"
                })
        except Exception as e:
            logger.error(f"Bulk update failed: {e}", exc_info = True)
            for payload in update_payloads:
                results.append({
                    'device': payload['_device_name'],
                    'module_bay': payload['_module_bay_name'],
                    'status': 'error',
                    'message': f"Bulk update failed: {str(e)}"
                })

    return results

#---- Debugging ----#
def show_module_on_device(nb_session: NetBoxApi, data = None):

    device_id = 599
    ic_name = "2/A"
    logger.info(f"Debugging '{ic_name}'s interfaces on the device with ID {device_id}")

    debug_device = nb_session.dcim.devices.get(device_id)
    logger.debug(debug_device)
    if debug_device:
        logger.info(f"Device: {debug_device.name}")
        interfaces = nb_session.dcim.interfaces.filter(device_id = device_id, name__ic = ic_name)
        for iface in interfaces:
            logger.info(f"\tInterface: {iface.name}, Module: {iface.module}")


if __name__ == '__main__':
    from pynetbox_functions import _main, _debug
    #_main("Processing modules data on a NetBox server", modules)

    # Debug
    _debug(show_module_on_device)
    _debug(modules)
