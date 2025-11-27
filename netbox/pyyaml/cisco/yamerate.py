#!/usr/bin/env python3

# Collect Cisco devices data and create yaml configs file 

import logging, sys, yaml
logger = logging.getLogger(__name__)

from json_functions import devices_json, modules_json, lags_json
from std_functions import data_folder


def cisco_ios(data_folder, output_file = sys.stdout):
    """
    Generate YAML configuration file from Cisco device configs.

    Args:
        data_folder: Path to folder containing Cisco config files
        output_file: Output file name

    Example:
        cisco_ios(data_folder, "cisco.yaml")
    """
    # For debugging output_file_path will be stdout
    if output_file == sys.stdout:
        f = sys.stdout
    else:
        output = data_folder.joinpath("yaml", output_file) # same data folder, different directory
        output.parent.mkdir(parents = True, exist_ok = True) # ensure the folder exists
        f = open(output, 'w')
    try:
        yaml.dump(devices_json(data_folder), f)
        yaml.dump(modules_json(data_folder), f)
        yaml.dump(lags_json(data_folder), f)
        #yaml.dump(device_interfaces_json(files), f)
        #yaml.dump(vlans_json(files), f)
        #yaml.dump(tagged_vlans_json(files), f)
        #yaml.dump(ip_addresses_json(files), f)
    finally:
        if f is not sys.stdout: # Don't close stdout
            f.close()
            logger.info(f"Generated YAML config: {output}")

if __name__ == "__main__":
    from std_functions import _main
    #_main(cisco_ios, data_folder, "cisco.yaml")

    # -- Debugging 
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from functions import _debug

    #_debug(cisco_ios, data_folder)
    _main(cisco_ios, data_folder)
