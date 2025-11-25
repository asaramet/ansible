#!/usr/bin/env python3

'''
Cisco config specific functions
'''

import logging, re

from pathlib import Path

# Configure logging
logger = logging.getLogger(__name__)

# Some paths
script_path = Path(__file__).resolve()
cisco_dir = script_path.parent
pyyaml_dir = cisco_dir.parent
project_dir = pyyaml_dir.parent
#data_folder = project_dir.joinpath('data', 'cisco')
data_folder = pyyaml_dir.joinpath('data')

def _main(function: callable, data_folder: Path = data_folder, **kwargs) -> None:
    """
    Parse Cisco config files and generate YAML data file.
    Args:
        function: function to execute, that should contain, as arguments, at least:
            data_folder: Data folder path. Default one is defined here already (../data/cisco)
    """
    # Configure logging
    logging.basicConfig(level = logging.INFO)

    function(data_folder, **kwargs)

def get_hostname_and_stack(data_folder):
    """
    Read Cisco config files from data folder and extract hostname and stack info.

    Args:
        data_folder: Path to the data folder containing Cisco config files

    Returns:
        list: List of dictionaries with keys:
            - hostname: str - Device hostname
            - stack: bool - True if device is in a stack (multiple switches)
            - switches: set - Set of switch numbers found in config
    """
    results = []
    data_path = Path(data_folder)

    if not data_path.exists():
        logger.error(f"Data folder does not exist: {data_folder}")
        return results

    # Read all files in the data folder
    for file_path in data_path.iterdir():
        if file_path.is_file():
            hostname = None
            stack_switches = set()

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        # Look for hostname line
                        hostname_match = re.match(r'^hostname\s+(\S+)', line)
                        if hostname_match:
                            hostname = hostname_match.group(1)

                        # Look for switch provision lines (indicates stack)
                        switch_match = re.match(r'^switch\s+(\d+)\s+provision', line)
                        if switch_match:
                            stack_switches.add(switch_match.group(1))

                # If we found a hostname, add it to results
                if hostname:
                    is_stack = len(stack_switches) > 1
                    results.append({
                        'hostname': hostname,
                        'stack': is_stack,
                        'switches': stack_switches
                    })
                    logger.debug(f"File {file_path.name}: hostname={hostname}, stack={is_stack}, switches={stack_switches}")
                else:
                    logger.warning(f"No hostname found in {file_path.name}")

            except Exception as e:
                logger.error(f"Error reading file {file_path.name}: {e}")

    return results

if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from functions import _debug

    # Test the get_hostname_and_stack function
    _debug(get_hostname_and_stack, data_folder)
