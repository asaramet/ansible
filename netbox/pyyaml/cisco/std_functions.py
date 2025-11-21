#!/usr/bin/env python3

'''
Cisco config specific functions
'''

import logging, argparse

from pathlib import Path

# Configure logging
logger = logging.getLogger(__name__)

# Some paths
script_path = Path(__file__).resolve()
cisco_dir = script_path.parent
pyyaml_dir = cisco_dir.parent
project_dir = pyyaml_dir.parent
data_folder = project_dir.joinpath('data', 'cisco')

def _main(description: str, function: callable, data_folder: Path = data_folder, **kwargs) -> None:
    """
    Parse Cisco config files and generate YAML data file.
    Args:
        description: String describing what the function does
        function: function to execute, that should contain, as arguments, at least:
            data_folder: Data folder path. Default one is defined here already (../data/cisco)
    """
    import argparse

    # Disable warnings about self-signed certificates
    from urllib3 import disable_warnings, exceptions
    disable_warnings(exceptions.InsecureRequestWarning)

    # Configure logging
    logging.basicConfig(level = logging.INFO)

    parser = argparse.ArgumentParser(description=description)

    function(data_folder, **kwargs)