#!/usr/bin/env python3
"""
Pre defined standard objects
"""

import typer, yaml
from pathlib import Path
from typing import Optional, List, Dict, Union

from network_inventory import NetworkInventory

app = typer.Typer(help = "Standard functions")

script_dir = Path(__file__).resolve().parent
project_dir = script_dir.parent
vault_file = script_dir / "vault"
vault_password_file = project_dir / "src" / "keys" / "vault_pass_netbox"

#host = "192.168.122.140"
host = "netbox-bb"

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

def get_devices_numbers(
        number = "serial_number",
        active_only: bool = False,
        inactive_only: bool = False,
        host: str = host,
        vault_file: str = vault_file,
        vault_password_file: str = vault_password_file
) -> List[Dict[str, str]]:
    """
    Get devices as a list of {hostname: number} dictionaries
    
    Args:
        number: The number type string,  available:
            - serial_number
            - inventory_number
        active_only: If True, return only active devices (default: True)
        host: Database host
        vault_file: Ansible vault file path
        vault_password_file: Vault password file path
    
    Returns:
        Dictionary in format {hostname: number, ...}
    
    Note:
        Devices without numbers will have None as the value
    """

    inventory = get_inventory_connection(host, vault_file, vault_password_file)
    devices = inventory.get_all_devices(active_only = active_only, inactive_only = inactive_only)
    
    # Convert to {hostname: serial_number} format
    return {device['hostname']: device[number] for device in devices}

def load_yaml(file_path: Path) -> Union[Dict, List]:
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

if __name__ == "__main__":
    app()