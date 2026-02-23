#!/usr/bin/env python3

# Collect HPE/Aruba switches data and create YAML config files

import sys, yaml
from pathlib import Path

from std_functions import device_type_slags, project_dir, config_files

from json_functions import devices_json, lags_json, device_interfaces_json
from json_functions import vlans_json, tagged_vlans_json
from json_functions import ip_addresses_json, modules_json

def process_switches(data_folder, output_file_path, devices_tags, is_modular=False):
    """
    Generate YAML configuration for switches.

    Collects device, interface, VLAN, and IP data from config files and outputs
    to a YAML file suitable for NetBox import via Ansible.

    Args:
        data_folder: Path to folder containing config files (Path or string)
        output_file_path: Output file path (Path/string) or sys.stdout for debugging
        devices_tags: Tags for devices (string or list, e.g., "switch" or ["switch", "stack"])
        is_modular: If True, include module data in output (default: False)

    Output YAML sections:
        - modular: Boolean flag
        - devices: Device and chassis entries
        - modules: Module data (only if is_modular=True)
        - lags: Link aggregation groups
        - device_interfaces: Interface definitions with PoE and VLAN assignments
        - vlans: VLAN definitions
        - tagged_vlans: Trunk interface VLAN assignments
        - ip_addresses: IP address assignments

    Example:
        process_switches('data/aruba-48-ports/', 'data/yaml/aruba_48_ports.yaml', ['switch'])
        process_switches('data/procurve-modular/', 'data/yaml/procurve_modular.yaml',
                        ['switch', 'modular-switch'], is_modular=True)
    """
    files = config_files(data_folder)

    # For debugging, output to stdout; otherwise write to file
    if output_file_path == sys.stdout:
        f = sys.stdout
    else:
        output_file = project_dir.joinpath(output_file_path)
        # Ensure parent directory exists
        output_file.parent.mkdir(parents=True, exist_ok=True)
        f = open(output_file, 'w')

    try:
        yaml.dump({"modular": is_modular}, f)
        yaml.dump(devices_json(files, device_type_slags, devices_tags), f)

        if is_modular:
            yaml.dump(modules_json(files), f)

        yaml.dump(lags_json(files), f)
        yaml.dump(device_interfaces_json(files), f)
        yaml.dump(vlans_json(files), f)
        yaml.dump(tagged_vlans_json(files), f)
        yaml.dump(ip_addresses_json(files), f)
    finally:
        if f is not sys.stdout:
            f.close()

def single(data_folder, output_file_path, devices_tags):
    """
    Generate YAML configuration for single (non-modular) switches.

    Wrapper function for backward compatibility. Calls process_switches() with is_modular=False.

    Args:
        data_folder: Path to folder containing config files (Path or string)
        output_file_path: Output file path (Path/string) or sys.stdout for debugging
        devices_tags: Tags for devices (string or list, e.g., "switch" or ["switch", "stack"])

    Example:
        single('data/aruba-48-ports/', 'data/yaml/aruba_48_ports.yaml', ['switch'])
    """
    process_switches(data_folder, output_file_path, devices_tags, is_modular=False)

def modular(data_folder, output_file_path, devices_tags):
    """
    Generate YAML configuration for modular switches.

    Wrapper function for backward compatibility. Calls process_switches() with is_modular=True.

    Args:
        data_folder: Path to folder containing config files (Path or string)
        output_file_path: Output file path (Path/string) or sys.stdout for debugging
        devices_tags: Tags for devices (string or list)

    Example:
        modular('data/procurve-modular/', 'data/yaml/procurve_modular.yaml',
                ['switch', 'modular-switch'])
    """
    process_switches(data_folder, output_file_path, devices_tags, is_modular=True)

#def assign_sfp_modules(t_file):
#    with open(main_folder + "/host_vars/99/sfp_modules.yaml", 'r' ) as f:
#        modules = yaml.safe_load(f)
#    return modules

def main():
    """
    Process all Aruba/HPE switch configurations and generate YAML files.

    Iterates through all switch categories (single and modular) and generates
    YAML output files suitable for NetBox import via Ansible.
    """
    # Configuration: folder -> (tags, processing_function)
    folder_config = {
        # Single switches
        "procurve_single": ("switch", single),
        "hpe_8_ports": ("switch", single),
        "hpe_24_ports": ("switch", single),
        "aruba_48_ports": ("switch", single),
        "aruba_8_ports": ("switch", single),
        "aruba_12_ports": ("switch", single),
        "aruba_6100": ("switch", single),
        "aruba_stack": (["switch", "stack"], single),
        "aruba_6300": (["switch", "stack"], single),

        # Modular switches
        "procurve_modular": (["switch", "modular-switch"], modular),
        "aruba_modular": (["switch", "modular-switch"], modular),
        "aruba_stack_2920": (["switch", "stack"], modular),
        "aruba_stack_2930": (["switch", "stack"], modular),
        "aruba_modular_stack": (["switch", "stack", "modular-switch"], modular),
    }

    data_folder = project_dir / "data"

    for folder, (tags, process_func) in folder_config.items():
        configs_folder = data_folder / folder
        output_file_path = data_folder / "yaml" / f"{folder}.yaml"

        switch_type = "modular" if process_func == modular else "single"
        print(f"Update {switch_type} switch data for {folder} into {output_file_path}")
        process_func(configs_folder, output_file_path, tags)

#----- Debugging -------
def debug_single():
    """Debug single switch processing with stdout output."""
    #data_folder = project_dir / "data" / "aruba-12-ports"
    data_folder = project_dir / "data" / "hpe-8-ports"

    print('---Debugging ', data_folder)
    single(data_folder, sys.stdout, ["switch"])
    print('---END Debugging---')

def debug_modular():
    """Debug modular switch processing with stdout output."""
    data_folder = project_dir / "data" / "procurve-modular"

    print("---Debugging ", data_folder)
    modular(data_folder, sys.stdout, ["switch", "modular-switch"])
    print('---END Debugging---')

def debug_dicts(d_folder):
    """Debug JSON extraction functions for a specific folder."""
    data_folder = project_dir / "data" / d_folder
    files = config_files(data_folder)

    print('---Debugging ', data_folder)

    # Collect all dictionaries in a list
    data_list = [
        #{"modular": False},
        devices_json(files, device_type_slags, ["switch"]),
        #modules_json(files),
        #lags_json(files),
        #device_interfaces_json(files),
        #vlans_json(files),
        #tagged_vlans_json(files),
        #ip_addresses_json(files)
    ]

    # Print the list of dictionaries
    yaml.dump(data_list, sys.stdout)

    print('---END Debugging ', data_folder)

def debug_multiple():
    data_folders = [
        "aruba-8-ports",
        #"aruba-12-ports",
        #"aruba-48-ports",
        #"hpe-8-ports",
        #"aruba-stack",
        #"aruba-stack-2920",
        #"aruba-stack-2930",
        #"aruba-modular",
        #"aruba-modular-stack",
        #"procurve-single",
        #"procurve-modular",

        "aruba_6100",
        "aruba_6300",
    ]

    for folder in data_folders:
        debug_dicts(folder)

if __name__ == "__main__":
    main()

    ## ------ Debug ----------##
    #debug_multiple()

