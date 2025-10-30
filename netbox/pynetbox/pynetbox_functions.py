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

    try:
        # pynetbox accepts a list as the first argument to create()
        created = endpoint.create(payloads)
        logger.info(f"Bulk-created {len(created)} {kind}(s).")
        return created
    except Exception as exc:
        logger.warning(
            f"Bulk create for {kind} failed ({exc}), falling back to per-item create.",
            exc_info = True
        )
        created = []
        for payload in payloads:
            try: 
                obj = endpoint.create(payload)
                created.append(obj)
            except Exception as exc2:
                logger.error(
                    f"Failed to create {kind} {payload.get('name')}: {exc2}", 
                    exc_info = True
                )
        return created

def _bulk_update(endpoint: Endpoint, payloads: List[Dict], kind: str) -> List:
    """
    Bulk update objects on a NetBox platform, with individual fallback on failure. 
    Args:
        endpoint: pynetbox endpoint space
        payloads: A list of objects characteristics dictionaries to add to NetBox
        kind: A string describing the objects to create
    """
    if not payloads: return []

    try:
        # Bulk update
        return endpoint.update(payloads)
    except Exception as e:
        logger.warning(f"Bulk update failed for {kind}, falling back to individual updates: {e}")

        # Cache all objects that need to be updated to minimize API calls
        object_ids = [payload.get('id') for payload in payloads if 'id' in payload.keys()]
        if not object_ids:
            logger.error(f"No valid IDs found in payloads for {kind}", exc_info = True)
            return []

        try:
            # Fetch all objects in one call using filter
            cached_objects = {obj.id: obj for obj in endpoint.filter(id = object_ids)}
        except Exception as e:
            logger.warning(f"Failed to cache {kind} objects, falling back to individual gets: {e}")
            cached_objects = {}

        updated_items = []
        successful_update = 0

        for payload in payloads:
            item_id = payload.pop('id')
            if not item_id:
                logger.warning(f"Skipping {kind} payload without ID")
                continue

            try:
                # Try to get from cache first, fallback to individual get
                updated_item = cached_objects.get(item_id)
                if not updated_item:
                    updated_item = endpoint.get(item_id)
                    if not updated_item:
                        logger.error(f"Could not find {kind} with ID {item_id}", exc_info = True)
                        continue

                # Track changes
                changes_made = False
                changes_log = []

                # Apply updates only if values are different
                for key, value in payload.items():
                    if key == 'id': continue # Skip the id field

                current_value = getattr(updated_item, key, None)
                if current_value != value:
                    setattr(updated_item, key, value)
                    changes_made = True
                    changes_log.append(f"{key}: {current_value} -> {value}")

                # Only save if changes were made
                if changes_made:
                    updated_item.save()
                    updated_items.append(updated_item)
                    successful_update += 1
                    logger.info(f"Successfully updated {kind} ID {item_id}: {', '.join(changes_log)}")
                else:
                    logger.debug(f"No changes for {kind} ID {item_id}")

            except Exception as e:
                logger.error(f"Failed to update individual {kind} with ID {item_id}: {e}", exc_info = True)

        if successful_update > 0:
            logger.info(f"Individual fallback completed: {successful_update}/{len(payloads)} {kind} updated successfully")       

        return updated_items

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
        "aruba_stack_2930.yaml"
    ]
    
    for file_name in files_yaml:
        data_file_path = f"{main_folder}/data/yaml/{file_name}"
        data = load_yaml(data_file_path)

        # Call the passed function, with additional arguments
        function(nb, data, **kwargs)

def _debug(function: Callable, **kwargs) -> None:
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
        "aruba_stack_2920.yaml"
    ]

    for file_name in files_yaml:
        data_file_path = f"{main_folder}/data/yaml/{file_name}"
        data = load_yaml(data_file_path)

    function(nb, data, **kwargs)