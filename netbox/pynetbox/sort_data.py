#!/usr/bin/env python3

# Sort collected running configs filles according to the switch type

import re

from pathlib import Path
from tabulate import tabulate
from std_functions import data_folder

raw_folder = Path(data_folder) / 'raw'
temp_folder = Path(raw_folder) / 'temp'

hw_folders = {
    'JL258A': 'aruba-8-ports',
    'JL693A': 'aruba-12-ports',

    'JL255A': 'aruba-48-ports',
    'JL256A': 'aruba-48-ports',
    #'JL322A': 'aruba-48-ports',
    'JL357A': 'aruba-48-ports',

    'JL322A': 'aruba-modular',

    'JL075A_stack': 'aruba-stack',
    'JL256A_stack': 'aruba-stack',
    'JL693A_stack': 'aruba-stack',
    'J9729A_stack': 'aruba-stack-2920',
    'JL322A_stack': 'aruba-stack-2930',
    'J9850A_stack': 'aruba-modular-stack',

    'J9137A': 'hpe-8-ports',
    'J9562A': 'hpe-8-ports',
    'J9565A': 'hpe-8-ports',
    'J9774A': 'hpe-8-ports',
    'J9780A': 'hpe-8-ports',

    'J9145A': 'hpe-24-ports',
    'J9623A': 'hpe-24-ports',
    'J9772A': 'hpe-24-ports',
    'J9776A': 'hpe-24-ports',
    'J9779A': 'hpe-24-ports',
    'J9853A': 'hpe-24-ports',

    'J8702A': 'procurve-modular',
    'J8705A': 'procurve-modular',
    'J8765A': 'procurve-modular',
    'J8768A': 'procurve-modular',
    'J9534A': 'procurve-modular',
    'J9550A': 'procurve-modular',
    'J9729A': 'procurve-modular',
    'J9850A': 'procurve-modular',
    'J9851A': 'procurve-modular',

    'J9085A': 'procurve-single',
    'J9086A': 'procurve-single',
    'J9089A': 'procurve-single'

}

def extract_running_configs(source_path, dest_path):
    """
    Search for directories matching patterns (rs*, rg*, rh*, rw*) and copy 
    their running-config files to a destination folder.
    """

    if not isinstance(source_path, Path): source_path = Path(source_path)
    if not isinstance(dest_path, Path): dest_path = Path(dest_path)

    # Create dest folder if it doesn't exist
    dest_path.mkdir(parents=True, exist_ok=True)

    # Folders prefixes to search for
    prefixes = ['rs', 'rg', 'rh', 'rw']

    # Track results
    results = {
        'copied': [],
        'missing_config': [],
        'errors': []
    }

    try:
        # Get all items in the source directory
        if not source_path.exists():
            results['errors'].append(f"Source directory does not exist: {source_path}")
            return results

        for item in source_path.iterdir():
            # Check if it's a directory and starts with one of the prefixes
            if item.is_dir() and any(item.name.startswith(prefix) for prefix in prefixes):
                running_config_file = item / "running-config"

                # Check if running-config file exists
                if running_config_file.is_file():
                    try:
                        # Move the running-config file to the destination with directory name
                        dest_file = dest_path / item.name
                        running_config_file.rename(dest_file)
                        results['copied'].append({
                            'source': str(running_config_file),
                            'destination': str(dest_file),
                        })

                        running_config_file.parent.rmdir() # Remove the empty folder
                        print(f"    + Copied: {item.name}/running-config -> {dest_file}")
                    
                    except Exception as e:
                        error_msg = f"Error copying {item.name}: {str(e)}" 
                        results['errors'].append(error_msg)
                        print(f"    x {error_msg}")

                else:
                    results['missing_config'].append(item.name)
                    running_config_file.parent.rmdir()
                    print(f"    - No running-config found in: {item.name}")


    except Exception as e:
        results['errors'].append(f"Error scanning source directory: {str(e)}")
        print(f"x Error scanning source directory: {str(e)}")

    # Remove empty source folder
    if source_path.exists(): 
        try:
            source_path.rmdir()
        except Exception as e:
            print(f"x Error removing the source folder: {str(e)}")

    # Print summary
    print(
    f"""
    Summary:
    Files copied: {len(results['copied'])}
    Directories without running-config: {len(results['missing_config'])}
    Errors: {len(results['errors'])}
    """)

    return results

def get_files(dir_folder):
    dir_path = Path(dir_folder)

    if not dir_path.is_dir():
        raise ValueError(f"{dir_folder} is not a valid directory")
    
    return [f for f in dir_path.iterdir() if f.is_file()]

def get_switch_type(config_file):

    # Convert strings into Path class
    if not isinstance(config_file, Path):
        config_file = Path(config_file)

    try:
        # Read content form a file path 
        content = config_file.read_text(encoding="utf-8")

        # First, check for stack configuration
        stack_members = {}
        
        # Pattern for stack members: member X type "SWITCH_TYPE" or member X type SWITCH_TYPE
        stack_pattern = r'member\s+(\d+)\s+type\s+["\']?([A-Z0-9]+[A-Z])["\']?'
        stack_matches = re.findall(stack_pattern, content, re.IGNORECASE)
        
        if stack_matches:
            for member_id, switch_type in stack_matches:
                stack_members[member_id] = switch_type.upper()
            return stack_members
        
        # If no stack found, check for single switch patterns

        # Pattern 1: Look for "; SWITCH_TYPE Configuration Editor" in header
        header_pattern = r';\s*([A-Z0-9]+[A-Z])\s+Configuration\s+Editor'
        match = re.search(header_pattern, content, re.IGNORECASE)
        
        if match:
            return match.group(1).upper()
        
        # Pattern 2: Look for "module X type SWITCH_TYPE" pattern
        module_pattern = r'module\s+\d+\s+type\s+([A-Z0-9]+[A-Z])'
        match = re.search(module_pattern, content, re.IGNORECASE)
        
        if match:
            return match.group(1).upper()
        
        # Pattern 3: Alternative pattern for different config formats
        # Look for switch type in comments or other locations
        alt_pattern = r'\b([A-Z]{2}\d{3}[A-Z])\b'
        matches = re.findall(alt_pattern, content)
        
        if matches:
            # Return the first match that looks like a switch type
            for match in matches:
                if len(match) == 6:  # Typical format like JL258A
                    return match.upper()
              
        return None

    except FileNotFoundError:
        raise FileNotFoundError(f"Configuration file '{config_file.name}' not found")
    except IOError as e:
        raise IOError(f"Error reading configuration file: {e}")
    except Exception as e:
        raise Exception(f"Unexpected error parsing config: {e}")

def sort_file(file_path, dest_path=data_folder):
    # Move a config file to the destined folder

    f_type = get_switch_type(file_path)
    f_name = file_path.name

    # Exit if device type is not found
    if not f_type:
        print(f"    - Couldn't find the type of {f_name}")
        return None

    # Get the file type from a return dict for stacks
    if isinstance(f_type, dict): f_type = f_type['1'] + "_stack"

    # Create destination folder if it doesn't exist
    if not isinstance(dest_path, Path):
        dest_path = Path(dest_path)

    if f_type not in hw_folders.keys():
        print(f"    - File type, {f_type} not found in hw_folders dict for {f_name}")
        return

    # define the dest folder according to the file type
    dest_folder = dest_path / hw_folders[f_type]

    dest_folder.mkdir(parents=True, exist_ok=True)

    try:
        file_path.rename(dest_folder / f_name)
        print(f"+ {file_path.name} sorted into {dest_folder}")
    except IOError as e:
        raise IOError(f"Error reading {file_path}: {e}")

    return dest_folder


#----- Debugging -------
def debug_get_switch_type(files_list):
    table = []
    headers = ["File name", "Switch type"]
    for f in files_list:
        table.append([ Path(f).name, get_switch_type(f) ])
    print(tabulate(table, headers, "github"))

def debug():
    debug_configs_dir = raw_folder

    #debug_configs_dir = Path(data_folder) / 'aruba-modular'
    #debug_configs_dir = Path(data_folder) / 'aruba-modular-stack'
    #debug_configs_dir = Path(data_folder) / 'aruba-stack-2930'
    debug_configs_dir = Path(data_folder) / 'aruba-stack'

    #debug_configs_dir = Path(data_folder) / 'aruba-48-ports'

    #debug_configs_dir = Path(data_folder) / 'hpe-24-ports'

    #debug_configs_dir = Path(data_folder) / 'procurve-single'
    #debug_configs_dir = Path(data_folder) / 'procurve-modular'

    config_files = get_files(debug_configs_dir)
    debug_get_switch_type(config_files)

def main():
    extract_running_configs(temp_folder, raw_folder)

    unsorted_files = get_files(raw_folder)
    
    for f in unsorted_files:
        sort_file(f)

if __name__ == "__main__":
    #main()

    debug()

