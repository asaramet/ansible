#!/usr/bin/env python3

import typer, yaml
from pathlib import Path
from typing import Optional, List, Dict, Union

from rich.console import Console
from rich.table import Table

from network_inventory import NetworkInventory

app = typer.Typer(help = "Devices table management in 'network_inventory' database over CLI")

script_dir = Path(__file__).resolve().parent
project_dir = script_dir.parent
vault_file = script_dir / "vault"
vault_password_file = project_dir / "src" / "keys" / "vault_pass_netbox"

#host = "192.168.122.140"
host = "netbox-bb"
yaml_db = project_dir / 'src' / 'serial_numbers.yaml'

# Global variable to store the inventory instance
inventory: Optional[NetworkInventory] = None

# Console instance to reuse
console = Console()

def devices_table(devices: List[Dist], title: str = "Network Inventory Devices") -> Table:
    """
    Create a Rich table for displaying devices
    
    Args:
        devices: List of device dictionaries
        title: Table title
    
    Returns:
        Rich Table object
    """
    table = Table(title = title)

    table.add_column("ID", style = "cyan", justify = "right")
    table.add_column("Hostname", style = "green", no_wrap = True)
    table.add_column("Serial Number", style = "magenta")
    table.add_column("Inventory Number", style = "magenta")
    table.add_column("Active", style = "yellow", justify = "center")
    table.add_column("Created At", style = "blue")
    table.add_column("Updated At", style = "blue")

    # Add rows
    for device in devices:
        table.add_row(
            str(device['id']),
            device['hostname'],
            device['serial_number'] or "-",
            device['inventory_number'] or "-",
            "\u2713" if device['active'] else "\u2717",
            device['created_at'].strftime("%Y-%m-%d %H:%M") if device['created_at'] else "-",
            device['updated_at'].strftime("%Y-%m-%d %H:%M") if device['updated_at'] else "-"
        )

    return table 

# Callback to initialize once before any command runs
@app.callback()
def initialize(
    ctx: typer.Context,
    host: str = host,
    vault_file: str = vault_file,
    vault_password_file: str = vault_password_file
):
    """Initialize database connection before running any command"""
    global inventory

    try:
        inventory = NetworkInventory(
            host = host,
            password_from = 'vault',
            vault_file = vault_file,
            vault_password_file = vault_password_file
        )
        typer.secho(f"\u2713 Connected to database on {host} using Ansible vault", 
                    fg = typer.colors.GREEN, dim = True)
    except ConnectionError as e:
        # Clean error from NetworkInventory class
        typer.secho(f"\u2717 {e}", fg = typer.colors.RED, err = True)
        raise typer.Exit(code = 1)
    except ValueError as e:
        typer.secho(f"\u2717 Configuration Error: {e}", fg = typer.colors.RED, err = True)
        raise typer.Exit(code = 1)

@app.command()
def list(active_only: bool = False):
    """List all devices"""
    devices = inventory.get_all_devices(active_only = active_only)

    if not devices:
        typer.secho(f"\u2717 No devices found", fg = typer.colors.YELLOW)
        return

    table = devices_table(devices)
    console.print(table)

    typer.secho(f"\u2713 Listed {len(devices)} devices")

@app.command()
def add(
    hostname: str, 
    serial_number: Optional[str] = None, 
    inventory_number: Optional[str] = None
    ):
    """Add new device"""

    # Check for exact duplicate (hostname + serial)
    if serial_number:
        existing_device = inventory.get_device(hostname, serial_number)
        if existing_device:
            typer.secho(f"\u2717 Device already exists with hostname '{hostname}' and serial '{serial_number}'", 
                       fg=typer.colors.RED, err=True)
            console.print(devices_table([existing_device], "Existing Device"))
            return

    # Check if hostname exists (warn user about duplicates)
    devices_with_hostname = inventory.get_devices_by_hostname(hostname)
    if devices_with_hostname:
        typer.secho(f"\u26a0 Warning: {len(devices_with_hostname)} device(s) already exist with hostname '{hostname}'", 
                   fg=typer.colors.YELLOW)
        console.print(devices_table(devices_with_hostname, "Existing Devices with Same Hostname"))
        
        if not typer.confirm("Do you want to add another device with this hostname?"):
            typer.secho("\u2717 Cancelled", fg=typer.colors.YELLOW)
            return

    # Add the device
    device_id = inventory.add_device(hostname, serial_number, inventory_number)
    device = inventory.get_device_by_id(device_id)
    
    if device:
        typer.secho(f"\n\u2713 Successfully added new device '{hostname}' with ID '{device_id}'", 
                   fg=typer.colors.GREEN)
        console.print(devices_table([device], "Added Device"))
    else:
        typer.secho(f"\u2717 Error: Could not retrieve device after adding", 
                   fg=typer.colors.RED, err=True)

    """
    # Check if device already exists
    existing_device = inventory.get_device(hostname)

    if existing_device:
        typer.secho(f"\u2717 Device already exist: {hostname}", fg = typer.colors.RED)
        console.print(devices_table([existing_device], "Existing device"))
        return

    # Add the device
    device_id = inventory.add_device(hostname, serial_number, inventory_number)

    # Retrieve newly added device
    device = inventory.get_device_by_id(device_id)

    if device:
        console.print(devices_table([device], "Added Device"))
    else:
        typer.secho(f"\u2717 Error: Could not retrieve device after adding", fg = typer.colors.RED, err = True)
    """    

@app.command()
def get(hostname: str):
    """Get device by hostname"""
    devices = inventory.get_devices_by_hostname(hostname)

    if devices:
        console.print(devices_table(devices, f"Found {hostname}"))
        return

    typer.secho(f"\u2717 No devices with hostname {hostname} found")

@app.command()
def update(
    hostname: str,
    serial_number: Optional[str] = None,
    new_hostname: Optional[str] = None,
    new_serial: Optional[str] = None,
    new_inventory: Optional[str] = None,
    set_inactive: bool = False,
    set_active: bool = False,
    force: bool = False
):
    """Update device information"""
    
    # Find the specific device
    device = inventory.get_device(hostname, serial_number, active_only=False)
    
    if not device:
        all_devices = inventory.get_devices_by_hostname(hostname, active_only=False)
        
        if not all_devices:
            typer.secho(f"\u2717 No device found with hostname '{hostname}'", 
                       fg=typer.colors.RED, err=True)
            return
        
        typer.secho(f"\u2717 Multiple devices found with hostname '{hostname}'. Please specify serial number:", 
                   fg=typer.colors.YELLOW)
        console.print(devices_table(all_devices, "Devices with Same Hostname"))
        return
    
    # Show current device
    typer.echo("\nCurrent device:")
    console.print(devices_table([device], "Device to Update"))

    # Build updates dictionary
    updates = {}
    changes = []

    if new_hostname:
        updates['hostname'] = new_hostname
        changes.append(f"hostname: '{device['hostname']}' -> {hew_hostname}")

    if new_serial is not None: # don't ignore empty string
        updates['serial_number'] = new_serial
        old_val = device['serial_number'] or 'NULL'
        new_val = new_serial if new_serial else 'NULL'
        changes.append(f"serial_number: '{old_val}' -> '{new_val}'")

    if new_inventory is not None: # don't ignore empty string
        updates['inventory_number'] = new_inventory
        old_val = device['inventory_number'] or 'NULL'
        new_val = new_inventory if new_inventory else 'NULL'
        changes.append(f"inventory_number: '{old_val}' -> '{new_val}'")

    if set_inactive:
        updates['active'] = False
        changes.append(f"active: {device['active']} -> False")
    elif set_active:
        updates['active'] = True
        changes.append(f"active: {device['active']} -> True")

    if not updates:
        types.secho("\u2717 No updates specified", fg=typer.colors.YELLOW)
        return
    
    # Show planned changes
    typer.secho("\nPlanned changes:", fg=typer.colors.CYAN)
    for change in changes:
        typer.echo(f" \u2022 {change}")

    # Confirm unless --force
    if not force:
        if not typer.confirm("\nProceed with update?"):
            typer.secho("\u2717 Update cancelled", fg=typer.colors.YELLOW)
            return
    
    # Perform updates
    success = inventory.update_device(device['id'], **updates)

    if success:
        updated_device = inventory.get_device_by_id(device['id'])
        typer.secho(f"\n\u2713 Successfully updated device with ID {device['id']}",
                    fg=typer.colors.GREEN)
        if updated_device:
            typer.echo("\nUpdated device:")
            console.print(devices_table([updated_device], "After Update"))

    else:
        typer.secho(f"\u2717 Failed to update device", fg=typer.colors.RED, err=True)

@app.command()
def delete(
    hostname: str,
    serial_number: Optional[str] = None,
    force: bool = False
):
    """Delete device"""
    
    # Try to find specific device
    device = inventory.get_device(hostname, serial_number, active_only=False)
    
    if not device:
        # Check if multiple devices exist
        all_devices = inventory.get_devices_by_hostname(hostname, active_only=False)
        
        if not all_devices:
            typer.secho(f"\u2717 No device found with hostname '{hostname}'", 
                       fg=typer.colors.RED, err=True)
            return
        
        if len(all_devices) > 1:
            typer.secho(f"\u2717 Found {len(all_devices)} devices with hostname '{hostname}'. Please specify serial number:", 
                       fg=typer.colors.YELLOW)
            console.print(devices_table(all_devices, "Devices with Same Hostname"))
            return
        
        device = all_devices[0]
    
    # Show device to be deleted
    typer.echo("\nDevice to be deleted:")
    console.print(devices_table([device], "\u26a0 Deleting Device"))
    
    if not force:
        confirm = typer.confirm("\nAre you sure you want to delete this device?")
        if not confirm:
            typer.secho("\u2717 Deletion cancelled", fg=typer.colors.YELLOW)
            return
    
    inventory.delete_device(device['id'])
    typer.secho(f"\n\u2713 Successfully deleted device '{hostname}' (ID: {device['id']})", 
               fg=typer.colors.GREEN)

def load_yaml(file_path: Path = yaml_db) -> Union[Dict, List]:
    """
    Load a YAML file and return its content as a dict or list.
    
    Args:
        file_path: Path to the YAML file
        
    Returns:
        The parsed YAML content (dict or list)
        
    Raises:
        FileNotFoundError: If the file doesn't exist
        yaml.YAMLError: If the file is not valid YAML
    """
    path = Path(file_path)
    
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    with open(path, 'r', encoding='utf-8') as file:
        data = yaml.safe_load(file)
    
    return data

def add_devices_from_list(devices_list: List[Dict[str, str]]) -> Dict[str, any]:
    """
    Add multiple devices from a list of {hostname: serial_number} dictionaries
    
    Args:
        devices_list: List of dicts, each with one key-value pair {hostname: serial_number}
    
    Returns:
        Dictionary with statistics: {added: int, skipped: int, errors: int, details: list}
    """
    results = {
        'added': 0,
        'skipped': 0,
        'errors': 0,
        'details': []
    }
    
    for device_dict in devices_list:
        # Extract hostname and serial from dict
        if not device_dict:
            continue
            
        hostname, serial_number = next(iter(device_dict.items()))
        
        try:
            # Check if device already exists with this hostname and serial
            existing = inventory.get_device(hostname, serial_number, active_only=False)
            
            if existing:
                # Device exists - update to active if needed
                if not existing['active']:
                    inventory.update_device(existing['id'], active=True)
                    results['details'].append({
                        'hostname': hostname,
                        'serial': serial_number,
                        'status': 'reactivated',
                        'id': existing['id']
                    })
                    typer.secho(f"  \u2713 Reactivated: {hostname} (Serial: {serial_number})", 
                               fg=typer.colors.YELLOW)
                else:
                    results['skipped'] += 1
                    results['details'].append({
                        'hostname': hostname,
                        'serial': serial_number,
                        'status': 'already_exists',
                        'id': existing['id']
                    })
                    typer.secho(f"  \u2022 Skipped: {hostname} (Serial: {serial_number}) - already exists", 
                               fg=typer.colors.BLUE, dim=True)
            else:
                # Device doesn't exist - add it
                device_id = inventory.add_device(
                    hostname=hostname,
                    serial_number=serial_number,
                    active=True
                )
                results['added'] += 1
                results['details'].append({
                    'hostname': hostname,
                    'serial': serial_number,
                    'status': 'added',
                    'id': device_id
                })
                typer.secho(f"  \u2713 Added: {hostname} (Serial: {serial_number}, ID: {device_id})", 
                           fg=typer.colors.GREEN)
                
        except Exception as e:
            results['errors'] += 1
            results['details'].append({
                'hostname': hostname,
                'serial': serial_number,
                'status': 'error',
                'error': str(e)
            })
            typer.secho(f"  \u2717 Error adding {hostname}: {e}", 
                       fg=typer.colors.RED, err=True)
    
    return results

@app.command()
def populate():
    """Populate devices from a local yaml file"""
    typer.secho(f"Populating devices database on {host}", fg = typer.colors.GREEN)

    devices = load_yaml()
    add_devices_from_list(devices)

def get_inventory_connection(
    host: str = host,
    vault_file: str = vault_file,
    vault_password_file: str = vault_password_file
) -> NetworkInventory:
    """
    Create and return a NetworkInventory connection
    
    Returns:
        Initialized NetworkInventory instance
    """
    return NetworkInventory(
        host = host,
        password_from = 'vault',
        vault_file = vault_file,
        vault_password_file = vault_password_file
    )

def get_devices_serials(
        active_only: bool = True,
        host: str = host,
        vault_file: str = vault_file,
        vault_password_file: str = vault_password_file
) -> List[Dict[str, str]]:
    """
    Get devices as a list of {hostname: serial_number} dictionaries
    
    Args:
        active_only: If True, return only active devices (default: True)
        host: Database host
        vault_file: Ansible vault file path
        vault_password_file: Vault password file path
    
    Returns:
        Dictionary in format {hostname: serial_number, ...}
    
    Note:
        Devices without serial numbers will have None as the value
    """
    inventory = get_inventory_connection(host, vault_file, vault_password_file)
    devices = inventory.get_all_devices(active_only = active_only)
    
    # Convert to {hostname: serial_number} format
    return {device['hostname']: device['serial_number'] for device in devices}

if __name__ == "__main__":
    app()