#!/usr/bin/env python3

# Sort collected running configs filles according to the switch type

import re

from pathlib import Path
from tabulate import tabulate

script_path = Path(__file__).resolve()
pyyaml_dir = script_path.parent
project_dir = pyyaml_dir.parent

data_folder = project_dir.joinpath('data')
raw_folder = data_folder.joinpath('raw')
temp_folder = raw_folder.joinpath('temp')

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

    'J8697A': 'procurve-modular',
    'J8698A': 'procurve-modular',
    'J8702A': 'procurve-modular',
    'J8705A': 'procurve-modular',
    'J8765A': 'procurve-modular',
    'J8768A': 'procurve-modular',
    'J8773A': 'procurve-modular',
    'J8770A': 'procurve-modular',
    'J9534A': 'procurve-modular',
    'J9550A': 'procurve-modular',
    'J9729A': 'procurve-modular',
    'J9850A': 'procurve-modular',
    'J9851A': 'procurve-modular',

    'J9085A': 'procurve-single',
    'J9086A': 'procurve-single',
    'J9089A': 'procurve-single',

    'JL679A': 'aruba_6100',
    'JL658A': 'aruba_6300',
    'JL659A': 'aruba_6300',

    'CISCO': 'cisco'

}

def move_file_and_cleanup(source_file, dest_file):
    """
    Helper function to move a file and track the operation.
    Returns tuple: (success: bool, error_message: str or None)
    """
    try:
        source_file.rename(dest_file)
        #print(f"    + Copied: {source_file.parent.name}/{source_file.name} -> {dest_file}")
        return True, None
    except Exception as e:
        error_msg = f"Error moving {source_file}: {str(e)}"
        print(f"    x {error_msg}")
        return False, error_msg

def cleanup_empty_dir(directory):
    """
    Helper function to remove an empty directory.
    """
    try:
        if directory.exists() and directory.is_dir():
            directory.rmdir()
    except Exception as e:
        print(f"    ! Could not remove {directory}: {str(e)}")

def process_switch_directory(switch_dir, dest_path, results, final_dest_path=None):
    """
    Process a single switch directory - either contains running-config directly
    or is a vendor folder (aruba_6100/aruba_6300) containing switch subdirectories.

    Args:
        switch_dir: Directory to process
        dest_path: Destination for regular configs (raw folder)
        results: Results dictionary to track operations
        final_dest_path: Final destination for vendor folders (data folder)
    """
    # Check if this is a vendor folder containing subdirectories
    vendor_folders = ['aruba_6100', 'aruba_6300']

    if switch_dir.name in vendor_folders:
        # Vendor folders go directly to their final destination, not raw
        if final_dest_path:
            vendor_dest = Path(final_dest_path) / switch_dir.name
        else:
            vendor_dest = dest_path.parent / switch_dir.name

        vendor_dest.mkdir(parents=True, exist_ok=True)

        print(f"  Processing vendor folder: {switch_dir.name}")
        print(f"    Source: {switch_dir}")
        print(f"    Destination: {vendor_dest}")

        # Get all items (files and directories) in the vendor folder
        for item in switch_dir.iterdir():
            if item.is_file():
                # Config file directly in vendor folder - move it
                dest_file = vendor_dest / item.name
                success, error = move_file_and_cleanup(item, dest_file)

                if success:
                    results['copied'].append({
                        'source': str(item),
                        'destination': str(dest_file),
                    })
                else:
                    results['errors'].append(error)

            elif item.is_dir():
                # Subdirectory containing config files
                config_files = [f for f in item.iterdir() if f.is_file()]

                if config_files:
                    # Move all config files from this subdirectory
                    for config_file in config_files:
                        dest_file = vendor_dest / config_file.name
                        success, error = move_file_and_cleanup(config_file, dest_file)

                        if success:
                            results['copied'].append({
                                'source': str(config_file),
                                'destination': str(dest_file),
                            })
                        else:
                            results['errors'].append(error)

                    # Cleanup subdirectory after moving all files
                    cleanup_empty_dir(item)
                else:
                    results['missing_config'].append(f"{switch_dir.name}/{item.name}")
                    print(f"    - No config found in: {switch_dir.name}/{item.name}")
                    cleanup_empty_dir(item)

        # Cleanup vendor folder after processing all subdirectories
        cleanup_empty_dir(switch_dir)
    else:
        # Regular switch directory - look for running-config
        running_config = switch_dir / "running-config"

        if running_config.is_file():
            dest_file = dest_path / switch_dir.name
            success, error = move_file_and_cleanup(running_config, dest_file)

            if success:
                results['copied'].append({
                    'source': str(running_config),
                    'destination': str(dest_file),
                })
            else:
                results['errors'].append(error)

            cleanup_empty_dir(switch_dir)
        else:
            results['missing_config'].append(switch_dir.name)
            print(f"    - No running-config found in: {switch_dir.name}")
            cleanup_empty_dir(switch_dir)

def extract_running_configs(source_path, dest_path, final_dest_path=None):
    """
    Search for directories and extract their config files to a destination folder.
    Handles:
    - Direct switch folders (rs*, rg*, rh*, rw*) with running-config files -> go to dest_path (raw)
    - Vendor folders (aruba_6100, aruba_6300) containing switch subdirectories -> go to final_dest_path (data)

    Args:
        source_path: Source directory (temp folder)
        dest_path: Destination for regular configs (raw folder)
        final_dest_path: Final destination for vendor folders (data folder)
    """
    source_path = Path(source_path) if not isinstance(source_path, Path) else source_path
    dest_path = Path(dest_path) if not isinstance(dest_path, Path) else dest_path

    # If final_dest_path not provided, use parent of dest_path
    if not final_dest_path:
        final_dest_path = dest_path.parent
    else:
        final_dest_path = Path(final_dest_path) if not isinstance(final_dest_path, Path) else final_dest_path

    # Create dest folder if it doesn't exist
    dest_path.mkdir(parents=True, exist_ok=True)

    # Track results
    results = {
        'copied': [],
        'missing_config': [],
        'errors': []
    }

    if not source_path.exists():
        results['errors'].append(f"Source directory does not exist: {source_path}")
        return results

    # Folders prefixes for direct switch directories
    switch_prefixes = ['rs', 'rg', 'rh', 'rw']
    # Vendor folders that contain switch subdirectories
    vendor_folders = ['aruba_6100', 'aruba_6300']

    try:
        for item in source_path.iterdir():
            if not item.is_dir():
                continue

            # Check if it's a switch folder or vendor folder
            is_switch_folder = any(item.name.startswith(prefix) for prefix in switch_prefixes)
            is_vendor_folder = item.name in vendor_folders

            if is_switch_folder or is_vendor_folder:
                process_switch_directory(item, dest_path, results, final_dest_path)

    except Exception as e:
        error_msg = f"Error scanning source directory: {str(e)}"
        results['errors'].append(error_msg)
        print(f"x {error_msg}")

    # Remove empty source folder
    cleanup_empty_dir(source_path)

    # Print summary
    print(f"""
    Summary:
    Files copied: {len(results['copied'])}
    Directories without config: {len(results['missing_config'])}
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

        # Pattern 4: For OS-CX switches without type info, infer from folder name
        # Check if this is an OS-CX config by looking for ArubaOS-CX in version
        if 'ArubaOS-CX' in content or 'AOS-CX' in content:
            parent_folder = config_file.parent.name
            # Map folder names to default device types
            folder_to_type = {
                'aruba_6100': 'JL679A',  # Aruba 6100-12G-POE4-2SFP+
                'aruba_6300': 'JL658A',  # Aruba 6300M-24SFP+-4SFP56 (default, could also be JL659A for 48-port)
            }
            if parent_folder in folder_to_type:
                return folder_to_type[parent_folder]

        return None

    except FileNotFoundError:
        raise FileNotFoundError(f"Configuration file '{config_file.name}' not found")
    except IOError as e:
        raise IOError(f"Error reading configuration file: {e}")
    except Exception as e:
        raise Exception(f"Unexpected error parsing config: {e}")

def is_cisco_config(config_file):
    """
    Detect if a configuration file is from a Cisco device.
    Returns True if Cisco patterns are found, False otherwise.
    """
    if not isinstance(config_file, Path):
        config_file = Path(config_file)

    try:
        content = config_file.read_text(encoding="utf-8")

        # Cisco config patterns to look for
        cisco_patterns = [
            r'^version\s+\d+\.\d+',  # version line (common in Cisco)
            r'Cisco\s+IOS',          # Cisco IOS mention
            r'Current configuration',  # Common header
            r'cisco\s+Systems',      # Cisco copyright
            r'^!\s*$',               # Lines with just "!" (Cisco comments)
            r'^hostname\s+\w+',      # hostname command
            r'^interface\s+(FastEthernet|GigabitEthernet|TenGigabitEthernet|Vlan)',  # Cisco interface naming
            r'^ip\s+route',          # ip route command
            r'^spanning-tree\s+mode',  # Cisco STP commands
        ]

        # Count how many patterns match
        matches = 0
        for pattern in cisco_patterns:
            if re.search(pattern, content, re.MULTILINE | re.IGNORECASE):
                matches += 1

        # If we found at least 3 Cisco patterns, it's likely a Cisco config
        return matches >= 3

    except Exception:
        return False

def normalize_switch_type(switch_type):
    """
    Helper function to normalize switch type.
    - If string: return as-is
    - If dict (stack): return first member type + "_stack" suffix
    - If None: return None
    """
    if not switch_type:
        return None

    if isinstance(switch_type, dict):
        # Stack configuration - use first member's type with _stack suffix
        first_member = min(switch_type.keys())  # Get first member
        return f"{switch_type[first_member]}_stack"

    return switch_type

def sort_file(file_path, dest_path=data_folder):
    """
    Move a config file to its destination folder based on switch type.
    Returns the destination folder path or None if sorting failed.
    """
    file_path = Path(file_path) if not isinstance(file_path, Path) else file_path
    dest_path = Path(dest_path) if not isinstance(dest_path, Path) else dest_path

    f_name = file_path.name

    # Get and normalize switch type
    raw_type = get_switch_type(file_path)
    f_type = normalize_switch_type(raw_type)

    # If type not found, check if it's a Cisco config
    if not f_type:
        if is_cisco_config(file_path):
            f_type = 'CISCO'
            print(f"    ! Detected Cisco config: {f_name}")
        else:
            print(f"    - Couldn't find the type of {f_name}")
            return None

    # Check if type is mapped to a hardware folder
    if f_type not in hw_folders:
        print(f"    - File type '{f_type}' not found in hw_folders dict for {f_name}")
        return None

    # Define destination folder according to file type
    dest_folder = dest_path / hw_folders[f_type]
    dest_folder.mkdir(parents=True, exist_ok=True)

    try:
        file_path.rename(dest_folder / f_name)
        print(f"+ {f_name} sorted into {dest_folder.name}/")
        return dest_folder
    except IOError as e:
        print(f"    x Error moving {f_name}: {e}")
        return None


#----- Debugging -------
def debug_get_switch_type(files_list):
    """
    Debug helper to display switch types for a list of config files.
    Shows both raw type (dict for stacks), normalized type, and Cisco detection.
    """
    table = []
    headers = ["File name", "Raw Type", "Normalized Type", "Is Cisco?"]
    for f in files_list:
        raw_type = get_switch_type(f)
        normalized = normalize_switch_type(raw_type)
        is_cisco = "Yes" if not normalized and is_cisco_config(f) else "No"
        final_type = "CISCO" if is_cisco == "Yes" else normalized
        table.append([Path(f).name, raw_type, final_type, is_cisco])
    print(tabulate(table, headers, "github"))

def debug():
    debug_configs_dir = raw_folder

    #debug_configs_dir = Path(data_folder) / 'aruba-modular'
    #debug_configs_dir = Path(data_folder) / 'aruba-modular-stack'
    #debug_configs_dir = Path(data_folder) / 'aruba-stack-2930'
    #debug_configs_dir = Path(data_folder) / 'aruba-stack'

    #debug_configs_dir = Path(data_folder) / 'aruba-48-ports'

    #debug_configs_dir = Path(data_folder) / 'hpe-24-ports'

    #debug_configs_dir = Path(data_folder) / 'procurve-single'
    #debug_configs_dir = Path(data_folder) / 'procurve-modular'

    debug_configs_dir = Path(data_folder) / 'aruba_6100'
    #debug_configs_dir = Path(data_folder) / 'aruba_6300'

    config_files = get_files(debug_configs_dir)
    debug_get_switch_type(config_files)

def main():
    """
    Main function to extract configs from temp folder and sort them by hardware type.
    """
    print(f"Starting config extraction and sorting...\n")
    print(f"Source: {temp_folder}")
    print(f"Raw destination: {raw_folder}")
    print(f"Final destination: {data_folder}\n")

    # Step 1: Extract configs from temp folder
    print("=" * 60)
    print("STEP 1: Extracting configs from temp folder")
    print("=" * 60)
    extract_results = extract_running_configs(temp_folder, raw_folder, data_folder)

    # Step 2: Sort extracted configs by hardware type
    print("\n" + "=" * 60)
    print("STEP 2: Sorting configs by hardware type")
    print("=" * 60)

    unsorted_files = get_files(raw_folder)

    if not unsorted_files:
        print("No files to sort.")
        return

    sorted_count = 0
    failed_count = 0

    for f in unsorted_files:
        result = sort_file(f)
        if result:
            sorted_count += 1
        else:
            failed_count += 1

    # Final summary
    print("\n" + "=" * 60)
    print("FINAL SUMMARY")
    print("=" * 60)
    print(f"Configs extracted: {len(extract_results['copied'])}")
    print(f"Configs sorted: {sorted_count}")
    print(f"Failed to sort: {failed_count}")
    print(f"Total errors: {len(extract_results['errors'])}")
    print("=" * 60)

if __name__ == "__main__":
    main()
    #debug()

