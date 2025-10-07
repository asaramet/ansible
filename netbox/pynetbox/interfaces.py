#!/usr/bin/env python3

'''
Synchronize device interfaces on a NetBox platform using `pynetbox` library
Main function, to import:

- interfaces(nb_session, data):
    - nb_session - pynetbox API session
    - data - data (yaml format)
'''

import pynetbox, logging

from typing import Dict, List
from pynetbox.core.api import Api as NetBoxApi

from pynetbox_functions import _bulk_create

# Configure logging
#logging.basicConfig(level = logging.INFO)
logging.basicConfig(level = logging.DEBUG)
logger = logging.getLogger(__name__)

def interfaces(nb_session: NetBoxApi, data: Dict[str, List[str]]) -> None:
    """
    Create or update interfaces in NetBox based on YAML data.
    Args:
        nb_session: pynetbox API session
        data: Dictionary containing 'device_interfaces' list
    """
    if 'device_interfaces' not in data:
        logger.warning("No 'device_interfaces' key found in data")
        return

    device_interfaces = data.get('device_interfaces', [])
    if not device_interfaces:
        logger.info("No interfaces to process")
        return

    # Cache all devices mentioned in the data
    device_names = list(set(item['hostname'] for item in device_interfaces))
    logger.debug(device_names)

if __name__ == '__main__':
    from pynetbox_functions import _main
    _main("Synchronizing device interfaces", interfaces)