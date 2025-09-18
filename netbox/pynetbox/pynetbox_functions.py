#!/usr/bin/env python3

'''
Specific pynetbox functions
'''

import pynetbox, yaml, logging, argparse

from pathlib import Path
from typing import Callable

# Configure logging
logging.basicConfig(level = logging.INFO)
logger = logging.getLogger(__name__)

def read_data(nb_session):
    for device in nb_session.dcim.devices.all():
        logger.info(f"{device.name} ({device.device_type.display}) in {device.site.name}")

def load_yaml(file_path):
    yaml_file = Path(file_path)

    with yaml_file.open('r') as f:
        return yaml.safe_load(f)

def _bulk_create_with_fallback(endpoint, payloads, kind):
    """
    Bulk create objects on a NetBox platform
    Args:
        endpoint: pynetbox endpoint space in form of response.Response
        payloads: A list of objects characteristics dictionaries to add to NetBox
        kind: A string describing the objects to create
    """
    if not payloads: return []

    created = []

    try:
        # pynetbox accepts a list as the first argument to create()
        created = endpoint.create(payloads)
        logger.info(f"Bulk-created {len(created)} {kind}(s).")
        return created
    except Exception as exc:
        logger.warning(f"Bulk create for {kind} failed ({exc}), falling back to per-item create.")
        created = []
        for payload in payloads:
            try: 
                obj = endpoint.create(payload)
                created.append(obj)
            except Exception as exc2:
                logger.error(f"Failed to create {kind} {payload.get('name')}: {exc2}")
        return created

def _delete_netbox_obj(obj):
    """
    Delete a provided NetBox object (obj)
    Args:
        obj: pynetbox response.Response Object to delete from the NetBox platform
    """
    if not obj: return False

    if not isinstance(obj, pynetbox.core.response.Record): 
        logger.info(f"Skiping non-Record object: {obj!r}")
        return  False

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
            logger.error(f"Failed to delete {obj.name}: {detail or e}")
        return False
    except Exception as exc:
        logger.error(f"Unexpected error deleting {getattr(obj, 'name', obj)}: {exc}")
        return False

def _main(description: str, function: Callable, **kwargs):
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