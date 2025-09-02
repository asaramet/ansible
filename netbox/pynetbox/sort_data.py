#!/usr/bin/env python3

# Sort collected running configs filles according to the switch type

import re

from os import path, listdir
from tabulate import tabulate
from std_functions import data_folder

raw_folder = path.join(data_folder, 'raw')

def extract_running_configs(temp_folder):
    print("TODO!")
    return

def get_files(dir_path):
    if not path.isdir(dir_path):
        raise ValueError(f"{dir_path} is not a valid directory")
    
    return [path.join(dir_path, f) for f in listdir(dir_path) if path.isfile(path.join(dir_path, f))]

def get_switch_type(config_file):
    try:
        # Check if input is a file path or direct content
        if '\n' in config_file or len(config_file) > 255:
            # Likely content, not a file path
            content = config_file
        else:
            # Assume it's a file path
            with open(config_file, 'r', encoding='utf-8') as file:
                content = file.read()

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

        # Pattern 1: Look for "module X type SWITCH_TYPE" pattern
        module_pattern = r'module\s+\d+\s+type\s+([A-Z0-9]+[A-Z])'
        match = re.search(module_pattern, content, re.IGNORECASE)
        
        if match:
            return match.group(1).upper()
        
        # Pattern 2: Look for "; SWITCH_TYPE Configuration Editor" in header
        header_pattern = r';\s*([A-Z0-9]+[A-Z])\s+Configuration\s+Editor'
        match = re.search(header_pattern, content, re.IGNORECASE)
        
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
        raise FileNotFoundError(f"Configuration file '{config_file}' not found")
    except IOError as e:
        raise IOError(f"Error reading configuration file: {e}")
    except Exception as e:
        raise Exception(f"Unexpected error parsing config: {e}")

#----- Debugging -------
def debug_get_switch_type(files_list):
    table = []
    headers = ["File name", "Switch type"]
    for f in files_list:
        table.append([ path.basename(f), get_switch_type(f) ])
    print(tabulate(table, headers, "github"))

def main():
    debug_configs_dir = raw_folder

    #debug_configs_dir = path.join(data_folder, 'aruba-modular-stack')
    #debug_configs_dir = path.join(data_folder, 'aruba-stack-2930')

    debug_configs_dir = path.join(data_folder, 'aruba-8-ports')

    config_files = get_files(debug_configs_dir)
    debug_get_switch_type(config_files)


if __name__ == "__main__":
    main()