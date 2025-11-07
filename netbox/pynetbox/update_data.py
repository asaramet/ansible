#!/usr/bin/env python3

'''
Update/add data to a NetBox platform using `pynetbox` library
Main function, to import:

- update(nb_session, data):
    - nb_session - NetBox HTTPS session
    - data - data (yaml format)
'''

import logging

from typing import Dict, List
from pynetbox.core.api import Api as NetBoxApi

from add_locations import add_locations
from switches import switches
from modules import module_bays, modules
from vlans import vlans
from interfaces import interfaces, delete_device_interfaces
#from lags import lags
#from ips import ips

# Get logger
logger = logging.getLogger(__name__)

def update(nb_session: NetBoxApi, data: Dict[str, List[str]]) -> None:
    """
    Update/Add data to a NetBox server from YAML data.

    Args:
        nb_session: pynetbox API session
        data: Data dictionary containing lists
    """
    #logger.info("-- Add missing locations --")
    #add_locations(nb_session, data)

    logger.info("-- Update/Add switches data --")
    switches(nb_session, data)

    logger.info("-- Synchronize VLANs --")
    vlans(nb_session, data)

    logger.info("-- Update/Add missing switch modules --")
    delete_device_interfaces(nb_session, data)
    module_bays(nb_session, data)
    modules(nb_session, data)

    logger.info("-- Update interfaces --")
    interfaces(nb_session, data)

    logger.info("-- Synchronize LAG interfaces --")
#    trunks(nb_session, data)

#    logger.info("-- Assign IPs to devices --")
#    ips(nb_session, data)

if __name__ == '__main__':
    from pynetbox_functions import _main
    _main("Update/add data to a NetBox server", update)