#!/usr/bin/env python3
"""
Network Inventory Database Access Examples

This script demonstrates how to interact with the network_inventory PostgreSQL database.

Install required packages:
    - pip install psycopg-binary pyyaml
    - sudo pacman -Sy python-psycopg

Secure password options:
    1. Environment variable: DB_PASSWORD='pass' python script.py
    2. Ansible vault: password_from='vault', vault_file='path/to/vault'
    3. Config file: password_from='config', config_file='path/to/config.yaml'
"""

import os
import sys
import subprocess
import yaml
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
from typing import List, Dict, Optional


class NetworkInventory:
    """Helper class for network_inventory database operations with secure password handling"""

    def __init__(self, host: str = 'localhost', port: int = 5432,
                 dbname: str = 'network_inventory',
                 user: str = 'netzadmin',
                 password: Optional[str] = None,
                 password_from: str = 'env',
                 vault_file: Optional[str] = None,
                 vault_password_file: str = '~/.ssh/vault_pass_netbox',
                 config_file: Optional[str] = None):
        """
        Initialize database connection with secure password handling

        Args:
            host: Database host (default: localhost)
            port: Database port (default: 5432)
            dbname: Database name
            user: Database user
            password: Database password (NOT RECOMMENDED - use password_from instead)
            password_from: Where to get password from:
                'env' - Environment variable DB_PASSWORD (default)
                'vault' - Ansible vault file (requires vault_file)
                'config' - YAML config file (requires config_file)
                'direct' - Use password parameter (insecure)
            vault_file: Path to Ansible vault file (for password_from='vault')
            vault_password_file: Path to vault password file (default: ~/.ssh/vault_pass_netbox)
            config_file: Path to YAML config file (for password_from='config')

        Raises:
            ValueError: If password cannot be retrieved from specified source
        """
        # Get password based on method
        retrieved_password = self._get_password(
            password, password_from, vault_file, vault_password_file, config_file
        )

        self.conn_params = {
            'host': host,
            'port': port,
            'dbname': dbname,
            'user': user,
            'password': retrieved_password
        }

    def _get_password(self, password: Optional[str], password_from: str,
                     vault_file: Optional[str], vault_password_file: str,
                     config_file: Optional[str]) -> str:
        """
        Retrieve password from specified source

        Args:
            password: Direct password
            password_from: Method to retrieve password
            vault_file: Path to Ansible vault
            vault_password_file: Path to vault password
            config_file: Path to config file

        Returns:
            Retrieved password string

        Raises:
            ValueError: If password cannot be retrieved
        """
        if password_from == 'env':
            return self._get_password_from_env()
        elif password_from == 'vault':
            return self._get_password_from_vault(vault_file, vault_password_file)
        elif password_from == 'config':
            return self._get_password_from_config(config_file)
        elif password_from == 'direct':
            if not password:
                raise ValueError("Password parameter required when password_from='direct'")
            print("WARNING: Using direct password is insecure. Consider using 'env', 'vault', or 'config'.")
            return password
        else:
            raise ValueError(f"Invalid password_from value: {password_from}. "
                           "Use 'env', 'vault', 'config', or 'direct'")

    def _get_password_from_env(self) -> str:
        """Get password from DB_PASSWORD environment variable"""
        password = os.environ.get('DB_PASSWORD')
        if not password:
            raise ValueError(
                "DB_PASSWORD environment variable not set.\n"
                "Usage: DB_PASSWORD='your_password' python script.py"
            )
        return password

    def _get_password_from_vault(self, vault_file: Optional[str],
                                  vault_password_file: str) -> str:
        """
        Get password from Ansible vault file

        Args:
            vault_file: Path to vault file
            vault_password_file: Path to vault password file

        Returns:
            Password from vault

        Raises:
            ValueError: If vault file not specified or ansible-vault command fails
        """
        if not vault_file:
            raise ValueError("vault_file parameter required when password_from='vault'")

        vault_file_path = Path(vault_file).expanduser().resolve()
        vault_password_path = Path(vault_password_file).expanduser().resolve()

        if not vault_file_path.exists():
            raise ValueError(f"Vault file not found: {vault_file_path}")

        if not vault_password_path.exists():
            raise ValueError(f"Vault password file not found: {vault_password_path}")

        try:
            # Use ansible-vault to decrypt and read the vault file
            result = subprocess.run(
                ['ansible-vault', 'view', str(vault_file_path),
                 '--vault-password-file', str(vault_password_path)],
                capture_output=True,
                text=True,
                check=True
            )

            # Parse YAML content
            vault_data = yaml.safe_load(result.stdout)

            # Look for password in vault
            password = vault_data.get('vault_sql_inventory_pass')
            if not password:
                raise ValueError(
                    "vault_sql_inventory_pass not found in vault file. "
                    "Available keys: " + ", ".join(vault_data.keys())
                )

            return password

        except subprocess.CalledProcessError as e:
            raise ValueError(f"Failed to read vault file: {e.stderr}")
        except yaml.YAMLError as e:
            raise ValueError(f"Failed to parse vault YAML: {e}")

    def _get_password_from_config(self, config_file: Optional[str]) -> str:
        """
        Get password from YAML config file

        Args:
            config_file: Path to config file

        Returns:
            Password from config

        Raises:
            ValueError: If config file not specified or cannot be read
        """
        if not config_file:
            raise ValueError("config_file parameter required when password_from='config'")

        config_path = Path(config_file).expanduser().resolve()

        if not config_path.exists():
            raise ValueError(f"Config file not found: {config_path}")

        try:
            with open(config_path, 'r') as f:
                config_data = yaml.safe_load(f)

            password = config_data.get('database', {}).get('password')
            if not password:
                raise ValueError("database.password not found in config file")

            return password

        except yaml.YAMLError as e:
            raise ValueError(f"Failed to parse config YAML: {e}")
        except Exception as e:
            raise ValueError(f"Failed to read config file: {e}")

    def _get_connection(self):
        """Create database connection"""
        return psycopg.connect(**self.conn_params)

    def add_device(self, hostname: str, serial_number: Optional[str] = None,
                   inventory_number: Optional[str] = None,
                   active: bool = True) -> int:
        """
        Add a new device to inventory

        Args:
            hostname: Device hostname (required, unique)
            serial_number: Manufacturer serial number (empty strings converted to NULL)
            inventory_number: Internal inventory tracking number (empty strings converted to NULL)
            active: Whether device is active (default: True)

        Returns:
            Device ID of the newly created record

        Note:
            Empty strings ('') are automatically converted to NULL for serial_number
            and inventory_number to maintain data quality. Use NULL/None to indicate
            missing or unknown values.
        """
        # Convert empty strings to None (NULL in database)
        serial_number = serial_number if serial_number and serial_number.strip() else None
        inventory_number = inventory_number if inventory_number and inventory_number.strip() else None

        query = """
            INSERT INTO devices (hostname, serial_number, inventory_number, active)
            VALUES (%s, %s, %s, %s)
            RETURNING id;
        """

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (hostname, serial_number, inventory_number, active))
                device_id = cur.fetchone()[0]
                conn.commit()
                print(f"\u2713 Added device: {hostname} (ID: {device_id})")
                return device_id

    def get_device(self, hostname: str, serial_number: Optional[str] = None, 
                active_only: bool = True) -> Optional[Dict]:
        """
        Get a specific device by hostname and optionally serial number
        
        Args:
            hostname: Device hostname to search for
            serial_number: Optional serial number for exact match
            active_only: If True, only return active devices (default: True)
        
        Returns:
            Device record as dictionary, or None if not found
            
        Note:
            - If serial_number provided: returns exact match or None
            - If serial_number not provided and active_only=True: returns active device with hostname
            - If serial_number not provided and active_only=False: returns first match (unreliable if duplicates)
        """
        if serial_number:
            # Exact match: hostname + serial number
            query = "SELECT * FROM devices WHERE hostname = %s AND serial_number = %s"
            params = (hostname, serial_number)
        else:
            # Just hostname, optionally filter by active status
            query = "SELECT * FROM devices WHERE hostname = %s"
            params = (hostname,)
            if active_only:
                query += " AND active = TRUE"
        
        query += " LIMIT 1;"
        
        with self._get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, params)
                result = cur.fetchone()
                return dict(result) if result else None

    def get_devices_by_hostname(self, hostname: str, active_only: bool = False) -> List[Dict]:
        """
        Get all devices with the given hostname

        Args:
            hostname: Device hostname to search for
            active_only: If True, only return active devices

        Returns:
            List of device records as dictionaries, may be empty, may contain multiple
        """
        query = "SELECT * FROM devices WHERE hostname = %s"
        if active_only:
            query += " AND active = TRUE"
        query += " ORDER BY active DESC, created_at DESC;" # Active first, then newest

        with self._get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (hostname,))
                return [dict(row) for row in cur.fetchall()]

    def get_device_by_id(self, id: int) -> Optional[Dict]:
        """
        Get device by ID

        Args:
            id: Device id to search for

        Returns:
            Device record as dictionary, or None if not found
        """
        query = "SELECT * FROM devices WHERE id = %s;"

        with self._get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (id,))
                result = cur.fetchone()
                return dict(result) if result else None

    def get_all_devices(self, active_only: bool = False) -> List[Dict]:
        """
        Get all devices from inventory

        Args:
            active_only: If True, return only active devices

        Returns:
            List of device records as dictionaries
        """
        query = "SELECT * FROM devices"
        if active_only:
            query += " WHERE active = TRUE"
        query += " ORDER BY hostname;"

        with self._get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query)
                return [dict(row) for row in cur.fetchall()]

    def update_device(self, device_id: int, **kwargs) -> bool:
        """
        Update device fields by ID

        Args:
            device_id: Device ID to update
            **kwargs: Fields to update (hostname, serial_number, inventory_number, active)

        Returns:
            True if device was updated, False if not found

        Note:
            Empty strings ('') for serial_number and inventory_number are
            automatically converted to NULL for consistency.
        """
        allowed_fields = ['hostname', 'serial_number', 'inventory_number', 'active']
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}

        if not updates:
            return False

        # Convert empty strings to None for serial_number and inventory_number
        for field in ['serial_number', 'inventory_number']:
            if field in updates:
                value = updates[field]
                if isinstance(value, str) and not value.strip():
                    updates[field] = None

        set_clause = ", ".join([f"{k} = %s" for k in updates.keys()])
        query = f"""
            UPDATE devices
            SET {set_clause}, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING id;
        """

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, list(updates.values()) + [device_id])
                result = cur.fetchone()
                conn.commit()

                return result is not None

    def delete_device(self, device_id: int) -> bool:
        """
        Delete device from inventory by ID

        Args:
            device_id: Device ID to delete

        Returns:
            True if device was deleted, False if not found
        """
        query = "DELETE FROM devices WHERE id = %s RETURNING id;"

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (device_id,))
                result = cur.fetchone()
                conn.commit()

                return result is not None

    def search_devices(self, search_term: str) -> List[Dict]:
        """
        Search devices by hostname, serial, or inventory number

        Args:
            search_term: Search term (case-insensitive)

        Returns:
            List of matching device records
        """
        query = """
            SELECT * FROM devices
            WHERE hostname ILIKE %s
               OR serial_number ILIKE %s
               OR inventory_number ILIKE %s
            ORDER BY hostname;
        """
        search_pattern = f"%{search_term}%"

        with self._get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, (search_pattern, search_pattern, search_pattern))
                return [dict(row) for row in cur.fetchall()]


# Example usage
if __name__ == "__main__":
    print("=" * 70)
    print("Network Inventory Database - Secure Password Examples")
    print("=" * 70)

    # METHOD 1: Environment Variable (RECOMMENDED - Most Common)
    # Usage: DB_PASSWORD='your_password' python network_inventory_example.py
    print("\n--- METHOD 1: Environment Variable (Default) ---")
    print("Usage: DB_PASSWORD='pass' python script.py")
    try:
        inv = NetworkInventory(host='localhost')
        print("\u2713 Connected using environment variable")
    except ValueError as e:
        print(f"\u2717 Error: {e}")
        print("\nTrying other methods...\n")

    # METHOD 2: Ansible Vault (RECOMMENDED - Integrates with existing setup)
    print("\n--- METHOD 2: Ansible Vault ---")
    print("Uses your existing Ansible vault configuration")
    try:
        inv = NetworkInventory(
            host='localhost',
            password_from='vault',
            vault_file='group_vars/local/vault',  # or group_vars/hs_netbox/vault
            vault_password_file='~/.ssh/vault_pass_netbox'  # Default
        )
        print("\u2713 Connected using Ansible vault")
    except ValueError as e:
        print(f"\u2717 Error: {e}")
    except Exception as e:
        print(f"\u2717 Error: {e}")

    # METHOD 3: Config File
    print("\n--- METHOD 3: Config File ---")
    print("Uses YAML config file with restricted permissions (chmod 600)")
    try:
        inv = NetworkInventory(
            host='localhost',
            password_from='config',
            config_file='sql_scripts/db_config.yaml'
        )
        print("\u2713 Connected using config file")
    except ValueError as e:
        print(f"\u2717 Error: {e}")
    except Exception as e:
        print(f"\u2717 Error: {e}")

    # METHOD 4: Direct Password (NOT RECOMMENDED - for testing only)
    print("\n--- METHOD 4: Direct Password (INSECURE) ---")
    print("Only use for testing, never commit to git!")
    # Uncomment to test:
    # inv = NetworkInventory(
    #     host='localhost',
    #     password='YOUR_PASSWORD_HERE',
    #     password_from='direct'
    # )

    # If connection successful, demonstrate operations
    try:
        # Try to get a connection (will use the last successful method)
        print("\n" + "=" * 70)
        print("Database Operations Example")
        print("=" * 70)

        # Get all devices
        print("\n=== All Active Devices ===")
        devices = inv.get_all_devices(active_only=True)
        for device in devices:
            print(f"- {device['hostname']}: {device['serial_number']} "
                  f"(Inv: {device['inventory_number']}, Active: {device['active']})")

        # Show only active devices
        print("\n=== Active Devices Only ===")
        active_devices = inv.get_all_devices(active_only=True)
        print(f"Total active devices: {len(active_devices)}")

    except NameError:
        print("\n\u2717 No successful connection established.")
        print("\nPlease use one of the secure password methods:")
        print("  1. DB_PASSWORD='pass' python script.py")
        print("  2. Configure Ansible vault path in the script")
        print("  3. Create db_config.yaml with database credentials")
