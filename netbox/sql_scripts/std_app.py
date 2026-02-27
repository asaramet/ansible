#!/usr/bin/env python3
"""
Pre defined standard objects for brighter usages
"""

import typer
from pathlib import Path
from typing import Optional

from network_inventory import NetworkInventory

app = typer.Typer(help = "Standard functions")

script_dir = Path(__file__).resolve().parent
project_dir = script_dir.parent
vault_file = script_dir / "vault"
vault_password_file = project_dir / "src" / "keys" / "vault_pass_netbox"

host = "192.168.122.140"
#host = "netbox-bb"

# Global variable to store the inventory instance
inventory: Optional[NetworkInventory] = None

# Callback to initialize once before any command runs
@app.callback()
def initialize_inventory(
    host: str = host,
    vault_file: str = vault_file,
    vault_password_file: str = vault_password_file
):
    """Initialize database connection before running any command"""

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

    return inventory

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