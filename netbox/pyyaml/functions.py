#!/usr/bin/env  python3

# Standard reusable functions

import yaml, logging

from pathlib import Path
from sys import stdout

# Configure logging
logger = logging.getLogger(__name__)

# Paths
script_path = Path(__file__).resolve()
pyyaml_dir = script_path.parent
project_dir = pyyaml_dir.parent
src_dir = project_dir.joinpath("src")

# Slugs for HE campuses
campuses = {
    "h": "flandernstrasse",
    "g": "gppingen",
    "s": "stadtmitte",
    "w": "weststadt"
}

# Return a list of devices serial numbers from the yaml file
def serial_numbers_yaml():
    yaml_file = src_dir.joinpath("serial_numbers.yaml")
    logger.debug(f"Serial numbers file: {yaml_file}")

    s_dict = {}
    with open(yaml_file, 'r') as f:
        for v_dict in yaml.safe_load(f):
            for key, value in v_dict.items():
                s_dict[key] = value

    return s_dict 

def serial_numbers(number = "serial_number", active_only = False, inactive_only = False):
    sql_folder = project_dir / 'sql_scripts'

    if not sql_folder.exists():
        raise FileNotFoundError(f"\u2717 Path doesn't exist: {sql_folder}")
        
    if not sql_folder.is_dir():
        raise NotADirectoryError(f"\u2717 Path exist but is not a directory: {sql_folder}")

    # import get_devices_serials function
    from sys import path
    path.insert(0, str(sql_folder))
    from std_objs import get_devices_numbers

    return get_devices_numbers(number, active_only, inactive_only)

# return a tuple (section, value), ex: (interface, interface_name), recursively from a switch config
def recursive_section_search(text, section, value):
    """
    Parses a config text block and returns a list of (section_value, value_found) tuples.
    Example: [('interface_name', 'interface_description')]
    """
    results = []
    current_section = None

    for line in text:
        stripped = line.strip()

        # Start of a section
        if stripped.startswith(section):
            parts = stripped.split(maxsplit=1)
            if len(parts) == 2:
                current_section = parts[1]
            continue
        
        # Value found inside section
        if current_section and stripped.startswith(value):
            _, val = stripped.split(' ', 1)
            results.append((current_section.split("multi-chassis")[0].strip(), val.strip('"')))
            continue

        # End of a section
        if stripped in {"exit", "!"}:
            current_section = None

    return results

def get_vlans_names(t_file):
    with open(t_file, "r") as f:
        text = f.readlines()

    vlans = {}
    for vlan_id, vlan_name in recursive_section_search(text, 'vlan', 'name '):
        vlans[vlan_id] = vlan_name
    return vlans

def extract_ip_from_mgmt(text):
    result = recursive_section_search(text, 'interface mgmt', 'ip static')
    if result:
        return result[0][1].split()[1]  # 'static 1.2.3.4'
    return None

def extract_ip_from_aoscx_vlan(text):
    result = recursive_section_search(text, 'interface vlan', 'ip address')
    if result:
        vlan_id = result[0][0].split()[1]  # 'vlan 101'
        ip = result[0][1].split()[1]       # 'address 1.2.3.4/24'
        return vlan_id, ip
    return None

def extract_ip_from_aruba_vlan(text):
    result = recursive_section_search(text, 'vlan', 'ip address')
    if result:
        vlan_id, ip_string = result[0]
        _, ip, netmask = ip_string.split()  # 'address 1.2.3.4 255.255.254.0'
        prefix = sum(bin(int(octet)).count('1') for octet in netmask.split('.'))
        return vlan_id, f'{ip}/{prefix}'
    return None


inactive_devices = serial_numbers(inactive_only = True)
def get_device_status(text):

    for line in text:
        if line.startswith('hostname'): 
            hostname = line.split()[1].strip().strip('"')
            break

    if hostname in inactive_devices or f"{hostname}-1" in inactive_devices:
        return "deprecated"
    return "active"

def get_ip_address(t_file):
    with open(t_file, "r") as f:
        text = f.readlines()

    # Try management interface first
    mgmt_ip = extract_ip_from_mgmt(text)
    if mgmt_ip:
        # Return 'mgmt' as a special marker for vlan_id to indicate management interface
        return 'mgmt', None, mgmt_ip, get_device_status(text)

    # Try AOS_CX VLAN interfaces
    vlan_info = extract_ip_from_aoscx_vlan(text)
    if not vlan_info:
        vlan_info = extract_ip_from_aruba_vlan(text)

    vlan_id, ip = vlan_info
    vlan_name = get_vlans_names(t_file).get(vlan_id, "UNKNOWN")

    return vlan_id, vlan_name, ip, get_device_status(text)

def get_device_role(t_file, hostname):
    role_code = hostname[2:4]
    if role_code == "cs":
        d_type = int(hostname[5])
        if d_type == 0:
            return "router"
        return "distribution-layer-switch"
    
    if hostname[-1] == "s":
        return "distribution-layer-switch"

    vlan_id, _, _, _ =  get_ip_address(t_file)

    if vlan_id in ["102", "202", "302"]:
        return "bueroswitch"

    return "access-layer-switch"

# Debugging
def _debug(function: callable, *args, **kwargs) -> None:
    """
    Debug functions with variable number of arguments.

    Args:
        function: debug function to execute
        *args: positional arguments to pass to the function
        **kwargs: keyword arguments to pass to the function

    Example:
        _debug(device_type, 'rscs0001')
        _debug(some_func, arg1, arg2, kwarg1='value')
    """
    # Set DEBUG logging output
    logging.basicConfig(level = logging.DEBUG)

    # Call the function with all provided arguments
    data = function(*args, **kwargs)

    # Build a nice string representation of the function call
    args_str = ', '.join([repr(arg) for arg in args])
    kwargs_str = ', '.join([f"{k}={repr(v)}" for k, v in kwargs.items()])
    all_args = ', '.join(filter(None, [args_str, kwargs_str]))
    func_call = f"{function.__name__}({all_args})"

    if isinstance(data, dict):
        logger.debug(f"Function '{func_call}' returns:")
        yaml.dump(data, stdout)
        return

    logger.debug(f"Function '{func_call}' returns: {repr(data)}")

if __name__ == "__main__":
    #_debug(serial_numbers_yaml)
    #_debug(serial_numbers, 'inventory_number')
    #_debug(serial_numbers, 'inventory_number')
    #_debug(serial_numbers, inactive_only = True)
    #_debug(serial_numbers, inactive_only = True)

    data_folders = [
#        "procurve_single",
#        "procurve_modular",

#        "hpe_8_ports",
#        "hpe_24_ports",

#        "aruba_8_ports",
#        "aruba_12_ports",
#        "aruba_48_ports",

#        "aruba_stack",
#        "aruba_stack_2920",
#        "aruba_stack_2930",

#        "aruba_modular",
#        "aruba_modular_stack",

        "aruba_6100",
        "aruba_6300", 
#        "aruba_8320"
    ]


    data_dir = project_dir.joinpath("data")

    for data_folder in data_folders:
        folder = data_dir.joinpath(data_folder)
        for f in folder.iterdir(): 
            if f.is_file():
                print(f)
                _debug(get_ip_address, f)