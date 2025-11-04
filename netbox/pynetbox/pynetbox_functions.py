#!/usr/bin/env python3

'''
Project specific functions for pynetbox based apps
'''

import pynetbox, yaml, logging, argparse

from pathlib import Path
from typing import Callable, Dict, List

from pynetbox.core.api import Api as NetBoxApi
from pynetbox.models.dcim import Devices
from pynetbox.core.endpoint import Endpoint
from pynetbox.core.response import Record

# Configure logging
logger = logging.getLogger(__name__)

def read_data(nb_session: NetBoxApi) -> None:
    for device in nb_session.dcim.devices.all():
        logger.info(f"{device.name} ({device.device_type.display}) in {device.site.name}")

def load_yaml(file_path: Path) -> Dict:
    yaml_file = Path(file_path)

    with yaml_file.open('r') as f:
        return yaml.safe_load(f)

def _get_device(nb_session: NetBoxApi, name: str) -> Devices:
    """
    Get an existing device object from an active NetBox session
    Args:
        nb_session: pynetbox API session
        name: device hostname (str)
    Return:
        Device object
    """
    d_obj = None
    try:
        d_obj = nb_session.dcim.devices.get(name = name)
        if not d_obj: 
            logger.warning(f"Device {name} not found in NetBox")
    except Exception as e:
        logger.error(f"Error retrieving device {d_name}: {e}", exc_info = True)

    return d_obj

def _extract_stack_number(device_name: str, data: Dict[str, str]) -> str:
    """
    Extract stack number from device name or data dictionary.
    Args:
        device_name: Device hostname (e.g rsgw0001-1)
        data: Data dictionary (e.g data['modules'])
    Return:
        Stack number as string or None if it's not a stack
    """
    # If 'new_position' in data dict
    if 'new_position' in data and '/' in data['new_position']:
        return data['new_position'].split('/')[0]
    
    # Stack number provided in the data dict
    if 'stack_number' in data:
        return str(data['stack_number'])

    # Check the device name
    if '-' in device_name:
        parts = device_name.split('-')
        last_part = parts[-1]
        if last_part.isdigit():
            return last_part

    return None

def _cache_devices(nb_session: NetBoxApi, device_names: List[str]) -> Dict[str, object]:
    """
    Get devices in a bulk and return them as cached dictionary
    Args:
        nb_session: pynetbox API session
        device_names: A list of device hostnames
    Return:
        Dictionary of device objects in the form of:
            hostname: device object
    """
    devices = nb_session.dcim.devices.filter(name = device_names)

    # Extend search if nothing is found
    if not devices:
        devices = nb_session.dcim.devices.filter(name__in = device_names)

    return {device.name: device for device in devices}

def _bulk_create(endpoint: Endpoint, payloads: List[Dict], kind: str) -> List:
    """
    Bulk create objects on a NetBox platform
    Args:
        endpoint: pynetbox endpoint space
        payloads: A list of objects characteristics dictionaries to add to NetBox
        kind: A string describing the objects to create
    Returns:
        List of successfully created objects.
    """
    if not payloads: 
        return []

    # Chunk large updates to avoid 504 Gateway Timeout
    chunk_size = 500

    if len(payloads) <= chunk_size:
        # Small batch - try bulk create directly
        try:
            logger.debug(f"Attempting bulk create of {len(payloads)} {kind} object(s)")
            created = endpoint.create(payloads)
            logger.info(f"Bulk-created {len(created)} {kind}(s).")
            return created
        except Exception as exc:
            logger.warning(
                f"Bulk create for {kind} failed ({exc}), falling back to individual creates.",
                exc_info=True
            )
            # Fall through to individual create fallback
    else:
        # Large batch - chunk it
        logger.info(f"Chunking {len(payloads)} {kind} creates into batches of {chunk_size}")
        all_created = []
        
        for i in range(0, len(payloads), chunk_size):
            chunk = payloads[i:i + chunk_size]
            chunk_num = (i // chunk_size) + 1
            total_chunks = (len(payloads) + chunk_size - 1) // chunk_size
            
            try:
                logger.debug(f"Creating chunk {chunk_num}/{total_chunks} ({len(chunk)} {kind}s)")
                created = endpoint.create(chunk)
                all_created.extend(created)
                logger.info(f"Chunk {chunk_num}/{total_chunks}: Created {len(created)} {kind}(s)")
            except Exception as exc:
                logger.warning(
                    f"Chunk {chunk_num}/{total_chunks} failed ({exc}), falling back to individual creates for this chunk"
                )
                # Fall back to individual creates for this chunk only
                individual_created = _individual_create_fallback(endpoint, chunk, kind)
                all_created.extend(individual_created)
        
        if all_created:
            logger.info(f"Completed chunked create: {len(all_created)}/{len(payloads)} {kind}(s) created")
        return all_created

    # Bulk create failed, fall back to individual creates
    return _individual_create_fallback(endpoint, payloads, kind)

def _individual_create_fallback(endpoint: Endpoint, payloads: List[Dict], kind: str) -> List:
    """
    Fallback to individual creates when bulk create fails.
    
    Args:
        endpoint: pynetbox endpoint space
        payloads: List of object dictionaries to create
        kind: Object type description
    
    Returns:
        List of successfully created objects
    """
    created = []
    failed = 0
    
    for payload in payloads:
        try:
            obj = endpoint.create(payload)
            created.append(obj)
            
            # Extract identifier for logging
            identifier = _extract_identifier(payload, obj)
            logger.debug(f"Successfully created {kind}: {identifier}")
            
        except Exception as exc:
            failed += 1
            identifier = _extract_identifier(payload)
            
            # Try to extract more specific error info
            error_detail = _extract_error_detail(exc)
            
            logger.error(
                f"Failed to create {kind} '{identifier}': {error_detail}",
                exc_info=True
            )
    
    # Summary logging
    if created:
        logger.info(
            f"Individual fallback completed: {len(created)}/{len(payloads)} {kind}(s) created successfully"
        )
    if failed > 0:
        logger.warning(f"Failed to create {failed}/{len(payloads)} {kind}(s)")
    
    return created

def _extract_identifier(payload: Dict, obj: object = None) -> str:
    """
    Extract a meaningful identifier from payload or created object for logging.
    
    Tries multiple fields in order of preference:
    1. Object name (if obj provided)
    2. Payload 'name'
    3. Payload 'interface' (for interfaces)
    4. Payload 'hostname'
    5. Payload 'device' + 'name'
    6. First 50 chars of payload
    
    Args:
        payload: Object dictionary
        obj: Created object (optional)
    
    Returns:
        String identifier for logging
    """
    # Try object name first
    if obj and hasattr(obj, 'name'):
        return str(obj.name)
    
    # Try common identifier fields
    for field in ['name', 'interface', 'hostname', 'display', 'slug']:
        if field in payload:
            return str(payload[field])
    
    # Try composite identifiers
    if 'device' in payload and 'name' in payload:
        device = payload['device']
        name = payload['name']
        # Handle case where device is an ID vs name
        device_str = str(device) if isinstance(device, (int, str)) else 'device'
        return f"{device_str}/{name}"
    
    # Last resort - show first part of payload
    payload_str = str(payload)
    if len(payload_str) > 50:
        return f"{payload_str[:47]}..."
    return payload_str


def _extract_error_detail(exc: Exception) -> str:
    """
    Extract meaningful error details from exception.
    
    Tries to extract:
    1. NetBox validation errors (field-specific)
    2. HTTP error details
    3. Generic error message
    
    Args:
        exc: Exception object
    
    Returns:
        String with error details
    """
    # Try to get NetBox validation error details
    if hasattr(exc, 'error'):
        error_data = exc.error
        
        # NetBox often returns field-specific errors
        if isinstance(error_data, dict):
            errors = []
            for field, messages in error_data.items():
                if isinstance(messages, list):
                    for msg in messages:
                        errors.append(f"{field}: {msg}")
                else:
                    errors.append(f"{field}: {messages}")
            if errors:
                return "; ".join(errors)
    
    # Try to get HTTP status code
    if hasattr(exc, 'req') and hasattr(exc.req, 'status_code'):
        status = exc.req.status_code
        return f"HTTP {status}: {str(exc)}"
    
    # Fallback to exception message
    return str(exc)

def _bulk_update(endpoint: Endpoint, payloads: List[Dict], kind: str) -> List:
    """
    Args:
        endpoint: pynetbox endpoint space
        payloads: A list of objects characteristics dictionaries to update in NetBox
                  Each payload MUST have an 'id' field
        kind: A string describing the objects to update
    
    Returns:
        List of successfully updated objects
    """
    if not payloads:
        return []

    # Validate all payloads have IDs before attempting bulk update
    object_ids = [payload.get('id') for payload in payloads]
    if not all(object_ids):
        logger.warning(f"Some {kind} payloads missing 'id' field, cannot bulk update")
        # Filter to only valid payloads
        payloads = [p for p in payloads if p.get('id')]
        object_ids = [p['id'] for p in payloads]
        
        if not payloads:
            logger.error(f"No valid payloads with IDs for {kind}")
            return []

    # Chunk large updates to avoid 504 Gateway Timeout
    chunk_size = 500

    if len(payloads) <= chunk_size:
        # Small batch - try bulk update directly
        try:
            # Attempt bulk update
            logger.debug(f"Attempting bulk update of {len(payloads)} {kind} object(s)")
            updated = endpoint.update(payloads)
            logger.info(f"Bulk-updated {len(updated)} {kind}(s).")
            return updated
        except Exception as e:
            logger.warning(
                f"Bulk update failed for {kind} ({e}), falling back to individual updates.",
                exc_info=True
            )

    else:
        # Large batch - chunk it
        logger.info(f"Chunking {len(payloads)} {kind} updates into batches of {chunk_size}")
        all_updated = []

        for i in range(0, len(payloads), chunk_size):
            chunk = payloads[i:i + chunk_size]
            chunk_num = (i // chunk_size) + 1
            total_chunks = (len(payloads) + chunk_size -1) // chunk_size

            try:
                logger.debug(f"Updating chunk {chunk_num}/{total_chunks} ({len(chunk)} {kind}s)")
                updated = endpoint.update(chunk)
                all_updated.extend(updated)
                logger.info(f"Chunk {chunk_num}/{total_chunks}: Updated {len(updated)} {kind}(s)")
            except Exception as e:
                logger.warning(
                    f"Chunk {chunk_num}/{total_chunks} failed ({e}), "
                    "falling back to individual updates for this chunk"
                )
                # Fall back to individual updates for this chunk only
                chunk_ids = [p.get('id') for p in chunk]
                individual_updated = _individual_update_fallback(endpoint, chunk, chunk_ids, kind)
                all_updated.extend(individual_updated)

        if all_updated:
            logger.info(f"Completed chunked update: {len(all_updated)}/{len(payloads)} {kind}(s) updated")
        return all_updated

    # Bulk update failed, fall back to individual updates
    return _individual_update_fallback(endpoint, payloads, object_ids, kind)

def _individual_update_fallback(endpoint: Endpoint, payloads: List[Dict], 
                                object_ids: List[int], kind: str) -> List:
    """
    Fallback to individual updates when bulk update fails.
    
    Args:
        endpoint: pynetbox endpoint space
        payloads: List of update payloads
        object_ids: List of object IDs to update
        kind: Object type description
    
    Returns:
        List of successfully updated objects
    """
    # Cache all objects that need to be updated to minimize API calls
    cached_objects = _cache_objects_for_update(endpoint, object_ids, kind)
    
    updated_items = []
    successful_update = 0
    skipped_no_changes = 0

    for payload in payloads:
        item_id = payload.get('id')  # Don't pop - preserve original data
        
        if not item_id:
            logger.warning(f"Skipping {kind} payload without ID")
            continue

        try:
            # Get object from cache or fetch individually
            updated_item = cached_objects.get(item_id)
            if not updated_item:
                updated_item = endpoint.get(item_id)
                if not updated_item:
                    logger.error(f"Could not find {kind} with ID {item_id}")
                    continue

            # Apply updates and track changes
            changes_made, changes_log = _apply_updates_to_object(
                updated_item, payload, item_id, kind
            )

            # Only save if changes were made
            if changes_made:
                updated_item.save()
                updated_items.append(updated_item)
                successful_update += 1
                logger.info(
                    f"Successfully updated {kind} ID {item_id}: {', '.join(changes_log)}"
                )
            else:
                skipped_no_changes += 1
                logger.debug(f"No changes needed for {kind} ID {item_id}")

        except Exception as e:
            logger.error(
                f"Failed to update individual {kind} with ID {item_id}: {e}", 
                exc_info=True
            )

    # Summary logging
    if successful_update > 0:
        logger.info(
            f"Individual fallback completed: {successful_update}/{len(payloads)} {kind} "
            f"updated successfully, {skipped_no_changes} unchanged"
        )
    elif skipped_no_changes > 0:
        logger.info(f"No changes needed for {skipped_no_changes} {kind} object(s)")

    return updated_items

def _cache_objects_for_update(endpoint: Endpoint, object_ids: List[int], kind: str) -> Dict[int, object]:
    """
    Cache objects by ID for efficient updates.
    
    Args:
        endpoint: pynetbox endpoint space
        object_ids: List of object IDs to cache
        kind: Object type description
    
    Returns:
        Dictionary mapping ID to object
    """
    try:
        # Fetch all objects in one call using filter
        # Chunk if there are too many IDs (NetBox may have limits)
        chunk_size = 100
        cached_objects = {}
        
        for i in range(0, len(object_ids), chunk_size):
            chunk = object_ids[i:i + chunk_size]
            objects = endpoint.filter(id=chunk)
            for obj in objects:
                cached_objects[obj.id] = obj
        
        logger.debug(f"Cached {len(cached_objects)} {kind} object(s) for update")
        return cached_objects
        
    except Exception as e:
        logger.warning(
            f"Failed to cache {kind} objects, will fetch individually: {e}"
        )
        return {}

def _apply_updates_to_object(obj: object, payload: Dict, obj_id: int, kind: str) -> tuple:
    """
    Apply updates from payload to object and track changes.
    
    Args:
        obj: NetBox object to update
        payload: Dictionary of fields to update
        obj_id: Object ID (for logging)
        kind: Object type description
    
    Returns:
        Tuple of (changes_made: bool, changes_log: List[str])
    """
    changes_made = False
    changes_log = []

    for key, value in payload.items():
        # Skip the id field and internal fields
        if key in ('id', '_choices'):
            continue

        try:
            current_value = getattr(obj, key, None)
            
            # Normalize values for comparison
            normalized_current = _normalize_value(current_value)
            normalized_new = _normalize_value(value)
            
            # Check if value actually changed
            if normalized_current != normalized_new:
                setattr(obj, key, value)
                changes_made = True
                
                # Format change log entry
                current_display = _format_value_for_log(current_value)
                new_display = _format_value_for_log(value)
                changes_log.append(f"{key}: {current_display} -> {new_display}")
                
        except AttributeError:
            logger.warning(
                f"Field '{key}' does not exist on {kind} ID {obj_id}, skipping"
            )
        except Exception as e:
            logger.warning(
                f"Error setting field '{key}' on {kind} ID {obj_id}: {e}"
            )

    return changes_made, changes_log

def _normalize_value(value):
    """
    Normalize a value for comparison.
    
    Handles:
    - Nested NetBox objects (compare by ID)
    - None vs empty string
    - Lists vs tuples
    - Case-sensitive strings
    
    Args:
        value: Value to normalize
    
    Returns:
        Normalized value for comparison
    """
    # Handle None
    if value is None:
        return None
    
    # Handle NetBox objects (compare by ID)
    if hasattr(value, 'id'):
        return value.id
    
    # Handle lists/tuples
    if isinstance(value, (list, tuple)):
        # Normalize list items recursively
        return tuple(_normalize_value(item) for item in value)
    
    # Handle dictionaries (shouldn't happen often, but just in case)
    if isinstance(value, dict):
        return tuple(sorted(value.items()))
    
    # Return as-is for primitives (str, int, float, bool)
    return value

def _format_value_for_log(value) -> str:
    """
    Format a value for display in logs.
    
    Args:
        value: Value to format
    
    Returns:
        String representation suitable for logs
    """
    if value is None:
        return "None"
    
    # NetBox objects - show name and ID if available
    if hasattr(value, 'id'):
        if hasattr(value, 'name'):
            return f"{value.name} (ID: {value.id})"
        elif hasattr(value, 'display'):
            return f"{value.display} (ID: {value.id})"
        else:
            return f"ID: {value.id}"
    
    # Lists/tuples - show count
    if isinstance(value, (list, tuple)):
        if len(value) > 5:
            return f"[{len(value)} items]"
        else:
            return str(value)
    
    # Strings - truncate if too long
    if isinstance(value, str) and len(value) > 50:
        return f"{value[:47]}..."
    
    return str(value)

def _delete_netbox_obj(obj: Record) -> bool:
    """
    Delete a provided NetBox object (obj)
    Args:
        obj: pynetbox response.Response Object to delete from the NetBox platform
    """
    if not obj: return False

    try: 
        obj.delete()
        logger.info(f"Removed {obj.name}, with id {obj.id}")
        return True
    except pynetbox.core.query.RequestError as e:
        # safe access to underlying HTTP response status code
        status = getattr(getattr(e, "req", None), "status_code", None)
        # try to get the server-provided error detail if present
        detail = getattr(e, "error", None) or getattr(e, "args", None)

        if status == 409:
            logger.info(f"Skipped {obj.name} (has dependencies). Detail: {detail}")
        else:
            logger.error(f"Failed to delete {obj.name}: {detail or e}", exc_info = True)
        return False
    except Exception as exc:
        logger.error(f"Unexpected error deleting {getattr(obj, 'name', obj)}: {exc}", exc_info = True)
        return False

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

def _resolve_tags(nb_session: NetBoxApi, tags: List[str] | str | None) -> List[int]:
    """
    Resolve tag names to tag IDs, creating tags if they don't exist.
    Args:
        nb_session: pynetbox API session
        tags: string, list of strings, None
    Returns: 
        List of IDs
    """
    if not tags: return []

    # Normalize to list
    tag_slugs = [tags] if isinstance(tags, str) else tags
    tag_ids = []

    nb_tags = nb_session.extras.tags
    for tag_slug in tag_slugs:
        try:
            # Try to get existing tag
            tag = nb_tags.get(slug = tag_slug)
            tag_ids.append(tag.id)

        except Exception as e:
            logger.warning(f"Error resolving tag '{tag_slug}': {e}")
            continue

    return tag_ids

def _manufacturer(nb_session: NetBoxApi, manufacturer_name: str) -> int:
    """
    Get or create a manufacturer and return its ID.
    Args:
        nb_session: pynetbox API session
        manufacturer_name: manufacturer's name
    Returns: 
        Manufacturer ID
    """
    nb_manufacturers = nb_session.dcim.manufacturers
    manufacturer = nb_manufacturers.get(name = manufacturer_name)

    if manufacturer:
        return manufacturer.id

    try:
        new_manufacturer = nb_manufacturers.create({
            'name': manufacturer_name,
            'slug': manufacturer_name.lower().replace(' ', '-')
        })
        return new_manufacturer.id
    except Exception as e:
        logging.error(f"Failed to create manufacturer {manufacturer_name}: {e}", exc_info = True)
        raise


def _main(description: str, function: Callable, **kwargs) -> None:
    """
    Initialize NetBox API with custom session
    Args:
        description: String describing what the script does
        function: function to execute, that should contain, as arguments, at least:
            nb_session: pynetbox API session
            data: Data dictionary
    """
    import argparse
    from std_functions import main_folder
    from nb import development, production

    # Disable warnings about self-signed certificates
    from urllib3 import disable_warnings, exceptions
    disable_warnings(exceptions.InsecureRequestWarning)

    # Configure logging
    logging.basicConfig(level = logging.INFO)

    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        '-s', "--server",
        choices = ["development", "production"],
        default= "development",
        help = "Select which NetBox server to connect to (default: development)"
    )

    args = parser.parse_args()

    if args.server == "development":
        nb = development
    elif args.server == "production":
        nb = production

    nb.http_session.verify = False # Disable SSL verification

    files_yaml = [
        #"aruba_stack_2930.yaml"
        "procurve_modular"
    ]
    
    for file_name in files_yaml:
        data_file_path = f"{main_folder}/data/yaml/{file_name}"
        data = load_yaml(data_file_path)

        # Call the passed function, with additional arguments
        function(nb, data, **kwargs)

def _debug(description: str, function: Callable, **kwargs) -> None:
    """
    Debug NetBox API with custom session
    Args:
        function: debug function to execute, that must have:
            nb_session: pynetbox API session
        as argument.
    """
    import argparse
    from std_functions import main_folder
    from nb import development, production

    # Set DEBUG logging output
    logging.basicConfig(level = logging.DEBUG)

    # Disable warnings about self-signed certificates
    from urllib3 import disable_warnings, exceptions
    disable_warnings(exceptions.InsecureRequestWarning)

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-s', "--server",
        choices = ["development", "production"],
        default= "development",
        help = "Select which NetBox server to connect to (default: development)"
    )

    args = parser.parse_args()

    if args.server == "development":
        nb = development
    elif args.server == "production":
        nb = production

    nb.http_session.verify = False # Disable SSL verification

    files_yaml = [
        "aruba_stack_2930.yaml"
    ]

    for file_name in files_yaml:
        data_file_path = f"{main_folder}/data/yaml/{file_name}"
        data = load_yaml(data_file_path)

    function(nb, data, **kwargs)