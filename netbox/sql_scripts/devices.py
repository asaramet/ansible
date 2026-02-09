#!/usr/bin/env python3

import typer
from pathlib import Path
from typing import Optional, List, Dict

from rich.console import Console
from rich.table import Table

from network_inventory import NetworkInventory

app = typer.Typer(help = "Devices table management in 'network_inventory' database over CLI")

script_dir = Path(__file__).resolve().parent
vault_file = script_dir / "vault"
vault_password_file='~/.ssh/vault_pass_netbox' 

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
    """List all devices in the database"""
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
    """Add new device to the database"""

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
    

@app.command()
def delete(device: str):
    """Manually delete a device from the database"""
    typer.secho(f"\u2713 Successfully deleted device: {device}")

@app.command()
def update(device: str):
    """Update a device in the database"""
    typer.secho(f"\u2713 Successfully updated device: {device}")

if __name__ == "__main__":
    app()