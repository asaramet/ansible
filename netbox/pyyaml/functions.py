#!/usr/bin/env  python3

# Standard reusable functions

import yaml, logging

from pathlib import Path
from sys import stdout
from tabulate import tabulate

# Configure logging
logger = logging.getLogger(__name__)

# Paths
script_path = Path(__file__).resolve()
pyyaml_dir = script_path.parent
project_dir = pyyaml_dir.parent
src_dir = project_dir.joinpath("src")

# Return a list of devices serial numbers from the yaml file
def serial_numbers():
    yaml_file = src_dir.joinpath("serial_numbers.yaml")
    logger.debug(f"Serial numbers file: {yaml_file}")

    s_dict = {}
    with open(yaml_file, 'r') as f:
        for v_dict in yaml.safe_load(f):
            for key, value in v_dict.items():
                s_dict[key] = value

    return s_dict 

# Return a list of devices dictionary
def devices():
    yaml_file = src_dir.joinpath("devices.yaml")

    with open(yaml_file, 'r') as f:
        return yaml.safe_load(f)

    return None

# Return device type for a given hostname
def device_type(hostname):
    for device_type, d_list in devices().items():
        if hostname in d_list:
            return device_type

    return None

# Debugging
def _debug(function: callable, arg_1: object = None, **kwargs) -> None:
    """
    Debug functions
    Args:
        function: debug function to execute, that may have
        arg_1: first argument
    """
    # Set DEBUG logging output
    logging.basicConfig(level = logging.DEBUG)

    data = function(arg_1, **kwargs) if arg_1 else function(**kwargs)
    
    if isinstance(data, dict):
        table = []
        headers = ["Key", "Value"]
        for key, value in data.items():
            table.append([key, value])
        
        logger.debug(tabulate(table, headers, "github"))
        return

    if isinstance(data, str):
        logger.debug(f" Function '{function.__name__}('{arg_1}')' returned '{data}'")
    

if __name__ == "__main__":
    _debug(serial_numbers)
    #_debug(device_type, 'rscs0001')