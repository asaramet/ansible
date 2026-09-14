#!/usr/bin/env python3
"""
Interact with 'device_specs' table in the postgres database, over CLI

Usage:

- show the help menu:
    ./exec.py --help

- show help for a specific command, like `list`
    ./exec.py [command] --help

    Example:
    ./exec.py list --help

- run a command
    ./exec.py [command]
"""

import typer
from pathlib import Path
from rich.console import Console
from rich.table import Table

from typing import Optional, List, Dict, Any

from device_specs import DeviceSpecifications

script_dir = Path(__file__).resolve().parent
project_dir = script_dir.parent
netbox_dir = project_dir / ".." / "netbox"

# UI Instances
console = Console()
app = typer.Typer(help = "Devices table management in 'device_specs' database over CLI")

def get_db() -> DeviceSpecifications:
    """
    Helper function to instantiate the database connection handler cleanly.
    Exits the CLI gracefully if configuration fails.
    """
    try:
        return DeviceSpecifications()
    except Exception as e:
        typer.secho(f"✗ Configuration Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

@app.command("initialize")
def initialize_table():
    """Initialize the new table if it doesn't exist"""
    db_handler = get_db()

    try:
        # Use the 'with' context manager to safely open and close the connection
        with db_handler as db:
            db.initialize_schema()
            typer.secho(f"✓ Connected to database and schema initialized.", fg=typer.colors.GREEN)

            # Check how many devices currently exist
            devices = db.get_all_devices()
            
            if len(devices) == 0:
                typer.secho("ℹ Table exists but is currently empty.", fg=typer.colors.BLUE)
            else:
                typer.secho(f"ℹ Table exists with {len(devices)} device(s).", fg=typer.colors.BLUE)

    except ConnectionError as e:
        typer.secho(f"✗ {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
    except Exception as e:
        typer.secho(f"✗ Database Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

def output_table(devices: List[Dict[str, Any]], title: str = "Devices Specifications") -> Table:
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
    table.add_column("Type", style = "magenta")
    table.add_column("Active", style = "yellow", justify = "center")
    table.add_column("Created At", style = "blue")
    table.add_column("Updated At", style = "blue")

    # Add rows
    for device in devices:
        table.add_row(
            str(device['id']),
            device['hostname'],
            device['type'] or "-",
            "\u2713" if device['active'] else "\u2717",
            device['created_at'].strftime("%Y-%m-%d %H:%M") if device['created_at'] else "-",
            device['updated_at'].strftime("%Y-%m-%d %H:%M") if device['updated_at'] else "-"
        )

    return table 

@app.command("list")
def list_devices(is_active: Optional[bool] = typer.Option(None, "--active/--inactive", help="Filter by active status")
):
    """List all devices in database"""
    db_handler = get_db()

    try:
        with db_handler as db:
            devices = db.get_all_devices(is_active) 

        if not devices:
            typer.secho(f"\u2717 No devices found", fg = typer.colors.YELLOW)
            return

        table = output_table(devices)
        console.print(table)

        typer.secho(f"\u2713 Listed {len(devices)} devices", fg = typer.colors.GREEN)
    
    except Exception as e:
        typer.secho(f"\u2717 Error fetching devices: {e}", fg = typer.colors.RED, err = True)
        raise typer.Exit(code = 1)

@app.command("add")
def add_device_cmd(
    hostname: str = typer.Argument(..., help="The unique hostname of the device"),
    device_type: Optional[str] = typer.Option(None, "--type", "-t", help="Type or model of the device"),
    is_active: bool = typer.Option(True, "--active/--inactive", help="Set the active state")
):
    """Add a new device, or conditionally update it if it already exists."""
    db_handler = get_db()
    
    try:
        with db_handler as db:
            # Unpack the returned tuple
            device, status = db.add_device(
                hostname=hostname, 
                device_type=device_type, 
                is_active=is_active
            )
            
        # Give smart CLI feedback based on the status!
        if status == "inserted":
            typer.secho(
                f"✓ Successfully added '{hostname}' with ID {device['id']}", 
                fg=typer.colors.GREEN
            )
        elif status == "updated":
            typer.secho(
                f"✓ Updated '{hostname}'. Type is now '{device['type'] or '-'}' and Active is {device['active']}.", 
                fg=typer.colors.CYAN
            )
        elif status == "ignored":
            typer.secho(
                f"ℹ Device '{hostname}' already exists with identical specifications. No changes made.", 
                fg=typer.colors.BLUE
            )
            
    except Exception as e:
        typer.secho(f"✗ Database Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

@app.command("delete")
def delete_device_cmd(
    hostname: Optional[str] = typer.Option(None, "--hostname", help="Hostname of the device to delete"),
    device_id: Optional[int] = typer.Option(None, "--id", help="Database ID of the device to delete")
):
    """Delete a device from the inventory by hostname or ID."""
    
    # 1. Validate CLI inputs
    if not (hostname or device_id) or (hostname and device_id):
        typer.secho("✗ Error: You must provide EXACTLY ONE of --hostname or --id", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
        
    db_handler = get_db()
    
    try:
        with db_handler as db:
            # 2. Call the class method
            deleted_device = db.delete_device(hostname=hostname, device_id=device_id)
            
        # 3. Provide user feedback
        if deleted_device:
            typer.secho(
                f"✓ Successfully deleted device '{deleted_device['hostname']}' (ID: {deleted_device['id']})", 
                fg=typer.colors.GREEN
            )
        else:
            identifier = f"hostname '{hostname}'" if hostname else f"ID {device_id}"
            typer.secho(
                f"ℹ No device found matching {identifier}. Nothing was deleted.", 
                fg=typer.colors.YELLOW
            )
            
    except ValueError as e:
        typer.secho(f"✗ Input Error: {e}", fg=typer.colors.YELLOW, err=True)
        raise typer.Exit(code=1)
    except Exception as e:
        typer.secho(f"✗ Database Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()
