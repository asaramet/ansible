#!/usr/bin/env python3

# Return Cisco devices JSON objects

import logging
from std_functions import data_folder

logger = logging.getLogger(__name__)

def devices_json(data_folder):
    data = {'devices': [], 'chassis': []}

    logger.debug(data_folder)

if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from functions import _debug

    _debug(devices_json, data_folder)
