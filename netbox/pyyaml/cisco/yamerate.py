#!/usr/bin/env python3

# Collect Cisco devices data and create yaml configs file 

import logging, sys
logger = logging.getLogger(__name__)

from json_functions import devices_json
from std_functions import data_folder


def cisco_ios(data_folder, output_file_path = sys.stdout):
    logger.info(f"DATA FOLDER: {data_folder}")

if __name__ == "__main__":
    #from std_functions import _main
    #_main(cisco_ios)

    # -- Debugging 
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from functions import _debug

    _debug(devices_json, data_folder)
