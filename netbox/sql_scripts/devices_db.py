#!/usr/bin/env python3

import typer
from pathlib import Path
from typing import Optional, List, Dict

from rich.console import Console
from rich.table import Table

from network_inventory import NetworkInventory

app = typer.Typer(help = "Devices table management in 'network_inventory' database over CLI")

script_dir = Path(__file__).resolve().parent
project_dir = script_dir.parent
vault_file = script_dir / "vault"
vault_password_file= project_dir / "src" / "keys" / "vault_pass_netbox"

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
    host: str = "192.168.122.140",
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
        typer.secho(f"\u2713 Connected to database on {host} using Ansible vault", fg = typer.colors.GREEN, dim = True)
    except ValueError as e:
        typer.secho(f"\u2717 Configuration Error: {e}", fg = typer.colors.RED, err = True)
        raise typer.Exit(code = 1)
    except Exception as e:
        typer.secho(f"\u2717 Connection Error: {e}", fg = typer.colors.RED, err = True)
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
    new_serial: Optional[str] = None,
    new_inventory: Optional[str] = None
):
    """Update device information"""
    
    # Find the specific device
    device = inventory.get_device(hostname, serial_number, active_only=False)
    
    if not device:
        # Show all devices with this hostname
        all_devices = inventory.get_devices_by_hostname(hostname, active_only=False)
        
        if not all_devices:
            typer.secho(f"\u2717 No device found with hostname '{hostname}'", 
                       fg=typer.colors.RED, err=True)
            return
        
        typer.secho(f"\u2717 Multiple devices found with hostname '{hostname}'. Please specify serial number:", 
                   fg=typer.colors.YELLOW)
        console.print(devices_table(all_devices, "Devices with Same Hostname"))
        return
    
    # Update the device
    # ... update logic here

@app.command()
def deactivate(device_id: str):
    """Mark device as inactive"""
    typer.secho(f"\u2713 Device ID: {device_id}")

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

if __name__ == "__main__":
    app()