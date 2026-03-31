#!/usr/bin/env python3

"""
Manage devices inventory database 

- Back up serial and inventory numbers from NetBox data to a local yaml file.
"""

import pynetbox, logging, yaml

from pathlib import Path

from pynetbox.core.api import Api as NetBoxApi

logger = logging.getLogger(__name__)

script_dir = Path(__file__).resolve().parent
project_dir = script_dir.parent

def _cache_devices(nb_session: NetBoxApi) -> dict[str, object]:
    """
    Get all devices from NetBox and return them as a cached dictionary.
    Args:
        nb_session: pynetbox API session
    Return:
        dictionary of device objects in the form of:
            hostname: device object
    """
    devices = nb_session.dcim.devices.all()

    return {device.name: device for device in devices}

def backup(nb_session: NetBoxApi) -> None:

    devices_cache = _cache_devices(nb_session)

    data = {}

    b_file = project_dir / 'data' / 'backup_db.yaml'

    for name, obj in devices_cache.items():
        data[name] = [obj['serial'], obj['asset_tag'], obj['status']['value']]

    logger.info("Backup NetBox device data to local backup yaml file")

    with open(b_file, 'w') as f:
        yaml.dump(data, f)

    return 

def _main(description: str, function: callable, **kwargs) -> None:
    """
    Initialize NetBox API with custom session
    Args:
        description: String describing what the script does
        function: function to execute, that should contain, as arguments, at least:
            nb_session: pynetbox API session
            data: Data dictionary
    """
    import argparse
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

    function(nb, **kwargs)

if __name__ == '__main__':
    _main("Backup NetBox data to a local YAML file", backup)