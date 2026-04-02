#!/usr/bin/env  python3

import logging, yaml

from pathlib import Path

from pynetbox.core.api import Api as NetBoxApi

script_dir = Path(__file__).resolve().parent
project_dir = script_dir.parent

# Configure logging
logger = logging.getLogger(__name__)

def _main(description: str, function: callable, **kwargs) -> None:
    """
    Initialize NetBox API with custom session
    Args:
        description: String describing what the script does
        function: function to execute, that should contain, as arguments, at least:
            nb_session: pynetbox API session
            data: Data dictionary
    """
    import argparse, sys

    pynetbox_dir = Path(__file__).resolve().parent.parent / 'pynetbox'
    sys.path.insert(0, str(pynetbox_dir))
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

    nb = production if args.server == "production" else development
    nb.http_session.verify = False # Disable SSL verification

    return function(nb, **kwargs)

def _cache_devices(nb_session: NetBoxApi) -> dict[str, object]:
    """
    Fetch all devices from NetBox and return them as a cached dictionary.
    Args:
        nb_session: pynetbox API session
    Returns:
        Dictionary mapping hostname -> pynetbox device object
    """

    logger.info("Fetching all devices from NetBox...")

    devices = nb_session.dcim.devices.all()

    device_cache = {device.name: device for device in devices}

    logger.info(f"Cached {len(device_cache)} devices.")

    return device_cache


# Not needed now, as I use auto_db.py seed and merge
def decommissioned_devices(nb_session: NetBoxApi) -> dict[str, list[str]]:
    """
    Collect decommissioned devices.
    Args:
        nb_session: pynetbox API session
    Returns:
        Dictionary mapping serial number (or name if serial is absent) -> [asset_tag, name]
        for devices with status 'offline' or 'decommissioning' whose name starts with
        'rs', 'rh', 'rg', or 'rw'.
    """
    PREFIXES  = ('rs', 'rh', 'rg', 'rw')
    STATUSES  = {'offline', 'decommissioning'}

    devices = _cache_devices(nb_session)

    result = {}
    for name, device in devices.items():
        if not name or not name.lower().startswith(PREFIXES):
            continue
        if str(device.status.value) not in STATUSES:
            continue

        serial    = device.serial   or None
        asset_tag = str(device.asset_tag) if device.asset_tag else None
        key       = serial if serial else name

        result[key] = [asset_tag, name]
        logger.info(f"Found decommissioned device: {name} (key={key})")

    logger.info(f"Total decommissioned devices found: {len(result)}")

    d_file = project_dir / "data" / "yaml" / "decommissioned.yaml"
    with open(d_file, 'w') as f:
        yaml.dump(result, f)

    return result



def delist(nb_session: NetBoxApi) -> None:
    """
    Delist decommissioned or inactive devices from active inventory, i.e:
    - free the hostname (rename them as SN), if it starts with 'rs', 'rh', 'rg' or 'rw'
    - save the hostname to description, for reference
    - set status to 'decommissioning' 
    """
    from functions import serial_numbers

    inactive_serials = serial_numbers(inactive_only = True)

    logger.info(inactive_serials)

    return


if __name__ == "__main__":
    cache = _main("Find decommissioned devices", decommissioned_devices)

    for serial, (asset_tag, name) in cache.items():
        print(f"{serial}: [{asset_tag}, {name}]")

    #from functions import _debug
    #_debug(serial_numbers, inactive_only = True)

