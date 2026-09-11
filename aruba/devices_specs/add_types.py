#!/usr/bin/env python3
"""
Add device types to the DB from Ansible output
"""

from device_specs import DeviceSpecifications

def sync_inventory_from_api(api_data):
    # 1. Connect to the database using your class
    db_handler = DeviceSpecifications(
        host="netbox-bb",
        password_from="vault",
        vault_file="path/to/vault",
        vault_password_file="path/to/key"
    )

    with db_handler as db:
        for item in api_data:
            try:
                # 2. Call the class method directly!
                device, status = db.add_device(
                    hostname=item['hostname'],
                    device_type=item['model'],
                    is_active=item['is_active']
                )
                
                # 3. Handle the logic programmatically (no Typer prints!)
                if status == "inserted":
                    # Send a slack message, log to a file, etc.
                    print(f"Log: Added {device['hostname']} to database.")
                    
            except Exception as e:
                # 4. Catch errors without crashing the whole script
                print(f"Failed to process {item['hostname']}: {e}")