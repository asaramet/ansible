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

def _main(function: callable, data_folder: Path = data_folder, *args, **kwargs) -> None:
    """
    Parse Cisco config files and generate YAML data file.
    Args:
        function: function to execute, that should contain, as arguments, at least:
            data_folder: Data folder path. Default one is defined here already (../data/cisco)
    """
    # Configure logging
    logging.basicConfig(level = logging.INFO)

    function(data_folder, *args, **kwargs)

def get_hostname_and_stack(config_file):
    """
    Read a Cisco config file and extract hostname and stack info.
    Supports both regular stacks (2960X, 3850, 9300, etc.) and VSS (Virtual Switching System).

    Args:
        config_file: Path to the Cisco config file (Path object or string)

    Returns:
        dict: Dictionary with keys:
            - hostname: str - Device hostname
            - stack: bool - True if device is in a stack (multiple switches)
            - switches: set - Set of switch numbers found in config
        Returns None if hostname not found or error occurs
    """
    if not isinstance(config_file, Path):
        config_file = Path(config_file)

    if not config_file.exists():
        logger.error(f"Config file does not exist: {config_file}")
        return None

    hostname = None
    stack_switches = set()
    is_vss = False

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            for line in f:
                # Look for hostname line
                hostname_match = re.match(r'^hostname\s+(\S+)', line)
                if hostname_match:
                    hostname = hostname_match.group(1)

                # Pattern 1: Regular stack - "switch X provision <model>"
                switch_match = re.match(r'^switch\s+(\d+)\s+provision', line)
                if switch_match:
                    stack_switches.add(switch_match.group(1))

                # Pattern 2: VSS (Virtual Switching System) - "module provision switch X"
                vss_match = re.match(r'^module\s+provision\s+switch\s+(\d+)', line)
                if vss_match:
                    stack_switches.add(vss_match.group(1))
                    is_vss = True

                # Pattern 3: VSS indicator - "switch mode virtual"
                if re.search(r'switch\s+mode\s+virtual', line):
                    is_vss = True

        # If we found a hostname, return the result
        if hostname:
            # Stack if: more than 1 switch OR VSS configuration
            is_stack = len(stack_switches) > 1 or (len(stack_switches) > 0 and is_vss)
            result = {
                'hostname': hostname,
                'stack': is_stack,
                'switches': stack_switches
            }
            logger.debug(f"File {config_file.name}: hostname={hostname}, stack={is_stack}, switches={stack_switches}, VSS={is_vss}")
            return result
        else:
            logger.warning(f"No hostname found in {config_file.name}")
            return None

    except Exception as e:
        logger.error(f"Error reading file {config_file.name}: {e}")
        return None

# Cisco module type mapping: slot-type ID -> module model
module_type_slags = {
    404: 'WS-X45-SUP8-E',      # Sup 8-E 10GE (SFP+), 1000BaseX (SFP)
    407: 'WS-X4724-SFP-E',     # 24-port 1000BaseX SFP
    398: 'WS-X4748-UPOE+E',    # 48-port 10/100/1000BaseT UPOE E Series
    387: 'WS-X4712-SFP+E',     # 12-port 10GE SFP+
}

def get_modules(config_file):
    """
    Extract module/slot information from Cisco config file.
    Returns list of modules for modular chassis switches (e.g., Catalyst 4500 VSS).

    Args:
        config_file: Path to the Cisco config file (Path object or string)

    Returns:
        list: List of dictionaries, each containing:
            - hostname: Device hostname (includes switch number for stacks: hostname-1, hostname-2)
            - switch: Switch number in stack/VSS (str)
            - slot: Slot number (str)
            - slot_type: Numeric slot-type ID from config (int)
            - module_model: Module model name (str) or None if unknown
            - base_mac: Base MAC address (str)
        Returns empty list if no modules found or error occurs

    Example:
        >>> get_modules(Path('/path/to/rgcs1234'))
        [{'hostname': 'rgcs1234-1', 'switch': '1', 'slot': '1',
          'slot_type': 404, 'module_model': 'WS-X45-SUP8-E',
          'base_mac': '80E0.1D11.1111'}, ...]
    """
    if not isinstance(config_file, Path):
        config_file = Path(config_file)

    if not config_file.exists():
        logger.error(f"Config file does not exist: {config_file}")
        return []

    # Get hostname and stack info first
    hostname_info = get_hostname_and_stack(config_file)
    if not hostname_info:
        logger.warning(f"Could not get hostname from {config_file.name}")
        return []

    hostname = hostname_info['hostname']
    is_stack = hostname_info['stack']

    modules = []
    current_switch = None

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            for line in f:
                # Match: "module provision switch X"
                switch_match = re.match(r'^module\s+provision\s+switch\s+(\d+)', line)
                if switch_match:
                    current_switch = switch_match.group(1)
                    continue

                # Match: " slot X slot-type YYY base-mac AA:BB:CC:DD:EE:FF"
                slot_match = re.match(r'^\s+slot\s+(\d+)\s+slot-type\s+(\d+)\s+base-mac\s+(\S+)', line)
                if slot_match and current_switch:
                    slot_num = slot_match.group(1)
                    slot_type_id = int(slot_match.group(2))
                    base_mac = slot_match.group(3)

                    # Get module model from mapping, or None if unknown
                    module_model = module_type_slags.get(slot_type_id)

                    # For stacks, append switch number to hostname
                    device_name = f"{hostname}-{current_switch}" if is_stack else hostname

                    modules.append({
                        'hostname': device_name,
                        'switch': current_switch,
                        'slot': slot_num,
                        'slot_type': slot_type_id,
                        'module_model': module_model,
                        'base_mac': base_mac
                    })

                    logger.debug(f"Found module: switch={current_switch}, slot={slot_num}, "
                               f"type={slot_type_id}, model={module_model}")

        if modules:
            logger.debug(f"Extracted {len(modules)} modules from {config_file.name}")
        else:
            logger.debug(f"No modules found in {config_file.name}")

        return modules

    except Exception as e:
        logger.error(f"Error extracting modules from {config_file.name}: {e}")
        return []

def get_device_type(config_file):
    """
    Extract device type from a Cisco configuration file.
    Supports both regular stacks and VSS/older switches.

    Args:
        config_file: Path to the Cisco config file (Path object or string)

    Returns:
        str: Device type (e.g., 'ws-c2960x-24pd-l', 'c9500-40x', 'cat4500es8')
             Returns None if no device type found

    Example:
        >>> get_device_type(Path('/path/to/config'))
        'ws-c2960x-24pd-l'
    """
    if not isinstance(config_file, Path):
        config_file = Path(config_file)

    if not config_file.exists():
        logger.error(f"Config file does not exist: {config_file}")
        return None

    boot_system_type = None

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            for line in f:
                # Pattern 1: Regular stack - "switch 1 provision <device-type>"
                provision_match = re.match(r'^switch\s+\d+\s+provision\s+(\S+)', line)
                if provision_match:
                    device_type = provision_match.group(1)
                    logger.debug(f"Found device type '{device_type}' via provision in {config_file.name}")
                    return device_type

                # Pattern 2: VSS/older switches - extract from boot system command
                # Example: "boot system flash bootflash:cat4500es8-universalk9.SPA.03.11.04.E.152-7.E4.bin"
                boot_match = re.match(r'^boot\s+system\s+.*?:(cat\d+\w*|ws-c\d+\w*-\w+)', line, re.IGNORECASE)
                if boot_match:
                    boot_system_type = boot_match.group(1).lower()
                    logger.debug(f"Found potential device type '{boot_system_type}' in boot system command")

        # If we found device type from boot system, return it
        if boot_system_type:
            logger.debug(f"Using device type '{boot_system_type}' from boot system in {config_file.name}")
            return boot_system_type

        logger.warning(f"No device type found in {config_file.name}")
        return None

    except Exception as e:
        logger.error(f"Error reading config file {config_file.name}: {e}")
        return None

if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from functions import _debug

    data_path = Path(data_folder)
    if data_path.exists():
        for file_path in sorted(data_path.iterdir()):
            if file_path.is_file():
                _debug(get_modules, file_path)