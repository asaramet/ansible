#!/usr/bin/env python3
"""
Add device types to the DB from a yaml file.
"""

import yaml
from pathlib import Path
from typing import List, Dict, Union, Any

from device_specs import DeviceSpecifications

def read_yaml(yaml_file: Union[str, Path]) -> List[Dict[str, Any]]:
    """
    Reads a YAML file containing a list of devices and their types.
    
    Expected YAML structure:
    - router-01: Cisco
    - switch-02: Juniper
    
    Args:
        yaml_file: Path to the YAML file.
        
    Returns:
        A list of dictionaries, e.g., [{'router-01': 'Cisco'}, {'switch-02': 'Juniper'}]
        
    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the YAML is invalid or not a list.
    """
    file_path = Path(yaml_file).expanduser().resolve()
    
    if not file_path.exists():
        raise FileNotFoundError(f"YAML file not found: {file_path}")
        
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            
        # Validate that the YAML actually parsed into a Python list
        if data is None:
            return []
        if not isinstance(data, list):
            raise ValueError(f"Expected a YAML list, but got {type(data).__name__}.")
            
        return data
        
    except yaml.YAMLError as e:
        raise ValueError(f"Failed to parse YAML file '{file_path.name}': {e}")


def sync_devices_from_yaml(yaml_path: Union[str, Path]):
    """Reads a YAML file and syncs its devices to the database."""
    
    # 1. Read the YAML data (using the function we just created)
    try:
        devices_list = read_yaml(yaml_path)
    except Exception as e:
        print(f"Error reading YAML: {e}")
        return

    if not devices_list:
        print("YAML file is empty or invalid. Nothing to sync.")
        return

    # 2. Initialize database connection handler
    db_handler = DeviceSpecifications()

    # Track exactly what happened for a summary report
    stats = {"inserted": 0, "updated": 0, "ignored": 0, "errors": 0}

    print(f"Starting sync of {len(devices_list)} devices...")

    # 3. Connect to DB and loop through the data
    try:
        with db_handler as db:
            for item in devices_list:
                # Unpack the single key-value pair, e.g., {'router-01': 'Cisco'}
                for hostname, device_type in item.items():
                    try:
                        # Call your class method!
                        device, status = db.add_device(
                            hostname=hostname,
                            device_type=device_type,
                            is_active=True  # Assuming new YAML imports are active by default
                        )
                        
                        stats[status] += 1
                        # Print realtime feedback
                        print(f" - [{status.upper()}] {hostname} (Type: {device_type or 'None'})")
                        
                    except Exception as e:
                        stats["errors"] += 1
                        print(f" - [ERROR] Failed to process '{hostname}': {e}")
                        
    except ConnectionError as e:
        print(f"Database connection failed: {e}")
        return

    # 4. Print summary
    print("\n=== Sync Complete ===")
    print(f"Inserted: {stats['inserted']}")
    print(f"Updated:  {stats['updated']}")
    print(f"Ignored:  {stats['ignored']} (Already identical)")
    print(f"Errors:   {stats['errors']}")


# If you want to test it by running this file directly:
if __name__ == "__main__":
    yaml_file_path = "../src/devices.yaml"
    sync_devices_from_yaml(yaml_file_path)